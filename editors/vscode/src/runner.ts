import { spawn } from "child_process";
import * as fs from "fs";
import * as os from "os";
import * as path from "path";
import * as vscode from "vscode";

import { ForgeConfig } from "./forgeConfig";
import { log } from "./log";
import { buildSubdir, resolveAgainstRoot } from "./paths";
import { ResultsDoc } from "./types";

export interface RunOutcome {
  doc: ResultsDoc | null;
  exitCode: number;
  stdout: string;
  stderr: string;
  error?: string; // spawn-level failure (e.g. vpl not found)
}

function shellQuote(s: string): string {
  return `'${s.replace(/'/g, "'\\''")}'`;
}

function cfg<T>(key: string, fallback: T): T {
  return vscode.workspace.getConfiguration("vyperling").get<T>(key, fallback);
}

export function resolveTarget(forge: ForgeConfig): string {
  const configured = cfg<string>("defaultTarget", "").trim();
  return configured || forge.defaultTarget;
}

// Run `vpl test --output json [-k name]` in the project root and read back the
// results.json it writes to build/<target>/results.json.
export async function runTests(
  forge: ForgeConfig,
  filter: string | undefined,
  token: vscode.CancellationToken,
  debug = false,
): Promise<RunOutcome> {
  const cliPath = cfg<string>("cliPath", "vpl");
  const jobs = cfg<number>("jobs", 4);
  const target = resolveTarget(forge);

  const args = ["test", "--target", target, "--output", "json", "-j", String(jobs)];
  if (filter) {
    args.push("-k", filter);
  }
  // --debug builds with -g -O0 into build/<target>-debug so a debugger can map
  // source lines; the optimised build's cache is left untouched.
  if (debug) {
    args.push("--debug");
  }
  const subdir = buildSubdir(target, debug);

  // GUI-launched VS Code does NOT inherit a login-shell PATH, so a bare
  // spawn("vpl") fails with ENOENT when vpl lives under nvm/poetry/venv.
  // Run the command through the user's shell so their profile (PATH, nvm,
  // virtualenv) is sourced, exactly like a real terminal. The flags are
  // configurable because interactive shells (-i) may load prompt plugins
  // (powerlevel10k/gitstatus) that emit harmless noise; -lc is quieter but
  // some setups put PATH only in an interactive rc.
  const cmdLine = [cliPath, ...args].map(shellQuote).join(" ");
  const shell = cfg<string>("shellPath", "") || process.env.SHELL || "/bin/sh";
  const shellArgs = cfg<string[]>("shellArgs", ["-lic"]);
  const useLoginShell = process.platform !== "win32";

  const resultsPath = path.join(forge.root, forge.buildDir, subdir, "results.json");
  // Remove a stale results file so we never map a previous run's output.
  try {
    fs.rmSync(resultsPath, { force: true });
  } catch {
    /* ignore */
  }

  log(`[run] cwd=${forge.root}`);
  log(
    `[run] ${useLoginShell ? `${shell} ${shellArgs.join(" ")}` : "spawn"}: ${cmdLine}`,
  );

  const child = useLoginShell
    ? spawn(shell, [...shellArgs, cmdLine], { cwd: forge.root })
    : spawn(cliPath, args, { cwd: forge.root, shell: true });
  token.onCancellationRequested(() => child.kill());

  let stdout = "";
  let stderr = "";
  let error: string | undefined;
  child.stdout.on("data", (d) => (stdout += d.toString()));
  child.stderr.on("data", (d) => (stderr += d.toString()));

  const exitCode: number = await new Promise((resolve) => {
    child.on("close", (code) => resolve(code ?? -1));
    child.on("error", (err) => {
      error = err.message;
      resolve(-1);
    });
  });

  log(`[run] exit=${exitCode}`);
  if (stdout.trim()) {
    log(`[run] stdout:${os.EOL}${stdout.trim()}`);
  }
  if (stderr.trim()) {
    log(`[run] stderr:${os.EOL}${stderr.trim()}`);
  }
  if (error) {
    log(`[run] spawn error: ${error}`);
  }

  let doc: ResultsDoc | null = null;
  try {
    if (fs.existsSync(resultsPath)) {
      doc = JSON.parse(fs.readFileSync(resultsPath, "utf-8")) as ResultsDoc;
      log(`[run] parsed ${resultsPath} (${doc.units.length} units)`);
    } else {
      log(`[run] results file not found: ${resultsPath}`);
    }
  } catch (e) {
    log(`[run] failed to parse results.json: ${(e as Error).message}`);
    doc = null;
  }

  return { doc, exitCode, stdout, stderr, error };
}

export interface BuiltBinary {
  program: string; // absolute path to the debug binary
  error?: string; // human-readable failure reason
}

// Build a unit with debug info (-g -O0) and resolve its binary path. Always
// builds in debug mode so breakpoints bind; uses build/<target>-debug.
export async function ensureBinary(
  forge: ForgeConfig,
  unitName: string,
  token: vscode.CancellationToken,
): Promise<BuiltBinary> {
  const outcome = await runTests(forge, unitName, token, /* debug */ true);
  if (outcome.error) {
    return { program: "", error: `could not run vpl: ${outcome.error}` };
  }
  const unit = outcome.doc?.units.find((u) => u.name === unitName);
  if (!unit) {
    return { program: "", error: `unit '${unitName}' not found in results` };
  }
  if (unit.compile_error || !unit.binary) {
    return {
      program: "",
      error: unit.stderr || "debug build failed (no binary produced)",
    };
  }
  // binary path in JSON is relative to the project root.
  const program = resolveAgainstRoot(forge.root, unit.binary);
  return { program };
}
