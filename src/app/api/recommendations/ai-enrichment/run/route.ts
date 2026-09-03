import { NextRequest, NextResponse } from "next/server";

import {
    fetchWithBackendAuthFallback,
    getBackendAuthContext,
    hasBackendAuthCandidate,
} from "../../../_shared/backend-auth";
import { BACKEND_URL } from "@/lib/config";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function clampLimit(value: unknown): number {
    if (typeof value !== "number" || !Number.isFinite(value)) {
        return 1;
    }
    return Math.max(1, Math.min(5, Math.trunc(value)));
}

function clampQueueLimit(value: unknown): number {
    if (typeof value !== "number" || !Number.isFinite(value)) {
        return 25;
    }
    return Math.max(1, Math.min(100, Math.trunc(value)));
}

export async function POST(request: NextRequest) {
    try {
        const authContext = await getBackendAuthContext();
        if (!authContext) {
            return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
        }

        const payload = await request.json().catch(() => ({}));
        const row = payload && typeof payload === "object"
            ? (payload as Record<string, unknown>)
            : {};
        const body = {
            limit: clampLimit(row.limit),
            queue_pending: typeof row.queue_pending === "boolean" ? row.queue_pending : true,
            force_queue: typeof row.force_queue === "boolean" ? row.force_queue : false,
            queue_limit: clampQueueLimit(row.queue_limit),
            background: typeof row.background === "boolean" ? row.background : false,
        };
        const targetUrl = `${BACKEND_URL}/api/recommendations/ai-enrichment/run`;

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
                { detail: data?.detail || "Failed to run recommendation AI enrichment" },
                { status: response.status },
            );
        }

        return NextResponse.json(data);
    } catch (error) {
        const message = error instanceof Error ? error.message : "Unknown AI enrichment run error";
        return NextResponse.json(
            { detail: `Could not run recommendation AI enrichment: ${message}` },
            { status: 503 },
        );
    }
}
