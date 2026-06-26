import * as fs from "fs";
import * as path from "path";
import * as vscode from "vscode";

import { debugUnit } from "./debug";
import {
  extractTestFns,
  isTestFile,
  unitNameFromFile,
} from "./discovery";
import { ForgeConfig, findForgeConfig } from "./forgeConfig";
import { log } from "./log";
import { crlf, resolveAgainstRoot } from "./paths";
import { runTests } from "./runner";
import { ResultsTest } from "./types";

interface UnitMeta {
  forge: ForgeConfig;
  unitName: string; // file basename minus prefix, matches RunResult.unit.name
  testFile: string; // absolute path to test_*.c
}

export function createController(
  context: vscode.ExtensionContext,
): vscode.TestController {
  const ctrl = vscode.tests.createTestController("vyperling", "Vyperling");
  context.subscriptions.push(ctrl);

  // unitItemId -> metadata needed to run/debug it.
  const unitMeta = new Map<string, UnitMeta>();

  ctrl.resolveHandler = async (item) => {
    if (!item) {
      await discoverAll(ctrl, unitMeta);
    }
  };

  ctrl.createRunProfile(
    "Run",
    vscode.TestRunProfileKind.Run,
    (req, token) => runHandler(ctrl, unitMeta, req, token, false),
    true,
  );
  ctrl.createRunProfile(
    "Debug",
    vscode.TestRunProfileKind.Debug,
    (req, token) => runHandler(ctrl, unitMeta, req, token, true),
    false,
  );

  // Re-discover when test files change.
  const watcher = vscode.workspace.createFileSystemWatcher("**/forge.yml");
  watcher.onDidCreate(() => discoverAll(ctrl, unitMeta));
  watcher.onDidChange(() => discoverAll(ctrl, unitMeta));
  context.subscriptions.push(watcher);

  void discoverAll(ctrl, unitMeta);
  return ctrl;
}

async function discoverAll(
  ctrl: vscode.TestController,
  unitMeta: Map<string, UnitMeta>,
): Promise<void> {
  ctrl.items.replace([]);
  unitMeta.clear();

  for (const folder of vscode.workspace.workspaceFolders ?? []) {
    const forge = findForgeConfig(folder.uri.fsPath);
    if (!forge) {
      continue;
    }
    const testDir = path.join(forge.root, forge.testDir);
    if (!fs.existsSync(testDir)) {
      continue;
    }
    for (const entry of fs.readdirSync(testDir)) {
      if (!isTestFile(entry, forge.testPrefix)) {
        continue;
      }
      const testFile = path.join(testDir, entry);
      const unitName = unitNameFromFile(entry, forge.testPrefix);
      addUnit(ctrl, unitMeta, forge, unitName, testFile);
    }
  }
}

function addUnit(
  ctrl: vscode.TestController,
  unitMeta: Map<string, UnitMeta>,
  forge: ForgeConfig,
  unitName: string,
  testFile: string,
): void {
  const uri = vscode.Uri.file(testFile);
  const unitId = `unit:${testFile}`;
  const unitItem = ctrl.createTestItem(unitId, unitName, uri);
  unitMeta.set(unitId, { forge, unitName, testFile });

  const text = fs.readFileSync(testFile, "utf-8");
  for (const t of extractTestFns(text, forge.testPrefix, forge.testNaming)) {
    const child = ctrl.createTestItem(`${unitId}::${t.name}`, t.name, uri);
    child.range = new vscode.Range(t.line, 0, t.line, 0);
    unitItem.children.add(child);
  }
  log(`[discover] ${unitName}: ${unitItem.children.size} test(s) in ${testFile}`);

  ctrl.items.add(unitItem);
}

function collectUnits(
  ctrl: vscode.TestController,
  unitMeta: Map<string, UnitMeta>,
  req: vscode.TestRunRequest,
): vscode.TestItem[] {
  const wanted = new Set<vscode.TestItem>();
  const include =
    req.include ?? Array.from(ctrl.items, ([, item]) => item);
  for (const item of include) {
    // A child (test fn) resolves to its parent unit; we run per-unit.
    const unit = item.parent ?? item;
    if (unitMeta.has(unit.id)) {
      wanted.add(unit);
    }
  }
  return Array.from(wanted);
}

async function runHandler(
  ctrl: vscode.TestController,
  unitMeta: Map<string, UnitMeta>,
  req: vscode.TestRunRequest,
  token: vscode.CancellationToken,
  debug: boolean,
): Promise<void> {
  const units = collectUnits(ctrl, unitMeta, req);

  if (debug) {
    // Debug runs one unit under gdb; multi-select debug picks the first.
    const meta = unitMeta.get(units[0]?.id ?? "");
    if (meta) {
      await debugUnit(meta.forge, meta.unitName, token);
    }
    return;
  }

  const run = ctrl.createTestRun(req);
  log(`[run] starting: ${units.length} unit(s)`);
  if (units.length === 0) {
    run.appendOutput(
      crlf(
        "No vyperling test units selected/discovered. " +
          "Check that a forge.yml exists and test_*.c files are present.\n",
      ),
    );
  }
  try {
    for (const unitItem of units) {
      if (token.isCancellationRequested) {
        break;
      }
      const meta = unitMeta.get(unitItem.id)!;
      markEnqueued(run, unitItem);

      const outcome = await runTests(meta.forge, meta.unitName, token);

      const resultUnit = outcome.doc?.units.find(
        (u) => u.name === meta.unitName,
      );
      const ok = !!resultUnit && !resultUnit.compile_error && !resultUnit.timed_out;

      // Always show the CLI stdout (the human-readable run report). Only show
      // stderr / spawn errors when something went wrong, to keep shell-profile
      // noise (e.g. gitstatus banners) out of successful runs.
      if (outcome.stdout.trim()) {
        run.appendOutput(crlf(outcome.stdout), undefined, unitItem);
      }
      if (!ok) {
        if (outcome.stderr.trim()) {
          run.appendOutput(crlf(outcome.stderr), undefined, unitItem);
        }
        if (outcome.error) {
          run.appendOutput(
            crlf(`Failed to launch vpl: ${outcome.error}\n`),
            undefined,
            unitItem,
          );
        }
      }

      if (!resultUnit || resultUnit.compile_error) {
        const detail =
          outcome.error
            ? `could not run vpl: ${outcome.error}`
            : resultUnit?.stderr || outcome.stderr || "compile failed";
        failAll(run, unitItem, new vscode.TestMessage(detail));
        continue;
      }
      if (resultUnit.timed_out) {
        failAll(run, unitItem, new vscode.TestMessage("test run timed out"));
        continue;
      }

      applyResults(run, meta, unitItem, resultUnit.tests);
    }
  } finally {
    run.end();
  }
}

function markEnqueued(run: vscode.TestRun, unit: vscode.TestItem): void {
  run.enqueued(unit);
  unit.children.forEach((c) => run.enqueued(c));
}

function failAll(
  run: vscode.TestRun,
  unit: vscode.TestItem,
  msg: vscode.TestMessage,
): void {
  if (unit.children.size === 0) {
    run.failed(unit, msg);
    return;
  }
  unit.children.forEach((c) => run.failed(c, msg));
}

function applyResults(
  run: vscode.TestRun,
  meta: UnitMeta,
  unit: vscode.TestItem,
  tests: ResultsTest[],
): void {
  // Index discovered children by function name for mapping.
  const byName = new Map<string, vscode.TestItem>();
  unit.children.forEach((c) => byName.set(c.label, c));

  for (const tc of tests) {
    const item = byName.get(tc.name);
    if (!item) {
      continue; // JSON test not in the discovered set (e.g. helper).
    }
    if (tc.status === "pass") {
      run.passed(item);
    } else if (tc.status === "ignore") {
      run.skipped(item);
    } else {
      const message = new vscode.TestMessage(tc.message || "assertion failed");
      // Locate the failure at file:line, resolved against the project root.
      const file = resolveAgainstRoot(meta.forge.root, tc.file);
      message.location = new vscode.Location(
        vscode.Uri.file(file),
        new vscode.Position(Math.max(0, tc.line - 1), 0),
      );
      run.failed(item, message);
    }
  }
}
