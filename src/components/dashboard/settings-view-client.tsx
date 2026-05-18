"use client";

import dynamic from "next/dynamic";
import type { FinanceSettings } from "@/lib/api";
import { ErrorBanner } from "@/components/dashboard/error-banner";

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

const SettingsView = dynamic(() => import("@/components/dashboard/settings-view").then((mod) => mod.SettingsView), { ssr: false });

export function SettingsViewClient({
    initialAccounts,
    initialFinanceSettings,
    loadError,
}: {
    initialAccounts: IntegrationAccount[];
    initialFinanceSettings: FinanceSettings;
    loadError: string | null;
}) {
    return (
        <div className="space-y-4">
            {loadError && <ErrorBanner message={loadError} />}
            <SettingsView initialAccounts={initialAccounts} initialFinanceSettings={initialFinanceSettings} />
        </div>
    );
}
