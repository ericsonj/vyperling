#!/usr/bin/env python3
"""Compare JUnit XML test results between Ceedling and vyperling runs.

Usage:
  python scripts/compare_results.py \\
    --ceedling build/artifacts/gcov/results.xml \\
    --vpl build/native/results.xml

Exit codes:
  0  — all tests present in both match (PASS/FAIL agreement)
  1  — at least one MISMATCH, MISSING, or EXTRA found
  2  — one or both input files missing or invalid
"""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TestCase:
    classname: str
    name: str
    passed: bool
    message: str = ""


def _normalize_suite(name: str) -> str:
    """Normalize suite name: strip path prefix and leading test-file prefix.

    Ceedling emits 'test/TestMain' (PascalCase convention) or
    'test/test_parser' (snake_case convention); vyperling emits 'Main' or
    'parser' respectively. Both normalize to the same bare module name.
    """
    # strip path components (e.g. 'test/TestMain' -> 'TestMain')
    name = name.rsplit("/", 1)[-1]
    # strip leading 'Test' (PascalCase) or 'test_' (snake_case) prefix
    if name.startswith("Test"):
        name = name[4:]
    elif name.startswith("test_"):
        name = name[5:]
    return name


def _parse_junit(path: Path) -> dict[str, TestCase]:
    try:
        tree = ET.parse(path)
    except (ET.ParseError, OSError) as exc:
        print(f"ERROR: cannot parse {path}: {exc}", file=sys.stderr)
        sys.exit(2)

    root = tree.getroot()
    # handle both <testsuites><testsuite>... and bare <testsuite>...
    suites = root.findall("testsuite") or ([root] if root.tag == "testsuite" else [])

    cases: dict[str, TestCase] = {}
    for suite in suites:
        suite_name = _normalize_suite(suite.get("name", ""))
        for tc in suite.findall("testcase"):
            # use classname if present, else fall back to suite name
            raw_classname = tc.get("classname", "")
            classname = _normalize_suite(raw_classname) if raw_classname else suite_name
            name = tc.get("name", "")
            key = f"{classname}::{name}"
            failure = tc.find("failure")
            error = tc.find("error")
            passed = failure is None and error is None
            msg = ""
            if failure is not None:
                msg = failure.get("message", failure.text or "")
            elif error is not None:
                msg = error.get("message", error.text or "")
            cases[key] = TestCase(classname=classname, name=name, passed=passed, message=msg)
    return cases


def _short_key(key: str) -> str:
    """Strip classname prefix for display if name is already descriptive."""
    parts = key.split("::")
    return parts[-1] if len(parts) > 1 else key


def compare(ceedling_path: Path, vpl_path: Path) -> int:
    ceedling = _parse_junit(ceedling_path)
    vpl = _parse_junit(vpl_path)

    all_keys = sorted(set(ceedling) | set(vpl))

    rows: list[tuple[str, str, str]] = []
    has_issue = False

    for key in all_keys:
        short = _short_key(key)
        in_c = key in ceedling
        in_v = key in vpl

        if in_c and in_v:
            c_pass = ceedling[key].passed
            v_pass = vpl[key].passed
            if c_pass == v_pass:
                status = "[MATCH  ]"
                detail = "PASS" if c_pass else "FAIL"
            else:
                status = "[MISMATCH]"
                detail = f"ceedling={'PASS' if c_pass else 'FAIL'}  vpl={'PASS' if v_pass else 'FAIL'}"
                if not v_pass:
                    detail += f"  ({vpl[key].message[:80]})"
                has_issue = True
        elif in_c and not in_v:
            status = "[MISSING ]"
            detail = "in ceedling, not in vpl"
            has_issue = True
        else:
            status = "[EXTRA   ]"
            detail = "in vpl, not in ceedling"
            has_issue = True

        rows.append((status, short, detail))

    max_name = max((len(r[1]) for r in rows), default=30)
    fmt = f"{{}}  {{:<{max_name}}}  {{}}"

    print(f"\nComparing: {ceedling_path}  vs  {vpl_path}\n")
    for status, name, detail in rows:
        print(fmt.format(status, name, detail))

    total = len(all_keys)
    matches = sum(1 for s, _, _ in rows if s.startswith("[MATCH"))
    issues = total - matches
    print(f"\n{matches}/{total} match", end="")
    if issues:
        print(f", {issues} issue(s) found")
    else:
        print(" — all results agree ✓")

    return 1 if has_issue else 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ceedling", required=True, type=Path, help="Ceedling JUnit XML output")
    parser.add_argument("--vpl", required=True, type=Path, help="vyperling JUnit XML output")
    args = parser.parse_args()

    for p in (args.ceedling, args.vpl):
        if not p.is_file():
            print(f"ERROR: file not found: {p}", file=sys.stderr)
            sys.exit(2)

    sys.exit(compare(args.ceedling, args.vpl))


if __name__ == "__main__":
    main()
