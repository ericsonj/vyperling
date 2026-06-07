# guarded_api — preprocessor-aware mocking + CException

Demonstrates two v0.0.3 features together in one small native project:

| Feature | Where |
|---------|-------|
| **Full preprocessor awareness in mockgen** (`#ifdef`-guarded declarations) | `parser_dump_state()` in `parser.h`, guarded by `#ifdef PARSER_DEBUG` |
| **CException support** (`compiler.cexception: true`) | `validator_check()` `Throw`s; `line_processor_handle()` and the tests `Try`/`Catch` it |

## How the `#ifdef` story works

`parser.h` declares `parser_dump_state()` only when `PARSER_DEBUG` is defined:

```c
#ifdef PARSER_DEBUG
void parser_dump_state(const char *line, int token_count);
#endif
```

`forge.yml` sets `compiler.defines: [PARSER_DEBUG]`. That list feeds **both**:
- the real compile (`compiler.py` passes it as `-DPARSER_DEBUG` to `gcc`), and
- `vpl mock`'s preprocessor pass (`mockgen.py`'s `_cpp_args` forwards the same
  `compiler.defines` to `cc -E`, the *real* preprocessor pycparser runs headers
  through).

Because both paths see the identical `-D` set, `mock_parser.h` ends up with a
`parser_dump_state_Expect(...)` exactly when the real `parser.c` has the
function — they can never silently disagree. `test_line_processor.c` asserts
on that mock call inside an `#ifdef PARSER_DEBUG` block, so the test file
itself only compiles the assertion when the symbol exists — mirroring the
guard in the header it is testing against.

Try it: delete `- PARSER_DEBUG` from `forge.yml`'s `compiler.defines` and
re-run. `parser_dump_state` vanishes from **both** the real build and the
generated mock at once — there is no place left for the two to drift apart.

(`vpl mock --target <cross-target>` also emits an advisory `UserWarning` —
"...resolve using this target's macros and may differ from 'native'..." —
because `#ifdef` resolution depends on the target toolchain's macros, not
just `compiler.defines`. This example is native-only, so that path isn't
exercised here, but it's worth knowing about for cross-compiled projects.)

## How the CException story works

`forge.yml` sets `compiler.cexception: true`, so vyperling links the vendored
`CException.c` (v1.3.4) into every test binary for this project — the same
opt-in switch that controls whether `compiler.defines`/`extra_cflags` apply,
just for the CException runtime. `validator_check()` reports failure by
`Throw`ing a `CEXCEPTION_T` (an `unsigned int` error code) instead of
returning a status:

```c
void validator_check(const char *line)
{
    if (line == NULL || line[0] == '\0') {
        Throw(VALIDATOR_ERR_EMPTY);
    }
    ...
}
```

`line_processor_handle()` is the SUT that wraps it in `Try`/`Catch` and
converts the exception into a `-1` return — `test_line_processor.c` checks
that conversion. Because that test mocks `parser` but keeps `validator`
**real** (a generated mock cannot replicate a `Throw`'s non-local jump),
`validator.c` is not auto-linked — vyperling links a test's SUT plus mocks
of its dependencies, never the real source of a mocked-out collaborator. So
`forge.yml` links it explicitly into just that one unit via `extra_srcs`:

```yaml
project:
  extra_srcs:
    line_processor:
      - src/validator.c
```

`test_validator.c` exercises `validator_check()` directly,
`Catch`ing each error code and asserting on it — proof that `Try`, `Catch`,
`Throw`, and `CEXCEPTION_T` all work exactly as upstream CException
documents, with zero extra setup beyond the `forge.yml` flag.

## Layout

```
guarded_api/
├── forge.yml                 # compiler.defines: [PARSER_DEBUG], compiler.cexception: true
├── src/
│   ├── parser.{h,c}          # #ifdef PARSER_DEBUG-guarded declaration
│   ├── validator.{h,c}       # Throw()s CEXCEPTION_T error codes
│   └── line_processor.{h,c}  # SUT — Try/Catch around validator_check, calls parser
└── test/
    ├── test_parser.c         # parser as its own SUT — calls the guarded fn directly
    ├── test_validator.c      # validator as its own SUT — Try/Catch/Throw, no mocks
    └── test_line_processor.c # line_processor as SUT — parser mocked, validator real
```

`mocks/` and `build/` are generated — they are git-ignored.

## Run

```bash
cd examples/guarded_api
vpl test                    # discover → mock → compile → run → report
vpl test -k validator       # just the CException tests
vpl mock src/parser.h       # inspect the generated mock_parser.{c,h} directly
```

## Cross-checked against Ceedling (the reference toolchain)

`project.yml` configures **the same test sources** to run under Ceedling —
the Ruby-based, CMock/CException-backed tool vyperling targets API-compat
with. `ceedling test:all` and `vpl test` both report **12/12 passing** on
byte-identical `test/*.c` files, with the parallel config:

| Setting | `forge.yml` (vyperling) | `project.yml` (Ceedling) |
|---------|------------------------|--------------------------|
| `#ifdef` define | `compiler.defines: [PARSER_DEBUG]` | `:defines: :test: '*': [PARSER_DEBUG]` |
| CException | `compiler.cexception: true` | `:project: :use_exceptions: TRUE` |
| Mock prefix | `mock_` (vyperling default) | `:cmock: :mock_prefix: mock_` |
| Test prefix | `test_` (vyperling default) | `:test_file_prefix: test_` |

Two details worth knowing if you read `test/test_line_processor.c`:

- **`TEST_SOURCE_FILE("validator.c")`** — a bare macro call right after the
  `#include`s. It expands to nothing (`#define TEST_SOURCE_FILE(a)` lives in
  `unity.h`, vendored identically by both tools), so it's a no-op for vyperling
  — which already links `validator.c` via `forge.yml`'s `project.extra_srcs`.
  For Ceedling, it's the **documented build-directive** that does the same
  job: link a real collaborator source into one specific test executable
  without mocking it. Same problem, each tool's own idiom, same macro text
  compiles cleanly under both.

Run both and diff the results — agreement here is the strongest signal that
vyperling's `#ifdef`-aware mockgen and CException support aren't just
internally self-consistent, but match the reference implementation's
behavior exactly:

```bash
vpl test            # 12 passed
ceedling test:all   # TESTED: 12  PASSED: 12  FAILED: 0
```

(Requires `gem install ceedling` — entirely optional; this comparison is not
needed to use or understand the example, just to trust it.)
