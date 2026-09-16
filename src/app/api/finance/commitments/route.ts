import { NextResponse } from "next/server";

import {
    fetchWithBackendAuthFallback,
    getBackendAuthContext,
    hasBackendAuthCandidate,
} from "../../_shared/backend-auth";
import { BACKEND_URL } from "@/lib/config";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
    try {
        const authContext = await getBackendAuthContext();
        if (!authContext) {
            return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
        }

        const targetUrl = `${BACKEND_URL}/api/finance/commitments`;
        if (!hasBackendAuthCandidate(targetUrl, authContext)) {
            return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
        }

        const response = await fetchWithBackendAuthFallback(
            fetch,
            targetUrl,
            {
                method: "GET",
                cache: "no-store",
                signal: AbortSignal.timeout(15_000),
            },
            authContext,
        );

        const data: unknown = await response.json().catch(() => null);
        if (!response.ok) {
            return NextResponse.json(
                data ?? { detail: "Failed to load commitments" },
                { status: response.status },
            );
        }
        if (data === null) {
            return NextResponse.json({ detail: "Commitments service returned invalid JSON" }, { status: 502 });
        }
        return NextResponse.json(data, { headers: { "Cache-Control": "no-store" } });
    } catch (error) {
        const timedOut = error instanceof Error && error.name === "TimeoutError";
        return NextResponse.json(
            { detail: timedOut ? "Commitments service timed out" : "Could not reach the commitments service" },
            { status: timedOut ? 504 : 503 },
        );
    }
}
