"""End-to-end CROSS-COMPILE smoke test — builds a MIPS binary and runs it under qemu-user.

Mirrors tests/test_e2e_native.py but for cross targets. Shells out to the REAL installed
`vpl` console script via subprocess (NOT Click's CliRunner) and imports zero vyperling code
— validating the installed tool as a black box: cross-gcc compiles a static foreign-arch
ELF, runner invokes `qemu-<arch> <binary>`, qemu-user executes the guest and forwards its
stdout + exit code, and Unity output parses identically to native.

Each target is independently skip-guarded on BOTH its cross-gcc AND its qemu-user emulator,
so a host with only some cross toolchains runs what it can and skips the rest with a clear
reason. The ELF magic/e_machine/endianness check is the smoke signal proving a real cross
build happened rather than a silent native fallback.

Skips the whole module (no hard fail) if the `vpl` console script is not installed
(`poetry install` / `pip install -e .` not run).

Two test groups:

* scaffold-based (test_cross_compile_and_run_passes, test_cross_failing_test_propagates_exit_1)
  — spins up a fresh `vpl new demo` project in tmp_path; validates the generic scaffold path.

* example-based (test_cross_mips_example_*)
  — runs against examples/cross_mips, a real multi-module project with mocks (CRC16 + packet
  framing). Verifies that mock generation, multi-unit compilation, and MIPS ELF production all
  work on a non-trivial codebase, not just the minimal scaffold.
"""

from __future__ import annotations

import os
import shutil
import struct
import subprocess
import sys
from pathlib import Path

import pytest

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"
CROSS_MIPS_EXAMPLE = EXAMPLES_DIR / "cross_compilation"

TIMEOUT_S = 120
EM_MIPS = 8  # ELF e_machine value for MIPS

# (target, cc binary, qemu-user binary, expected EI_DATA: 1=little-endian, 2=big-endian)
CROSS_TARGETS = [
    ("mips32", "mips-linux-gnu-gcc", "qemu-mips", 2),
    ("mips32el", "mipsel-linux-gnu-gcc", "qemu-mipsel", 1),
]


def _resolve_script(name: str) -> Path | None:
    candidate = Path(sys.prefix) / "bin" / name
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return candidate
    found = shutil.which(name)
    return Path(found) if found else None


VPL = _resolve_script("vpl")

pytestmark = pytest.mark.skipif(
    VPL is None,
    reason="vpl console script not installed "
    "(run `poetry install` or `pip install -e .`)",
)


def _require_cross(cc: str, qemu: str, target: str) -> None:
    """Skip the current test unless BOTH the cross-gcc and qemu-user are installed."""
    if shutil.which(cc) is None:
        pytest.skip(f"{cc} not installed (cross compiler for {target} missing)")
    if shutil.which(qemu) is None:
        pytest.skip(f"{qemu} not installed (qemu-user for {target} missing)")


def _run(script: Path, *args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(script), *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=TIMEOUT_S,
    )


def _assert_mips_elf(binary: Path, expected_ei_data: int) -> None:
    """Prove `binary` is a MIPS ELF of the expected endianness (real cross build)."""
    assert binary.is_file(), f"expected cross binary at {binary}"
    data = binary.read_bytes()
    assert len(data) >= 20, "file too small to be an ELF"
    assert data[0:4] == b"\x7fELF", "missing ELF magic"
    ei_data = data[5]  # EI_DATA: 1 = LSB (little), 2 = MSB (big)
    assert ei_data == expected_ei_data, (
        f"endianness mismatch: EI_DATA={ei_data}, expected {expected_ei_data}"
    )
    endian = "<" if ei_data == 1 else ">"
    (e_machine,) = struct.unpack_from(endian + "H", data, 18)  # e_machine at offset 18
    assert e_machine == EM_MIPS, f"e_machine={e_machine}, expected {EM_MIPS} (EM_MIPS)"


def _first_available_target() -> tuple[str, str, str, int] | None:
    for row in CROSS_TARGETS:
        _target, cc, qemu, _ei = row
        if shutil.which(cc) is not None and shutil.which(qemu) is not None:
            return row
    return None


@pytest.mark.parametrize(
    "target, cc, qemu, ei_data",
    CROSS_TARGETS,
    ids=[t[0] for t in CROSS_TARGETS],
)
def test_cross_compile_and_run_passes(
    target: str, cc: str, qemu: str, ei_data: int, tmp_path: Path
) -> None:
    _require_cross(cc, qemu, target)

    new = _run(VPL, "new", "demo", cwd=tmp_path)
    assert new.returncode == 0, new.stderr
    project = tmp_path / "demo"
    assert (project / "forge.yml").is_file()

    out = _run(VPL, "test", "--target", target, cwd=project)
    combined = out.stdout + out.stderr
    assert out.returncode == 0, combined
    assert "1 passed" in combined
    assert "✓" in combined

    # Smoke signal: a REAL cross binary of the right arch/endianness was produced.
    _assert_mips_elf(project / "build" / target / "example", ei_data)


def test_cross_failing_test_propagates_exit_1(tmp_path: Path) -> None:
    """A failing Unity assertion under qemu-user must propagate a non-zero exit code.

    Distinct from native: qemu-user must forward the guest process exit status as its
    own. Runs against the first cross target available on this host.
    """
    row = _first_available_target()
    if row is None:
        pytest.skip("no cross toolchain (gcc + qemu-user pair) available on this host")
    target, *_ = row

    assert _run(VPL, "new", "demo", cwd=tmp_path).returncode == 0, "scaffold failed"
    project = tmp_path / "demo"

    # Flip the scaffold's single (already-registered) test to fail — fixture-file edit
    # inside tmp_path only, registration-agnostic.
    test_file = project / "test" / "test_example.c"
    src = test_file.read_text()
    bad = src.replace(
        "TEST_ASSERT_EQUAL_INT(5, example_add(2, 3));",
        "TEST_ASSERT_EQUAL_INT(99, example_add(2, 3));",
    )
    assert bad != src, "scaffold assertion line changed; update the failing-test patch"
    test_file.write_text(bad)

    out = _run(VPL, "test", "--target", target, cwd=project)
    combined = out.stdout + out.stderr
    assert out.returncode != 0, f"expected non-zero exit, got 0:\n{combined}"
    assert "✗" in combined


# ---------------------------------------------------------------------------
# examples/cross_mips — real multi-module project with mocks
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "target, cc, qemu, ei_data",
    CROSS_TARGETS,
    ids=[t[0] for t in CROSS_TARGETS],
)
def test_cross_mips_example_all_tests_pass(
    target: str, cc: str, qemu: str, ei_data: int, tmp_path: Path
) -> None:
    """cross_mips example: mock generation + multi-unit compile + MIPS ELF verified.

    Copies the example into tmp_path so the source tree stays clean (no build/
    or mocks/ artefacts committed). Checks that both the pure-C crc16 unit and
    the mock-driven packet unit pass under qemu-user, and that every produced
    binary is a genuine MIPS ELF of the expected endianness.
    """
    _require_cross(cc, qemu, target)

    # Copy example into tmp_path — keeps source tree clean.
    project = tmp_path / "cross_compilation"
    shutil.copytree(CROSS_MIPS_EXAMPLE, project)

    out = _run(VPL, "test", "--target", target, cwd=project)
    combined = out.stdout + out.stderr
    assert out.returncode == 0, combined
    assert "passed" in combined
    assert "✓" in combined
    assert "✗" not in combined

    # Both units must produce a genuine MIPS ELF.
    for unit in ("crc16", "packet"):
        _assert_mips_elf(project / "build" / target / unit, ei_data)


@pytest.mark.parametrize(
    "target, cc, qemu, ei_data",
    CROSS_TARGETS,
    ids=[t[0] for t in CROSS_TARGETS],
)
def test_cross_mips_example_elf_is_static(
    target: str, cc: str, qemu: str, ei_data: int, tmp_path: Path
) -> None:
    """MIPS toolchain builds static binaries — no dynamic linker required.

    ET_EXEC (e_type=2) + no PT_INTERP segment confirms the binary is fully
    static and can run under qemu-user without a sysroot.
    """
    _require_cross(cc, qemu, target)

    project = tmp_path / "cross_compilation"
    shutil.copytree(CROSS_MIPS_EXAMPLE, project)

    out = _run(VPL, "test", "--target", target, cwd=project)
    assert out.returncode == 0, out.stdout + out.stderr

    # Check the crc16 binary (no mocks — simplest ELF to inspect).
    binary = project / "build" / target / "crc16"
    _assert_mips_elf(binary, ei_data)

    data = binary.read_bytes()
    endian = "<" if ei_data == 1 else ">"
    (e_type,) = struct.unpack_from(endian + "H", data, 16)  # e_type at offset 16
    assert e_type == 2, f"expected ET_EXEC (2), got e_type={e_type} — binary is not static exec"


def test_cross_mips_example_crc_unit_fails_propagates_exit_1(tmp_path: Path) -> None:
    """A failing CRC assertion under qemu-user propagates a non-zero exit code.

    Patches test_crc16.c to flip a known-vector assertion so it fails, then
    checks that qemu-user forwards the non-zero guest exit status. Uses the
    first available MIPS target on this host.
    """
    row = _first_available_target()
    if row is None:
        pytest.skip("no cross toolchain (gcc + qemu-user pair) available on this host")
    target, *_ = row

    project = tmp_path / "cross_compilation"
    shutil.copytree(CROSS_MIPS_EXAMPLE, project)

    test_file = project / "test" / "test_crc16.c"
    src = test_file.read_text()
    bad = src.replace(
        "TEST_ASSERT_EQUAL_HEX16(0x29B1, crc16_compute(data, sizeof(data)));",
        "TEST_ASSERT_EQUAL_HEX16(0xDEAD, crc16_compute(data, sizeof(data)));",
    )
    assert bad != src, "known-vector assertion changed in test_crc16.c; update the patch"
    test_file.write_text(bad)

    out = _run(VPL, "test", "--target", target, cwd=project)
    combined = out.stdout + out.stderr
    assert out.returncode != 0, f"expected non-zero exit, got 0:\n{combined}"
    assert "✗" in combined
