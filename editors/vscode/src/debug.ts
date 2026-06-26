import * as vscode from "vscode";

import { ForgeConfig } from "./forgeConfig";
import { ensureBinary } from "./runner";

// Launch a native test binary under gdb via the cpptools cppdbg adapter.
// Native target only this phase; QEMU `-g <port>` + gdb attach is a follow-up.
export async function debugUnit(
  forge: ForgeConfig,
  unitName: string,
  token: vscode.CancellationToken,
): Promise<void> {
  const target = vscode.workspace
    .getConfiguration("vyperling")
    .get<string>("defaultTarget", "")
    .trim();
  if (target && target !== "native") {
    vscode.window.showWarningMessage(
      `Vyperling debug supports the 'native' target only; '${target}' is configured. ` +
        `Cross-target (QEMU gdbserver) debugging is not yet implemented.`,
    );
    return;
  }

  const built = await ensureBinary(forge, unitName, token);
  if (built.error || !built.program) {
    vscode.window.showErrorMessage(
      `Vyperling: cannot debug '${unitName}': ${built.error ?? "unknown error"}`,
    );
    return;
  }
  const program = built.program;

  const folder = vscode.workspace.getWorkspaceFolder(vscode.Uri.file(forge.root));
  const config: vscode.DebugConfiguration = {
    type: "cppdbg",
    request: "launch",
    name: `Debug ${unitName}`,
    program,
    args: [],
    stopAtEntry: false,
    cwd: forge.root,
    MIMode: "gdb",
    setupCommands: [
      {
        description: "Enable pretty-printing for gdb",
        text: "-enable-pretty-printing",
        ignoreFailures: true,
      },
    ],
  };

  await vscode.debug.startDebugging(folder, config);
}
