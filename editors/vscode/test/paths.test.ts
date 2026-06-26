import { describe, it, expect } from "vitest";
import * as path from "path";

import { buildSubdir, crlf, resolveAgainstRoot } from "../src/paths";

describe("resolveAgainstRoot", () => {
  it("joins a relative path to the root", () => {
    expect(resolveAgainstRoot("/proj", "build/native/Executor")).toBe(
      path.join("/proj", "build/native/Executor"),
    );
  });
  it("returns an absolute path unchanged", () => {
    expect(resolveAgainstRoot("/proj", "/abs/Executor")).toBe("/abs/Executor");
  });
});

describe("buildSubdir", () => {
  it("appends -debug when debug", () => {
    expect(buildSubdir("native", true)).toBe("native-debug");
  });
  it("returns the bare target otherwise", () => {
    expect(buildSubdir("native", false)).toBe("native");
    expect(buildSubdir("mips32", false)).toBe("mips32");
  });
});

describe("crlf", () => {
  it("converts LF to CRLF", () => {
    expect(crlf("a\nb\n")).toBe("a\r\nb\r\n");
  });
  it("does not double up existing CRLF", () => {
    expect(crlf("a\r\nb")).toBe("a\r\nb");
  });
});
