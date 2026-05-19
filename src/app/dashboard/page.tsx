import { getDashboardPageData } from '@/lib/dashboard/data';
import { DashboardSectionsClient } from '@/components/dashboard/dashboard-sections-client';
import { DashboardFinanceLoader } from '@/components/dashboard/dashboard-finance-loader';
import { syncUser } from '@/lib/sync-user';
import { Suspense } from 'react';

export const dynamic = "force-dynamic";

export default async function DashboardPage() {
    const actionableStatuses = new Set(['zombie', 'waste', 'non_compliant']);
    const hasActionableStatus = (status: string) => actionableStatuses.has((status || 'unknown').toLowerCase());

    await syncUser();

    const { stats, resources, wasteData, spendData, permissionAlert, activeIntegrationCount, integrations } = await getDashboardPageData();

    const hasConnectedAccounts =
        activeIntegrationCount > 0 ||
        resources.length > 0 ||
        Boolean(stats && stats.providerCosts.length > 0);

    // Transform resources for the inventory table
    const allResources = resources.map((resource) => {
        const normalizedStatus = (resource.status || 'unknown').toLowerCase();
        const hasIssue = hasActionableStatus(normalizedStatus);

        return {
            id: resource.id,
            name: resource.resource_name || 'Unknown',
            type: resource.resource_type || 'Unknown',
            region: resource.region || 'global',
            cost: resource.monthly_cost || 0,
            costLabel: resource.cost_label,
            costStatus: resource.cost_status,
            provider: String(resource.provider || '').toLowerCase(),
            status: normalizedStatus === 'non_compliant'
                ? 'Non-Compliant'
                : hasIssue
                    ? 'Idle/Zombie'
                    : 'Healthy',
            risk: hasIssue ? 'High' : 'Low',
            metadata: resource.metadata,
            waste_type: resource.waste_type,
            cpu_utilization: resource.cpu_utilization,
            memory_utilization: resource.memory_utilization,
        };
    });

    // Categorize for inventory tabs
    const inventoryData = {
        zombieAssets: allResources.filter((resource) => resource.status !== 'Healthy'),
        shadowIT: resources.filter((resource) => resource.region_compliance === 'shadow_it' || resource.metadata?.['is_shadow_it'] === true).map((resource) => ({
            id: resource.id,
            name: resource.resource_name || 'Unknown',
            type: resource.resource_type || 'Unknown',
            region: resource.region || 'global',
            cost: resource.monthly_cost || 0,
            costLabel: resource.cost_label,
            costStatus: resource.cost_status,
            provider: String(resource.provider || '').toLowerCase(),
            status: 'Shadow IT',
            risk: 'Medium'
        })),
        orphanedStorage: resources.filter((resource) => {
            const type = resource.resource_type?.toLowerCase() || '';
            const wasteType = (resource.waste_type || '').toLowerCase();
            const isStorageType = type.includes('ebs') || type.includes('volume') ||
                type.includes('disk') || type.includes('storage');
            return isStorageType && (wasteType.includes('orphan') || resource.status === 'zombie' || resource.status === 'waste');
        }).map((resource) => ({
            id: resource.id,
            name: resource.resource_name || 'Unknown',
            type: resource.resource_type || 'Unknown',
            region: resource.region || 'global',
            cost: resource.monthly_cost || 0,
            costLabel: resource.cost_label,
            costStatus: resource.cost_status,
            provider: String(resource.provider || '').toLowerCase(),
            status: 'Orphaned',
            risk: 'High'
        }))
    };

    const monitoredProviders = new Set(
        resources
            .map((resource) => String(resource.provider || '').trim().toLowerCase())
            .filter(Boolean)
    );
    const issueCount = resources.filter((resource) =>
        actionableStatuses.has((resource.status || '').toLowerCase())
    ).length;
    const costTrackedResources = stats?.totalResources ?? resources.length;

    return (
        <main className="p-6 md:p-10 w-full bg-slate-950 min-h-screen text-slate-200">
            {permissionAlert && (
                <div className="mb-6 bg-rose-500/10 border border-rose-500/30 rounded-xl p-4 flex flex-col md:flex-row items-start md:items-center gap-4 animate-in fade-in slide-in-from-top-4">
                    <div className="p-2 bg-rose-500/20 rounded-lg shrink-0 text-rose-400">
                        <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                        </svg>
                    </div>
                    <div className="flex-1">
                        <h3 className="text-rose-400 font-bold mb-1">{permissionAlert.action || "Restricted Access Detected"}</h3>
                        <p className="text-rose-200/80 text-sm">
                            {((permissionAlert.metadata as Record<string, unknown> | null | undefined)?.description as string | undefined) || permissionAlert.recommendation || "Your cloud provider is denying read access to certain services. We've performed a partial scan using available Billing data."}
                        </p>
                    </div>
                </div>
            )}
            {resources.length > 0 && (
                <div className="mb-6 flex items-center justify-between rounded-2xl border border-white/5 bg-slate-900/40 px-5 py-3">
                    <div className="flex items-center gap-2">
                        <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
                        <span className="text-sm text-slate-400">
                            {costTrackedResources.toLocaleString()} cost-tracked resources across {monitoredProviders.size} provider
                            {monitoredProviders.size !== 1 ? 's' : ''}
                        </span>
                    </div>
                    <div className="flex items-center gap-4 text-xs text-slate-500">
                        <span className="flex items-center gap-1.5">
                            <span className="h-1.5 w-1.5 rounded-full bg-rose-400" />
                            {issueCount} issues found
                        </span>
                        <span className="hidden lg:block">{resources.length.toLocaleString()} inventory assets scanned</span>
                        <span className="hidden md:block">Live data · refreshes on scan</span>
                    </div>
                </div>
            )}
            <DashboardSectionsClient
                stats={stats}
                resources={allResources}
                wasteData={wasteData}
                spendData={spendData}
                inventory={inventoryData}
                hasConnectedAccounts={hasConnectedAccounts}
                portfolioForecast={null}
                portfolioBudgetEvent={null}
                accountForecasts={[]}
                financeLoadError={null}
            />
            <Suspense fallback={
                <div className="mt-6 rounded-2xl border border-white/5 bg-slate-900/50 p-6 animate-pulse">
                    <div className="h-6 w-48 bg-slate-800 rounded mb-4" />
                    <div className="h-40 bg-slate-800/50 rounded" />
                </div>
            }>
                <DashboardFinanceLoader integrations={integrations} />
            </Suspense>
        </main>
    );
}
