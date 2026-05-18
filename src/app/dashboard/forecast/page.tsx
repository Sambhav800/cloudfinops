import { ForecastViewClient } from "@/components/dashboard/forecast-view-client";
import type { ForecastAccountSummary } from "@/components/dashboard/forecast-view";
import {
    getBackendIntegrations,
    getFinanceBudgetEvents,
    getFinanceForecast,
    getFinanceSpendHistory,
    syncFinanceBudgetEvents,
} from "@/lib/api";
import { syncUser } from "@/lib/sync-user";

export const dynamic = "force-dynamic";

export default async function ForecastPage() {
    let portfolioForecast = null as Awaited<ReturnType<typeof getFinanceForecast>>;
    let spendHistory = null as Awaited<ReturnType<typeof getFinanceSpendHistory>>;
    let accountForecasts: ForecastAccountSummary[] = [];
    let budgetEvents = [] as Awaited<ReturnType<typeof getFinanceBudgetEvents>>;
    let loadError: string | null = null;

    try {
        await syncUser();
        await syncFinanceBudgetEvents();

        const [forecastResult, historyResult, integrationsResult, budgetEventsResult] = await Promise.all([
            getFinanceForecast({ scope: "portfolio", days: 60 }),
            getFinanceSpendHistory({ scope: "portfolio", days: 60 }),
            getBackendIntegrations(),
            getFinanceBudgetEvents(6),
        ]);

        portfolioForecast = forecastResult;
        spendHistory = historyResult;
        budgetEvents = budgetEventsResult;

        const activeIntegrations = (integrationsResult ?? []).filter((integration) =>
            (integration.status || "").toLowerCase() === "active"
        );

        accountForecasts = await Promise.all(
            activeIntegrations.map(async (integration) => ({
                integration,
                forecast: await getFinanceForecast({
                    scope: "integration",
                    integrationId: integration.id,
                    days: 60,
                }),
            }))
        );
    } catch (error) {
        if (process.env.NODE_ENV === "development") {
            console.error("Forecast page load error:", error);
        }
        loadError = "Forecast data could not be loaded.";
    }

    return (
        <div className="min-h-screen bg-slate-950 text-slate-200">
            <div className="px-6 py-4">
                <h1 className="text-2xl font-bold text-white">Forecast</h1>
                <p className="text-sm text-slate-400">
                    Budget Copilot for portfolio and per-account month-end spend risk.
                </p>
            </div>
            <ForecastViewClient
                initialPortfolioForecast={portfolioForecast}
                initialSpendHistory={spendHistory}
                initialAccountForecasts={accountForecasts}
                initialBudgetEvents={budgetEvents}
                loadError={loadError}
            />
        </div>
    );
}
