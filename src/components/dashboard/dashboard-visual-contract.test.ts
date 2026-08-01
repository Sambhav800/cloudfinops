import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const dashboardPageSource = readFileSync(
    new URL("../../app/dashboard/page.tsx", import.meta.url),
    "utf8"
);
const sectionsSource = readFileSync(
    new URL("./dashboard-sections-client.tsx", import.meta.url),
    "utf8"
);
const overviewSource = readFileSync(new URL("./overview.tsx", import.meta.url), "utf8");
const costScoreSource = readFileSync(
    new URL("./cost-score-section.tsx", import.meta.url),
    "utf8"
);
const insightsSource = readFileSync(
    new URL("./finops-insights.tsx", import.meta.url),
    "utf8"
);
const financeSummarySource = readFileSync(
    new URL("./dashboard-finance-summary.tsx", import.meta.url),
    "utf8"
);
const forecastViewSource = readFileSync(
    new URL("./forecast-view.tsx", import.meta.url),
    "utf8"
);
const globalStylesSource = readFileSync(
    new URL("../../app/globals.css", import.meta.url),
    "utf8"
);
const resourcesPageSource = readFileSync(
    new URL("../../app/dashboard/resources/page.tsx", import.meta.url),
    "utf8"
);
const optimizerPageSource = readFileSync(
    new URL("../../app/dashboard/optimizer/page.tsx", import.meta.url),
    "utf8"
);
const arbitragePageSource = readFileSync(
    new URL("../../app/dashboard/arbitrage/page.tsx", import.meta.url),
    "utf8"
);
const resourcesViewSource = readFileSync(
    new URL("./resources-view.tsx", import.meta.url),
    "utf8"
);
const pendingActionsPageSource = readFileSync(
    new URL("../../app/dashboard/pending-actions/page.tsx", import.meta.url),
    "utf8"
);
const pendingActionsListClientSource = readFileSync(
    new URL("./pending-actions-list-client.tsx", import.meta.url),
    "utf8"
);
const actionsListSource = readFileSync(
    new URL("./actions-list.tsx", import.meta.url),
    "utf8"
);
const alertsViewSource = readFileSync(
    new URL("./alerts-view.tsx", import.meta.url),
    "utf8"
);
const reportsViewSource = readFileSync(
    new URL("./reports-view.tsx", import.meta.url),
    "utf8"
);
const commitmentsPageSource = readFileSync(
    new URL("../../app/dashboard/commitments/page.tsx", import.meta.url),
    "utf8"
);
const pendingActionsExecuteRouteSource = readFileSync(
    new URL("../../app/api/pending-actions/execute/route.ts", import.meta.url),
    "utf8"
);
const pendingActionsRejectRouteSource = readFileSync(
    new URL("../../app/api/pending-actions/reject/route.ts", import.meta.url),
    "utf8"
);
const pendingActionsFixRouteSource = readFileSync(
    new URL("../../app/api/pending-actions/generate-fix/route.ts", import.meta.url),
    "utf8"
);
const notificationsRouteSource = readFileSync(
    new URL("../../app/api/notifications/[notificationId]/route.ts", import.meta.url),
    "utf8"
);
const dashboardDataSource = readFileSync(
    new URL("../../lib/dashboard/data.ts", import.meta.url),
    "utf8"
);

test("dashboard sections define the provider filter tabs and pass activeProvider into the main sections", () => {
    assert.ok(sectionsSource.includes('const [activeProvider, setActiveProvider] = useState<"all" | "aws" | "azure" | "gcp">("all")'));
    assert.ok(sectionsSource.includes("All Providers"));
    assert.ok(sectionsSource.includes("Executive Overview"));
    assert.ok(sectionsSource.includes("Portfolio operating posture"));
    assert.ok(sectionsSource.includes("Provider Lens"));
    assert.ok(sectionsSource.includes("<CostScoreSection"));
    assert.ok(sectionsSource.includes("activeProvider={activeProvider}"));
    assert.ok(sectionsSource.includes("<FinOpsInsights stats={stats} activeProvider={activeProvider} />"));
    assert.ok(sectionsSource.includes("availableProviderCosts"));
    assert.ok(sectionsSource.includes("providerCost.resources > 0"));
    assert.ok(sectionsSource.includes("providerCost.savings > 0"));
    assert.ok(!sectionsSource.includes("AI-Powered Infrastructure Analysis"));
});

test("overview uses a direct recharts area chart and custom waste bars with empty-state messaging", () => {
    assert.ok(overviewSource.includes("from 'recharts'"));
    assert.ok(!overviewSource.includes("@tremor/react"));
    assert.ok(!overviewSource.includes("<Badge"));
    assert.ok(!overviewSource.includes("tremor-content"));
    assert.ok(overviewSource.includes("ResponsiveContainer"));
    assert.ok(overviewSource.includes("AreaChart"));
    assert.ok(overviewSource.includes("Portfolio spend over time"));
    assert.ok(overviewSource.includes("Waste Distribution"));
    assert.ok(overviewSource.includes("Estimated Waste Exposure"));
    assert.ok(overviewSource.includes("const totalWasteExposure = sortedWasteData.reduce"));
    assert.ok(overviewSource.includes("No waste detected"));
    assert.ok(overviewSource.includes("and {sortedWasteData.length - visibleWasteData.length} more"));
    assert.ok(overviewSource.includes("No spend history yet — run a scan to populate"));
    assert.ok(overviewSource.includes("animate-pulse"));
    assert.ok(overviewSource.includes("linearGradient id=\"spendGradient\""));
    assert.ok(overviewSource.includes("grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8"));
    assert.ok(overviewSource.includes("style={{ minHeight: '320px' }}"));
});

test("overview and optimizer monetary displays use INR formatters instead of visible dollar prefixes", () => {
    const dollarSign = String.fromCharCode(36);

    assert.ok(overviewSource.includes("formatInrCurrency"));
    assert.ok(overviewSource.includes("compactValueFormatter"));
    assert.ok(!overviewSource.includes("Intl.NumberFormat('en-US')"));
    assert.ok(!overviewSource.includes("item.value.toLocaleString()"));
    assert.ok(!overviewSource.includes("value >= 1000 ?"));
    assert.ok(!overviewSource.includes("Number(value).toLocaleString()"));
    assert.ok(optimizerPageSource.includes("formatInrCurrency(toDisplayInrAmount"));
    assert.ok(!optimizerPageSource.includes(dollarSign + dollarSign + "{formatCurrency("));
    assert.ok(arbitragePageSource.includes("formatAnalysisAmountInInr"));
    assert.ok(!arbitragePageSource.includes(" · " + dollarSign));
    assert.ok(forecastViewSource.includes("formatCompactCurrency(value, chartCurrency)"));
    assert.ok(!forecastViewSource.includes("? `" + dollarSign + dollarSign + "{"));
    assert.ok(!forecastViewSource.includes(": `" + dollarSign + dollarSign + "{"));
});

test("overview table uses provider-aware enterprise labels instead of mismatched id copy", () => {
    assert.ok(overviewSource.includes('<th className="w-[30%] p-4 font-medium">Resource</th>'));
    assert.ok(overviewSource.includes('<th className="w-[12%] p-4 font-medium">Provider</th>'));
    assert.ok(overviewSource.includes('<th className="w-[12%] p-4 font-medium text-right">Cost Signal</th>'));
    assert.ok(overviewSource.includes('min-w-[1080px] table-fixed'));
    assert.ok(overviewSource.includes("const visibleResources = [...filteredResources].sort"));
    assert.ok(overviewSource.includes('colSpan={6}'));
    assert.ok(!overviewSource.includes('Resource ID'));
});

test("daily spend trend uses flexible chart and empty-state containers so the card does not leave dead space below the chart", () => {
    assert.ok(overviewSource.includes('className="flex h-full flex-col"'));
    assert.ok(overviewSource.includes('className="mt-4 flex flex-1 items-center justify-center rounded-xl border border-dashed border-white/5 bg-white/[0.02]"'));
    assert.ok(overviewSource.includes('className="mt-4 flex-1 min-h-[240px]"'));
    assert.ok(overviewSource.includes('ResponsiveContainer width="100%" height="100%"'));
});

test("cost score section includes the custom provider donut and separates MTD spend from forecasts", () => {
    assert.ok(costScoreSource.includes("function ProviderDonut"));
    assert.ok(costScoreSource.includes("function getMaturityStage"));
    assert.ok(costScoreSource.includes("No provider data"));
    assert.ok(costScoreSource.includes("Spend by Provider"));
    assert.ok(costScoreSource.includes("const MIN_PCT = 0.04;"));
    assert.ok(costScoreSource.includes("100% of spend — single provider"));
    assert.ok(costScoreSource.includes("MTD Spend"));
    assert.ok(costScoreSource.includes("FinOps Maturity"));
    assert.ok(costScoreSource.includes("Savings Share"));
    assert.ok(costScoreSource.includes("AI Confidence"));
    assert.ok(costScoreSource.includes("Resources In Scope"));
    assert.ok(costScoreSource.includes("Optimization Baseline"));
    assert.ok(costScoreSource.includes("grid flex-1 grid-cols-1 gap-2 sm:grid-cols-2"));
    assert.ok(costScoreSource.includes("sm:col-span-2"));
    assert.ok(costScoreSource.includes("Monthly Opportunity"));
    assert.ok(costScoreSource.includes("Annualized Impact"));
    assert.ok(costScoreSource.includes("MTD Actual"));
    assert.ok(costScoreSource.includes("current calendar month to date"));
    assert.ok(costScoreSource.includes("/yr potential"));
    assert.ok(costScoreSource.includes("/yr if nothing changes"));
    assert.ok(costScoreSource.includes("border-t-2 border-t-indigo-500/60"));
    assert.ok(costScoreSource.includes("border-t-2 border-t-emerald-500/60"));
    assert.ok(costScoreSource.includes("border-t-2 border-t-rose-500/60"));
    assert.ok(costScoreSource.includes("border-t-2 border-t-sky-500/60"));
    assert.ok(!costScoreSource.includes("Projected post-optimization spend"));
});

test("insights and finance summary cards carry the new color accents", () => {
    assert.ok(insightsSource.includes("border-t-2 border-t-emerald-500/50"));
    assert.ok(insightsSource.includes("border-l-2 border-l-emerald-500/50"));
    assert.ok(insightsSource.includes("border-t-2 border-t-violet-500/50"));
    assert.ok(insightsSource.includes("border-t-2 border-t-teal-500/50"));
    assert.ok(insightsSource.includes("border-t-2 border-t-blue-500/50"));
    assert.ok(insightsSource.includes("Latest backend scan"));
    assert.ok(insightsSource.includes("bg-violet-500/15"));
    assert.ok(insightsSource.includes("bg-blue-500/15"));
    assert.ok(insightsSource.includes("Truck"));
    assert.ok(!insightsSource.includes("Model Used"));
    assert.ok(!insightsSource.includes("function LeavesIcon"));
    assert.ok(!insightsSource.includes("function CarIcon"));
    assert.ok(!dashboardDataSource.includes('model: "Gemini AI"'));
    assert.ok(financeSummarySource.includes("border-t-2 border-t-sky-400/60"));
    assert.ok(financeSummarySource.includes("border-t-2 border-t-violet-400/60"));
    assert.ok(financeSummarySource.includes("border-t-2 border-t-amber-400/60"));
    assert.ok(financeSummarySource.includes("border-t-2 border-t-emerald-400/60"));
    assert.ok(financeSummarySource.includes("border-b-2 border-b-sky-400/30"));
    assert.ok(financeSummarySource.includes("bg-emerald-400/15"));
});

test("dashboard page includes the monitored-resource status strip", () => {
    assert.ok(dashboardPageSource.includes("cost-tracked resources across"));
    assert.ok(dashboardPageSource.includes("inventory assets scanned"));
    assert.ok(dashboardPageSource.includes("Live data · refreshes on scan"));
    assert.ok(dashboardPageSource.includes("issues found"));
});

test("forecast view uses direct recharts for the richer forecast outlook and daily spend visuals", () => {
    assert.ok(forecastViewSource.includes('from "recharts"'));
    assert.ok(forecastViewSource.includes("ResponsiveContainer"));
    assert.ok(forecastViewSource.includes("AreaChart"));
    assert.ok(forecastViewSource.includes("ComposedChart"));
    assert.ok(forecastViewSource.includes("ReferenceLine"));
    assert.ok(forecastViewSource.includes("linearGradient"));
    assert.ok(forecastViewSource.includes("Recorded MTD"));
    assert.ok(forecastViewSource.includes("Projected runway"));
    assert.ok(forecastViewSource.includes("Budget headroom"));
    assert.ok(forecastViewSource.includes("14-day average"));
    assert.ok(forecastViewSource.includes("Peak recorded day"));
    assert.ok(forecastViewSource.includes("Actual MTD"));
    assert.ok(forecastViewSource.includes("Projected EOM"));
    assert.ok(forecastViewSource.includes("3-day average"));
    assert.ok(!forecastViewSource.includes('import { BarChart, Card, Text, Title } from "@tremor/react";'));
});

test("resources page and table include the Phase 3 badges, columns, and type summary strip", () => {
    assert.ok(resourcesPageSource.includes("border-t-2 border-t-indigo-500/60"));
    assert.ok(resourcesPageSource.includes("border-t-2 border-t-rose-500/60"));
    assert.ok(resourcesPageSource.includes("border-t-2 border-t-amber-500/60"));
    assert.ok(resourcesPageSource.includes("border-t-2 border-t-emerald-500/60"));
    assert.ok(resourcesPageSource.includes("Infrastructure health is stable"));
    assert.ok(!resourcesPageSource.includes("🎉"));
    assert.ok(resourcesViewSource.includes("const PROVIDER_COLORS: Record<string, string> ="));
    assert.ok(resourcesViewSource.includes("const typeCounts = initialResources.reduce"));
    assert.ok(resourcesViewSource.includes("Owner"));
    assert.ok(resourcesViewSource.includes("Cost Signal"));
    assert.ok(resourcesViewSource.includes("Annual Signal"));
    assert.ok(resourcesPageSource.includes("Known MTD Spend"));
    assert.ok(resourcesPageSource.includes("Cost-tracked Resources"));
    assert.ok(resourcesPageSource.includes("Inventory Assets"));
    assert.ok(resourcesPageSource.includes("No MTD actual yet"));
    assert.ok(resourcesViewSource.includes("type ResourceTab = 'costTracked' | 'all' | 'zombie' | 'shadow' | 'orphaned';"));
    assert.ok(resourcesViewSource.includes("const [activeTab, setActiveTab] = useState<ResourceTab>('costTracked');"));
    assert.ok(resourcesViewSource.includes("label: 'Cost Tracked'"));
    assert.ok(resourcesViewSource.includes("label: 'All Inventory'"));
    assert.ok(resourcesViewSource.includes("No resource-level cost match"));
    assert.ok(resourcesViewSource.includes("const visibleResources = [...currentData].sort"));
    assert.ok(resourcesViewSource.includes("resource.cost_label"));
    assert.ok(overviewSource.includes("item.costLabel || valueFormatter(item.cost)"));
    assert.ok(resourcesViewSource.includes("providerStyle.label"));
    assert.ok(resourcesViewSource.includes("resource.tags?.Owner"));
    assert.ok(resourcesViewSource.includes("Resources by Type"));
    assert.ok(resourcesViewSource.includes("Resources by Cloud"));
    assert.ok(resourcesViewSource.includes("const typeCountData ="));
    assert.ok(resourcesViewSource.includes("const byCloudData ="));
    assert.ok(resourcesViewSource.includes("from 'recharts'"));
});

test("resources view search and sorting tolerate sparse scanner rows", () => {
    assert.ok(resourcesViewSource.includes("function toSearchText(value: unknown): string"));
    assert.ok(resourcesViewSource.includes("function toDisplayText(value: unknown, fallback: string): string"));
    assert.ok(resourcesViewSource.includes("const normalizedSearchQuery = toSearchText(searchQuery);"));
    assert.ok(resourcesViewSource.includes("toSearchText(resource.resource_name).includes(normalizedSearchQuery)"));
    assert.ok(resourcesViewSource.includes("toSearchText(resource.created_by).includes(normalizedSearchQuery)"));
    assert.ok(resourcesViewSource.includes("toDisplayText(left.resource_name, 'Unknown resource').localeCompare"));
    assert.ok(resourcesViewSource.includes("const resourceName = toDisplayText(resource.resource_name, 'Unknown resource');"));
    assert.ok(!resourcesViewSource.includes("resource.resource_name.toLowerCase()"));
    assert.ok(!resourcesViewSource.includes("resource.created_by.toLowerCase()"));
    assert.ok(!resourcesViewSource.includes("left.resource_name.localeCompare"));
});

test("global styles do not force every recharts bar to the same color", () => {
    assert.ok(!globalStylesSource.includes(".recharts-bar-rectangle path"));
    assert.ok(!globalStylesSource.includes(".recharts-bar-rectangle rect"));
    assert.ok(!globalStylesSource.includes('.recharts-sector[name="Azure VM"]'));
    assert.ok(!globalStylesSource.includes('.recharts-sector[name="Azure Disk"]'));
    assert.ok(!globalStylesSource.includes('.recharts-sector[name="Azure Public IP"]'));
    assert.ok(!globalStylesSource.includes("recharts-pie-sector:nth-child(1)"));
    assert.ok(!globalStylesSource.includes("recharts-pie-sector:nth-child(2)"));
    assert.ok(!globalStylesSource.includes("recharts-pie-sector:nth-child(3)"));
});

test("pending actions list includes the OpsHLD savings KPI cards, charts, and action table columns", () => {
    assert.ok(actionsListSource.includes('from "recharts"'));
    assert.ok(actionsListSource.includes("Gem"));
    assert.ok(actionsListSource.includes("CheckCircle2"));
    assert.ok(actionsListSource.includes("Target"));
    assert.ok(actionsListSource.includes("const totalIdentified ="));
    assert.ok(actionsListSource.includes("const totalRealized ="));
    assert.ok(actionsListSource.includes("const totalPotential ="));
    assert.ok(actionsListSource.includes("const realizationRate ="));
    assert.ok(actionsListSource.includes("border-t-2 border-t-indigo-500/60"));
    assert.ok(actionsListSource.includes("border-t-2 border-t-emerald-500/60"));
    assert.ok(actionsListSource.includes("border-t-2 border-t-amber-500/60"));
    assert.ok(actionsListSource.includes("border-t-2 border-t-cyan-500/60"));
    assert.ok(actionsListSource.includes("Savings Trend"));
    assert.ok(actionsListSource.includes("Savings by Category"));
    assert.ok(actionsListSource.includes("const monthlyData ="));
    assert.ok(actionsListSource.includes("const categoryData ="));
    assert.ok(actionsListSource.includes("ResponsiveContainer"));
    assert.ok(actionsListSource.includes("LineChart"));
    assert.ok(actionsListSource.includes("BarChart"));
    assert.ok(actionsListSource.includes("Provider"));
    assert.ok(actionsListSource.includes("Annual Savings"));
    assert.ok(actionsListSource.includes("Impact"));
    assert.ok(actionsListSource.includes("Effort"));
    assert.ok(actionsListSource.includes("formatAnnualCurrency(totalIdentified)"));
    assert.ok(actionsListSource.includes("const providerColor ="));
    assert.ok(actionsListSource.includes("No pending actions yet"));
    assert.ok(actionsListSource.includes("No actions available for this filter"));
    assert.ok(actionsListSource.includes('useEffect(() => {'));
    assert.ok(actionsListSource.includes('setActions(initialActions);'));
    assert.ok(actionsListSource.includes('/api/pending-actions/execute'));
    assert.ok(actionsListSource.includes('/api/pending-actions/reject'));
    assert.ok(actionsListSource.includes('/api/pending-actions/generate-fix'));
    assert.ok(!actionsListSource.includes('aws ec2 terminate-instances'));
});

test("pending actions route no longer hides the live list behind an ssr:false dynamic wrapper", () => {
    assert.ok(!pendingActionsListClientSource.includes("dynamic("));
    assert.ok(!pendingActionsListClientSource.includes("ssr: false"));
    assert.ok(pendingActionsListClientSource.includes('import { PendingActionsList } from "@/components/dashboard/actions-list";'));
});

test("pending actions page renders the updated list directly from the active route", () => {
    assert.ok(pendingActionsPageSource.includes('import { PendingActionsList } from "@/components/dashboard/actions-list";'));
    assert.ok(pendingActionsPageSource.includes("<PendingActionsList initialActions={actions} />"));
    assert.ok(!pendingActionsPageSource.includes("PendingActionsListClient"));
});

test("pending actions route preserves the load-error banner path", () => {
    assert.ok(pendingActionsPageSource.includes('import { ErrorBanner } from "@/components/dashboard/error-banner";'));
    assert.ok(pendingActionsPageSource.includes("{loadError && <ErrorBanner message={loadError} />}"));
    assert.ok(pendingActionsListClientSource.includes("{loadError && <ErrorBanner message={loadError} />}"));
});

test("pending actions loader maps durable notification metadata before falling back to ids", () => {
    assert.ok(dashboardDataSource.includes("function mapPendingActionRow(action: NotificationRow): ActionItem"));
    assert.ok(dashboardDataSource.includes('meta["resource_name"]'));
    assert.ok(dashboardDataSource.includes('meta["resource_type"]'));
    assert.ok(dashboardDataSource.includes('meta["action_type"]'));
    assert.ok(dashboardDataSource.includes('meta["estimated_savings"] ?? meta["potential_savings"]'));
    assert.ok(dashboardDataSource.includes('meta["description"]'));
    assert.ok(dashboardDataSource.includes('meta["ai_reasoning"]'));
    assert.ok(dashboardDataSource.includes('pickFirstString('));
    assert.ok(dashboardDataSource.includes(".map((action) => mapPendingActionRow(action as NotificationRow));"));
});

test("commitments page derives coverage analytics from backend recommendation data instead of hardcoded spend numbers", () => {
    assert.ok(commitmentsPageSource.includes('/api/finance/commitment-recommendation'));
    assert.ok(commitmentsPageSource.includes('recommended_scenario'));
    assert.ok(commitmentsPageSource.includes('forecast_eom_spend_usd'));
    assert.ok(commitmentsPageSource.includes('commitment_pct'));
    assert.ok(!commitmentsPageSource.includes("const coverageData = ["));
    assert.ok(!commitmentsPageSource.includes("63%"));
    assert.ok(!commitmentsPageSource.includes("$19,663"));
    assert.ok(!commitmentsPageSource.includes("AWS US-East-1 (Compute)"));
});

test("pending action proxy routes delegate approve, reject, and script generation to backend endpoints", () => {
    assert.ok(pendingActionsExecuteRouteSource.includes('/api/execute-action'));
    assert.ok(pendingActionsRejectRouteSource.includes('/api/reject-action'));
    assert.ok(pendingActionsFixRouteSource.includes('/api/generate-fix'));
    assert.ok(pendingActionsExecuteRouteSource.includes('fetchWithBackendAuthFallback'));
    assert.ok(pendingActionsRejectRouteSource.includes('fetchWithBackendAuthFallback'));
    assert.ok(pendingActionsFixRouteSource.includes('fetchWithBackendAuthFallback'));
});

test("alerts view and reports view resync refreshed props instead of freezing initial client state", () => {
    assert.ok(alertsViewSource.includes('useEffect(() => {'));
    assert.ok(alertsViewSource.includes('setServerAlerts(initialAlerts);'));
    assert.ok(alertsViewSource.includes('/api/notifications/'));
    assert.ok(!alertsViewSource.includes('const mergedAlerts = useMemo'));
    assert.ok(reportsViewSource.includes('useEffect(() => {'));
    assert.ok(reportsViewSource.includes('setReports(initialReports);'));
});

test("notification mutation route marks alerts read and deletes them with user scoping", () => {
    assert.ok(notificationsRouteSource.includes('fetchWithBackendAuthFallback'));
    assert.ok(notificationsRouteSource.includes('/api/notifications/${encodeURIComponent(normalizedId)}'));
    assert.ok(notificationsRouteSource.includes('proxyNotificationMutation("PATCH"'));
    assert.ok(notificationsRouteSource.includes('proxyNotificationMutation("DELETE"'));
});
