'use server';

import { getCommitments } from "@/lib/api";

export async function fetchCommitments() {
    try {
        const commitments = await getCommitments();
        return { commitments, error: null };
    } catch (error) {
        console.error("Error in fetchCommitments action:", error);
        return { commitments: [], error: "Failed to fetch commitments" };
    }
}
