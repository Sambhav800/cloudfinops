'use server';

import { auth } from "@clerk/nextjs/server";
import { estimateTerraformPlan as estimatePlan } from "@/lib/api";

/**
 * Server Action bridge for the Terraform Simulator.
 * This allows Client Components to safely trigger estimations
 * while keeping auth token logic on the server.
 */
export async function simulateTerraformCost(plan: Record<string, unknown>, filename?: string | null) {
    try {
        const { userId } = await auth();
        if (!userId) {
            return { error: "Unauthorized: Please sign in to use the simulator." };
        }

        // Call our internal API library which handles backend communication
        const { data, error } = await estimatePlan(plan, filename);
        
        if (error) {
            return { error };
        }

        return { data };
    } catch (error) {
        return {
            error: error instanceof Error ? error.message : "An unexpected error occurred during simulation." 
        };
    }
}
