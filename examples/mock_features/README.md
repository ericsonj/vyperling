# mock_features — mockgen edge-case coverage

Demonstrates that vyperling's mock generator handles three C constructs that
were skipped in v0.1 and are now fully supported:

| Construct | Example | How the mock handles it |
|-----------|---------|-------------------------|
| **Variadic functions** | `int log_printf(const char *fmt, ...)` | Fixed params captured & asserted; the variadic tail is ignored (a `va_list` can't be inspected after the call). `_Expect`/`_ExpectAndReturn` cover only the fixed params. |
| **Function-pointer params** | `void register_cb(void (*cb)(int))` | The pointer is stored as `void *` and asserted by identity via `UNITY_TEST_ASSERT_EQUAL_PTR` — "was the right callback passed?". |
| **Complete struct-by-value** | `int classify_point(struct Point p)` | Byte-compared with `UNITY_TEST_ASSERT_EQUAL_MEMORY` (`sizeof` is known). |
| **Pointer-to-opaque** | `void use_opaque_ptr(struct Opaque *o)` | Mocked normally — pointer size is always known. |

## Layout

```
mock_features/
├── forge.yml           # project config (mock_prefix: "Mock")
├── src/
│   ├── Logger.{h,c}    # variadic dependency
│   ├── EventBus.{h,c}  # function-pointer-param dependency
│   ├── Geometry.{h,c}  # struct-by-value (complete + anon-typedef + opaque)
│   └── App.{h,c}       # SUT that calls all three
└── test/
    ├── TestVariadic.c  # variadic mock, exercised directly
    ├── TestFnptr.c     # fnptr-param mock, exercised directly
    ├── TestStructs.c   # struct + opaque-pointer mock, exercised directly
    └── TestApp.c       # all three mocked behind the App SUT
```

`mocks/` and `build/` are generated — they are git-ignored.

Note: `TestVariadic`/`TestFnptr`/`TestStructs` deliberately do NOT match a `src/`
module (a `TestFoo.c` is conventionally the test for `Foo.c`, which is then linked
as the SUT). These tests have no SUT — they drive the generated mock API directly —
so `vpl test` prints a harmless "No source file found" warning for each. `TestApp`
follows the normal convention: `App.c` is the SUT, its dependencies are mocked.

## Run

```bash
cd examples/mock_features
vpl test            # discover → mock → compile → run → report
vpl test -k Logger  # just the variadic tests
```

All tests pass with no warnings — the struct Opaque forward declaration is present in
`Geometry.h` (enabling the pointer variant) but `use_opaque_ptr` is the only function
using it, and pointer size is always known.
