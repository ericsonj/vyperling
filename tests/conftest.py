"""Shared test fixtures for the vyperling suite.

These are factory fixtures (each returns a callable) consolidating helpers that were
previously duplicated across test modules. They are used by the Step 14 gap-fill tests;
existing modules keep their local helpers untouched to avoid churn on the green suite.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from vyperling.compiler import CompileResult
from vyperling.config import load_config
from vyperling.discoverer import TestUnit
from vyperling.runner import RunResult, TestCase


@pytest.fixture
def mock_proc():
    """Factory for a fake ``subprocess.run`` result (superset of the local variants)."""

    def _make(returncode: int = 0, stdout: str = "", stderr: str = "") -> MagicMock:
        m = MagicMock()
        m.returncode = returncode
        m.stdout = stdout
        m.stderr = stderr
        return m

    return _make


@pytest.fixture
def make_config():
    """Factory: write a minimal forge.yml under a dir and load it."""

    def _make(directory: Path, name: str = "proj", mock_dir: str = "mocks") -> dict:
        path = directory / "forge.yml"
        path.write_text(
            f"project:\n  name: {name}\n  mock_dir: {mock_dir}\n", encoding="utf-8"
        )
        return load_config(path)

    return _make


@pytest.fixture
def make_unit_path():
    """Factory: a pure-Path TestUnit (no filesystem writes)."""

    def _make(name: str = "uart", with_source: bool = True, mocks=None) -> TestUnit:
        return TestUnit(
            test_file=Path(f"test/test_{name}.c"),
            source_file=Path(f"src/{name}.c") if with_source else None,
            name=name,
            mocks=list(mocks or []),
        )

    return _make


@pytest.fixture
def make_unit_fs():
    """Factory: a TestUnit whose test (and optional source) files are written to disk."""

    def _make(directory: Path, name: str = "uart", with_source: bool = True) -> TestUnit:
        test_file = directory / "test" / f"test_{name}.c"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("", encoding="utf-8")
        source_file = None
        if with_source:
            source_file = directory / "src" / f"{name}.c"
            source_file.parent.mkdir(parents=True, exist_ok=True)
            source_file.write_text("", encoding="utf-8")
        return TestUnit(test_file=test_file, source_file=source_file, name=name)

    return _make


@pytest.fixture
def make_tc():
    """Factory for a TestCase."""

    def _make(
        name: str = "test_x",
        *,
        passed: bool = True,
        ignored: bool = False,
        message: str = "",
        file: str = "test/test_uart.c",
        line: int = 1,
    ) -> TestCase:
        return TestCase(
            file=file,
            line=line,
            name=name,
            passed=passed,
            ignored=ignored,
            message=message,
        )

    return _make


@pytest.fixture
def make_rr(make_unit_path):
    """Factory for a RunResult."""

    def _make(
        name: str = "uart",
        *,
        tests=None,
        exit_code: int = 0,
        timed_out: bool = False,
        binary_ok: bool = True,
        stdout: str = "",
        stderr: str = "",
        duration_ms: int = 10,
    ) -> RunResult:
        return RunResult(
            unit=make_unit_path(name),
            binary=Path(f"build/native/{name}") if binary_ok else None,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            duration_ms=duration_ms,
            timed_out=timed_out,
            tests=list(tests or []),
        )

    return _make
