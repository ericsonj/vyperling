"""vyperling.errors — centralised exception hierarchy."""


class ForgeError(Exception):
    """Base class for all vyperling errors. CLI catches this and exits 1."""


class ForgeConfigError(ForgeError):
    """forge.yml not found, missing required field, or invalid schema. CLI exits 2."""


class ForgeToolchainError(ForgeError):
    """Unknown target name or compiler binary not on PATH. CLI exits 3."""


class ForgeCompileError(ForgeError):
    """Unrecoverable compiler setup error.

    Per-unit compile failures are captured in CompileResult.success, not raised.
    """


class ForgeMockgenError(ForgeError):
    """C header could not be parsed by the mock generator."""


class ForgeCoverageError(ForgeError):
    """Coverage tooling missing, no .gcda data, or gcovr failed.

    Coverage is best-effort: the CLI prints this as a warning and does NOT
    change the test exit code.
    """


class ForgeScaffoldError(ForgeError):
    """`vyperling new` target directory already exists or could not be written."""
