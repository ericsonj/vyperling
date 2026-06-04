"""vyperling.reporter — rich terminal output + JUnit XML writer."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from rich import box
from rich.console import Console
from rich.table import Table

from vyperling.runner import RunResult, TestCase

_console = Console()


def print_terminal_report(run_results: list[RunResult]) -> None:
    for i, rr in enumerate(run_results):
        table = Table(
            title=rr.unit.name,
            box=box.SIMPLE_HEAD,
            show_header=True,
            header_style="bold",
        )
        table.add_column("Test", justify="left", no_wrap=False)
        table.add_column("Result", justify="center", width=8)
        table.add_column("ms", justify="right", width=6)

        if rr.binary is None:
            table.add_row("[red]COMPILE ERROR[/red]", "", "")
            if rr.stderr.strip():
                table.add_row(f"[dim]{rr.stderr.strip()}[/dim]", "", "")
        elif rr.timed_out:
            table.add_row(rr.unit.name, "[yellow]TIMEOUT[/yellow]", str(rr.duration_ms))
        else:
            n = max(len(rr.tests), 1)
            per_ms = rr.duration_ms // n
            for tc in rr.tests:
                if tc.passed:
                    label = "[green]PASS[/green]"
                elif tc.ignored:
                    label = "[yellow]IGNORE[/yellow]"
                else:
                    label = "[red]FAIL[/red]"
                table.add_row(tc.name, label, str(per_ms))
                if not tc.passed and not tc.ignored and tc.message:
                    table.add_row(f"[dim]  {tc.message}[/dim]", "", "")

        _console.print(table)
        if i < len(run_results) - 1:
            _console.print()


def print_summary(run_results: list[RunResult]) -> None:
    passed = 0
    failed = 0
    ignored = 0
    timed_out = 0
    total_ms = 0

    for rr in run_results:
        total_ms += rr.duration_ms
        if rr.binary is None:
            failed += 1
            continue
        if rr.timed_out:
            timed_out += 1
            continue
        for tc in rr.tests:
            if tc.ignored:
                ignored += 1
            elif tc.passed:
                passed += 1
            else:
                failed += 1

    color = "green" if failed == 0 and timed_out == 0 else "red"
    line = (
        f"  {passed} passed, {failed} failed, {ignored} ignored, "
        f"{timed_out} timed out — {total_ms / 1000:.1f}s total"
    )
    _console.print(f"[{color}]{line}[/{color}]")


def write_junit_xml(run_results: list[RunResult], output_path: Path) -> None:
    root = ET.Element("testsuites")

    for rr in run_results:
        n_tests = len(rr.tests)
        n_failures = sum(1 for tc in rr.tests if not tc.passed and not tc.ignored)
        n_skipped = sum(1 for tc in rr.tests if tc.ignored)
        n_errors = 0
        compile_error = rr.binary is None
        timeout_error = rr.timed_out and rr.binary is not None

        if compile_error or timeout_error:
            n_errors = 1

        per_s = rr.duration_ms / 1000.0 / max(n_tests, 1)

        suite = ET.SubElement(root, "testsuite")
        suite.set("name", rr.unit.name)
        suite.set("tests", str(n_tests))
        suite.set("failures", str(n_failures))
        suite.set("errors", str(n_errors))
        suite.set("skipped", str(n_skipped))
        suite.set("time", f"{rr.duration_ms / 1000.0:.3f}")

        if compile_error:
            err = ET.SubElement(suite, "error")
            err.set("message", "compile failed")
            err.text = rr.stderr or ""
            continue

        if timeout_error:
            err = ET.SubElement(suite, "error")
            err.set("type", "timeout")
            err.set("message", "timed out")
            continue

        for tc in rr.tests:
            case = ET.SubElement(suite, "testcase")
            case.set("name", tc.name)
            case.set("classname", rr.unit.name)
            case.set("time", f"{per_s:.3f}")

            if tc.ignored:
                ET.SubElement(case, "skipped")
            elif not tc.passed:
                failure = ET.SubElement(case, "failure")
                failure.set("message", tc.message)
                failure.text = (
                    f"{tc.file}:{tc.line}:{tc.name}:FAIL: {tc.message}"
                )

    ET.indent(root)
    tree = ET.ElementTree(root)
    tree.write(str(output_path), encoding="unicode", xml_declaration=True)
