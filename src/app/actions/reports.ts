'use server';

import { revalidatePath } from "next/cache";

import {
    createBackendReport,
    type BackendReportRecord,
    type BackendReportType,
} from "@/lib/api";

const SUPPORTED_REPORT_TYPES = new Set<BackendReportType>([
    "monthly_executive_summary",
    "budget_variance",
    "provider_spend_summary",
    "board_pack",
]);

export async function generateReportAction(formData: FormData): Promise<{
    success: boolean;
    error?: string;
    report?: BackendReportRecord;
}> {
    const reportType = String(formData.get("reportType") || "").trim();
    const startDate = String(formData.get("startDate") || "").trim();
    const endDate = String(formData.get("endDate") || "").trim();

    if (!reportType) {
        return { success: false, error: "Report type is required" };
    }

    if (!SUPPORTED_REPORT_TYPES.has(reportType as BackendReportType)) {
        return { success: false, error: "Unsupported report type" };
    }

    const result = await createBackendReport({
        reportType: reportType as BackendReportType,
        startDate: startDate || undefined,
        endDate: endDate || undefined,
    });

    if (!result.report) {
        return {
            success: false,
            error: result.error || "Failed to generate report",
        };
    }

    revalidatePath("/dashboard/reports");
    return { success: true, report: result.report };
}
