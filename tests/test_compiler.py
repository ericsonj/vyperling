"""Tests for vyperling.compiler — CompileResult dataclass, compile_unit, compile_all."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from vyperling.compiler import CompileResult, compile_all, compile_unit
from vyperling.config import load_config
from vyperling.discoverer import TestUnit
from vyperling.toolchains import get_toolchain


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_proc(returncode: int = 0, stdout: str = "") -> MagicMock:
    m = MagicMock()
    m.returncode = returncode
    m.stdout = stdout
    return m


def _make_config(tmp_path: Path) -> dict:
    (tmp_path / "forge.yml").write_text("project:\n  name: proj\n")
    return load_config(tmp_path / "forge.yml")


def _make_unit(tmp_path: Path, name: str = "uart", with_source: bool = True) -> TestUnit:
    test_file = tmp_path / "test" / f"test_{name}.c"
    test_file.write_text("")
    source_file = None
    if with_source:
        source_file = tmp_path / "src" / f"{name}.c"
        source_file.write_text("")
    return TestUnit(test_file=test_file, source_file=source_file, name=name)


# ---------------------------------------------------------------------------
# TestCompileResult
# ---------------------------------------------------------------------------

class TestCompileResult:
    def test_is_dataclass(self):
        assert dataclasses.is_dataclass(CompileResult)

    def test_has_five_fields(self):
        assert len(dataclasses.fields(CompileResult)) == 5

    def test_field_names(self):
        names = {f.name for f in dataclasses.fields(CompileResult)}
        assert names == {"unit", "binary", "success", "output", "duration_ms"}

    def test_binary_accepts_none(self):
        unit = TestUnit(test_file=Path("t.c"), source_file=None, name="x")
        r = CompileResult(unit=unit, binary=None, success=False, output="", duration_ms=0)
        assert r.binary is None

    def test_success_is_bool(self):
        unit = TestUnit(test_file=Path("t.c"), source_file=None, name="x")
        r = CompileResult(unit=unit, binary=Path("b"), success=True, output="", duration_ms=0)
        assert isinstance(r.success, bool)


# ---------------------------------------------------------------------------
# TestCompileUnit
# ---------------------------------------------------------------------------

class TestCompileUnit:
    @pytest.fixture(autouse=True)
    def setup(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "src").mkdir()
        (tmp_path / "test").mkdir()
        (tmp_path / "mocks").mkdir()
        self.tmp = tmp_path
        self.config = _make_config(tmp_path)
        self.toolchain = get_toolchain("native", {})
        self.build_dir = tmp_path / "build" / "native"
        self.build_dir.mkdir(parents=True)

    def _run(self, unit=None, toolchain=None, coverage=False, verbose=False, proc=None):
        if unit is None:
            unit = _make_unit(self.tmp)
        if toolchain is None:
            toolchain = self.toolchain
        if proc is None:
            proc = _mock_proc()
        with patch("subprocess.run", return_value=proc) as mock_run:
            result = compile_unit(unit, toolchain, self.config, self.build_dir, verbose, coverage)
        return result, mock_run

    def test_cc_is_first_arg(self):
        _, mock_run = self._run()
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == self.toolchain.cc

    def test_binary_in_build_dir(self):
        result, _ = self._run()
        assert result.binary == self.build_dir / "uart"

    def test_unity_c_in_sources(self):
        _, mock_run = self._run()
        cmd = mock_run.call_args[0][0]
        assert any("unity.c" in arg for arg in cmd)

    def test_test_file_in_sources(self):
        unit = _make_unit(self.tmp)
        _, mock_run = self._run(unit=unit)
        cmd = mock_run.call_args[0][0]
        assert str(unit.test_file) in cmd

    def test_source_file_in_sources_when_present(self):
        unit = _make_unit(self.tmp, with_source=True)
        _, mock_run = self._run(unit=unit)
        cmd = mock_run.call_args[0][0]
        assert str(unit.source_file) in cmd

    def test_no_crash_when_source_file_absent(self):
        unit = _make_unit(self.tmp, with_source=False)
        result, mock_run = self._run(unit=unit)
        assert result.success is True
        cmd = mock_run.call_args[0][0]
        assert str(unit.test_file) in cmd

    def test_unity_include_dir_in_flags(self):
        _, mock_run = self._run()
        cmd = mock_run.call_args[0][0]
        assert any(arg.startswith("-I") and "unity" in arg.lower() or
                   arg.startswith("-I") and "vyperling" in arg.lower()
                   for arg in cmd)

    def test_static_flag_when_toolchain_static_true(self):
        tc = get_toolchain("mips32", {})
        _, mock_run = self._run(toolchain=tc)
        cmd = mock_run.call_args[0][0]
        assert "-static" in cmd

    def test_no_static_flag_when_toolchain_static_false(self):
        _, mock_run = self._run()
        cmd = mock_run.call_args[0][0]
        assert "-static" not in cmd

    def test_coverage_flags_native(self):
        _, mock_run = self._run(coverage=True)
        cmd = mock_run.call_args[0][0]
        assert "--coverage" in cmd
        assert "-fprofile-arcs" in cmd
        assert "-ftest-coverage" in cmd

    def test_no_coverage_flags_cross_target(self):
        tc = get_toolchain("mips32", {})
        _, mock_run = self._run(toolchain=tc, coverage=True)
        cmd = mock_run.call_args[0][0]
        assert "--coverage" not in cmd

    def test_no_coverage_flags_when_coverage_false(self):
        _, mock_run = self._run(coverage=False)
        cmd = mock_run.call_args[0][0]
        assert "--coverage" not in cmd

    def test_failure_returncode_gives_success_false(self):
        result, _ = self._run(proc=_mock_proc(returncode=1))
        assert result.success is False

    def test_failure_returncode_gives_binary_none(self):
        result, _ = self._run(proc=_mock_proc(returncode=1))
        assert result.binary is None

    def test_success_returncode_gives_success_true(self):
        result, _ = self._run(proc=_mock_proc(returncode=0))
        assert result.success is True

    def test_output_captured(self):
        result, _ = self._run(proc=_mock_proc(stdout="some compiler output"))
        assert result.output == "some compiler output"

    def test_duration_ms_non_negative(self):
        result, _ = self._run()
        assert result.duration_ms >= 0

    def test_dep_file_written_on_success(self):
        self._run()
        dep_file = self.build_dir / "uart.forge_deps.json"
        assert dep_file.is_file()
        data = json.loads(dep_file.read_text())
        assert isinstance(data, dict)

    def test_dep_file_not_written_on_failure(self):
        self._run(proc=_mock_proc(returncode=1))
        dep_file = self.build_dir / "uart.forge_deps.json"
        assert not dep_file.exists()

    def test_included_mock_c_is_linked(self):
        mock_c = self.tmp / "mocks" / "mock_spi.c"
        mock_c.write_text("")
        unit = _make_unit(self.tmp)
        unit.mocks = ["spi"]
        _, mock_run = self._run(unit=unit)
        cmd = mock_run.call_args[0][0]
        assert any("mock_spi.c" in arg for arg in cmd)

    def test_unincluded_mock_c_is_not_linked(self):
        # A mock present on disk but NOT included by the test must not be linked
        # (would redefine the unit's own source symbols).
        mock_c = self.tmp / "mocks" / "mock_spi.c"
        mock_c.write_text("")
        unit = _make_unit(self.tmp)  # mocks defaults to []
        _, mock_run = self._run(unit=unit)
        cmd = mock_run.call_args[0][0]
        assert not any("mock_spi.c" in arg for arg in cmd)

    def test_cached_result_skips_subprocess(self):
        unit = _make_unit(self.tmp)
        # First compile to populate dep file
        with patch("subprocess.run", return_value=_mock_proc()) as first:
            compile_unit(unit, self.toolchain, self.config, self.build_dir, False, False)
        # Create binary so cache check passes
        (self.build_dir / "uart").write_text("")
        # Second compile — should be cached
        with patch("subprocess.run", return_value=_mock_proc()) as second:
            result = compile_unit(unit, self.toolchain, self.config, self.build_dir, False, False)
        assert not second.called
        assert result.output == "[cached]"
        assert result.success is True

    def test_stale_dep_triggers_recompile(self):
        unit = _make_unit(self.tmp)
        # Write an obviously stale dep file
        dep_file = self.build_dir / "uart.forge_deps.json"
        dep_file.write_text(json.dumps({str(unit.test_file): 0.0}))
        (self.build_dir / "uart").write_text("")
        with patch("subprocess.run", return_value=_mock_proc()) as mock_run:
            compile_unit(unit, self.toolchain, self.config, self.build_dir, False, False)
        assert mock_run.called

    def test_dep_missing_key_triggers_recompile(self):
        unit = _make_unit(self.tmp)
        # Dep file exists but has only one of the required source keys
        dep_file = self.build_dir / "uart.forge_deps.json"
        dep_file.write_text(json.dumps({"nonexistent_key.c": 1.0}))
        (self.build_dir / "uart").write_text("")
        with patch("subprocess.run", return_value=_mock_proc()) as mock_run:
            compile_unit(unit, self.toolchain, self.config, self.build_dir, False, False)
        assert mock_run.called

    def test_dep_oserror_on_stat_triggers_recompile(self):
        unit = _make_unit(self.tmp)
        # Dep file has the key, but source file is deleted before stat → OSError path
        dep_file = self.build_dir / "uart.forge_deps.json"
        mtime = unit.test_file.stat().st_mtime
        dep_file.write_text(json.dumps({str(unit.test_file): mtime}))
        (self.build_dir / "uart").write_text("")
        # Delete the test file so _is_cached hits OSError on stat
        unit.test_file.unlink()
        with patch("subprocess.run", return_value=_mock_proc()) as mock_run:
            compile_unit(unit, self.toolchain, self.config, self.build_dir, False, False)
        assert mock_run.called

    def test_verbose_prints_command(self, capsys):
        unit = _make_unit(self.tmp)
        with patch("subprocess.run", return_value=_mock_proc()):
            compile_unit(unit, self.toolchain, self.config, self.build_dir, verbose=True, coverage=False)
        captured = capsys.readouterr()
        assert "gcc" in captured.out

    def test_no_mock_dir_skips_mock_sources(self):
        import shutil
        shutil.rmtree(self.tmp / "mocks")
        unit = _make_unit(self.tmp)
        _, mock_run = self._run(unit=unit)
        cmd = mock_run.call_args[0][0]
        assert not any("mocks" in arg for arg in cmd)

    def test_support_srcs_linked(self):
        stub = self.tmp / "src" / "stub_helper.c"
        stub.write_text("")
        # Inject support_srcs into config
        self.config["project"]["support_srcs"] = [str(stub)]
        unit = _make_unit(self.tmp)
        _, mock_run = self._run(unit=unit)
        cmd = mock_run.call_args[0][0]
        assert str(stub) in cmd

    def test_support_srcs_missing_file_not_linked(self):
        self.config["project"]["support_srcs"] = ["nonexistent.c"]
        unit = _make_unit(self.tmp)
        _, mock_run = self._run(unit=unit)
        cmd = mock_run.call_args[0][0]
        assert "nonexistent.c" not in cmd

    def test_extra_srcs_linked(self):
        extra = self.tmp / "src" / "extra_helper.c"
        extra.write_text("")
        unit = _make_unit(self.tmp)
        unit.extra_srcs = [extra]
        _, mock_run = self._run(unit=unit)
        cmd = mock_run.call_args[0][0]
        assert str(extra) in cmd

    def test_runner_c_generated_and_linked(self):
        unit = _make_unit(self.tmp)
        _, mock_run = self._run(unit=unit)
        cmd = mock_run.call_args[0][0]
        runner_name = f"{unit.name}_runner.c"
        assert any(runner_name in arg for arg in cmd)

    def test_cexception_absent_by_default(self):
        _, mock_run = self._run()
        cmd = mock_run.call_args[0][0]
        assert not any("CException.c" in arg for arg in cmd)

    def test_cexception_linked_when_enabled(self):
        self.config["compiler"]["cexception"] = True
        _, mock_run = self._run()
        cmd = mock_run.call_args[0][0]
        assert any("CException.c" in arg for arg in cmd)


# ---------------------------------------------------------------------------
# TestCompileAll
# ---------------------------------------------------------------------------

class TestCompileAll:
    @pytest.fixture(autouse=True)
    def setup(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "src").mkdir()
        (tmp_path / "test").mkdir()
        (tmp_path / "mocks").mkdir()
        self.tmp = tmp_path
        self.config = _make_config(tmp_path)
        self.toolchain = get_toolchain("native", {})

    def test_returns_list_same_length(self):
        units = [_make_unit(self.tmp, "uart"), _make_unit(self.tmp, "spi")]
        with patch("subprocess.run", return_value=_mock_proc()):
            results = compile_all(units, self.toolchain, self.config)
        assert len(results) == 2

    def test_results_in_same_order(self):
        units = [_make_unit(self.tmp, "uart"), _make_unit(self.tmp, "spi")]
        with patch("subprocess.run", return_value=_mock_proc()):
            results = compile_all(units, self.toolchain, self.config)
        assert results[0].unit.name == "uart"
        assert results[1].unit.name == "spi"

    def test_build_dir_created(self):
        units = [_make_unit(self.tmp, "uart")]
        expected = self.tmp / "build" / "native"
        assert not expected.exists()
        with patch("subprocess.run", return_value=_mock_proc()):
            compile_all(units, self.toolchain, self.config)
        assert expected.is_dir()

    def test_no_dep_file_triggers_compile(self):
        units = [_make_unit(self.tmp, "uart")]
        with patch("subprocess.run", return_value=_mock_proc()) as mock_run:
            compile_all(units, self.toolchain, self.config)
        assert mock_run.called

    def test_multiple_units_jobs_2(self):
        units = [_make_unit(self.tmp, "uart"), _make_unit(self.tmp, "spi")]
        with patch("subprocess.run", return_value=_mock_proc()):
            results = compile_all(units, self.toolchain, self.config, jobs=2)
        assert len(results) == 2
        assert all(r.success for r in results)

    def test_failed_unit_does_not_stop_others(self):
        units = [_make_unit(self.tmp, "uart"), _make_unit(self.tmp, "spi")]
        side_effects = [_mock_proc(returncode=1), _mock_proc(returncode=0)]
        with patch("subprocess.run", side_effect=side_effects):
            results = compile_all(units, self.toolchain, self.config)
        names = {r.unit.name: r.success for r in results}
        assert names["uart"] is False
        assert names["spi"] is True

    def test_empty_units_returns_empty_list(self):
        with patch("subprocess.run", return_value=_mock_proc()):
            results = compile_all([], self.toolchain, self.config)
        assert results == []

    def test_all_results_are_compile_result(self):
        units = [_make_unit(self.tmp, "uart")]
        with patch("subprocess.run", return_value=_mock_proc()):
            results = compile_all(units, self.toolchain, self.config)
        assert all(isinstance(r, CompileResult) for r in results)
