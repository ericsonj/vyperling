"""Tests for vyperling.reporter — print_terminal_report, print_summary, write_junit_xml."""

from __future__ import annotations

import io
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from rich.console import Console

import vyperling.reporter as reporter_mod
from vyperling.discoverer import TestUnit
from vyperling.reporter import print_summary, print_terminal_report, write_junit_xml
from vyperling.runner import RunResult, TestCase


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_unit(name: str = "uart") -> TestUnit:
    return TestUnit(
        test_file=Path(f"test/test_{name}.c"),
        source_file=Path(f"src/{name}.c"),
        name=name,
    )


def _make_tc(
    name: str = "test_foo",
    *,
    passed: bool = True,
    ignored: bool = False,
    message: str = "",
) -> TestCase:
    return TestCase(
        file="test/test_uart.c",
        line=10,
        name=name,
        passed=passed,
        ignored=ignored,
        message=message,
    )


def _make_rr(
    name: str = "uart",
    tests: list[TestCase] | None = None,
    *,
    timed_out: bool = False,
    binary_ok: bool = True,
    duration_ms: int = 12,
    stderr: str = "",
) -> RunResult:
    binary = Path(f"build/native/{name}") if binary_ok else None
    return RunResult(
        unit=_make_unit(name),
        binary=binary,
        exit_code=0 if binary_ok else -1,
        stdout="",
        stderr=stderr,
        duration_ms=duration_ms,
        timed_out=timed_out,
        tests=tests or [],
    )


def _capture_summary(run_results, monkeypatch) -> str:
    buf = io.StringIO()
    con = Console(file=buf, highlight=False, markup=True)
    monkeypatch.setattr(reporter_mod, "_console", con)
    print_summary(run_results)
    return buf.getvalue()


def _capture_report(run_results, monkeypatch) -> str:
    buf = io.StringIO()
    con = Console(file=buf, highlight=False, markup=True)
    monkeypatch.setattr(reporter_mod, "_console", con)
    print_terminal_report(run_results)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# print_summary
# ---------------------------------------------------------------------------

class TestPrintSummary:
    def test_all_pass(self, monkeypatch):
        rr = _make_rr(tests=[_make_tc("a"), _make_tc("b")])
        out = _capture_summary([rr], monkeypatch)
        assert "2 passed" in out
        assert "0 failed" in out

    def test_with_failures(self, monkeypatch):
        rr = _make_rr(tests=[
            _make_tc("ok"),
            _make_tc("bad", passed=False, message="Expected 1 was 0"),
        ])
        out = _capture_summary([rr], monkeypatch)
        assert "1 passed" in out
        assert "1 failed" in out

    def test_ignored(self, monkeypatch):
        rr = _make_rr(tests=[
            _make_tc("ok"),
            _make_tc("skip", passed=False, ignored=True),
        ])
        out = _capture_summary([rr], monkeypatch)
        assert "1 ignored" in out

    def test_compile_error_counts_as_failure(self, monkeypatch):
        rr = _make_rr(binary_ok=False)
        out = _capture_summary([rr], monkeypatch)
        assert "1 failed" in out

    def test_timeout_counted_separately(self, monkeypatch):
        rr = _make_rr(timed_out=True)
        out = _capture_summary([rr], monkeypatch)
        assert "1 timed out" in out

    def test_total_ms_shown(self, monkeypatch):
        rr = _make_rr(duration_ms=500, tests=[_make_tc()])
        out = _capture_summary([rr], monkeypatch)
        assert "0.5s" in out


# ---------------------------------------------------------------------------
# print_terminal_report
# ---------------------------------------------------------------------------

class TestPrintTerminalReport:
    def test_smoke_no_exception(self, monkeypatch):
        rr = _make_rr(tests=[_make_tc("foo"), _make_tc("bar", passed=False, message="boom")])
        _capture_report([rr], monkeypatch)  # must not raise

    def test_compile_error_row(self, monkeypatch):
        rr = _make_rr(binary_ok=False, stderr="undefined symbol")
        out = _capture_report([rr], monkeypatch)
        assert "COMPILE ERROR" in out
        assert "undefined symbol" in out

    def test_timeout_row(self, monkeypatch):
        rr = _make_rr(timed_out=True)
        out = _capture_report([rr], monkeypatch)
        assert "TIMEOUT" in out

    def test_pass_row(self, monkeypatch):
        rr = _make_rr(tests=[_make_tc("test_ok")])
        out = _capture_report([rr], monkeypatch)
        assert "test_ok" in out
        assert "PASS" in out

    def test_fail_message_shown(self, monkeypatch):
        rr = _make_rr(tests=[_make_tc("test_bad", passed=False, message="Expected 0 was 1")])
        out = _capture_report([rr], monkeypatch)
        assert "Expected 0 was 1" in out

    def test_ignore_label_shown(self, monkeypatch):
        rr = _make_rr(tests=[_make_tc("test_skipme", passed=False, ignored=True)])
        out = _capture_report([rr], monkeypatch)
        assert "IGNORE" in out

    def test_multiple_reports_separated(self, monkeypatch):
        rr1 = _make_rr("uart", tests=[_make_tc("test_a")])
        rr2 = _make_rr("spi", tests=[_make_tc("test_b")])
        out = _capture_report([rr1, rr2], monkeypatch)
        assert "uart" in out and "spi" in out


# ---------------------------------------------------------------------------
# write_junit_xml
# ---------------------------------------------------------------------------

class TestWriteJunitXml:
    def _xml(self, run_results, tmp_path) -> ET.Element:
        out = tmp_path / "results.xml"
        write_junit_xml(run_results, out)
        return ET.fromstring(out.read_text())

    def test_pass_no_failure_elements(self, tmp_path):
        rr = _make_rr(tests=[_make_tc("test_ok")])
        root = self._xml([rr], tmp_path)
        assert root.find(".//failure") is None
        assert root.find(".//error") is None

    def test_fail_has_failure_element(self, tmp_path):
        rr = _make_rr(tests=[_make_tc("test_bad", passed=False, message="Expected 1 was 0")])
        root = self._xml([rr], tmp_path)
        failure = root.find(".//failure")
        assert failure is not None
        assert failure.get("message") == "Expected 1 was 0"

    def test_compile_error_has_error_element(self, tmp_path):
        rr = _make_rr(binary_ok=False, stderr="link error")
        root = self._xml([rr], tmp_path)
        suite = root.find("testsuite")
        assert suite.get("errors") == "1"
        err = suite.find("error")
        assert err is not None
        assert "link error" in (err.text or "")

    def test_timeout_has_error_element(self, tmp_path):
        rr = _make_rr(timed_out=True)
        root = self._xml([rr], tmp_path)
        suite = root.find("testsuite")
        assert suite.get("errors") == "1"
        err = suite.find("error")
        assert err is not None
        assert err.get("type") == "timeout"

    def test_attributes_counts(self, tmp_path):
        rr = _make_rr(tests=[
            _make_tc("ok"),
            _make_tc("fail", passed=False, message="x"),
            _make_tc("skip", passed=False, ignored=True),
        ])
        root = self._xml([rr], tmp_path)
        suite = root.find("testsuite")
        assert suite.get("tests") == "3"
        assert suite.get("failures") == "1"
        assert suite.get("skipped") == "1"
        assert suite.get("errors") == "0"

    def test_classname_set(self, tmp_path):
        rr = _make_rr(name="spi", tests=[_make_tc("test_spi_init")])
        root = self._xml([rr], tmp_path)
        case = root.find(".//testcase")
        assert case.get("classname") == "spi"

    def test_multiple_suites(self, tmp_path):
        rr1 = _make_rr("uart", tests=[_make_tc("a")])
        rr2 = _make_rr("spi", tests=[_make_tc("b")])
        root = self._xml([rr1, rr2], tmp_path)
        suites = root.findall("testsuite")
        assert len(suites) == 2
        names = {s.get("name") for s in suites}
        assert names == {"uart", "spi"}

    def test_xml_declaration_written(self, tmp_path):
        rr = _make_rr(tests=[_make_tc()])
        out = tmp_path / "results.xml"
        write_junit_xml([rr], out)
        content = out.read_text()
        assert content.startswith("<?xml")
