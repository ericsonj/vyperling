"""Tests for vyperling.discoverer — TestUnit dataclass and discover()."""

import dataclasses
from pathlib import Path

import pytest

from vyperling.config import load_config
from vyperling.discoverer import TestUnit, _parse_mock_includes, discover


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_project(tmp_path: Path, src_files=(), test_files=()):
    (tmp_path / "src").mkdir(exist_ok=True)
    (tmp_path / "test").mkdir(exist_ok=True)
    for name in src_files:
        (tmp_path / "src" / name).write_text("")
    for name in test_files:
        (tmp_path / "test" / name).write_text("")
    (tmp_path / "forge.yml").write_text("project:\n  name: proj\n")
    return load_config(tmp_path / "forge.yml")


# ---------------------------------------------------------------------------
# TestTestUnitDataclass
# ---------------------------------------------------------------------------

class TestTestUnitDataclass:
    def test_is_dataclass(self):
        assert dataclasses.is_dataclass(TestUnit)

    def test_has_five_fields(self):
        assert len(dataclasses.fields(TestUnit)) == 5

    def test_field_names(self):
        names = {f.name for f in dataclasses.fields(TestUnit)}
        assert names == {"test_file", "source_file", "name", "mocks", "extra_srcs"}

    def test_mocks_defaults_empty(self):
        unit = TestUnit(test_file=Path("t.c"), source_file=None, name="x")
        assert unit.mocks == []

    def test_extra_srcs_defaults_empty(self):
        unit = TestUnit(test_file=Path("t.c"), source_file=None, name="x")
        assert unit.extra_srcs == []

    def test_instantiate_with_keyword_args(self):
        unit = TestUnit(test_file=Path("test/test_uart.c"), source_file=None, name="uart")
        assert unit.name == "uart"
        assert unit.source_file is None

    def test_source_file_accepts_path(self):
        unit = TestUnit(
            test_file=Path("test/test_uart.c"),
            source_file=Path("src/uart.c"),
            name="uart",
        )
        assert unit.source_file == Path("src/uart.c")


# ---------------------------------------------------------------------------
# TestDiscover
# ---------------------------------------------------------------------------

class TestDiscover:
    def test_empty_test_dir_returns_empty_list(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cfg = make_project(tmp_path)
        assert discover(cfg) == []

    def test_missing_test_dir_returns_empty_list(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "forge.yml").write_text("project:\n  name: proj\n  test_dir: no_such_dir\n")
        cfg = load_config(tmp_path / "forge.yml")
        assert discover(cfg) == []

    def test_non_test_c_files_ignored(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cfg = make_project(tmp_path, test_files=["helper.c", "utils.h", "README.md"])
        assert discover(cfg) == []

    def test_single_test_file_no_source(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cfg = make_project(tmp_path, test_files=["test_uart.c"])
        with pytest.warns(UserWarning):
            units = discover(cfg)
        assert len(units) == 1
        assert units[0].name == "uart"
        assert units[0].source_file is None

    def test_parses_mock_includes(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cfg = make_project(tmp_path, src_files=["uart.c"], test_files=["test_uart.c"])
        (tmp_path / "test" / "test_uart.c").write_text(
            '#include "unity.h"\n'
            '#include "uart.h"\n'
            '#include "mock_spi.h"\n'
            '#include "mock_clock.h"\n'
            '#include "mock_spi.h"\n'  # duplicate -> deduped
        )
        units = discover(cfg)
        assert units[0].mocks == ["spi", "clock"]

    def test_no_mock_includes_yields_empty(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cfg = make_project(tmp_path, src_files=["uart.c"], test_files=["test_uart.c"])
        (tmp_path / "test" / "test_uart.c").write_text('#include "uart.h"\n')
        assert discover(cfg)[0].mocks == []

    def test_single_test_file_with_source(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cfg = make_project(tmp_path, src_files=["uart.c"], test_files=["test_uart.c"])
        units = discover(cfg)
        assert len(units) == 1
        assert units[0].name == "uart"
        assert units[0].source_file == Path("src/uart.c")
        assert units[0].test_file == Path("test/test_uart.c")

    def test_returns_list_of_test_units(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cfg = make_project(tmp_path, src_files=["uart.c"], test_files=["test_uart.c"])
        units = discover(cfg)
        assert isinstance(units, list)
        assert all(isinstance(u, TestUnit) for u in units)

    def test_multiple_test_files_all_returned(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cfg = make_project(
            tmp_path,
            src_files=["uart.c", "spi.c"],
            test_files=["test_uart.c", "test_spi.c"],
        )
        units = discover(cfg)
        assert len(units) == 2

    def test_multiple_test_files_sorted_by_name(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cfg = make_project(
            tmp_path,
            src_files=["uart.c", "spi.c", "adc.c"],
            test_files=["test_uart.c", "test_spi.c", "test_adc.c"],
        )
        units = discover(cfg)
        names = [u.name for u in units]
        assert names == sorted(names)

    def test_source_not_found_emits_user_warning(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cfg = make_project(tmp_path, test_files=["test_uart.c"])
        with pytest.warns(UserWarning, match="uart"):
            discover(cfg)

    def test_source_found_no_warning(self, tmp_path, monkeypatch, recwarn):
        monkeypatch.chdir(tmp_path)
        cfg = make_project(tmp_path, src_files=["uart.c"], test_files=["test_uart.c"])
        discover(cfg)
        assert len(recwarn) == 0

    def test_filter_pattern_match(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cfg = make_project(
            tmp_path,
            src_files=["uart.c", "spi.c"],
            test_files=["test_uart.c", "test_spi.c"],
        )
        units = discover(cfg, filter_pattern="uart")
        assert len(units) == 1
        assert units[0].name == "uart"

    def test_filter_pattern_no_match_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cfg = make_project(
            tmp_path,
            src_files=["uart.c"],
            test_files=["test_uart.c"],
        )
        units = discover(cfg, filter_pattern="nonexistent")
        assert units == []

    def test_filter_pattern_none_returns_all(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cfg = make_project(
            tmp_path,
            src_files=["uart.c", "spi.c"],
            test_files=["test_uart.c", "test_spi.c"],
        )
        units = discover(cfg, filter_pattern=None)
        assert len(units) == 2

    def test_filter_pattern_substring_matches_multiple(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cfg = make_project(
            tmp_path,
            test_files=["test_uart_init.c", "test_uart_send.c", "test_spi.c"],
        )
        with pytest.warns(UserWarning):
            units = discover(cfg, filter_pattern="uart")
        names = [u.name for u in units]
        assert "uart_init" in names
        assert "uart_send" in names
        assert "spi" not in names

    def test_multiple_src_dirs_first_match_wins(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "src").mkdir()
        (tmp_path / "lib").mkdir()
        (tmp_path / "test").mkdir()
        (tmp_path / "src" / "uart.c").write_text("")
        (tmp_path / "lib" / "uart.c").write_text("")
        (tmp_path / "test" / "test_uart.c").write_text("")
        (tmp_path / "forge.yml").write_text(
            "project:\n  name: proj\n  src_dirs:\n    - src\n    - lib\n"
        )
        cfg = load_config(tmp_path / "forge.yml")
        units = discover(cfg)
        assert units[0].source_file == Path("src/uart.c")

    def test_multiple_src_dirs_fallback_to_second(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "src").mkdir()
        (tmp_path / "lib").mkdir()
        (tmp_path / "test").mkdir()
        (tmp_path / "lib" / "uart.c").write_text("")
        (tmp_path / "test" / "test_uart.c").write_text("")
        (tmp_path / "forge.yml").write_text(
            "project:\n  name: proj\n  src_dirs:\n    - src\n    - lib\n"
        )
        cfg = load_config(tmp_path / "forge.yml")
        units = discover(cfg)
        assert units[0].source_file == Path("lib/uart.c")

    def test_test_file_path_is_path_type(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cfg = make_project(tmp_path, src_files=["uart.c"], test_files=["test_uart.c"])
        units = discover(cfg)
        assert isinstance(units[0].test_file, Path)

    def test_source_file_path_is_path_type(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cfg = make_project(tmp_path, src_files=["uart.c"], test_files=["test_uart.c"])
        units = discover(cfg)
        assert isinstance(units[0].source_file, Path)

    def test_mixed_found_and_missing_sources(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cfg = make_project(
            tmp_path,
            src_files=["uart.c"],
            test_files=["test_uart.c", "test_spi.c"],
        )
        with pytest.warns(UserWarning, match="spi"):
            units = discover(cfg)
        assert len(units) == 2
        uart = next(u for u in units if u.name == "uart")
        spi = next(u for u in units if u.name == "spi")
        assert uart.source_file is not None
        assert spi.source_file is None


    def test_multi_test_dir_list(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "test_a").mkdir()
        (tmp_path / "test_b").mkdir()
        (tmp_path / "src").mkdir()
        (tmp_path / "test_a" / "test_uart.c").write_text("")
        (tmp_path / "test_b" / "test_spi.c").write_text("")
        (tmp_path / "src" / "uart.c").write_text("")
        (tmp_path / "src" / "spi.c").write_text("")
        (tmp_path / "forge.yml").write_text(
            "project:\n  name: proj\n  test_dir:\n    - test_a\n    - test_b\n"
        )
        cfg = load_config(tmp_path / "forge.yml")
        units = discover(cfg)
        names = {u.name for u in units}
        assert names == {"uart", "spi"}

    def test_nested_test_file_via_rglob(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        nested = tmp_path / "test" / "module"
        nested.mkdir(parents=True)
        (tmp_path / "src").mkdir()
        (nested / "test_uart.c").write_text("")
        (tmp_path / "src" / "uart.c").write_text("")
        (tmp_path / "forge.yml").write_text("project:\n  name: proj\n")
        cfg = load_config(tmp_path / "forge.yml")
        units = discover(cfg)
        assert len(units) == 1
        assert units[0].name == "uart"

    def test_extra_srcs_populated_from_config(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "src").mkdir()
        (tmp_path / "test").mkdir()
        stub = tmp_path / "src" / "stub_helper.c"
        stub.write_text("")
        (tmp_path / "src" / "uart.c").write_text("")
        (tmp_path / "test" / "test_uart.c").write_text("")
        (tmp_path / "forge.yml").write_text(
            "project:\n"
            "  name: proj\n"
            "  extra_srcs:\n"
            "    uart:\n"
            "      - src/stub_helper.c\n"
        )
        cfg = load_config(tmp_path / "forge.yml")
        units = discover(cfg)
        assert units[0].name == "uart"
        assert Path("src/stub_helper.c") in units[0].extra_srcs

    def test_extra_srcs_empty_for_unit_not_in_map(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        cfg = make_project(tmp_path, src_files=["uart.c"], test_files=["test_uart.c"])
        units = discover(cfg)
        assert units[0].extra_srcs == []


class TestNamingConventions:
    """discover() respects conventions.test_prefix and conventions.mock_prefix."""

    def _forge(self, tmp_path: Path, extra_yaml: str = "") -> Path:
        (tmp_path / "src").mkdir(exist_ok=True)
        (tmp_path / "test").mkdir(exist_ok=True)
        return tmp_path / "forge.yml"

    def test_ceedling_test_prefix_discovers_Test_files(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "src").mkdir()
        (tmp_path / "test").mkdir()
        (tmp_path / "src" / "uart.c").write_text("")
        (tmp_path / "test" / "TestUart.c").write_text("")
        (tmp_path / "forge.yml").write_text(
            "project:\n  name: proj\nconventions:\n  test_prefix: \"Test\"\n"
        )
        cfg = load_config(tmp_path / "forge.yml")
        units = discover(cfg)
        assert len(units) == 1
        assert units[0].name == "Uart"

    def test_default_prefix_does_not_discover_Test_files(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "src").mkdir()
        (tmp_path / "test").mkdir()
        (tmp_path / "src" / "uart.c").write_text("")
        (tmp_path / "test" / "TestUart.c").write_text("")
        (tmp_path / "forge.yml").write_text("project:\n  name: proj\n")
        cfg = load_config(tmp_path / "forge.yml")
        units = discover(cfg)
        assert units == []

    def test_ceedling_mock_prefix_parses_Mock_includes(self, tmp_path):
        f = tmp_path / "TestFoo.c"
        f.write_text('#include "MockClock.h"\n#include "MockTimer.h"\n')
        result = _parse_mock_includes(f, mock_prefix="Mock")
        assert result == ["Clock", "Timer"]

    def test_default_mock_prefix_does_not_match_Mock_includes(self, tmp_path):
        f = tmp_path / "test_foo.c"
        f.write_text('#include "MockClock.h"\n')
        result = _parse_mock_includes(f, mock_prefix="mock_")
        assert result == []

    def test_discover_with_Mock_prefix_populates_unit_mocks(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "src").mkdir()
        (tmp_path / "test").mkdir()
        (tmp_path / "src" / "uart.c").write_text("")
        (tmp_path / "test" / "TestUart.c").write_text(
            '#include "MockClock.h"\n'
        )
        (tmp_path / "forge.yml").write_text(
            "project:\n  name: proj\n"
            "conventions:\n  test_prefix: \"Test\"\n  mock_prefix: \"Mock\"\n"
        )
        cfg = load_config(tmp_path / "forge.yml")
        units = discover(cfg)
        assert units[0].mocks == ["Clock"]


class TestParseMockIncludes:
    def test_unreadable_file_returns_empty(self, tmp_path):
        # Nonexistent path -> read_text raises OSError -> returns [].
        assert _parse_mock_includes(tmp_path / "ghost.c") == []
