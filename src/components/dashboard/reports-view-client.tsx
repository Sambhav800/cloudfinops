"use client";

import dynamic from "next/dynamic";
import type { BackendReportRecord } from "@/lib/api";
import { ErrorBanner } from "@/components/dashboard/error-banner";

const ReportsView = dynamic(() => import("@/components/dashboard/reports-view").then((mod) => mod.ReportsView), { ssr: false });

export function ReportsViewClient({ initialReports, loadError }: { initialReports: BackendReportRecord[]; loadError: string | null }) {
    return (
        <div className="space-y-4">
            {loadError && <ErrorBanner message={loadError} />}
            <ReportsView initialReports={initialReports} />
        </div>
    );
}
