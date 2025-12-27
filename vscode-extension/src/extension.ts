import * as vscode from 'vscode';
import { CanvasEditorProvider } from './canvasEditorProvider';
import { ServerManager } from './serverManager';

let serverManager: ServerManager | undefined;

// Empty tree data provider for welcome view
class EmptyTreeDataProvider implements vscode.TreeDataProvider<void> {
    getTreeItem(): vscode.TreeItem {
        throw new Error('No items');
    }
    getChildren(): void[] {
        return []; // Empty - shows viewsWelcome content
    }
}

export async function activate(context: vscode.ExtensionContext) {
    console.log('Event Storming Navigator is now active!');

    // Initialize server manager
    serverManager = new ServerManager(context);

    // Auto-start server if configured
    const config = vscode.workspace.getConfiguration('eventStorming');
    if (config.get('autoStartServer', true)) {
        try {
            await serverManager.start();
        } catch (error) {
            vscode.window.showWarningMessage(
                `Failed to auto-start backend server: ${error}. You can start it manually via command palette.`
            );
        }
    }

    // Register empty tree view for welcome content
    context.subscriptions.push(
        vscode.window.createTreeView('eventStorming.welcome', {
            treeDataProvider: new EmptyTreeDataProvider()
        })
    );

    // Register canvas editor provider (for full-screen canvas)
    const canvasEditorProvider = new CanvasEditorProvider(context.extensionUri, serverManager);
    context.subscriptions.push(
        vscode.window.registerWebviewPanelSerializer('eventStorming.canvas', canvasEditorProvider)
    );

    // Register commands
    context.subscriptions.push(
        vscode.commands.registerCommand('eventStorming.openCanvas', () => {
            canvasEditorProvider.openCanvas();
        })
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('eventStorming.startServer', async () => {
            try {
                await serverManager?.start();
                vscode.window.showInformationMessage('Backend server started successfully');
            } catch (error) {
                vscode.window.showErrorMessage(`Failed to start server: ${error}`);
            }
        })
    );

    context.subscriptions.push(
        vscode.commands.registerCommand('eventStorming.stopServer', () => {
            serverManager?.stop();
            vscode.window.showInformationMessage('Backend server stopped');
        })
    );
}

export function deactivate() {
    // Stop server on deactivation
    serverManager?.stop();
}

