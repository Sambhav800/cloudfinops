import { NextRequest, NextResponse } from "next/server";

import { fetchWithBackendAuthFallback, getBackendAuthContext } from "../../_shared/backend-auth";
import { BACKEND_URL } from "@/lib/config";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type RouteContext = {
    params: Promise<{
        analysisId: string;
    }>;
};

export async function GET(request: NextRequest, context: RouteContext) {
    try {
        const authContext = await getBackendAuthContext();
        const fallbackUserId = request.nextUrl.searchParams.get("userId");

        if (!authContext && !fallbackUserId) {
            return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
        }

        const { analysisId } = await context.params;
        const response = await fetchWithBackendAuthFallback(
            fetch,
            `${BACKEND_URL}/api/bill-analyses/${encodeURIComponent(analysisId)}`,
            {
                method: "GET",
                cache: "no-store",
            },
            authContext ?? { userId: null, token: null },
            fallbackUserId,
        );

        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            return NextResponse.json(
                { detail: data?.detail || "Failed to load bill analysis" },
                { status: response.status },
            );
        }

        return NextResponse.json(data);
    } catch (error) {
        const message = error instanceof Error ? error.message : "Unknown bill analysis error";
        return NextResponse.json(
            { detail: `Could not reach the analysis service: ${message}` },
            { status: 503 },
        );
    }
}
