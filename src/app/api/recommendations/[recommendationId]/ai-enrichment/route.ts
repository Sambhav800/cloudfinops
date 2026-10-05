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

function normalizeRecommendationId(value: unknown): string {
    return typeof value === "string" ? value.trim() : "";
}

async function proxyAiEnrichment(
    recommendationId: string,
    requestInit: RequestInit,
    pathSuffix = "",
) {
    try {
        const authContext = await getBackendAuthContext();
        if (!authContext) {
            return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
        }

        if (!recommendationId) {
            return NextResponse.json({ detail: "recommendationId is required" }, { status: 400 });
        }

        const targetUrl = `${BACKEND_URL}/api/recommendations/${encodeURIComponent(recommendationId)}/ai-enrichment${pathSuffix}`;
        if (!hasBackendAuthCandidate(targetUrl, authContext)) {
            return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
        }

        const response = await fetchWithBackendAuthFallback(
            fetch,
            targetUrl,
            {
                ...requestInit,
                cache: "no-store",
            },
            authContext,
        );

        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            return NextResponse.json(
                { detail: data?.detail || "Failed to load recommendation AI enrichment" },
                { status: response.status },
            );
        }

        return NextResponse.json(data);
    } catch (error) {
        const message = error instanceof Error ? error.message : "Unknown AI enrichment proxy error";
        return NextResponse.json(
            { detail: `Recommendation AI enrichment proxy failed: ${message}` },
            { status: 503 },
        );
    }
}

export async function GET(_request: NextRequest, context: RouteContext) {
    try {
        const { recommendationId } = await context.params;
        return await proxyAiEnrichment(
            normalizeRecommendationId(recommendationId),
            { method: "GET" },
        );
    } catch (error) {
        const message = error instanceof Error ? error.message : "Unknown AI enrichment error";
        return NextResponse.json(
            { detail: `Could not load recommendation AI enrichment: ${message}` },
            { status: 503 },
        );
    }
}

export async function POST(request: NextRequest, context: RouteContext) {
    try {
        const { recommendationId } = await context.params;
        const payload = await request.json().catch(() => ({}));
        const force = payload && typeof payload === "object" && "force" in payload
            ? (payload as Record<string, unknown>).force
            : false;
        return await proxyAiEnrichment(
            normalizeRecommendationId(recommendationId),
            {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ force: typeof force === "boolean" ? force : false }),
            },
            "/queue",
        );
    } catch (error) {
        const message = error instanceof Error ? error.message : "Unknown AI enrichment queue error";
        return NextResponse.json(
            { detail: `Could not queue recommendation AI enrichment: ${message}` },
            { status: 503 },
        );
    }
}
