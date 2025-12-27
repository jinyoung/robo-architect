import * as vscode from 'vscode';
import { ServerManager } from './serverManager';
import { getNonce, getUri } from './utils';

export class SidebarProvider implements vscode.WebviewViewProvider {
    public static readonly viewType = 'eventStorming.sidebar';
    private _view?: vscode.WebviewView;
    private _currentPort: number;

    constructor(
        private readonly _extensionUri: vscode.Uri,
        private readonly _serverManager: ServerManager
    ) {
        this._currentPort = this._serverManager.getPort();
        
        // Listen for port changes
        this._serverManager.onPortChanged((newPort) => {
            this._currentPort = newPort;
            // Update webview with new port
            if (this._view) {
                this._view.webview.postMessage({
                    type: 'portChanged',
                    port: newPort
                });
            }
        });
    }

    public resolveWebviewView(
        webviewView: vscode.WebviewView,
        context: vscode.WebviewViewResolveContext,
        _token: vscode.CancellationToken
    ) {
        this._view = webviewView;
        
        // Get the current port from server manager
        this._currentPort = this._serverManager.getPort();

        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [
                vscode.Uri.joinPath(this._extensionUri, 'webview', 'dist'),
                vscode.Uri.joinPath(this._extensionUri, 'resources')
            ]
        };

        webviewView.webview.html = this._getHtmlForWebview(webviewView.webview);

        // Handle messages from the webview
        webviewView.webview.onDidReceiveMessage(async (message) => {
            await this._handleMessage(message, webviewView.webview);
        });
    }

    private async _handleMessage(message: any, webview: vscode.Webview) {
        switch (message.type) {
            case 'openCanvas':
                vscode.commands.executeCommand('eventStorming.openCanvas');
                break;

            case 'saveFiles':
                await this._saveFilesToWorkspace(message.files, message.basePath);
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

    private async _saveFilesToWorkspace(files: Array<{path: string, content: string}>, basePath: string) {
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
                const readmePath = vscode.Uri.joinPath(baseUri, 'README.md');
                try {
                    await vscode.workspace.fs.stat(readmePath);
                    vscode.window.showTextDocument(readmePath);
                } catch {
                    // Try CLAUDE.md if README doesn't exist
                    const claudePath = vscode.Uri.joinPath(baseUri, 'CLAUDE.md');
                    try {
                        await vscode.workspace.fs.stat(claudePath);
                        vscode.window.showTextDocument(claudePath);
                    } catch {
                        vscode.window.showWarningMessage('No README.md or CLAUDE.md found');
                    }
                }
            }

            // Notify webview of success
            this._view?.webview.postMessage({
                type: 'filesSaved',
                success: true,
                basePath: basePath
            });
        } catch (error) {
            vscode.window.showErrorMessage(`Failed to save files: ${error}`);
            this._view?.webview.postMessage({
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
        const nonce = getNonce();
        
        // Get URIs for webview resources
        const scriptUri = getUri(webview, this._extensionUri, ['webview', 'dist', 'assets', 'index.js']);
        const styleUri = getUri(webview, this._extensionUri, ['webview', 'dist', 'assets', 'index.css']);
        
        // Use the actual port from server manager
        const serverPort = this._currentPort;
        
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
    <title>Event Storming Navigator</title>
    <script>
        window.IS_VSCODE = true;
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

    public postMessage(message: any) {
        this._view?.webview.postMessage(message);
    }
}

