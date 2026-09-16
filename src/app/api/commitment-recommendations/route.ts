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

        const targetUrl = new URL(`${BACKEND_URL}/api/commitment-recommendations`);

        const coverageTarget = request.nextUrl.searchParams.get("coverage_target")?.trim();
        if (coverageTarget) {
            targetUrl.searchParams.set("coverage_target", coverageTarget);
        }

        const maxTerm = request.nextUrl.searchParams.get("max_term")?.trim();
        if (maxTerm) {
            targetUrl.searchParams.set("max_term", maxTerm);
        }

        const paymentOption = request.nextUrl.searchParams.get("payment_option")?.trim();
        if (paymentOption) {
            targetUrl.searchParams.set("payment_option", paymentOption);
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
                { detail: data?.detail || "Failed to load commitment recommendations" },
                { status: response.status },
            );
        }

        return NextResponse.json(data);
    } catch (error) {
        const message = error instanceof Error ? error.message : "Unknown error";
        return NextResponse.json(
            { detail: `Could not reach the commitment recommendations service: ${message}` },
            { status: 503 },
        );
    }
}
