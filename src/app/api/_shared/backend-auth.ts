import { auth } from "@clerk/nextjs/server";
import {
    buildBackendAuthHeaders,
    fetchWithBackendAuthFallback,
    hasBackendAuthCandidate,
    type BackendAuthContext,
} from "./fetch-with-backend-auth-fallback";

export async function getBackendAuthContext(): Promise<BackendAuthContext | null> {
    const { userId, getToken } = await auth();
    if (!userId) {
        return null;
    }

    let token: string | null = null;
    try {
        token = await getToken();
    } catch {
        token = null;
    }

    if (!token) {
        try {
            token = await getToken({ template: "default" });
        } catch {
            token = null;
        }
    }

    return { userId, token };
}
export { buildBackendAuthHeaders, fetchWithBackendAuthFallback, hasBackendAuthCandidate };
