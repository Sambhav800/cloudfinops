"use client";

import { IndianRupee, TrendingDown, Zap, Cloud, Server } from "lucide-react";
import { motion } from "framer-motion";
import { SavingsCopilotCard } from "@/components/dashboard/savings-copilot-card";
import { Skeleton } from "@/components/ui/skeleton";
import { formatInrCurrency } from "@/lib/resources/contract";

interface ProviderCost {
    provider: string;
    spend: number;
    resources: number;
    savings: number;
}

interface CostScoreProps {
    totalSpend: number;
    potentialSavings: number;
    annualSavings: number;
    aiConfidence: number;
    totalResources: number;
    costOfInaction: number;
    providerCosts: ProviderCost[];
    isLoading?: boolean;
}

const PROVIDER_COLORS: Record<string, string> = {
    aws: "#FF9900",
    azure: "#0078D4",
    gcp: "#4285F4",
};

function getProviderKey(provider: string) {
    const normalized = provider.toLowerCase();
    return normalized in PROVIDER_COLORS
        ? (normalized as keyof typeof PROVIDER_COLORS)
        : null;
}

function formatMoney(value: number): string {
    return formatInrCurrency(value, {
        minimumFractionDigits: 0,
        maximumFractionDigits: 0,
    });
}

function getMaturityStage(score: number) {
    if (score >= 85) {
        return {
            label: "Advanced",
            summary: "Strong optimization coverage with disciplined cost controls already in motion.",
            badgeClassName: "border border-emerald-500/20 bg-emerald-500/10 text-emerald-400",
        };
    }

    if (score >= 65) {
        return {
            label: "Scaling",
            summary: "Core FinOps habits are working, but there is still meaningful savings headroom to operationalize.",
            badgeClassName: "border border-indigo-500/20 bg-indigo-500/10 text-indigo-400",
        };
    }

    if (score >= 40) {
        return {
            label: "Foundational",
            summary: "The baseline is visible, but optimization and accountability loops still need to tighten.",
            badgeClassName: "border border-amber-500/20 bg-amber-500/10 text-amber-400",
        };
    }

    return {
        label: "Reactive",
        summary: "The estate is still spending reactively. Prioritize waste removal and policy coverage first.",
        badgeClassName: "border border-rose-500/20 bg-rose-500/10 text-rose-400",
    };
}

function ProviderDonut({
    data,
    total,
}: {
    data: { name: string; value: number; color: string }[];
    total: number;
}) {
    const MIN_PCT = 0.04;
    const radius = 48;
    const circumference = 2 * Math.PI * radius;
    let cumulativeOffset = 0;

    const rawSegments = data
        .filter((segment) => segment.value > 0)
        .map((item) => ({ ...item, pct: total > 0 ? item.value / total : 0 }));

    if (rawSegments.length === 0) {
        const label = data.length > 0 ? "No MTD billing yet" : "No provider data";
        return (
            <div className="flex h-32 flex-col items-center justify-center">
                <p className="text-xs text-slate-500">{label}</p>
            </div>
        );
    }

    if (rawSegments.length === 1) {
        const sole = rawSegments[0];
        return (
            <div className="flex h-32 flex-col items-center justify-center gap-2">
                <span
                    className="h-4 w-4 rounded-full"
                    style={{ backgroundColor: sole.color }}
                />
                <p className="text-lg font-bold text-white">{sole.name}</p>
                <p className="text-xs text-slate-400">100% of spend — single provider</p>
            </div>
        );
    }

    const boosted = rawSegments.map((segment) => ({
        ...segment,
        pct: Math.max(segment.pct, MIN_PCT),
    }));
    const sum = boosted.reduce((accumulator, segment) => accumulator + segment.pct, 0);
    const normalized = boosted.map((segment) => ({ ...segment, pct: segment.pct / sum }));

    const segments = normalized.map((segment) => {
        const dash = segment.pct * circumference;
        const offset = -cumulativeOffset;
        cumulativeOffset += dash;
        return { ...segment, dash, offset };
    });

    return (
        <div className="flex flex-col items-center">
            <p className="mb-3 text-[10px] font-semibold uppercase tracking-widest text-slate-500">
                Spend by Provider
            </p>
            <svg
                width="120"
                height="120"
                viewBox="0 0 120 120"
                style={{ transform: "rotate(-90deg)" }}
            >
                <circle
                    cx="60"
                    cy="60"
                    r={radius}
                    fill="none"
                    stroke="#1e293b"
                    strokeWidth="14"
                />
                {segments.map((segment, index) => (
                    <circle
                        key={index}
                        cx="60"
                        cy="60"
                        r={radius}
                        fill="none"
                        stroke={segment.color}
                        strokeWidth="14"
                        strokeDasharray={`${segment.dash} ${circumference - segment.dash}`}
                        strokeDashoffset={segment.offset}
                        strokeLinecap="butt"
                    />
                ))}
            </svg>
            <div className="mt-3 flex flex-wrap justify-center gap-x-3 gap-y-1">
                {segments.map((segment, index) => (
                    <div key={index} className="flex items-center gap-1.5">
                        <span
                            className="h-2 w-2 flex-shrink-0 rounded-full"
                            style={{ backgroundColor: segment.color }}
                        />
                        <span className="text-xs text-slate-400">
                            {segment.name} {Math.round((total > 0 ? segment.value / total : 0) * 100)}%
                        </span>
                    </div>
                ))}
            </div>
        </div>
    );
}

export function CostScoreSection({
    totalSpend,
    potentialSavings,
    annualSavings,
    aiConfidence,
    totalResources,
    costOfInaction,
    providerCosts,
    isLoading = false,
    activeProvider = "all",
}: CostScoreProps & { activeProvider?: "all" | "aws" | "azure" | "gcp" }) {
    const normalizedProviderCosts = providerCosts.filter(
        (providerCost) =>
            providerCost.spend > 0 ||
            providerCost.savings > 0 ||
            providerCost.resources > 0
    );
    const activeProviderStats =
        activeProvider === "all"
            ? null
            : normalizedProviderCosts.find(
                  (providerCost) => getProviderKey(providerCost.provider) === activeProvider
              ) ?? null;
    const visibleProviderCosts =
        activeProvider === "all"
            ? normalizedProviderCosts
            : normalizedProviderCosts.filter(
                  (providerCost) => getProviderKey(providerCost.provider) === activeProvider
              );
    const displayedSpend = activeProviderStats?.spend ?? totalSpend;
    const displayedPotentialSavings = activeProviderStats?.savings ?? potentialSavings;
    const displayedAnnualSavings = activeProviderStats
        ? activeProviderStats.savings * 12
        : annualSavings;
    const monitoredResources = activeProviderStats?.resources ?? totalResources;
    const donutData = visibleProviderCosts.map((providerCost) => ({
        name: providerCost.provider.toUpperCase(),
        value: providerCost.spend,
        color: PROVIDER_COLORS[providerCost.provider.toLowerCase()] ?? "#94a3b8",
    }));

    const savingsRatio =
        displayedSpend > 0
            ? Math.min(
                  100,
                  Math.round((1 - displayedPotentialSavings / displayedSpend) * 100)
              )
            : 100;
    const finOpsScore = Math.round(savingsRatio * 0.6 + aiConfidence * 0.4);
    const savingsShare = displayedSpend > 0
        ? Math.min(100, (displayedPotentialSavings / displayedSpend) * 100)
        : 0;
    const maturityStage = getMaturityStage(finOpsScore);

    const scoreColor =
        finOpsScore >= 80
            ? "text-emerald-400"
            : finOpsScore >= 50
              ? "text-amber-400"
              : "text-rose-400";

    const circumference = 2 * Math.PI * 52;
    const dashOffset = circumference - (finOpsScore / 100) * circumference;
    return (
        <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="mb-8"
        >
            <div className="mb-4 flex items-center gap-2">
                <Cloud className="h-5 w-5 text-cyan-400" />
                <h3 className="text-lg font-bold text-white">Cloud Cost & FinOps Score</h3>
            </div>

            <div className="space-y-4">
                <div className="mb-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
                    <div className="overflow-hidden rounded-2xl border border-white/10 border-t-2 border-t-indigo-500/60 bg-gradient-to-br from-slate-900/60 to-slate-900/40 p-6">
                        <div className="flex h-full flex-col gap-5">
                            {isLoading ? (
                                <>
                                    <div className="flex items-start justify-between gap-4">
                                        <div className="min-w-0 space-y-3">
                                            <Skeleton className="h-3 w-28 bg-slate-800" />
                                            <Skeleton className="h-7 w-32 bg-slate-800" />
                                            <Skeleton className="h-4 w-64 bg-slate-800" />
                                        </div>
                                        <Skeleton className="h-6 w-20 shrink-0 rounded-full bg-slate-800" />
                                    </div>
                                    <div className="flex flex-col gap-5 md:flex-row md:items-center">
                                        <Skeleton className="h-28 w-28 rounded-full bg-slate-800" />
                                        <div className="grid flex-1 grid-cols-1 gap-2 sm:grid-cols-2">
                                            {[1, 2, 3].map((item) => (
                                                <div
                                                    key={item}
                                                    className={`rounded-xl border border-white/5 bg-white/5 p-3 ${
                                                        item === 3 ? "sm:col-span-2" : ""
                                                    }`}
                                                >
                                                    <Skeleton className="h-3 w-16 bg-slate-800" />
                                                    <Skeleton className="mt-2 h-6 w-14 bg-slate-800" />
                                                    <Skeleton className="mt-2 h-3 w-20 bg-slate-800" />
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                    <div className="rounded-xl border border-white/5 bg-white/5 p-3.5">
                                        <Skeleton className="h-3 w-40 bg-slate-800" />
                                        <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
                                            <div>
                                                <Skeleton className="h-3 w-24 bg-slate-800" />
                                                <Skeleton className="mt-2 h-5 w-24 bg-slate-800" />
                                            </div>
                                            <div>
                                                <Skeleton className="h-3 w-24 bg-slate-800" />
                                                <Skeleton className="mt-2 h-5 w-24 bg-slate-800" />
                                            </div>
                                        </div>
                                    </div>
                                </>
                            ) : (
                                <>
                                    <div className="flex items-start justify-between gap-4">
                                        <div className="min-w-0">
                                            <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-indigo-400">
                                                FinOps Maturity
                                            </p>
                                            <h4 className="mt-2 text-xl font-semibold text-white">
                                                {maturityStage.label}
                                            </h4>
                                            <p className="mt-2 max-w-sm text-sm leading-relaxed text-slate-400">
                                                {maturityStage.summary}
                                            </p>
                                        </div>
                                        <span
                                            className={`shrink-0 rounded-full px-2.5 py-1 text-[10px] font-medium uppercase tracking-wide ${maturityStage.badgeClassName}`}
                                        >
                                            {finOpsScore >= 80
                                                ? "Excellent"
                                                : finOpsScore >= 50
                                                    ? "Improving"
                                                    : "Needs attention"}
                                        </span>
                                    </div>

                                    <div className="flex flex-col gap-5 md:flex-row md:items-center">
                                        <div className="relative h-28 w-28 shrink-0">
                                            <svg className="h-28 w-28 -rotate-90" viewBox="0 0 120 120">
                                                <circle
                                                    cx="60"
                                                    cy="60"
                                                    r="52"
                                                    fill="none"
                                                    stroke="rgba(255,255,255,0.05)"
                                                    strokeWidth="8"
                                                />
                                                <circle
                                                    cx="60"
                                                    cy="60"
                                                    r="52"
                                                    fill="none"
                                                    stroke={
                                                        finOpsScore >= 80
                                                            ? "#34d399"
                                                            : finOpsScore >= 50
                                                                ? "#fbbf24"
                                                                : "#f87171"
                                                    }
                                                    strokeWidth="8"
                                                    strokeLinecap="round"
                                                    strokeDasharray={circumference}
                                                    strokeDashoffset={dashOffset}
                                                    style={{
                                                        transition: "stroke-dashoffset 1s ease-in-out",
                                                    }}
                                                />
                                            </svg>
                                            <div className="absolute inset-0 flex flex-col items-center justify-center">
                                                <span className={`text-3xl font-bold ${scoreColor}`}>
                                                    {finOpsScore}
                                                </span>
                                                <span className="text-[10px] uppercase tracking-wider text-slate-400">
                                                    Score
                                                </span>
                                            </div>
                                        </div>

                                        <div className="grid flex-1 grid-cols-1 gap-2 sm:grid-cols-2">
                                            <div className="min-w-0 overflow-hidden rounded-xl border border-white/5 bg-white/5 p-3">
                                                <p className="text-[10px] uppercase tracking-wide text-slate-500">
                                                    Savings Share
                                                </p>
                                                <div className="mt-2 flex items-baseline gap-2">
                                                    <p className="shrink-0 text-lg font-semibold text-white">
                                                        {savingsShare.toFixed(1)}%
                                                    </p>
                                                    <p className="truncate text-[10px] leading-4 text-slate-500">
                                                        of live spend
                                                    </p>
                                                </div>
                                            </div>
                                            <div className="min-w-0 overflow-hidden rounded-xl border border-white/5 bg-white/5 p-3">
                                                <p className="text-[10px] uppercase tracking-wide text-slate-500">
                                                    AI Confidence
                                                </p>
                                                <div className="mt-2 flex items-baseline gap-2">
                                                    <p className="shrink-0 text-lg font-semibold text-white">
                                                        {aiConfidence}%
                                                    </p>
                                                    <p className="truncate text-[10px] leading-4 text-slate-500">
                                                        scan confidence
                                                    </p>
                                                </div>
                                            </div>
                                            <div className="min-w-0 overflow-hidden rounded-xl border border-white/5 bg-white/5 p-3 sm:col-span-2">
                                                <p className="text-[10px] uppercase tracking-wide text-slate-500">
                                                    Resources In Scope
                                                </p>
                                                <div className="mt-2 flex items-baseline gap-2">
                                                    <p className="shrink-0 text-lg font-semibold text-white">
                                                        {monitoredResources.toLocaleString()}
                                                    </p>
                                                    <p className="truncate text-[10px] leading-4 text-slate-500">
                                                        resources tracked
                                                    </p>
                                                </div>
                                            </div>
                                        </div>
                                    </div>

                                    <div className="rounded-xl border border-white/5 bg-white/5 p-3.5">
                                        <p className="text-[10px] uppercase tracking-wide text-slate-500">
                                            Optimization Baseline
                                        </p>
                                        <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
                                            <div className="rounded-lg border border-white/5 bg-slate-950/20 p-3">
                                                <p className="text-[10px] uppercase tracking-wide text-slate-500">
                                                    Monthly Opportunity
                                                </p>
                                                <p className="mt-1 text-lg font-semibold text-white">
                                                    {formatMoney(displayedPotentialSavings)}
                                                    /mo
                                                </p>
                                                <p className="mt-1 text-[10px] text-slate-500">
                                                    identified today
                                                </p>
                                            </div>
                                            <div className="rounded-lg border border-white/5 bg-slate-950/20 p-3">
                                                <p className="text-[10px] uppercase tracking-wide text-slate-500">
                                                    Annualized Impact
                                                </p>
                                                <p className="mt-1 text-lg font-semibold text-white">
                                                    {formatMoney(displayedAnnualSavings)}
                                                    /yr
                                                </p>
                                                <p className="mt-1 text-[10px] text-slate-500">
                                                    optimization runway
                                                </p>
                                            </div>
                                        </div>
                                    </div>
                                </>
                            )}
                        </div>
                    </div>

                    <SavingsCopilotCard />

                    <div className="overflow-hidden rounded-2xl border border-white/10 border-t-2 border-t-sky-500/60 bg-gradient-to-br from-slate-900/60 to-slate-900/40 p-6">
                        {isLoading ? (
                            <div className="flex h-full flex-col justify-between gap-4">
                                <div className="flex items-center gap-6">
                                    <Skeleton className="h-32 w-32 rounded-full bg-slate-800" />
                                    <div className="min-w-0 flex-1 space-y-3">
                                        <Skeleton className="h-4 w-20 bg-slate-800" />
                                        <Skeleton className="h-8 w-32 bg-slate-800" />
                                        <Skeleton className="h-3 w-28 bg-slate-800" />
                                        <div className="space-y-2">
                                            <Skeleton className="h-3 w-full bg-slate-800" />
                                            <Skeleton className="h-3 w-full bg-slate-800" />
                                            <Skeleton className="h-3 w-full bg-slate-800" />
                                        </div>
                                    </div>
                                </div>
                                <div className="grid grid-cols-3 gap-2">
                                    {[1, 2, 3].map((pill) => (
                                        <div
                                            key={pill}
                                            className="rounded-xl border border-white/5 bg-white/5 p-3"
                                        >
                                            <Skeleton className="h-3 w-12 bg-slate-800" />
                                            <Skeleton className="mt-2 h-4 w-16 bg-slate-800" />
                                            <Skeleton className="mt-2 h-3 w-14 bg-slate-800" />
                                        </div>
                                    ))}
                                </div>
                            </div>
                        ) : (
                            <div className="flex h-full flex-col justify-between gap-4">
                                <div className="flex flex-col items-center gap-4">
                                    <ProviderDonut
                                        data={donutData}
                                        total={displayedSpend}
                                    />
                                    <div className="flex w-full min-w-0 flex-col gap-3">
                                        <div>
                                            <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-500">
                                                MTD Spend
                                            </p>
                                            <p className="mt-1 truncate text-2xl font-bold text-white">
                                                {formatMoney(displayedSpend)}
                                            </p>
                                            <p className="mt-0.5 text-xs text-slate-500">
                                                {visibleProviderCosts.length} provider
                                                {visibleProviderCosts.length !== 1 ? "s" : ""} connected
                                            </p>
                                        </div>

                                        <div className="space-y-1.5">
                                            {visibleProviderCosts.map((providerCost) => {
                                                const key = providerCost.provider.toLowerCase();
                                                const color =
                                                    PROVIDER_COLORS[
                                                        key as keyof typeof PROVIDER_COLORS
                                                    ] ?? "#94a3b8";
                                                const percent =
                                                    displayedSpend > 0
                                                        ? Math.round(
                                                              (providerCost.spend / displayedSpend) * 100
                                                          )
                                                        : 0;

                                                return (
                                                    <div
                                                        key={key}
                                                        className="flex items-center justify-between gap-2"
                                                    >
                                                        <div className="flex min-w-0 items-center gap-1.5">
                                                            <span
                                                                className="h-2 w-2 flex-shrink-0 rounded-full"
                                                                style={{ backgroundColor: color }}
                                                            />
                                                            <span className="truncate text-xs font-medium uppercase text-slate-400">
                                                                {providerCost.provider.toUpperCase()}
                                                            </span>
                                                        </div>
                                                        <div className="flex shrink-0 items-center gap-2">
                                                            <span className="text-xs font-mono text-white">
                                                                {formatMoney(providerCost.spend)}
                                                            </span>
                                                            <span className="text-[10px] text-slate-500">
                                                                {percent}%
                                                            </span>
                                                        </div>
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    </div>
                                </div>

                                <div className="grid grid-cols-2 gap-2">
                                    <div className="min-w-0 rounded-xl border border-white/5 bg-white/5 p-3">
                                        <p className="text-[10px] uppercase tracking-wide text-slate-500">
                                            MTD Actual
                                        </p>
                                        <p className="mt-1 truncate text-sm font-bold text-white">
                                            {formatMoney(displayedSpend)}
                                        </p>
                                        <p className="mt-0.5 text-[10px] text-slate-600">
                                            month to date
                                        </p>
                                    </div>
                                    <div className="min-w-0 rounded-xl border border-emerald-500/10 bg-emerald-500/5 p-3">
                                        <p className="text-[10px] uppercase tracking-wide text-emerald-600">
                                            Savings
                                        </p>
                                        <p className="mt-1 truncate text-sm font-bold text-emerald-400">
                                            {formatMoney(displayedPotentialSavings)}
                                        </p>
                                        <p className="mt-0.5 text-[10px] text-slate-600">
                                            /month potential
                                        </p>
                                    </div>
                                </div>
                            </div>
                        )}
                    </div>
                </div>

                <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
                    <div className="flex flex-col justify-between rounded-xl border border-white/10 border-t-2 border-t-indigo-500/60 bg-slate-900/60 p-4 backdrop-blur-xl">
                        <div className="mb-2 flex items-center justify-between">
                            <span className="text-xs uppercase tracking-wider text-slate-400">
                                MTD Spend
                            </span>
                            <IndianRupee className="h-4 w-4 text-slate-500" />
                        </div>
                        {isLoading ? (
                            <>
                                <Skeleton className="h-8 w-28 bg-slate-700" />
                                <Skeleton className="mt-3 h-3 w-44 bg-slate-800" />
                            </>
                        ) : (
                            <>
                                <p className="text-2xl font-bold text-white">
                                    {formatMoney(displayedSpend)}
                                </p>
                                <p className="mt-1 text-xs text-slate-500">
                                    current calendar month to date
                                </p>
                            </>
                        )}
                    </div>

                    <div className="flex flex-col justify-between rounded-xl border border-white/10 border-t-2 border-t-emerald-500/60 bg-slate-900/60 p-4 backdrop-blur-xl">
                        <div className="mb-2 flex items-center justify-between">
                            <span className="text-xs uppercase tracking-wider text-slate-400">
                                Savings Opportunity
                            </span>
                            <Zap className="h-4 w-4 text-amber-400" />
                        </div>
                        {isLoading ? (
                            <>
                                <Skeleton className="h-8 w-28 bg-slate-700" />
                                <Skeleton className="mt-3 h-3 w-40 bg-slate-800" />
                            </>
                        ) : (
                            <>
                                <p className="text-2xl font-bold text-emerald-400">
                                    {formatMoney(displayedPotentialSavings)}
                                    <span className="text-sm font-normal text-slate-500">/mo</span>
                                </p>
                                <p className="mt-1 flex items-center gap-1 text-xs text-emerald-500/70">
                                    <TrendingDown className="h-3 w-3" />
                                    {formatMoney(displayedAnnualSavings)}
                                    /yr potential
                                </p>
                            </>
                        )}
                    </div>

                    <div className="flex flex-col justify-between rounded-xl border border-white/10 border-t-2 border-t-rose-500/60 bg-slate-900/60 p-4 backdrop-blur-xl">
                        <div className="mb-2 flex items-center justify-between">
                            <span className="text-xs uppercase tracking-wider text-slate-400">
                                Cost of Inaction
                            </span>
                            <Server className="h-4 w-4 text-rose-400" />
                        </div>
                        {isLoading ? (
                            <>
                                <Skeleton className="h-8 w-28 bg-slate-700" />
                                <Skeleton className="mt-3 h-3 w-36 bg-slate-800" />
                            </>
                        ) : (
                            <>
                                <p className="text-2xl font-bold text-rose-400">
                                    {formatMoney(costOfInaction)}
                                    <span className="text-sm font-normal text-slate-500">/6 months</span>
                                </p>
                                <p className="mt-1 text-xs text-slate-500">
                                    {formatMoney(costOfInaction * 2)}
                                    /yr if nothing changes
                                </p>
                                <p className="mt-2 text-[10px] text-slate-600">
                                    {totalResources} resources monitored
                                </p>
                            </>
                        )}
                    </div>
                </div>
            </div>
        </motion.div>
    );
}
