import { NextResponse } from "next/server";
import { auth } from "@clerk/nextjs/server";
import { syncUser } from "@/lib/sync-user";

export const runtime = "nodejs";

export async function POST() {
    const { userId } = await auth();
    if (!userId) {
        return NextResponse.json(
            { success: false, error: "Unauthorized" },
            { status: 401 },
        );
    }

    const syncedUserId = await syncUser();

    if (!syncedUserId) {
        return NextResponse.json(
            { success: false, error: "User sync failed" },
            { status: 500 },
        );
    }

    return NextResponse.json({ success: true, userId: syncedUserId });
}
