"""Tests for vyperling.coverage — check_coverage_tools, generate_coverage.

No real gcovr/gcov is invoked: shutil.which and subprocess.run are mocked, and a
real empty .gcda file is created so the rglob guard passes.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from vyperling.config import load_config
from vyperling.coverage import check_coverage_tools, generate_coverage
from vyperling.errors import ForgeCoverageError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_proc(returncode: int = 0, stdout: str = "") -> MagicMock:
    m = MagicMock()
    m.returncode = returncode
    m.stdout = stdout
    return m


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
            "vyperling.coverage.subprocess.run", return_value=_mock_proc(0)
        ):
            result = generate_coverage(config, build_dir, build_dir)
        assert result == build_dir / "coverage" / "index.html"

    def test_generate_creates_output_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr("vyperling.coverage.shutil.which", _which_all)
        config = _make_config(tmp_path)
        build_dir = _make_build_dir(tmp_path)
        with patch(
            "vyperling.coverage.subprocess.run", return_value=_mock_proc(0)
        ):
            generate_coverage(config, build_dir, build_dir)
        assert (build_dir / "coverage").is_dir()

    def test_command_construction(self, tmp_path, monkeypatch):
        monkeypatch.setattr("vyperling.coverage.shutil.which", _which_all)
        config = _make_config(tmp_path)
        build_dir = _make_build_dir(tmp_path)
        with patch(
            "vyperling.coverage.subprocess.run", return_value=_mock_proc(0)
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
            "vyperling.coverage.subprocess.run", return_value=_mock_proc(0)
        ) as run:
            generate_coverage(config, build_dir, build_dir)
        cmd = run.call_args[0][0]
        assert any("custom_mocks" in arg for arg in cmd)

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
            "vyperling.coverage.subprocess.run", return_value=_mock_proc(0)
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
