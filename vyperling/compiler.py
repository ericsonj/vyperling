"""vyperling.compiler — compile TestUnits into executables via subprocess."""

from __future__ import annotations

import json
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from vyperling.config import get_build_dir, get_include_dirs
from vyperling.discoverer import TestUnit
from vyperling.runnergen import generate_runner
from vyperling.toolchains import Toolchain
from vyperling.unity import (
    get_forge_mock_c_path,
    get_unity_c_path,
    get_unity_include_dir,
)


@dataclass
class CompileResult:
    unit: TestUnit
    binary: Path | None
    success: bool
    output: str
    duration_ms: int


def _load_deps(dep_file: Path) -> dict[str, float]:
    try:
        return json.loads(dep_file.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def _is_cached(dep_file: Path, sources: list[Path]) -> bool:
    stored = _load_deps(dep_file)
    if not stored:
        return False
    for src in sources:
        key = str(src)
        if key not in stored:
            return False
        try:
            if src.stat().st_mtime != stored[key]:
                return False
        except OSError:
            return False
    return True


def _write_deps(dep_file: Path, sources: list[Path]) -> None:
    data = {}
    for src in sources:
        try:
            data[str(src)] = src.stat().st_mtime
        except OSError:
            pass
    dep_file.write_text(json.dumps(data))


def compile_unit(
    unit: TestUnit,
    toolchain: Toolchain,
    config: dict,
    build_dir: Path,
    verbose: bool = False,
    coverage: bool = False,
) -> CompileResult:
    conventions = config.get("conventions", {})
    mock_prefix: str = conventions.get("mock_prefix", "mock_")
    test_prefix: str = conventions.get("test_prefix", "test_")
    test_naming: str = conventions.get("test_naming", "snake_case")

    mock_dir = Path(config["project"]["mock_dir"])

    sources: list[Path] = [unit.test_file]
    if unit.source_file is not None:
        sources.append(unit.source_file)
    # Link only the mocks this test explicitly includes (`#include "<prefix><dep>.h"`),
    # never glob-all — that would redefine the unit's own source symbols. This
    # mirrors Ceedling: a test links its SUT plus mocks of its dependencies, and
    # the real dependency source is replaced by the mock, never linked alongside.
    for dep in unit.mocks:
        mock_c = mock_dir / f"{mock_prefix}{dep}.c"
        if mock_c.is_file():
            sources.append(mock_c)
    # Link support sources (always-linked stubs/helpers) declared in forge.yml.
    for src_path in config["project"].get("support_srcs", []):
        p = Path(src_path)
        if p.is_file():
            sources.append(p)
    # Link per-test extra sources declared in forge.yml project.extra_srcs.
    for p in unit.extra_srcs:
        if p.is_file() and p not in sources:
            sources.append(p)
    sources.append(get_unity_c_path())
    sources.append(get_forge_mock_c_path())

    # Generate the Unity runner (main + RUN_TEST list) for this test, the way
    # Ceedling auto-creates one. Without it the test TU has no main() to link.
    runner_path = build_dir / f"{unit.name}_runner.c"
    generate_runner(
        unit.test_file,
        runner_path,
        list(unit.mocks),
        test_prefix=test_prefix,
        test_naming=test_naming,
        mock_prefix=mock_prefix,
    )
    sources.append(runner_path)

    include_dirs: list[Path] = list(get_include_dirs(config))
    include_dirs.append(get_unity_include_dir())
    if mock_dir.is_dir():
        include_dirs.append(mock_dir)

    binary = build_dir / unit.name
    dep_file = build_dir / f"{unit.name}.forge_deps.json"

    if _is_cached(dep_file, sources) and binary.is_file():
        return CompileResult(
            unit=unit,
            binary=binary,
            success=True,
            output="[cached]",
            duration_ms=0,
        )

    flags: list[str] = list(toolchain.cflags)
    flags += ["-D" + d for d in config["compiler"]["defines"]]
    flags += list(config["compiler"]["extra_cflags"])
    if toolchain.static:
        flags.append("-static")
    if coverage and toolchain.name == "native":
        flags += ["--coverage", "-fprofile-arcs", "-ftest-coverage"]
    flags += ["-I" + str(d) for d in include_dirs]

    ldflags: list[str] = list(config["compiler"].get("extra_ldflags", []))
    cmd = [toolchain.cc] + flags + [str(s) for s in sources] + ["-o", str(binary)] + ldflags

    if verbose:
        print(" ".join(cmd))

    t0 = time.monotonic()
    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    duration_ms = int((time.monotonic() - t0) * 1000)

    if proc.returncode == 0:
        _write_deps(dep_file, sources)
        return CompileResult(
            unit=unit,
            binary=binary,
            success=True,
            output=proc.stdout,
            duration_ms=duration_ms,
        )

    return CompileResult(
        unit=unit,
        binary=None,
        success=False,
        output=proc.stdout,
        duration_ms=duration_ms,
    )


def compile_all(
    units: list[TestUnit],
    toolchain: Toolchain,
    config: dict,
    jobs: int = 1,
    verbose: bool = False,
    coverage: bool = False,
) -> list[CompileResult]:
    build_dir = get_build_dir(config, toolchain.name)
    build_dir.mkdir(parents=True, exist_ok=True)

    def _compile(unit: TestUnit) -> CompileResult:
        return compile_unit(unit, toolchain, config, build_dir, verbose, coverage)

    with ThreadPoolExecutor(max_workers=jobs) as executor:
        return list(executor.map(_compile, units))
