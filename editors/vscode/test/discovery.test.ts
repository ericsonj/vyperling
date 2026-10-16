import { describe, it, expect } from "vitest";

import {
  escapeRe,
  extractTestFns,
  isTestFile,
  testFnRegex,
  unitNameFromFile,
} from "../src/discovery";

describe("escapeRe", () => {
  it("escapes regex metacharacters", () => {
    expect(escapeRe("a.b*c")).toBe("a\\.b\\*c");
  });
  it("leaves plain identifiers untouched", () => {
    expect(escapeRe("test_")).toBe("test_");
  });
});

describe("testFnRegex — snake_case (default)", () => {
  const re = () => testFnRegex("test_", "snake_case");

  it("matches a standard test function", () => {
    expect("void test_uart_init(void)".match(re())?.[1]).toBe("test_uart_init");
  });
  it("matches the empty-arg form ()", () => {
    expect("void test_foo()".match(re())?.[1]).toBe("test_foo");
  });
  it("tolerates extra whitespace and tabs", () => {
    expect("\tvoid\ttest_bar ( void )".match(re())?.[1]).toBe("test_bar");
  });
  it("rejects setUp / tearDown", () => {
    expect("void setUp(void)".match(re())).toBeNull();
    expect("void tearDown(void)".match(re())).toBeNull();
  });
  it("rejects a non-prefixed function", () => {
    expect("void helper_thing(void)".match(re())).toBeNull();
  });
});

describe("testFnRegex — camelCase Ceedling (prefix 'Test')", () => {
  const re = () => testFnRegex("Test", "camelCase");

  it("matches the lowercase-first function form (testFoo)", () => {
    expect(
      "void testInitShouldCallInit(void)".match(re())?.[1],
    ).toBe("testInitShouldCallInit");
  });
  it("also matches the exact-prefix form (TestFoo)", () => {
    expect("void TestRunSomething(void)".match(re())?.[1]).toBe(
      "TestRunSomething",
    );
  });
  it("rejects setUp / tearDown", () => {
    expect("void setUp(void)".match(re())).toBeNull();
  });
});

describe("isTestFile", () => {
  it("accepts snake_case test files", () => {
    expect(isTestFile("test_uart.c", "test_")).toBe(true);
  });
  it("accepts Ceedling Test files", () => {
    expect(isTestFile("TestExecutor.c", "Test")).toBe(true);
  });
  it("rejects headers and non-test sources", () => {
    expect(isTestFile("Executor.h", "Test")).toBe(false);
    expect(isTestFile("helper.c", "test_")).toBe(false);
  });
});

describe("unitNameFromFile", () => {
  it("strips snake_case prefix and .c", () => {
    expect(unitNameFromFile("test_uart.c", "test_")).toBe("uart");
  });
  it("strips Ceedling prefix and .c", () => {
    expect(unitNameFromFile("TestExecutor.c", "Test")).toBe("Executor");
  });
});

describe("extractTestFns", () => {
  const src = [
    "#include <unity.h>",
    "void setUp(void) {}",
    "",
    "void test_a(void) {",
    "  TEST_ASSERT(1);",
    "}",
    "void test_b(void) {}",
  ].join("\n");

  it("returns ordered names with 0-based line numbers", () => {
    const found = extractTestFns(src, "test_", "snake_case");
    expect(found).toEqual([
      { name: "test_a", line: 3 },
      { name: "test_b", line: 6 },
    ]);
  });

  it("finds nothing when the prefix truly doesn't appear", () => {
    // 'Spec' prefix: neither Spec* nor spec* appears in the snake_case source.
    expect(extractTestFns(src, "Spec", "camelCase")).toEqual([]);
  });

  it("handles camelCase Ceedling sources", () => {
    const cc = "void testInitShouldRun(void) {}\nvoid tearDown(void) {}";
    expect(extractTestFns(cc, "Test", "camelCase")).toEqual([
      { name: "testInitShouldRun", line: 0 },
    ]);
  });
});
