import { describe, it, expect } from "vitest";

import { ResultsDoc, ResultsUnit, ResultsTest } from "../src/types";

// Guards the schema mirror in src/types.ts against drift from the JSON written
// by vyperling/reporter.py:write_results_json (schema 1).
describe("ResultsDoc schema", () => {
  const doc: ResultsDoc = {
    schema: 1,
    target: "native",
    units: [
      {
        name: "Executor",
        binary: "build/native/Executor",
        compile_error: false,
        timed_out: false,
        duration_ms: 3,
        stderr: "",
        tests: [
          {
            file: "test/TestExecutor.c",
            line: 25,
            name: "testInitShouldRun",
            status: "pass",
            message: "",
          },
        ],
      },
    ],
  };

  it("round-trips through JSON", () => {
    const parsed = JSON.parse(JSON.stringify(doc)) as ResultsDoc;
    expect(parsed).toEqual(doc);
  });

  it("allows binary to be null on compile error", () => {
    const unit: ResultsUnit = { ...doc.units[0], binary: null, compile_error: true };
    expect(unit.binary).toBeNull();
  });

  it("accepts each test status literal", () => {
    const statuses: ResultsTest["status"][] = ["pass", "fail", "ignore"];
    expect(statuses).toHaveLength(3);
  });
});
