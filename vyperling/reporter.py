"""vyperling.reporter — rich terminal output + JUnit XML writer."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from rich.console import Console
from rich.table import Table

from vyperling.coverage import CoverageSummary
from vyperling.runner import RunResult

_console = Console()

# gcovr's own banding (defaults): high >= 90, medium >= 75, low < 75.
# Matches the colors of the HTML report produced by the same run.
_COV_HIGH = 90.0
_COV_MEDIUM = 75.0


# Per-test status glyphs (markup-free; colored at print time).
_PASS = "✓"
_FAIL = "✗"
_IGNORE = "~"

# Minimum width for the test-name column so short names still align.
_NAME_MIN = 32


def _unit_failed(rr: RunResult) -> bool:
    """True if a unit had a compile error, timed out, or has any failing test."""
    if rr.binary is None or rr.timed_out:
        return True
    return any(not tc.passed and not tc.ignored for tc in rr.tests)


def print_terminal_report(run_results: list[RunResult], compact: bool = False) -> None:
    """Render a compact tree of per-unit test results.

    Default view lists every test under a unit header; ``compact`` collapses each
    unit to a single dot-leadered line. RunResult carries only a per-unit total
    duration, so per-test ms is the unit total divided evenly across its tests.
    """
    if compact:
        _print_compact(run_results)
        return

    for i, rr in enumerate(run_results):
        _console.print(f"[bold cyan]▸[/bold cyan] [bold]{rr.unit.name}[/bold]"
                       f"  [dim]({len(rr.tests)} tests)[/dim]")

        if rr.binary is None:
            _console.print(f"  [red]{_FAIL} COMPILE ERROR[/red]")
            if rr.stderr.strip():
                _console.print(f"    [dim]{rr.stderr.strip()}[/dim]")
        elif rr.timed_out:
            _console.print(f"  [red]{_FAIL} TIMEOUT[/red]  "
                           f"[dim]{rr.duration_ms}ms[/dim]")
        else:
            n = max(len(rr.tests), 1)
            per_ms = rr.duration_ms // n
            width = max((len(tc.name) for tc in rr.tests), default=0)
            width = max(width, _NAME_MIN)
            for tc in rr.tests:
                if tc.passed:
                    glyph, color = _PASS, "green"
                elif tc.ignored:
                    glyph, color = _IGNORE, "yellow"
                else:
                    glyph, color = _FAIL, "red"
                _console.print(
                    f"  [{color}]{glyph}[/{color}] {tc.name:<{width}}  "
                    f"[dim]{per_ms}ms[/dim]"
                )
                if not tc.passed and not tc.ignored:
                    if tc.message:
                        _console.print(f"    [dim]{tc.message}[/dim]")
                    _console.print(f"    [dim cyan]{tc.file}:{tc.line}[/dim cyan]")

        if i < len(run_results) - 1:
            _console.print()


def _compact_dots(rr: RunResult) -> str:
    """One status char per test: `.` pass, `✗` fail (red), `~` ignore (yellow).

    Compile-error / timeout units have no per-test data, so they render a single
    red ✗ standing in for the whole unit.
    """
    if rr.binary is None or rr.timed_out:
        return f"[red]{_FAIL}[/red]"
    out = []
    for tc in rr.tests:
        if tc.passed:
            out.append(".")
        elif tc.ignored:
            out.append(f"[yellow]{_IGNORE}[/yellow]")
        else:
            out.append(f"[red]{_FAIL}[/red]")
    return "".join(out)


def _print_compact(run_results: list[RunResult]) -> None:
    """One line per unit: name, a status char per test, then total ms.

    The dot row doubles as a count (one mark per test) and a status strip — any
    ✗ in it flags a failing unit at a glance.
    """
    width = max((len(rr.unit.name) for rr in run_results), default=0)
    for rr in run_results:
        color = "red" if _unit_failed(rr) else "green"
        pad = " " * (width - len(rr.unit.name))
        _console.print(
            f"[bold cyan]▸[/bold cyan] [{color}]{rr.unit.name}[/{color}]{pad}  "
            f"{_compact_dots(rr)}  [dim]{rr.duration_ms}ms[/dim]"
        )


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

    clean = failed == 0 and timed_out == 0
    color = "green" if clean else "red"
    glyph = "✔" if clean else "✘"
    line = (
        f"{glyph} {passed} passed  {failed} failed · {ignored} ignored · "
        f"{timed_out} timed out — {total_ms / 1000:.1f}s total"
    )
    _console.print(f"\n[{color}]{line}[/{color}]")


def _cov_color(pct: float) -> str:
    """Map a coverage percentage to a rich color using gcovr's banding."""
    if pct >= _COV_HIGH:
        return "green"
    if pct >= _COV_MEDIUM:
        return "yellow"
    return "red"


def _cov_cell(pct: float) -> str:
    return f"[{_cov_color(pct)}]{pct:.1f}%[/{_cov_color(pct)}]"


def _cov_bar(pct: float, width: int = 10) -> str:
    """A `width`-cell filled/empty bar (`█`/`░`) colored by gcovr banding."""
    filled = round(pct / 100 * width)
    filled = max(0, min(width, filled))
    bar = "█" * filled + "░" * (width - filled)
    color = _cov_color(pct)
    return f"[{color}]{bar}[/{color}]"


def print_coverage_report(summary: CoverageSummary) -> None:
    """Render a rich per-file coverage table (worst-first) plus a TOTAL row,
    followed by a callout of files below the medium (75%) line threshold."""
    _console.print()  # separate from the test summary above
    table = Table(
        title="Coverage",
        title_justify="left",
        title_style="bold",
        box=None,
        show_header=True,
        header_style="bold",
        pad_edge=True,
    )
    table.add_column("File", justify="left", no_wrap=False)
    table.add_column("", justify="left", width=10)  # average-coverage bar
    table.add_column("Lines", justify="right", width=8)
    table.add_column("Functions", justify="right", width=10)
    table.add_column("Branches", justify="right", width=9)

    for f in sorted(summary.files, key=lambda c: c.line_percent):
        avg = (f.line_percent + f.function_percent + f.branch_percent) / 3
        table.add_row(
            f.filename,
            _cov_bar(avg),
            _cov_cell(f.line_percent),
            _cov_cell(f.function_percent),
            _cov_cell(f.branch_percent),
        )

    table.add_row("", "", "", "", "")  # blank spacer above TOTAL (box=None)
    total_avg = (
        summary.line_percent + summary.function_percent + summary.branch_percent
    ) / 3
    table.add_row(
        "[bold]TOTAL[/bold]",
        _cov_bar(total_avg),
        f"[bold]{_cov_cell(summary.line_percent)}[/bold]",
        f"[bold]{_cov_cell(summary.function_percent)}[/bold]",
        f"[bold]{_cov_cell(summary.branch_percent)}[/bold]",
    )

    _console.print(table)

    low = [f for f in summary.files if f.line_percent < _COV_MEDIUM]
    if low:
        listed = ", ".join(
            f"{f.filename} ({f.line_percent:.1f}%)"
            for f in sorted(low, key=lambda c: c.line_percent)
        )
        _console.print(
            f"[red]Below {_COV_MEDIUM:.0f}% line coverage:[/red] {listed}"
        )


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
