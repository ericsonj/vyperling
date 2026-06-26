import * as vscode from "vscode";

// Single shared output channel. Open via: View -> Output -> "Vyperling".
export const output = vscode.window.createOutputChannel("Vyperling");

export function log(msg: string): void {
  output.appendLine(msg);
}
