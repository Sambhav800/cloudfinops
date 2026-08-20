import { NextRequest, NextResponse } from "next/server";

import {
    fetchWithBackendAuthFallback,
    getBackendAuthContext,
    hasBackendAuthCandidate,
} from "../../../_shared/backend-auth";
import { BACKEND_URL } from "@/lib/config";
import type { RecommendationState } from "@/lib/recommendations/types";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type RouteContext = {
    params: Promise<{
        recommendationId: string;
    }>;
};

const ALLOWED_STATES: ReadonlySet<RecommendationState> = new Set([
    "detected",
    "evidence_ready",
    "provider_checked",
    "ready_for_review",
    "approved",
    "dismissed",
    "implemented",
    "verifying",
    "verified_saved",
    "verified_no_savings",
    "expired",
    "superseded",
]);

function isRecommendationState(value: unknown): value is RecommendationState {
    return typeof value === "string" && ALLOWED_STATES.has(value as RecommendationState);
}

export async function POST(request: NextRequest, context: RouteContext) {
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

        const payload = await request.json().catch(() => ({}));
        const nextState = payload && typeof payload === "object" && "state" in payload
            ? (payload as Record<string, unknown>).state
            : null;
        if (!isRecommendationState(nextState)) {
            return NextResponse.json({ detail: "Valid state is required" }, { status: 400 });
        }

        const reason = payload && typeof payload === "object" && "reason" in payload
            ? (payload as Record<string, unknown>).reason
            : null;
        const body = {
            state: nextState,
            reason: typeof reason === "string" && reason.trim() ? reason.trim() : null,
        };
        const targetUrl = `${BACKEND_URL}/api/recommendations/${encodeURIComponent(normalizedId)}/state`;

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
                { detail: data?.detail || "Failed to update recommendation state" },
                { status: response.status },
            );
        }

        return NextResponse.json(data);
    } catch (error) {
        const message = error instanceof Error ? error.message : "Unknown recommendation state error";
        return NextResponse.json(
            { detail: `Could not update recommendation state: ${message}` },
            { status: 503 },
        );
    }
}
