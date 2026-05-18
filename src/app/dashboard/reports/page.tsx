
import { getBackendReports } from "@/lib/api";
import { ReportsViewClient } from "@/components/dashboard/reports-view-client";

export const dynamic = "force-dynamic";

export default async function ReportsPage() {
    let reports = [] as Awaited<ReturnType<typeof getBackendReports>>;
    let loadError: string | null = null;

    try {
        reports = await getBackendReports();
    } catch (error) {
        if (process.env.NODE_ENV === "development") {
            console.error("Reports page load error:", error);
        }
        loadError = error instanceof Error ? error.message : "Failed to load reports";
    }

    return (
        <div className="min-h-screen">
            <div className="px-6 py-4">
                <h1 className="text-2xl font-bold text-white">Reports</h1>
                <p className="text-sm text-gray-400">Generate and download executive-ready finance reports</p>
            </div>
            <ReportsViewClient initialReports={reports} loadError={loadError} />
        </div>
    );
}
