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

async function proxyVerification(
    recommendationId: string,
    method: "GET" | "POST",
    pathSuffix: "" | "/run",
) {
    try {
        const authContext = await getBackendAuthContext();
        if (!authContext) {
            return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
        }

        if (!recommendationId) {
            return NextResponse.json({ detail: "recommendationId is required" }, { status: 400 });
        }

        const targetUrl = `${BACKEND_URL}/api/recommendations/${encodeURIComponent(recommendationId)}/verification${pathSuffix}`;
        if (!hasBackendAuthCandidate(targetUrl, authContext)) {
            return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
        }

        const response = await fetchWithBackendAuthFallback(
            fetch,
            targetUrl,
            {
                method,
                cache: "no-store",
            },
            authContext,
        );

        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            return NextResponse.json(
                { detail: data?.detail || "Failed to load savings verification" },
                { status: response.status },
            );
        }

        return NextResponse.json(data);
    } catch (error) {
        const message = error instanceof Error ? error.message : "Unknown verification proxy error";
        return NextResponse.json(
            { detail: `Savings verification proxy failed: ${message}` },
            { status: 503 },
        );
    }
}

export async function GET(_request: NextRequest, context: RouteContext) {
    try {
        const { recommendationId } = await context.params;
        return await proxyVerification(normalizeRecommendationId(recommendationId), "GET", "");
    } catch (error) {
        const message = error instanceof Error ? error.message : "Unknown verification error";
        return NextResponse.json(
            { detail: `Could not load savings verification: ${message}` },
            { status: 503 },
        );
    }
}

export async function POST(_request: NextRequest, context: RouteContext) {
    try {
        const { recommendationId } = await context.params;
        return await proxyVerification(normalizeRecommendationId(recommendationId), "POST", "/run");
    } catch (error) {
        const message = error instanceof Error ? error.message : "Unknown verification error";
        return NextResponse.json(
            { detail: `Could not run savings verification: ${message}` },
            { status: 503 },
        );
    }
}
