import {
    fetchWithBackendAuthFallback,
    getBackendAuthContext,
    hasBackendAuthCandidate,
} from "../../_shared/backend-auth";
import { BACKEND_URL } from "@/lib/config";

export const runtime = "nodejs";

export async function GET() {
    let authContext: Awaited<ReturnType<typeof getBackendAuthContext>> = null;

    try {
        authContext = await getBackendAuthContext();
    } catch (error) {
        const message = error instanceof Error ? error.message : "unknown auth error";
        console.error("Agent summary proxy auth error:", message);
    }

    if (!authContext?.userId) {
        return new Response(
            JSON.stringify({ error: "Unauthorized" }),
            { status: 401, headers: { "Content-Type": "application/json" } }
        );
    }

    const summaryUrl = `${BACKEND_URL}/api/agent/summary`;

    try {
        if (!hasBackendAuthCandidate(summaryUrl, authContext)) {
            return new Response(
                JSON.stringify({ error: "Unauthorized" }),
                { status: 401, headers: { "Content-Type": "application/json" } }
            );
        }

        const backendRes = await fetchWithBackendAuthFallback(fetch, summaryUrl, {
            method: "GET",
            cache: "no-store",
        }, authContext);

        const text = await backendRes.text();
        return new Response(text, {
            status: backendRes.status,
            headers: { "Content-Type": backendRes.headers.get("Content-Type") || "application/json" },
        });
    } catch (error) {
        console.error("Agent summary proxy error:", error);
        return new Response(
            JSON.stringify({ error: "Failed to load agent summary" }),
            { status: 502, headers: { "Content-Type": "application/json" } }
        );
    }
}
