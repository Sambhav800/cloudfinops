import { NextRequest } from "next/server";

import {
    fetchWithBackendAuthFallback,
    getBackendAuthContext,
    hasBackendAuthCandidate,
} from "../_shared/backend-auth";
import { BACKEND_URL } from "@/lib/config";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
    let authContext: Awaited<ReturnType<typeof getBackendAuthContext>> = null;

    try {
        authContext = await getBackendAuthContext();
    } catch (error) {
        const message = error instanceof Error ? error.message : "unknown auth error";
        console.error("Notifications proxy auth error:", message);
    }

    if (!authContext?.userId) {
        return new Response(
            JSON.stringify({ detail: "Unauthorized" }),
            { status: 401, headers: { "Content-Type": "application/json" } },
        );
    }

    try {
        const backendUrl = new URL(`${BACKEND_URL}/api/notifications`);
        const status = request.nextUrl.searchParams.get("status");
        if (status) {
            backendUrl.searchParams.set("status", status);
        }

        if (!hasBackendAuthCandidate(backendUrl.toString(), authContext)) {
            return new Response(
                JSON.stringify({ detail: "Unauthorized" }),
                { status: 401, headers: { "Content-Type": "application/json" } },
            );
        }

        const response = await fetchWithBackendAuthFallback(
            fetch,
            backendUrl.toString(),
            {
                method: "GET",
                cache: "no-store",
            },
            authContext,
        );

        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            return new Response(
                JSON.stringify({ detail: data?.detail || "Failed to load notifications" }),
                {
                    status: response.status,
                    headers: { "Content-Type": "application/json" },
                },
            );
        }

        return new Response(JSON.stringify(data), {
            status: 200,
            headers: { "Content-Type": "application/json" },
        });
    } catch (error) {
        const message = error instanceof Error ? error.message : "Unknown notifications error";
        return new Response(
            JSON.stringify({ detail: `Could not load notifications: ${message}` }),
            { status: 503, headers: { "Content-Type": "application/json" } },
        );
    }
}
