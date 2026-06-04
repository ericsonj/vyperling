"""vyperling.discoverer — test_*.c discovery and source file matching."""

from __future__ import annotations

import re
import warnings
from dataclasses import dataclass, field
from pathlib import Path

# Matches `#include "mock_<dep>.h"` and captures <dep>.
_MOCK_INCLUDE = re.compile(r'^\s*#\s*include\s+"mock_([A-Za-z0-9_]+)\.h"', re.MULTILINE)


@dataclass
class TestUnit:
    test_file: Path
    source_file: Path | None
    name: str
    mocks: list[str] = field(default_factory=list)


def _parse_mock_includes(test_file: Path) -> list[str]:
    """Return the dependency names from `#include "mock_<dep>.h"` lines, in order."""
    try:
        text = test_file.read_text(encoding="utf-8")
    except OSError:
        return []
    seen: list[str] = []
    for dep in _MOCK_INCLUDE.findall(text):
        if dep not in seen:
            seen.append(dep)
    return seen


def discover(config: dict, filter_pattern: str | None = None) -> list[TestUnit]:
    """Glob test_dir for test_*.c, resolve matching source files, apply filter.

    Paths are relative to cwd. Warns (does not raise) when source file not found.
    """
    test_dir = Path(config["project"]["test_dir"])
    src_dirs = [Path(d) for d in config["project"]["src_dirs"]]

    if not test_dir.is_dir():
        return []

    units: list[TestUnit] = []
    for test_file in sorted(test_dir.glob("test_*.c")):
        name = test_file.stem[5:]  # strip "test_"

        if filter_pattern is not None and filter_pattern not in name:
            continue

        source_file: Path | None = None
        for src_dir in src_dirs:
            candidate = src_dir / f"{name}.c"
            if candidate.is_file():
                source_file = candidate
                break

        if source_file is None:
            warnings.warn(
                f"No source file found for '{name}' in {[str(d) for d in src_dirs]}",
                UserWarning,
                stacklevel=2,
            )

        mocks = _parse_mock_includes(test_file)
        units.append(
            TestUnit(
                test_file=test_file,
                source_file=source_file,
                name=name,
                mocks=mocks,
            )
        )

    return units
