'use server';

import {
    fetchWithBackendAuthFallback,
    getBackendAuthContext,
    hasBackendAuthCandidate,
} from "@/app/api/_shared/backend-auth";
import { BACKEND_URL } from "@/lib/config";

export async function pollScanProgress(): Promise<{
    type: string;
    percent: number;
    message: string;
    status: string;
}> {
    const authContext = await getBackendAuthContext();
    if (!authContext?.userId) {
        return { type: "idle", percent: 0, message: "Unauthorized", status: "idle" };
    }

    const scanProgressUrl = `${BACKEND_URL}/api/scan-progress`;

    if (!hasBackendAuthCandidate(scanProgressUrl, authContext)) {
        return { type: "idle", percent: 0, message: "Authentication unavailable", status: "idle" };
    }

    try {
        const res = await fetchWithBackendAuthFallback(fetch, scanProgressUrl, {
            headers: { "Content-Type": "application/json" },
            cache: 'no-store',
        }, authContext);

        if (res.ok) {
            return await res.json();
        }
    } catch {
        // Polling failed silently
    }

    return { type: "idle", percent: 0, message: "Unable to reach backend", status: "idle" };
}
