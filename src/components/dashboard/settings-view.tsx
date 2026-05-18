"use client";

import {
    Bell,
    Cloud,
    Plus,
    Settings2,
    Shield,
    Trash2,
} from "lucide-react";
import { useState, useSyncExternalStore } from "react";
import { useAuth } from "@clerk/nextjs";
import { useRouter } from "next/navigation";

import { buildBackendAuthHeaders } from "@/app/api/_shared/fetch-with-backend-auth-fallback";
import { ConnectCloudForm } from "@/components/dashboard/connect-cloud-form";
import { BillUploadForm } from "@/components/dashboard/bill-upload-form";
import type { FinanceReportCadence, FinanceSettings } from "@/lib/api";
import { deleteCloudAccount } from "@/app/actions/accounts";
import { useScan } from "@/components/dashboard/scan-provider";
import { useNotifications } from "@/components/dashboard/notification-provider";
import { formatInrCurrency } from "@/lib/resources/contract";

const emptySubscribe = () => () => { };
const surfaceClassName = "bg-slate-900/50 backdrop-blur-xl border border-white/10 rounded-2xl";
const modalOverlayClassName = "fixed inset-0 z-[200] grid place-items-center overflow-y-auto bg-black/60 p-4 backdrop-blur-sm sm:p-6";
const modalPanelBaseClassName = "my-auto max-h-[calc(100vh-2rem)] w-full overflow-y-auto overscroll-contain rounded-2xl border border-white/10 bg-slate-900 p-6 shadow-2xl sm:max-h-[calc(100vh-3rem)]";

type SettingsTab = "finance-controls" | "cloud-accounts";
type StatusNotice = { type: "success" | "error"; message: string } | null;

function FormattedDate({ date }: { date: string }) {
    const formatted = useSyncExternalStore(
        emptySubscribe,
        () => new Date(date).toLocaleString(),
        () => ""
    );

    if (!formatted) return <span className="opacity-0">Loading...</span>;
    return <>{formatted}</>;
}

function splitReportRecipients(rawValue: string): string[] {
    return rawValue
        .split(/[\n,]+/)
        .map((value) => value.trim())
        .filter(Boolean);
}

function maskPhoneNumber(value: string): string | null {
    const digits = value.replace(/\D/g, "");
    if (digits.length < 4) {
        return null;
    }
    return `***${digits.slice(-4)}`;
}

function formatCurrency(value?: number | null): string {
    if (typeof value !== "number" || Number.isNaN(value)) {
        return "Not set";
    }
    return formatInrCurrency(value, {
        minimumFractionDigits: 0,
        maximumFractionDigits: 0,
    });
}

function formatValidationLocation(location: unknown): string {
    if (!Array.isArray(location)) {
        return "";
    }

    const parts = location
        .map((segment) =>
            typeof segment === "string" || typeof segment === "number"
                ? String(segment)
                : ""
        )
        .filter(Boolean);

    const normalizedParts = parts[0] === "body" ? parts.slice(1) : parts;
    return normalizedParts.join(".");
}

function formatApiErrorDetail(detail: unknown, fallbackMessage: string): string {
    if (typeof detail === "string") {
        return detail.trim() || fallbackMessage;
    }

    if (Array.isArray(detail)) {
        const messages = detail
            .map((item) => {
                if (typeof item === "string") {
                    return item.trim();
                }

                if (!item || typeof item !== "object") {
                    return "";
                }

                const message = typeof (item as { msg?: unknown }).msg === "string"
                    ? (item as { msg: string }).msg.trim()
                    : "";
                const location = formatValidationLocation((item as { loc?: unknown }).loc);

                if (location && message) {
                    return `${location}: ${message}`;
                }
                return message;
            })
            .filter(Boolean);

        return messages.length > 0 ? messages.join(" ") : fallbackMessage;
    }

    if (detail && typeof detail === "object" && "detail" in detail) {
        return formatApiErrorDetail(
            (detail as { detail?: unknown }).detail,
            fallbackMessage
        );
    }

    return fallbackMessage;
}

function StatusBanner({ status }: { status: StatusNotice }) {
    if (!status) {
        return null;
    }

    return (
        <div
            className={`rounded-xl border px-4 py-3 text-sm ${status.type === "success"
                ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-200"
                : "border-rose-500/30 bg-rose-500/10 text-rose-200"
                }`}
        >
            {status.message}
        </div>
    );
}

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

interface SettingsViewProps {
    initialAccounts: IntegrationAccount[];
    initialFinanceSettings: FinanceSettings;
}

export function SettingsView({
    initialAccounts,
    initialFinanceSettings,
}: SettingsViewProps) {
    const { getToken, userId } = useAuth();
    const router = useRouter();
    const { resetScan } = useScan();
    const { clearAllNotifications } = useNotifications();

    const [activeTab, setActiveTab] = useState<SettingsTab>("finance-controls");
    const [addAccountMode, setAddAccountMode] = useState<"selection" | "deep-scan" | "bill-upload" | null>(null);
    const [configAccount, setConfigAccount] = useState<IntegrationAccount | null>(null);

    const [accounts, setAccounts] = useState(initialAccounts);
    const [financeSettings, setFinanceSettings] = useState(initialFinanceSettings);

    const [portfolioBudgetLimit, setPortfolioBudgetLimit] = useState(
        initialFinanceSettings.portfolio_budget_limit != null
            ? String(initialFinanceSettings.portfolio_budget_limit)
            : ""
    );
    const [reportRecipientsInput, setReportRecipientsInput] = useState(
        initialFinanceSettings.report_recipients.join(", ")
    );
    const [reportCadence, setReportCadence] = useState<FinanceReportCadence>(
        initialFinanceSettings.report_cadence
    );
    const [warningThresholdPct, setWarningThresholdPct] = useState(
        String(initialFinanceSettings.alert_thresholds.warning_pct)
    );
    const [criticalThresholdPct, setCriticalThresholdPct] = useState(
        String(initialFinanceSettings.alert_thresholds.critical_pct)
    );

    const [budgetLimit, setBudgetLimit] = useState("");
    const [whatsappNumber, setWhatsappNumber] = useState("");
    const [slackWebhook, setSlackWebhook] = useState("");
    const [clearPhoneNumber, setClearPhoneNumber] = useState(false);
    const [clearSlackWebhook, setClearSlackWebhook] = useState(false);

    const [isSavingFinance, setIsSavingFinance] = useState(false);
    const [isSavingAccount, setIsSavingAccount] = useState(false);
    const [financeStatus, setFinanceStatus] = useState<StatusNotice>(null);
    const [accountStatus, setAccountStatus] = useState<StatusNotice>(null);

    const tabs = [
        { id: "finance-controls" as const, name: "Finance Controls", icon: Bell },
        { id: "cloud-accounts" as const, name: "Cloud Accounts", icon: Cloud },
    ];

    async function buildAuthHeaders(url: string): Promise<Record<string, string>> {
        let token = await getToken();
        if (!token) {
            try {
                token = await getToken({ template: "default" });
            } catch {
                token = null;
            }
        }

        const requestUrl = typeof window === "undefined"
            ? url
            : new URL(url, window.location.origin).toString();

        return buildBackendAuthHeaders(requestUrl, {
            token,
            userId: userId ?? null,
        }, {
            "Content-Type": "application/json",
        });
    }

    async function handleDelete(id: string, name: string) {
        if (!confirm(`Are you sure you want to delete ${name}? This action cannot be undone.`)) return;

        const res = await deleteCloudAccount(id);
        if (res.success) {
            setAccounts((prev) => prev.filter((account) => account.id !== id));
            resetScan();
            clearAllNotifications();
            router.refresh();
        } else {
            setAccountStatus({
                type: "error",
                message: res.error || "Failed to delete cloud account.",
            });
        }
    }

    function openAccountSettings(account: IntegrationAccount) {
        setConfigAccount(account);
        setBudgetLimit(
            account.monthly_budget_limit != null ? String(account.monthly_budget_limit) : ""
        );
        setWhatsappNumber("");
        setSlackWebhook("");
        setClearPhoneNumber(false);
        setClearSlackWebhook(false);
        setAccountStatus(null);
    }

    async function handleSaveFinanceSettings() {
        setFinanceStatus(null);

        const trimmedPortfolioBudgetLimit = portfolioBudgetLimit.trim();
        const parsedPortfolioBudgetLimit = trimmedPortfolioBudgetLimit
            ? Number(trimmedPortfolioBudgetLimit)
            : null;
        const parsedWarningThresholdPct = Number(warningThresholdPct);
        const parsedCriticalThresholdPct = Number(criticalThresholdPct);

        if (
            trimmedPortfolioBudgetLimit &&
            (
                parsedPortfolioBudgetLimit == null ||
                !Number.isFinite(parsedPortfolioBudgetLimit) ||
                parsedPortfolioBudgetLimit < 0
            )
        ) {
            setFinanceStatus({
                type: "error",
                message: "Portfolio budget must be 0 or higher.",
            });
            return;
        }

        if (
            !Number.isFinite(parsedWarningThresholdPct) ||
            parsedWarningThresholdPct < 1 ||
            parsedWarningThresholdPct > 100
        ) {
            setFinanceStatus({
                type: "error",
                message: "Warning threshold must be between 1% and 100%.",
            });
            return;
        }

        if (
            !Number.isFinite(parsedCriticalThresholdPct) ||
            parsedCriticalThresholdPct < 1 ||
            parsedCriticalThresholdPct > 200
        ) {
            setFinanceStatus({
                type: "error",
                message: "Critical threshold must be between 1% and 200%.",
            });
            return;
        }

        if (parsedCriticalThresholdPct < parsedWarningThresholdPct) {
            setFinanceStatus({
                type: "error",
                message: "Critical threshold must be greater than or equal to the warning threshold.",
            });
            return;
        }

        setIsSavingFinance(true);

        try {
            const response = await fetch("/api/finance/settings", {
                method: "PUT",
                headers: await buildAuthHeaders("/api/finance/settings"),
                body: JSON.stringify({
                    portfolio_budget_limit: parsedPortfolioBudgetLimit,
                    report_recipients: splitReportRecipients(reportRecipientsInput),
                    report_cadence: reportCadence,
                    alert_thresholds: {
                        warning_pct: parsedWarningThresholdPct,
                        critical_pct: parsedCriticalThresholdPct,
                    },
                }),
            });

            const payload = await response.json().catch(() => null);
            if (!response.ok) {
                throw new Error(
                    formatApiErrorDetail(
                        payload?.detail ?? payload,
                        "Failed to save finance settings."
                    )
                );
            }

            const updatedSettings = payload as FinanceSettings;
            setFinanceSettings(updatedSettings);
            setPortfolioBudgetLimit(
                updatedSettings.portfolio_budget_limit != null
                    ? String(updatedSettings.portfolio_budget_limit)
                    : ""
            );
            setReportRecipientsInput(updatedSettings.report_recipients.join(", "));
            setReportCadence(updatedSettings.report_cadence);
            setWarningThresholdPct(String(updatedSettings.alert_thresholds.warning_pct));
            setCriticalThresholdPct(String(updatedSettings.alert_thresholds.critical_pct));
            setFinanceStatus({
                type: "success",
                message: "Finance preferences saved.",
            });
            router.refresh();
        } catch (error) {
            setFinanceStatus({
                type: "error",
                message: error instanceof Error ? error.message : "Failed to save finance settings.",
            });
        } finally {
            setIsSavingFinance(false);
        }
    }

    async function handleSaveAccountSettings() {
        if (!configAccount) return;

        setIsSavingAccount(true);
        setAccountStatus(null);

        try {
            const body: Record<string, unknown> = {
                monthly_budget_limit: budgetLimit.trim() ? parseFloat(budgetLimit) : null,
            };

            if (whatsappNumber.trim() || clearPhoneNumber) {
                body.alert_phone_number = clearPhoneNumber ? null : whatsappNumber.trim();
            }

            if (slackWebhook.trim() || clearSlackWebhook) {
                body.alert_slack_webhook = clearSlackWebhook ? null : slackWebhook.trim();
            }

            const response = await fetch(`/api/integrations/${configAccount.id}/settings`, {
                method: "PUT",
                headers: await buildAuthHeaders(`/api/integrations/${configAccount.id}/settings`),
                body: JSON.stringify(body),
            });
            const payload = await response.json().catch(() => null);

            if (!response.ok) {
                throw new Error(
                    formatApiErrorDetail(
                        payload?.detail ?? payload,
                        "Failed to save account settings."
                    )
                );
            }

            const nextBudget = budgetLimit.trim() ? parseFloat(budgetLimit) : null;
            setAccounts((prev) =>
                prev.map((account) => {
                    if (account.id !== configAccount.id) {
                        return account;
                    }

                    return {
                        ...account,
                        monthly_budget_limit: nextBudget,
                        alert_phone_number_masked: clearPhoneNumber
                            ? null
                            : whatsappNumber.trim()
                                ? maskPhoneNumber(whatsappNumber.trim())
                                : account.alert_phone_number_masked,
                        alert_slack_webhook_configured: clearSlackWebhook
                            ? false
                            : slackWebhook.trim()
                                ? true
                                : account.alert_slack_webhook_configured,
                    };
                })
            );

            setConfigAccount(null);
            setAccountStatus({
                type: "success",
                message: `Saved settings for ${configAccount.name}.`,
            });
            router.refresh();
        } catch (error) {
            setAccountStatus({
                type: "error",
                message: error instanceof Error ? error.message : "Failed to save account settings.",
            });
        } finally {
            setIsSavingAccount(false);
        }
    }

    return (
        <>
            <div className="min-h-screen p-6">
            <div className="flex flex-col gap-6 lg:flex-row">
                <div className="lg:w-64 lg:flex-shrink-0">
                    <nav className={`${surfaceClassName} space-y-1 p-2`}>
                        {tabs.map((tab) => (
                            <button
                                key={tab.id}
                                onClick={() => setActiveTab(tab.id)}
                                className={`flex w-full items-center gap-3 rounded-xl px-4 py-3 text-left transition-colors ${activeTab === tab.id
                                    ? "bg-primary text-black font-medium"
                                    : "text-gray-400 hover:bg-white/5 hover:text-white"
                                    }`}
                            >
                                <tab.icon className="h-5 w-5" />
                                {tab.name}
                            </button>
                        ))}
                    </nav>
                </div>

                <div className="flex-1">
                    <div className={`${surfaceClassName} p-6`}>
                        {activeTab === "finance-controls" && (
                            <div className="space-y-6">
                                <div>
                                    <h2 className="text-xl font-bold text-white">Finance Controls</h2>
                                    <p className="mt-1 text-sm text-gray-400">
                                        Set the portfolio budget, scheduled report delivery, and budget-alert thresholds that power Release 1.
                                    </p>
                                </div>

                                <StatusBanner status={financeStatus} />

                                <div className="grid gap-6 xl:grid-cols-[1.35fr_1fr]">
                                    <section className="rounded-2xl border border-white/5 bg-black/20 p-5">
                                        <h3 className="text-lg font-semibold text-white">Portfolio Budget</h3>
                                        <p className="mt-1 text-sm text-gray-400">
                                            Leave this empty to let forecast and reports fall back to the sum of active account budgets.
                                        </p>
                                        <div className="mt-5 grid gap-4 md:grid-cols-[minmax(0,1fr)_220px]">
                                            <label className="space-y-2">
                                                <span className="text-sm font-medium text-gray-300">Portfolio monthly budget (INR)</span>
                                                <input
                                                    type="number"
                                                    min="0"
                                                    step="0.01"
                                                    value={portfolioBudgetLimit}
                                                    onChange={(event) => setPortfolioBudgetLimit(event.target.value)}
                                                    placeholder="1400000"
                                                    className="w-full rounded-xl border border-white/10 bg-black/40 px-4 py-3 text-white placeholder:text-gray-600 focus:border-primary focus:outline-none"
                                                />
                                            </label>
                                            <div className="rounded-2xl border border-emerald-500/15 bg-emerald-500/5 p-4">
                                                <p className="text-xs uppercase tracking-[0.22em] text-emerald-200/75">Current Target</p>
                                                <p className="mt-3 text-2xl font-semibold text-white">
                                                    {formatCurrency(financeSettings.portfolio_budget_limit)}
                                                </p>
                                                <p className="mt-2 text-sm text-gray-400">
                                                    Forecast falls back to account budgets when no portfolio ceiling is configured.
                                                </p>
                                            </div>
                                        </div>
                                    </section>

                                    <section className="rounded-2xl border border-white/5 bg-black/20 p-5">
                                        <h3 className="text-lg font-semibold text-white">Scheduled Reports</h3>
                                        <p className="mt-1 text-sm text-gray-400">
                                            Send executive summaries to finance or leadership without granting write access to your cloud accounts.
                                        </p>
                                        <div className="mt-5 space-y-4">
                                            <label className="space-y-2">
                                                <span className="text-sm font-medium text-gray-300">Report recipients</span>
                                                <textarea
                                                    value={reportRecipientsInput}
                                                    onChange={(event) => setReportRecipientsInput(event.target.value)}
                                                    placeholder="finance@company.com, cto@company.com"
                                                    rows={4}
                                                    className="w-full rounded-xl border border-white/10 bg-black/40 px-4 py-3 text-white placeholder:text-gray-600 focus:border-primary focus:outline-none"
                                                />
                                                <p className="text-xs text-gray-500">
                                                    Separate recipients with commas or new lines. Leave empty to use the synced account email as the fallback.
                                                </p>
                                            </label>

                                            <label className="space-y-2">
                                                <span className="text-sm font-medium text-gray-300">Report cadence</span>
                                                <select
                                                    value={reportCadence}
                                                    onChange={(event) => setReportCadence(event.target.value as FinanceReportCadence)}
                                                    className="w-full rounded-xl border border-white/10 bg-black/40 px-4 py-3 text-white focus:border-primary focus:outline-none"
                                                >
                                                    <option value="manual">Manual only</option>
                                                    <option value="weekly">Weekly</option>
                                                    <option value="monthly">Monthly</option>
                                                </select>
                                            </label>
                                        </div>
                                    </section>
                                </div>

                                <section className="rounded-2xl border border-white/5 bg-black/20 p-5">
                                    <h3 className="text-lg font-semibold text-white">Budget Alert Thresholds</h3>
                                    <p className="mt-1 text-sm text-gray-400">
                                        Warning thresholds drive the “approaching budget” state before a forecasted overrun happens.
                                    </p>
                                    <div className="mt-5 grid gap-4 md:grid-cols-2">
                                        <label className="space-y-2">
                                            <span className="text-sm font-medium text-gray-300">Warning threshold (%)</span>
                                            <input
                                                type="number"
                                                min="1"
                                                max="100"
                                                step="1"
                                                value={warningThresholdPct}
                                                onChange={(event) => setWarningThresholdPct(event.target.value)}
                                                className="w-full rounded-xl border border-white/10 bg-black/40 px-4 py-3 text-white placeholder:text-gray-600 focus:border-primary focus:outline-none"
                                            />
                                        </label>
                                        <label className="space-y-2">
                                            <span className="text-sm font-medium text-gray-300">Critical threshold (%)</span>
                                            <input
                                                type="number"
                                                min="1"
                                                max="200"
                                                step="1"
                                                value={criticalThresholdPct}
                                                onChange={(event) => setCriticalThresholdPct(event.target.value)}
                                                className="w-full rounded-xl border border-white/10 bg-black/40 px-4 py-3 text-white placeholder:text-gray-600 focus:border-primary focus:outline-none"
                                            />
                                        </label>
                                    </div>
                                </section>

                                <div className="flex justify-end">
                                    <button
                                        onClick={handleSaveFinanceSettings}
                                        disabled={isSavingFinance}
                                        className="rounded-xl bg-primary px-5 py-3 font-medium text-black transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
                                    >
                                        {isSavingFinance ? "Saving..." : "Save Finance Settings"}
                                    </button>
                                </div>
                            </div>
                        )}

                        {activeTab === "cloud-accounts" && (
                            <div className="space-y-6">
                                <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                                    <div>
                                        <h2 className="text-xl font-bold text-white">Cloud Accounts</h2>
                                        <p className="mt-1 text-sm text-gray-400">
                                            Manage connected accounts, set per-account budgets, and control WhatsApp or Slack destinations for budget alerts.
                                        </p>
                                    </div>
                                    <button
                                        onClick={() => setAddAccountMode("selection")}
                                        className="inline-flex items-center gap-2 rounded-xl bg-primary px-4 py-2.5 font-medium text-black transition-colors hover:bg-primary/90"
                                    >
                                        <Plus className="h-4 w-4" />
                                        Add Account
                                    </button>
                                </div>

                                <StatusBanner status={accountStatus} />

                                <div className="space-y-3">
                                    {accounts.length === 0 ? (
                                        <div className="rounded-2xl border border-dashed border-white/10 bg-black/20 px-6 py-10 text-center text-gray-500">
                                            No accounts connected yet.
                                        </div>
                                    ) : (
                                        accounts.map((account) => (
                                            <div
                                                key={account.id}
                                                className="flex flex-col gap-4 rounded-2xl border border-white/5 bg-black/20 p-4 lg:flex-row lg:items-center lg:justify-between"
                                            >
                                                <div className="flex items-start gap-4">
                                                    <div className={`rounded-full px-3 py-1 text-sm font-medium ${account.provider === "aws"
                                                        ? "bg-orange-500/10 text-orange-300"
                                                        : account.provider === "azure"
                                                            ? "bg-sky-500/10 text-sky-300"
                                                            : "bg-emerald-500/10 text-emerald-300"
                                                        }`}>
                                                        {account.provider.toUpperCase()}
                                                    </div>
                                                    <div className="space-y-2">
                                                        <div>
                                                            <p className="font-medium text-white">{account.name}</p>
                                                            <p className="text-sm font-mono text-gray-500">
                                                                {account.account_identifier || "Connected account"}
                                                            </p>
                                                        </div>
                                                        <div className="flex flex-wrap gap-2 text-xs">
                                                            <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-gray-300">
                                                                Budget: {formatCurrency(account.monthly_budget_limit)}
                                                            </span>
                                                            <span className={`rounded-full border px-3 py-1 ${account.alert_phone_number_masked
                                                                ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-200"
                                                                : "border-white/10 bg-white/5 text-gray-400"
                                                                }`}>
                                                                WhatsApp: {account.alert_phone_number_masked || "Not configured"}
                                                            </span>
                                                            <span className={`rounded-full border px-3 py-1 ${account.alert_slack_webhook_configured
                                                                ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-200"
                                                                : "border-white/10 bg-white/5 text-gray-400"
                                                                }`}>
                                                                Slack: {account.alert_slack_webhook_configured ? "Configured" : "Not configured"}
                                                            </span>
                                                        </div>
                                                    </div>
                                                </div>

                                                <div className="flex items-center gap-4">
                                                    <div className="text-right">
                                                        <span className={`rounded-full px-2 py-1 text-xs font-medium ${account.status === "active"
                                                            ? "bg-green-500/10 text-green-400"
                                                            : "bg-yellow-500/10 text-yellow-400"
                                                            }`}>
                                                            {account.status}
                                                        </span>
                                                        <p className="mt-1 text-xs text-gray-600">
                                                            {account.last_scan ? (
                                                                <>Last scan: <FormattedDate date={account.last_scan} /></>
                                                            ) : "Never scanned"}
                                                        </p>
                                                    </div>

                                                    <button
                                                        onClick={() => openAccountSettings(account)}
                                                        className="rounded-lg p-2 text-gray-500 transition-colors hover:bg-blue-500/10 hover:text-blue-300"
                                                        title="Configure budget and alerts"
                                                    >
                                                        <Settings2 className="h-4 w-4" />
                                                    </button>
                                                    <button
                                                        onClick={() => handleDelete(account.id, account.name)}
                                                        className="rounded-lg p-2 text-gray-500 transition-colors hover:bg-red-500/10 hover:text-red-400"
                                                        title="Delete account"
                                                    >
                                                        <Trash2 className="h-4 w-4" />
                                                    </button>
                                                </div>
                                            </div>
                                        ))
                                    )}
                                </div>

                            </div>
                        )}
                    </div>
                </div>
            </div>
            </div>

            {addAccountMode === "selection" && (
                <div className={modalOverlayClassName}>
                    <div className={`${modalPanelBaseClassName} max-w-2xl`}>
                        <div className="mb-6 flex items-center justify-between">
                            <h2 className="text-xl font-bold text-white">Choose Analysis Mode</h2>
                            <button
                                onClick={() => setAddAccountMode(null)}
                                className="text-gray-400 hover:text-white"
                            >
                                ✕
                            </button>
                        </div>
                        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                            <button
                                type="button"
                                onClick={() => setAddAccountMode("deep-scan")}
                                className="rounded-xl border border-white/10 bg-black/30 p-5 text-left hover:bg-white/5"
                            >
                                <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-primary/20 text-primary">
                                    <Shield className="h-5 w-5" />
                                </div>
                                <h3 className="font-semibold text-white">Live Connection</h3>
                                <p className="mt-1 text-sm text-gray-400">
                                    Connect cloud API credentials for deep infrastructure scans.
                                </p>
                            </button>
                            <button
                                type="button"
                                onClick={() => setAddAccountMode("bill-upload")}
                                className="rounded-xl border border-blue-500/25 bg-blue-500/10 p-5 text-left hover:bg-blue-500/15"
                            >
                                <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-blue-500/20 text-blue-300">
                                    <Bell className="h-5 w-5" />
                                </div>
                                <h3 className="font-semibold text-white">Zero-Risk Bill Scan</h3>
                                <p className="mt-1 text-sm text-gray-400">
                                    Upload bills or configure automated billing sync without compute write access.
                                </p>
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {addAccountMode === "deep-scan" && (
                <div className={modalOverlayClassName}>
                    <div className={`${modalPanelBaseClassName} max-w-md`}>
                        <div className="mb-4 flex items-center gap-3">
                            <button
                                onClick={() => setAddAccountMode("selection")}
                                className="text-gray-400 hover:text-white"
                            >
                                ← Back
                            </button>
                            <h2 className="text-xl font-bold text-white">Add Cloud Account</h2>
                        </div>
                        <ConnectCloudForm onCancel={() => setAddAccountMode(null)} />
                    </div>
                </div>
            )}

            {addAccountMode === "bill-upload" && (
                <div className={modalOverlayClassName}>
                    <div className={`${modalPanelBaseClassName} max-w-lg`}>
                        <div className="mb-4 flex items-center gap-3">
                            <button
                                onClick={() => setAddAccountMode("selection")}
                                className="text-gray-400 hover:text-white"
                            >
                                ← Back
                            </button>
                            <h2 className="text-xl font-bold text-white">Bill Analysis Setup</h2>
                        </div>
                        <BillUploadForm onCancel={() => setAddAccountMode(null)} />
                    </div>
                </div>
            )}

            {configAccount && (
                <div className={modalOverlayClassName}>
                    <div className={`${modalPanelBaseClassName} max-w-md`}>
                        <div className="mb-4">
                            <h2 className="text-xl font-bold text-white">Configure Account Budget & Alerts</h2>
                            <p className="mt-1 text-sm text-gray-400">
                                Update the budget ceiling and delivery destinations for {configAccount.name}.
                            </p>
                        </div>

                        <StatusBanner status={accountStatus} />

                        <div className="mt-4 space-y-4">
                            <label className="space-y-2">
                                <span className="text-sm font-medium text-gray-300">Monthly budget limit (INR)</span>
                                <input
                                    type="number"
                                    min="0"
                                    step="0.01"
                                    value={budgetLimit}
                                    onChange={(event) => setBudgetLimit(event.target.value)}
                                    placeholder="415000"
                                    className="w-full rounded-xl border border-white/10 bg-black/40 px-4 py-3 text-white placeholder:text-gray-600 focus:border-primary focus:outline-none"
                                />
                            </label>

                            <div className="space-y-2">
                                <label className="text-sm font-medium text-gray-300">WhatsApp notification number</label>
                                <input
                                    type="text"
                                    value={whatsappNumber}
                                    onChange={(event) => setWhatsappNumber(event.target.value)}
                                    placeholder="+919876543210"
                                    className="w-full rounded-xl border border-white/10 bg-black/40 px-4 py-3 text-white placeholder:text-gray-600 focus:border-primary focus:outline-none"
                                />
                                <div className="flex items-center justify-between text-xs text-gray-500">
                                    <span>
                                        Current: {configAccount.alert_phone_number_masked || "Not configured"}
                                    </span>
                                    {configAccount.alert_phone_number_masked && (
                                        <button
                                            type="button"
                                            onClick={() => setClearPhoneNumber((current) => !current)}
                                            className={`rounded-full px-2 py-1 ${clearPhoneNumber
                                                ? "bg-rose-500/15 text-rose-200"
                                                : "bg-white/5 text-gray-300"
                                                }`}
                                        >
                                            {clearPhoneNumber ? "Will remove" : "Remove current"}
                                        </button>
                                    )}
                                </div>
                            </div>

                            <div className="space-y-2">
                                <label className="text-sm font-medium text-gray-300">Slack webhook URL</label>
                                <input
                                    type="url"
                                    value={slackWebhook}
                                    onChange={(event) => setSlackWebhook(event.target.value)}
                                    placeholder="https://hooks.slack.com/services/..."
                                    className="w-full rounded-xl border border-white/10 bg-black/40 px-4 py-3 text-white placeholder:text-gray-600 focus:border-primary focus:outline-none"
                                />
                                <div className="flex items-center justify-between text-xs text-gray-500">
                                    <span>
                                        Current: {configAccount.alert_slack_webhook_configured ? "Configured" : "Not configured"}
                                    </span>
                                    {configAccount.alert_slack_webhook_configured && (
                                        <button
                                            type="button"
                                            onClick={() => setClearSlackWebhook((current) => !current)}
                                            className={`rounded-full px-2 py-1 ${clearSlackWebhook
                                                ? "bg-rose-500/15 text-rose-200"
                                                : "bg-white/5 text-gray-300"
                                                }`}
                                        >
                                            {clearSlackWebhook ? "Will remove" : "Remove current"}
                                        </button>
                                    )}
                                </div>
                            </div>
                        </div>

                        <div className="mt-8 flex justify-end gap-3">
                            <button
                                onClick={() => setConfigAccount(null)}
                                className="px-4 py-2 text-gray-400 transition-colors hover:text-white"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={handleSaveAccountSettings}
                                disabled={isSavingAccount}
                                className="rounded-xl bg-primary px-4 py-2 font-medium text-black transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
                            >
                                {isSavingAccount ? "Saving..." : "Save Account Settings"}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </>
    );
}
