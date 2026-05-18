import { ErrorBanner } from "@/components/dashboard/error-banner";
import { SecurityView } from "@/components/dashboard/security-view";
import { getSecurityPosture } from "@/lib/dashboard/data";

export const dynamic = "force-dynamic";

export default async function SecurityPage() {
    const fallbackPosture = {
        summary: {
            score: 0,
            rating: "No data",
            critical: 0,
            high: 0,
            open: 0,
            exposedResources: 0,
            monitoredResources: 0,
            lastDetectedAt: null,
        },
        findingsBySeverity: [],
        findingsByCategory: [],
        activeFindings: [],
        exposedResources: [],
        recentAlerts: [],
    } as Awaited<ReturnType<typeof getSecurityPosture>>;

    let posture = fallbackPosture;
    let loadError: string | null = null;

    try {
        posture = await getSecurityPosture() || fallbackPosture;
    } catch (error) {
        if (process.env.NODE_ENV === "development") {
            console.error("Security page load error:", error);
        }
        loadError = error instanceof Error ? error.message : "Failed to load security data";
    }

    return (
        <div className="min-h-screen bg-slate-950 text-slate-200">
            <div className="px-6 py-4 space-y-4">
                {loadError && <ErrorBanner message={loadError} />}
                <SecurityView initialPosture={posture} />
            </div>
        </div>
    );
}
