import { auth } from "@clerk/nextjs/server";
import { NextRequest, NextResponse } from "next/server";

import {
    createBackendAutomatedSyncIntegration,
} from "@/lib/api";
import {
    fetchWithBackendAuthFallback,
    hasBackendAuthCandidate,
} from "../_shared/backend-auth";
import { BACKEND_URL } from "@/lib/config";

type Provider = "aws" | "azure" | "gcp";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function normalizeProvider(value: unknown): Provider | null {
    const provider = String(value || "").trim().toLowerCase();
    if (provider === "aws" || provider === "azure" || provider === "gcp") {
        return provider;
    }
    return null;
}

export async function POST(request: NextRequest) {
    const payload = await request.json().catch(() => ({}));
    const provider = normalizeProvider(payload.provider);
    const storagePath = typeof payload.storagePath === "string" ? payload.storagePath.trim() : "";
    const credential = typeof payload.credential === "string" ? payload.credential.trim() : "";

    if (!provider || !storagePath || !credential) {
        return NextResponse.json({ error: "Missing required fields" }, { status: 400 });
    }

    const { userId, getToken } = await auth();
    if (!userId) {
        return NextResponse.json({ error: "Unauthorized: Please log in first" }, { status: 401 });
    }

    try {
        let token: string | null = null;
        try {
            token = await getToken();
        } catch {
            token = null;
        }

        if (!token) {
            try {
                token = await getToken({ template: "default" });
            } catch {
                token = null;
            }
        }

        const validationUrl = `${BACKEND_URL}/api/scan/validate-automated-sync`;
        const authContext = { userId, token };
        if (!hasBackendAuthCandidate(validationUrl, authContext)) {
            return NextResponse.json(
                { error: "Unauthorized: Backend token unavailable" },
                { status: 401 },
            );
        }

        const validationResponse = await fetchWithBackendAuthFallback(fetch, validationUrl, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                provider,
                storage_path: storagePath,
                credential,
            }),
        }, authContext);

        if (!validationResponse.ok) {
            const body = await validationResponse.json().catch(() => ({}));
            return NextResponse.json(
                { error: body?.detail || "Validation failed. Please check credentials and path." },
                { status: validationResponse.status },
            );
        }

        const result = await createBackendAutomatedSyncIntegration({
            provider,
            storage_path: storagePath,
            credential,
            aws_discount: Number(payload.awsDiscount ?? 0),
            azure_discount: Number(payload.azureDiscount ?? 0),
            gcp_discount: Number(payload.gcpDiscount ?? 0),
        });

        if (result.error || !result.integration) {
            return NextResponse.json(
                { error: result.error || "Failed to save automated billing integration" },
                { status: result.status >= 400 ? result.status : 500 },
            );
        }

        return NextResponse.json({
            success: true,
            message: "Automated billing configured successfully.",
        });
    } catch (error) {
        const message = error instanceof Error ? error.message : "Unknown error";
        return NextResponse.json({ error: message }, { status: 500 });
    }
}
