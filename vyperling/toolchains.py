"""vyperling.toolchains — Toolchain dataclass, built-in registry, and resolver."""

from __future__ import annotations

from dataclasses import dataclass

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
    # arm-linux-gnueabihf: Linux userspace ARM — mirrors MIPS pattern.
    # qemu-arm (user mode) works without semihosting; static=True avoids sysroot.
    "arm-linux": Toolchain(
        name="arm-linux",
        description="ARM Linux gnueabihf — arm-linux-gnueabihf-gcc + qemu-arm (user mode)",
        cc="arm-linux-gnueabihf-gcc",
        ar="arm-linux-gnueabihf-ar",
        cflags=["-march=armv7-a", "-mfpu=vfpv3-d16", "-mfloat-abi=hard"],
        emulator="qemu-arm",
        emulator_args=[],
        sysroot=None,
        static=True,
    ),
    # ARM Cortex-M4 bare-metal under qemu-arm (user mode). Three parts work together:
    #
    #   cflags --specs=rdimon.specs -lrdimon
    #       Bare-metal libc has no OS to call. rdimon ("rdi monitor") links the
    #       semihosting C library: printf/exit/etc. compile down to a BKPT 0xAB
    #       instruction (the ARM semihosting call), instead of a Linux syscall.
    #
    #   emulator_args -cpu cortex-m4   (REQUIRED — not optional)
    #       qemu-arm's default CPU is an A-profile core that does not implement the
    #       M-profile thumb semihosting trap. Without this flag the BKPT is treated
    #       as a real breakpoint → "uncaught target signal 5 (SIGTRAP)" core dump.
    #       -cpu cortex-m4 selects an M-profile core that intercepts the trap and
    #       services it as a semihosting request — forwarding stdout/exit to host.
    #
    #   NO -semihosting flag
    #       That flag belongs to qemu-SYSTEM (full-machine emulation). qemu-arm
    #       USER mode enables semihosting automatically and ERRORS on the flag
    #       ("unknown option 'semihosting'"), quitting before the binary runs —
    #       which silently parses as 0 tests. Pass -cpu only.
    #
    # Result: Unity's printf output reaches stdout, runner parses it, exit code
    # propagates. static=True keeps the ELF self-contained (no sysroot needed).
    "arm-cortex-m4": Toolchain(
        name="arm-cortex-m4",
        description="ARM Cortex-M4 bare-metal — arm-none-eabi-gcc + qemu-arm-static -cpu cortex-m4 (semihosting)",
        cc="arm-none-eabi-gcc",
        ar="arm-none-eabi-ar",
        cflags=["-mcpu=cortex-m4", "-mthumb", "--specs=rdimon.specs", "-lrdimon"],
        emulator="qemu-arm-static",
        emulator_args=["-cpu", "cortex-m4"],
        sysroot=None,
        static=True,
    ),
    # arm-cortex-m4-pyocd: real hardware via SWD. --target must match the chip (e.g. stm32f407vg).
    # Override emulator_args in forge.yml toolchains to set the correct chip ID:
    #   toolchains:
    #     arm-cortex-m4-pyocd:
    #       emulator_args: ["run", "--target", "stm32f407vg"]
    "arm-cortex-m4-pyocd": Toolchain(
        name="arm-cortex-m4-pyocd",
        description="ARM Cortex-M4 on real hardware — arm-none-eabi-gcc + pyocd run",
        cc="arm-none-eabi-gcc",
        ar="arm-none-eabi-ar",
        cflags=["-mcpu=cortex-m4", "-mthumb", "--specs=rdimon.specs", "-lrdimon"],
        emulator="pyocd",
        emulator_args=["run", "--target", "cortex_m"],
        sysroot=None,
        static=True,
    ),
    "arm-cortex-m0": Toolchain(
        name="arm-cortex-m0",
        description="ARM Cortex-M0 bare-metal — arm-none-eabi-gcc + qemu-arm-static -cpu cortex-m0 (semihosting)",
        cc="arm-none-eabi-gcc",
        ar="arm-none-eabi-ar",
        cflags=["-mcpu=cortex-m0", "-mthumb", "--specs=rdimon.specs", "-lrdimon"],
        emulator="qemu-arm-static",
        emulator_args=["-cpu", "cortex-m0"],
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
        f"Unknown toolchain target {name!r}. " f"Available: {', '.join(available)}"
    )
