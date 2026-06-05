"""vyperling.discoverer — test_*.c discovery and source file matching."""

from __future__ import annotations

import re
import warnings
from dataclasses import dataclass, field
from pathlib import Path

def _mock_include_re(mock_prefix: str) -> re.Pattern:
    p = re.escape(mock_prefix)
    # Allow an optional path prefix (e.g. "calculators/MockFoo.h") before the
    # mock prefix — the dep name captured is always just the stem after the prefix.
    return re.compile(
        rf'^\s*#\s*include\s+"(?:[^"*/]*/)*{p}([A-Za-z0-9_]+)\.h"', re.MULTILINE
    )


@dataclass
class TestUnit:
    test_file: Path
    source_file: Path | None
    name: str
    mocks: list[str] = field(default_factory=list)
    extra_srcs: list[Path] = field(default_factory=list)


def _parse_mock_includes(test_file: Path, mock_prefix: str = "mock_") -> list[str]:
    """Return dependency names from `#include "<mock_prefix><dep>.h"` lines, in order."""
    try:
        text = test_file.read_text(encoding="utf-8")
    except OSError:
        return []
    seen: list[str] = []
    for dep in _mock_include_re(mock_prefix).findall(text):
        if dep not in seen:
            seen.append(dep)
    return seen


def discover(config: dict, filter_pattern: str | None = None) -> list[TestUnit]:
    """Glob test_dir(s) for test_*.c, resolve matching source files, apply filter.

    `project.test_dir` may be a single path or a list of paths; each is searched
    recursively. Paths are relative to cwd. Warns (does not raise) when a source
    file is not found.
    """
    conventions = config.get("conventions", {})
    test_prefix: str = conventions.get("test_prefix", "test_")
    mock_prefix: str = conventions.get("mock_prefix", "mock_")

    raw_test_dir = config["project"]["test_dir"]
    test_dirs = (
        [Path(raw_test_dir)]
        if isinstance(raw_test_dir, (str, Path))
        else [Path(d) for d in raw_test_dir]
    )
    src_dirs = [Path(d) for d in config["project"]["src_dirs"]]

    # Optional per-test extra sources: {test_name: [path, ...]}.  Lets a single
    # test link a non-mocked, non-SUT dependency (e.g. a shared util .c) without
    # polluting every other test the way support_srcs would.
    extra_srcs_map = config["project"].get("extra_srcs", {}) or {}

    prefix_len = len(test_prefix)
    test_files = sorted(
        {
            tf
            for td in test_dirs
            if td.is_dir()
            for tf in td.rglob(f"{test_prefix}*.c")
        }
    )
    if not test_files:
        return []

    units: list[TestUnit] = []
    for test_file in test_files:
        name = test_file.stem[prefix_len:]  # strip test_prefix

        if filter_pattern is not None and filter_pattern not in name:
            continue

        source_file: Path | None = None
        for src_dir in src_dirs:
            matches = sorted(src_dir.rglob(f"{name}.c"))
            if matches:
                source_file = matches[0]
                break

        if source_file is None:
            warnings.warn(
                f"No source file found for '{name}' in {[str(d) for d in src_dirs]}",
                UserWarning,
                stacklevel=2,
            )

        mocks = _parse_mock_includes(test_file, mock_prefix)
        extra = [Path(p) for p in extra_srcs_map.get(name, [])]
        units.append(
            TestUnit(
                test_file=test_file,
                source_file=source_file,
                name=name,
                mocks=mocks,
                extra_srcs=extra,
            )
        )

    return units
