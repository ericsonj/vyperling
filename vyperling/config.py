"""vyperling.config — forge.yml loader, validator, and accessor API."""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

from vyperling.errors import ForgeConfigError

DEFAULT_CONFIG: dict[str, Any] = {
    "project": {
        "name": None,
        "src_dirs": ["src"],
        "test_dir": "test",
        "include_dirs": ["src"],
        "build_dir": "build",
        "mock_dir": "mocks",
        "support_srcs": [],
        "extra_srcs": {},
    },
    "targets": {
        "default": "native",
    },
    "compiler": {
        "extra_cflags": [],
        "defines": [],
    },
    "toolchains": {},
    "conventions": {
        "test_prefix": "test_",
        "mock_prefix": "mock_",
        "test_naming": "snake_case",
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def find_config(start: Path) -> Path:
    """Walk up from start until forge.yml is found. Raises ForgeConfigError if not found."""
    current = start.resolve()
    while True:
        candidate = current / "forge.yml"
        if candidate.is_file():
            return candidate
        parent = current.parent
        if parent == current:
            raise ForgeConfigError(
                f"forge.yml not found in {start} or any parent directory."
            )
        current = parent


def load_config(config_path: Path) -> dict:
    """Load forge.yml, validate, deep-merge with defaults. Raises ForgeConfigError on any error."""
    try:
        raw = config_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ForgeConfigError(f"Cannot read {config_path}: {exc}") from exc

    try:
        parsed = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ForgeConfigError(f"Invalid YAML in {config_path}: {exc}") from exc

    if not isinstance(parsed, dict):
        raise ForgeConfigError(
            f"{config_path} is empty or not a YAML mapping."
        )

    project = parsed.get("project")
    if not isinstance(project, dict) or not project.get("name"):
        raise ForgeConfigError(
            f"{config_path}: 'project.name' is required but missing or empty."
        )

    return _deep_merge(DEFAULT_CONFIG, parsed)


def get_build_dir(config: dict, target: str) -> Path:
    return Path(config["project"]["build_dir"]) / target


def get_test_dir(config: dict) -> Path:
    return Path(config["project"]["test_dir"])


def get_src_dirs(config: dict) -> list[Path]:
    return [Path(d) for d in config["project"]["src_dirs"]]


def get_include_dirs(config: dict) -> list[Path]:
    return [Path(d) for d in config["project"]["include_dirs"]]


def get_mock_dir(config: dict) -> Path:
    return Path(config["project"]["mock_dir"])
