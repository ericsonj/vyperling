import * as path from "path";

// Pure (vscode-free) path / text helpers, unit-testable under vitest.

// Resolve a path emitted by vpl (relative to the project root) to an absolute
// path. Absolute paths are returned unchanged. Used for both the test binary
// and Unity's reported source files.
export function resolveAgainstRoot(root: string, p: string): string {
  return path.isAbsolute(p) ? p : path.join(root, p);
}

// The per-target build subdirectory. `--debug` builds land in `<target>-debug`
// so they never clobber the optimised/coverage build's cache.
export function buildSubdir(target: string, debug: boolean): string {
  return debug ? `${target}-debug` : target;
}

// TestRun.appendOutput needs CRLF line endings to render in the terminal panel.
export function crlf(s: string): string {
  return s.replace(/\r?\n/g, "\r\n");
}
