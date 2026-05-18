"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
    animate,
    motion,
    useInView,
    useMotionValue,
    useMotionValueEvent,
    useScroll,
    useSpring,
    useTransform,
    type MotionValue,
} from "framer-motion";
import { ArrowRight, Check, Sparkles } from "lucide-react";
import { COLORS, EASE } from "@/components/landing/tokens";

type PanelDefinition = {
    number: string;
    color: string;
    eyebrow: string;
    title: string;
    mutedTitle: string;
    subtitle: string;
    bullets: string[];
    chromeLabel: string;
    mockup: React.ReactNode;
};

const PANELS: PanelDefinition[] = [
    {
        number: "01",
        color: COLORS.accent,
        eyebrow: "STEP 01",
        title: "Connect every cloud.",
        mutedTitle: "In minutes, not weeks.",
        subtitle: "Read-only IAM, zero agents, and a clean handshake across every hyperscaler your platform team already runs.",
        bullets: [
            "AWS, Azure, GCP supported",
            "Read-only IAM roles",
            "No agents, no daemons",
        ],
        chromeLabel: "cloudfinops.solutions/connect",
        mockup: <ConnectMockup />,
    },
    {
        number: "02",
        color: COLORS.success,
        eyebrow: "STEP 02",
        title: "See unified spend.",
        mutedTitle: "Across every provider.",
        subtitle: "Normalized spend, tag coverage, and cost ownership all land in one view without context switching between consoles.",
        bullets: [
            "Normalized across providers",
            "Hourly sync",
            "Per-team, per-tag rollups",
        ],
        chromeLabel: "cloudfinops.solutions/overview",
        mockup: <SpendMockup />,
    },
    {
        number: "03",
        color: COLORS.warning,
        eyebrow: "STEP 03",
        title: "Surface waste instantly.",
        mutedTitle: "Before finance does.",
        subtitle: "Idle compute, oversized clusters, forgotten snapshots, and orphaned networking all show up ranked by savings and effort.",
        bullets: [
            "40+ resource types scanned",
            "Idle detection with 30-day utilization",
            "One-click remediation",
        ],
        chromeLabel: "cloudfinops.solutions/savings",
        mockup: <WasteMockup />,
    },
    {
        number: "04",
        color: COLORS.danger,
        eyebrow: "STEP 04",
        title: "Enforce policy.",
        mutedTitle: "With context built in.",
        subtitle: "Tagging, budgets, and compliance controls ship with reasoning and remediation so engineering and audit are reading the same truth.",
        bullets: [
            "CIS, SOC 2, PCI-DSS mapping",
            "Natural-language rule explanations",
            "Signed audit logs",
        ],
        chromeLabel: "cloudfinops.solutions/governance",
        mockup: <PolicyMockup />,
    },
    {
        number: "05",
        color: "#8b5cf6",
        eyebrow: "STEP 05",
        title: "Ship with confidence.",
        mutedTitle: "Forecast the blast radius.",
        subtitle: "Model month-end run rate, compare planned Terraform changes, and catch budget drift before it lands in production.",
        bullets: [
            "Holt-Winters projections",
            "Terraform scenario simulation",
            "Budget alerts before overrun",
        ],
        chromeLabel: "cloudfinops.solutions/forecast",
        mockup: <ForecastMockup />,
    },
];

const PROVIDER_TREND_PATHS = {
    aws: "M0,118 C42,110 76,102 118,92 C160,80 196,92 236,72 C280,48 322,44 360,38 C388,34 412,40 440,36",
    azure: "M0,130 C46,126 84,120 126,112 C166,104 204,108 246,92 C288,78 328,76 366,70 C392,66 418,68 440,62",
    gcp: "M0,142 C44,136 86,132 126,126 C168,118 206,116 246,104 C286,92 324,92 364,82 C396,76 420,74 440,68",
};

const WASTE_ROWS = [
    { label: "Idle compute", amount: "₹6.16L", width: "100%" },
    { label: "Orphaned storage", amount: "₹4.47L", width: "72%" },
    { label: "Oversized VMs", amount: "₹2.59L", width: "58%" },
    { label: "Unused LBs", amount: "₹1.28L", width: "34%" },
    { label: "Old snapshots", amount: "₹64.7K", width: "21%" },
];

const FORECAST_POINTS = {
    history: "M0,116 C34,106 68,102 108,96 C150,88 188,90 232,78 C274,66 308,62 344,56",
    forecastTop: "M344,56 C370,50 396,42 422,36 C434,34 446,32 456,30",
    forecastBottom: "M344,68 C370,64 396,58 422,52 C434,50 446,46 456,44",
};

export function HorizontalShowcase() {
    const containerRef = useRef<HTMLDivElement>(null);
    const { scrollYProgress } = useScroll({
        target: containerRef,
        offset: ["start start", "end end"],
    });

    const springConfig = { stiffness: 80, damping: 25, restDelta: 0.001 };
    const smoothProgress = useSpring(scrollYProgress, springConfig);
    const x = useTransform(smoothProgress, [0, 1], ["0%", "-80%"]);
    const [activeIndex, setActiveIndex] = useState(0);

    useMotionValueEvent(smoothProgress, "change", (latest) => {
        const nextIndex = Math.min(PANELS.length - 1, Math.floor(latest * PANELS.length));
        setActiveIndex(nextIndex);
    });

    return (
        <>
            <section ref={containerRef} className="relative hidden h-[500vh] md:block">
                <div className="sticky top-0 flex h-screen items-center overflow-hidden">
                    <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_80%_50%_at_50%_50%,rgba(99,102,241,0.08),transparent_60%)]" />
                    <HorizontalProgress progress={smoothProgress} />
                    <HorizontalDots activeIndex={activeIndex} />

                    <motion.div
                        style={{ x, willChange: "transform" }}
                        className="flex h-full items-center"
                    >
                        {PANELS.map((panel, index) => (
                            <DesktopPanel
                                key={panel.number}
                                panel={panel}
                                index={index}
                                progress={smoothProgress}
                            />
                        ))}
                    </motion.div>
                </div>
            </section>

            <section className="px-6 py-24 md:hidden">
                <div className="mx-auto max-w-6xl space-y-20">
                    {PANELS.map((panel, index) => (
                        <MobilePanel key={panel.number} panel={panel} index={index} />
                    ))}
                </div>
            </section>
        </>
    );
}

function HorizontalProgress({ progress }: { progress: MotionValue<number> }) {
    return (
        <div className="pointer-events-none absolute top-8 left-1/2 z-30 -translate-x-1/2 rounded-full border border-white/[0.08] bg-white/[0.02] px-4 py-1.5 backdrop-blur">
            <div className="flex items-center gap-3">
                <span className="text-[11px] font-medium uppercase tracking-[0.22em] text-zinc-500">
                    The platform
                </span>
                <div className="h-0.5 w-20 overflow-hidden rounded-full bg-white/[0.08]">
                    <motion.div
                        style={{ scaleX: progress, transformOrigin: "0%" }}
                        className="h-full bg-indigo-400"
                    />
                </div>
            </div>
        </div>
    );
}

function HorizontalDots({ activeIndex }: { activeIndex: number }) {
    return (
        <div className="pointer-events-none absolute bottom-10 left-1/2 z-30 flex -translate-x-1/2 items-center gap-3">
            {PANELS.map((panel, index) => (
                <div
                    key={panel.number}
                    className={
                        index === activeIndex
                            ? "h-1.5 w-8 rounded-full bg-white transition-all duration-300"
                            : "h-1.5 w-1.5 rounded-full bg-white/20 transition-all duration-300"
                    }
                />
            ))}
        </div>
    );
}

function DesktopPanel({
    panel,
    index,
    progress,
}: {
    panel: PanelDefinition;
    index: number;
    progress: MotionValue<number>;
}) {
    const segment = 1 / PANELS.length;
    const start = index === 0 ? 0 : Math.max(0, index * segment - 0.05);
    const mid = index === 0 ? Math.min(1, segment * 0.22) : Math.min(1, index * segment + 0.08);
    const end = Math.min(1, index * segment + 0.28);
    const fadeOutStart = Math.min(1, (index + 1) * segment - 0.04);
    const fadeOutEnd = Math.min(1, (index + 1) * segment + 0.03);
    const contentOpacity = useTransform(
        progress,
        [start, mid, fadeOutStart, fadeOutEnd],
        [index === 0 ? 1 : 0.22, 1, 1, 0.22],
    );
    const titleY = useTransform(progress, [start, mid], [index === 0 ? 0 : 40, 0]);
    const subtitleY = useTransform(progress, [start, mid], [index === 0 ? 0 : 24, 0]);
    const mockupY = useTransform(progress, [start, mid], [index === 0 ? 0 : 32, 0]);
    const ghostOpacity = useTransform(progress, [start, mid], [index === 0 ? 0.15 : 0, 0.15]);

    return (
        <div className="flex h-screen w-screen flex-shrink-0 items-center">
            <div className="mx-auto grid h-full max-w-7xl grid-cols-12 items-center gap-12 px-12">
                <motion.div
                    style={{ opacity: contentOpacity }}
                    className="relative col-span-5"
                >
                    <motion.div
                        style={{ opacity: ghostOpacity, scale: useTransform(progress, [start, mid], [0.8, 1]) }}
                        className="pointer-events-none absolute -top-24 left-0 text-[120px] font-medium leading-none tracking-[-0.08em]"
                    >
                        <span style={{ color: panel.color }}>{panel.number}</span>
                    </motion.div>

                    <div
                        className="relative z-10 inline-flex items-center rounded-full border px-3 py-1 text-[11px] font-medium uppercase tracking-[0.24em]"
                        style={{
                            color: panel.color,
                            borderColor: `${panel.color}33`,
                            backgroundColor: `${panel.color}10`,
                        }}
                    >
                        {panel.eyebrow}
                    </div>

                    <motion.h2
                        style={{ y: titleY }}
                        className="relative z-10 mt-6 text-[56px] font-medium tracking-[-0.03em] text-white md:text-[64px] md:leading-[1.05]"
                    >
                        {panel.title}
                        <br />
                        <span className="text-zinc-500">{panel.mutedTitle}</span>
                    </motion.h2>

                    <motion.p
                        style={{ y: subtitleY }}
                        className="relative z-10 mt-6 max-w-md text-[18px] leading-relaxed text-zinc-400"
                    >
                        {panel.subtitle}
                    </motion.p>

                    <div className="relative z-10 mt-8 space-y-3">
                        {panel.bullets.map((bullet, bulletIndex) => (
                            <motion.div
                                key={bullet}
                                style={{
                                    opacity: useTransform(
                                        progress,
                                        [start + 0.03 * bulletIndex, mid + 0.03 * bulletIndex],
                                        [index === 0 ? 1 : 0, 1],
                                    ),
                                    y: useTransform(
                                        progress,
                                        [start + 0.03 * bulletIndex, mid + 0.03 * bulletIndex],
                                        [index === 0 ? 0 : 20, 0],
                                    ),
                                }}
                                className="flex items-start gap-3"
                            >
                                <span
                                    className="mt-2 h-1 w-1 rounded-sm"
                                    style={{ backgroundColor: panel.color }}
                                />
                                <span className="text-[14px] leading-relaxed text-zinc-300">
                                    {bullet}
                                </span>
                            </motion.div>
                        ))}
                    </div>
                </motion.div>

                <motion.div style={{ opacity: contentOpacity, y: mockupY }} className="col-span-7">
                    <ShowcaseWindow chromeLabel={panel.chromeLabel}>{panel.mockup}</ShowcaseWindow>
                </motion.div>
            </div>
        </div>
    );
}

function MobilePanel({ panel, index }: { panel: PanelDefinition; index: number }) {
    return (
        <motion.article
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-100px" }}
            transition={{ duration: 0.7, delay: index * 0.06, ease: EASE }}
            className="space-y-8"
        >
            <div className="inline-flex items-center rounded-full border px-3 py-1 text-[11px] font-medium uppercase tracking-[0.24em] text-indigo-300"
                style={{ borderColor: `${panel.color}33`, backgroundColor: `${panel.color}10`, color: panel.color }}>
                {panel.eyebrow}
            </div>
            <div className="space-y-5">
                <div
                    className="text-[72px] font-medium leading-none tracking-[-0.08em] opacity-[0.15]"
                    style={{ color: panel.color }}
                >
                    {panel.number}
                </div>
                <h2 className="text-[38px] font-medium leading-[1.08] tracking-tight text-white">
                    {panel.title}
                    <br />
                    <span className="text-zinc-500">{panel.mutedTitle}</span>
                </h2>
                <p className="text-[16px] leading-relaxed text-zinc-400">{panel.subtitle}</p>
                <div className="space-y-3">
                    {panel.bullets.map((bullet) => (
                        <div key={bullet} className="flex items-start gap-3">
                            <span
                                className="mt-2 h-1 w-1 rounded-sm"
                                style={{ backgroundColor: panel.color }}
                            />
                            <span className="text-[14px] leading-relaxed text-zinc-300">{bullet}</span>
                        </div>
                    ))}
                </div>
            </div>
            <ShowcaseWindow chromeLabel={panel.chromeLabel}>{panel.mockup}</ShowcaseWindow>
        </motion.article>
    );
}

function ShowcaseWindow({
    chromeLabel,
    children,
}: {
    chromeLabel: string;
    children: React.ReactNode;
}) {
    return (
        <div className="overflow-hidden rounded-2xl border border-white/[0.08] bg-gradient-to-b from-[#0c0d12] to-[#07080c] shadow-[0_40px_80px_-20px_rgba(0,0,0,0.6),0_0_0_1px_rgba(255,255,255,0.05)]">
            <div className="relative flex h-8 items-center gap-2 border-b border-white/[0.06] bg-white/[0.02] px-3">
                <span className="h-2 w-2 rounded-full bg-[#ff5f57]" />
                <span className="h-2 w-2 rounded-full bg-[#febc2e]" />
                <span className="h-2 w-2 rounded-full bg-[#28c840]" />
                <div className="absolute left-1/2 -translate-x-1/2 rounded-md border border-white/[0.06] bg-white/[0.04] px-3 py-1 text-[11px] text-zinc-500">
                    {chromeLabel}
                </div>
            </div>
            {children}
        </div>
    );
}

function ConnectMockup() {
    const providers = [
        { short: "AWS", name: "Amazon Web Services", detail: "IAM role assumed · us-east-1", color: COLORS.aws, delay: 0 },
        { short: "Az", name: "Microsoft Azure", detail: "Reader SPN · westeurope", color: COLORS.azure, delay: 1 },
        { short: "GCP", name: "Google Cloud Platform", detail: "Viewer SA · europe-west1", color: COLORS.gcp, delay: 2 },
    ];

    return (
        <div className="space-y-4 p-5">
            {providers.map((provider, index) => (
                <motion.div
                    key={provider.short}
                    initial={{ opacity: 0, y: 16 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true, margin: "-100px" }}
                    transition={{ duration: 0.55, delay: index * 0.15, ease: EASE }}
                    className="flex items-center gap-4 rounded-xl border border-white/[0.06] bg-white/[0.02] p-4"
                >
                    <div
                        className="flex h-11 w-11 items-center justify-center rounded-lg text-[13px] font-semibold text-black"
                        style={{ backgroundColor: provider.color }}
                    >
                        {provider.short}
                    </div>
                    <div className="min-w-0 flex-1">
                        <p className="text-[14px] font-medium text-white">{provider.name}</p>
                        <p className="text-[11px] text-zinc-500">{provider.detail}</p>
                    </div>
                    <div className="relative h-10 w-32 overflow-hidden">
                        <motion.div
                            className="absolute inset-0 flex items-center justify-center rounded-lg border border-white/[0.08] bg-white/[0.02] text-[12px] font-medium text-zinc-300"
                            initial={{ opacity: 1, y: 0 }}
                            whileInView={{ opacity: [1, 1, 0, 0, 1], y: [0, 0, -6, -6, 0] }}
                            viewport={{ once: true, margin: "-100px" }}
                            transition={{
                                duration: 4,
                                delay: provider.delay,
                                repeat: Number.POSITIVE_INFINITY,
                                ease: EASE,
                            }}
                        >
                            Connect
                        </motion.div>
                        <motion.div
                            className="absolute inset-0 flex items-center justify-center gap-1 rounded-lg border border-emerald-500/20 bg-emerald-500/10 text-[12px] font-medium text-emerald-300"
                            initial={{ opacity: 0, y: 8 }}
                            whileInView={{ opacity: [0, 0, 1, 1, 0], y: [8, 8, 0, 0, 8] }}
                            viewport={{ once: true, margin: "-100px" }}
                            transition={{
                                duration: 4,
                                delay: provider.delay,
                                repeat: Number.POSITIVE_INFINITY,
                                ease: EASE,
                            }}
                        >
                            <span className="relative inline-flex h-2.5 w-2.5 items-center justify-center">
                                <span className="absolute inline-flex h-2.5 w-2.5 rounded-full bg-emerald-400 opacity-75 animate-ping" />
                                <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-400" />
                            </span>
                            Connected
                            <Check className="h-3.5 w-3.5" />
                        </motion.div>
                    </div>
                </motion.div>
            ))}
        </div>
    );
}

function SpendMockup() {
    const tiles = [
        { label: "Total", value: "₹1.03Cr" },
        { label: "AWS", value: "₹48.5L" },
        { label: "Azure", value: "₹23.4L" },
        { label: "GCP", value: "₹31.3L" },
    ];

    return (
        <div className="space-y-4 p-5">
            <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-4">
                <div className="flex items-center justify-between">
                    <p className="text-[13px] font-medium text-white">Unified provider spend</p>
                    <div className="flex items-center gap-3 text-[11px] text-zinc-500">
                        <LegendDot color={COLORS.aws} label="AWS" />
                        <LegendDot color={COLORS.azure} label="Azure" />
                        <LegendDot color={COLORS.gcp} label="GCP" />
                    </div>
                </div>
                <svg viewBox="0 0 440 180" className="mt-4 h-48 w-full" role="img" aria-label="Unified spend trend">
                    <defs>
                        <linearGradient id="horizontal-aws-fill" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="0%" stopColor={COLORS.aws} stopOpacity="0.2" />
                            <stop offset="100%" stopColor={COLORS.aws} stopOpacity="0" />
                        </linearGradient>
                        <linearGradient id="horizontal-azure-fill" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="0%" stopColor={COLORS.azure} stopOpacity="0.18" />
                            <stop offset="100%" stopColor={COLORS.azure} stopOpacity="0" />
                        </linearGradient>
                        <linearGradient id="horizontal-gcp-fill" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="0%" stopColor={COLORS.gcp} stopOpacity="0.18" />
                            <stop offset="100%" stopColor={COLORS.gcp} stopOpacity="0" />
                        </linearGradient>
                    </defs>
                    {[26, 64, 102, 140].map((y) => (
                        <line key={y} x1="0" y1={y} x2="440" y2={y} stroke="rgba(255,255,255,0.04)" />
                    ))}
                    <path d={`${PROVIDER_TREND_PATHS.gcp} L440,180 L0,180 Z`} fill="url(#horizontal-gcp-fill)" />
                    <path d={`${PROVIDER_TREND_PATHS.azure} L440,180 L0,180 Z`} fill="url(#horizontal-azure-fill)" />
                    <path d={`${PROVIDER_TREND_PATHS.aws} L440,180 L0,180 Z`} fill="url(#horizontal-aws-fill)" />
                    <motion.path
                        d={PROVIDER_TREND_PATHS.aws}
                        fill="none"
                        stroke={COLORS.aws}
                        strokeWidth="3"
                        strokeLinecap="round"
                        initial={{ pathLength: 0, opacity: 0.2 }}
                        whileInView={{ pathLength: 1, opacity: 1 }}
                        viewport={{ once: true, margin: "-100px" }}
                        transition={{ duration: 1.1, delay: 0.25, ease: EASE }}
                    />
                    <motion.path
                        d={PROVIDER_TREND_PATHS.azure}
                        fill="none"
                        stroke={COLORS.azure}
                        strokeWidth="3"
                        strokeLinecap="round"
                        initial={{ pathLength: 0, opacity: 0.2 }}
                        whileInView={{ pathLength: 1, opacity: 1 }}
                        viewport={{ once: true, margin: "-100px" }}
                        transition={{ duration: 1.1, delay: 0.4, ease: EASE }}
                    />
                    <motion.path
                        d={PROVIDER_TREND_PATHS.gcp}
                        fill="none"
                        stroke={COLORS.gcp}
                        strokeWidth="3"
                        strokeLinecap="round"
                        initial={{ pathLength: 0, opacity: 0.2 }}
                        whileInView={{ pathLength: 1, opacity: 1 }}
                        viewport={{ once: true, margin: "-100px" }}
                        transition={{ duration: 1.1, delay: 0.55, ease: EASE }}
                    />
                </svg>
            </div>

            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
                {tiles.map((tile, index) => (
                    <motion.div
                        key={tile.label}
                        initial={{ opacity: 0, y: 12 }}
                        whileInView={{ opacity: 1, y: 0 }}
                        viewport={{ once: true, margin: "-100px" }}
                        transition={{ duration: 0.45, delay: 0.2 + index * 0.08, ease: EASE }}
                        className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-4"
                    >
                        <p className="text-[11px] uppercase tracking-[0.18em] text-zinc-500">{tile.label}</p>
                        <p className="mt-2 text-[20px] font-medium text-white tabular-nums">{tile.value}</p>
                    </motion.div>
                ))}
            </div>
        </div>
    );
}

function WasteMockup() {
    return (
        <div className="grid gap-4 p-5 lg:grid-cols-[1.2fr_0.8fr]">
            <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-4">
                <p className="text-[12px] text-zinc-400">Potential monthly savings</p>
                <p className="mt-2 text-[28px] font-medium text-white tabular-nums">
                    <InlineCount target={1513920} formatter={(value) => `₹${Math.round(value).toLocaleString("en-IN")}`} />
                </p>
                <p className="text-[11px] text-emerald-400">+₹3.49L vs last scan</p>

                <div className="mt-5 space-y-3">
                    {WASTE_ROWS.map((row, index) => (
                        <div key={row.label} className="space-y-1">
                            <div className="flex items-center justify-between text-[11px] text-zinc-400">
                                <span>{row.label}</span>
                                <span className="tabular-nums text-zinc-300">{row.amount}</span>
                            </div>
                            <div className="h-2 overflow-hidden rounded-full bg-white/[0.04]">
                                <motion.div
                                    initial={{ width: 0 }}
                                    whileInView={{ width: row.width }}
                                    viewport={{ once: true, margin: "-100px" }}
                                    transition={{ duration: 0.75, delay: 0.2 + index * 0.1, ease: EASE }}
                                    className="h-full rounded-full bg-emerald-400"
                                />
                            </div>
                        </div>
                    ))}
                </div>
            </div>

            <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-4">
                <p className="text-[12px] text-zinc-400">Ready to apply</p>
                <div className="mt-2 flex items-end gap-2">
                    <p className="text-[28px] font-medium text-white tabular-nums">12</p>
                    <p className="pb-1 text-[11px] text-zinc-500">actions queued</p>
                </div>
                <div className="my-3 border-t border-white/[0.04]" />
                <div className="space-y-1">
                    {[
                        { color: COLORS.accent, text: "Terminate 8 idle EC2 instances" },
                        { color: COLORS.success, text: "Downsize gke-prod-west nodepool" },
                        { color: COLORS.danger, text: "Delete 34 orphaned EBS volumes" },
                        { color: COLORS.warning, text: "Snapshot and archive 2TB bucket" },
                    ].map((item, index) => (
                        <motion.div
                            key={item.text}
                            initial={{ opacity: 0, y: 8 }}
                            whileInView={{ opacity: 1, y: 0 }}
                            viewport={{ once: true, margin: "-100px" }}
                            transition={{ duration: 0.45, delay: 0.55 + index * 0.08, ease: EASE }}
                            className="flex items-center gap-2 py-2"
                        >
                            <span
                                className="h-3 w-3 rounded-sm"
                                style={{ backgroundColor: item.color }}
                            />
                            <span className="flex-1 truncate text-[12px] text-zinc-300">{item.text}</span>
                            <span className="text-[12px] text-zinc-600">→</span>
                        </motion.div>
                    ))}
                </div>
                <motion.button
                    type="button"
                    initial={{ opacity: 0, scale: 0.95 }}
                    whileInView={{ opacity: 1, scale: 1 }}
                    viewport={{ once: true, margin: "-100px" }}
                    transition={{ duration: 0.4, delay: 0.95, ease: EASE }}
                    className="mt-4 w-full rounded-md bg-white px-4 py-2 text-[12px] font-medium text-black"
                >
                    Apply all →
                </motion.button>
            </div>
        </div>
    );
}

function PolicyMockup() {
    const severities = [
        { label: "8 critical", className: "border-rose-500/20 bg-rose-500/10 text-rose-400" },
        { label: "14 high", className: "border-amber-500/20 bg-amber-500/10 text-amber-400" },
        { label: "32 medium", className: "border-white/[0.08] bg-white/[0.03] text-zinc-400" },
    ];

    const rows = [
        ["Untagged resource", "i-0a3b21ef4cc", "critical", "Missing required tag: cost-center"],
        ["Budget exceeded", "prod/billing-svc", "critical", "Monthly budget exceeded by 34%"],
        ["Public S3 bucket", "legacy-reports-2019", "high", "Bucket ACL allows public read"],
        ["Oversized instance", "vm-worker-eu-1", "medium", "CPU avg 4.2% over 30 days"],
    ] as const;

    return (
        <div className="space-y-4 p-5">
            <div className="flex items-center justify-between border-b border-white/[0.06] pb-4">
                <p className="text-[13px] font-medium text-white">Active violations</p>
                <div className="flex items-center gap-2">
                    {severities.map((severity, index) => (
                        <motion.span
                            key={severity.label}
                            initial={{ opacity: 0, y: 8 }}
                            whileInView={{ opacity: 1, y: 0 }}
                            viewport={{ once: true, margin: "-100px" }}
                            transition={{ duration: 0.4, delay: 0.2 + index * 0.08, ease: EASE }}
                            className={`rounded-md border px-2 py-0.5 text-[11px] ${severity.className}`}
                        >
                            {severity.label}
                        </motion.span>
                    ))}
                </div>
            </div>

            <div className="overflow-hidden rounded-xl border border-white/[0.06]">
                <div className="grid grid-cols-[1.2fr_1fr_0.9fr_1.5fr] border-b border-white/[0.06] bg-white/[0.02] px-4 py-2 text-[10px] font-medium uppercase tracking-[0.18em] text-zinc-500">
                    <span>Rule</span>
                    <span>Resource</span>
                    <span>Severity</span>
                    <span>Reasoning</span>
                </div>
                {rows.map((row, index) => (
                    <motion.div
                        key={row[0]}
                        initial={{ opacity: 0, x: -8 }}
                        whileInView={{ opacity: 1, x: 0 }}
                        viewport={{ once: true, margin: "-100px" }}
                        transition={{ duration: 0.42, delay: 0.3 + index * 0.08, ease: EASE }}
                        className="grid grid-cols-[1.2fr_1fr_0.9fr_1.5fr] gap-4 border-b border-white/[0.04] px-4 py-3 text-[12px] last:border-b-0"
                    >
                        <span className="font-medium text-white">{row[0]}</span>
                        <span className="font-mono text-zinc-400">{row[1]}</span>
                        <span>
                            <span
                                className={`rounded-md px-2 py-0.5 text-[11px] ${
                                    row[2] === "critical"
                                        ? "bg-rose-500/10 text-rose-400"
                                        : row[2] === "high"
                                          ? "bg-amber-500/10 text-amber-400"
                                          : "bg-white/[0.04] text-zinc-400"
                                }`}
                            >
                                {row[2]}
                            </span>
                        </span>
                        <span className="italic text-zinc-500">{row[3]}</span>
                    </motion.div>
                ))}
            </div>

            <div className="grid gap-3 rounded-xl border border-white/[0.06] bg-white/[0.02] p-4 lg:grid-cols-3">
                {[
                    { label: "CIS", value: "87%" },
                    { label: "SOC 2", value: "92%" },
                    { label: "PCI-DSS", value: "78%" },
                ].map((framework, index) => (
                    <div key={framework.label} className="space-y-2">
                        <div className="flex items-center justify-between text-[11px] text-zinc-500">
                            <span>{framework.label}</span>
                            <span className="tabular-nums text-zinc-300">{framework.value}</span>
                        </div>
                        <div className="h-1.5 overflow-hidden rounded-full bg-white/[0.04]">
                            <motion.div
                                initial={{ width: 0 }}
                                whileInView={{ width: framework.value }}
                                viewport={{ once: true, margin: "-100px" }}
                                transition={{ duration: 0.7, delay: 0.5 + index * 0.08, ease: EASE }}
                                className="h-full rounded-full bg-indigo-400"
                            />
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}

function ForecastMockup() {
    return (
        <div className="grid gap-4 p-5 lg:grid-cols-[1.35fr_0.65fr]">
            <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-4">
                <p className="text-[12px] text-zinc-400">Month-end forecast</p>
                <svg viewBox="0 0 460 200" className="mt-4 h-52 w-full" role="img" aria-label="Forecast preview">
                    <defs>
                        <linearGradient id="forecast-band" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="0%" stopColor={COLORS.accent} stopOpacity="0.18" />
                            <stop offset="100%" stopColor={COLORS.accent} stopOpacity="0" />
                        </linearGradient>
                    </defs>
                    {[24, 64, 104, 144, 184].map((y) => (
                        <line key={y} x1="0" y1={y} x2="460" y2={y} stroke="rgba(255,255,255,0.04)" />
                    ))}
                    <path
                        d={`${FORECAST_POINTS.history} ${FORECAST_POINTS.forecastTop} L456,44 ${FORECAST_POINTS.forecastBottom
                            .replace("M344,68", "L344,68")
                            .replace("M", "")} L344,68 Z`}
                        fill="url(#forecast-band)"
                    />
                    <motion.path
                        d={FORECAST_POINTS.history}
                        fill="none"
                        stroke={COLORS.accent}
                        strokeWidth="3"
                        strokeLinecap="round"
                        initial={{ pathLength: 0, opacity: 0.2 }}
                        whileInView={{ pathLength: 1, opacity: 1 }}
                        viewport={{ once: true, margin: "-100px" }}
                        transition={{ duration: 1, delay: 0.2, ease: EASE }}
                    />
                    <motion.path
                        d={FORECAST_POINTS.forecastTop.replace("M344,56", "M344,56")}
                        fill="none"
                        stroke={COLORS.accentBright}
                        strokeWidth="3"
                        strokeDasharray="6 6"
                        strokeLinecap="round"
                        initial={{ pathLength: 0, opacity: 0.2 }}
                        whileInView={{ pathLength: 1, opacity: 1 }}
                        viewport={{ once: true, margin: "-100px" }}
                        transition={{ duration: 0.8, delay: 0.55, ease: EASE }}
                    />
                </svg>
            </div>

            <div className="space-y-4">
                <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-4">
                    <p className="text-[12px] text-zinc-400">Projected month-end</p>
                    <p className="mt-2 text-[28px] font-medium text-white tabular-nums">₹1.18Cr</p>
                    <p className="mt-2 text-[11px] text-zinc-500">Historical + Holt-Winters confidence band</p>
                </div>
                <div className="rounded-xl border border-amber-500/20 bg-amber-500/[0.06] p-4">
                    <p className="text-[11px] font-medium uppercase tracking-[0.2em] text-amber-300">
                        Budget alert
                    </p>
                    <p className="mt-3 text-[14px] leading-relaxed text-zinc-200">
                        On track to exceed budget by 8%
                    </p>
                </div>
            </div>
        </div>
    );
}

function LegendDot({ color, label }: { color: string; label: string }) {
    return (
        <span className="inline-flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full" style={{ backgroundColor: color }} />
            <span>{label}</span>
        </span>
    );
}

function InlineCount({
    target,
    formatter,
}: {
    target: number;
    formatter: (value: number) => string;
}) {
    const ref = useRef<HTMLSpanElement>(null);
    const inView = useInView(ref, { once: true, margin: "-100px" });
    const count = useMotionValue(0);
    const display = useTransform(count, formatter);

    useEffect(() => {
        if (!inView) return;

        const controls = animate(count, target, {
            duration: 1.8,
            ease: EASE,
        });

        return () => controls.stop();
    }, [count, inView, target]);

    return <motion.span ref={ref}>{display}</motion.span>;
}
