"use server";

import { auth } from "@clerk/nextjs/server";
import { revalidatePath } from "next/cache";

import { getBackendIntegrations, triggerBackendScan } from "@/lib/api";

export async function triggerRescan() {
    const { userId } = await auth();
    if (!userId) {
        return { success: false, error: "Unauthorized: Please log in" };
    }

    try {
        const integrations = await getBackendIntegrations();
        if (!integrations) {
            return { success: false, error: "Failed to load connected cloud accounts" };
        }

        if (integrations.length === 0) {
            return { success: false, error: "No cloud accounts connected" };
        }

        let triggered = 0;
        const failures: string[] = [];

        for (const integration of integrations) {
            try {
                await triggerBackendScan(integration.id, { userId });
                triggered += 1;
            } catch (error) {
                const message = error instanceof Error ? error.message : String(error);
                failures.push(`${integration.provider}:${integration.id} -> ${message}`);
            }
        }

        if (triggered === 0) {
            return {
                success: false,
                error: failures[0] || "Unable to trigger scan for any connected account.",
            };
        }

        revalidatePath("/dashboard");

        return {
            success: true,
            message: failures.length > 0
                ? `Started scanning ${triggered} accounts (${failures.length} failed to start).`
                : `Started scanning ${triggered} accounts.`,
            insights: null,
        };
    } catch (error) {
        const message = error instanceof Error ? error.message : "Unknown error during scan";
        return { success: false, error: message };
    }
}
