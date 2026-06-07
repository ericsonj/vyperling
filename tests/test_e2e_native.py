"""End-to-end NATIVE smoke test — invokes the REAL installed console script.

Unlike tests/test_cli.py (Click CliRunner, in-process) and tests/test_scaffold.py
(direct gcc subprocess, bypasses the CLI), this module shells out to the actually
installed `vpl`/`vyperling` console-script binary via subprocess. It is the only test
that validates wheel packaging (bundled C assets/templates), console-script entrypoint
registration, and importlib.resources asset resolution when run as an installed tool.

Skips the whole module (no hard fail) if the console script is not installed
(`poetry install` / `pip install -e .` not run) or gcc is unavailable.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

TIMEOUT_S = 120


def _resolve_script(name: str) -> Path | None:
    candidate = Path(sys.prefix) / "bin" / name
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return candidate
    found = shutil.which(name)
    return Path(found) if found else None


VPL = _resolve_script("vpl")
VYPERLING = _resolve_script("vyperling")

pytestmark = [
    pytest.mark.skipif(
        VPL is None or VYPERLING is None,
        reason="vpl/vyperling console script not installed "
        "(run `poetry install` or `pip install -e .`)",
    ),
    pytest.mark.skipif(shutil.which("gcc") is None, reason="gcc not available"),
]


def _run(script: Path, *args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(script), *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=TIMEOUT_S,
    )


def test_new_then_test_passes(tmp_path: Path) -> None:
    new = _run(VPL, "new", "demo", cwd=tmp_path)
    assert new.returncode == 0, new.stderr
    project = tmp_path / "demo"
    assert (project / "forge.yml").is_file()

    out = _run(VPL, "test", cwd=project)
    combined = out.stdout + out.stderr
    assert out.returncode == 0, combined
    assert "1 passed" in combined
    assert "✓" in combined


def test_vyperling_twin_entrypoint(tmp_path: Path) -> None:
    proc = _run(VYPERLING, "targets", cwd=tmp_path)
    assert proc.returncode == 0, proc.stderr
    assert "native" in proc.stdout


def test_junit_artifact_written(tmp_path: Path) -> None:
    assert _run(VPL, "new", "demo", cwd=tmp_path).returncode == 0, "scaffold failed"
    project = tmp_path / "demo"
    proc = _run(VPL, "test", "--output", "junit", cwd=project)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert (project / "build" / "native" / "results.xml").is_file()
