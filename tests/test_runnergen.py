"""Tests for vyperling.runnergen — Unity runner generator."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from vyperling.runnergen import extract_tests, generate_runner, render_runner
from vyperling.unity import (
    get_forge_mock_c_path,
    get_forge_mock_include_dir,
    get_unity_c_path,
    get_unity_include_dir,
)

HAVE_GCC = shutil.which("gcc") is not None


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# extract_tests
# ---------------------------------------------------------------------------

class TestExtractTests:
    def test_basic_extraction(self, tmp_path):
        f = _write(
            tmp_path / "test_foo.c",
            "void test_one(void) {}\nvoid test_two(void) {}\nvoid test_three(void) {}\n",
        )
        assert extract_tests(f) == ["test_one", "test_two", "test_three"]

    def test_deduplication(self, tmp_path):
        # Same name declared + defined — forward decl looks like a definition too
        f = _write(
            tmp_path / "test_foo.c",
            "void test_alpha(void);\nvoid test_alpha(void) {}\n",
        )
        result = extract_tests(f)
        assert result.count("test_alpha") == 1

    def test_preserves_order(self, tmp_path):
        f = _write(
            tmp_path / "test_foo.c",
            "void test_c(void){}\nvoid test_a(void){}\nvoid test_b(void){}\n",
        )
        assert extract_tests(f) == ["test_c", "test_a", "test_b"]

    def test_missing_file_returns_empty(self, tmp_path):
        assert extract_tests(tmp_path / "nonexistent.c") == []

    def test_no_tests_in_file(self, tmp_path):
        f = _write(tmp_path / "test_empty.c", "// nothing here\n")
        assert extract_tests(f) == []


# ---------------------------------------------------------------------------
# _has_symbol (via render_runner output)
# ---------------------------------------------------------------------------

class TestHasSymbol:
    def test_setup_detected(self, tmp_path):
        f = _write(
            tmp_path / "test_foo.c",
            "void setUp(void) { /* something */ }\nvoid test_x(void){}\n",
        )
        output = render_runner(f, ["test_x"])
        # If setUp was detected, runner must NOT emit a default stub
        assert "void setUp(void) {}" not in output

    def test_no_setup_generates_default(self, tmp_path):
        f = _write(tmp_path / "test_foo.c", "void test_x(void){}\n")
        output = render_runner(f, ["test_x"])
        assert "void setUp(void) {}" in output

    def test_teardown_detected(self, tmp_path):
        f = _write(
            tmp_path / "test_foo.c",
            "void tearDown(void) {}\nvoid test_x(void){}\n",
        )
        output = render_runner(f, ["test_x"])
        assert "void tearDown(void) {}" not in output


# ---------------------------------------------------------------------------
# render_runner structure
# ---------------------------------------------------------------------------

class TestRenderRunner:
    def test_includes_unity(self, tmp_path):
        f = _write(tmp_path / "test_foo.c", "void test_x(void){}\n")
        output = render_runner(f, ["test_x"])
        assert '#include "unity.h"' in output

    def test_includes_mock_headers(self, tmp_path):
        f = _write(tmp_path / "test_foo.c", "void test_x(void){}\n")
        output = render_runner(f, ["test_x"], mocks=["uart", "gpio"])
        assert '#include "mock_uart.h"' in output
        assert '#include "mock_gpio.h"' in output

    def test_no_mocks_no_mock_includes(self, tmp_path):
        f = _write(tmp_path / "test_foo.c", "void test_x(void){}\n")
        output = render_runner(f, ["test_x"], mocks=[])
        assert '#include "mock_' not in output

    def test_run_test_calls_present(self, tmp_path):
        f = _write(
            tmp_path / "test_foo.c",
            "void test_alpha(void){}\nvoid test_beta(void){}\n",
        )
        output = render_runner(f, ["test_alpha", "test_beta"])
        assert 'run_test(test_alpha, "test_alpha"' in output
        assert 'run_test(test_beta, "test_beta"' in output

    def test_suite_setup_extern(self, tmp_path):
        f = _write(
            tmp_path / "test_foo.c",
            "void suiteSetUp(void){}\nvoid test_x(void){}\n",
        )
        output = render_runner(f, ["test_x"])
        assert "extern void suiteSetUp(void);" in output
        assert "suiteSetUp();" in output


# ---------------------------------------------------------------------------
# generate_runner file I/O
# ---------------------------------------------------------------------------

class TestGenerateRunner:
    def test_creates_file(self, tmp_path):
        f = _write(tmp_path / "test_foo.c", "void test_x(void){}\n")
        out = tmp_path / "build" / "test_foo_runner.c"
        generate_runner(f, out)
        assert out.is_file()

    def test_skips_rewrite_when_unchanged(self, tmp_path):
        f = _write(tmp_path / "test_foo.c", "void test_x(void){}\n")
        out = tmp_path / "build" / "test_foo_runner.c"
        generate_runner(f, out)
        mtime_first = out.stat().st_mtime_ns
        generate_runner(f, out)
        assert out.stat().st_mtime_ns == mtime_first

    def test_returns_path_and_names(self, tmp_path):
        f = _write(
            tmp_path / "test_foo.c",
            "void test_a(void){}\nvoid test_b(void){}\n",
        )
        out = tmp_path / "runner.c"
        path, names = generate_runner(f, out)
        assert path == out
        assert names == ["test_a", "test_b"]


# ---------------------------------------------------------------------------
# Naming convention support
# ---------------------------------------------------------------------------

class TestNamingConventions:
    def test_camelcase_extracts_testFoo(self, tmp_path):
        f = _write(
            tmp_path / "TestFoo.c",
            "void testInit(void) {}\nvoid testRun(void) {}\n",
        )
        result = extract_tests(f, test_prefix="test", test_naming="camelCase")
        assert result == ["testInit", "testRun"]

    def test_camelcase_extracts_TestFoo(self, tmp_path):
        f = _write(
            tmp_path / "TestFoo.c",
            "void TestInit(void) {}\nvoid TestRun(void) {}\n",
        )
        result = extract_tests(f, test_prefix="Test", test_naming="camelCase")
        assert result == ["TestInit", "TestRun"]

    def test_ceedling_pattern_Test_file_test_functions(self, tmp_path):
        # Ceedling uses Test*.c files but void test*() functions (lowercase t).
        # With test_prefix="Test" + camelCase, both Test* and test* are matched.
        f = _write(
            tmp_path / "TestFoo.c",
            "void testInit(void) {}\nvoid testRun(void) {}\n",
        )
        result = extract_tests(f, test_prefix="Test", test_naming="camelCase")
        assert result == ["testInit", "testRun"]

    def test_camelcase_deduplication(self, tmp_path):
        f = _write(
            tmp_path / "TestFoo.c",
            "void testAlpha(void);\nvoid testAlpha(void) {}\n",
        )
        result = extract_tests(f, test_prefix="test", test_naming="camelCase")
        assert result.count("testAlpha") == 1

    def test_mock_prefix_in_runner_includes(self, tmp_path):
        f = _write(tmp_path / "TestFoo.c", "void testX(void){}\n")
        output = render_runner(
            f,
            ["testX"],
            mocks=["Clock", "Timer"],
            mock_prefix="Mock",
        )
        assert '#include "MockClock.h"' in output
        assert '#include "MockTimer.h"' in output
        assert '#include "mock_' not in output

    def test_mock_prefix_in_lifecycle_calls(self, tmp_path):
        f = _write(tmp_path / "TestFoo.c", "void testX(void){}\n")
        output = render_runner(f, ["testX"], mocks=["Clock"], mock_prefix="Mock")
        assert "MockClock_Init();" in output
        assert "MockClock_Verify();" in output
        assert "MockClock_Destroy();" in output

    def test_default_prefix_unchanged(self, tmp_path):
        f = _write(tmp_path / "test_foo.c", "void test_x(void){}\n")
        output = render_runner(f, ["test_x"], mocks=["clock"])
        assert '#include "mock_clock.h"' in output
        assert "mock_clock_Init();" in output


# ---------------------------------------------------------------------------
# Compile check (gated on gcc)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not HAVE_GCC, reason="gcc not installed")
class TestCompiles:
    def test_runner_compiles_with_gcc(self, tmp_path):
        test_src = _write(
            tmp_path / "test_add.c",
            """\
#include "unity.h"
void setUp(void) {}
void tearDown(void) {}
void test_add(void) { TEST_ASSERT_EQUAL_INT(4, 2 + 2); }
""",
        )
        runner_path = tmp_path / "build" / "test_add_runner.c"
        generate_runner(test_src, runner_path, mocks=[])

        binary = tmp_path / "test_add"
        uinc = get_unity_include_dir()
        cmd = [
            "gcc", "-Wall",
            f"-I{uinc}",
            str(test_src), str(runner_path),
            str(get_unity_c_path()), str(get_forge_mock_c_path()),
            f"-I{get_forge_mock_include_dir()}",
            "-o", str(binary),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        assert proc.returncode == 0, proc.stderr

        run = subprocess.run([str(binary)], capture_output=True, text=True)
        assert run.returncode == 0
        assert "OK" in run.stdout
