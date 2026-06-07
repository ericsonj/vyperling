"""Tests for vyperling.cli — Click command wiring."""

import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

from vyperling.cli import cli

CUSTOM_TOOLCHAIN_YAML = """\
project:
  name: demo
toolchains:
  myboard:
    description: "My custom board"
    cc: gcc
"""

FAILING_TEST_C = """\
#include "unity.h"
void setUp(void) {}
void tearDown(void) {}
void test_fails(void) { TEST_ASSERT_EQUAL_INT(1, 2); }
"""

gcc_only = pytest.mark.skipif(shutil.which("gcc") is None, reason="gcc not available")


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


# --------------------------------------------------------------------------- #
# new
# --------------------------------------------------------------------------- #

def test_new_creates_project(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["new", "demo"])
        assert result.exit_code == 0, result.output
        assert Path("demo/forge.yml").is_file()


def test_new_existing_dir_exits_1(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        Path("demo").mkdir()
        result = runner.invoke(cli, ["new", "demo"])
        assert result.exit_code == 1


# --------------------------------------------------------------------------- #
# --version
# --------------------------------------------------------------------------- #

def test_version_exits_0_and_shows_version(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "vyperling, version " in result.output
    assert "0.0.1" not in result.output  # regression guard: stale hardcode


def test_version_shows_framework_versions(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["--version"])
    assert "Unity" in result.output
    assert "CMock" in result.output
    assert "CException" in result.output
    unity_line = next(line for line in result.output.splitlines() if "Unity" in line)
    assert "2.6.1" in unity_line


def test_version_matches_installed_metadata(runner: CliRunner) -> None:
    from importlib.metadata import PackageNotFoundError, version as pkg_version

    from vyperling import __version__

    try:
        assert __version__ == pkg_version("vyperling")
    except PackageNotFoundError:
        assert __version__ == "0.0.0+dev"


def test_version_falls_back_when_metadata_missing(monkeypatch) -> None:
    import importlib

    import vyperling

    def _raise(_name):
        from importlib.metadata import PackageNotFoundError

        raise PackageNotFoundError

    monkeypatch.setattr("importlib.metadata.version", _raise)
    importlib.reload(vyperling)
    try:
        assert vyperling.__version__ == "0.0.0+dev"
    finally:
        importlib.reload(vyperling)  # restore real value for subsequent tests


# --------------------------------------------------------------------------- #
# targets
# --------------------------------------------------------------------------- #

def test_targets_without_forge_yml(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["targets"])
        assert result.exit_code == 0
        assert "Built-in targets:" in result.output
        assert "native" in result.output
        assert "Project-defined targets:" in result.output
        assert "(none)" in result.output


def test_targets_with_custom_toolchain(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        Path("forge.yml").write_text(CUSTOM_TOOLCHAIN_YAML, encoding="utf-8")
        result = runner.invoke(cli, ["targets"])
        assert result.exit_code == 0
        assert "myboard" in result.output
        assert "My custom board" in result.output


# --------------------------------------------------------------------------- #
# test — error exit codes
# --------------------------------------------------------------------------- #

def test_test_no_config_exits_2(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["test"])
        assert result.exit_code == 2


def test_test_unknown_target_exits_3(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        import os

        runner.invoke(cli, ["new", "demo"])
        os.chdir("demo")
        result = runner.invoke(cli, ["test", "--target", "zzz"])
        assert result.exit_code == 3


# --------------------------------------------------------------------------- #
# test / build — happy paths (require gcc)
# --------------------------------------------------------------------------- #

@gcc_only
def test_test_happy_path_passes(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        import os

        runner.invoke(cli, ["new", "demo"])
        os.chdir("demo")
        result = runner.invoke(cli, ["test"])
        assert result.exit_code == 0, result.output
        assert "1 passed" in result.output


@gcc_only
def test_test_failing_assertion_exits_1(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        import os

        runner.invoke(cli, ["new", "demo"])
        os.chdir("demo")
        Path("test/test_example.c").write_text(FAILING_TEST_C, encoding="utf-8")
        result = runner.invoke(cli, ["test"])
        assert result.exit_code == 1


@gcc_only
def test_test_output_junit_writes_xml(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        import os

        runner.invoke(cli, ["new", "demo"])
        os.chdir("demo")
        result = runner.invoke(cli, ["test", "--output", "junit"])
        assert result.exit_code == 0, result.output
        assert Path("build/native/results.xml").is_file()


@gcc_only
def test_test_with_mocked_dependency_passes(runner: CliRunner) -> None:
    """End-to-end mock pipeline: a SUT calls a dependency the test mocks.

    `widget.c` depends on `clock_now()` declared in `clock.h`. The test includes
    `mock_clock.h`, so auto-mock generates `mock_clock.{c,h}` and the compiler
    links the mock (not the real `clock.c`) into `test_widget`.
    """
    with runner.isolated_filesystem():
        import os

        runner.invoke(cli, ["new", "demo"])
        os.chdir("demo")
        Path("src/clock.h").write_text("int clock_now(void);\n")
        Path("src/clock.c").write_text(
            '#include "clock.h"\nint clock_now(void) { return 999; }\n'
        )
        Path("src/widget.h").write_text("int widget_tick(void);\n")
        Path("src/widget.c").write_text(
            '#include "widget.h"\n#include "clock.h"\n'
            "int widget_tick(void) { return clock_now() + 1; }\n"
        )
        Path("test/test_widget.c").write_text(
            '#include "unity.h"\n'
            '#include "widget.h"\n'
            '#include "mock_clock.h"\n'
            "void setUp(void) {}\n"
            "void tearDown(void) {}\n"
            "void test_widget_uses_clock(void) {\n"
            "    clock_now_ExpectAndReturn(41);\n"
            "    TEST_ASSERT_EQUAL_INT(42, widget_tick());\n"
            "}\n"
        )
        result = runner.invoke(cli, ["test", "-k", "widget"])
        assert result.exit_code == 0, result.output
        assert "1 passed" in result.output
        assert Path("mocks/mock_clock.c").is_file()


@gcc_only
def test_build_compiles_no_run(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        import os

        runner.invoke(cli, ["new", "demo"])
        os.chdir("demo")
        result = runner.invoke(cli, ["build"])
        assert result.exit_code == 0, result.output
        assert "[OK]" in result.output
        assert "PASS" not in result.output


# --------------------------------------------------------------------------- #
# clean
# --------------------------------------------------------------------------- #

@gcc_only
def test_clean_removes_build(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        import os

        runner.invoke(cli, ["new", "demo"])
        os.chdir("demo")
        runner.invoke(cli, ["test"])
        assert Path("build").is_dir()
        result = runner.invoke(cli, ["clean"])
        assert result.exit_code == 0
        assert not Path("build").exists()


@gcc_only
def test_clean_target_only(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        import os

        runner.invoke(cli, ["new", "demo"])
        os.chdir("demo")
        runner.invoke(cli, ["test"])
        result = runner.invoke(cli, ["clean", "--target", "native"])
        assert result.exit_code == 0
        assert not Path("build/native").exists()


def test_clean_no_build_dir(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        import os

        runner.invoke(cli, ["new", "demo"])
        os.chdir("demo")
        result = runner.invoke(cli, ["clean"])
        assert result.exit_code == 0
        assert "Nothing to clean" in result.output


def test_clean_target_missing_dir(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        import os

        runner.invoke(cli, ["new", "demo"])
        os.chdir("demo")
        result = runner.invoke(cli, ["clean", "--target", "native"])
        assert result.exit_code == 0
        assert "Nothing to clean" in result.output
        assert "build/native" in result.output


def test_clean_no_config_exits_2(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["clean"])
        assert result.exit_code == 2


# --------------------------------------------------------------------------- #
# mock
# --------------------------------------------------------------------------- #

def test_mock_no_headers_echoes(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        import os

        runner.invoke(cli, ["new", "demo"])
        os.chdir("demo")
        result = runner.invoke(cli, ["mock"])
        assert result.exit_code == 0
        assert "No headers to mock." in result.output


def test_mock_missing_config_exits_1(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["mock", "x.h"])
        assert result.exit_code == 1


@gcc_only
def test_mock_single_header_generates(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        import os

        runner.invoke(cli, ["new", "demo"])
        os.chdir("demo")
        Path("src/clock.h").write_text("int clock_now(void);\n")
        result = runner.invoke(cli, ["mock", "src/clock.h"])
        assert result.exit_code == 0, result.output
        assert "Generated" in result.output
        assert Path("mocks/mock_clock.c").is_file()
        assert Path("mocks/mock_clock.h").is_file()


@gcc_only
def test_mock_all_globs_src_headers(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        import os

        runner.invoke(cli, ["new", "demo"])
        os.chdir("demo")
        Path("src/a.h").write_text("int a_fn(void);\n")
        Path("src/b.h").write_text("int b_fn(void);\n")
        result = runner.invoke(cli, ["mock", "--all"])
        assert result.exit_code == 0, result.output
        assert Path("mocks/mock_a.c").is_file()
        assert Path("mocks/mock_b.c").is_file()


# --------------------------------------------------------------------------- #
# test / build — gap-fill (no-tests, warnings, error chains)
# --------------------------------------------------------------------------- #

def _scaffold_and_enter(runner: CliRunner, name: str = "demo") -> None:
    import os

    runner.invoke(cli, ["new", name])
    os.chdir(name)


def test_test_empty_test_dir_reports_none(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        _scaffold_and_enter(runner)
        Path("test/test_example.c").unlink()
        result = runner.invoke(cli, ["test"])
        assert result.exit_code == 0
        assert "No tests found." in result.output


def test_build_empty_test_dir_reports_none(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        _scaffold_and_enter(runner)
        Path("test/test_example.c").unlink()
        result = runner.invoke(cli, ["build"])
        assert result.exit_code == 0
        assert "No tests found." in result.output


def test_coverage_warns_non_native_target(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        _scaffold_and_enter(runner)
        result = runner.invoke(
            cli, ["test", "--target", "mips32", "--coverage", "--no-mock"]
        )
        assert "coverage is native-only; skipping for 'mips32'" in result.output


def test_test_generic_forgeerror_clickexception(runner: CliRunner, monkeypatch) -> None:
    import vyperling.discoverer as discoverer_mod
    from vyperling.errors import ForgeError

    def _boom(*_a, **_k):
        raise ForgeError("xx")

    monkeypatch.setattr(discoverer_mod, "discover", _boom)
    with runner.isolated_filesystem():
        _scaffold_and_enter(runner)
        result = runner.invoke(cli, ["test"])
        assert result.exit_code == 1
        assert "xx" in result.output


def test_build_generic_forgeerror_clickexception(runner: CliRunner, monkeypatch) -> None:
    import vyperling.discoverer as discoverer_mod
    from vyperling.errors import ForgeError

    def _boom(*_a, **_k):
        raise ForgeError("xx")

    monkeypatch.setattr(discoverer_mod, "discover", _boom)
    with runner.isolated_filesystem():
        _scaffold_and_enter(runner)
        result = runner.invoke(cli, ["build"])
        assert result.exit_code == 1
        assert "xx" in result.output


@gcc_only
def test_test_no_mock_skips_generation(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        _scaffold_and_enter(runner)
        Path("src/clock.h").write_text("int clock_now(void);\n")
        Path("test/test_example.c").write_text(
            '#include "unity.h"\n#include "mock_clock.h"\n'
            "void setUp(void) {}\nvoid tearDown(void) {}\n"
            "void test_x(void) {}\n"
        )
        result = runner.invoke(cli, ["test", "--no-mock"])
        # mock not generated -> mock_clock.h missing -> compile fails
        assert not Path("mocks/mock_clock.c").exists()
        assert result.exit_code == 1


@gcc_only
def test_coverage_generation_failure_warns(runner: CliRunner, monkeypatch) -> None:
    import vyperling.coverage as coverage_mod
    from vyperling.errors import ForgeCoverageError

    def _boom(*_a, **_k):
        raise ForgeCoverageError("boom")

    monkeypatch.setattr(coverage_mod, "generate_coverage", _boom)
    with runner.isolated_filesystem():
        _scaffold_and_enter(runner)
        result = runner.invoke(cli, ["test", "--coverage"])
        assert result.exit_code == 0, result.output
        assert "Warning: boom" in result.output


@gcc_only
def test_coverage_success_reports_path(runner: CliRunner) -> None:
    # gcovr is a runtime dep, so coverage generation succeeds on a native run.
    with runner.isolated_filesystem():
        _scaffold_and_enter(runner)
        result = runner.invoke(cli, ["test", "--coverage"])
        assert result.exit_code == 0, result.output
        assert "Coverage report:" in result.output


def test_test_unknown_target_in_build_exits_3(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        _scaffold_and_enter(runner)
        result = runner.invoke(cli, ["build", "--target", "zzz"])
        assert result.exit_code == 3


def test_build_no_config_exits_2(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["build"])
        assert result.exit_code == 2


@gcc_only
def test_test_mock_include_without_matching_header(runner: CliRunner) -> None:
    # A test includes mock_ghost.h but no src/ghost.h exists -> header skipped,
    # no mock generated, exercises the dep-not-found branch in _mock_headers_for_units.
    with runner.isolated_filesystem():
        _scaffold_and_enter(runner)
        Path("test/test_example.c").write_text(
            '#include "unity.h"\n#include "example.h"\n#include "mock_ghost.h"\n'
            "void setUp(void) {}\nvoid tearDown(void) {}\n"
            "void test_x(void) { TEST_ASSERT_EQUAL_INT(5, example_add(2,3)); }\n"
        )
        result = runner.invoke(cli, ["build"])
        # ghost has no header -> no mock_ghost.c generated
        assert not Path("mocks/mock_ghost.c").exists()


@gcc_only
def test_build_reports_compile_failure(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        _scaffold_and_enter(runner)
        # Break the source so compilation fails -> [FAIL] row + exit 1.
        Path("src/example.c").write_text("this is not valid C;\n")
        result = runner.invoke(cli, ["build"])
        assert result.exit_code == 1
        assert "[FAIL]" in result.output


@gcc_only
def test_build_generates_mocks(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        _scaffold_and_enter(runner)
        Path("src/clock.h").write_text("int clock_now(void);\n")
        Path("test/test_example.c").write_text(
            '#include "unity.h"\n#include "mock_clock.h"\n'
            "void setUp(void) {}\nvoid tearDown(void) {}\n"
            "void test_x(void) {}\n"
        )
        result = runner.invoke(cli, ["build"])
        assert result.exit_code == 0, result.output
        assert Path("mocks/mock_clock.c").is_file()


def test_clean_generic_forgeerror_clickexception(runner: CliRunner, monkeypatch) -> None:
    import vyperling.config as config_mod
    from vyperling.errors import ForgeError

    def _boom(*_a, **_k):
        raise ForgeError("xx")

    monkeypatch.setattr(config_mod, "load_config", _boom)
    with runner.isolated_filesystem():
        _scaffold_and_enter(runner)
        result = runner.invoke(cli, ["clean"])
        assert result.exit_code == 1
        assert "xx" in result.output
