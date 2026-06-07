# temp_sensor — Ceedling Compatibility Example

Ported from the official [Ceedling temp_sensor example](https://github.com/ThrowTheSwitch/Ceedling/tree/master/examples/temp_sensor) with **zero file renames**. Source files and test files are verbatim copies from the upstream repo.

## What this validates

- Test file prefix `Test` and mock prefix `Mock` via `conventions` in `forge.yml`
- camelCase test function names (`testFooBar()` — Ceedling convention)
- Nested test dirs (`test/` and `test/adc/`) via `rglob`
- Nested source dirs (`src/` and `src/calculators/`)
- Custom assertions in `test/support/` via `support_srcs`
- Integration tests (`TestTimerIntegrated`, `TestUsartIntegrated`) using `extra_srcs`
- `extra_ldflags: [-lm]` for math library
- Global defines (`TEST`, `SUPPLY_VOLTAGE`, `TEST_USART_INTEGRATED_STRING`)
- Struct-by-value params in mocks (`EXAMPLE_STRUCT_T`)
- Pointer params with `ReturnThruPtr`

## Results

```
50 passed, 0 failed, 0 ignored — all tests green
```

## Running

```bash
cd examples/temp_sensor
vpl test               # run all tests
vpl test -k AdcModel   # run one module
vpl test --output junit  # generate build/native/results.xml
```

## Porting notes

All changes relative to the Ceedling project are in `forge.yml` only:

| Ceedling `project.yml` | `forge.yml` equivalent |
|------------------------|------------------------|
| `test_file_prefix: Test` | `conventions.test_prefix: "Test"` |
| `mock_prefix: Mock` | `conventions.mock_prefix: "Mock"` |
| `test_naming: camelCase` | `conventions.test_naming: "camelCase"` |
| `source_root: src/**` | `src_dirs: [src, src/calculators]` |
| `test_root: test/**` | `test_dir: test` (rglob covers subdirs) |
| `support_root: test/support` | `support_srcs: [test/support/UnityHelper.c]` |
| per-file `extra_srcs` | `project.extra_srcs` map |
| `-lm` library | `compiler.extra_ldflags: [-lm]` |
| test-specific defines | `compiler.defines` (applied globally) |

## Known gaps vs Ceedling

| Gap | Notes |
|-----|-------|
| Per-test defines (`SUPPLY_VOLTAGE` per file) | vyperling applies defines globally; no per-unit override |
| `mocks/calculators/` path includes | Requires `mocks/calculators -> .` symlink; see forge.yml |
| Strict ordering | Not implemented in vyperling |
| gcov plugin | Use `vpl test --coverage` instead |
