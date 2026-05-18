"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { DashboardFinanceSummary, type DashboardFinanceAccountSummary } from "./dashboard-finance-summary";
import type { BackendIntegration, FinanceForecastResponse, FinanceBudgetEvent } from "@/lib/api";

interface DashboardFinanceLoaderProps {
    integrations: BackendIntegration[];
}

interface FinanceData {
    portfolioForecast: FinanceForecastResponse | null;
    accountForecasts: DashboardFinanceAccountSummary[];
    portfolioBudgetEvent: FinanceBudgetEvent | null;
}

export function DashboardFinanceLoader({ integrations }: DashboardFinanceLoaderProps) {
    const { getToken } = useAuth();
    const [data, setData] = useState<FinanceData | null>(null);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;

        async function loadFinanceData() {
            try {
                const token = await getToken();
                if (!token) return;

                const headers = { Authorization: `Bearer ${token}` };
                const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "";

                const [portfolioRes, budgetRes] = await Promise.all([
                    fetch(`${backendUrl}/api/finance/forecast?scope=portfolio&days=60`, { headers }),
                    fetch(`${backendUrl}/api/finance/budget-events?limit=10`, { headers }),
                ]);

                const portfolioForecast: FinanceForecastResponse | null = portfolioRes.ok ? await portfolioRes.json() : null;
                const budgetEvents: FinanceBudgetEvent[] = budgetRes.ok ? (await budgetRes.json())?.events ?? [] : [];
                const portfolioBudgetEvent = budgetEvents.find((e) => e.scope === "portfolio") ?? null;

                const activeIntegrations = integrations.filter(
                    (i) => (i.status || "").toLowerCase() === "active"
                );

                const accountForecasts: DashboardFinanceAccountSummary[] = await Promise.all(
                    activeIntegrations.map(async (integration) => {
                        try {
                            const res = await fetch(
                                `${backendUrl}/api/finance/forecast?scope=integration&integration_id=${integration.id}&days=60`,
                                { headers }
                            );
                            const forecast: FinanceForecastResponse | null = res.ok ? await res.json() : null;
                            return { integration, forecast };
                        } catch {
                            return { integration, forecast: null };
                        }
                    })
                );

                if (!cancelled) {
                    setData({ portfolioForecast, accountForecasts, portfolioBudgetEvent });
                }
            } catch {
                if (!cancelled) {
                    setError("Budget Copilot summary could not be loaded.");
                }
            }
        }

        if (integrations.length > 0) {
            loadFinanceData();
        }

        return () => { cancelled = true; };
    }, [integrations, getToken]);

    if (integrations.length === 0) {
        return null;
    }

    if (!data && !error) {
        return (
            <div className="mt-6 rounded-2xl border border-white/5 bg-slate-900/50 p-6 animate-pulse">
                <div className="h-6 w-48 bg-slate-800 rounded mb-4" />
                <div className="h-40 bg-slate-800/50 rounded" />
            </div>
        );
    }

    if (error || !data) {
        return (
            <div className="mt-6 rounded-2xl border border-amber-500/20 bg-amber-500/5 p-4 text-sm text-amber-300">
                {error || "Could not load finance data."}
            </div>
        );
    }

    return (
        <div className="mt-6">
            <DashboardFinanceSummary
                portfolioForecast={data.portfolioForecast}
                portfolioBudgetEvent={data.portfolioBudgetEvent}
                accountForecasts={data.accountForecasts}
                loadError={null}
            />
        </div>
    );
}
