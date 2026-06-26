import { afterEach, describe, it, expect } from "vitest";
import * as fs from "fs";
import * as os from "os";
import * as path from "path";

import { findForgeConfig } from "../src/forgeConfig";

const tmpRoots: string[] = [];

function mkTmp(): string {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "vpl-cfg-"));
  tmpRoots.push(dir);
  return dir;
}

function writeYml(dir: string, body: string): void {
  fs.writeFileSync(path.join(dir, "forge.yml"), body, "utf-8");
}

afterEach(() => {
  while (tmpRoots.length) {
    fs.rmSync(tmpRoots.pop()!, { recursive: true, force: true });
  }
});

describe("findForgeConfig — defaults", () => {
  it("falls back to defaults when keys are absent", () => {
    const dir = mkTmp();
    writeYml(dir, "project:\n  name: demo\n");
    const cfg = findForgeConfig(dir)!;
    expect(cfg.root).toBe(dir);
    expect(cfg.testDir).toBe("test");
    expect(cfg.buildDir).toBe("build");
    expect(cfg.testPrefix).toBe("test_");
    expect(cfg.testNaming).toBe("snake_case");
    expect(cfg.defaultTarget).toBe("native");
  });
});

describe("findForgeConfig — explicit values", () => {
  it("reads project, conventions and targets scalars", () => {
    const dir = mkTmp();
    writeYml(
      dir,
      [
        "project:",
        "  name: temp_sensor",
        "  test_dir: spec",
        "  build_dir: out",
        "targets:",
        "  default: mips32",
        "conventions:",
        '  test_prefix: "Test"',
        '  test_naming: "camelCase"',
        "",
      ].join("\n"),
    );
    const cfg = findForgeConfig(dir)!;
    expect(cfg.testDir).toBe("spec");
    expect(cfg.buildDir).toBe("out");
    expect(cfg.defaultTarget).toBe("mips32");
    expect(cfg.testPrefix).toBe("Test");
    expect(cfg.testNaming).toBe("camelCase");
  });
});

describe("findForgeConfig — walk up", () => {
  it("finds an ancestor forge.yml from a nested subdir", () => {
    const dir = mkTmp();
    writeYml(dir, "project:\n  name: demo\n");
    const nested = path.join(dir, "a", "b", "c");
    fs.mkdirSync(nested, { recursive: true });
    const cfg = findForgeConfig(nested);
    expect(cfg?.root).toBe(dir);
  });

  it("returns undefined when no forge.yml exists up to fs root", () => {
    const dir = mkTmp(); // empty, no forge.yml
    const nested = path.join(dir, "x");
    fs.mkdirSync(nested);
    expect(findForgeConfig(nested)).toBeUndefined();
  });
});
