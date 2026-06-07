# cross_mips — MIPS cross-compile example

Demonstrates `vyperling` cross-compiling C unit tests to MIPS (big-endian and
little-endian) and running them transparently under `qemu-user`.

## Modules

| Source | What it does |
|--------|-------------|
| `src/crc16.{c,h}` | CRC-16/CCITT-FALSE — bitwise, no lookup table |
| `src/packet.{c,h}` | Packet framing: SOF + length + payload + CRC16 |

`packet` calls `crc16_compute()` — mocked in `test_packet.c` so the
framing logic is tested independently of the CRC arithmetic.

## Requirements

| Tool | Package (Debian/Ubuntu) |
|------|------------------------|
| `mips-linux-gnu-gcc` | `gcc-mips-linux-gnu` |
| `mipsel-linux-gnu-gcc` | `gcc-mipsel-linux-gnu` |
| `qemu-mips` | `qemu-user` |
| `qemu-mipsel` | `qemu-user` |

```bash
sudo apt install gcc-mips-linux-gnu gcc-mipsel-linux-gnu qemu-user
```

## Running

```bash
# Native — fast iteration, no cross toolchain needed
vpl test

# MIPS big-endian (EI_DATA=2)
vpl test --target mips32

# MIPS little-endian (EI_DATA=1)
vpl test --target mips32el
```

## What the E2E test checks

`tests/test_e2e_cross.py` exercises this example directly:

1. Runs `vpl test --target mips32` (and `mips32el`) inside a temp copy.
2. Asserts all tests pass and Unity reports `N passed`.
3. Reads the produced ELF and verifies: magic `\x7fELF`, correct `EI_DATA`
   endianness byte, and `e_machine == 8` (EM_MIPS) — proving a real cross
   binary was built, not a silent native fallback.
4. Mutates one assertion to force failure and verifies qemu-user propagates a
   non-zero exit code back to the host.
