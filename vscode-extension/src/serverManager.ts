import * as vscode from 'vscode';
import * as path from 'path';
import { spawn, ChildProcess } from 'child_process';
import treeKill from 'tree-kill';

export type ServerStatus = 'stopped' | 'starting' | 'running' | 'error';

export class ServerManager {
    private _process: ChildProcess | null = null;
    private _status: ServerStatus = 'stopped';
    private _outputChannel: vscode.OutputChannel;
    private _port: number;
    private _basePort: number;
    private _maxPortAttempts: number = 20;
    private _extensionPath: string;
    private _onPortChanged: vscode.EventEmitter<number> = new vscode.EventEmitter<number>();
    public readonly onPortChanged: vscode.Event<number> = this._onPortChanged.event;

    constructor(context: vscode.ExtensionContext) {
        this._extensionPath = context.extensionPath;
        this._outputChannel = vscode.window.createOutputChannel('Event Storming Server');
        
        const config = vscode.workspace.getConfiguration('eventStorming');
        this._basePort = config.get('serverPort', 8001);
        this._port = this._basePort;
    }

    public getStatus(): ServerStatus {
        return this._status;
    }

    public getPort(): number {
        return this._port;
    }

    public async start(): Promise<void> {
        if (this._status === 'running' || this._status === 'starting') {
            this._outputChannel.appendLine('Server is already running or starting');
            return;
        }

        this._status = 'starting';
        this._outputChannel.show(true);
        this._outputChannel.appendLine('Starting backend server...');

        // Try ports from basePort to basePort + maxAttempts
        for (let attempt = 0; attempt < this._maxPortAttempts; attempt++) {
            const port = this._basePort + attempt;
            
            try {
                await this._tryStartOnPort(port);
                // If successful, we're done
                this._port = port;
                this._onPortChanged.fire(this._port);
                return;
            } catch (error: any) {
                const errorMessage = error?.message || String(error);
                
                // Check if it's a port-in-use error
                if (errorMessage.includes('Address already in use') || 
                    errorMessage.includes('EADDRINUSE') ||
                    errorMessage.includes('Errno 48')) {
                    this._outputChannel.appendLine(`Port ${port} is in use, trying ${port + 1}...`);
                    continue;
                }
                
                // For other errors, stop trying
                this._status = 'error';
                this._outputChannel.appendLine(`Failed to start server: ${errorMessage}`);
                throw error;
            }
        }
        
        // All ports exhausted
        this._status = 'error';
        const errorMsg = `No available port found in range ${this._basePort}-${this._basePort + this._maxPortAttempts - 1}`;
        this._outputChannel.appendLine(errorMsg);
        throw new Error(errorMsg);
    }

    private async _tryStartOnPort(port: number): Promise<void> {
        const pythonPath = await this._findPython();
        const serverPath = path.join(this._extensionPath, 'server');

        this._outputChannel.appendLine(`Trying port ${port}...`);
        this._outputChannel.appendLine(`Python: ${pythonPath}`);
        this._outputChannel.appendLine(`Server path: ${serverPath}`);

        // Check if server directory exists
        const fs = require('fs');
        if (!fs.existsSync(serverPath)) {
            throw new Error(`Server directory not found: ${serverPath}`);
        }

        return new Promise<void>((resolve, reject) => {
            // Start the uvicorn server
            this._process = spawn(pythonPath, [
                '-m', 'uvicorn',
                'api.main:app',
                '--host', '0.0.0.0',
                '--port', port.toString(),
                '--reload'
            ], {
                cwd: serverPath,
                env: {
                    ...process.env,
                    PYTHONPATH: serverPath
                }
            });

            let startupOutput = '';
            let resolved = false;
            
            const onSuccess = () => {
                if (!resolved) {
                    resolved = true;
                    this._status = 'running';
                    this._port = port;
                    this._outputChannel.appendLine(`✓ Server is ready on port ${port}`);
                    vscode.window.showInformationMessage(`Event Storming server started on port ${port}`);
                    resolve();
                }
            };

            const onFailure = (error: Error) => {
                if (!resolved) {
                    resolved = true;
                    this._process = null;
                    this._status = 'stopped';
                    reject(error);
                }
            };

            // Set a timeout for startup
            const timeout = setTimeout(() => {
                if (!resolved) {
                    // Check if we got an address in use error
                    if (startupOutput.includes('Address already in use') || 
                        startupOutput.includes('Errno 48')) {
                        onFailure(new Error('Address already in use'));
                    } else if (this._status === 'starting') {
                        // Assume it's running if no error after timeout
                        onSuccess();
                    }
                }
            }, 3000);

            this._process.stdout?.on('data', (data) => {
                const output = data.toString();
                startupOutput += output;
                this._outputChannel.appendLine(output);
                
                if (output.includes('Uvicorn running') || output.includes('Application startup complete')) {
                    clearTimeout(timeout);
                    onSuccess();
                }
            });

            this._process.stderr?.on('data', (data) => {
                const output = data.toString();
                startupOutput += output;
                this._outputChannel.appendLine(output);
                
                // Check for address in use error
                if (output.includes('Address already in use') || output.includes('Errno 48')) {
                    clearTimeout(timeout);
                    // Kill the process if it's still running
                    if (this._process?.pid) {
                        treeKill(this._process.pid, 'SIGTERM');
                    }
                    onFailure(new Error('Address already in use'));
                    return;
                }
                
                // Uvicorn logs to stderr
                if (output.includes('Uvicorn running') || output.includes('Application startup complete')) {
                    clearTimeout(timeout);
                    onSuccess();
                }
            });

            this._process.on('error', (error) => {
                clearTimeout(timeout);
                this._outputChannel.appendLine(`Process error: ${error.message}`);
                onFailure(error);
            });

            this._process.on('exit', (code) => {
                clearTimeout(timeout);
                if (!resolved) {
                    if (code !== 0) {
                        // Check if it was an address in use error
                        if (startupOutput.includes('Address already in use') || 
                            startupOutput.includes('Errno 48')) {
                            onFailure(new Error('Address already in use'));
                        } else {
                            onFailure(new Error(`Server exited with code ${code}`));
                        }
                    }
                }
                
                if (resolved && this._status === 'running') {
                    this._outputChannel.appendLine(`Server exited with code ${code}`);
                    this._status = 'stopped';
                    this._process = null;
                }
            });
        });
    }

    public stop(): void {
        if (this._process) {
            this._outputChannel.appendLine('Stopping server...');
            
            const pid = this._process.pid;
            if (pid) {
                treeKill(pid, 'SIGTERM', (err) => {
                    if (err) {
                        this._outputChannel.appendLine(`Error stopping server: ${err}`);
                        treeKill(pid, 'SIGKILL');
                    }
                });
            }
            
            this._process = null;
            this._status = 'stopped';
            this._outputChannel.appendLine('Server stopped');
        }
    }

    private async _findPython(): Promise<string> {
        const config = vscode.workspace.getConfiguration('eventStorming');
        const configuredPath = config.get<string>('pythonPath');
        
        if (configuredPath && configuredPath.trim()) {
            return configuredPath;
        }

        // Try to get Python from VS Code Python extension
        const pythonExtension = vscode.extensions.getExtension('ms-python.python');
        if (pythonExtension) {
            if (!pythonExtension.isActive) {
                await pythonExtension.activate();
            }
            
            const pythonApi = pythonExtension.exports;
            if (pythonApi) {
                try {
                    const interpreter = await pythonApi.settings.getExecutionDetails(
                        vscode.workspace.workspaceFolders?.[0]?.uri
                    );
                    if (interpreter?.execCommand?.[0]) {
                        return interpreter.execCommand[0];
                    }
                } catch {
                    // Fall through to default detection
                }
            }
        }

        // Try common Python paths
        const { execSync } = require('child_process');
        const candidates = ['python3', 'python', 'py'];
        
        for (const candidate of candidates) {
            try {
                execSync(`${candidate} --version`, { stdio: 'ignore' });
                return candidate;
            } catch {
                // Continue to next candidate
            }
        }

        throw new Error('Python not found. Please install Python or configure the path in settings.');
    }

    public dispose(): void {
        this.stop();
        this._outputChannel.dispose();
    }
}
