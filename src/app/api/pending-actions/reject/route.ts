import { NextRequest, NextResponse } from "next/server";

import { fetchWithBackendAuthFallback, getBackendAuthContext } from "../../_shared/backend-auth";
import { BACKEND_URL } from "@/lib/config";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
    try {
        const authContext = await getBackendAuthContext();
        if (!authContext) {
            return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
        }

        const payload = await request.json().catch(() => ({}));
        const notificationId = typeof payload?.notification_id === "string"
            ? payload.notification_id.trim()
            : "";
        const reason = typeof payload?.reason === "string"
            ? payload.reason.trim()
            : "";

        if (!notificationId) {
            return NextResponse.json({ detail: "notification_id is required" }, { status: 400 });
        }

        const response = await fetchWithBackendAuthFallback(
            fetch,
            `${BACKEND_URL}/api/reject-action`,
            {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    notification_id: notificationId,
                    reason: reason || "Rejected from dashboard",
                }),
                cache: "no-store",
            },
            authContext,
        );

        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            return NextResponse.json(
                { detail: data?.detail || "Failed to reject pending action" },
                { status: response.status },
            );
        }

        return NextResponse.json(data);
    } catch (error) {
        const message = error instanceof Error ? error.message : "Unknown pending action error";
        return NextResponse.json(
            { detail: `Could not update pending action: ${message}` },
            { status: 503 },
        );
    }
}
