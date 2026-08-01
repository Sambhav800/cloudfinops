import { getExclusions, getExclusionStats, getExclusionSuggestions } from "@/lib/api";
import { ExclusionsView } from "@/components/dashboard/exclusions-view";

export const dynamic = "force-dynamic";

export default async function ExclusionsPage() {
    let exclusions = null;
    let stats = null;
    let suggestions = null;

    try {
        [exclusions, stats, suggestions] = await Promise.all([
            getExclusions(),
            getExclusionStats(),
            getExclusionSuggestions(),
        ]);
    } catch (error) {
        if (process.env.NODE_ENV === "development") {
            console.error("Exclusions page load error:", error);
        }
    }

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-semibold text-white">Zombie Shield</h1>
                <p className="mt-1 text-sm text-slate-400">
                    Protect seasonal, DR, and batch resources from false zombie detection
                </p>
            </div>
            <ExclusionsView
                exclusions={exclusions?.exclusions ?? []}
                stats={stats}
                suggestions={suggestions?.suggestions ?? []}
            />
        </div>
    );
}
