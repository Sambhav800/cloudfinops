import { NextRequest, NextResponse } from "next/server";

import { fetchWithBackendAuthFallback, getBackendAuthContext } from "../../_shared/backend-auth";
import { BACKEND_URL } from "@/lib/config";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type RouteContext = {
    params: Promise<{
        notificationId: string;
    }>;
};

async function proxyNotificationMutation(
    method: "PATCH" | "DELETE",
    _request: NextRequest,
    context: RouteContext,
) {
    try {
        const authContext = await getBackendAuthContext();
        if (!authContext) {
            return NextResponse.json({ detail: "Unauthorized" }, { status: 401 });
        }

        const { notificationId } = await context.params;
        const normalizedId = typeof notificationId === "string" ? notificationId.trim() : "";
        if (!normalizedId) {
            return NextResponse.json({ detail: "notificationId is required" }, { status: 400 });
        }

        const response = await fetchWithBackendAuthFallback(
            fetch,
            `${BACKEND_URL}/api/notifications/${encodeURIComponent(normalizedId)}`,
            {
                method,
                cache: "no-store",
            },
            authContext,
        );

        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            return NextResponse.json(
                { detail: data?.detail || "Notification update failed" },
                { status: response.status },
            );
        }

        return NextResponse.json(data);
    } catch (error) {
        const message = error instanceof Error ? error.message : "Unknown notification mutation error";
        return NextResponse.json(
            { detail: `Could not update notification: ${message}` },
            { status: 503 },
        );
    }
}

export async function PATCH(request: NextRequest, context: RouteContext) {
    return proxyNotificationMutation("PATCH", request, context);
}

export async function DELETE(request: NextRequest, context: RouteContext) {
    return proxyNotificationMutation("DELETE", request, context);
}
