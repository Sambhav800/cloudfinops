import { getActiveArchitectureIntegrations } from '@/lib/dashboard/data';
import { ArchitecturePageV2Client } from '@/components/dashboard/architecture/architecture-page-v2-client';
import { Network, AlertCircle } from 'lucide-react';
import { syncUser } from '@/lib/sync-user';

export const dynamic = 'force-dynamic';

export default async function ArchitecturePage() {
    let integrations = [] as Awaited<ReturnType<typeof getActiveArchitectureIntegrations>>;
    let loadError: string | null = null;

    try {
        // Sync user before loading architecture data so auth stays request-bound
        await syncUser();

        // Fetch all active cloud integrations (AWS/Azure/GCP)
        integrations = await getActiveArchitectureIntegrations();
    } catch (error) {
        if (process.env.NODE_ENV === "development") {
            console.error("Architecture page load error:", error);
        }
        loadError = error instanceof Error ? error.message : "Failed to load architecture data";
    }

    return (
        <main className="p-6 md:p-10 w-full bg-slate-950 min-h-screen text-slate-200">
            {/* Header Section */}
            <div className="mb-6 flex flex-col md:flex-row md:items-end justify-between gap-4">
                <div>
                    <h2 className="text-xl font-bold text-white mb-1 flex items-center gap-2">
                        <Network className="w-6 h-6 text-indigo-400" />
                        Cloud Architecture
                    </h2>
                    <p className="text-slate-400 text-sm">Live deterministic topology mapped from latest infrastructure scans</p>
                </div>
            </div>

            {integrations.length === 0 ? (
                <div className="space-y-4">
                    {loadError && (
                        <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-300">
                            <div className="flex items-start gap-3">
                                <svg className="w-5 h-5 text-rose-400 mt-0.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                                </svg>
                                <div>
                                    <p className="font-medium text-rose-200">Data could not be loaded</p>
                                    <p className="mt-1 text-rose-300/80">{loadError}</p>
                                </div>
                            </div>
                        </div>
                    )}
                    <div className="flex flex-col items-center justify-center rounded-2xl border border-white/10 bg-slate-900/50 p-12 backdrop-blur-xl">
                        <AlertCircle className="w-12 h-12 text-slate-500 mb-4" />
                        <h3 className="text-white font-medium text-lg mb-2">No Active Cloud Integration</h3>
                        <p className="text-slate-400 text-center max-w-md">
                            Please connect an AWS, Azure, or GCP account in Settings and run a successful scan to view your architecture.
                        </p>
                    </div>
                </div>
            ) : (
                <ArchitecturePageV2Client
                    integrations={integrations}
                    loadError={loadError}
                />
            )}
        </main>
    );
}
