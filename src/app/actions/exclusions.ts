"use server";

import { auth } from "@clerk/nextjs/server";
import { revalidatePath } from "next/cache";

import {
    createExclusion,
    createRuleExclusion,
    deleteExclusion,
    acceptExclusionSuggestion,
    dismissExclusionSuggestion,
    type UsageSchedule,
    type RuleMatch,
} from "@/lib/api";

export async function shieldResource(payload: {
    cloud_resource_id: string;
    integration_id: string;
    resource_name?: string;
    provider?: string;
    reason: string;
    reason_note?: string;
    usage_schedule?: UsageSchedule;
    expires_in_days?: number;
}) {
    const { userId } = await auth();
    if (!userId) {
        return { success: false, error: "Unauthorized" };
    }

    const result = await createExclusion(payload);
    if (result.error) {
        return { success: false, error: result.error };
    }

    revalidatePath("/dashboard/exclusions");
    revalidatePath("/dashboard/resources");
    return { success: true, exclusion: result.data?.exclusion };
}

export async function createShieldRule(payload: {
    rule_match: RuleMatch;
    reason: string;
    reason_note?: string;
    usage_schedule?: UsageSchedule;
    expires_in_days?: number;
}) {
    const { userId } = await auth();
    if (!userId) {
        return { success: false, error: "Unauthorized" };
    }

    const result = await createRuleExclusion(payload);
    if (result.error) {
        return { success: false, error: result.error };
    }

    revalidatePath("/dashboard/exclusions");
    revalidatePath("/dashboard/resources");
    return { success: true, exclusion: result.data?.exclusion };
}

export async function removeShield(exclusionId: string) {
    const { userId } = await auth();
    if (!userId) {
        return { success: false, error: "Unauthorized" };
    }

    const result = await deleteExclusion(exclusionId);
    if (result.error) {
        return { success: false, error: result.error };
    }

    revalidatePath("/dashboard/exclusions");
    revalidatePath("/dashboard/resources");
    return { success: true };
}

export async function acceptSuggestion(
    suggestionId: string,
    payload: {
        cloud_resource_id: string;
        integration_id: string;
        resource_name?: string;
        provider?: string;
        reason: string;
        reason_note?: string;
        usage_schedule?: UsageSchedule;
        expires_in_days?: number;
    },
) {
    const { userId } = await auth();
    if (!userId) {
        return { success: false, error: "Unauthorized" };
    }

    const result = await acceptExclusionSuggestion(suggestionId, payload);
    if (result.error) {
        return { success: false, error: result.error };
    }

    revalidatePath("/dashboard/exclusions");
    revalidatePath("/dashboard/resources");
    return { success: true, exclusion: result.data?.exclusion };
}

export async function dismissSuggestionAction(suggestionId: string) {
    const { userId } = await auth();
    if (!userId) {
        return { success: false, error: "Unauthorized" };
    }

    const result = await dismissExclusionSuggestion(suggestionId);
    if (result.error) {
        return { success: false, error: result.error };
    }

    revalidatePath("/dashboard/exclusions");
    return { success: true };
}
