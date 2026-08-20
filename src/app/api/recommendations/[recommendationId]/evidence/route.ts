import { NextRequest, NextResponse } from "next/server";

import {
    fetchWithBackendAuthFallback,
    getBackendAuthContext,
    hasBackendAuthCandidate,
} from "../../../_shared/backend-auth";
import { BACKEND_URL } from "@/lib/config";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type RouteContext = {
    params: Promise<{
        recommendationId: string;
    }>;
};

export async function GET(_request: NextRequest, context: RouteContext) {
    try {
        const authContext = await getBackendAuthContext();
        if (!authContext) {
            return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
        }

        const { recommendationId } = await context.params;
        const normalizedId = typeof recommendationId === "string" ? recommendationId.trim() : "";
        if (!normalizedId) {
            return NextResponse.json({ detail: "recommendationId is required" }, { status: 400 });
        }

        const targetUrl = `${BACKEND_URL}/api/recommendations/${encodeURIComponent(normalizedId)}/evidence`;
        if (!hasBackendAuthCandidate(targetUrl, authContext)) {
            return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
        }

        const response = await fetchWithBackendAuthFallback(
            fetch,
            targetUrl,
            {
                method: "GET",
                cache: "no-store",
            },
            authContext,
        );

        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            return NextResponse.json(
                { detail: data?.detail || "Failed to load recommendation evidence" },
                { status: response.status },
            );
        }

        return NextResponse.json(data);
    } catch (error) {
        const message = error instanceof Error ? error.message : "Unknown recommendation evidence error";
        return NextResponse.json(
            { detail: `Could not load recommendation evidence: ${message}` },
            { status: 503 },
        );
    }
}
