# Vyperling — VS Code extension

Inline pass/fail annotations and native debugging for
[vyperling](../../README.md) embedded-C unit tests, built on the native VS Code
Test Explorer API.

## What it does

- Discovers test files in your project's `test_dir` and lists each test function
  in the Test Explorer. Honors your `forge.yml` `conventions`: both default
  snake_case (`test_uart.c` → `void test_*(void)`) and Ceedling-style
  (`test_prefix: "Test"` + `test_naming: "camelCase"` → `TestUart.c` →
  `void testFoo(void)`).
- **Run** a test unit → invokes `vpl test --output json` and maps results back to
  the editor: green/red gutter icons, failing assertions peek their message
  inline at `file:line`, ignored tests show as skipped.
- **Debug** a test unit → rebuilds it with debug symbols (`vpl test --debug`) and
  launches the native binary under gdb (via the C/C++ extension), so breakpoints
  in both the test file and the source-under-test hit.

## Requirements

- The `vpl` (or `vyperling`) CLI on your `PATH` — install with
  `pip install vyperling` or `poetry install` in the tool repo.
- A `forge.yml` at (or above) your workspace root. Activation triggers on
  `workspaceContains:**/forge.yml`.
- [ms-vscode.cpptools](https://marketplace.visualstudio.com/items?itemName=ms-vscode.cpptools)
  (declared as an extension dependency) for debugging.
- `gcc` + `gdb` for the native target.

## Settings

| Setting | Default | Description |
| --- | --- | --- |
| `vyperling.cliPath` | `vpl` | Path to the vyperling CLI. |
| `vyperling.defaultTarget` | `""` | `--target` value; empty uses `targets.default` from `forge.yml`. |
| `vyperling.jobs` | `4` | Parallel compile jobs (`-j`). |
| `vyperling.shellPath` | `""` | Shell used to run vpl so your profile PATH (nvm/poetry/venv) loads. Empty uses `$SHELL`. |
| `vyperling.shellArgs` | `["-lic"]` | Args for that shell. `-lic` (login+interactive) sources your rc but may emit prompt-plugin noise; use `["-lc"]` if PATH is in a login profile and you want a quieter run. |

### Why a shell?

GUI-launched VS Code does **not** inherit your login-shell `PATH`, so a bare
`vpl` would fail to resolve when it lives under nvm, poetry, or a virtualenv. The
extension runs the CLI through your shell (default `$SHELL -lic`) so the same
`PATH` you have in a terminal is used. Verify with `your-shell -lc 'which vpl'`.

## Debugging

Native (`target == native`) only in this version. The Debug profile first runs
`vpl test --debug -k <unit>`, which builds with `-g -O0` into
`build/native-debug/` (a separate dir so the optimised/coverage build cache is
untouched), then launches a `cppdbg` session on that binary. Breakpoints in the
`test_*.c` and the source-under-test bind because the debug build has DWARF
symbols.

If you prefer a manual config, build once with `vpl test --debug` and add this
to your project's `.vscode/launch.json`:

```jsonc
{
  "type": "cppdbg",
  "request": "launch",
  "name": "Debug <unit>",
  "program": "${workspaceFolder}/build/native-debug/<unit>",
  "MIMode": "gdb",
  "cwd": "${workspaceFolder}"
}
```

Cross-target debugging (QEMU `-g <port>` + gdb attach) is a planned follow-up.

## Troubleshooting

Open **View → Output → "Vyperling"** for the exact command, working directory,
exit code, and `vpl` stdout/stderr of every run.

| Symptom | Cause | Fix |
| --- | --- | --- |
| "did not record any output" | `vpl` not found in the GUI `PATH`. | Set `vyperling.cliPath` to an absolute path, or fix `vyperling.shellArgs` so your rc loads. Check the Vyperling output for a spawn error. |
| Tests show as **skipped** (no green/red) | Discovered function names don't match the run results — usually a convention mismatch. | Confirm `conventions.test_prefix` / `test_naming` in `forge.yml`. The output channel logs `[discover] <unit>: N test(s)`; if `N` is 0 the matcher missed your signatures. |
| Debug session exits immediately, breakpoints never bind | Binary built without `-g` (DWARF). | The Debug profile builds with `--debug` automatically; if running gdb manually, build with `vpl test --debug` and point at `build/<target>-debug/`. |
| Shell banner / `gitstatus` noise in the run | Interactive shell (`-i`) loads prompt plugins. | Set `vyperling.shellArgs` to `["-lc"]` (verify `vpl` still resolves first). |

## Developing the extension

Uses [Yarn Berry](https://yarnpkg.com/) (pinned via `packageManager` in
`package.json`). [corepack](https://nodejs.org/api/corepack.html) ships with
Node ≥ 16 and resolves the right Yarn version automatically:

```bash
cd editors/vscode
corepack enable        # one-time: lets `yarn` use the pinned version
yarn install
yarn build             # bundle src -> dist/extension.js via esbuild
yarn typecheck         # tsc --noEmit
yarn test              # vitest unit tests (pure logic; no vscode needed)
yarn test:cov          # tests + coverage report (text + html)
```

### Unit tests

Pure, vscode-free logic lives in `src/discovery.ts` (convention matcher ported
from `runnergen.py`), `src/paths.ts`, and `src/forgeConfig.ts`, and is covered by
[vitest](https://vitest.dev/) suites under `test/`. The vscode-coupled modules
(`testController.ts`, `runner.ts`, `debug.ts`) are verified manually via the F5
dev host — the tests never import `vscode`, so no API mock is required.

Then open `editors/vscode` in VS Code and press **F5** ("Run Extension") to
launch an Extension Development Host. Open a vyperling project (e.g. the
`temp_sensor` example) inside it and exercise the Test Explorer. Set breakpoints
in `src/*.ts` in the main window to step through the extension itself.

The JSON contract is produced by `vpl test --output json` — see
`write_results_json` in [vyperling/reporter.py](../../vyperling/reporter.py).
Keep [src/types.ts](src/types.ts) in sync with its `schema` version.
