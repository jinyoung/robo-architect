// VS Code API Bridge for webview communication

let vscodeApi = null;

/**
 * Check if running inside VS Code webview
 */
export function isVSCode() {
    return typeof window !== 'undefined' && window.IS_VSCODE === true;
}

/**
 * Check if running in canvas view (full panel) vs sidebar
 */
export function isCanvasView() {
    return typeof window !== 'undefined' && window.IS_CANVAS_VIEW === true;
}

/**
 * Get the API base URL
 */
export function getApiBaseUrl() {
    if (typeof window !== 'undefined' && window.API_BASE_URL) {
        return window.API_BASE_URL;
    }
    // Default for web development
    return '';
}

/**
 * Get VS Code API instance (singleton)
 */
export function getVSCodeApi() {
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
export function postMessage(message) {
    const api = getVSCodeApi();
    if (api) {
        api.postMessage(message);
    }
}

/**
 * Request to save files to workspace (VS Code only)
 */
export function saveFilesToWorkspace(files, basePath) {
    postMessage({
        type: 'saveFiles',
        files,
        basePath
    });
}

/**
 * Request to open a file in VS Code (VS Code only)
 */
export function openFile(path) {
    postMessage({
        type: 'openFile',
        path
    });
}

/**
 * Open canvas in a separate panel (VS Code sidebar only)
 */
export function openCanvas() {
    postMessage({
        type: 'openCanvas'
    });
}

/**
 * Show a message in VS Code
 */
export function showMessage(text, level = 'info') {
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
export function notifyReady() {
    postMessage({ type: 'ready' });
}

/**
 * Listen for messages from VS Code extension host
 */
export function onMessage(handler) {
    const listener = (event) => {
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
export function saveState(state) {
    const api = getVSCodeApi();
    if (api) {
        api.setState(state);
    }
}

/**
 * Get saved state from VS Code
 */
export function getState() {
    const api = getVSCodeApi();
    if (api) {
        return api.getState();
    }
    return null;
}

