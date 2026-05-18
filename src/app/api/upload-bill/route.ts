import { NextRequest, NextResponse } from "next/server";

import {
    fetchWithBackendAuthFallback,
    getBackendAuthContext,
    hasBackendAuthCandidate,
} from "../_shared/backend-auth";
import { BACKEND_URL } from "@/lib/config";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
const UPLOAD_TIMEOUT_MS = 240_000;

export async function POST(request: NextRequest) {
    try {
        const authContext = await getBackendAuthContext();
        if (!authContext?.userId) {
            return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
        }

        const incomingForm = await request.formData();
        const file = incomingForm.get("file");
        if (!(file instanceof File)) {
            return NextResponse.json({ detail: "No file provided." }, { status: 400 });
        }

        const MAX_UPLOAD_BYTES = 50 * 1024 * 1024;
        if (file.size > MAX_UPLOAD_BYTES) {
            return NextResponse.json(
                { detail: "File too large. Maximum size is 50 MB." },
                { status: 413 },
            );
        }

        const outgoingForm = new FormData();
        const fileBuffer = await file.arrayBuffer();
        const blob = new Blob([fileBuffer], { type: file.type || "application/octet-stream" });
        outgoingForm.append("file", blob, file.name);

        for (const field of ["aws_discount_pct", "gcp_discount_pct", "azure_discount_pct"]) {
            outgoingForm.append(field, incomingForm.get(field)?.toString() || "0");
        }
        const uploadUrl = `${BACKEND_URL}/api/scan/upload-bill`;
        if (!hasBackendAuthCandidate(uploadUrl, authContext)) {
            return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
        }

        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), UPLOAD_TIMEOUT_MS);

        let response: Response;
        try {
            response = await fetchWithBackendAuthFallback(fetch, uploadUrl, {
                method: "POST",
                body: outgoingForm,
                signal: controller.signal,
            }, authContext);
        } catch (error) {
            if (error instanceof Error && error.name === "AbortError") {
                return NextResponse.json(
                    {
                        detail:
                            "Bill analysis timed out while waiting for the backend. Try a CSV/Excel export, or use a smaller text-based PDF if this was a scanned invoice.",
                    },
                    { status: 504 },
                );
            }
            throw error;
        } finally {
            clearTimeout(timeoutId);
        }

        const data = await response.json();
        if (!response.ok) {
            return NextResponse.json(
                { detail: data?.detail || "Analysis failed" },
                { status: response.status },
            );
        }

        return NextResponse.json(data);
    } catch (error) {
        const message = error instanceof Error ? error.message : "Unknown upload error";
        return NextResponse.json(
            { detail: `Could not reach the analysis engine: ${message}` },
            { status: 503 },
        );
    }
}
