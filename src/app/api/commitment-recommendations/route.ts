import { NextRequest, NextResponse } from "next/server";

import {
    fetchWithBackendAuthFallback,
    getBackendAuthContext,
    hasBackendAuthCandidate,
} from "../_shared/backend-auth";
import { BACKEND_URL } from "@/lib/config";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const RESPONSE_HEADERS = { "Cache-Control": "no-store" };

export async function GET(request: NextRequest): Promise<NextResponse> {
    let upstreamSignal: AbortSignal | undefined;
    try {
        const authContext = await getBackendAuthContext();
        if (!authContext) {
            return NextResponse.json({ detail: "Unauthorized" }, { status: 401, headers: RESPONSE_HEADERS });
        }

        const targetUrl = new URL(`${BACKEND_URL}/api/commitment-recommendations`);
        // Preserve even empty legacy parameters so backend validation rejects them.
        for (const parameter of ["integration_id", "coverage_target", "max_term", "payment_option"]) {
            for (const value of request.nextUrl.searchParams.getAll(parameter)) {
                targetUrl.searchParams.append(parameter, value);
            }
        }

        if (!hasBackendAuthCandidate(targetUrl.toString(), authContext)) {
            return NextResponse.json({ detail: "Unauthorized" }, { status: 401, headers: RESPONSE_HEADERS });
        }

        const timeoutSignal = AbortSignal.timeout(15_000);
        upstreamSignal = typeof AbortSignal.any === "function"
            ? AbortSignal.any([request.signal, timeoutSignal])
            : timeoutSignal;

        const response = await fetchWithBackendAuthFallback(
            fetch,
            targetUrl.toString(),
            {
                method: "GET",
                cache: "no-store",
                signal: upstreamSignal,
            },
            authContext,
        );

        const data: unknown = await response.json().catch((error: unknown) => {
            if (!(error instanceof SyntaxError)) throw error;
            return null;
        });
        if (!response.ok) {
            return NextResponse.json(
                data ?? { detail: "Failed to load commitment recommendations" },
                { status: response.status, headers: RESPONSE_HEADERS },
            );
        }

        if (data === null || typeof data !== "object" || Array.isArray(data)) {
            return NextResponse.json(
                { detail: "Commitment recommendations service returned invalid JSON" },
                { status: 502, headers: RESPONSE_HEADERS },
            );
        }

        return NextResponse.json(data, { headers: RESPONSE_HEADERS });
    } catch (error) {
        const failure: unknown = upstreamSignal?.aborted ? upstreamSignal.reason : error;
        const timedOut = failure instanceof Error && failure.name === "TimeoutError";
        return NextResponse.json(
            { detail: timedOut ? "Commitment recommendations service timed out" : "Could not reach the commitment recommendations service" },
            { status: timedOut ? 504 : 503, headers: RESPONSE_HEADERS },
        );
    }
}
