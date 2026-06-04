# vyperling

**Embedded C test runner with cross-compilation support.**
A pip-installable replacement for [Ceedling](https://github.com/ThrowTheSwitch/Ceedling) — no Ruby required.

## Requirements

- Python >= 3.11
- GCC (native target): `sudo apt install gcc`
- Cross-compilers and QEMU for embedded targets (see table below)

## Install

```bash
pip install vyperling
```

Development (editable install from source):

```bash
git clone https://github.com/ericsonjoseph/vyperling.git
cd vyperling
pip install -e .
```

## Quick start

```bash
vyperling new myproject
cd myproject
vyperling test
vyperling test --target mips32
vyperling mock src/uart.h
vyperling targets
```

## Cross-compilation targets

| Target | Install |
|--------|---------|
| `native` | (default, no extra packages) |
| `mips32` | `sudo apt install gcc-mips-linux-gnu qemu-user` |
| `mips32el` | `sudo apt install gcc-mipsel-linux-gnu qemu-user` |
| `arm-cortex-m4` | `sudo apt install gcc-arm-none-eabi qemu-user` |
| `riscv32` | `sudo apt install gcc-riscv64-unknown-elf qemu-user` |
| `avr` | `sudo apt install gcc-avr avr-libc simavr` |

## Project layout

```
myproject/
├── forge.yml        # project configuration
├── src/             # source under test
├── test/            # test_*.c files
└── mocks/           # auto-generated mock stubs
```

## License

MIT
