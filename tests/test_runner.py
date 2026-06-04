"""Tests for vyperling.runner — TestCase, RunResult, _parse_unity_output, run_binary, run_all."""

from __future__ import annotations

import dataclasses
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vyperling.compiler import CompileResult
from vyperling.discoverer import TestUnit
from vyperling.runner import RunResult, TestCase, _parse_unity_output, run_all, run_binary
from vyperling.toolchains import get_toolchain


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_proc(returncode: int = 0, stdout: str = "", stderr: str = "") -> MagicMock:
    m = MagicMock()
    m.returncode = returncode
    m.stdout = stdout
    m.stderr = stderr
    return m


def _make_unit(name: str = "uart") -> TestUnit:
    return TestUnit(
        test_file=Path(f"test/test_{name}.c"),
        source_file=Path(f"src/{name}.c"),
        name=name,
    )


def _make_cr(name: str = "uart", success: bool = True) -> CompileResult:
    binary = Path(f"build/native/{name}") if success else None
    return CompileResult(
        unit=_make_unit(name),
        binary=binary,
        success=success,
        output="",
        duration_ms=10,
    )


# ---------------------------------------------------------------------------
# TestRunResultDataclass
# ---------------------------------------------------------------------------

class TestRunResultDataclass:
    def test_is_dataclass(self):
        assert dataclasses.is_dataclass(RunResult)

    def test_has_eight_fields(self):
        assert len(dataclasses.fields(RunResult)) == 8

    def test_field_names(self):
        names = {f.name for f in dataclasses.fields(RunResult)}
        assert names == {"unit", "binary", "exit_code", "stdout", "stderr", "duration_ms", "timed_out", "tests"}

    def test_binary_accepts_none(self):
        r = RunResult(
            unit=_make_unit(),
            binary=None,
            exit_code=-1,
            stdout="",
            stderr="",
            duration_ms=0,
            timed_out=False,
            tests=[],
        )
        assert r.binary is None

    def test_tests_accepts_empty_list(self):
        r = RunResult(
            unit=_make_unit(),
            binary=Path("b"),
            exit_code=0,
            stdout="",
            stderr="",
            duration_ms=0,
            timed_out=False,
            tests=[],
        )
        assert r.tests == []

    def test_timed_out_accepts_bool(self):
        r = RunResult(
            unit=_make_unit(),
            binary=None,
            exit_code=-1,
            stdout="",
            stderr="",
            duration_ms=0,
            timed_out=False,
            tests=[],
        )
        assert isinstance(r.timed_out, bool)


# ---------------------------------------------------------------------------
# TestTestCaseDataclass
# ---------------------------------------------------------------------------

class TestTestCaseDataclass:
    def test_is_dataclass(self):
        assert dataclasses.is_dataclass(TestCase)

    def test_has_six_fields(self):
        assert len(dataclasses.fields(TestCase)) == 6

    def test_field_names(self):
        names = {f.name for f in dataclasses.fields(TestCase)}
        assert names == {"file", "line", "name", "passed", "ignored", "message"}

    def test_pass_case_fields(self):
        tc = TestCase(file="test/test_x.c", line=1, name="test_a", passed=True, ignored=False, message="")
        assert tc.passed is True
        assert tc.ignored is False

    def test_fail_case_fields(self):
        tc = TestCase(file="test/test_x.c", line=1, name="test_a", passed=False, ignored=False, message="err")
        assert tc.passed is False
        assert tc.ignored is False

    def test_ignore_case_fields(self):
        tc = TestCase(file="test/test_x.c", line=1, name="test_a", passed=False, ignored=True, message="")
        assert tc.passed is False
        assert tc.ignored is True


# ---------------------------------------------------------------------------
# TestParseUnityOutput
# ---------------------------------------------------------------------------

class TestParseUnityOutput:
    def test_empty_string_returns_empty(self):
        assert _parse_unity_output("") == []

    def test_non_unity_lines_returns_empty(self):
        out = "some random output\nOK\n3 Tests 0 Failures 0 Ignored\nFAIL"
        assert _parse_unity_output(out) == []

    def test_pass_line_parsed(self):
        cases = _parse_unity_output("test/test_uart.c:42:test_init:PASS")
        assert len(cases) == 1
        tc = cases[0]
        assert tc.file == "test/test_uart.c"
        assert tc.line == 42
        assert tc.name == "test_init"
        assert tc.passed is True
        assert tc.ignored is False
        assert tc.message == ""

    def test_fail_line_parsed(self):
        cases = _parse_unity_output("test/test_uart.c:58:test_send:FAIL: Expected 0 but was 1")
        assert len(cases) == 1
        tc = cases[0]
        assert tc.passed is False
        assert tc.ignored is False
        assert tc.message == "Expected 0 but was 1"

    def test_ignore_line_no_message(self):
        cases = _parse_unity_output("test/test_uart.c:71:test_todo:IGNORE")
        assert len(cases) == 1
        tc = cases[0]
        assert tc.ignored is True
        assert tc.message == ""

    def test_ignore_line_with_message(self):
        cases = _parse_unity_output("test/test_uart.c:80:test_todo:IGNORE: Not implemented")
        assert len(cases) == 1
        tc = cases[0]
        assert tc.ignored is True
        assert tc.message == "Not implemented"

    def test_multiple_lines_all_parsed(self):
        out = (
            "test/test_x.c:1:test_a:PASS\n"
            "test/test_x.c:2:test_b:FAIL: oops\n"
            "test/test_x.c:3:test_c:IGNORE"
        )
        cases = _parse_unity_output(out)
        assert len(cases) == 3
        assert cases[0].passed is True
        assert cases[1].passed is False
        assert cases[2].ignored is True

    def test_fail_message_with_colons(self):
        cases = _parse_unity_output("test/test_x.c:10:test_y:FAIL: Expected: 0 Was: 1")
        assert cases[0].message == "Expected: 0 Was: 1"

    def test_ansi_pass_stripped(self):
        cases = _parse_unity_output("test/test_x.c:5:test_a:\033[42mPASS\033[0m")
        assert len(cases) == 1
        assert cases[0].passed is True

    def test_ansi_fail_stripped(self):
        cases = _parse_unity_output("test/test_x.c:5:test_a:\033[41mFAIL\033[0m: msg")
        assert len(cases) == 1
        assert cases[0].passed is False
        assert cases[0].message == "msg"

    def test_ansi_ignore_stripped(self):
        cases = _parse_unity_output("test/test_x.c:5:test_a:\033[43mIGNORE\033[0m")
        assert len(cases) == 1
        assert cases[0].ignored is True

    def test_mixed_ansi_and_plain(self):
        out = (
            "test/test_x.c:1:test_a:\033[42mPASS\033[0m\n"
            "test/test_x.c:2:test_b:FAIL: plain fail"
        )
        cases = _parse_unity_output(out)
        assert len(cases) == 2

    def test_line_number_parsed_as_int(self):
        cases = _parse_unity_output("test/test_x.c:42:test_a:PASS")
        assert isinstance(cases[0].line, int)
        assert cases[0].line == 42

    def test_nested_path_in_file_field(self):
        cases = _parse_unity_output("test/subdir/test_x.c:1:test_a:PASS")
        assert cases[0].file == "test/subdir/test_x.c"

    def test_ok_line_not_parsed(self):
        assert _parse_unity_output("OK") == []

    def test_unity_summary_line_not_parsed(self):
        assert _parse_unity_output("3 Tests 1 Failures 0 Ignored") == []


# ---------------------------------------------------------------------------
# TestRunBinary
# ---------------------------------------------------------------------------

class TestRunBinary:
    @pytest.fixture(autouse=True)
    def setup(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        self.native = get_toolchain("native", {})
        self.mips32 = get_toolchain("mips32", {})
        self.mips32r5 = get_toolchain("mips32r5", {})

    def _run(self, cr=None, toolchain=None, timeout_s=30, proc=None):
        if cr is None:
            cr = _make_cr()
        if toolchain is None:
            toolchain = self.native
        if proc is None:
            proc = _mock_proc()
        with patch("subprocess.run", return_value=proc) as mock_run:
            result = run_binary(cr, toolchain, timeout_s)
        return result, mock_run

    def test_failed_compile_returns_synthetic(self):
        result, mock_run = self._run(cr=_make_cr(success=False))
        assert result.exit_code == -1
        assert result.timed_out is False
        assert result.stdout == ""
        assert result.stderr == ""
        assert result.tests == []
        mock_run.assert_not_called()

    def test_none_binary_with_success_true_returns_synthetic(self):
        cr = CompileResult(unit=_make_unit(), binary=None, success=True, output="", duration_ms=0)
        result, mock_run = self._run(cr=cr)
        assert result.exit_code == -1
        mock_run.assert_not_called()

    def test_synthetic_binary_is_none(self):
        result, _ = self._run(cr=_make_cr(success=False))
        assert result.binary is None

    def test_synthetic_subprocess_not_called(self):
        _, mock_run = self._run(cr=_make_cr(success=False))
        mock_run.assert_not_called()

    def test_native_cmd_is_binary_only(self):
        cr = _make_cr()
        _, mock_run = self._run(cr=cr, toolchain=self.native)
        cmd = mock_run.call_args[0][0]
        assert cmd == [str(cr.binary)]

    def test_emulator_cmd_includes_emulator(self):
        _, mock_run = self._run(toolchain=self.mips32)
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "qemu-mips"

    def test_emulator_cmd_binary_at_end(self):
        cr = _make_cr()
        _, mock_run = self._run(cr=cr, toolchain=self.mips32)
        cmd = mock_run.call_args[0][0]
        assert cmd[-1] == str(cr.binary)

    def test_emulator_args_included(self):
        _, mock_run = self._run(toolchain=self.mips32r5)
        cmd = mock_run.call_args[0][0]
        assert "-cpu" in cmd
        assert "P5600" in cmd

    def test_sysroot_prepends_L_flag(self):
        from vyperling.toolchains import Toolchain
        tc = Toolchain(
            name="custom", description="", cc="gcc", ar="ar",
            cflags=[], emulator="qemu-mips", emulator_args=[],
            sysroot="/usr/mips-linux-gnu", static=True,
        )
        _, mock_run = self._run(toolchain=tc)
        cmd = mock_run.call_args[0][0]
        assert "-L" in cmd
        assert "/usr/mips-linux-gnu" in cmd
        l_idx = cmd.index("-L")
        assert cmd[l_idx + 1] == "/usr/mips-linux-gnu"

    def test_no_sysroot_no_L_flag(self):
        _, mock_run = self._run(toolchain=self.mips32)
        cmd = mock_run.call_args[0][0]
        assert "-L" not in cmd

    def test_stdout_captured_separately(self):
        result, _ = self._run(proc=_mock_proc(stdout="hello"))
        assert result.stdout == "hello"

    def test_stderr_captured_separately(self):
        result, _ = self._run(proc=_mock_proc(stderr="error"))
        assert result.stderr == "error"

    def test_exit_code_zero(self):
        result, _ = self._run(proc=_mock_proc(returncode=0))
        assert result.exit_code == 0

    def test_exit_code_nonzero(self):
        result, _ = self._run(proc=_mock_proc(returncode=1))
        assert result.exit_code == 1

    def test_timed_out_false_on_success(self):
        result, _ = self._run()
        assert result.timed_out is False

    def test_duration_ms_non_negative(self):
        result, _ = self._run()
        assert result.duration_ms >= 0

    def test_subprocess_called_with_pipe_stdout(self):
        _, mock_run = self._run()
        kwargs = mock_run.call_args[1]
        assert kwargs["stdout"] == subprocess.PIPE

    def test_subprocess_called_with_pipe_stderr(self):
        _, mock_run = self._run()
        kwargs = mock_run.call_args[1]
        assert kwargs["stderr"] == subprocess.PIPE

    def test_subprocess_called_with_text_true(self):
        _, mock_run = self._run()
        kwargs = mock_run.call_args[1]
        assert kwargs["text"] is True

    def test_subprocess_called_with_timeout(self):
        _, mock_run = self._run(timeout_s=30)
        kwargs = mock_run.call_args[1]
        assert kwargs["timeout"] == 30

    def test_unit_preserved(self):
        cr = _make_cr()
        result, _ = self._run(cr=cr)
        assert result.unit is cr.unit

    def test_binary_preserved(self):
        cr = _make_cr()
        result, _ = self._run(cr=cr)
        assert result.binary == cr.binary

    def test_unity_output_parsed_into_tests(self):
        out = "test/test_uart.c:1:test_a:PASS\ntest/test_uart.c:2:test_b:FAIL: oops"
        result, _ = self._run(proc=_mock_proc(stdout=out))
        assert len(result.tests) == 2
        assert isinstance(result.tests[0], TestCase)

    def test_passing_tests_parsed(self):
        result, _ = self._run(proc=_mock_proc(stdout="test/test_x.c:1:test_a:PASS"))
        assert result.tests[0].passed is True

    def test_failing_tests_parsed(self):
        result, _ = self._run(proc=_mock_proc(stdout="test/test_x.c:1:test_a:FAIL: bad"))
        assert result.tests[0].passed is False

    def test_no_unity_output_gives_empty_tests(self):
        result, _ = self._run(proc=_mock_proc(stdout="no unity here"))
        assert result.tests == []


# ---------------------------------------------------------------------------
# TestRunBinaryTimeout
# ---------------------------------------------------------------------------

class TestRunBinaryTimeout:
    @pytest.fixture(autouse=True)
    def setup(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        self.native = get_toolchain("native", {})

    def _run_timeout(self, exc_stdout=None, exc_stderr=None):
        cr = _make_cr()
        exc = subprocess.TimeoutExpired(cmd=[str(cr.binary)], timeout=30)
        exc.stdout = exc_stdout
        exc.stderr = exc_stderr
        with patch("subprocess.run", side_effect=exc):
            result = run_binary(cr, self.native, timeout_s=30)
        return result

    def test_timed_out_true(self):
        result = self._run_timeout()
        assert result.timed_out is True

    def test_exit_code_minus_one(self):
        result = self._run_timeout()
        assert result.exit_code == -1

    def test_partial_stdout_captured(self):
        result = self._run_timeout(exc_stdout="partial output")
        assert result.stdout == "partial output"

    def test_partial_stderr_captured(self):
        result = self._run_timeout(exc_stderr="partial err")
        assert result.stderr == "partial err"

    def test_stdout_none_gives_empty_string(self):
        result = self._run_timeout(exc_stdout=None)
        assert result.stdout == ""

    def test_stderr_none_gives_empty_string(self):
        result = self._run_timeout(exc_stderr=None)
        assert result.stderr == ""

    def test_duration_ms_non_negative(self):
        result = self._run_timeout()
        assert result.duration_ms >= 0

    def test_tests_empty_on_timeout(self):
        result = self._run_timeout(exc_stdout="not a unity line")
        assert result.tests == []


# ---------------------------------------------------------------------------
# TestRunAll
# ---------------------------------------------------------------------------

class TestRunAll:
    @pytest.fixture(autouse=True)
    def setup(self, monkeypatch, tmp_path):
        monkeypatch.chdir(tmp_path)
        self.native = get_toolchain("native", {})

    def test_empty_list_returns_empty(self):
        with patch("subprocess.run", return_value=_mock_proc()):
            results = run_all([], self.native)
        assert results == []

    def test_returns_list_of_run_results(self):
        crs = [_make_cr("uart"), _make_cr("spi")]
        with patch("subprocess.run", return_value=_mock_proc()):
            results = run_all(crs, self.native)
        assert all(isinstance(r, RunResult) for r in results)

    def test_count_matches_input(self):
        crs = [_make_cr("uart"), _make_cr("spi"), _make_cr("adc")]
        with patch("subprocess.run", return_value=_mock_proc()):
            results = run_all(crs, self.native)
        assert len(results) == 3

    def test_results_in_order(self):
        crs = [_make_cr("uart"), _make_cr("spi")]
        with patch("subprocess.run", return_value=_mock_proc()):
            results = run_all(crs, self.native)
        assert results[0].unit.name == "uart"
        assert results[1].unit.name == "spi"

    def test_failed_compile_gives_synthetic(self):
        crs = [_make_cr("uart", success=False)]
        with patch("subprocess.run", return_value=_mock_proc()):
            results = run_all(crs, self.native)
        assert results[0].exit_code == -1

    def test_failed_compile_does_not_stop_others(self):
        crs = [_make_cr("uart", success=False), _make_cr("spi", success=True)]
        with patch("subprocess.run", return_value=_mock_proc(returncode=0)):
            results = run_all(crs, self.native)
        assert len(results) == 2
        assert results[1].exit_code == 0

    def test_subprocess_called_once_per_successful(self):
        crs = [_make_cr("uart", success=True), _make_cr("spi", success=False), _make_cr("adc", success=True)]
        with patch("subprocess.run", return_value=_mock_proc()) as mock_run:
            run_all(crs, self.native)
        assert mock_run.call_count == 2

    def test_custom_timeout_passed_through(self):
        crs = [_make_cr()]
        with patch("subprocess.run", return_value=_mock_proc()) as mock_run:
            run_all(crs, self.native, timeout_s=5)
        assert mock_run.call_args[1]["timeout"] == 5

    def test_serial_execution_order(self):
        crs = [_make_cr("uart"), _make_cr("spi")]
        procs = [_mock_proc(stdout="uart output"), _mock_proc(stdout="spi output")]
        with patch("subprocess.run", side_effect=procs):
            results = run_all(crs, self.native)
        assert results[0].stdout == "uart output"
        assert results[1].stdout == "spi output"
