import { NextRequest, NextResponse } from "next/server";

import {
    fetchWithBackendAuthFallback,
    getBackendAuthContext,
    hasBackendAuthCandidate,
} from "../../_shared/backend-auth";
import { BACKEND_URL } from "@/lib/config";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
    try {
        const authContext = await getBackendAuthContext();
        if (!authContext) {
            return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
        }

        const backendUrl = new URL(`${BACKEND_URL}/api/finance/commitment-recommendation`);
        const integrationId = request.nextUrl.searchParams.get("integration_id");
        if (integrationId) {
            backendUrl.searchParams.set("integration_id", integrationId);
        }

        const targetUrl = backendUrl.toString();
        if (!hasBackendAuthCandidate(targetUrl, authContext)) {
            return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
        }

        const response = await fetchWithBackendAuthFallback(fetch, targetUrl, {
            method: "GET",
            cache: "no-store",
        }, authContext);

        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            return NextResponse.json(
                { detail: data?.detail || "Failed to load commitment recommendation" },
                { status: response.status },
            );
        }

        return NextResponse.json(data);
    } catch (error) {
        const message = error instanceof Error ? error.message : "Unknown optimizer error";
        return NextResponse.json(
            { detail: `Could not reach the optimizer service: ${message}` },
            { status: 503 },
        );
    }
}
