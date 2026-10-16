import * as vscode from "vscode";

import { registerPanel } from "./panel";
import { createController } from "./testController";

export function activate(context: vscode.ExtensionContext): void {
  createController(context);
  registerPanel(context);
}

export function deactivate(): void {
  // TestController is disposed via context.subscriptions.
}
