// VS Code API Bridge for webview communication

declare global {
    interface Window {
        IS_VSCODE?: boolean;
        IS_CANVAS_VIEW?: boolean;
        API_BASE_URL?: string;
        acquireVsCodeApi?: () => VSCodeApi;
    }
}

interface VSCodeApi {
    postMessage(message: any): void;
    getState(): any;
    setState(state: any): void;
}

let vscodeApi: VSCodeApi | null = null;

/**
 * Check if running inside VS Code webview
 */
export function isVSCode(): boolean {
    return typeof window !== 'undefined' && window.IS_VSCODE === true;
}

/**
 * Check if running in canvas view (full panel) vs sidebar
 */
export function isCanvasView(): boolean {
    return typeof window !== 'undefined' && window.IS_CANVAS_VIEW === true;
}

/**
 * Get the API base URL
 */
export function getApiBaseUrl(): string {
    if (typeof window !== 'undefined' && window.API_BASE_URL) {
        return window.API_BASE_URL;
    }
    // Default for web development
    return '';
}

/**
 * Get VS Code API instance (singleton)
 */
export function getVSCodeApi(): VSCodeApi | null {
    if (!isVSCode()) {
        return null;
    }

    if (!vscodeApi && window.acquireVsCodeApi) {
        vscodeApi = window.acquireVsCodeApi();
    }

    return vscodeApi;
}

/**
 * Send message to VS Code extension host
 */
export function postMessage(message: any): void {
    const api = getVSCodeApi();
    if (api) {
        api.postMessage(message);
    }
}

/**
 * Request to save files to workspace (VS Code only)
 */
export function saveFilesToWorkspace(files: Array<{path: string, content: string}>, basePath: string): void {
    postMessage({
        type: 'saveFiles',
        files,
        basePath
    });
}

/**
 * Request to open a file in VS Code (VS Code only)
 */
export function openFile(path: string): void {
    postMessage({
        type: 'openFile',
        path
    });
}

/**
 * Open canvas in a separate panel (VS Code sidebar only)
 */
export function openCanvas(): void {
    postMessage({
        type: 'openCanvas'
    });
}

/**
 * Show a message in VS Code
 */
export function showMessage(text: string, level: 'info' | 'warning' | 'error' = 'info'): void {
    if (isVSCode()) {
        postMessage({
            type: 'showMessage',
            text,
            level
        });
    } else {
        // Fallback for web
        if (level === 'error') {
            console.error(text);
        } else if (level === 'warning') {
            console.warn(text);
        } else {
            console.log(text);
        }
    }
}

/**
 * Notify extension that webview is ready
 */
export function notifyReady(): void {
    postMessage({ type: 'ready' });
}

/**
 * Listen for messages from VS Code extension host
 */
export function onMessage(handler: (message: any) => void): () => void {
    const listener = (event: MessageEvent) => {
        handler(event.data);
    };

    window.addEventListener('message', listener);

    return () => {
        window.removeEventListener('message', listener);
    };
}

/**
 * Save state to VS Code (persisted across webview lifecycle)
 */
export function saveState(state: any): void {
    const api = getVSCodeApi();
    if (api) {
        api.setState(state);
    }
}

/**
 * Get saved state from VS Code
 */
export function getState(): any {
    const api = getVSCodeApi();
    if (api) {
        return api.getState();
    }
    return null;
}

