"""vyperling.toolchains — Toolchain dataclass, built-in registry, and resolver."""

from __future__ import annotations

from dataclasses import dataclass, field

from vyperling.errors import ForgeToolchainError


@dataclass
class Toolchain:
    name: str
    description: str
    cc: str
    ar: str
    cflags: list[str]
    emulator: str | None
    emulator_args: list[str]
    sysroot: str | None
    static: bool


BUILTIN_TOOLCHAINS: dict[str, Toolchain] = {
    "native": Toolchain(
        name="native",
        description="Host machine (no cross compilation)",
        cc="gcc",
        ar="ar",
        cflags=[],
        emulator=None,
        emulator_args=[],
        sysroot=None,
        static=False,
    ),
    "mips32": Toolchain(
        name="mips32",
        description="MIPS32 big-endian — mips-linux-gnu-gcc + qemu-mips",
        cc="mips-linux-gnu-gcc",
        ar="mips-linux-gnu-ar",
        cflags=["-mips32", "-EB"],
        emulator="qemu-mips",
        emulator_args=[],
        sysroot=None,
        static=True,
    ),
    "mips32el": Toolchain(
        name="mips32el",
        description="MIPS32 little-endian — mipsel-linux-gnu-gcc + qemu-mipsel",
        cc="mipsel-linux-gnu-gcc",
        ar="mipsel-linux-gnu-ar",
        cflags=["-mips32", "-EL"],
        emulator="qemu-mipsel",
        emulator_args=[],
        sysroot=None,
        static=True,
    ),
    "mips32r5": Toolchain(
        name="mips32r5",
        description="MIPS32r5 PIC32MK — mips-linux-gnu-gcc + qemu-mips -cpu P5600",
        cc="mips-linux-gnu-gcc",
        ar="mips-linux-gnu-ar",
        cflags=["-march=mips32r5", "-EL"],
        emulator="qemu-mips",
        emulator_args=["-cpu", "P5600"],
        sysroot=None,
        static=True,
    ),
    "arm-cortex-m4": Toolchain(
        name="arm-cortex-m4",
        description="ARM Cortex-M4 — arm-none-eabi-gcc + qemu-arm",
        cc="arm-none-eabi-gcc",
        ar="arm-none-eabi-ar",
        cflags=["-mcpu=cortex-m4", "-mthumb"],
        emulator="qemu-arm",
        emulator_args=[],
        sysroot=None,
        static=True,
    ),
    "arm-cortex-m0": Toolchain(
        name="arm-cortex-m0",
        description="ARM Cortex-M0 — arm-none-eabi-gcc + qemu-arm",
        cc="arm-none-eabi-gcc",
        ar="arm-none-eabi-ar",
        cflags=["-mcpu=cortex-m0", "-mthumb"],
        emulator="qemu-arm",
        emulator_args=[],
        sysroot=None,
        static=True,
    ),
    "riscv32": Toolchain(
        name="riscv32",
        description="RISC-V 32-bit — riscv32-unknown-elf-gcc + qemu-riscv32",
        cc="riscv32-unknown-elf-gcc",
        ar="riscv32-unknown-elf-ar",
        cflags=["-march=rv32imc"],
        emulator="qemu-riscv32",
        emulator_args=[],
        sysroot=None,
        static=True,
    ),
    "avr": Toolchain(
        name="avr",
        description="AVR — avr-gcc + simavr",
        cc="avr-gcc",
        ar="avr-ar",
        cflags=[],
        emulator="simavr",
        emulator_args=[],
        sysroot=None,
        static=True,
    ),
}


def _toolchain_from_dict(name: str, raw: dict) -> Toolchain:
    return Toolchain(
        name=name,
        description=raw.get("description", ""),
        cc=raw["cc"],
        ar=raw.get("ar", "ar"),
        cflags=raw.get("cflags", []),
        emulator=raw.get("emulator", None),
        emulator_args=raw.get("emulator_args", []),
        sysroot=raw.get("sysroot", None),
        static=raw.get("static", False),
    )


def get_toolchain(name: str, config: dict) -> Toolchain:
    """Resolve toolchain by name. User config wins over builtins. Raises ForgeToolchainError if unknown."""
    user_toolchains = config.get("toolchains", {})

    if name in user_toolchains:
        return _toolchain_from_dict(name, user_toolchains[name])

    if name in BUILTIN_TOOLCHAINS:
        return BUILTIN_TOOLCHAINS[name]

    available = sorted(set(BUILTIN_TOOLCHAINS) | set(user_toolchains))
    raise ForgeToolchainError(
        f"Unknown toolchain target {name!r}. "
        f"Available: {', '.join(available)}"
    )
