/**
 * Centralized configuration — single source of truth for backend URL.
 * In production, PYTHON_BACKEND_URL or NEXT_PUBLIC_BACKEND_URL MUST be set.
 * Localhost fallback only allowed in development.
 */

function resolveBackendUrl(): string {
    const url = process.env.PYTHON_BACKEND_URL || process.env.NEXT_PUBLIC_BACKEND_URL;
    if (url) return url;

    if (process.env.NODE_ENV === "production") {
        throw new Error(
            "PYTHON_BACKEND_URL or NEXT_PUBLIC_BACKEND_URL must be configured in production.",
        );
    }
    return "http://127.0.0.1:8000";
}

export const BACKEND_URL = resolveBackendUrl();
