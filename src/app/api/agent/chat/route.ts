import { NextRequest } from "next/server";

import {
    fetchWithBackendAuthFallback,
    getBackendAuthContext,
    hasBackendAuthCandidate,
} from "../../_shared/backend-auth";
import { BACKEND_URL } from "@/lib/config";

export const runtime = "nodejs";

export async function POST(req: NextRequest) {
    let authContext: Awaited<ReturnType<typeof getBackendAuthContext>> = null;

    try {
        authContext = await getBackendAuthContext();
    } catch (error) {
        const message = error instanceof Error ? error.message : "unknown auth error";
        console.error("Chat proxy auth error:", message);
    }

    if (!authContext?.userId) {
        return new Response(
            JSON.stringify({ error: "Unauthorized" }),
            { status: 401, headers: { "Content-Type": "application/json" } }
        );
    }

    let token = authContext.token;
    if (!token) {
        const forwardedAuth = req.headers.get("authorization");
        if (forwardedAuth?.startsWith("Bearer ")) {
            token = forwardedAuth.slice("Bearer ".length).trim() || null;
        }
    }

    let body: unknown = null;
    try {
        body = await req.json();
    } catch {
        return new Response(
            JSON.stringify({ error: "Invalid JSON payload" }),
            { status: 400, headers: { "Content-Type": "application/json" } }
        );
    }

    const chatUrl = `${BACKEND_URL}/api/agent/chat`;
    const requestAuthContext = {
        userId: authContext.userId,
        token,
    };

    try {
        if (!hasBackendAuthCandidate(chatUrl, requestAuthContext)) {
            return new Response(
                JSON.stringify({ error: "Unauthorized" }),
                { status: 401, headers: { "Content-Type": "application/json" } }
            );
        }

        const backendRes = await fetchWithBackendAuthFallback(fetch, chatUrl, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
        }, requestAuthContext);

        if (!backendRes.ok) {
            const errorText = await backendRes.text();
            return new Response(errorText, {
                status: backendRes.status,
                headers: { "Content-Type": "text/plain" },
            });
        }

        // Stream the SSE response through to the client
        return new Response(backendRes.body, {
            status: 200,
            headers: {
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache, no-transform",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        });
    } catch (e) {
        console.error("Chat proxy error:", e);
        return new Response(
            `data: ${JSON.stringify({ type: "error", content: "Failed to reach AI backend." })}\n\n`,
            {
                status: 200,
                headers: { "Content-Type": "text/event-stream" },
            }
        );
    }
}
