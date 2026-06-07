"""Tests for vyperling.config — forge.yml loader and accessors."""

from pathlib import Path

import pytest

from vyperling.config import (
    DEFAULT_CONFIG,
    find_config,
    get_build_dir,
    get_include_dirs,
    get_src_dirs,
    get_test_dir,
    load_config,
)
from vyperling.errors import ForgeConfigError

MINIMAL_YAML = "project:\n  name: myproj\n"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def write_forge_yml(directory: Path, content: str = MINIMAL_YAML) -> Path:
    path = directory / "forge.yml"
    path.write_text(content, encoding="utf-8")
    return path


def minimal_config() -> dict:
    return load_config(write_forge_yml(_make_tmp()))


def _make_tmp(tmp_path_factory=None):
    # only used via write_forge_yml in parametrize helpers — not a fixture
    pass


# ---------------------------------------------------------------------------
# TestFindConfig
# ---------------------------------------------------------------------------

class TestFindConfig:
    def test_finds_in_given_dir(self, tmp_path):
        write_forge_yml(tmp_path)
        assert find_config(tmp_path) == tmp_path / "forge.yml"

    def test_returns_path_type(self, tmp_path):
        write_forge_yml(tmp_path)
        assert isinstance(find_config(tmp_path), Path)

    def test_returns_absolute(self, tmp_path):
        write_forge_yml(tmp_path)
        assert find_config(tmp_path).is_absolute()

    def test_walks_up_to_parent(self, tmp_path):
        forge_yml = write_forge_yml(tmp_path)
        subdir = tmp_path / "src" / "deep"
        subdir.mkdir(parents=True)
        assert find_config(subdir) == forge_yml

    def test_walks_up_multiple_levels(self, tmp_path):
        forge_yml = write_forge_yml(tmp_path)
        deep = tmp_path / "a" / "b" / "c"
        deep.mkdir(parents=True)
        assert find_config(deep) == forge_yml

    def test_raises_when_not_found(self, tmp_path):
        # tmp_path has no forge.yml — walk hits root with none found
        # Use a subdir that won't accidentally find a forge.yml from the real FS.
        # tmp_path is already isolated; just ensure there's no forge.yml.
        with pytest.raises(ForgeConfigError, match="forge.yml not found"):
            find_config(tmp_path)

    def test_prefers_closest_forge_yml(self, tmp_path):
        write_forge_yml(tmp_path)
        subdir = tmp_path / "sub"
        subdir.mkdir()
        inner_yml = write_forge_yml(subdir, "project:\n  name: inner\n")
        assert find_config(subdir) == inner_yml


# ---------------------------------------------------------------------------
# TestLoadConfig
# ---------------------------------------------------------------------------

class TestLoadConfig:
    def test_minimal_valid_yaml(self, tmp_path):
        cfg = load_config(write_forge_yml(tmp_path))
        assert cfg["project"]["name"] == "myproj"

    def test_returns_dict(self, tmp_path):
        cfg = load_config(write_forge_yml(tmp_path))
        assert isinstance(cfg, dict)

    def test_missing_project_name_raises(self, tmp_path):
        path = write_forge_yml(tmp_path, "project:\n  src_dirs: [src]\n")
        with pytest.raises(ForgeConfigError, match="project.name"):
            load_config(path)

    def test_empty_project_name_raises(self, tmp_path):
        path = write_forge_yml(tmp_path, "project:\n  name: \n")
        with pytest.raises(ForgeConfigError, match="project.name"):
            load_config(path)

    def test_empty_file_raises(self, tmp_path):
        path = write_forge_yml(tmp_path, "")
        with pytest.raises(ForgeConfigError):
            load_config(path)

    def test_invalid_yaml_raises(self, tmp_path):
        path = write_forge_yml(tmp_path, "project:\n  name: [unclosed\n")
        with pytest.raises(ForgeConfigError, match="Invalid YAML"):
            load_config(path)

    def test_unreadable_file_raises(self, tmp_path):
        path = tmp_path / "forge.yml"
        with pytest.raises(ForgeConfigError, match="Cannot read"):
            load_config(path)

    def test_defaults_filled_for_partial_config(self, tmp_path):
        cfg = load_config(write_forge_yml(tmp_path, MINIMAL_YAML))
        assert cfg["project"]["src_dirs"] == DEFAULT_CONFIG["project"]["src_dirs"]
        assert cfg["project"]["test_dir"] == DEFAULT_CONFIG["project"]["test_dir"]
        assert cfg["project"]["build_dir"] == DEFAULT_CONFIG["project"]["build_dir"]
        assert cfg["project"]["mock_dir"] == DEFAULT_CONFIG["project"]["mock_dir"]
        assert cfg["targets"] == DEFAULT_CONFIG["targets"]
        assert cfg["compiler"] == DEFAULT_CONFIG["compiler"]

    def test_support_srcs_default_empty(self, tmp_path):
        cfg = load_config(write_forge_yml(tmp_path, MINIMAL_YAML))
        assert cfg["project"]["support_srcs"] == []

    def test_extra_srcs_default_empty_dict(self, tmp_path):
        cfg = load_config(write_forge_yml(tmp_path, MINIMAL_YAML))
        assert cfg["project"]["extra_srcs"] == {}

    def test_user_list_replaces_default_list(self, tmp_path):
        yaml_content = "project:\n  name: proj\n  src_dirs:\n    - custom\n    - extra\n"
        cfg = load_config(write_forge_yml(tmp_path, yaml_content))
        assert cfg["project"]["src_dirs"] == ["custom", "extra"]

    def test_user_dict_merged_with_defaults(self, tmp_path):
        yaml_content = "project:\n  name: proj\ncompiler:\n  extra_cflags: [-Wall]\n"
        cfg = load_config(write_forge_yml(tmp_path, yaml_content))
        assert cfg["compiler"]["extra_cflags"] == ["-Wall"]
        assert cfg["compiler"]["defines"] == []  # default preserved

    def test_cexception_defaults_false(self, tmp_path):
        cfg = load_config(write_forge_yml(tmp_path, MINIMAL_YAML))
        assert cfg["compiler"]["cexception"] is False

    def test_cexception_enabled_via_config(self, tmp_path):
        yaml_content = "project:\n  name: proj\ncompiler:\n  cexception: true\n"
        cfg = load_config(write_forge_yml(tmp_path, yaml_content))
        assert cfg["compiler"]["cexception"] is True

    def test_user_value_wins_over_default(self, tmp_path):
        yaml_content = "project:\n  name: proj\n  build_dir: dist\n"
        cfg = load_config(write_forge_yml(tmp_path, yaml_content))
        assert cfg["project"]["build_dir"] == "dist"

    def test_does_not_mutate_default_config(self, tmp_path):
        original_defaults = str(DEFAULT_CONFIG)
        load_config(write_forge_yml(tmp_path))
        assert str(DEFAULT_CONFIG) == original_defaults

    def test_toolchains_empty_by_default(self, tmp_path):
        cfg = load_config(write_forge_yml(tmp_path))
        assert cfg["toolchains"] == {}

    def test_custom_toolchain_preserved(self, tmp_path):
        yaml_content = (
            "project:\n  name: proj\n"
            "toolchains:\n"
            "  pic32mk:\n"
            "    cc: mips-linux-gnu-gcc\n"
            "    cflags: [-march=mips32r5]\n"
        )
        cfg = load_config(write_forge_yml(tmp_path, yaml_content))
        assert cfg["toolchains"]["pic32mk"]["cc"] == "mips-linux-gnu-gcc"


# ---------------------------------------------------------------------------
# TestAccessors
# ---------------------------------------------------------------------------

class TestGetBuildDir:
    def test_native_target(self, tmp_path):
        cfg = load_config(write_forge_yml(tmp_path))
        assert get_build_dir(cfg, "native") == Path("build/native")

    def test_custom_target(self, tmp_path):
        cfg = load_config(write_forge_yml(tmp_path))
        assert get_build_dir(cfg, "pic32mk") == Path("build/pic32mk")

    def test_returns_path(self, tmp_path):
        cfg = load_config(write_forge_yml(tmp_path))
        assert isinstance(get_build_dir(cfg, "native"), Path)

    def test_custom_build_dir(self, tmp_path):
        yaml_content = "project:\n  name: proj\n  build_dir: dist\n"
        cfg = load_config(write_forge_yml(tmp_path, yaml_content))
        assert get_build_dir(cfg, "native") == Path("dist/native")


class TestGetTestDir:
    def test_default(self, tmp_path):
        cfg = load_config(write_forge_yml(tmp_path))
        assert get_test_dir(cfg) == Path("test")

    def test_custom(self, tmp_path):
        yaml_content = "project:\n  name: proj\n  test_dir: tests\n"
        cfg = load_config(write_forge_yml(tmp_path, yaml_content))
        assert get_test_dir(cfg) == Path("tests")

    def test_returns_path(self, tmp_path):
        cfg = load_config(write_forge_yml(tmp_path))
        assert isinstance(get_test_dir(cfg), Path)


class TestGetSrcDirs:
    def test_default(self, tmp_path):
        cfg = load_config(write_forge_yml(tmp_path))
        assert get_src_dirs(cfg) == [Path("src")]

    def test_multiple_dirs(self, tmp_path):
        yaml_content = "project:\n  name: proj\n  src_dirs:\n    - src\n    - lib\n"
        cfg = load_config(write_forge_yml(tmp_path, yaml_content))
        assert get_src_dirs(cfg) == [Path("src"), Path("lib")]

    def test_returns_list_of_paths(self, tmp_path):
        cfg = load_config(write_forge_yml(tmp_path))
        result = get_src_dirs(cfg)
        assert isinstance(result, list)
        assert all(isinstance(p, Path) for p in result)


class TestConventionsDefaults:
    def test_conventions_key_present(self, tmp_path):
        cfg = load_config(write_forge_yml(tmp_path))
        assert "conventions" in cfg

    def test_default_test_prefix(self, tmp_path):
        cfg = load_config(write_forge_yml(tmp_path))
        assert cfg["conventions"]["test_prefix"] == "test_"

    def test_default_mock_prefix(self, tmp_path):
        cfg = load_config(write_forge_yml(tmp_path))
        assert cfg["conventions"]["mock_prefix"] == "mock_"

    def test_default_test_naming(self, tmp_path):
        cfg = load_config(write_forge_yml(tmp_path))
        assert cfg["conventions"]["test_naming"] == "snake_case"

    def test_override_test_prefix(self, tmp_path):
        yaml_content = "project:\n  name: proj\nconventions:\n  test_prefix: \"Test\"\n"
        cfg = load_config(write_forge_yml(tmp_path, yaml_content))
        assert cfg["conventions"]["test_prefix"] == "Test"

    def test_override_mock_prefix(self, tmp_path):
        yaml_content = "project:\n  name: proj\nconventions:\n  mock_prefix: \"Mock\"\n"
        cfg = load_config(write_forge_yml(tmp_path, yaml_content))
        assert cfg["conventions"]["mock_prefix"] == "Mock"

    def test_override_test_naming(self, tmp_path):
        yaml_content = "project:\n  name: proj\nconventions:\n  test_naming: \"camelCase\"\n"
        cfg = load_config(write_forge_yml(tmp_path, yaml_content))
        assert cfg["conventions"]["test_naming"] == "camelCase"

    def test_partial_override_preserves_other_defaults(self, tmp_path):
        yaml_content = "project:\n  name: proj\nconventions:\n  test_prefix: \"Test\"\n"
        cfg = load_config(write_forge_yml(tmp_path, yaml_content))
        assert cfg["conventions"]["mock_prefix"] == "mock_"
        assert cfg["conventions"]["test_naming"] == "snake_case"


class TestGetIncludeDirs:
    def test_default(self, tmp_path):
        cfg = load_config(write_forge_yml(tmp_path))
        assert get_include_dirs(cfg) == [Path("src")]

    def test_multiple_dirs(self, tmp_path):
        yaml_content = "project:\n  name: proj\n  include_dirs:\n    - src\n    - include\n"
        cfg = load_config(write_forge_yml(tmp_path, yaml_content))
        assert get_include_dirs(cfg) == [Path("src"), Path("include")]

    def test_returns_list_of_paths(self, tmp_path):
        cfg = load_config(write_forge_yml(tmp_path))
        result = get_include_dirs(cfg)
        assert isinstance(result, list)
        assert all(isinstance(p, Path) for p in result)
