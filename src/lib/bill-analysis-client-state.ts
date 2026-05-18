export const LAST_ANALYSIS_STORAGE_KEY = "lastBillAnalysisId";
export const LAST_ANALYSIS_SNAPSHOT_STORAGE_KEY = "lastBillAnalysisSnapshot";
export const BILL_ANALYSIS_CREATED_EVENT = "cloudfinops:bill-analysis-created";
export const BILL_ANALYSIS_REPORT_CONTRACT_VERSION = "2026-04-28-bill-line-rule-estimate-v5";

type AnalysisIdSource =
    | string
    | {
        analysis_id?: string | null;
        id?: string | null;
    }
    | null
    | undefined;

export type PersistedBillAnalysisSnapshot<T = unknown> = {
    analysisId: string;
    savedAt: string;
    version: string;
    data: T;
};

export function getBillAnalysisId(value: AnalysisIdSource): string | null {
    if (!value) {
        return null;
    }

    if (typeof value === "string") {
        const trimmed = value.trim();
        return trimmed || null;
    }

    const analysisId = String(value.analysis_id || value.id || "").trim();
    return analysisId || null;
}

export function buildBillScanHref(analysisId: string | null | undefined): string {
    const safeAnalysisId = getBillAnalysisId(analysisId);
    if (!safeAnalysisId) {
        return "/dashboard/arbitrage?tab=executive";
    }
    return `/dashboard/arbitrage?id=${encodeURIComponent(safeAnalysisId)}&tab=executive`;
}

export function shouldEnableBillAnalysisNav(params: {
    featureEnabled: boolean;
    persistedAnalysisId?: string | null;
    pathname?: string | null;
}): boolean {
    if (params.featureEnabled) {
        return true;
    }

    if (getBillAnalysisId(params.persistedAnalysisId)) {
        return true;
    }

    return Boolean(params.pathname?.startsWith("/dashboard/arbitrage"));
}

export function parsePersistedBillAnalysisSnapshot<T>(
    raw: string | null | undefined,
): PersistedBillAnalysisSnapshot<T> | null {
    if (!raw) {
        return null;
    }

    try {
        const parsed = JSON.parse(raw) as PersistedBillAnalysisSnapshot<T>;
        const analysisId = getBillAnalysisId(parsed?.analysisId);
        if (
            !analysisId
            || !parsed
            || typeof parsed !== "object"
            || !("data" in parsed)
            || String(parsed.version || "") !== BILL_ANALYSIS_REPORT_CONTRACT_VERSION
        ) {
            return null;
        }

        return {
            analysisId,
            savedAt: String(parsed.savedAt || ""),
            version: String(parsed.version || ""),
            data: parsed.data,
        };
    } catch {
        return null;
    }
}

export function snapshotMatchesAnalysisId<T>(
    snapshot: PersistedBillAnalysisSnapshot<T> | null,
    analysisId: string | null | undefined,
): snapshot is PersistedBillAnalysisSnapshot<T> {
    const safeAnalysisId = getBillAnalysisId(analysisId);
    return Boolean(snapshot && safeAnalysisId && snapshot.analysisId === safeAnalysisId);
}


function asObject(value: unknown): Record<string, unknown> | null {
    return value && typeof value === "object" && !Array.isArray(value)
        ? (value as Record<string, unknown>)
        : null;
}


export function hasCurrentBillAnalysisContract(value: unknown): boolean {
    const raw = asObject(value);
    const sourceMetadata = asObject(raw?.source_metadata);
    return String(sourceMetadata?.report_contract_version || "") === BILL_ANALYSIS_REPORT_CONTRACT_VERSION;
}
