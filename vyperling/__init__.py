"""vyperling — Embedded C test runner with cross-compilation support."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("vyperling")
except PackageNotFoundError:  # editable/dev install without resolvable metadata
    __version__ = "0.0.0+dev"
