import * as vscode from "vscode";

import { output } from "./log";

// Activity Bar panel. The tree is always empty on purpose: VS Code shows the
// view's welcome content (package.json "viewsWelcome") only for empty trees,
// and that content holds the panel's actions.
export function registerPanel(context: vscode.ExtensionContext): void {
  const empty: vscode.TreeDataProvider<never> = {
    getTreeItem: (item) => item,
    getChildren: () => [],
  };
  context.subscriptions.push(
    vscode.window.registerTreeDataProvider("vyperling.home", empty),
    vscode.commands.registerCommand("vyperling.showOutput", () => output.show()),
  );
  // Opening the panel activates the extension in any workspace, so pick the
  // welcome text by whether this one is a vyperling project.
  void vscode.workspace
    .findFiles("**/forge.yml", "**/node_modules/**", 1)
    .then((files) =>
      vscode.commands.executeCommand("setContext", "vyperling.hasForge", files.length > 0),
    );
}
