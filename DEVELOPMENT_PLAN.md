# vyperling — Development Plan

> Guide for implementing vyperling from scratch, step by step.  
> Each step maps to a plan document. Mark completion as you go.

---

## How to use this file

1. Pick the lowest-numbered ⬜ step with all dependencies ✅.
2. Create `plans/plan-NN-<name>.md` with detailed design for that step.
3. Implement it.
4. Run its tests.
5. Change status to ✅ in the table above.
6. Repeat.

---

## Progress overview

| # | Step | Status | Plan doc |
|---|------|--------|----------|
| 1 | Project scaffold & pyproject.toml | ✅ | [plan-01-scaffold.md](plans/plan-01-scaffold.md) |
| 2 | Vendor Unity C assets | ✅ | [plan-02-unity.md](plans/plan-02-unity.md) |
| 3 | `ForgeError` hierarchy | ✅ | [plan-03-errors.md](plans/plan-03-errors.md) |
| 4 | `config.py` — forge.yml loader | ✅ | [plan-04-config.md](plans/plan-04-config.md) |
| 5 | `toolchains.py` — Toolchain dataclass + built-in profiles | ✅ | [plan-05-toolchains.md](plans/plan-05-toolchains.md) |
| 6 | `discoverer.py` — test file discovery | ✅ | [plan-06-discoverer.md](plans/plan-06-discoverer.md) |
| 7 | `compiler.py` — subprocess GCC, parallel jobs, dep tracking | ✅ | [plan-07-compiler.md](plans/plan-07-compiler.md) |
| 8 | `runner.py` — native + QEMU execution, Unity output parsing | ✅ | [plan-08-runner.md](plans/plan-08-runner.md) |
| 9 | `reporter.py` — rich terminal table + JUnit XML | ✅ | [plan-09-reporter.md](plans/plan-09-reporter.md) |
| 10 | `mockgen.py` — C header parser + mock generator | ✅ | [plan-10-mockgen.md](plans/plan-10-mockgen.md) |
| 11 | `coverage.py` — gcov/lcov HTML pipeline | ✅ | [plan-11-coverage.md](plans/plan-11-coverage.md) |
| 12 | `scaffold.py` — `vyperling new` template generator | ✅ | [plan-12-scaffold-cmd.md](plans/plan-12-scaffold-cmd.md) |
| 13 | `cli.py` — Click entry point, all commands wired | ✅ | [plan-13-cli.md](plans/plan-13-cli.md) |
| 14 | Python test suite (`tests/`) | ✅ | [plan-14-tests.md](plans/plan-14-tests.md) |
| 15 | End-to-end smoke test (native target) | ✅ | [plan-15-e2e-native.md](plans/plan-15-e2e-native.md) |
| 16 | End-to-end smoke test (mips32 / cross-compile) | ✅ | [plan-16-e2e-mips32.md](plans/plan-16-e2e-mips32.md) |
| 17 | CI pipeline (GitHub Actions) | ✅ | [plan-17-ci.md](plans/plan-17-ci.md) |

**Status legend:** ⬜ pending · 🔄 in progress · ✅ done · ❌ blocked

---

## Step details

### Step 1 — Project scaffold & pyproject.toml

**Goal:** Bare installable package. `pip install -e .` works. `vyperling --help` prints help.

**Deliverables:**
- `pyproject.toml` with `hatchling` build backend, `click`, `rich`, `pyyaml` deps
- `vyperling/__init__.py`
- `vyperling/cli.py` — stub `cli` group with no commands yet
- `README.md`

**Dependencies:** none

---

### Step 2 — Vendor Unity C assets

**Goal:** Unity headers and source bundled inside the package and resolvable at runtime.

**Deliverables:**
- `vyperling/c/unity.h`, `unity.c`, `unity_internals.h`, `unity_fixture.h` (ThrowTheSwitch v2.5.4, MIT)
- `importlib.resources` accessor function in `vyperling/__init__.py` or `vyperling/unity.py`
- pyproject.toml `include` covers `vyperling/c/*.h` and `vyperling/c/*.c`

**Dependencies:** Step 1

---

### Step 3 — `ForgeError` hierarchy

**Goal:** Centralised exception types used by all modules.

**Deliverables:**
- `vyperling/errors.py`
  - `ForgeError`
  - `ForgeConfigError`
  - `ForgeToolchainError`
  - `ForgeCompileError`
  - `ForgeMockgenError`
  - `ForgeCoverageError` *(added in Step 11)*
  - `ForgeScaffoldError` *(added in Step 13)*

**Dependencies:** Step 1

---

### Step 4 — `config.py`

**Goal:** Load, validate, and deep-merge `forge.yml` with defaults.

**Deliverables:**
- `vyperling/config.py`
  - `DEFAULT_CONFIG` dict
  - `find_config(start)` — walks up cwd to find `forge.yml`
  - `load_config(config_path)` — loads + deep-merges
  - `get_build_dir(config, target) -> Path`
  - `get_test_dir(config) -> Path`
  - `get_src_dirs(config) -> list[Path]`
  - `get_include_dirs(config) -> list[Path]`
- `tests/test_config.py`

**Dependencies:** Steps 1, 3

---

### Step 5 — `toolchains.py`

**Goal:** `Toolchain` dataclass + registry of all 8 built-in profiles + custom resolver.

**Deliverables:**
- `vyperling/toolchains.py`
  - `Toolchain` dataclass
  - `BUILTIN_TOOLCHAINS` dict
  - `get_toolchain(name, config) -> Toolchain`

**Built-in profiles:** `native`, `mips32`, `mips32el`, `mips32r5`, `arm-cortex-m4`, `arm-cortex-m0`, `riscv32`, `avr`

**Dependencies:** Steps 1, 3

---

### Step 6 — `discoverer.py`

**Goal:** Find `test_*.c` files, resolve matching source files, apply filter.

**Deliverables:**
- `vyperling/discoverer.py`
  - `TestUnit` dataclass (`test_file`, `source_file`, `name`, `mocks`)
  - `discover(config, filter_pattern) -> list[TestUnit]`
  - Parses `#include "mock_<dep>.h"` lines from each test → `TestUnit.mocks` (deduped,
    ordered). Drives Ceedling-parity per-test mock linking (Step 7). *Added in Step 13.*
- `tests/test_discoverer.py`

**Dependencies:** Steps 1, 4

---

### Step 7 — `compiler.py`

**Goal:** Compile each `TestUnit` into an executable; parallel jobs; dep tracking.

**Deliverables:**
- `vyperling/compiler.py`
  - `CompileResult` dataclass
  - `compile_unit(unit, toolchain, config, verbose) -> CompileResult`
  - `compile_all(units, toolchain, config, jobs, verbose) -> list[CompileResult]`
  - `.forge_deps` JSON dep tracking (skip unchanged)
  - Coverage flags injected when `--coverage` + native
  - Links each binary against ONLY the mocks the test includes (`unit.mocks`), not a
    glob of `mocks/*.c`. The real dependency source is replaced by its mock, never linked
    alongside it. *Changed in Step 13 — see "Ceedling-parity mock linking" below.*
- `tests/test_compiler.py`

**Dependencies:** Steps 2, 4, 5, 6

---

### Step 8 — `runner.py`

**Goal:** Execute compiled binaries (native or via QEMU), parse Unity output.

**Deliverables:**
- `vyperling/runner.py`
  - `RunResult` dataclass
  - `run_binary(compile_result, toolchain, timeout_s) -> RunResult`
  - `run_all(compile_results, toolchain, timeout_s) -> list[RunResult]`
  - Unity line parser: `test/test_uart.c:42:test_name:PASS|FAIL: msg`

**Dependencies:** Steps 5, 7

---

### Step 9 — `reporter.py`

**Goal:** Rich terminal table output + JUnit XML writer.

**Deliverables:**
- `vyperling/reporter.py`
  - `print_terminal_report(run_results)`
  - `print_summary(run_results)`
  - `write_junit_xml(run_results, output_path)`
- `tests/test_reporter.py`

**Dependencies:** Steps 1, 8

---

### Step 10 — `mockgen.py`

**Goal:** Parse C headers with regex, emit `mock_*.h` + `mock_*.c`.

**Deliverables:**
- `vyperling/mockgen.py`
  - `FunctionDecl` dataclass (`name`, `return_type`, `params`)
  - `parse_header(header_path) -> list[FunctionDecl]`
  - `generate_mock(header_path, mock_dir) -> tuple[Path, Path]`
  - `generate_all(headers, mock_dir)`
- Generated mock API: call counters, return injectors, `EXPECT_*` macros, `forge_mocks_reset()`
- `tests/test_mockgen.py`

**Limitations (v0.1):** no variadic, no function pointer params, no transitive includes

**Dependencies:** Steps 1, 3

---

### Step 11 — `coverage.py`

**Goal:** gcov HTML coverage report via `gcovr` (native target only).

**Deliverables:**
- `vyperling/coverage.py`
  - `check_coverage_tools()` — verify `gcovr` + `gcov` present
  - `generate_coverage(config, build_dir, output_dir) -> Path`
  - Runs a single `gcovr` pass: `--html-details` (HTML report) + `--cobertura`
    (XML for Step 17 CI), excluding Unity/forge_mock/mocks/system paths
- `gcovr>=7.0,<9.0` added to runtime deps (pure-Python, pip-installable — no
  lcov/genhtml system tools; `gcov` ships with gcc)

**Dependencies:** Steps 1, 4

---

### Step 12 — `scaffold.py`

**Goal:** `vyperling new <name>` creates a working project skeleton.

**Deliverables:**
- `vyperling/scaffold.py`
  - `create_project(name, base_dir)`
  - Emits: `forge.yml`, `src/example.c`, `test/test_example.c`, `mocks/.gitkeep`, `README.md`
  - Generated `test_example.c` passes on first `vyperling test`

**Dependencies:** Steps 1, 4

---

### Step 13 — `cli.py`

**Goal:** All CLI commands wired up and functional end-to-end.

**Deliverables:**
- `vyperling/cli.py` — final implementation
  - `vyperling new <name>` → `scaffold.create_project`
  - `vyperling test [options]` → discover → auto-mock → compile → run → report
  - `vyperling build [options]` → discover → auto-mock → compile (no run)
  - `vyperling mock [headers] [--all]`
  - `vyperling clean [--target]` → `shutil.rmtree` build dir (all targets or one)
  - `vyperling targets` → built-in + project-defined profiles (works without forge.yml)
- Flags: `--target`, `-v`, `-j`, `--coverage`, `--output junit`, `-k`, `--no-mock`
- `--target` defaults to `config.targets.default` (sentinel `None` → resolved post-load),
  not a hardcoded `"native"`.
- Fine-grained exit codes via `ctx.exit`: `0` pass · `1` test fail/compile fail · `2`
  `ForgeConfigError` · `3` `ForgeToolchainError`. Other `ForgeError` → `ClickException` (1).
- Coverage is native-only + best-effort: cross target warns and skips instrumentation;
  `ForgeCoverageError` is caught as a warning, never changes exit code.

**Auto-mock (Ceedling parity):** `test`/`build` resolve the mocks each test needs from its
`#include "mock_<dep>.h"` lines (via `TestUnit.mocks`), find the matching `<dep>.h` in
`src_dirs`, and generate only those — never the unit-under-test's own header. The compiler
links only those per-test mocks. This avoids the duplicate-symbol link error that
glob-linking every `mocks/*.c` produced (`mock_<mod>.c` + real `<mod>.c` in one binary).
`mock --all` keeps the explicit "mock every src header" behavior. Required matching changes
in Step 6 (`discoverer.py` parse) and Step 7 (`compiler.py` per-include link).

**Also added in this step:** `ForgeScaffoldError(ForgeError)` in `errors.py`.

**Dependencies:** Steps 4, 5, 6, 7, 8, 9, 10, 11, 12

---

### Step 14 — Python test suite

**Goal:** Full unit test coverage across all modules.

**Deliverables:**
- One `tests/test_<module>.py` per module (config, discoverer, mockgen, compiler, reporter,
  runner, coverage, toolchains, unity, errors, scaffold, cli).
- `tests/conftest.py` — shared factory fixtures (`mock_proc`, `make_config`,
  `make_unit_path`, `make_unit_fs`, `make_tc`, `make_rr`). *Used by the Step 14 gap-fill
  tests; existing modules keep their local helpers (no migration — deferred to its own PR).*
- gcc-dependent e2e tests gated via `pytest.mark.skipif(shutil.which("gcc") is None, ...)`.
- Coverage gate: `fail_under = 85` in `[tool.coverage.report]` ([pyproject.toml](pyproject.toml)).
- `pytest` passes with no failures.

**Result:** 387 tests pass. Coverage **99%** with gcc available (cli/unity/reporter/discoverer
at 100%), **90%** on a gcc-less lane (e2e tests skip) — both clear the 85 gate. Two branches
left uncovered by design: `mockgen.py:188,192` (defensive AST-shape guards) and
`cli.py 31->30, 186->191` (loop-continue / empty-headers fast paths) — accepted as
not-worth-testing defensive code.

**Dependencies:** Steps 3–12

---

### Step 15 — End-to-end smoke test (native)

**Goal:** `vyperling new demo && cd demo && vyperling test` passes on host machine.

**Checklist:**
- [x] Scaffold creates all expected files (forge.yml, src/example.{c,h}, test/test_example.c, mocks/.gitkeep, README.md)
- [x] `vyperling test` compiles `test_example.c` with native gcc
- [x] Unity reports `1 passed` / `PASS`
- [x] Exit code 0

**Result:** Added `tests/test_e2e_native.py` — 3 out-of-process smoke tests invoking the REAL
installed `vpl`/`vyperling` console script via `subprocess.run` (explicit cwd + 120s timeout):
1. `new` → `test` happy path (rc 0, `1 passed` + Unity `PASS`) — validates wheel packaging,
   bundled C assets/templates, and `importlib.resources` resolution as an installed tool.
2. `vyperling targets` — proves the long-name entrypoint twin is registered (both
   `[project.scripts]` map to `vyperling.cli:cli`).
3. `vpl test --output junit` writes `build/native/results.xml` — installed-tool artifact contract.
Module self-skips (no hard fail) when the console script is absent (no `pip install -e .`) or gcc
is missing. Child-process execution contributes no coverage; the 85 gate is unaffected (390
tests, 99.43%). Step 16 (e2e-mips32, deps 13+15) is now unblocked.

**Dependencies:** Steps 13, 14

---

### Step 16 — End-to-end smoke test (mips32)

**Goal:** `vyperling test --target mips32` compiles + runs via `qemu-mips`.

**Checklist:**
- [x] Requires `gcc-mips-linux-gnu` (mips32 BE) / `mipsel-linux-gnu-gcc` (mips32el) + `qemu-user`; each target self-skips if its (gcc, qemu) pair is absent
- [x] Binary links `-static` (qemu-user needs no guest sysroot/loader)
- [x] `qemu-<arch>` executes the binary; Unity output captured + parsed identically to native
- [x] Exit code 0 on pass; non-zero exit propagates through qemu-user on failure
- [x] ELF magic + `e_machine == EM_MIPS` + endianness check proves a real cross build (not native fallback)

**Result:** Added `tests/test_e2e_cross.py` — out-of-process cross-compile smoke tests invoking
the REAL installed `vpl` console script via `subprocess.run` (explicit cwd + 120s timeout, zero
vyperling imports). Parametrized over `mips32` (BE, `mips-linux-gnu-gcc` + `qemu-mips`) and
`mips32el` (LE, `mipsel-linux-gnu-gcc` + `qemu-mipsel`); each case self-skips (no hard fail)
unless BOTH its cross-gcc and its qemu-user emulator are installed. Each happy-path test
scaffolds a project, runs `vpl test --target <t>`, asserts rc 0 + `1 passed` + Unity `PASS`,
and reads `build/<target>/example` bytes to verify ELF magic, `e_machine==8` (EM_MIPS) and the
expected EI_DATA endianness — the signal that a real foreign-arch cross build ran (not a silent
native fallback). qemu-user is invoked by name (`qemu-mips <binary>`), not via binfmt_misc;
`-static` linking means no guest sysroot/loader; the guest's stdout and exit code propagate
back through qemu-user so Unity parsing and exit-code mapping are identical to native. A single
additional test flips the scaffold's assertion to fail and asserts a non-zero exit propagates
THROUGH qemu-user (a cross-specific risk not covered by native e2e). With both cross toolchains
installed, all 3 cases run green on this host (mips32 EI_DATA=2, mips32el EI_DATA=1). Child-process
execution adds no coverage; the 85 gate is unaffected (393 tests, 99.43%). No production code,
toolchain shared-instance bug fix, CI yaml, or plan doc was touched. Step 17 (CI, deps 15+16) is
now unblocked.

**Dependencies:** Steps 13, 15

---

### Step 17 — CI pipeline (GitHub Actions)

**Goal:** Automated test on push/PR for native and mips32 targets.

**Deliverables:**
- `.github/workflows/ci.yml`
  - `test-native` job
  - `test-mips32` job (installs `gcc-mips-linux-gnu qemu-user`)
  - JUnit XML upload via `upload-artifact`

**Dependencies:** Steps 15, 16

---

## Dependency graph

```
1 (scaffold)
└── 2 (unity)
└── 3 (errors)
    └── 4 (config)
        └── 5 (toolchains)
        └── 6 (discoverer)
            └── 7 (compiler) ← also needs 2, 5
                └── 8 (runner) ← also needs 5
                    └── 9 (reporter)
    └── 10 (mockgen) ← also needs 3
    └── 11 (coverage)
    └── 12 (scaffold-cmd)
        └── 13 (cli) ← all of 4–12
            └── 14 (tests)
                └── 15 (e2e-native)
                    └── 16 (e2e-mips32)
                        └── 17 (ci)
```

---

## Known issues / latent bugs

| Severity | Location | Issue | Found | Fix |
|----------|----------|-------|-------|-----|
| Medium | `toolchains.py:137` — `get_toolchain()` | Returns the SHARED `BUILTIN_TOOLCHAINS[name]` instance instead of a copy. Any caller mutating a field (e.g. `tc.cc = ...`) poisons the singleton process-wide, corrupting every later `get_toolchain` call for that target. Surfaced during Step 10: a test that set `.cc` on the returned object broke an unrelated `test_toolchains` assertion. | Step 10 | Return `dataclasses.replace(BUILTIN_TOOLCHAINS[name])` (or `copy.deepcopy`) so each call yields an independent instance. Until fixed, callers must use `dataclasses.replace` to derive variants — never mutate in place. |
| ~~High~~ **FIXED** | `compiler.py:74-86` — `compile_unit()` | Glob-linked every `mocks/*.c` into every test binary. When a `mock_<mod>.c` existed for a module that also had a real `<mod>.c` source, the same symbols were defined twice → `multiple definition` link error. Surfaced during Step 13 e2e: the scaffolded `example` failed to link once its header was auto-mocked. | Step 13 | Fixed in Step 13. `discover` now records each test's `#include "mock_<dep>.h"` set as `TestUnit.mocks`; `compile_unit` links only `mock_<dep>.c` for `dep in unit.mocks`. Mock and real of the same module never co-occur in one link (Ceedling per-include model). |
| ~~Medium~~ **FIXED rc.1** | `mockgen.py` — `_extract_functions()` | Mocked functions from transitive `#include`s (e.g. `osal.h` pulled in by `uart.h`) — caused duplicate-symbol link errors when real project headers were parsed. | rc.1 | `_extract_functions` now filters by `coord.file` resolved against the target header path; only functions declared in the requested header are mocked. |
| ~~Medium~~ **FIXED rc.1** | `runner.py` — `run_binary()` | Compile stderr not surfaced when binary was `None` — compile errors invisible in the run report. | rc.1 | `RunResult.stderr` now set to `compile_result.output` when binary is absent. |
| ~~High~~ **FIXED rc.1** | `compiler.py` + `runnergen.py` | No Unity runner generated — test binaries had no `main()` and failed to link in real projects. `runnergen.py` did not exist. | rc.1 | New `runnergen.py` module generates `<unit>_runner.c` (main + RUN_TEST list + CMock lifecycle). `compile_unit` calls it and links the result. |
| Low | `runnergen.py` — `_has_symbol()` | Word-boundary regex matches commented-out symbols (e.g. `/* setUp */`). A commented-out `setUp` would suppress the generated default stub. | rc.1 | Strip C comments before symbol search, or use a stricter definition-only regex. |
| ~~Medium~~ **FIXED v0.0.2** | `mockgen.py` — `_is_opaque_struct_param()` | Anonymous typedef struct (`typedef struct { ... } Size;`) wrongly skipped: it resolves to `Struct(name=None)`, and the old code did `struct_defs.get(None)` → False → flagged opaque, even though `decls` was present (complete). | v0.0.2 (found building `examples/mock_features`) | Check the resolved struct's own `decls` before the tag-name lookup — a non-None member list means complete regardless of tag name. |
| ~~Medium~~ **FIXED v0.0.2** | `mockgen.py` — `_build_param()` | `_ReturnThruPtr_*` was emitted for a pointer to an incomplete struct (`struct Opaque *o`), generating a `struct Opaque o_thru;` field of incomplete type → compile error. | v0.0.2 (found building `examples/mock_features`) | New `_pointee_is_incomplete_struct` guard excludes pointer-to-incomplete from `return_thru`, same as the existing `void *` exclusion. |

---

## Current limitations

These are known limitations in the implemented code (steps 1–10). Each entry explains
what the constraint is, why it exists, how severe it is, and the concrete path to fix it.

---

### mockgen.py

~~**Variadic and function-pointer params — functions skipped entirely**~~
**FIXED in v0.0.2** — `_extract_functions` no longer skips these:

- **Variadic functions** (`int log_printf(const char *fmt, ...)`): mocked. The fixed
  prefix params are captured and asserted; the mock's signature keeps the trailing `...`
  but the variadic tail is ignored (a `va_list` can't be inspected after the call), so
  only the fixed params get `_Expect`/`_ExpectAndReturn`. `FunctionDecl.is_variadic` carries
  the flag; `_decl_params` appends `...`.
- **Function-pointer params** (`void register_cb(void (*cb)(int))`): mocked. `_build_param`
  detects the `PtrDecl`→`FuncDecl` shape, renders the typed declarator via
  `gen.visit(param)` (name embedded), stores the pointer as `void *` in the CALL_INSTANCE,
  and asserts identity with `UNITY_TEST_ASSERT_EQUAL_PTR`. `Param.is_fnptr` carries the flag.

A runnable demo lives in `examples/mock_features` (TestVariadic / TestFnptr / TestApp).

**Incomplete (opaque) struct-by-value params — still skipped (by design)**
`void use_opaque(struct Opaque o)` where `struct Opaque` is forward-declared only has an
unknown `sizeof`, so it cannot be stored or byte-compared. `_collect_struct_info` +
`_is_opaque_struct_param` detect this (including typedef chains and anonymous typedef
structs) and skip just that function with a warning. Complete structs (inline definition or
typedef to a complete one) ARE mocked via `UNITY_TEST_ASSERT_EQUAL_MEMORY`. A pointer to an
opaque struct is fine — it is mocked, and is correctly excluded from `_ReturnThruPtr_*`
(the `_thru` copy field would need the unknown pointee size).

~~**Unknown scalar types silently compare as INT**~~
~~`_treat_as` returns `"INT"` and emits a `UserWarning` for any typedef not in `TREAT_AS`.
A user-defined type like `bool_t` or `error_code_t` will be compared with
`UNITY_TEST_ASSERT_EQUAL_INT`, which is 32-bit. If the real width is 8 or 64 bits, the
assertion may pass silently when it should fail (truncation). Fix: expose a `treat_as`
map in `forge.yml` (`mockgen.treat_as: {bool_t: UINT8, error_code_t: INT32}`) and merge
it into `TREAT_AS` at startup.~~
**FIXED in rc.1** — `_treat_as` now returns `"MEMORY"` for unknown types, using
`UNITY_TEST_ASSERT_EQUAL_MEMORY` (byte-comparison). Struct-by-value params work correctly.
A `treat_as` forge.yml override for named types is still a future improvement.

**`ReturnThruPtr_<param>` copies a single element only**
The generated `_CALL_INSTANCE` struct stores `pointee_type param_thru` (one value, not an
array), and the mock body copies `sizeof(param_thru)` bytes. Passing a pointer to an array
of N elements will silently copy only the first. Fix: add a `_ReturnArrayThruPtr_<param>`
variant (matching CMock's API) that takes `(T *val, size_t len)` and stores both the
pointer and the length in the instance struct, then uses `memcpy(ptr, val, len*sizeof(T))`.

**Pointer args compared by identity, not by content**
Non-`char*` pointer params generate `UNITY_TEST_ASSERT_EQUAL_PTR`, which checks the
*address*, not the pointed-to data. Passing two pointers to equal but distinct structs
will fail even though the values match. Fix: add an `ExpectWithArray` family (CMock's
`:plugins: [:array]`) that takes an extra `_Depth` parameter and deep-compares through
the pointer using `UNITY_TEST_ASSERT_EQUAL_MEMORY_ARRAY`.

---

### compiler.py

**Regenerating mock headers does not trigger recompile**
Dep tracking stores mtimes of `.c` source files. When `vyperling mock` regenerates
`mock_uart.h`, the mtime of `mock_uart.c` may not change if its content stays identical.
The binary is then served from cache with stale header content. Fix: include all `.h`
files transitively reachable from each source in the dep snapshot — or, simpler, include
the `mock_<mod>.h` alongside each `mock_<mod>.c` in the mtime set.

---

### runner.py

**Sequential test execution**
`run_all` is a plain list comprehension over `compile_results`. All binaries run one at a
time. On a large suite each binary's timeout blocks the next. Fix: mirror `compile_all`'s
`ThreadPoolExecutor` approach — run binaries in parallel, each with its own timeout, and
collect results in input order. Output ordering is already handled by the result list.

**Colon in test name breaks Unity line parsing**
The regex `_UNITY_LINE` splits on `:` positionally. A test named `test_state:idle` would
consume `idle` into the result field, breaking the match. Unity itself disallows colons in
test names, but generated or external test runners might emit them. Fix: anchor the result
field more tightly — `PASS|FAIL|IGNORE` are the only valid result strings, so a
`PASS|FAIL|IGNORE` literal match after the name field is safe and unambiguous.

---

### discoverer.py

**First source-dir match wins without ambiguity warning**
`discover` iterates `src_dirs` and breaks on the first `name.c` hit. If `src/uart.c` and
`lib/uart.c` both exist, only `src/uart.c` is ever picked — silently. Fix: collect *all*
matches first, then warn and pick the first if there are multiple, giving the user
visibility.

---

### toolchains.py

**`get_toolchain()` returns the shared `BUILTIN_TOOLCHAINS` instance** *(also in Known Issues)*
Any caller that mutates a field on the returned `Toolchain` (e.g. setting `.cc` for a
test) poisons every subsequent call for that target in the same process. Already
documented in the Known Issues table. Fix: `return dataclasses.replace(BUILTIN_TOOLCHAINS[name])`.

---

### forge_mock.c (C runtime)

**Expectation args stored by shallow copy — pointer arguments not deep-copied**
`forge_mock_queue_push` allocates a `_CALL_INSTANCE` struct and the caller writes the
expected argument values into it. For pointer params the struct stores the *pointer value*,
not a copy of the pointed-to data. If the caller modifies the pointed-to memory between
`Expect()` and the actual mock call, the comparison sees the modified value, not the
original expectation. This is subtle and silent. Fix: for pointer params where the type is
known (generated code), emit a `memcpy` of the pointed-to data into a fixed-size
arena-allocated buffer inside the instance struct, alongside the pointer. This is what
CMock does for the `ExpectWithArray` family.

**Fixed 32 KB arena — no runtime override**
The arena is a `static unsigned char [FORGE_MOCK_MEM_SIZE]` compiled into the test binary.
The only way to raise the limit is a compile-time `-DFORGE_MOCK_MEM_SIZE=N` flag. There is
no forge.yml knob, no per-test resize, and overflow causes an immediate Unity failure mid-
test with no recovery. Fix: expose `compiler.mock_arena_size` in `forge.yml`, default
`32768`, and emit `-DFORGE_MOCK_MEM_SIZE=<value>` into the cflags list in `compile_unit`.

---

### reporter.py

**Per-test timing is fake (averaged)**
Unity emits no per-test timestamps. Both `print_terminal_report` and `write_junit_xml`
divide the whole-binary duration equally across tests. The numbers are informative for
human readers but misleading in CI timing dashboards. Fix: Unity v2.6+ supports
`UNITY_INCLUDE_EXEC_TIME` which instruments each `RUN_TEST` call; vyperling could
enable that define and parse the extended output format `file:line:name:PASS (Xms)`.

---

### Summary by severity

| Severity | Module | Issue |
|----------|--------|-------|
| **Breaks correctness** | `forge_mock.c` | Pointer args not deep-copied in Expect records |
| **Breaks correctness** | `toolchains.py` | `get_toolchain` returns shared mutable instance |
| ~~**Breaks feature**~~ **FIXED v0.0.2** | `mockgen.py` | ~~Variadic functions produce no mock~~ Variadic + fnptr params now mocked; only opaque struct-by-value skipped |
| ~~**Degrades silently**~~ **FIXED rc.1** | `mockgen.py` | ~~Unknown types compared as INT (may pass when it should fail)~~ Now uses MEMORY (byte-compare) |
| **Degrades silently** | `mockgen.py` | `ReturnThruPtr` copies only first element |
| **Degrades silently** | `compiler.py` | Stale binary after mock header regeneration |
| **Degrades silently** | `discoverer.py` | Ambiguous source match with no warning |
| **Performance** | `runner.py` | Sequential binary execution |
| **Edge case** | `runner.py` | Colon in test name breaks line parser |
| **Capacity** | `forge_mock.c` | Hard arena limit, no forge.yml override |
| **Cosmetic** | `reporter.py` | Averaged per-test timing |
| **Edge case** | `runnergen.py` | `_has_symbol` matches commented-out symbols |

