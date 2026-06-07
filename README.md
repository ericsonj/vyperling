# vyperling

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI version](https://img.shields.io/badge/PyPI-0.0.1-brightgreen.svg)](https://pypi.org/)
[![Build Status](https://img.shields.io/badge/status-active-brightgreen.svg)](https://github.com/ericsonjoseph/vyperling)

**Embedded C unit test runner with cross-compilation support.**  
A pip-installable replacement for [Ceedling](https://github.com/ThrowTheSwitch/Ceedling) — no Ruby dependencies, modern Python-first design.

## Overview

`vyperling` (`vpl` for short) is a complete embedded C testing framework that:

- 🔍 **Auto-discovers** `test_*.c` files in your test directory
- 🎯 **Generates CMock-style mocks** from C headers using pycparser + Jinja2
- 🔨 **Cross-compiles** for native (GCC) and embedded targets (ARM, MIPS, RISC-V, AVR) with parallel jobs
- 🖥️ **Executes** natively or under emulation (QEMU, simavr)
- 📊 **Parses** Unity test output with rich terminal reporting
- 📈 **Generates coverage** reports (gcov) for native targets
- 📋 **Exports** JUnit XML for CI/CD integration

Perfect for firmware development, embedded systems testing, and hardware validation workflows.

## Demo

![vyperling demo](docs/demo.gif)

## Quick Start

### 1. Install

```bash
pip install vyperling
# Alias 'vpl' is registered automatically
vpl --version
```

Development (editable install from source):

```bash
git clone https://github.com/ericsonjoseph/vyperling.git
cd vyperling
pip install -e .
```

### 2. Create a Project

```bash
vpl new myproject
cd myproject
```

This scaffolds:
- `forge.yml` — project configuration
- `src/` — source files under test
- `test/` — test files (test_*.c pattern)
- `mocks/` — auto-generated mocks

### 3. Run Tests

```bash
# Test native target (default)
vpl test

# Cross-compile for MIPS32
vpl test --target mips32

# Run specific tests (pattern match)
vpl test -k uart

# Parallel compilation (4 jobs)
vpl test -j4

# Generate coverage report (native only)
vpl test --coverage

# Export JUnit XML for CI
vpl test --output junit
```

## Commands Reference

All commands use **`vyperling`** or **`vpl`** interchangeably.

### `vpl test` — Discover, Compile, Run, Report

```bash
vpl test [OPTIONS]

OPTIONS:
  --target TEXT           Toolchain target (default: targets.default from forge.yml)
  -k, --filter PATTERN    Run only tests matching PATTERN
  -j, --jobs N            Parallel compile jobs (default: 1)
  --coverage              Enable gcov coverage (native target only)
  --output FORMAT         Export results: junit
  -v, --verbose           Print every compiler command
  --no-mock               Skip automatic mock generation
```

**Example:** Test UART module with coverage on 4 parallel jobs:
```bash
vpl test -k uart -j4 --coverage
```

### `vpl mock` — Generate Mocks from Headers

Generate CMock-style mocks from C header files:

```bash
vpl mock src/uart.h src/spi.h

# Or mock all headers in configured source dirs
vpl mock --all

# Use a specific toolchain's preprocessor
vpl mock --target arm-cortex-m4 src/uart.h
```

Output: `mocks/mock_uart.{c,h}` and `mocks/mock_spi.{c,h}`

### `vpl build` — Compile Only (No Execution)

```bash
vpl build [OPTIONS]

OPTIONS:
  --target TEXT           Toolchain target
  -j, --jobs N            Parallel compile jobs
  -v, --verbose           Print compiler commands
  --no-mock               Skip mock generation
```

Useful for checking compilation without running tests:
```bash
vpl build --target arm-cortex-m4 --verbose
```

### `vpl targets` — List Available Toolchains

```bash
vpl targets
```

Shows:
- **Built-in targets** (native, mips32, mips32el, arm-cortex-m4, riscv32, avr)
- **Project-defined targets** (from `forge.yml`)

### `vpl clean` — Remove Build Artifacts

```bash
vpl clean              # Remove all build directories
vpl clean --target mips32  # Remove only target's build dir
```

### `vpl --version` / `vpl --help`

Show version or full command help.

## Cross-Compilation Targets

| Target | Triplet | Emulator | Install (Debian/Ubuntu) |
|--------|---------|----------|------------------------|
| `native` | (native) | direct exec | (included with GCC) |
| `mips32` | `mips-linux-gnu` | QEMU | `gcc-mips-linux-gnu qemu-user` |
| `mips32el` | `mipsel-linux-gnu` | QEMU | `gcc-mipsel-linux-gnu qemu-user` |
| `arm-cortex-m4` | `arm-none-eabi` | QEMU | `gcc-arm-none-eabi qemu-user` |
| `riscv32` | `riscv64-unknown-elf` | QEMU | `gcc-riscv64-unknown-elf qemu-user` |
| `avr` | `avr` | simavr | `gcc-avr avr-libc simavr` |

**Installation on Ubuntu/Debian:**

```bash
# Native (GCC)
sudo apt install gcc build-essential

# MIPS cross-compile
sudo apt install gcc-mips-linux-gnu qemu-user

# ARM Cortex-M4 (bare-metal)
sudo apt install gcc-arm-none-eabi qemu-user

# RISC-V
sudo apt install gcc-riscv64-unknown-elf qemu-user

# AVR (Arduino)
sudo apt install gcc-avr avr-libc simavr
```

### Custom Toolchains

Define custom targets in `forge.yml`:

```yaml
project:
  name: myproject

toolchains:
  custom-arm:
    description: "Custom ARM GCC 12.2"
    cc: "arm-linux-gcc-12.2"
    ar: "arm-linux-ar-12.2"
    cflags: ["-mcpu=cortex-a7", "-mfloat-abi=hard"]
    emulator: qemu-arm-static
    sysroot: /path/to/sysroot

targets:
  default: native
```

## Configuration (`forge.yml`)

Minimal required:

```yaml
project:
  name: MyProject
```

Full example with all options:

```yaml
project:
  name: my-firmware
  src_dirs:
    - src
    - lib/hal
  test_dir: test
  include_dirs:
    - src
    - lib/hal/include
  build_dir: build
  mock_dir: mocks

targets:
  default: native

compiler:
  extra_cflags:
    - -Wall
    - -Wextra
    - -pedantic
  defines:
    - DEBUG=1
    - VERSION=1.0.0

toolchains:
  custom-mcu:
    description: "STM32 Cross-Compile"
    cc: arm-none-eabi-gcc
    ar: arm-none-eabi-ar
    cflags:
      - -mcpu=cortex-m4
      - -mthumb
    emulator: qemu-arm-static
```

## Project Layout

After `vpl new myproject`:

```
myproject/
├── forge.yml              # Project configuration
├── src/                   # Source files under test
│   ├── uart.h
│   ├── uart.c
│   └── spi.c
├── test/                  # Unit tests
│   ├── test_uart.c
│   └── test_spi.c
└── mocks/                 # Auto-generated mocks (created by 'vpl mock')
    ├── mock_uart.h
    ├── mock_uart.c
    ├── mock_spi.h
    └── mock_spi.c
```

### Test File Pattern

Tests use the **`test_*.c`** pattern. Each test file:
- Includes `unity.h` (provided by vyperling)
- Includes mocks via `#include "mock_<dependency>.h"`
- Defines test cases with `void test_<name>(void)`

**Example: `test/test_uart.c`**

```c
#include "unity.h"
#include "uart.h"
#include "mock_gpio.h"

void setUp(void) {
    // Called before each test
}

void tearDown(void) {
    // Called after each test
}

void test_uart_init_should_configure_pins(void) {
    gpio_init_Expect();
    uart_init();
    TEST_ASSERT_TRUE(1);
}

void test_uart_send_should_transmit_byte(void) {
    uart_send(0x42);
    TEST_ASSERT_EQUAL_INT(0x42, last_byte_sent);
}
```

## Test Framework

vyperling uses:

- **Unity** — lightweight C assertion framework ([ThrowTheSwitch](https://github.com/ThrowTheSwitch/Unity))
- **CMock** — automated mocking for C functions (auto-generated via `vpl mock`)
- **pycparser** — C header parser for mock generation

### Assertion Macros

Unity provides rich assertions:

```c
// Basic checks
TEST_ASSERT_TRUE(condition)
TEST_ASSERT_FALSE(condition)
TEST_ASSERT_NULL(ptr)
TEST_ASSERT_NOT_NULL(ptr)

// Equality
TEST_ASSERT_EQUAL_INT(expected, actual)
TEST_ASSERT_EQUAL_UINT(expected, actual)
TEST_ASSERT_EQUAL_HEX(expected, actual)
TEST_ASSERT_EQUAL_STRING(expected, actual)

// Arrays
TEST_ASSERT_EQUAL_INT_ARRAY(expected, actual, len)
TEST_ASSERT_EQUAL_MEMORY(expected, actual, len)

// Floating point
TEST_ASSERT_EQUAL_FLOAT(expected, actual, delta)
```

See [Unity documentation](https://github.com/ThrowTheSwitch/Unity/blob/master/docs/UnityAssertionsReference.md) for complete reference.

## Architecture

vyperling's pipeline flows through 8 independent modules, connected by dataclasses:

```
TestUnit ──→ CompileResult ──→ RunResult
```

| Module | Responsibility |
|--------|---|
| **config.py** | Load `forge.yml`, resolve paths, manage project settings |
| **toolchains.py** | Maintain toolchain registry (builtin + user-defined) |
| **discoverer.py** | Glob `test_*.c`, match source files, emit `TestUnit` list |
| **mockgen.py** | Parse headers with pycparser, generate mocks via Jinja2 |
| **compiler.py** | Invoke GCC with ThreadPoolExecutor, cache via `.forge_deps.json` |
| **runner.py** | Execute binaries natively or under QEMU/simavr, parse Unity output |
| **reporter.py** | Rich terminal tables + JUnit XML export |
| **coverage.py** | Generate gcov reports (native-only, best-effort) |

**Key invariant:** Each module emits structured output (dataclass) that the next consumes — no hidden state.

## Development

### Install for Development

```bash
git clone https://github.com/ericsonjoseph/vyperling.git
cd vyperling
pip install -e .
```

### Run Tests

```bash
# Full test suite (coverage on by default)
pytest

# Single test file
pytest tests/test_mockgen.py

# Single test by name
pytest -k test_cross_compile

# Disable coverage
pytest --no-cov
```

### Project Structure

- `vyperling/` — main library
  - `cli.py` — Click entry point (commands: test, build, mock, clean, targets, new)
  - `config.py` — forge.yml loader and config validation
  - `toolchains.py` — Toolchain dataclass + registry
  - `discoverer.py` — test file discovery
  - `mockgen.py` — C header parsing + mock generation
  - `compiler.py` — GCC invocation with caching and parallel jobs
  - `runner.py` — test execution and Unity output parsing
  - `reporter.py` — rich terminal output + JUnit export
  - `coverage.py` — gcov/gcovr pipeline
  - `scaffold.py` — project template generation
  - `errors.py` — exception hierarchy
  - `unity.py` — Unity C framework accessor
  - `c/` — vendored C assets (Unity v2.6.1 + forge_mock)
  - `templates/` — Jinja2 templates for mocks and scaffolding
- `tests/` — comprehensive Python test suite

## Dependencies

**Runtime:**
- `click>=8.0` — CLI framework
- `rich>=13.0` — terminal formatting
- `pyyaml>=6.0` — YAML config parsing
- `pycparser>=2.21` — C header parsing
- `jinja2>=3.0` — template engine
- `gcovr>=7.0` — coverage reporting

**Development:**
- `pytest>=7.0` — testing
- `pytest-cov>=4.0` — coverage measurement

## Mock Generation Capabilities

`vpl mock` (pycparser + Jinja2) emits the full CMock-style API per function:
`_Expect` / `_ExpectAndReturn`, `_ExpectAnyArgs`, `_Ignore` / `_IgnoreAndReturn`,
`_IgnoreArg_<param>`, `_ReturnThruPtr_<param>`, `_AddCallback` / `_Stub`, and
`mock_<module>_Init` / `_Verify` / `_Destroy`.

Supported argument/function shapes:

| Shape | Example | Handling |
|-------|---------|----------|
| Scalars / typedefs | `uint16_t len` | Mapped to the matching `UNITY_TEST_ASSERT_EQUAL_*` |
| `const char *` | `const char *msg` | String compare |
| Other pointers | `uint8_t *buf` | Pointer-identity compare; writable ptrs get `_ReturnThruPtr_*` |
| **Variadic** | `int log_printf(const char *fmt, ...)` | Fixed params asserted; variadic tail ignored |
| **Function-pointer params** | `void register_cb(void (*cb)(int))` | Stored as `void *`, asserted by identity (PTR) |
| **Struct-by-value (complete)** | `int classify(struct Point p)` | Byte-compared via `UNITY_TEST_ASSERT_EQUAL_MEMORY` |

See [examples/mock_features](examples/mock_features) for a runnable project that
exercises all three of the last group.

## Known Limitations (v0.0.2)

- **Mock generation**: Incomplete (opaque) struct-by-value params are skipped with a
  warning — a forward-declared `struct Foo` has unknown `sizeof`, so it cannot be
  stored or compared. A pointer to the same struct mocks fine.
- **Coverage**: Native target only; requires GCC with `-fprofile-arcs -ftest-coverage` support
- **Emulation**: Timeout-based (default 30s per test binary)

## Roadmap

### v0.0.3
- Full C preprocessor awareness in mockgen (`#ifdef`-guarded declarations)
- CException support

### v0.0.4
- On-target execution via OpenOCD/pyOCD debug probe (`--target on-device`)
- VS Code extension for inline pass/fail annotations

### v0.0.N (Future)
- `--watch` mode: rerun tests on file change
- Argument capture in mocks (store last N calls, not just count)
- `vyperling report` command to re-display results from previous run without recompiling

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Write tests for your changes
4. Run the full test suite (`pytest`)
5. Commit with conventional messages
6. Push and open a pull request

For major changes, please open an issue first to discuss.

## License

MIT — see [LICENSE](LICENSE) file for details.

## Credits

- **vyperling** by [Ericson Joseph](https://github.com/ericsonjoseph)
- **Unity** testing framework by [ThrowTheSwitch](https://github.com/ThrowTheSwitch/Unity)
- **CMock** concepts adapted from [CMock](https://github.com/ThrowTheSwitch/CMock)

## Support

- 📖 [Architecture Documentation](vyperling-architecture.md)
- 🐛 [Issue Tracker](https://github.com/ericsonjoseph/vyperling/issues)
- 💬 [Discussions](https://github.com/ericsonjoseph/vyperling/discussions)
