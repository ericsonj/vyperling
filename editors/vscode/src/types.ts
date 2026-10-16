// Mirror of the JSON schema written by `vpl test --output json`
// (vyperling/reporter.py:write_results_json). Keep in sync with schema:1.

export type TestStatus = "pass" | "fail" | "ignore";

export interface ResultsTest {
  file: string;
  line: number;
  name: string;
  status: TestStatus;
  message: string;
}

export interface ResultsUnit {
  name: string;
  binary: string | null;
  compile_error: boolean;
  timed_out: boolean;
  duration_ms: number;
  stderr: string;
  tests: ResultsTest[];
}

export interface ResultsDoc {
  schema: number;
  target: string;
  units: ResultsUnit[];
}
