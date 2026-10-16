import * as fs from "fs";
import * as path from "path";

// Minimal forge.yml reader. We only need a handful of keys for discovery and
// build-dir resolution; defaults mirror vyperling/config.py:DEFAULT_CONFIG.
// A naive line-based parser keeps the extension dependency-free (no yaml lib).

export interface ForgeConfig {
  root: string; // directory containing forge.yml
  testDir: string; // project.test_dir (default "test")
  buildDir: string; // project.build_dir (default "build")
  testPrefix: string; // conventions.test_prefix (default "test_")
  testNaming: string; // conventions.test_naming ("snake_case" | "camelCase")
  defaultTarget: string; // targets.default (default "native")
}

const DEFAULTS = {
  testDir: "test",
  buildDir: "build",
  testPrefix: "test_",
  testNaming: "snake_case",
  defaultTarget: "native",
};

// Extract a `key: value` under a top-level section without a real YAML parser.
// Good enough for the flat scalar keys we read; falls back to defaults.
function scalar(text: string, section: string, key: string): string | undefined {
  const lines = text.split(/\r?\n/);
  let inSection = false;
  let sectionIndent = -1;
  for (const raw of lines) {
    if (!raw.trim() || raw.trim().startsWith("#")) {
      continue;
    }
    const indent = raw.length - raw.trimStart().length;
    const trimmed = raw.trim();
    if (indent === 0) {
      inSection = trimmed === `${section}:`;
      sectionIndent = inSection ? indent : -1;
      continue;
    }
    if (inSection && indent > sectionIndent) {
      const m = trimmed.match(/^([A-Za-z_]+):\s*(.+)$/);
      if (m && m[1] === key) {
        return m[2].replace(/^["']|["']$/g, "").trim();
      }
    }
  }
  return undefined;
}

export function findForgeConfig(startDir: string): ForgeConfig | undefined {
  let dir = startDir;
  // Walk up like find_config() in config.py.
  for (;;) {
    const candidate = path.join(dir, "forge.yml");
    if (fs.existsSync(candidate)) {
      const text = fs.readFileSync(candidate, "utf-8");
      return {
        root: dir,
        testDir: scalar(text, "project", "test_dir") ?? DEFAULTS.testDir,
        buildDir: scalar(text, "project", "build_dir") ?? DEFAULTS.buildDir,
        testPrefix:
          scalar(text, "conventions", "test_prefix") ?? DEFAULTS.testPrefix,
        testNaming:
          scalar(text, "conventions", "test_naming") ?? DEFAULTS.testNaming,
        defaultTarget:
          scalar(text, "targets", "default") ?? DEFAULTS.defaultTarget,
      };
    }
    const parent = path.dirname(dir);
    if (parent === dir) {
      return undefined;
    }
    dir = parent;
  }
}
