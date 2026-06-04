"""vyperling.coverage — gcov coverage report via gcovr (native target only).

Coverage instrumentation is injected by compiler.py (``--coverage`` flags) only
for the native toolchain, so ``.gcno``/``.gcda`` land in ``build/native/``. This
module turns that data into an HTML report (+ Cobertura XML for CI) using gcovr,
which is pure-Python and pip-installable — no lcov/genhtml system tools required.

Native-only enforcement is split: the CLI warns and skips on cross-compile
targets (it knows the target); this module defends via the missing-``.gcda``
check, so a mis-call still fails loudly instead of producing a garbage report.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from vyperling.config import get_mock_dir
from vyperling.errors import ForgeCoverageError


def check_coverage_tools() -> None:
    """Verify gcovr and gcov are on PATH. Raise ForgeCoverageError otherwise."""
    missing = [t for t in ("gcovr", "gcov") if shutil.which(t) is None]
    if missing:
        raise ForgeCoverageError(
            f"Coverage requires {' and '.join(missing)} on PATH. "
            "Install gcovr with `pip install gcovr`; gcov ships with gcc."
        )


def generate_coverage(config: dict, build_dir: Path, output_dir: Path) -> Path:
    """Run gcovr over build_dir, write HTML + Cobertura XML under
    output_dir/coverage/, and return the path to index.html.

    Raises ForgeCoverageError if tools are missing, no .gcda data exists, or
    gcovr returns non-zero.
    """
    check_coverage_tools()

    if not build_dir.is_dir() or not any(build_dir.rglob("*.gcda")):
        raise ForgeCoverageError(
            f"No coverage data (.gcda) found under {build_dir}. "
            "Run `vyperling test --coverage` on the native target first."
        )

    report_dir = output_dir / "coverage"
    report_dir.mkdir(parents=True, exist_ok=True)
    html_index = report_dir / "index.html"
    cobertura_xml = report_dir / "coverage.xml"

    root = Path.cwd()
    mock_dir = get_mock_dir(config)

    cmd = [
        "gcovr",
        "--root", str(root),
        "--gcov-ignore-parse-errors",        # robustness vs gcc/gcov version skew
        "--exclude-unreachable-branches",
        "--exclude-throw-branches",
        "--exclude", r".*/unity\.c$",        # vendored Unity
        "--exclude", r".*/forge_mock\.c$",   # vendored mock runtime
        "--exclude", r".*/vyperling/c/.*",      # vyperling vendored C dir
        "--exclude", re.escape(str(mock_dir)) + r"/.*",  # generated mocks
        "--exclude", r"/usr/.*",             # system headers
        "--html-details", str(html_index),
        "--cobertura", str(cobertura_xml),   # CI artifact (Step 17)
        "--cobertura-pretty",
        "--print-summary",
        str(build_dir),                      # search path for .gcda
    ]

    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if proc.returncode != 0:
        raise ForgeCoverageError(
            f"gcovr failed (exit {proc.returncode}):\n{proc.stdout.strip()}"
        )

    return html_index
