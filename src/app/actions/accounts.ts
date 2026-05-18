"use server";

import { auth } from "@clerk/nextjs/server";
import { revalidatePath } from "next/cache";

import { deleteBackendIntegration } from "@/lib/api";

export async function deleteCloudAccount(accountId: string) {
    const { userId } = await auth();
    if (!userId) {
        return { success: false, error: "Unauthorized" };
    }

    try {
        const result = await deleteBackendIntegration(accountId);
        if (result.error) {
            return { success: false, error: result.error };
        }

        revalidatePath("/dashboard/settings");
        revalidatePath("/dashboard/governance");
        revalidatePath("/dashboard");

        return { success: true };
    } catch (error) {
        const message = error instanceof Error ? error.message : "Failed to delete account";
        return { success: false, error: message };
    }
}
