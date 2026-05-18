"use client";

import { motion } from "framer-motion";
import { COLORS, DURATION, EASE } from "@/components/landing/tokens";

const statCards = [
    {
        label: "FinOps Score",
        value: "87",
        delta: "↑ 12 pts",
        border: COLORS.accent,
        deltaClassName: "text-emerald-400",
    },
    {
        label: "Monthly Spend",
        value: "₹1.03Cr",
        delta: "↓ 8.2%",
        border: COLORS.success,
        deltaClassName: "text-emerald-400",
    },
    {
        label: "Waste Detected",
        value: "₹15.1L",
        delta: "23% of spend",
        border: COLORS.danger,
        deltaClassName: "text-rose-400",
    },
    {
        label: "Savings Realized",
        value: "₹34.9L",
        delta: "this quarter",
        border: COLORS.warning,
        deltaClassName: "text-amber-400",
    },
];

const providerLegend = [
    { label: "AWS", color: COLORS.aws },
    { label: "Azure", color: COLORS.azure },
    { label: "GCP", color: COLORS.gcp },
];

const activities = [
    { color: COLORS.aws, label: "Terminated 12 idle EC2 instances", amount: "+₹3.59L/mo" },
    { color: COLORS.azure, label: "Downsized 8 VMs to appropriate tier", amount: "+₹1.81L/mo" },
    { color: COLORS.gcp, label: "Removed orphaned persistent disks", amount: "+₹73.9K/mo" },
];

const awsLine = "M0,92 C38,88 68,72 106,68 C144,64 178,82 214,60 C248,40 284,48 324,42 C360,36 382,50 400,46";
const azureLine = "M0,112 C38,104 70,96 108,94 C146,92 176,100 212,82 C246,64 286,72 324,66 C360,60 382,68 400,62";
const gcpLine = "M0,126 C40,120 76,116 112,108 C146,100 178,102 214,94 C248,84 286,86 324,78 C360,72 384,76 400,70";

const donutSegments = [
    { color: COLORS.aws, length: 126.67, offset: 0, delay: 0 },
    { color: COLORS.azure, length: 105.56, offset: -126.67, delay: 0.15 },
    { color: COLORS.gcp, length: 69.37, offset: -(126.67 + 105.56), delay: 0.3 },
];

export function DashboardMockup() {
    return (
        <div className="overflow-hidden rounded-2xl border border-white/[0.08] bg-gradient-to-b from-[#0c0d12] to-[#07080c] shadow-[0_40px_80px_-20px_rgba(0,0,0,0.8),0_0_0_1px_rgba(255,255,255,0.05),0_80px_160px_-40px_rgba(99,102,241,0.25)]">
            <div className="relative flex h-10 items-center gap-3 border-b border-white/[0.06] bg-white/[0.02] px-4">
                <div className="flex items-center gap-2">
                    <span className="h-3 w-3 rounded-full bg-[#ff5f57]" />
                    <span className="h-3 w-3 rounded-full bg-[#febc2e]" />
                    <span className="h-3 w-3 rounded-full bg-[#28c840]" />
                </div>
                <div className="absolute left-1/2 -translate-x-1/2 rounded-md border border-white/[0.06] bg-white/[0.04] px-3 py-1 text-[11px] text-zinc-500">
                    cloudfinops.solutions/dashboard
                </div>
            </div>

            <div className="grid grid-cols-12 gap-4 p-6">
                {statCards.map((card) => (
                    <div
                        key={card.label}
                        className="col-span-6 rounded-lg border border-white/[0.06] bg-white/[0.02] p-4 xl:col-span-3"
                        style={{ borderTopWidth: 2, borderTopColor: card.border }}
                    >
                        <p className="text-[11px] uppercase tracking-wider text-zinc-500">{card.label}</p>
                        <p className="mt-2 text-[24px] font-medium text-white tabular-nums">{card.value}</p>
                        <p className={`mt-1 text-[11px] ${card.deltaClassName}`}>{card.delta}</p>
                    </div>
                ))}

                <div className="col-span-12 rounded-lg border border-white/[0.06] bg-white/[0.02] p-4 xl:col-span-8">
                    <div className="flex items-center justify-between gap-4">
                        <p className="text-[13px] font-medium text-white">Daily spend trend</p>
                        <div className="flex items-center gap-3">
                            {providerLegend.map((provider) => (
                                <div key={provider.label} className="flex items-center gap-1.5">
                                    <span className="h-2 w-2 rounded-full" style={{ backgroundColor: provider.color }} />
                                    <span className="text-[11px] text-zinc-500">{provider.label}</span>
                                </div>
                            ))}
                        </div>
                    </div>
                    <svg viewBox="0 0 400 160" className="mt-4 h-40 w-full" aria-label="Daily spend trend chart" role="img">
                        <defs>
                            <linearGradient id="aws-fill" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stopColor={COLORS.aws} stopOpacity="0.22" />
                                <stop offset="100%" stopColor={COLORS.aws} stopOpacity="0" />
                            </linearGradient>
                            <linearGradient id="azure-fill" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stopColor={COLORS.azure} stopOpacity="0.18" />
                                <stop offset="100%" stopColor={COLORS.azure} stopOpacity="0" />
                            </linearGradient>
                            <linearGradient id="gcp-fill" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stopColor={COLORS.gcp} stopOpacity="0.18" />
                                <stop offset="100%" stopColor={COLORS.gcp} stopOpacity="0" />
                            </linearGradient>
                        </defs>
                        {[20, 60, 100, 140].map((y) => (
                            <line
                                key={y}
                                x1="0"
                                x2="400"
                                y1={y}
                                y2={y}
                                stroke="rgba(255,255,255,0.04)"
                                strokeWidth="1"
                            />
                        ))}

                        <path d={`${gcpLine} L400,160 L0,160 Z`} fill="url(#gcp-fill)" />
                        <path d={`${azureLine} L400,160 L0,160 Z`} fill="url(#azure-fill)" />
                        <path d={`${awsLine} L400,160 L0,160 Z`} fill="url(#aws-fill)" />

                        <motion.path
                            d={awsLine}
                            fill="none"
                            stroke={COLORS.aws}
                            strokeWidth="3"
                            strokeLinecap="round"
                            initial={{ pathLength: 0, opacity: 0.2 }}
                            animate={{ pathLength: 1, opacity: 1 }}
                            transition={{ duration: 1.2, delay: 0.3, ease: EASE }}
                        />
                        <motion.path
                            d={azureLine}
                            fill="none"
                            stroke={COLORS.azure}
                            strokeWidth="3"
                            strokeLinecap="round"
                            initial={{ pathLength: 0, opacity: 0.2 }}
                            animate={{ pathLength: 1, opacity: 1 }}
                            transition={{ duration: 1.2, delay: 0.45, ease: EASE }}
                        />
                        <motion.path
                            d={gcpLine}
                            fill="none"
                            stroke={COLORS.gcp}
                            strokeWidth="3"
                            strokeLinecap="round"
                            initial={{ pathLength: 0, opacity: 0.2 }}
                            animate={{ pathLength: 1, opacity: 1 }}
                            transition={{ duration: 1.2, delay: 0.6, ease: EASE }}
                        />
                    </svg>
                </div>

                <div className="col-span-12 rounded-lg border border-white/[0.06] bg-white/[0.02] p-4 xl:col-span-4">
                    <p className="text-[13px] font-medium text-white">Provider mix</p>
                    <div className="mt-3 flex items-center justify-center">
                        <svg viewBox="0 0 120 120" className="h-44 w-44" aria-label="Provider mix donut chart" role="img">
                            <circle
                                cx="60"
                                cy="60"
                                r="48"
                                fill="none"
                                stroke="rgba(255,255,255,0.06)"
                                strokeWidth="16"
                            />
                            {donutSegments.map((segment) => (
                                <motion.circle
                                    key={segment.color}
                                    cx="60"
                                    cy="60"
                                    r="48"
                                    fill="none"
                                    stroke={segment.color}
                                    strokeWidth="16"
                                    strokeLinecap="round"
                                    transform="rotate(-90 60 60)"
                                    strokeDasharray={`${segment.length} 301.59`}
                                    initial={{ strokeDashoffset: 301.59 }}
                                    animate={{ strokeDashoffset: segment.offset }}
                                    transition={{ duration: 0.9, delay: segment.delay, ease: EASE }}
                                />
                            ))}
                            <text
                                x="60"
                                y="58"
                                textAnchor="middle"
                                className="fill-white text-[16px] font-medium"
                            >
                                ₹1.03Cr
                            </text>
                            <text
                                x="60"
                                y="74"
                                textAnchor="middle"
                                className="fill-zinc-500 text-[10px]"
                            >
                                this month
                            </text>
                        </svg>
                    </div>
                </div>

                <div className="col-span-12 rounded-lg border border-white/[0.06] bg-white/[0.02] p-4">
                    <p className="mb-3 text-[13px] font-medium text-white">Recent optimizations</p>
                    <div className="space-y-1">
                        {activities.map((activity, index) => (
                            <div
                                key={activity.label}
                                className={`flex items-center justify-between gap-3 py-2 ${index < activities.length - 1 ? "border-b border-white/[0.04]" : ""}`}
                            >
                                <div className="flex min-w-0 items-center gap-3 text-[12px] text-zinc-300">
                                    <span className="h-2 w-2 rounded-full" style={{ backgroundColor: activity.color }} />
                                    <span className="truncate">{activity.label}</span>
                                </div>
                                <span className="text-[12px] tabular-nums text-emerald-400">{activity.amount}</span>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
}
