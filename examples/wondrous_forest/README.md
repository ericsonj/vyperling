# wondrous_forest — Not Ported (Ceedling Partials)

This example from the official Ceedling repo demonstrates the **Partials** feature, which enables testing of `static`, `inline`, and `static inline` C functions and file-scope static variables — something impossible under normal C linkage rules.

## Why this example is not ported

Ceedling Partials work by injecting the entire source TU into the test TU at compile time via a preprocessor trick (`TEST_PARTIAL_ALL_MODULE`). This is not a mocking technique — it requires compiler-level source injection.

vyperling does not implement Partials and has no equivalent. The core pipeline is:

1. **Compile** test TU + SUT TU + mock TUs separately
2. **Link** them into a test binary

Partials break step 1 by merging test and SUT TUs. Supporting this would require a fundamentally different compile step for affected tests.

## Patterns used in wondrous_forest that DO work in vyperling

| Pattern | wondrous_forest test | vyperling support |
|---------|----------------------|-------------------|
| Traditional mock-based tests | `TestUartDriver.c`, `TestAlertManager.c` (mock-only tests) | ✓ fully supported |
| CMock `_ExpectAndReturn` / `_Expect` | all test files | ✓ |
| `setUp` / `tearDown` lifecycle | all test files | ✓ |

## If you need to test static functions

Options within vyperling:

1. **Expose via a test-only header**: wrap static functions in `#ifdef TEST` and declare them non-static.
2. **Extract to a helper module**: move logic out of static scope into a separately testable module.
3. **Use `extra_srcs`**: include the source TU directly so the linker sees its symbols (works for non-static functions; static still won't link across TUs).

These are standard embedded C testing patterns that don't require toolchain magic.
