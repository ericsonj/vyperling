"""vyperling.unity — accessors for vendored Unity C test framework (v2.6.1, MIT)."""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path

from vyperling.errors import ForgeError


def _unity_dir() -> Path:
    return Path(str(files("vyperling").joinpath("c")))


def get_unity_c_path() -> Path:
    """Absolute path to vendored unity.c.

    Raises ForgeError for broken/incomplete installs.
    """
    path = _unity_dir() / "unity.c"
    if not path.is_file():
        raise ForgeError(
            f"Vendored unity.c not found at {path}. "
            "vyperling installation may be incomplete."
        )
    return path


def get_unity_include_dir() -> Path:
    """Absolute path to vyperling/c/ — pass as -I flag to compiler.

    Raises ForgeError for broken/incomplete installs.
    """
    path = _unity_dir()
    if not path.is_dir():
        raise ForgeError(
            f"Vendored Unity include dir not found at {path}. "
            "vyperling installation may be incomplete."
        )
    return path


def get_forge_mock_c_path() -> Path:
    """Absolute path to vendored forge_mock.c (the mock runtime).

    Compiled into every test binary alongside unity.c.
    Raises ForgeError for broken/incomplete installs.
    """
    path = _unity_dir() / "forge_mock.c"
    if not path.is_file():
        raise ForgeError(
            f"Vendored forge_mock.c not found at {path}. "
            "vyperling installation may be incomplete."
        )
    return path


def get_forge_mock_include_dir() -> Path:
    """Absolute path to vyperling/c/ — same dir as Unity, holds forge_mock.h."""
    return get_unity_include_dir()
