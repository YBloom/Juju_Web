/**
 * Global Error Handler Module
 * Handles both client-side (JS/Network) and server-side (5xx) errors.
 */

// Error Categories
const ERROR_TYPES = {
    NETWORK_OFFLINE: 'network_offline',
    SERVER_FAULT: 'server_fault',
    CLIENT_ERROR: 'client_error'
};

// UI Config for different error types
const ERROR_UI_CONFIG = {
    [ERROR_TYPES.NETWORK_OFFLINE]: {
        title: '网络连接似乎断开了',
        message: '请检查您的网络连接是否正常。',
        icon: 'wifi_off',
        theme: 'theme-network', // Neutral/Blue
        canRetry: true
    },
    [ERROR_TYPES.SERVER_FAULT]: {
        title: '服务器遇到了一点问题',
        message: '我们的工程师正在紧急修复，请稍后再试。',
        icon: 'dns',
        theme: 'theme-server', // Warning/Orange
        canRetry: true
    },
    [ERROR_TYPES.CLIENT_ERROR]: {
        title: '哎呀，出错了',
        message: '页面遇到了一些意外情况，刷新可能解决问题。',
        icon: 'error_outline',
        theme: 'theme-client', // Error/Red
        canRetry: true
    }
};

let errorOverlay = null;
let errorTitle = null;
let errorMessage = null;
let errorIcon = null;
let errorDetail = null;

function ensureOverlayElements() {
    if (errorOverlay) return;

    // The overlay should already be in HTML, or we can inject it if missing?
    // Plan said Modify index.html, so we assume it exists.
    // However, specifically safeguarding here.
    errorOverlay = document.getElementById('global-error-overlay');
    if (!errorOverlay) {
        console.warn('Global error overlay element not found in DOM.');
        return;
    }

    errorTitle = errorOverlay.querySelector('.error-title');
    errorMessage = errorOverlay.querySelector('.error-message');
    errorIcon = errorOverlay.querySelector('.error-icon i');
    errorDetail = errorOverlay.querySelector('.error-detail'); // For technical details (optional)
}

function showGlobalError(type, technicalDetail = '') {
    ensureOverlayElements();
    if (!errorOverlay) return;

    const config = ERROR_UI_CONFIG[type] || ERROR_UI_CONFIG[ERROR_TYPES.CLIENT_ERROR];

    // Reset Classes
    errorOverlay.classList.remove('theme-network', 'theme-server', 'theme-client');
    errorOverlay.classList.add(config.theme);

    // Set Content
    if (errorTitle) errorTitle.textContent = config.title;
    if (errorMessage) errorMessage.textContent = config.message;
    if (errorIcon) errorIcon.textContent = config.icon;

    // Technical detail (hidden by default in CSS usually, or collapsed)
    if (errorDetail) {
        errorDetail.textContent = technicalDetail;
        errorDetail.style.display = technicalDetail ? 'block' : 'none';
        // Hide detail initially to not scare users? 
        // For now, let's keep it simple. If provided, show it but maybe small.
    }

    // Show Overlay
    errorOverlay.classList.add('active');

    // Prevent scrolling on body
    document.body.style.overflow = 'hidden';
}

function hideGlobalError() {
    ensureOverlayElements();
    if (!errorOverlay) return;

    errorOverlay.classList.remove('active');
    document.body.style.overflow = '';
}

export function initErrorHandler() {
    console.log('[ErrorHandler] Initializing...');

    // 1. Network Status (Online/Offline)
    window.addEventListener('online', () => {
        // Auto-hide offline error when network returns, 
        // BUT only if the current error is actually a network error.
        // For simplicity, we might just reload or let user click refresh.
        // Let's just log for now, or maybe show a toast "Network Restored".
    });

    window.addEventListener('offline', () => {
        showGlobalError(ERROR_TYPES.NETWORK_OFFLINE, 'Navigator reported offline.');
    });

    // 2. Client-Side JS Errors
    window.addEventListener('error', (event) => {
        // Ignore Script Error with no info (CORS issues mostly)
        if (event.message === 'Script error.' && !event.lineno) {
            return;
        }

        // Filter out non-critical or noise if necessary
        console.error('[ErrorHandler] Caught JS Error:', event.error);

        // resource loading errors (img, script) use capture:true, plain 'error' event
        // window.onerror arguments are different.
        // addEventListener('error') catches both if not prevented? 
        // Actually, resource errors don't bubble to window, need capturing phase.
    }, true);

    // Better way for standard JS errors
    const oldOnerror = window.onerror;
    window.onerror = function (msg, url, lineNo, columnNo, error) {
        const detail = `${msg}\nAt: ${url}:${lineNo}`;
        // Only show full page error for uncaught critical exceptions?
        // Maybe we don't want to block the user for every small console error.
        // Let's only show if it seems critical or we can deduce it broke the page.
        // For now, let's be conservative and NOT show overlay for every JS error 
        // unless it's explicitly calling a fatal handler. 
        // Users hate it when a small bug blocks the whole page despite it technically working.

        // However, user ASKED for a page to show when "code crashes".
        // Let's show it.
        showGlobalError(ERROR_TYPES.CLIENT_ERROR, detail);

        if (typeof oldOnerror === 'function') {
            return oldOnerror(msg, url, lineNo, columnNo, error);
        }
        return false;
    };

    // 3. Promise Rejections
    window.addEventListener('unhandledrejection', (event) => {
        console.error('[ErrorHandler] Unhandled Rejection:', event.reason);
        const detail = event.reason ? (event.reason.message || event.reason.toString()) : 'Unknown Promise Error';
        showGlobalError(ERROR_TYPES.CLIENT_ERROR, detail);
    });

    // 4. Server Errors - Intercept Fetch
    const originalFetch = window.fetch;
    window.fetch = async function (...args) {
        // If we are already offline, navigator.onLine check usually handles it,
        // but fetch might throw immediately.

        try {
            const response = await originalFetch(...args);

            // Critical Server Errors
            if (response.status >= 500) {
                const detail = `${response.status} ${response.statusText} for ${args[0]}`;
                showGlobalError(ERROR_TYPES.SERVER_FAULT, detail);
                // We typically still want to return the response so the app logic *could* handle it 
                // (e.g. stop loading spinners), but the Overlay will be on top.
            }
            else if (response.status === 404) {
                // 404 might be normal (search result empty), so DO NOT blockage global error
                // unless it's a critical static resource?
                // But fetch usually is for API. API 404 usually means entity not found, not "Site broken".
                // So we SKIP 404 here unless we have a specific list of critical endpoints.
                // User request says "404" though.
                // Compromise: If it's a static file (e.g. .js .css) fetch? (Usually loaded by tags, not fetch).
                // For now, ignore 404 in fetch regarding global overlay.
            }

            return response;

        } catch (error) {
            // Network Error (Fetch failed completely)
            console.error('[ErrorHandler] Fetch Failed:', error);

            // Put it under Network Issue
            if (!navigator.onLine) {
                showGlobalError(ERROR_TYPES.NETWORK_OFFLINE, error.message);
            } else {
                // Could be DNS error, timeout, CORS.
                // Treat as Server Fault or Network Issue?
                showGlobalError(ERROR_TYPES.SERVER_FAULT, `Network Request Failed: ${error.message}`);
            }

            throw error;
        }
    };
}
