// API utility with dynamic base URL support for both web and VS Code

import { getApiBaseUrl } from './vscode';

/**
 * Make an API request with automatic base URL handling
 * @param {string} path - API path (e.g., '/api/chat/message')
 * @param {RequestInit} options - Fetch options
 * @returns {Promise<Response>}
 */
export async function apiFetch(path, options = {}) {
    const baseUrl = getApiBaseUrl();
    const url = `${baseUrl}${path}`;
    
    return fetch(url, {
        ...options,
        headers: {
            'Content-Type': 'application/json',
            ...options.headers
        }
    });
}

/**
 * GET request
 */
export async function apiGet(path) {
    return apiFetch(path, { method: 'GET' });
}

/**
 * POST request with JSON body
 */
export async function apiPost(path, data) {
    return apiFetch(path, {
        method: 'POST',
        body: JSON.stringify(data)
    });
}

/**
 * PUT request with JSON body
 */
export async function apiPut(path, data) {
    return apiFetch(path, {
        method: 'PUT',
        body: JSON.stringify(data)
    });
}

/**
 * DELETE request
 */
export async function apiDelete(path) {
    return apiFetch(path, { method: 'DELETE' });
}

/**
 * Helper to handle streaming responses (for chat)
 */
export async function* apiStream(path, data) {
    const baseUrl = getApiBaseUrl();
    const url = `${baseUrl}${path}`;
    
    const response = await fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
    });

    if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const reader = response.body?.getReader();
    if (!reader) {
        throw new Error('No response body');
    }

    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
            if (line.startsWith('data: ')) {
                const data = line.slice(6);
                if (data === '[DONE]') {
                    return;
                }
                try {
                    yield JSON.parse(data);
                } catch {
                    // Not JSON, yield as-is
                    yield data;
                }
            }
        }
    }

    // Handle remaining buffer
    if (buffer.startsWith('data: ')) {
        const data = buffer.slice(6);
        if (data !== '[DONE]') {
            try {
                yield JSON.parse(data);
            } catch {
                yield data;
            }
        }
    }
}

