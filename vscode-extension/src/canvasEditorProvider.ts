import * as vscode from 'vscode';
import { ServerManager } from './serverManager';
import { getUri } from './utils';

export class CanvasEditorProvider implements vscode.WebviewPanelSerializer {
    public static readonly viewType = 'eventStorming.canvas';
    private _panel?: vscode.WebviewPanel;

    constructor(
        private readonly _extensionUri: vscode.Uri,
        private readonly _serverManager: ServerManager
    ) {}

    public async deserializeWebviewPanel(
        webviewPanel: vscode.WebviewPanel,
        state: any
    ): Promise<void> {
        this._panel = webviewPanel;
        this._setupPanel(webviewPanel);
    }

    public openCanvas(): void {
        if (this._panel) {
            // If panel exists, reveal it
            this._panel.reveal(vscode.ViewColumn.One);
            return;
        }

        // Create new panel
        this._panel = vscode.window.createWebviewPanel(
            CanvasEditorProvider.viewType,
            'Event Storming Canvas',
            vscode.ViewColumn.One,
            {
                enableScripts: true,
                retainContextWhenHidden: true,
                localResourceRoots: [
                    vscode.Uri.joinPath(this._extensionUri, 'webview', 'dist'),
                    vscode.Uri.joinPath(this._extensionUri, 'resources')
                ]
            }
        );

        this._setupPanel(this._panel);
    }

    private _setupPanel(panel: vscode.WebviewPanel): void {
        panel.webview.html = this._getHtmlForWebview(panel.webview);

        // Handle messages from the webview
        panel.webview.onDidReceiveMessage(async (message) => {
            await this._handleMessage(message, panel.webview);
        });

        // Clean up when panel is disposed
        panel.onDidDispose(() => {
            this._panel = undefined;
        });
    }

    private async _handleMessage(message: any, webview: vscode.Webview) {
        switch (message.type) {
            case 'saveFiles':
                await this._saveFilesToWorkspace(message.files, message.basePath, webview);
                break;

            case 'openFile':
                await this._openFile(message.path);
                break;

            case 'getServerStatus':
                webview.postMessage({
                    type: 'serverStatus',
                    status: this._serverManager.getStatus()
                });
                break;

            case 'getServerPort':
                const port = this._serverManager.getPort();
                webview.postMessage({
                    type: 'serverPort',
                    port: port
                });
                break;

            case 'showMessage':
                if (message.level === 'error') {
                    vscode.window.showErrorMessage(message.text);
                } else if (message.level === 'warning') {
                    vscode.window.showWarningMessage(message.text);
                } else {
                    vscode.window.showInformationMessage(message.text);
                }
                break;

            case 'ready':
                // Webview is ready, send initial config
                const config = vscode.workspace.getConfiguration('eventStorming');
                webview.postMessage({
                    type: 'config',
                    apiBaseUrl: `http://localhost:${config.get('serverPort', 8000)}`,
                    isVSCode: true
                });
                break;
        }
    }

    private async _saveFilesToWorkspace(
        files: Array<{path: string, content: string}>, 
        basePath: string,
        webview: vscode.Webview
    ) {
        const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
        if (!workspaceFolder) {
            vscode.window.showErrorMessage('No workspace folder open. Please open a folder first.');
            return;
        }

        const baseUri = vscode.Uri.joinPath(workspaceFolder.uri, basePath);

        try {
            // Create base directory
            await vscode.workspace.fs.createDirectory(baseUri);

            // Write each file
            for (const file of files) {
                const filePath = vscode.Uri.joinPath(baseUri, file.path);
                
                // Create parent directories if needed
                const parentDir = vscode.Uri.joinPath(filePath, '..');
                try {
                    await vscode.workspace.fs.createDirectory(parentDir);
                } catch {
                    // Directory might already exist
                }

                // Write file content
                const content = new TextEncoder().encode(file.content);
                await vscode.workspace.fs.writeFile(filePath, content);
            }

            const selection = await vscode.window.showInformationMessage(
                `PRD files created in ${basePath}/`,
                'Open Folder',
                'Open README'
            );

            if (selection === 'Open Folder') {
                vscode.commands.executeCommand('revealInExplorer', baseUri);
            } else if (selection === 'Open README') {
                const readmePath = vscode.Uri.joinPath(baseUri, 'CLAUDE.md');
                try {
                    await vscode.workspace.fs.stat(readmePath);
                    vscode.window.showTextDocument(readmePath);
                } catch {
                    vscode.window.showWarningMessage('No CLAUDE.md found');
                }
            }

            // Notify webview of success
            webview.postMessage({
                type: 'filesSaved',
                success: true,
                basePath: basePath
            });
        } catch (error) {
            vscode.window.showErrorMessage(`Failed to save files: ${error}`);
            webview.postMessage({
                type: 'filesSaved',
                success: false,
                error: String(error)
            });
        }
    }

    private async _openFile(filePath: string) {
        const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
        if (!workspaceFolder) {
            return;
        }

        const uri = vscode.Uri.joinPath(workspaceFolder.uri, filePath);
        try {
            await vscode.window.showTextDocument(uri);
        } catch (error) {
            vscode.window.showErrorMessage(`Failed to open file: ${filePath}`);
        }
    }

    private _getHtmlForWebview(webview: vscode.Webview): string {
        // Get URIs for webview resources
        const scriptUri = getUri(webview, this._extensionUri, ['webview', 'dist', 'assets', 'index.js']);
        const styleUri = getUri(webview, this._extensionUri, ['webview', 'dist', 'assets', 'index.css']);
        
        // Use actual port from server manager
        const serverPort = this._serverManager.getPort();
        
        // Allow a range of ports in CSP (8001-8020) for auto-detection
        const portRange = Array.from({length: 20}, (_, i) => 8001 + i);
        const connectSrc = portRange.map(p => `http://localhost:${p} http://127.0.0.1:${p} ws://localhost:${p} ws://127.0.0.1:${p}`).join(' ');

        return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${webview.cspSource} 'unsafe-inline'; script-src ${webview.cspSource} 'unsafe-inline' 'unsafe-eval'; connect-src ${connectSrc}; img-src ${webview.cspSource} https: data:; font-src ${webview.cspSource} data:;">
    <link rel="stylesheet" href="${styleUri}">
    <title>Event Storming Canvas</title>
    <script>
        window.IS_VSCODE = true;
        window.IS_CANVAS_VIEW = true;
        window.API_BASE_URL = 'http://localhost:${serverPort}';
        
        // Listen for port change messages from extension
        window.addEventListener('message', function(event) {
            const message = event.data;
            if (message.type === 'portChanged') {
                window.API_BASE_URL = 'http://localhost:' + message.port;
                console.log('API port changed to:', message.port);
            }
        });
    </script>
</head>
<body>
    <div id="app"></div>
    <script type="module" src="${scriptUri}"></script>
</body>
</html>`;
    }
}

