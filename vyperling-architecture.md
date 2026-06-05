# vyperling — Architecture Document

> Embedded C test runner with cross-compilation support.  
> A pip-installable Ceedling alternative focused on MIPS32, ARM, RISC-V, and AVR targets.

---

## Table of contents

1. [Project overview](#1-project-overview)
2. [Design goals](#2-design-goals)
3. [Package structure](#3-package-structure)
4. [CLI contract](#4-cli-contract)
5. [forge.yml schema](#5-forgeyml-schema)
6. [Core modules](#6-core-modules)
   - 6.1 [cli.py](#61-clipy)
   - 6.2 [config.py](#62-configpy)
   - 6.3 [toolchains.py](#63-toolchainspy)
   - 6.4 [discoverer.py](#64-discovererpy)
   - 6.5 [compiler.py](#65-compilerpy)
   - 6.6 [runner.py](#66-runnerpy)
   - 6.7 [mockgen.py](#67-mockgenpy)
   - 6.8 [coverage.py](#68-coveragepy)
   - 6.9 [reporter.py](#69-reporterpy)
   - 6.10 [scaffold.py](#610-scaffoldpy)
7. [Vendored C assets](#7-vendored-c-assets)
8. [Built-in toolchain profiles](#8-built-in-toolchain-profiles)
9. [Execution pipeline](#9-execution-pipeline)
10. [Mock generation spec](#10-mock-generation-spec)
11. [Coverage pipeline](#11-coverage-pipeline)
12. [Ceedling compatibility](#12-ceedling-compatibility)
13. [Project layout convention](#13-project-layout-convention)
14. [pyproject.toml spec](#14-pyprojecttoml-spec)
15. [Error handling strategy](#15-error-handling-strategy)
16. [CI integration](#16-ci-integration)
17. [Future roadmap](#17-future-roadmap)

---

## 1. Project overview

**vyperling** is a command-line tool installable via pip that orchestrates the full lifecycle of C unit testing for embedded systems:

- Discovers test files by convention (`test_*.c`)
- Compiles them against the source under test using any configured cross-compiler
- Runs the resulting binaries natively or through QEMU user-mode emulation
- Generates mocks from C headers (like CMock)
- Reports results in the terminal and as JUnit XML + gcov HTML (via gcovr)

It is designed to be a drop-in workflow replacement for Ceedling without requiring Ruby. Tests written for Ceedling/Unity work unchanged.

---

## 2. Design goals

| Goal | Description |
|---|---|
| **pip-installable** | `pip install vyperling` — no Ruby, no gem, no system package beyond gcc and qemu-user |
| **Ceedling compatible** | Unity assertion macros (`TEST_ASSERT_EQUAL`, `RUN_TEST`, etc.) work unchanged |
| **Cross-compilation first** | `--target mips32` is a first-class flag, not an afterthought |
| **QEMU transparent** | Test binaries run through `qemu-mips`, `qemu-arm`, etc. automatically — no manual wrapping |
| **Zero magic** | Every compilation command is printed when `-v` is passed; nothing is hidden |
| **Extensible toolchains** | Custom targets defined in `forge.yml` without touching vyperling source |
| **Fast** | Parallel compilation with `-j N`; only recompiles changed files |
| **CI ready** | JUnit XML output, meaningful exit codes, no interactive prompts |

---

## 3. Package structure

```
vyperling/
├── vyperling/
│   ├── __init__.py
│   ├── cli.py              # click entry point, command registration
│   ├── config.py           # forge.yml loader, deep merge with defaults
│   ├── toolchains.py       # built-in toolchain profiles + custom resolver
│   ├── discoverer.py       # test_*.c discovery, source file matching
│   ├── compiler.py         # subprocess gcc invocation, parallel jobs, dep tracking
│   ├── runner.py           # native exec or qemu-* with timeout, stdout capture
│   ├── mockgen.py          # C header parser → mock_*.c + mock_*.h generator
│   ├── coverage.py         # gcovr invocation, HTML + Cobertura XML report
│   ├── reporter.py         # rich terminal table, JUnit XML writer
│   └── scaffold.py         # `vyperling new` project template generator
│
├── vyperling/c/
│   ├── unity.h             # vendored Unity (ThrowTheSwitch, MIT license)
│   ├── unity.c             # vendored Unity source
│   ├── unity_internals.h   # vendored Unity internals
│   └── unity_fixture.h     # fixture support (setUp/tearDown)
│
├── tests/                  # vyperling's own Python test suite
│   ├── test_config.py
│   ├── test_discoverer.py
│   ├── test_mockgen.py
│   ├── test_compiler.py
│   └── test_reporter.py
│
├── pyproject.toml
├── README.md
└── ARCHITECTURE.md         # this document
```

---

## 4. CLI contract

All commands follow the pattern `vyperling <command> [options]`.

### `vyperling new <name>`

Scaffolds a new project directory.

```
vyperling new myproject
```

Creates:
```
myproject/
├── forge.yml
├── src/
│   └── example.c
├── test/
│   └── test_example.c
└── mocks/
```

### `vyperling test`

Full pipeline: discover → mock (if needed) → compile → run → report.

```
vyperling test                            # native target
vyperling test --target mips32            # cross-compile + qemu-mips
vyperling test --target arm-cortex-m4     # cross-compile + qemu-arm
vyperling test -k uart                    # filter: only files matching "uart"
vyperling test -j 4                       # parallel compile jobs
vyperling test --coverage                 # enable gcov (native only)
vyperling test --output junit             # also write build/results.xml
vyperling test -v                         # verbose: print every gcc command
vyperling test --no-mock                  # skip auto mock generation
```

### `vyperling build`

Compile only, do not run tests.

```
vyperling build
vyperling build --target mips32
```

### `vyperling mock`

Generate mock stubs from a header file.

```
vyperling mock src/uart.h                 # → mocks/mock_uart.h + mocks/mock_uart.c
vyperling mock src/uart.h src/spi.h       # multiple headers at once
vyperling mock --all                      # mock every header in src/
```

### `vyperling clean`

Remove the build directory.

```
vyperling clean
vyperling clean --target mips32           # clean only that target's build dir
```

### `vyperling targets`

List all available toolchain profiles.

```
vyperling targets
```

Output example:
```
Built-in targets:
  native          Host machine (no cross compilation)
  mips32          MIPS32 big-endian — mips-linux-gnu-gcc + qemu-mips
  mips32el        MIPS32 little-endian — mipsel-linux-gnu-gcc + qemu-mipsel
  mips32r5        MIPS32r5 PIC32MK — mips-linux-gnu-gcc + qemu-mips -cpu P5600
  arm-cortex-m4   ARM Cortex-M4 — arm-none-eabi-gcc + qemu-arm
  arm-cortex-m0   ARM Cortex-M0 — arm-none-eabi-gcc + qemu-arm
  riscv32         RISC-V 32-bit — riscv32-unknown-elf-gcc + qemu-riscv32
  avr             AVR — avr-gcc + simavr

Project-defined targets:
  (none)
```

---

## 5. forge.yml schema

```yaml
project:
  name: myproject
  src_dirs:
    - src             # one or more source directories
  test_dir: test      # directory containing test_*.c files
  include_dirs:
    - src             # passed as -I flags to compiler
  build_dir: build    # root build output dir; per-target subdirs created inside
  mock_dir: mocks     # where generated mocks are written and read from

targets:
  default: native     # used when --target is not specified

compiler:
  extra_cflags: []    # appended to every compile command
  defines: []         # passed as -D flags (without -D prefix)

# Optional: define custom toolchain profiles
toolchains:
  pic32mk:
    description: "PIC32MK production flags"
    cc: mips-linux-gnu-gcc
    ar: mips-linux-gnu-ar
    cflags:
      - -march=mips32r5
      - -mhard-float
      - -EL
      - -Wall
      - -Wextra
      - -g
    emulator: qemu-mips
    emulator_args:
      - -cpu
      - P5600
    sysroot: /usr/mips-linux-gnu
    static: true
```

All keys under `project` have defaults; a minimal `forge.yml` only needs `project.name`.

---

## 6. Core modules

### 6.1 `cli.py`

Entry point. Registers all commands with Click. Handles global options (`--target`, `-v`, `-j`).

Responsibilities:
- Parse global flags and pass them as a context object to subcommands
- Load `forge.yml` via `config.py` before dispatching any command
- Print a human-readable error and exit 1 on any `ForgeError`

### 6.2 `config.py`

Loads and validates `forge.yml`.

Responsibilities:
- Walk up from `cwd` to find `forge.yml` (same behaviour as Ceedling)
- Deep-merge user config with `DEFAULT_CONFIG`
- Expose typed helper functions: `get_build_dir(config, target)`, `get_src_dirs(config)`, `get_include_dirs(config)`
- Raise `ForgeConfigError` with a descriptive message on missing required fields

Key function signatures:
```python
def find_config(start: Path | None = None) -> Path
def load_config(config_path: Path | None = None) -> dict
def get_build_dir(config: dict, target: str) -> Path
def get_test_dir(config: dict) -> Path
def get_src_dirs(config: dict) -> list[Path]
def get_include_dirs(config: dict) -> list[Path]
```

### 6.3 `toolchains.py`

Defines the `Toolchain` dataclass and the registry of built-in profiles.

```python
@dataclass
class Toolchain:
    name: str
    description: str
    cc: str                           # compiler binary, e.g. mips-linux-gnu-gcc
    ar: str                           # archiver binary
    cflags: list[str]                 # base compiler flags
    emulator: str | None              # qemu binary or None for native
    emulator_args: list[str]          # extra args passed to emulator
    sysroot: str | None               # used as -L for dynamic qemu runs
    static: bool                      # link with -static
```

`get_toolchain(name, config)` resolves in this order:
1. User-defined toolchains in `forge.yml` under `toolchains:`
2. Built-in profiles in `BUILTIN_TOOLCHAINS`
3. Raises `ForgeToolchainError` with available options listed

### 6.4 `discoverer.py`

Finds all test files and resolves their corresponding source files.

**Convention:** `test/test_uart.c` tests `src/uart.c`. The discoverer strips the `test_` prefix and searches `src_dirs` for a matching `.c` file.

```python
@dataclass
class TestUnit:
    test_file: Path          # test/test_uart.c
    source_file: Path | None # src/uart.c (None if no match found)
    name: str                # "uart"
```

```python
def discover(config: dict, filter_pattern: str | None = None) -> list[TestUnit]
```

- Globs `test_dir` for `test_*.c`
- Applies `filter_pattern` as a substring match on `TestUnit.name` if provided
- Warns (does not fail) when no matching source file is found — allows header-only or mock-only tests

### 6.5 `compiler.py`

Compiles each `TestUnit` into an executable using the resolved `Toolchain`.

Each test binary is compiled from:
- The test `.c` file
- The matching source `.c` file (if found)
- All `.c` files in `mock_dir`
- `unity.c` (vendored)
- Any `.c` files in `extra_sources` from `forge.yml`

```python
@dataclass
class CompileResult:
    unit: TestUnit
    binary: Path | None      # None if compilation failed
    success: bool
    output: str              # combined stdout+stderr from compiler
    duration_ms: int

def compile_all(
    units: list[TestUnit],
    toolchain: Toolchain,
    config: dict,
    jobs: int = 1,
    verbose: bool = False,
) -> list[CompileResult]
```

**Parallel compilation:** uses `concurrent.futures.ThreadPoolExecutor` with `jobs` workers. Each `TestUnit` is an independent compilation — no linking step between units.

**Dependency tracking:** stores a `.forge_deps` JSON file in the build dir mapping source files to their last-modified timestamps. Skips recompilation if all inputs are unchanged.

**Coverage flags:** when `--coverage` is active and target is `native`, appends `--coverage -fprofile-arcs -ftest-coverage` to `cflags`.

### 6.6 `runner.py`

Executes compiled test binaries and captures their output.

```python
@dataclass
class RunResult:
    unit: TestUnit
    binary: Path
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool

def run_all(
    compile_results: list[CompileResult],
    toolchain: Toolchain,
    timeout_s: int = 30,
) -> list[RunResult]
```

**Execution logic:**
- If `toolchain.emulator` is `None`: run binary directly
- Otherwise: `[toolchain.emulator] + toolchain.emulator_args + [str(binary)]`
- For dynamic builds with a sysroot: prepend `-L sysroot` to emulator args
- Captures stdout and stderr separately
- A non-zero exit code is a test failure; a timeout is reported separately

**Unity output parsing:** Unity prints one line per test in the format:
```
test/test_uart.c:42:test_uart_init_sets_baud:PASS
test/test_uart.c:58:test_uart_send_null:FAIL: Expected 0 but was 1
```
The runner parses this format to extract individual test case results from a single binary's output.

### 6.7 `mockgen.py`

Parses C headers and generates mock implementations.

**Input:** a `.h` file  
**Output:** `mock_<name>.h` and `mock_<name>.c` written to `mock_dir`

**Generated mock `.h` provides:**
```c
// Call counter for each function
extern int mock_uart_send_call_count;

// Return value injector
extern int mock_uart_send_return_val;
#define UART_SEND_RETURNS(v) mock_uart_send_return_val = (v)

// Argument capture (last call)
extern const char* mock_uart_send_last_data;

// Expectation macro
#define EXPECT_UART_SEND_CALLED(n) \
  do { if (mock_uart_send_call_count != (n)) { \
    forge_fail("Expected uart_send called %d time(s), got %d", (n), mock_uart_send_call_count); \
  }} while(0)

// Reset all mocks (call in setUp)
void forge_mocks_reset(void);
```

**Parser approach:**
- Strip comments (block and line)
- Match function declarations with a regex: return type, name, parameter list, trailing semicolon
- Skip: preprocessor directives, typedefs, structs, enums, `extern const` declarations
- Handle pointer return types and pointer parameters correctly
- Does not require a full C parser — regex is sufficient for well-formed headers

**Limitations (v0.1):**
- No variadic function support (`...`)
- No function pointer parameters
- Does not parse `#include`d transitive headers

### 6.8 `coverage.py`

Produces a gcov HTML coverage report (plus Cobertura XML for CI) via `gcovr`.

Only active when `--coverage` is passed and target is `native`. Warns and skips otherwise.

```python
def check_coverage_tools() -> None        # verify gcovr + gcov on PATH
def generate_coverage(
    config: dict,
    build_dir: Path,
    output_dir: Path,
) -> Path  # path to generated index.html
```

**Pipeline:** a single `gcovr` invocation wraps `gcov` internally — no separate
gcov pass. It searches `build_dir` for `.gcda`/`.gcno`, excludes vendored Unity,
`forge_mock.c`, the mocks dir, and system headers, then emits both an
`--html-details` report and a `--cobertura` XML to `<output_dir>/coverage/`.
Returns the path to `index.html`.

**Requirements:** `gcovr` (pip-installable — a vyperling runtime dependency) and
`gcov` (ships with gcc). No lcov/genhtml system tools. vyperling checks for both via
`check_coverage_tools()` and raises `ForgeCoverageError` with an install hint if
missing. Coverage is best-effort: failures are surfaced as a warning by the CLI
and do not change the test exit code.

### 6.9 `reporter.py`

Formats and outputs test results.

```python
def print_terminal_report(run_results: list[RunResult]) -> None
def write_junit_xml(run_results: list[RunResult], output_path: Path) -> None
def print_summary(run_results: list[RunResult]) -> None
```

**Terminal output** uses `rich` for colour and table formatting:
- Green `PASS` / Red `FAIL` / Yellow `TIMEOUT` per test case
- Per-binary timing
- Final summary line: `X passed, Y failed, Z timed out in N.Nms`

**JUnit XML** follows the standard schema compatible with Jenkins, GitLab CI, and GitHub Actions test reporters.

```xml
<testsuites>
  <testsuite name="uart" tests="3" failures="1" time="0.012">
    <testcase name="test_uart_init_sets_baud" time="0.004"/>
    <testcase name="test_uart_send_null" time="0.005">
      <failure message="Expected 0 but was 1">...</failure>
    </testcase>
  </testsuite>
</testsuites>
```

### 6.10 `scaffold.py`

Generates the initial project structure for `vyperling new <name>`.

Creates:
- `forge.yml` with sensible defaults and commented examples
- `src/example.c` with a simple function
- `test/test_example.c` with a Unity-style test that passes out of the box
- `mocks/` empty directory with a `.gitkeep`
- `README.md` with quick-start instructions

The generated `test_example.c` is intentionally simple — its purpose is to verify the toolchain works end-to-end on the first `vyperling test` run.

---

## 7. Vendored C assets

Unity is vendored inside the package under `vyperling/c/`. This means:

- No internet access required during `vyperling test`
- No version mismatch between vyperling and Unity
- Unity source is compiled as part of each test binary automatically

**Unity version:** ThrowTheSwitch Unity v2.5.4 (MIT license)  
**Files included:** `unity.h`, `unity.c`, `unity_internals.h`, `unity_fixture.h`

The path to the vendored `unity.c` is resolved at runtime using `importlib.resources` so it works whether vyperling is installed from pip, from a wheel, or run from source.

---

## 8. Built-in toolchain profiles

| Target name | Compiler | Emulator | Notes |
|---|---|---|---|
| `native` | `gcc` | none | Host arch, dynamic linking |
| `mips32` | `mips-linux-gnu-gcc` | `qemu-mips` | Big-endian, static |
| `mips32el` | `mipsel-linux-gnu-gcc` | `qemu-mipsel` | Little-endian, static |
| `mips32r5` | `mips-linux-gnu-gcc` | `qemu-mips -cpu P5600` | PIC32MK target |
| `arm-cortex-m4` | `arm-none-eabi-gcc` | `qemu-arm` | `-mcpu=cortex-m4 -mthumb` |
| `arm-cortex-m0` | `arm-none-eabi-gcc` | `qemu-arm` | `-mcpu=cortex-m0 -mthumb` |
| `riscv32` | `riscv32-unknown-elf-gcc` | `qemu-riscv32` | `-march=rv32imc` |
| `avr` | `avr-gcc` | `simavr` | `-mmcu` from forge.yml |

**Required system packages per target:**

```bash
# MIPS32 (Debian/Ubuntu)
sudo apt install gcc-mips-linux-gnu qemu-user

# MIPS32 little-endian
sudo apt install gcc-mipsel-linux-gnu qemu-user

# ARM bare-metal
sudo apt install gcc-arm-none-eabi qemu-user

# RISC-V
sudo apt install gcc-riscv64-unknown-elf qemu-user  # or riscv32 variant

# AVR
sudo apt install gcc-avr avr-libc simavr
```

vyperling checks for the required compiler binary at the start of `vyperling test` and prints a clear installation hint if it is missing.

---

## 9. Execution pipeline

The full pipeline for `vyperling test --target mips32`:

```
forge.yml
    │
    ▼
config.py          load + validate config
    │
    ▼
toolchains.py      resolve Toolchain(cc="mips-linux-gnu-gcc", emulator="qemu-mips", ...)
    │
    ▼
discoverer.py      → [TestUnit(test_file, source_file, name), ...]
    │
    ▼
mockgen.py         generate missing mocks for headers referenced in test files
    │
    ▼
compiler.py        for each TestUnit (parallel):
                     mips-linux-gnu-gcc -static -march=mips32r2 \
                       -I src -I mocks -I <unity_dir> \
                       test/test_uart.c src/uart.c mocks/mock_spi.c unity.c \
                       -o build/mips32/test_uart
    │
    ▼
runner.py          for each binary:
                     qemu-mips build/mips32/test_uart
                     capture stdout, exit code, timing
    │
    ▼
reporter.py        print rich table
                   write build/results.xml  (if --output junit)
                   open build/coverage/index.html  (if --coverage)
    │
    ▼
exit 0 (all pass) or exit 1 (any failure)
```

---

## 10. Mock generation spec

### Input header example

```c
// src/uart.h
#ifndef UART_H
#define UART_H

#include <stdint.h>

int  uart_init(uint32_t baud_rate);
int  uart_send(const char *data, uint16_t len);
void uart_flush(void);
int  uart_read_byte(void);

#endif
```

### Generated `mocks/mock_uart.h`

```c
/* Auto-generated by vyperling. DO NOT EDIT. */
#ifndef MOCK_UART_H
#define MOCK_UART_H

#include "uart.h"
#include <stdint.h>

/* Call counters */
extern int mock_uart_init_call_count;
extern int mock_uart_send_call_count;
extern int mock_uart_flush_call_count;
extern int mock_uart_read_byte_call_count;

/* Return value injectors */
extern int mock_uart_init_return_val;
#define UART_INIT_RETURNS(v)      mock_uart_init_return_val = (v)
extern int mock_uart_send_return_val;
#define UART_SEND_RETURNS(v)      mock_uart_send_return_val = (v)
extern int mock_uart_read_byte_return_val;
#define UART_READ_BYTE_RETURNS(v) mock_uart_read_byte_return_val = (v)

/* Expectation helpers */
#define EXPECT_UART_INIT_CALLED(n) \
  do { if (mock_uart_init_call_count != (n)) \
    forge_fail("uart_init: expected %d calls, got %d", (n), mock_uart_init_call_count); } while(0)
#define EXPECT_UART_SEND_CALLED(n) \
  do { if (mock_uart_send_call_count != (n)) \
    forge_fail("uart_send: expected %d calls, got %d", (n), mock_uart_send_call_count); } while(0)
#define EXPECT_UART_FLUSH_CALLED(n) \
  do { if (mock_uart_flush_call_count != (n)) \
    forge_fail("uart_flush: expected %d calls, got %d", (n), mock_uart_flush_call_count); } while(0)

/* Reset all mocks — call this in setUp() */
void forge_mocks_reset(void);
void forge_fail(const char *fmt, ...);

#endif
```

### Generated `mocks/mock_uart.c`

```c
/* Auto-generated by vyperling. DO NOT EDIT. */
#include "mock_uart.h"
#include <stdio.h>
#include <stdarg.h>
#include <stdlib.h>

void forge_fail(const char *fmt, ...) {
    va_list args;
    va_start(args, fmt);
    vfprintf(stderr, fmt, args);
    va_end(args);
    fprintf(stderr, "\n");
    exit(1);
}

int mock_uart_init_call_count     = 0;
int mock_uart_send_call_count     = 0;
int mock_uart_flush_call_count    = 0;
int mock_uart_read_byte_call_count = 0;

int mock_uart_init_return_val     = 0;
int mock_uart_send_return_val     = 0;
int mock_uart_read_byte_return_val = 0;

void forge_mocks_reset(void) {
    mock_uart_init_call_count      = 0;
    mock_uart_send_call_count      = 0;
    mock_uart_flush_call_count     = 0;
    mock_uart_read_byte_call_count = 0;
}

int uart_init(uint32_t baud_rate) {
    (void)baud_rate;
    mock_uart_init_call_count++;
    return mock_uart_init_return_val;
}

int uart_send(const char *data, uint16_t len) {
    (void)data; (void)len;
    mock_uart_send_call_count++;
    return mock_uart_send_return_val;
}

void uart_flush(void) {
    mock_uart_flush_call_count++;
}

int uart_read_byte(void) {
    mock_uart_read_byte_call_count++;
    return mock_uart_read_byte_return_val;
}
```

---

## 11. Coverage pipeline

Coverage is only supported on the `native` target. When `--coverage` is passed with a cross-compilation target, vyperling prints a warning and skips coverage generation.

**Full pipeline:**

```bash
# 1. Compile with coverage instrumentation (handled by compiler.py)
gcc --coverage -fprofile-arcs -ftest-coverage ...

# 2. Run tests (produces .gcda files alongside .gcno files)
./build/native/test_uart

# 3. Generate report — single gcovr pass (handled by coverage.py).
#    gcovr wraps gcov internally; exclude patterns are REGEXES (not lcov globs).
gcovr --root . \
      --gcov-ignore-parse-errors \
      --exclude '.*/unity\.c$' \
      --exclude '.*/forge_mock\.c$' \
      --exclude '.*/vyperling/c/.*' \
      --exclude 'mocks/.*' \
      --exclude '/usr/.*' \
      --html-details build/native/coverage/index.html \
      --cobertura     build/native/coverage/coverage.xml \
      --cobertura-pretty \
      --print-summary \
      build/native
```

The path to `build/native/coverage/index.html` is printed at the end of the run.
The Cobertura `coverage.xml` is consumed by the CI pipeline (Step 17) as an
artifact. `gcovr` is pip-installable (a vyperling runtime dependency) and `gcov`
ships with gcc, so no lcov/genhtml system packages are required.

---

## 12. Ceedling compatibility

Any test file written for Ceedling using Unity assertions works without modification.

| Ceedling/Unity feature | vyperling support |
|---|---|
| `TEST_ASSERT_EQUAL(expected, actual)` | ✅ via vendored Unity |
| `TEST_ASSERT_TRUE(condition)` | ✅ |
| `TEST_ASSERT_NULL(pointer)` | ✅ |
| `TEST_ASSERT_EQUAL_STRING(e, a)` | ✅ |
| `TEST_ASSERT_EQUAL_MEMORY(e, a, len)` | ✅ |
| `TEST_ASSERT_FLOAT_WITHIN(delta, e, a)` | ✅ |
| `RUN_TEST(func)` | ✅ |
| `setUp()` / `tearDown()` | ✅ |
| `TEST_FAIL_MESSAGE(msg)` | ✅ |
| `UnityBegin` / `UnityEnd` | ✅ |
| CMock auto-generated mocks | ✅ replaced by vyperling mockgen |
| CException | ❌ not supported in v0.1 |
| `project.yml` | ❌ replaced by `forge.yml` |

### Migration from Ceedling

1. Replace `project.yml` with `forge.yml` (schemas are different but both are YAML)
2. Run `vyperling mock --all` to regenerate mocks (output API is compatible)
3. Run `vyperling test` — existing test files work unchanged

---

## 13. Project layout convention

```
myproject/
├── forge.yml               # project configuration
├── src/
│   ├── uart.c              # source under test
│   ├── uart.h
│   ├── spi.c
│   └── spi.h
├── test/
│   ├── test_uart.c         # tests for uart.c
│   └── test_spi.c          # tests for spi.c
├── mocks/
│   ├── mock_uart.h         # auto-generated (do not edit)
│   ├── mock_uart.c
│   ├── mock_spi.h
│   └── mock_spi.c
└── build/
    ├── native/
    │   ├── test_uart
    │   ├── test_spi
    │   └── coverage/
    │       └── index.html
    └── mips32/
        ├── test_uart
        └── test_spi
```

**Naming convention:**

- Test files: `test_<module>.c`
- Mock files: `mock_<module>.h` / `mock_<module>.c`
- Source files: `<module>.c` / `<module>.h`

The discoverer links `test_uart.c` → `uart.c` by stripping the `test_` prefix. If no matching source file exists, the test still compiles — it just won't link against any production code (useful for integration-style tests).

---

## 14. pyproject.toml spec

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "vyperling"
version = "0.1.0"
description = "Embedded C test runner with cross-compilation support"
readme = "README.md"
license = { text = "MIT" }
requires-python = ">=3.11"
dependencies = [
    "click>=8.0",
    "rich>=13.0",
    "pyyaml>=6.0",
]

[project.scripts]
vyperling = "vyperling.cli:cli"

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-cov",
]

[tool.hatch.build.targets.wheel]
include = [
    "vyperling/**/*.py",
    "vyperling/c/*.h",
    "vyperling/c/*.c",
]
```

**Runtime dependencies are intentionally minimal:**
- `click` — CLI framework
- `rich` — terminal output formatting
- `pyyaml` — forge.yml parsing

No build system dependency (no CMake, no Make) — those are assumed to be on the host.

---

## 15. Error handling strategy

All internal errors raise a subclass of `ForgeError`. The CLI top-level catches these and prints a formatted message before exiting with code 1.

```python
class ForgeError(Exception):
    pass

class ForgeConfigError(ForgeError):
    pass      # forge.yml not found, invalid schema

class ForgeToolchainError(ForgeError):
    pass      # unknown target, missing compiler binary

class ForgeCompileError(ForgeError):
    pass      # gcc returned non-zero (printed inline, not raised)

class ForgeMockgenError(ForgeError):
    pass      # unparseable header
```

Compile errors are **not** raised as exceptions — they are captured in `CompileResult.success = False` and reported in the terminal table alongside test results. This allows all other tests to still run even if one fails to compile.

---

## 16. CI integration

### GitHub Actions example

```yaml
name: vyperling tests

on: [push, pull_request]

jobs:
  test-native:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install vyperling
      - run: vyperling test --output junit
      - uses: actions/upload-artifact@v4
        with:
          name: test-results
          path: build/results.xml

  test-mips32:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: sudo apt install -y gcc-mips-linux-gnu qemu-user
      - run: pip install vyperling
      - run: vyperling test --target mips32 --output junit
```

### Exit codes

| Code | Meaning |
|---|---|
| `0` | All tests passed |
| `1` | One or more tests failed or timed out |
| `2` | Configuration error (forge.yml missing or invalid) |
| `3` | Toolchain error (compiler not found) |

---

## 17. Future roadmap

### v0.0.1-rc.1: initial release candidate with core features:
- First test in real application code, fix any critical bug and changes needed to support it

### v0.0.2
- Add examples in repository root for users to clone and test with, FreeRTOS + STM32 example project, etc. (Note: the examples should test them with ceedling and vyperling to verify compatibility, migration reference, documentation and functionality validation)
- Refine coverage report generation: add a summary line with percentage, fail the run if coverage is below a threshold and print coverage details in the terminal
- Testing real application code and fix limitations

### v0.0.3
- Full C preprocessor awareness in mockgen (handle `#ifdef`-guarded declarations)
- CException support
- Plugin API for custom reporters and custom emulator adapters

### v0.0.4
- On-target execution via OpenOCD/pyOCD debug probe (for `--target on-device`)
- VS Code extension for inline pass/fail annotations

### v0.0.N
- `--watch` mode: rerun tests on file change using `watchdog`
- Argument capture in mocks (store last N calls, not just count)
- `vyperling report` command to re-display results from a previous run without recompiling
