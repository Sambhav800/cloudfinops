"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { Cloud, Calendar } from "lucide-react";
import Link from "next/link";
import type { CloudCommitment } from "@/lib/api";
import { formatCommitmentPercent, formatSavingsPeriod } from "@/lib/commitments/presentation";
import {
    Table,
    TableHeader,
    TableBody,
    TableRow,
    TableHead,
    TableCell,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";

export interface FormattedCommitment extends CloudCommitment {
    daysRemaining: number | null;
    endDateStr: string;
    formattedAmount: string;
    formattedSavings: string;
}

type FilterTab = "all" | "active" | "expiring" | "expired";

interface InventoryTableProps {
    commitments: FormattedCommitment[];
    isLoading: boolean;
}

const PROVIDER_BADGE: Record<string, string> = {
    aws: "border-amber-500/20 bg-amber-500/10 text-amber-400",
    azure: "border-sky-500/20 bg-sky-500/10 text-sky-400",
    gcp: "border-blue-500/20 bg-blue-500/10 text-blue-400",
};

const TABS: { key: FilterTab; label: string }[] = [
    { key: "all", label: "All" },
    { key: "active", label: "Active" },
    { key: "expiring", label: "Expiring Soon" },
    { key: "expired", label: "Expired" },
];

export function InventoryTable({ commitments, isLoading }: InventoryTableProps) {
    const [activeTab, setActiveTab] = useState<FilterTab>("all");

    const filtered = commitments.filter((c) => {
        if (activeTab === "all") return true;
        if (activeTab === "active") return c.status === "active" && (c.daysRemaining === null || c.daysRemaining > 0);
        if (activeTab === "expiring") return c.status === "active" && c.daysRemaining !== null && c.daysRemaining > 0 && c.daysRemaining <= 90;
        if (activeTab === "expired") return c.status === "expired" || (c.daysRemaining !== null && c.daysRemaining <= 0);
        return true;
    });

    return (
        <div>
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                    <Calendar className="h-5 w-5 text-amber-400" />
                    <h2 className="text-lg font-bold text-white">Commitment Inventory</h2>
                </div>
                <div className="flex items-center gap-1 rounded-xl border border-white/10 bg-white/5 p-1">
                    {TABS.map((tab) => (
                        <button
                            key={tab.key}
                            onClick={() => setActiveTab(tab.key)}
                            className={`relative rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                                activeTab === tab.key
                                    ? "text-white"
                                    : "text-slate-400 hover:text-slate-200"
                            }`}
                        >
                            {activeTab === tab.key && (
                                <motion.div
                                    layoutId="commitmentFilter"
                                    className="absolute inset-0 rounded-lg bg-white/10"
                                    transition={{ type: "spring", bounce: 0.2, duration: 0.4 }}
                                />
                            )}
                            <span className="relative">{tab.label}</span>
                        </button>
                    ))}
                </div>
            </div>

            <div className="overflow-hidden rounded-2xl border border-white/10 bg-slate-900/50 backdrop-blur-xl">
                {isLoading ? (
                    <div className="space-y-0">
                        <div className="border-b border-white/10 bg-white/[0.03] px-4 py-3">
                            <Skeleton className="h-4 w-full bg-slate-800" />
                        </div>
                        {[1, 2, 3, 4].map((i) => (
                            <div key={i} className="border-b border-white/5 px-4 py-4">
                                <Skeleton className="h-5 w-full bg-slate-800" />
                            </div>
                        ))}
                    </div>
                ) : filtered.length === 0 ? (
                    <div className="flex flex-col items-center justify-center px-6 py-16 text-center">
                        <div className="mb-3 rounded-full bg-white/5 p-3">
                            <Cloud className="h-6 w-6 text-slate-400" />
                        </div>
                        <h4 className="text-sm font-medium text-white">
                            {commitments.length === 0
                                ? "No commitment rows in this snapshot"
                                : "No commitments match this filter"}
                        </h4>
                        <p className="mt-1 max-w-xs text-xs text-slate-500">
                            {commitments.length === 0
                                ? "See account sync status above."
                                : "Try selecting a different filter tab."}
                        </p>
                    </div>
                ) : (
                    <div className="overflow-x-auto">
                        <Table className="w-full min-w-[900px]">
                            <TableHeader>
                                <TableRow className="border-b border-white/10 bg-white/[0.03] hover:bg-white/[0.03]">
                                    <TableHead className="px-4 py-3 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                                        Commitment
                                    </TableHead>
                                    <TableHead className="px-4 py-3 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                                        Region
                                    </TableHead>
                                    <TableHead className="px-4 py-3 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                                        Monthly equivalent
                                    </TableHead>
                                    <TableHead className="px-4 py-3 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                                        Utilization
                                    </TableHead>
                                    <TableHead className="px-4 py-3 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                                        Measured savings
                                    </TableHead>
                                    <TableHead className="px-4 py-3 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                                        Risk
                                    </TableHead>
                                    <TableHead className="px-4 py-3 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                                        Expiry
                                    </TableHead>
                                    <TableHead className="px-4 py-3 text-right text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                                        Action
                                    </TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {filtered.map((item) => (
                                    <TableRow
                                        key={`${item.integration_id}-${item.id}`}
                                        className="border-b border-white/5 transition-colors hover:bg-white/[0.03]"
                                    >
                                        <TableCell className="px-4 py-3">
                                            <div className="flex items-center gap-2">
                                                <span
                                                    className={`inline-flex shrink-0 rounded-md border px-1.5 py-0.5 text-[9px] font-bold uppercase ${
                                                        PROVIDER_BADGE[item.provider.toLowerCase()] ??
                                                        "border-slate-500/20 bg-slate-500/10 text-slate-400"
                                                    }`}
                                                >
                                                    {item.provider.toUpperCase()}
                                                </span>
                                                <div className="min-w-0">
                                                    <p className="truncate text-sm font-medium text-white">
                                                        {item.name}
                                                    </p>
                                                    <p className="text-[10px] text-slate-500">
                                                        {item.type} &middot; {item.coverage_type}
                                                    </p>
                                                    <p className="break-all text-[10px] text-slate-500">Integration: {item.integration_id || "Not measured"}</p>
                                                    <p className="text-[10px] text-slate-500">Source: {item.source}</p>
                                                    <p className="text-[10px] text-slate-500">Pricing basis: {item.pricing_basis === "live_api" ? "Provider API" : "Not measured"}</p>
                                                </div>
                                            </div>
                                        </TableCell>
                                        <TableCell className="px-4 py-3 text-xs text-slate-400">
                                            {item.region || "Not measured"}
                                        </TableCell>
                                        <TableCell className="px-4 py-3 text-xs font-medium text-white">
                                            {item.formattedAmount}
                                        </TableCell>
                                        <TableCell className="px-4 py-3">
                                            <div className="flex items-center gap-2">
                                                {item.utilization_pct != null && <div className="h-1.5 w-16 overflow-hidden rounded-full bg-slate-800">
                                                    <div
                                                        className={`h-full rounded-full transition-all duration-700 ${
                                                            item.utilization_pct >= 85
                                                                ? "bg-emerald-500"
                                                                : item.utilization_pct >= 70
                                                                  ? "bg-amber-500"
                                                                  : "bg-rose-500"
                                                        }`}
                                                        style={{ width: `${Math.min(item.utilization_pct, 100)}%` }}
                                                    />
                                                </div>}
                                                <span className="text-xs font-medium text-slate-300">
                                                    {formatCommitmentPercent(item.utilization_pct)}
                                                </span>
                                            </div>
                                        </TableCell>
                                        <TableCell className="px-4 py-3 text-xs font-medium text-emerald-400">
                                            {item.formattedSavings}
                                            <p className="mt-1 text-[10px] text-slate-400">{formatSavingsPeriod(item.savings_period_start, item.savings_period_end)}</p>
                                        </TableCell>
                                        <TableCell className="px-4 py-3">
                                            <span className="text-xs text-slate-400">Not measured</span>
                                        </TableCell>
                                        <TableCell className="px-4 py-3">
                                            <p className="text-xs text-slate-300">{item.endDateStr}</p>
                                            <p
                                                className={`text-[10px] ${
                                                    item.daysRemaining !== null && item.daysRemaining < 30
                                                        ? "font-bold text-rose-400"
                                                        : item.daysRemaining !== null && item.daysRemaining < 90
                                                          ? "text-amber-400"
                                                          : "text-slate-500"
                                                }`}
                                            >
                                                {item.daysRemaining === null ? "Not measured" : item.daysRemaining > 0
                                                    ? `${item.daysRemaining}d left`
                                                    : "Expired"}
                                            </p>
                                        </TableCell>
                                        <TableCell className="px-4 py-3 text-right">
                                            <Link href={`/dashboard/simulator?id=${encodeURIComponent(item.id)}&action=renew`}>
                                                <button className="rounded-lg bg-indigo-600 px-3 py-1.5 text-[10px] font-medium text-white transition hover:bg-indigo-500">
                                                    Simulate
                                                </button>
                                            </Link>
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </div>
                )}
            </div>
        </div>
    );
}
