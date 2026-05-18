
import { getPendingActions } from "@/lib/dashboard/data";
import { PendingActionsList } from "@/components/dashboard/actions-list";
import { ErrorBanner } from "@/components/dashboard/error-banner";

export const dynamic = "force-dynamic";

export default async function PendingActionsPage() {
    let actions = [] as Awaited<ReturnType<typeof getPendingActions>>;
    let loadError: string | null = null;

    try {
        actions = await getPendingActions();
    } catch (error) {
        if (process.env.NODE_ENV === "development") {
            console.error("Pending actions page load error:", error);
        }
        loadError = error instanceof Error ? error.message : "Failed to load pending actions";
    }

    const pendingCount = actions.filter(a => a.status === "pending").length;

    return (
        <div className="min-h-screen">
            <div className="px-6 py-4">
                <h1 className="text-2xl font-bold text-white">Pending Actions</h1>
                <p className="text-sm text-gray-400">{`${pendingCount} actions awaiting your approval`}</p>
            </div>
            <div className="space-y-4">
                {loadError && <ErrorBanner message={loadError} />}
                <PendingActionsList initialActions={actions} />
            </div>
        </div>
    );
}
