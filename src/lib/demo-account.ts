export const CANONICAL_DEMO_DATA_OWNER_ID = "user_3ALOgTiKSBfTVwyOEahrUCjIWmi";

const LEGACY_DEMO_DATA_OWNER_IDS = new Set<string>([
    "user_38kP2Ff8Jo2Y5g4zCtTr4Qg85kN",
    CANONICAL_DEMO_DATA_OWNER_ID,
]);

const DEMO_ACCOUNT_EMAILS = new Set<string>([
    "sambhavpal5@gmail.com",
]);

function normalizeEmail(value: unknown): string | null {
    if (typeof value !== "string") {
        return null;
    }

    const trimmed = value.trim().toLowerCase();
    return trimmed.length > 0 ? trimmed : null;
}

export function isDemoAccountEmail(value: unknown): boolean {
    const normalized = normalizeEmail(value);
    return normalized !== null && DEMO_ACCOUNT_EMAILS.has(normalized);
}

export function normalizeDemoDataOwnerId(value: string | null | undefined): string | null {
    if (typeof value !== "string") {
        return null;
    }

    const trimmed = value.trim();
    if (!trimmed) {
        return null;
    }

    if (LEGACY_DEMO_DATA_OWNER_IDS.has(trimmed)) {
        return CANONICAL_DEMO_DATA_OWNER_ID;
    }

    return trimmed;
}
