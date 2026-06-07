"""Tests for vyperling.toolchains — Toolchain dataclass, built-in registry, resolver."""

import dataclasses

import pytest

from vyperling.errors import ForgeToolchainError
from vyperling.toolchains import BUILTIN_TOOLCHAINS, Toolchain, get_toolchain

BUILTIN_NAMES = [
    "native",
    "mips32",
    "mips32el",
    "mips32r5",
    "arm-linux",
    "arm-cortex-m4",
    "arm-cortex-m4-pyocd",
    "arm-cortex-m0",
    "riscv32",
    "avr",
]

EMPTY_CONFIG: dict = {"toolchains": {}}


# ---------------------------------------------------------------------------
# TestToolchainDataclass
# ---------------------------------------------------------------------------

class TestToolchainDataclass:
    def test_has_nine_fields(self):
        assert len(dataclasses.fields(Toolchain)) == 9

    def test_field_names(self):
        names = {f.name for f in dataclasses.fields(Toolchain)}
        assert names == {
            "name", "description", "cc", "ar", "cflags",
            "emulator", "emulator_args", "sysroot", "static",
        }

    def test_instantiate_with_keyword_args(self):
        tc = Toolchain(
            name="test",
            description="test toolchain",
            cc="gcc",
            ar="ar",
            cflags=[],
            emulator=None,
            emulator_args=[],
            sysroot=None,
            static=False,
        )
        assert tc.name == "test"
        assert tc.cc == "gcc"

    def test_is_dataclass(self):
        assert dataclasses.is_dataclass(Toolchain)


# ---------------------------------------------------------------------------
# TestBuiltinToolchains
# ---------------------------------------------------------------------------

class TestBuiltinToolchains:
    def test_has_exactly_ten_entries(self):
        assert len(BUILTIN_TOOLCHAINS) == 10

    @pytest.mark.parametrize("name", BUILTIN_NAMES)
    def test_all_expected_names_present(self, name):
        assert name in BUILTIN_TOOLCHAINS

    @pytest.mark.parametrize("name", BUILTIN_NAMES)
    def test_all_values_are_toolchain_instances(self, name):
        assert isinstance(BUILTIN_TOOLCHAINS[name], Toolchain)

    def test_native_has_no_emulator(self):
        assert BUILTIN_TOOLCHAINS["native"].emulator is None

    def test_native_is_not_static(self):
        assert BUILTIN_TOOLCHAINS["native"].static is False

    def test_native_cc_is_gcc(self):
        assert BUILTIN_TOOLCHAINS["native"].cc == "gcc"

    def test_mips32_is_static(self):
        assert BUILTIN_TOOLCHAINS["mips32"].static is True

    def test_mips32_emulator(self):
        assert BUILTIN_TOOLCHAINS["mips32"].emulator == "qemu-mips"

    def test_mips32el_emulator(self):
        assert BUILTIN_TOOLCHAINS["mips32el"].emulator == "qemu-mipsel"

    def test_mips32r5_emulator_args(self):
        assert BUILTIN_TOOLCHAINS["mips32r5"].emulator_args == ["-cpu", "P5600"]

    def test_arm_cortex_m4_cflags(self):
        assert "-mcpu=cortex-m4" in BUILTIN_TOOLCHAINS["arm-cortex-m4"].cflags

    def test_arm_cortex_m4_thumb(self):
        assert "-mthumb" in BUILTIN_TOOLCHAINS["arm-cortex-m4"].cflags

    def test_arm_cortex_m0_cflags(self):
        assert "-mcpu=cortex-m0" in BUILTIN_TOOLCHAINS["arm-cortex-m0"].cflags

    def test_riscv32_cflags(self):
        assert "-march=rv32imc" in BUILTIN_TOOLCHAINS["riscv32"].cflags

    def test_avr_emulator(self):
        assert BUILTIN_TOOLCHAINS["avr"].emulator == "simavr"

    def test_all_builtins_have_no_sysroot(self):
        for name, tc in BUILTIN_TOOLCHAINS.items():
            assert tc.sysroot is None, f"{name} should have sysroot=None"

    @pytest.mark.parametrize("name", BUILTIN_NAMES)
    def test_builtin_name_matches_key(self, name):
        assert BUILTIN_TOOLCHAINS[name].name == name


# ---------------------------------------------------------------------------
# TestGetToolchain
# ---------------------------------------------------------------------------

class TestGetToolchain:
    @pytest.mark.parametrize("name", BUILTIN_NAMES)
    def test_returns_builtin(self, name):
        tc = get_toolchain(name, EMPTY_CONFIG)
        assert isinstance(tc, Toolchain)
        assert tc.name == name

    def test_unknown_name_raises(self):
        with pytest.raises(ForgeToolchainError):
            get_toolchain("nonexistent-target", EMPTY_CONFIG)

    def test_error_message_lists_available_targets(self):
        with pytest.raises(ForgeToolchainError, match="native"):
            get_toolchain("nonexistent-target", EMPTY_CONFIG)

    def test_error_message_contains_unknown_name(self):
        with pytest.raises(ForgeToolchainError, match="nonexistent-target"):
            get_toolchain("nonexistent-target", EMPTY_CONFIG)

    def test_user_toolchain_wins_over_builtin(self):
        config = {
            "toolchains": {
                "native": {
                    "description": "custom native",
                    "cc": "clang",
                    "ar": "llvm-ar",
                    "cflags": ["-O2"],
                    "static": False,
                }
            }
        }
        tc = get_toolchain("native", config)
        assert tc.cc == "clang"
        assert tc.description == "custom native"

    def test_user_only_toolchain_resolved(self):
        config = {
            "toolchains": {
                "pic32mk": {
                    "description": "PIC32MK production",
                    "cc": "mips-linux-gnu-gcc",
                    "ar": "mips-linux-gnu-ar",
                    "cflags": ["-march=mips32r5"],
                    "emulator": "qemu-mips",
                    "emulator_args": ["-cpu", "P5600"],
                    "static": True,
                }
            }
        }
        tc = get_toolchain("pic32mk", config)
        assert tc.name == "pic32mk"
        assert tc.cc == "mips-linux-gnu-gcc"
        assert tc.static is True

    def test_user_toolchain_missing_optional_fields_get_defaults(self):
        config = {
            "toolchains": {
                "minimal": {
                    "cc": "gcc",
                }
            }
        }
        tc = get_toolchain("minimal", config)
        assert tc.emulator is None
        assert tc.emulator_args == []
        assert tc.sysroot is None
        assert tc.static is False
        assert tc.cflags == []

    def test_config_without_toolchains_key_works(self):
        config = {}
        tc = get_toolchain("native", config)
        assert tc.name == "native"

    def test_returns_toolchain_instance(self):
        tc = get_toolchain("native", EMPTY_CONFIG)
        assert isinstance(tc, Toolchain)

    def test_user_toolchain_listed_in_error_for_unknown(self):
        config = {"toolchains": {"custom-tc": {"cc": "gcc"}}}
        with pytest.raises(ForgeToolchainError, match="custom-tc"):
            get_toolchain("nonexistent-target", config)
