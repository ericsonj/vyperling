# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`vyperling` is a pip-installable embedded-C unit test runner — a Ceedling replacement with no Ruby. It discovers `test_*.c` files, auto-generates CMock-style mocks from C headers, cross-compiles per target (native GCC or cross-GCC), runs binaries directly or under QEMU/simavr, parses Unity output, and reports to terminal/JUnit/coverage.

The CLI ships **two equivalent entrypoints**, `vyperling` and `vpl` (alias) — both map to `vyperling.cli:cli` in [pyproject.toml](pyproject.toml#L34-L36). Use either interchangeably in commands and docs.

## Commands

```bash
pip install -e .              # editable dev install (registers vyperling + vpl)
pytest                        # full suite; coverage on by default (see pyproject addopts)
pytest tests/test_mockgen.py  # single test file
pytest -k cross_compile       # single test by name substring
pytest --no-cov               # disable the auto coverage report
```

CLI (after install — `vpl` is the short alias for `vyperling`):

```bash
vpl test --target mips32 -k uart -j4 --coverage   # discover→mock→compile→run→report
vpl mock src/uart.h                                # generate mocks/mock_uart.{c,h}
vpl targets                                        # list toolchain profiles
```

`pip install -e .` is required before the CLI works — `pytest` does **not** need it (tests import the package directly).

NEVER run a build after changes (global rule). To verify compilation, ask first.

## Architecture — the test pipeline

The `vpl test` flow is a linear pipeline; each module is one stage and they connect through three dataclasses (`TestUnit` → `CompileResult` → `RunResult`). Understanding the dataclass handoff is the fastest way to read this codebase:

1. [config.py](vyperling/config.py) — loads `forge.yml`, walks **up** the tree to find it (`find_config`), deep-merges over `DEFAULT_CONFIG`. `project.name` is the only required field. All `get_*` accessors return `Path`s relative to cwd.
2. [toolchains.py](vyperling/toolchains.py) — `Toolchain` dataclass + `BUILTIN_TOOLCHAINS` registry. `get_toolchain` resolves by name; **user `toolchains:` config wins over builtins**. A toolchain carries `cc`/`ar`/`cflags`/`emulator`/`static` — this is the single source of truth for both compile flags and how to run the binary.
3. [discoverer.py](vyperling/discoverer.py) — globs `test_dir/test_*.c`, strips `test_` prefix to get the module name, matches `<name>.c` in `src_dirs`. Missing source **warns, never raises** → `TestUnit`.
4. [mockgen.py](vyperling/mockgen.py) — parses headers with **pycparser** (using the resolved toolchain's `cc -E` as preprocessor + `pycparser_fake_libc`), emits a full queue-based CMock-style API via **jinja2** templates. See the **mockgen divergence** note below.
5. [compiler.py](vyperling/compiler.py) — `subprocess` GCC invocation, `ThreadPoolExecutor` for `-j`. Caches via per-unit `*.forge_deps.json` (source mtimes); skips recompile when unchanged and binary exists. Compiles `unity.c` + `forge_mock.c` into **every** binary. Per-unit failures land in `CompileResult.success`, not exceptions → `CompileResult`.
6. [runner.py](vyperling/runner.py) — runs native (direct exec) or cross (`toolchain.emulator` + args, prepends `-L sysroot` if set), with timeout. Regex-parses Unity's `file:line:name:PASS|FAIL|IGNORE[:msg]` lines (strips ANSI first) → `RunResult`.
7. [reporter.py](vyperling/reporter.py) — `rich` terminal tables + `print_summary`; `write_junit_xml` for CI.
8. [coverage.py](vyperling/coverage.py) — **native-only**, best-effort. `gcovr` (pure-Python, no lcov) over `build/native/`'s `.gcda`. Excludes vendored/generated C from the report.

### Cross-cutting invariants

- **Errors:** all custom exceptions derive from `ForgeError` in [errors.py](vyperling/errors.py); the CLI catches `ForgeError` and converts to `click.ClickException`. The docstrings record intended exit codes (config=2, toolchain=3, etc.). Note the historical `Forge*` prefix — the project was renamed from "forge" to "vyperling" but the error/config/file naming (`forge.yml`, `forge_mock.c`, `*.forge_deps.json`, `ForgeError`) was kept. Don't "fix" these to `Vyperling*`.
- **Best-effort vs fatal:** missing source files (discoverer) and coverage failures (coverage) warn and continue; they never fail the test run. Config/toolchain problems are fatal.
- **Vendored C assets** live in [vyperling/c/](vyperling/c/) (Unity v2.6.1 + `forge_mock.{c,h}` runtime) and are accessed via `importlib.resources` in [unity.py](vyperling/unity.py) — never hardcode paths. They're bundled into the wheel via the `include` list in pyproject. jinja2 templates are in [vyperling/templates/](vyperling/templates/).

### mockgen divergence (read before touching mocks)

[mockgen.py](vyperling/mockgen.py:1) **intentionally supersedes** the regex-parser design in [vyperling-architecture.md](vyperling-architecture.md) sections 6.7/10. The real implementation is pycparser + jinja2 emitting the full CMock API (`_Expect`, `_ExpectAndReturn`, `_ReturnThruPtr_*`, `_Ignore`, `_AddCallback`, `mock_*_Init/_Verify/_Destroy`). The module docstring is authoritative; the architecture doc is stale on this point. v0.1 skips (with a warning) variadic functions, function-pointer params, and incomplete struct-by-value params. `TREAT_AS` maps C types → Unity assertion suffixes (typedefs matched before base types).

## Project status & workflow

Implementation follows [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md): steps 1–11 (all library modules) are ✅; **steps 12–17 remain** — `scaffold.py` (`vpl new`), full CLI wiring, the Python test suite, e2e smoke tests, and CI. Several `cli.py` commands (`new`, `test`, `build`, `clean`, `targets`) are still **stubs that print `[stub] … not yet implemented`**; only `mock` is wired. Per-step design lives in [plans/](plans/).

`.claude/hooks/` auto-syncs step status in DEVELOPMENT_PLAN.md: a `PreToolUse` hook on `Agent` marks a step 🔄 when a prompt mentions "step N"/"plan-0N", and the `Stop` hook flips it to ✅. To set status manually: `bash .claude/hooks/set-step.sh <N> [in_progress|done|pending]`. Be aware edits you make near a step boundary may get auto-marked.
