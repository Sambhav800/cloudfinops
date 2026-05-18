"use client";

import type { ReactNode } from "react";
import { motion } from "framer-motion";
import {
    Cpu,
    FileText,
    MessageSquare,
    Network,
    TerminalSquare,
    TrendingUp,
} from "lucide-react";
import { SectionHeading } from "@/components/landing/section-heading";
import { COLORS, EASE } from "@/components/landing/tokens";

type BentoCardProps = {
    icon: ReactNode;
    title: string;
    description: string;
    delay: number;
    visualization: ReactNode;
};

function BentoCard({ icon, title, description, delay, visualization }: BentoCardProps) {
    return (
        <motion.div
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-100px" }}
            transition={{ duration: 0.7, delay, ease: EASE }}
            className="group cursor-default rounded-xl border border-white/[0.08] bg-gradient-to-b from-white/[0.03] to-transparent p-6 transition-all duration-300 hover:border-white/[0.15]"
        >
            <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-indigo-500/20 bg-indigo-500/10 text-indigo-400">
                {icon}
            </div>
            <h3 className="mt-4 text-[16px] font-medium text-white">{title}</h3>
            <p className="mt-2 text-[13px] leading-relaxed text-zinc-400">{description}</p>
            <div className="mt-6 h-24">{visualization}</div>
        </motion.div>
    );
}

function ForecastViz() {
    return (
        <svg viewBox="0 0 240 96" className="h-full w-full" aria-hidden="true">
            <defs>
                <linearGradient id="forecast-fill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={COLORS.accent} stopOpacity="0.25" />
                    <stop offset="100%" stopColor={COLORS.accent} stopOpacity="0" />
                </linearGradient>
            </defs>
            <path
                d="M8,68 C40,54 62,56 88,44 C112,34 132,30 158,26 C178,24 194,22 232,18 L232,88 L8,88 Z"
                fill="url(#forecast-fill)"
            />
            <path
                d="M8,74 C40,60 62,62 88,50 C112,40 132,36 158,32 C178,30 194,28 232,24"
                fill="none"
                stroke="rgba(129,140,248,0.24)"
                strokeWidth="8"
                strokeLinecap="round"
            />
            <motion.path
                d="M8,68 C40,54 62,56 88,44 C112,34 132,30 158,26 C178,24 194,22 232,18"
                fill="none"
                stroke={COLORS.accent}
                strokeWidth="3"
                strokeLinecap="round"
                initial={{ pathLength: 0 }}
                whileInView={{ pathLength: 1 }}
                viewport={{ once: true, margin: "-100px" }}
                transition={{ duration: 1, delay: 0.3, ease: EASE }}
            />
            {[186, 210].map((x) => (
                <line
                    key={x}
                    x1={x}
                    x2={x}
                    y1="10"
                    y2="88"
                    stroke="rgba(255,255,255,0.18)"
                    strokeDasharray="4 4"
                />
            ))}
        </svg>
    );
}

function ArchitectureViz() {
    const nodes = [
        { x: 18, y: 44, label: "API" },
        { x: 78, y: 24, label: "Queue" },
        { x: 78, y: 64, label: "Cache" },
        { x: 148, y: 44, label: "Core" },
        { x: 212, y: 44, label: "DB" },
    ];

    return (
        <svg viewBox="0 0 240 96" className="h-full w-full" aria-hidden="true">
            <motion.path
                d="M36,44 H70 L86,24 H140 L156,44 H194"
                fill="none"
                stroke={COLORS.accent}
                strokeWidth="2"
                strokeDasharray="6 6"
                initial={{ strokeDashoffset: 20, opacity: 0 }}
                whileInView={{ strokeDashoffset: 0, opacity: 1 }}
                viewport={{ once: true, margin: "-100px" }}
                transition={{ duration: 1.2, delay: 0.3, ease: "linear", repeat: Infinity, repeatType: "loop" }}
            />
            <motion.path
                d="M36,44 H70 L86,64 H140 L156,44 H194"
                fill="none"
                stroke={COLORS.accent}
                strokeWidth="2"
                strokeDasharray="6 6"
                initial={{ strokeDashoffset: 24, opacity: 0 }}
                whileInView={{ strokeDashoffset: 0, opacity: 1 }}
                viewport={{ once: true, margin: "-100px" }}
                transition={{ duration: 1.4, delay: 0.4, ease: "linear", repeat: Infinity, repeatType: "loop" }}
            />
            {nodes.map((node, index) => (
                <motion.g
                    key={node.label}
                    initial={{ opacity: 0, scale: 0.9 }}
                    whileInView={{ opacity: 1, scale: 1 }}
                    viewport={{ once: true, margin: "-100px" }}
                    transition={{ duration: 0.4, delay: 0.3 + index * 0.08, ease: EASE }}
                >
                    <rect
                        x={node.x}
                        y={node.y}
                        width="28"
                        height="16"
                        rx="4"
                        fill="rgba(255,255,255,0.04)"
                        stroke="rgba(255,255,255,0.08)"
                    />
                    <text x={node.x + 14} y={node.y + 10.5} textAnchor="middle" className="fill-zinc-300 text-[7px]">
                        {node.label}
                    </text>
                </motion.g>
            ))}
        </svg>
    );
}

function SimulatorViz() {
    return (
        <svg viewBox="0 0 240 96" className="h-full w-full" aria-hidden="true">
            <rect x="36" y="20" width="36" height="54" rx="4" fill="rgba(255,255,255,0.12)" />
            <rect x="160" y="34" width="36" height="40" rx="4" fill={COLORS.accent} />
            <path d="M98 48 H138" stroke="rgba(255,255,255,0.3)" strokeWidth="2" strokeDasharray="4 4" />
            <path d="M130 40 L142 48 L130 56" fill="none" stroke={COLORS.accent} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            <text x="30" y="86" className="fill-zinc-500 text-[9px]">Current</text>
            <text x="154" y="86" className="fill-zinc-500 text-[9px]">Proposed</text>
            <text x="112" y="40" className="fill-indigo-400 text-[10px] font-medium">-38%</text>
        </svg>
    );
}

function GpuViz() {
    const chips = [
        { label: "A100", active: false },
        { label: "A100", active: false },
        { label: "H100", active: true },
        { label: "A100", active: false },
    ];

    return (
        <div className="grid grid-cols-4 gap-2">
            {chips.map((chip, index) => (
                <motion.div
                    key={`${chip.label}-${index}`}
                    initial={{ opacity: 0, y: 8 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true, margin: "-100px" }}
                    transition={{ duration: 0.35, delay: 0.3 + index * 0.08, ease: EASE }}
                    className={`rounded-lg border p-2 ${chip.active ? "border-indigo-500/30 bg-indigo-500/10" : "border-white/[0.08] bg-white/[0.03]"}`}
                >
                    <div className="flex items-center justify-between">
                        <span className={`h-2 w-2 rounded-full ${chip.active ? "bg-emerald-400" : "bg-rose-400"}`} />
                        <Cpu className={`h-3.5 w-3.5 ${chip.active ? "text-indigo-300" : "text-zinc-500"}`} />
                    </div>
                    <div className={`mt-4 text-[10px] font-medium ${chip.active ? "text-white" : "text-zinc-400"}`}>{chip.label}</div>
                </motion.div>
            ))}
        </div>
    );
}

function BillScannerViz() {
    return (
        <div className="relative h-full overflow-hidden rounded-lg border border-white/[0.08] bg-white/[0.02] p-3">
            <div className="pointer-events-none absolute inset-x-3 top-3 bottom-3 overflow-hidden rounded-md border border-white/[0.06] bg-black/20">
                <div className="flex h-full flex-col justify-evenly px-3 py-2">
                    {[0, 1, 2, 3, 4].map((row) => (
                        <div
                            key={row}
                            className="flex items-center justify-between rounded-md bg-white/[0.03] px-3 py-2"
                        >
                            <span
                                className="h-2 rounded-full bg-white/[0.08]"
                                style={{ width: row === 2 ? "56%" : row === 4 ? "34%" : "74%" }}
                            />
                            <span
                                className="h-2 rounded-full bg-white/[0.06]"
                                style={{ width: row % 2 === 0 ? "18%" : "26%" }}
                            />
                        </div>
                    ))}
                </div>

                <motion.div
                    initial={{ opacity: 0 }}
                    whileInView={{ opacity: 1 }}
                    viewport={{ once: true, margin: "-100px" }}
                    className="absolute inset-x-3 top-3 h-8 rounded-md bg-indigo-400/10 blur-md"
                    animate={{ y: [0, 18, 38, 58, 0], opacity: [0.15, 0.4, 0.55, 0.35, 0.15] }}
                    transition={{ duration: 2.6, ease: "easeInOut", repeat: Infinity }}
                />
                <motion.div
                    initial={{ opacity: 0 }}
                    whileInView={{ opacity: 1 }}
                    viewport={{ once: true, margin: "-100px" }}
                    className="absolute left-3 right-3 top-5 h-[2px] bg-indigo-400 shadow-[0_0_18px_rgba(99,102,241,0.45)]"
                    animate={{ y: [0, 18, 38, 58, 0], opacity: [0.25, 1, 1, 0.8, 0.25] }}
                    transition={{ duration: 2.6, ease: "easeInOut", repeat: Infinity }}
                />
                <div className="absolute inset-x-0 bottom-0 h-10 bg-gradient-to-t from-[#0c0d12] to-transparent" />
            </div>
        </div>
    );
}

function AgentViz() {
    return (
        <div className="space-y-3">
            <div className="ml-auto max-w-[70%] rounded-2xl rounded-br-md bg-white/[0.08] px-3 py-2 text-[11px] text-zinc-300">
                Why is our GCP bill up?
            </div>
            <div className="max-w-[82%] rounded-2xl rounded-bl-md border border-indigo-500/20 bg-indigo-500/10 px-3 py-2 text-[11px] text-zinc-300">
                <div className="mb-2">Comparing slot usage and storage growth...</div>
                <div className="flex items-center gap-1">
                    {[0, 1, 2].map((dot) => (
                        <motion.span
                            key={dot}
                            className="h-2 w-2 rounded-full bg-indigo-300"
                            animate={{ opacity: [0.3, 1, 0.3] }}
                            transition={{ duration: 0.6, delay: dot * 0.2, repeat: Infinity, ease: "easeInOut" }}
                        />
                    ))}
                </div>
            </div>
        </div>
    );
}

export function CapabilitiesBento() {
    return (
        <section className="px-6 py-32">
            <div className="mx-auto max-w-7xl">
                <SectionHeading
                    eyebrow="THE FULL PLATFORM"
                    align="center"
                    title={
                        <>
                            Everything you need.
                            <span className="text-zinc-500"> Nothing you don&apos;t.</span>
                        </>
                    }
                    description="Beyond cost and governance, CloudFinOps ships with forecasting, architecture intelligence, simulation, and AI agents — all in one platform."
                />

                <div className="mt-16 grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
                    <BentoCard
                        icon={<TrendingUp className="h-5 w-5" />}
                        title="AI-powered forecasting"
                        description="Holt-Winters time-series projections with 92% accuracy on month-end spend."
                        delay={0}
                        visualization={<ForecastViz />}
                    />
                    <BentoCard
                        icon={<Network className="h-5 w-5" />}
                        title="Architecture intelligence"
                        description="Auto-generated infrastructure diagrams from your live cloud state."
                        delay={0.08}
                        visualization={<ArchitectureViz />}
                    />
                    <BentoCard
                        icon={<TerminalSquare className="h-5 w-5" />}
                        title="Terraform simulator"
                        description="Preview cost impact before `terraform apply`. Compare scenarios side by side."
                        delay={0.16}
                        visualization={<SimulatorViz />}
                    />
                    <BentoCard
                        icon={<Cpu className="h-5 w-5" />}
                        title="GPU intelligence"
                        description="Detect ghost GPUs, recommend MIG partitioning, arbitrage across specialized clouds."
                        delay={0.24}
                        visualization={<GpuViz />}
                    />
                    <BentoCard
                        icon={<FileText className="h-5 w-5" />}
                        title="Bill scanner"
                        description="Drop a cloud bill PDF. Get executive-grade line-item analysis in 30 seconds."
                        delay={0.32}
                        visualization={<BillScannerViz />}
                    />
                    <BentoCard
                        icon={<MessageSquare className="h-5 w-5" />}
                        title="Clousy AI agent"
                        description="MCP-enabled assistant that knows your entire cloud inventory by name."
                        delay={0.4}
                        visualization={<AgentViz />}
                    />
                </div>
            </div>
        </section>
    );
}
