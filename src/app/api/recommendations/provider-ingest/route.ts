import { NextRequest, NextResponse } from "next/server";

import {
    fetchWithBackendAuthFallback,
    getBackendAuthContext,
    hasBackendAuthCandidate,
} from "../../_shared/backend-auth";
import { BACKEND_URL } from "@/lib/config";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
    try {
        const authContext = await getBackendAuthContext();
        if (!authContext) {
            return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
        }

        const payload = await request.json().catch(() => ({}));
        const integrationId = payload && typeof payload === "object" && "integration_id" in payload
            ? (payload as Record<string, unknown>).integration_id
            : null;
        const forceRefresh = payload && typeof payload === "object" && "force_refresh" in payload
            ? (payload as Record<string, unknown>).force_refresh
            : null;
        const body = {
            integration_id: typeof integrationId === "string" && integrationId.trim()
                ? integrationId.trim()
                : null,
            force_refresh: typeof forceRefresh === "boolean" ? forceRefresh : false,
        };
        const targetUrl = `${BACKEND_URL}/api/recommendations/provider-ingest`;

        if (!hasBackendAuthCandidate(targetUrl, authContext)) {
            return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
        }

        const response = await fetchWithBackendAuthFallback(
            fetch,
            targetUrl,
            {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(body),
                cache: "no-store",
            },
            authContext,
        );

        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            return NextResponse.json(
                { detail: data?.detail || "Failed to ingest provider recommendations" },
                { status: response.status },
            );
        }

        return NextResponse.json(data);
    } catch (error) {
        const message = error instanceof Error ? error.message : "Unknown provider ingestion error";
        return NextResponse.json(
            { detail: `Could not ingest provider recommendations: ${message}` },
            { status: 503 },
        );
    }
}
