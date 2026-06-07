"""Tests for vyperling.coverage — check_coverage_tools, generate_coverage.

No real gcovr/gcov is invoked: shutil.which and subprocess.run are mocked, and a
real empty .gcda file is created so the rglob guard passes.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vyperling.config import load_config
from vyperling.coverage import (
    check_coverage_tools,
    generate_coverage,
    parse_coverage_summary,
)
from vyperling.errors import ForgeCoverageError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_proc(returncode: int = 0, stdout: str = "") -> MagicMock:
    m = MagicMock()
    m.returncode = returncode
    m.stdout = stdout
    return m


# A minimal but valid gcovr --json-summary payload.
_FAKE_SUMMARY = {
    "root": ".",
    "line_percent": 80.0,
    "function_percent": 90.0,
    "branch_percent": 70.0,
    "files": [
        {
            "filename": "src/uart.c",
            "line_total": 10,
            "line_covered": 8,
            "line_percent": 80.0,
            "function_total": 2,
            "function_covered": 2,
            "function_percent": 100.0,
            "branch_total": 4,
            "branch_covered": 3,
            "branch_percent": 75.0,
        }
    ],
}


def _run_writes_summary(build_dir: Path, returncode: int = 0, stdout: str = ""):
    """subprocess.run side_effect: write a fake summary.json (as real gcovr
    would via --json-summary), then return a mock proc."""
    import json

    def fake(*_args, **_kwargs) -> MagicMock:
        summary = build_dir / "coverage" / "summary.json"
        summary.parent.mkdir(parents=True, exist_ok=True)
        summary.write_text(json.dumps(_FAKE_SUMMARY))
        return _mock_proc(returncode, stdout)

    return fake


def _make_config(tmp_path: Path, mock_dir: str = "mocks") -> dict:
    (tmp_path / "forge.yml").write_text(
        f"project:\n  name: proj\n  mock_dir: {mock_dir}\n"
    )
    return load_config(tmp_path / "forge.yml")


def _make_build_dir(tmp_path: Path) -> Path:
    """Create build/native with one empty .gcda so the rglob guard passes."""
    build_dir = tmp_path / "build" / "native"
    build_dir.mkdir(parents=True)
    (build_dir / "uart.gcda").write_text("")
    return build_dir


def _which_all(_tool: str) -> str | None:
    return "/usr/bin/" + _tool


def _which_missing(*missing: str):
    def fake(tool: str) -> str | None:
        return None if tool in missing else "/usr/bin/" + tool

    return fake


# ---------------------------------------------------------------------------
# check_coverage_tools
# ---------------------------------------------------------------------------

class TestCheckCoverageTools:
    def test_check_tools_present(self, monkeypatch):
        monkeypatch.setattr("vyperling.coverage.shutil.which", _which_all)
        check_coverage_tools()  # no exception

    def test_check_tools_missing_gcovr(self, monkeypatch):
        monkeypatch.setattr(
            "vyperling.coverage.shutil.which", _which_missing("gcovr")
        )
        with pytest.raises(ForgeCoverageError) as exc:
            check_coverage_tools()
        assert "pip install gcovr" in str(exc.value)

    def test_check_tools_missing_gcov(self, monkeypatch):
        monkeypatch.setattr(
            "vyperling.coverage.shutil.which", _which_missing("gcov")
        )
        with pytest.raises(ForgeCoverageError) as exc:
            check_coverage_tools()
        assert "gcov" in str(exc.value)


# ---------------------------------------------------------------------------
# generate_coverage
# ---------------------------------------------------------------------------

class TestGenerateCoverage:
    def test_generate_returns_index_path(self, tmp_path, monkeypatch):
        monkeypatch.setattr("vyperling.coverage.shutil.which", _which_all)
        config = _make_config(tmp_path)
        build_dir = _make_build_dir(tmp_path)
        with patch(
            "vyperling.coverage.subprocess.run",
            side_effect=_run_writes_summary(build_dir),
        ):
            index, summary = generate_coverage(config, build_dir, build_dir)
        assert index == build_dir / "coverage" / "index.html"
        assert summary.line_percent == 80.0
        assert summary.files[0].filename == "src/uart.c"

    def test_generate_creates_output_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr("vyperling.coverage.shutil.which", _which_all)
        config = _make_config(tmp_path)
        build_dir = _make_build_dir(tmp_path)
        with patch(
            "vyperling.coverage.subprocess.run",
            side_effect=_run_writes_summary(build_dir),
        ):
            generate_coverage(config, build_dir, build_dir)
        assert (build_dir / "coverage").is_dir()

    def test_command_construction(self, tmp_path, monkeypatch):
        monkeypatch.setattr("vyperling.coverage.shutil.which", _which_all)
        config = _make_config(tmp_path)
        build_dir = _make_build_dir(tmp_path)
        with patch(
            "vyperling.coverage.subprocess.run",
            side_effect=_run_writes_summary(build_dir),
        ) as run:
            generate_coverage(config, build_dir, build_dir)
        cmd = run.call_args[0][0]
        assert cmd[0] == "gcovr"
        assert "--html-details" in cmd
        assert "--cobertura" in cmd
        assert "--root" in cmd
        assert r".*/unity\.c$" in cmd
        assert r".*/forge_mock\.c$" in cmd
        assert r"/usr/.*" in cmd
        assert str(build_dir) in cmd

    def test_excludes_mock_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr("vyperling.coverage.shutil.which", _which_all)
        config = _make_config(tmp_path, mock_dir="custom_mocks")
        build_dir = _make_build_dir(tmp_path)
        with patch(
            "vyperling.coverage.subprocess.run",
            side_effect=_run_writes_summary(build_dir),
        ) as run:
            generate_coverage(config, build_dir, build_dir)
        cmd = run.call_args[0][0]
        assert any("custom_mocks" in arg for arg in cmd)

    def test_excludes_generated_runners(self, tmp_path, monkeypatch):
        monkeypatch.setattr("vyperling.coverage.shutil.which", _which_all)
        config = _make_config(tmp_path)
        build_dir = _make_build_dir(tmp_path)
        with patch(
            "vyperling.coverage.subprocess.run",
            side_effect=_run_writes_summary(build_dir),
        ) as run:
            generate_coverage(config, build_dir, build_dir)
        cmd = run.call_args[0][0]
        assert r".*_runner\.c$" in cmd

    def test_excludes_test_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr("vyperling.coverage.shutil.which", _which_all)
        config = _make_config(tmp_path)
        build_dir = _make_build_dir(tmp_path)
        with patch(
            "vyperling.coverage.subprocess.run",
            side_effect=_run_writes_summary(build_dir),
        ) as run:
            generate_coverage(config, build_dir, build_dir)
        cmd = run.call_args[0][0]
        # default test_dir is "test"; exclude pattern is "<test_dir>/.*"
        assert any(arg.startswith("test") and arg.endswith("/.*") for arg in cmd)

    def test_missing_gcda_raises(self, tmp_path, monkeypatch):
        monkeypatch.setattr("vyperling.coverage.shutil.which", _which_all)
        config = _make_config(tmp_path)
        build_dir = tmp_path / "build" / "native"
        build_dir.mkdir(parents=True)  # exists but no .gcda
        with pytest.raises(ForgeCoverageError) as exc:
            generate_coverage(config, build_dir, build_dir)
        assert "No coverage data" in str(exc.value)

    def test_gcovr_failure_raises(self, tmp_path, monkeypatch):
        monkeypatch.setattr("vyperling.coverage.shutil.which", _which_all)
        config = _make_config(tmp_path)
        build_dir = _make_build_dir(tmp_path)
        with patch(
            "vyperling.coverage.subprocess.run",
            return_value=_mock_proc(2, "boom"),
        ):
            with pytest.raises(ForgeCoverageError) as exc:
                generate_coverage(config, build_dir, build_dir)
        msg = str(exc.value)
        assert "boom" in msg
        assert "exit 2" in msg

    def test_cobertura_emitted(self, tmp_path, monkeypatch):
        monkeypatch.setattr("vyperling.coverage.shutil.which", _which_all)
        config = _make_config(tmp_path)
        build_dir = _make_build_dir(tmp_path)
        with patch(
            "vyperling.coverage.subprocess.run",
            side_effect=_run_writes_summary(build_dir),
        ) as run:
            generate_coverage(config, build_dir, build_dir)
        cmd = run.call_args[0][0]
        idx = cmd.index("--cobertura")
        assert cmd[idx + 1].endswith("coverage.xml")

    def test_check_called_before_run(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "vyperling.coverage.shutil.which", _which_missing("gcovr")
        )
        config = _make_config(tmp_path)
        build_dir = _make_build_dir(tmp_path)
        with patch("vyperling.coverage.subprocess.run") as run:
            with pytest.raises(ForgeCoverageError):
                generate_coverage(config, build_dir, build_dir)
        run.assert_not_called()

    def test_json_summary_flag_present(self, tmp_path, monkeypatch):
        monkeypatch.setattr("vyperling.coverage.shutil.which", _which_all)
        config = _make_config(tmp_path)
        build_dir = _make_build_dir(tmp_path)
        with patch(
            "vyperling.coverage.subprocess.run",
            side_effect=_run_writes_summary(build_dir),
        ) as run:
            generate_coverage(config, build_dir, build_dir)
        cmd = run.call_args[0][0]
        idx = cmd.index("--json-summary")
        assert cmd[idx + 1].endswith("summary.json")

    def test_generate_returns_summary(self, tmp_path, monkeypatch):
        monkeypatch.setattr("vyperling.coverage.shutil.which", _which_all)
        config = _make_config(tmp_path)
        build_dir = _make_build_dir(tmp_path)
        with patch(
            "vyperling.coverage.subprocess.run",
            side_effect=_run_writes_summary(build_dir),
        ):
            result = generate_coverage(config, build_dir, build_dir)
        assert isinstance(result, tuple) and len(result) == 2
        index, summary = result
        assert summary.function_percent == 90.0
        assert summary.branch_percent == 70.0


# ---------------------------------------------------------------------------
# parse_coverage_summary
# ---------------------------------------------------------------------------

class TestParseCoverageSummary:
    def test_parses_files_and_totals(self, tmp_path):
        import json

        path = tmp_path / "summary.json"
        path.write_text(json.dumps(_FAKE_SUMMARY))
        summary = parse_coverage_summary(path)
        assert summary.line_percent == 80.0
        assert summary.function_percent == 90.0
        assert summary.branch_percent == 70.0
        assert len(summary.files) == 1
        f = summary.files[0]
        assert f.filename == "src/uart.c"
        assert f.line_covered == 8
        assert f.line_total == 10
        assert f.branch_percent == 75.0

    def test_null_branch_percent_defaults_zero(self, tmp_path):
        import json

        payload = {
            "line_percent": 100.0,
            "function_percent": 100.0,
            "branch_percent": None,
            "files": [
                {
                    "filename": "test/test_uart.c",
                    "line_total": 5,
                    "line_covered": 5,
                    "line_percent": 100.0,
                    "function_percent": 100.0,
                    "branch_percent": None,
                }
            ],
        }
        path = tmp_path / "summary.json"
        path.write_text(json.dumps(payload))
        summary = parse_coverage_summary(path)
        assert summary.branch_percent == 0.0
        assert summary.files[0].branch_percent == 0.0
