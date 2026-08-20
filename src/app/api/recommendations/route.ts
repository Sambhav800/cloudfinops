import { NextRequest, NextResponse } from "next/server";

import {
    fetchWithBackendAuthFallback,
    getBackendAuthContext,
    hasBackendAuthCandidate,
} from "../_shared/backend-auth";
import { BACKEND_URL } from "@/lib/config";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
    try {
        const authContext = await getBackendAuthContext();
        if (!authContext) {
            return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
        }

        const targetUrl = new URL(`${BACKEND_URL}/api/recommendations`);
        const integrationId = request.nextUrl.searchParams.get("integration_id")?.trim();
        const state = request.nextUrl.searchParams.get("state")?.trim();

        if (integrationId) {
            targetUrl.searchParams.set("integration_id", integrationId);
        }
        if (state) {
            targetUrl.searchParams.set("state", state);
        }

        if (!hasBackendAuthCandidate(targetUrl.toString(), authContext)) {
            return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
        }

        const response = await fetchWithBackendAuthFallback(
            fetch,
            targetUrl.toString(),
            {
                method: "GET",
                cache: "no-store",
            },
            authContext,
        );

        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            return NextResponse.json(
                { detail: data?.detail || "Failed to load recommendations" },
                { status: response.status },
            );
        }

        return NextResponse.json(data);
    } catch (error) {
        const message = error instanceof Error ? error.message : "Unknown recommendations error";
        return NextResponse.json(
            { detail: `Could not reach the recommendations service: ${message}` },
            { status: 503 },
        );
    }
}
