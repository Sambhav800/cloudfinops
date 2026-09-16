"use client";

import { ArrowUpRight } from "lucide-react";
import Link from "next/link";
import type { CommitmentRecommendationResponse } from "@/lib/api";
import { formatCommitmentDate, RECOMMENDATION_STATUS_LABELS } from "@/lib/commitments/presentation";

export function ProviderRecommendationsCard({ data, showOptimizerLink = true }: { data: CommitmentRecommendationResponse; showOptimizerLink?: boolean }) {
    return (
        <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-6 lg:col-span-3">
            <h3 className="text-sm font-bold text-white">AWS Compute Savings Plan purchase estimates</h3>
            <p className="mt-2 text-xs text-slate-400">Source: AWS Cost Explorer. Azure unsupported; GCP inventory only.</p>
            <p className="mt-3 text-sm text-slate-300">{RECOMMENDATION_STATUS_LABELS[data.status]}</p>
            {data.message && <p className="mt-2 text-sm text-slate-400">{data.message}</p>}
            <dl className="mt-4 space-y-2 text-xs text-slate-400">
                <div><dt className="inline">Fetched: </dt><dd className="inline">{formatCommitmentDate(data.fetched_at, true)}</dd></div>
                <div><dt className="inline">Generated: </dt><dd className="inline">{formatCommitmentDate(data.generated_at, true)}</dd></div>
                <div><dt className="inline">Pricing basis: </dt><dd className="inline">{data.pricing_basis === "live_api" ? "Provider API" : "Not measured"}</dd></div>
                <div><dt className="inline">Over-commitment risk: </dt><dd className="inline">Not measured</dd></div>
            </dl>
            {showOptimizerLink && <Link href="/dashboard/optimizer" className="mt-5 inline-flex items-center gap-1.5 text-xs font-medium text-indigo-400 hover:text-indigo-300">
                Review provider alternatives <ArrowUpRight className="h-3.5 w-3.5" />
            </Link>}
        </div>
    );
}
