// Pure (vscode-free) test discovery logic. Ports the conventions from
// vyperling/discoverer.py and runnergen.py so the extension treats files and
// functions as tests exactly the way the CLI does. Kept free of `vscode` imports
// so it is unit-testable under vitest.

export function escapeRe(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

// Build the test-function matcher for the project's conventions. Ports
// _test_func_re() from vyperling/runnergen.py: snake_case `test_*` or camelCase
// `testFoo`, with the `Test`-file / `test`-fn Ceedling variant handled too.
export function testFnRegex(testPrefix: string, testNaming: string): RegExp {
  let namePat: string;
  if (testNaming === "camelCase") {
    const p = escapeRe(testPrefix);
    const pLower = escapeRe(testPrefix[0].toLowerCase() + testPrefix.slice(1));
    namePat =
      p === pLower
        ? `${p}[A-Za-z0-9_]+`
        : `(?:${p}|${pLower})[A-Za-z0-9_]+`;
  } else {
    namePat = `${escapeRe(testPrefix)}[A-Za-z0-9_]+`;
  }
  // Mirrors runnergen: `void <name>( void? )` with flexible whitespace.
  return new RegExp(
    `^[ \\t]*void[ \\t]+(${namePat})[ \\t]*\\([ \\t]*(?:void)?[ \\t]*\\)`,
  );
}

// True if a directory entry is a test file under the given prefix (e.g.
// `test_uart.c` for prefix "test_", `TestUart.c` for prefix "Test").
export function isTestFile(entry: string, testPrefix: string): boolean {
  return entry.startsWith(testPrefix) && entry.endsWith(".c");
}

// Strip the test prefix and the `.c` suffix to get the unit name, mirroring
// discoverer.py (`TestExecutor.c` -> `Executor`, `test_uart.c` -> `uart`).
export function unitNameFromFile(entry: string, testPrefix: string): string {
  return entry.slice(testPrefix.length, -2);
}

export interface DiscoveredTest {
  name: string;
  line: number; // 0-based line index of the function definition
}

// Scan a test file's text for test function definitions, returning each name
// with its 0-based line. The caller turns `line` into a vscode.Range.
export function extractTestFns(
  text: string,
  testPrefix: string,
  testNaming: string,
): DiscoveredTest[] {
  const re = testFnRegex(testPrefix, testNaming);
  const out: DiscoveredTest[] = [];
  text.split(/\r?\n/).forEach((line, idx) => {
    const m = line.match(re);
    if (m) {
      out.push({ name: m[1], line: idx });
    }
  });
  return out;
}
