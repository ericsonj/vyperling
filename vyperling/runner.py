"""vyperling.runner — execute test binaries (native or via QEMU), parse Unity output."""

from __future__ import annotations

import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from vyperling.compiler import CompileResult
from vyperling.discoverer import TestUnit
from vyperling.toolchains import Toolchain

_ANSI_ESCAPE = re.compile(r"\033\[[0-9;]*m")

_UNITY_LINE = re.compile(
    r"^(?P<file>[^:]+)"
    r":(?P<line>\d+)"
    r":(?P<name>[^:]+)"
    r":(?P<result>PASS|FAIL|IGNORE)"
    r"(?::[ ]?(?P<message>.+))?$"
)


@dataclass
class TestCase:
    file: str
    line: int
    name: str
    passed: bool
    ignored: bool
    message: str


@dataclass
class RunResult:
    unit: TestUnit
    binary: Path | None
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool
    tests: list[TestCase]


def _parse_unity_output(stdout: str) -> list[TestCase]:
    cases: list[TestCase] = []
    for raw_line in stdout.splitlines():
        line = _ANSI_ESCAPE.sub("", raw_line).rstrip()
        m = _UNITY_LINE.match(line)
        if not m:
            continue
        result = m.group("result")
        cases.append(TestCase(
            file=m.group("file"),
            line=int(m.group("line")),
            name=m.group("name").strip(),
            passed=(result == "PASS"),
            ignored=(result == "IGNORE"),
            message=(m.group("message") or "").strip(),
        ))
    return cases


def run_binary(
    compile_result: CompileResult,
    toolchain: Toolchain,
    timeout_s: int = 30,
) -> RunResult:
    if not compile_result.success or compile_result.binary is None:
        return RunResult(
            unit=compile_result.unit,
            binary=None,
            exit_code=-1,
            stdout="",
            stderr=compile_result.output,
            duration_ms=0,
            timed_out=False,
            tests=[],
        )

    binary = compile_result.binary

    if toolchain.emulator is None:
        cmd = [str(binary)]
    else:
        emulator_args = list(toolchain.emulator_args)
        if toolchain.sysroot is not None:
            emulator_args = ["-L", toolchain.sysroot] + emulator_args
        cmd = [toolchain.emulator] + emulator_args + [str(binary)]

    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_s,
        )
        duration_ms = int((time.monotonic() - t0) * 1000)
        stdout = proc.stdout
        stderr = proc.stderr
        exit_code = proc.returncode
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        duration_ms = int((time.monotonic() - t0) * 1000)
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        exit_code = -1
        timed_out = True

    return RunResult(
        unit=compile_result.unit,
        binary=binary,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        duration_ms=duration_ms,
        timed_out=timed_out,
        tests=_parse_unity_output(stdout),
    )


def run_all(
    compile_results: list[CompileResult],
    toolchain: Toolchain,
    timeout_s: int = 30,
) -> list[RunResult]:
    return [run_binary(cr, toolchain, timeout_s) for cr in compile_results]
