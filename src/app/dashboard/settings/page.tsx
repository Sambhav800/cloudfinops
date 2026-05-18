import { SettingsViewClient } from "@/components/dashboard/settings-view-client";
import {
    getBackendIntegrations,
    getFinanceSettings,
    type BackendIntegration,
    type FinanceSettings,
} from "@/lib/api";

export const dynamic = "force-dynamic";

interface IntegrationAccount {
    id: string;
    name: string;
    provider: string;
    account_identifier: string;
    status: string;
    last_scan: string | null;
    created_at: string;
    monthly_budget_limit?: number | null;
    alert_phone_number_masked?: string | null;
    alert_slack_webhook_configured?: boolean;
}

const DEFAULT_FINANCE_SETTINGS: FinanceSettings = {
    portfolio_budget_limit: null,
    report_recipients: [],
    report_cadence: "weekly",
    alert_thresholds: {
        warning_pct: 80,
        critical_pct: 100,
    },
};

function toSettingsAccounts(integrations: BackendIntegration[]): IntegrationAccount[] {
    const uniqueMap = new Map<string, IntegrationAccount>();

    for (const integration of integrations) {
        const account: IntegrationAccount = {
            id: integration.id,
            name: integration.name,
            provider: integration.provider,
            account_identifier: integration.account_identifier || "Connected Account",
            status: integration.status,
            last_scan: integration.last_scan,
            created_at: integration.created_at || "",
            monthly_budget_limit: integration.monthly_budget_limit ?? null,
            alert_phone_number_masked: integration.alert_phone_number_masked ?? null,
            alert_slack_webhook_configured: integration.alert_slack_webhook_configured ?? false,
        };

        const key = account.account_identifier || account.name;
        const existing = uniqueMap.get(key);
        if (!existing || new Date(account.created_at) > new Date(existing.created_at)) {
            uniqueMap.set(key, account);
        }
    }

    return Array.from(uniqueMap.values());
}

export default async function SettingsPage() {
    let accounts: IntegrationAccount[] = [];
    let financeSettings: FinanceSettings = DEFAULT_FINANCE_SETTINGS;
    let loadError: string | null = null;

    try {
        const [integrations, fetchedFinanceSettings] = await Promise.all([
            getBackendIntegrations(),
            getFinanceSettings(),
        ]);
        if (integrations) {
            accounts = toSettingsAccounts(integrations);
        }
        if (fetchedFinanceSettings) {
            financeSettings = fetchedFinanceSettings;
        }
    } catch (error) {
        if (process.env.NODE_ENV === "development") {
            console.error("Settings page load error:", error);
        }
        loadError = error instanceof Error ? error.message : "Failed to load settings";
    }

    return <SettingsViewClient initialAccounts={accounts} initialFinanceSettings={financeSettings} loadError={loadError} />;
}
