"use client";

import { motion } from "framer-motion";
import { useEffect, useState } from "react";

// ══════════════════════════════════════════════════════════════════
//  SVG Cloud Provider Logos (Real, recognizable logos)
// ══════════════════════════════════════════════════════════════════

function AWSLogo({ size = 24 }: { size?: number }) {
    return (
        <svg width={size} height={size} viewBox="0 0 48 48" fill="none">
            <path d="M13.527 21.529c0 .597.064 1.08.176 1.435.128.355.288.742.512 1.161.08.129.112.258.112.37 0 .161-.096.322-.304.484l-1.008.672a.77.77 0 01-.416.145c-.16 0-.32-.08-.48-.225a4.957 4.957 0 01-.576-.749 12.47 12.47 0 01-.496-.93c-1.248 1.47-2.816 2.206-4.704 2.206-1.344 0-2.416-.384-3.2-1.15-.784-.768-1.184-1.792-1.184-3.072 0-1.36.48-2.464 1.456-3.296.976-.832 2.272-1.248 3.92-1.248.544 0 1.104.048 1.696.128.592.08 1.2.208 1.84.368v-1.168c0-1.216-.256-2.064-.752-2.56-.512-.496-1.376-.736-2.608-.736-.56 0-1.136.064-1.728.208a12.726 12.726 0 00-1.728.544 4.588 4.588 0 01-.56.208.984.984 0 01-.256.048c-.224 0-.336-.16-.336-.496v-.784c0-.258.032-.45.112-.562a1.18 1.18 0 01.448-.337 9.22 9.22 0 011.984-.72A9.532 9.532 0 019.527 11c2.016 0 3.488.458 4.432 1.374.928.917 1.4 2.31 1.4 4.178v5.504h.168zm-6.496 2.43c.528 0 1.072-.096 1.648-.289a3.56 3.56 0 001.52-1.009c.256-.304.448-.642.544-1.03.096-.385.16-.849.16-1.393v-.672a13.38 13.38 0 00-1.472-.288 12.02 12.02 0 00-1.504-.096c-1.072 0-1.856.208-2.384.641-.528.432-.784 1.04-.784 1.84 0 .753.192 1.31.592 1.697.384.385.944.576 1.68.576v.023zm12.848 1.697c-.288 0-.48-.048-.608-.16-.128-.096-.24-.322-.336-.625l-3.76-12.37a2.77 2.77 0 01-.144-.642c0-.257.128-.4.384-.4h1.568c.304 0 .512.048.624.16.128.096.224.32.32.625l2.688 10.595 2.496-10.595c.08-.321.176-.529.304-.625a1.09 1.09 0 01.64-.16h1.28c.304 0 .512.048.64.16.128.096.24.32.304.625l2.528 10.723 2.768-10.723c.096-.321.208-.529.32-.625.128-.096.336-.16.624-.16h1.488c.256 0 .4.128.4.4 0 .08-.016.16-.032.257a2.48 2.48 0 01-.112.4l-3.856 12.37c-.096.32-.208.529-.336.625-.128.112-.336.16-.608.16h-1.376c-.304 0-.512-.048-.64-.16-.128-.112-.24-.321-.304-.641l-2.48-10.323-2.464 10.307c-.08.32-.176.529-.304.641-.128.112-.352.16-.64.16h-1.376l.016.016zm20.512.4c-.832 0-1.664-.096-2.464-.288-.8-.192-1.424-.4-1.856-.641-.272-.145-.448-.305-.528-.449a1.13 1.13 0 01-.112-.481v-.816c0-.336.128-.497.368-.497a.91.91 0 01.288.048c.096.032.24.096.4.16a8.71 8.71 0 001.728.544c.64.129 1.264.193 1.904.193 1.008 0 1.792-.177 2.336-.529.544-.353.832-.865.832-1.521 0-.449-.144-.817-.432-1.122-.288-.304-.832-.576-1.616-.832l-2.32-.72c-1.168-.37-2.032-.913-2.56-1.634-.528-.706-.8-1.49-.8-2.326 0-.672.144-1.265.432-1.777a3.96 3.96 0 011.168-1.297c.496-.353 1.056-.625 1.712-.8A7.756 7.756 0 0141.527 11c.368 0 .752.016 1.12.064.384.048.736.112 1.072.192.32.096.624.192.896.305.272.112.48.224.624.336.208.145.352.289.432.449.08.145.128.336.128.577v.752c0 .336-.128.513-.368.513a1.66 1.66 0 01-.608-.192c-.816-.37-1.728-.557-2.736-.557-.912 0-1.632.145-2.128.449-.496.305-.752.769-.752 1.41 0 .449.16.833.48 1.137.32.305.912.61 1.76.88l2.272.72c1.152.37 1.984.882 2.48 1.538.496.657.736 1.41.736 2.238 0 .688-.144 1.313-.416 1.857a4.37 4.37 0 01-1.152 1.393c-.496.385-1.088.672-1.776.865-.72.208-1.488.305-2.32.305h-.016z" fill="#FF9900" />
            <path d="M43.527 33.95c-5.216 3.872-12.784 5.936-19.296 5.936-9.12 0-17.344-3.376-23.552-8.993-.496-.449-.048-1.057.544-.706 6.72 3.904 15.008 6.257 23.584 6.257 5.792 0 12.144-1.2 18-3.68.88-.385 1.616.577.72 1.185z" fill="#FF9900" />
            <path d="M45.527 31.59c-.672-.865-4.448-.417-6.16-.21-.512.065-.592-.385-.128-.72 3.008-2.113 7.952-1.505 8.528-.793.576.72-.16 5.681-2.976 8.05-.432.368-.848.177-.656-.305.64-1.586 2.064-5.153 1.392-6.02z" fill="#FF9900" />
        </svg>
    );
}

function AzureLogo({ size = 24 }: { size?: number }) {
    return (
        <svg width={size} height={size} viewBox="0 0 48 48" fill="none">
            <path d="M17.28 5.25h12.45L16.74 42.75H5.25L17.28 5.25z" fill="#0078D4" />
            <path d="M33.48 15.75H21.9l-5.16 27h12.54l4.2-27z" fill="#0078D4" opacity="0.8" />
            <path d="M28.5 28.5L16.74 42.75h26.01L28.5 28.5z" fill="#0078D4" opacity="0.6" />
        </svg>
    );
}

function GCPLogo({ size = 24 }: { size?: number }) {
    return (
        <svg width={size} height={size} viewBox="0 -25 256 256" preserveAspectRatio="xMidYMid meet">
            <path d="M170.252 56.819L192.505 34.566L193.988 25.196C153.437-11.677 88.976-7.496 52.421 33.92C42.267 45.423 34.734 59.764 30.717 74.573L38.687 73.45L83.192 66.111L86.628 62.597C106.425 40.855 139.898 37.93 162.756 56.429L170.252 56.819Z" fill="#EA4335" />
            <path d="M224.205 73.918C219.09 55.082 208.589 38.149 193.988 25.196L162.756 56.428C175.944 67.204 183.457 83.438 183.135 100.465V106.009C198.486 106.009 210.932 118.454 210.932 133.805C210.932 149.157 198.486 161.29 183.135 161.29H127.464L121.998 167.224V200.564L127.464 205.795H183.135C223.065 206.106 255.687 174.301 255.998 134.371C256.186 110.168 244.253 87.478 224.205 73.918" fill="#4285F4" />
            <path d="M71.87 205.796H127.463V161.29H71.87C67.909 161.289 64.073 160.438 60.471 158.792L52.584 161.212L30.175 183.465L28.223 191.039C40.79 200.528 56.123 205.864 71.87 205.796" fill="#34A853" />
            <path d="M71.87 61.426C31.939 61.664-0.237 94.228 0.001 134.158C0.134 156.456 10.548 177.446 28.223 191.039L60.471 158.792C46.48 152.471 40.263 136.006 46.584 122.016C52.904 108.026 69.37 101.809 83.359 108.129C89.524 110.914 94.461 115.852 97.246 122.016L129.494 89.769C115.773 71.832 94.453 61.345 71.87 61.426" fill="#FBBC05" />
        </svg>
    );
}



// ═══════════════════════════════════════════════════════════════════
//  Feature Visuals
// ═══════════════════════════════════════════════════════════════════

// ─── 1. Multi-Cloud Scan Animation ───────────────────────────────
export function MultiCloudScan() {
    const clouds = [
        { name: "AWS", Logo: AWSLogo, color: "#FF9900", delay: 0 },
        { name: "Azure", Logo: AzureLogo, color: "#0078D4", delay: 0.15 },
        { name: "GCP", Logo: GCPLogo, color: "#4285F4", delay: 0.3 },
    ];
    const [scanned, setScanned] = useState(0);

    useEffect(() => {
        const timer = setInterval(() => {
            setScanned(prev => (prev >= 247 ? 0 : prev + Math.floor(Math.random() * 12 + 3)));
        }, 200);
        return () => clearInterval(timer);
    }, []);

    return (
        <div className="space-y-5">
            <div className="flex items-center justify-between">
                <span className="text-xs text-gray-500 uppercase tracking-widest">
                    Cloud Providers Connected
                </span>
                <span className="text-xs text-green-400 font-mono">
                    {Math.min(scanned, 247)} resources found
                </span>
            </div>
            <div className="grid grid-cols-3 gap-3">
                {clouds.map((cloud) => (
                    <motion.div
                        key={cloud.name}
                        initial={{ opacity: 0, scale: 0.8 }}
                        whileInView={{ opacity: 1, scale: 1 }}
                        viewport={{ once: true }}
                        transition={{ delay: cloud.delay, duration: 0.4 }}
                        className="flex flex-col items-center gap-2 p-3 rounded-xl bg-white/5 border border-white/10 hover:border-white/20 transition-colors"
                    >
                        <div
                            className="w-10 h-10 rounded-lg flex items-center justify-center"
                            style={{ backgroundColor: `${cloud.color}15`, border: `1px solid ${cloud.color}30` }}
                        >
                            <cloud.Logo size={28} />
                        </div>
                        <span className="text-[10px] text-gray-400">{cloud.name}</span>
                    </motion.div>
                ))}
            </div>
            {/* Scan progress bar */}
            <div className="relative h-1.5 bg-white/5 rounded-full overflow-hidden">
                <motion.div
                    className="absolute inset-y-0 left-0 bg-gradient-to-r from-primary to-secondary rounded-full"
                    animate={{ width: ["0%", "100%"] }}
                    transition={{ duration: 2.5, repeat: Infinity, ease: "easeInOut" }}
                />
            </div>
            <div className="text-center text-[10px] text-gray-500">
                Scanning 3 providers across all regions
            </div>
        </div>
    );
}

// ─── 2. Zombie/Waste Detection Visual ────────────────────────────
export function ZombieDetection() {
    const resources = [
        { name: "prod-api-server", type: "EC2", cpu: "2%", cost: "₹13K/mo", status: "zombie" },
        { name: "old-staging-db", type: "RDS", cpu: "0%", cost: "₹19.1K/mo", status: "zombie" },
        { name: "test-disk-2024", type: "EBS", cpu: "—", cost: "₹3.7K/mo", status: "orphan" },
        { name: "unused-ip-east", type: "EIP", cpu: "—", cost: "₹1.5K/mo", status: "idle" },
    ];

    return (
        <div className="space-y-2">
            <div className="flex items-center justify-between mb-3">
                <span className="text-xs text-gray-500 uppercase tracking-widest">Waste Found</span>
                <span className="text-sm font-semibold text-red-400">₹37.3K/mo wasted</span>
            </div>
            {resources.map((r, i) => (
                <motion.div
                    key={r.name}
                    initial={{ opacity: 0, x: -10 }}
                    whileInView={{ opacity: 1, x: 0 }}
                    viewport={{ once: true }}
                    transition={{ delay: i * 0.1 }}
                    className="flex items-center gap-3 p-2 rounded-lg bg-white/[0.03] border border-white/[0.06] hover:bg-white/[0.06] transition-colors"
                >
                    <div className={`w-1.5 h-1.5 rounded-full ${r.status === "zombie" ? "bg-red-500" : r.status === "orphan" ? "bg-orange-500" : "bg-yellow-500"}`} />
                    <div className="flex-1 min-w-0">
                        <div className="text-xs text-gray-300 truncate">{r.name}</div>
                        <div className="text-[10px] text-gray-500">{r.type} · CPU {r.cpu}</div>
                    </div>
                    <span className="text-xs text-red-400 font-mono whitespace-nowrap">{r.cost}</span>
                </motion.div>
            ))}
        </div>
    );
}

// ─── 3. Clousy AI Chat Visual ────────────────────────────────────
export function ClouSyChat() {
    const [typing, setTyping] = useState(false);

    useEffect(() => {
        const timer = setInterval(() => setTyping(prev => !prev), 3000);
        return () => clearInterval(timer);
    }, []);

    return (
        <div className="space-y-3">
            <div className="flex items-center gap-2 mb-2">
                <div className="w-5 h-5 rounded-full bg-gradient-to-br from-primary to-secondary flex items-center justify-center">
                    <span className="text-[8px] text-white font-bold">C</span>
                </div>
                <span className="text-xs text-gray-400">Clousy — AI Agent</span>
                <span className="text-[9px] text-green-400 flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" /> Live
                </span>
            </div>

            {/* User question */}
            <motion.div
                initial={{ opacity: 0, y: 10 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: 0.2 }}
                className="flex justify-end"
            >
                <div className="bg-primary/15 border border-primary/25 rounded-xl rounded-br-sm px-3 py-2 text-xs text-gray-200 max-w-[220px]">
                    How much am I wasting on AWS this month?
                </div>
            </motion.div>

            {/* AI response */}
            <motion.div
                initial={{ opacity: 0, y: 10 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: 0.5 }}
                className="flex gap-2"
            >
                <div className="w-5 h-5 rounded-full bg-primary/20 flex items-center justify-center text-[8px] shrink-0">C</div>
                <div className="bg-white/5 border border-white/10 rounded-xl rounded-bl-sm px-3 py-2 text-xs text-gray-300 max-w-[240px]">
                    <div className="text-[9px] text-primary/60 mb-1">🔧 Analyzing resources + cost data…</div>
                    You&apos;re wasting <span className="text-red-400 font-semibold">₹1.94L/mo</span> across <span className="text-white font-semibold">12 zombie resources</span>.
                    Top 3: idle EC2 (₹73.9K), orphan EBS (₹35.7K), unused RDS (₹26.6K).
                </div>
            </motion.div>

            {/* Typing indicator - always rendered to prevent layout shift */}
            <div className={`flex gap-2 items-center transition-opacity duration-300 ${typing ? 'opacity-100' : 'opacity-0'}`}>
                <div className="w-5 h-5 rounded-full bg-primary/20 flex items-center justify-center text-[8px] shrink-0">C</div>
                <div className="flex gap-1">
                    <motion.div className="w-1 h-1 bg-gray-500 rounded-full" animate={{ opacity: [0.2, 1, 0.2] }} transition={{ duration: 1, repeat: Infinity, delay: 0 }} />
                    <motion.div className="w-1 h-1 bg-gray-500 rounded-full" animate={{ opacity: [0.2, 1, 0.2] }} transition={{ duration: 1, repeat: Infinity, delay: 0.2 }} />
                    <motion.div className="w-1 h-1 bg-gray-500 rounded-full" animate={{ opacity: [0.2, 1, 0.2] }} transition={{ duration: 1, repeat: Infinity, delay: 0.4 }} />
                </div>
            </div>
        </div>
    );
}

// ─── 4. Executive Report Visual ──────────────────────────────────
export function ExecutiveReport() {
    return (
        <div className="space-y-3">
            <div className="flex items-center justify-between">
                <span className="text-xs text-gray-500 uppercase tracking-widest">AI-Generated Report</span>
                <span className="text-[10px] text-gray-600">Feb 2026</span>
            </div>
            <div className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.06]">
                <div className="flex items-center justify-between mb-3">
                    <span className="text-sm text-white font-medium">Infrastructure Audit</span>
                    <span className="text-xs font-bold px-2 py-0.5 rounded-md bg-green-500/15 text-green-400 border border-green-500/25">Grade: A-</span>
                </div>
                <div className="space-y-2">
                    {[
                        { label: "Total Spend", value: "₹39.2L", change: "-18%" },
                        { label: "Waste Identified", value: "₹10.7L", change: "" },
                        { label: "Actions Taken", value: "23 of 31", change: "" },
                        { label: "Compliance Score", value: "94%", change: "+6%" },
                    ].map((item, i) => (
                        <motion.div
                            key={item.label}
                            initial={{ opacity: 0, x: -10 }}
                            whileInView={{ opacity: 1, x: 0 }}
                            viewport={{ once: true }}
                            transition={{ delay: i * 0.08 }}
                            className="flex items-center justify-between text-xs"
                        >
                            <span className="text-gray-500">{item.label}</span>
                            <div className="flex items-center gap-2">
                                <span className="text-gray-200 font-mono">{item.value}</span>
                                {item.change && (
                                    <span className="text-[10px] text-green-400">
                                        {item.change}
                                    </span>
                                )}
                            </div>
                        </motion.div>
                    ))}
                </div>
            </div>
            <div className="flex gap-2">
                <div className="flex-1 text-center text-[10px] text-gray-600 py-1.5 rounded-lg bg-white/[0.02] border border-white/[0.06]">
                    📊 Export PDF
                </div>
                <div className="flex-1 text-center text-[10px] text-gray-600 py-1.5 rounded-lg bg-white/[0.02] border border-white/[0.06]">
                    📧 Share
                </div>
            </div>
        </div>
    );
}

// ─── 5. Governance & Compliance Visual ───────────────────────────
export function GovernanceVisual() {
    const policies = [
        { name: "Resource Tagging", score: 87, status: "pass" },
        { name: "Region Compliance", score: 94, status: "pass" },
        { name: "Network Security", score: 72, status: "warn" },
        { name: "Storage Encryption", score: 96, status: "pass" },
        { name: "Cost Waste", score: 65, status: "fail" },
    ];

    return (
        <div className="space-y-3">
            <div className="flex items-center justify-between">
                <span className="text-xs text-gray-500 uppercase tracking-widest">Governance Score</span>
                <div className="flex items-baseline gap-1">
                    <span className="text-2xl font-bold text-white">83</span>
                    <span className="text-xs text-gray-500">/100</span>
                </div>
            </div>
            <div className="space-y-1.5">
                {policies.map((p, i) => (
                    <motion.div
                        key={p.name}
                        initial={{ opacity: 0, x: -10 }}
                        whileInView={{ opacity: 1, x: 0 }}
                        viewport={{ once: true }}
                        transition={{ delay: i * 0.08 }}
                        className="flex items-center gap-2"
                    >
                        <span className="text-xs text-gray-400 w-28 truncate">{p.name}</span>
                        <div className="flex-1 h-1.5 rounded-full bg-white/5 overflow-hidden">
                            <motion.div
                                className={`h-full rounded-full ${p.score >= 90 ? "bg-green-500" : p.score >= 75 ? "bg-yellow-500" : "bg-red-500"
                                    }`}
                                initial={{ width: 0 }}
                                whileInView={{ width: `${p.score}%` }}
                                viewport={{ once: true }}
                                transition={{ delay: i * 0.1, duration: 0.6 }}
                            />
                        </div>
                        <span className="text-[10px] text-gray-500 font-mono w-6 text-right">{p.score}%</span>
                    </motion.div>
                ))}
            </div>
        </div>
    );
}

// ─── 6. Security Architecture Visual ─────────────────────────────
export function SecurityVisual() {
    const layers = [
        { icon: "🔐", label: "AES-256 Encryption", desc: "All credentials encrypted at rest", active: true },
        { icon: "🛡️", label: "Row-Level Security", desc: "Complete tenant data isolation", active: true },
        { icon: "👁️", label: "Read-Only Cloud Access", desc: "We never modify your resources", active: true },
        { icon: "🔑", label: "JWT Token Verification", desc: "Clerk-powered authentication", active: true },
        { icon: "🌐", label: "TLS 1.3 Transport", desc: "End-to-end encrypted connections", active: true },
    ];

    return (
        <div className="space-y-2">
            <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-gray-500 uppercase tracking-widest">Security Layers</span>
                <span className="text-[10px] text-green-400 flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-green-400" /> All Active
                </span>
            </div>
            {layers.map((layer, i) => (
                <motion.div
                    key={layer.label}
                    initial={{ opacity: 0, x: -10 }}
                    whileInView={{ opacity: 1, x: 0 }}
                    viewport={{ once: true }}
                    transition={{ delay: i * 0.08 }}
                    className="flex items-center gap-3 p-2 rounded-lg bg-white/[0.03] border border-white/[0.06]"
                >
                    <span className="text-sm">{layer.icon}</span>
                    <div className="flex-1 min-w-0">
                        <div className="text-xs text-gray-200">{layer.label}</div>
                        <div className="text-[10px] text-gray-500">{layer.desc}</div>
                    </div>
                    <div className="w-4 h-4 rounded-full bg-green-500/15 border border-green-500/30 flex items-center justify-center">
                        <span className="text-green-400 text-[8px]">✓</span>
                    </div>
                </motion.div>
            ))}
        </div>
    );
}

// ─── 7. Spend Trends & Anomaly Detection Visual ─────────────────
export function SpendTrendsVisual() {
    const data = [
        { month: "Mar", value: 32, spend: "₹26.6L" },
        { month: "Apr", value: 28, spend: "₹23.2L" },
        { month: "May", value: 35, spend: "₹29.1L" },
        { month: "Jun", value: 31, spend: "₹25.7L" },
        { month: "Jul", value: 29, spend: "₹24.1L" },
        { month: "Aug", value: 34, spend: "₹28.2L" },
        { month: "Sep", value: 72, spend: "₹59.8L", anomaly: true },
        { month: "Oct", value: 38, spend: "₹31.5L" },
        { month: "Nov", value: 30, spend: "₹24.9L" },
        { month: "Dec", value: 33, spend: "₹27.4L" },
        { month: "Jan", value: 27, spend: "₹22.4L" },
        { month: "Feb", value: 31, spend: "₹25.7L" },
    ];

    const maxVal = 80; // Fixed scale so bars are proportional
    const chartHeight = 120; // pixels

    const [animated, setAnimated] = useState(false);
    useEffect(() => {
        const timer = setTimeout(() => setAnimated(true), 300);
        return () => clearTimeout(timer);
    }, []);

    return (
        <div className="space-y-3">
            <div className="flex items-center justify-between">
                <span className="text-xs text-gray-500 uppercase tracking-widest">Daily Spend Trend</span>
                <span className="text-[10px] text-red-400 flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-red-400 animate-pulse" /> Anomaly Detected
                </span>
            </div>

            {/* Chart */}
            <div className="p-3 rounded-xl bg-white/[0.02] border border-white/[0.06]">
                {/* Chart area */}
                <div className="flex gap-0.5">
                    {/* Y-axis */}
                    <div className="flex flex-col justify-between text-[8px] text-gray-600 pr-1" style={{ height: `${chartHeight}px` }}>
                        <span>₹66L</span>
                        <span>₹50L</span>
                        <span>₹33L</span>
                        <span>₹17L</span>
                        <span>₹0</span>
                    </div>

                    {/* Bars container */}
                    <div className="flex-1 relative">
                        {/* Horizontal grid lines */}
                        {[0, 25, 50, 75, 100].map((pct) => (
                            <div
                                key={pct}
                                className="absolute left-0 right-0 border-t border-white/[0.04]"
                                style={{ top: `${pct}%` }}
                            />
                        ))}

                        {/* Bars */}
                        <div className="flex items-end gap-[3px] relative" style={{ height: `${chartHeight}px` }}>
                            {data.map((d, i) => {
                                const barHeight = animated ? Math.round((d.value / maxVal) * chartHeight) : 0;
                                return (
                                    <div key={i} className="flex-1 flex flex-col items-center justify-end" style={{ height: `${chartHeight}px` }}>
                                        <div
                                            className={`w-full rounded-t-sm transition-all duration-700 ease-out ${d.anomaly
                                                ? "bg-red-500 shadow-[0_0_16px_rgba(239,68,68,0.5)]"
                                                : "bg-primary"
                                                }`}
                                            style={{
                                                height: `${barHeight}px`,
                                                transitionDelay: `${i * 50}ms`,
                                                background: d.anomaly
                                                    ? "linear-gradient(to top, #991b1b, #ef4444, #f87171)"
                                                    : "linear-gradient(to top, #814AC8, #DF7AFE)",
                                            }}
                                        />
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                </div>

                {/* X-axis labels */}
                <div className="flex mt-1.5 ml-7">
                    <div className="flex-1 flex gap-[3px]">
                        {data.map((d, i) => (
                            <span key={i} className={`flex-1 text-center text-[7px] ${d.anomaly ? "text-red-400 font-bold" : "text-gray-600"}`}>
                                {d.month}
                            </span>
                        ))}
                    </div>
                </div>
            </div>

            {/* Anomaly alert */}
            <div className="flex items-center gap-2 p-2 rounded-lg bg-red-500/10 border border-red-500/20">
                <span className="text-xs">⚠️</span>
                <span className="text-[10px] text-red-300">
                    Sep spike: <span className="font-semibold text-red-400">+127%</span> —
                    12 new untagged resources detected
                </span>
            </div>
        </div>
    );
}

// ─── 8. AI Fix Script Generation Visual ──────────────────────────
export function FixScriptVisual() {
    const [step, setStep] = useState(0);

    useEffect(() => {
        const timer = setInterval(() => {
            setStep(prev => (prev >= 3 ? 0 : prev + 1));
        }, 2000);
        return () => clearInterval(timer);
    }, []);

    const lines = [
        { type: "comment", text: "# AI-Generated Fix for: idle EC2 i-0abc12345" },
        { type: "command", text: "aws ec2 stop-instances \\" },
        { type: "flag", text: "  --instance-ids i-0abc12345 \\" },
        { type: "flag", text: "  --region us-east-1" },
    ];

    return (
        <div className="space-y-3">
            <div className="flex items-center justify-between">
                <span className="text-xs text-gray-500 uppercase tracking-widest">AI Fix Generator</span>
                <span className="text-[10px] text-primary flex items-center gap-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" /> Generating
                </span>
            </div>
            <div className="p-3 rounded-xl bg-gray-950 border border-white/10 font-mono text-[11px]">
                <div className="flex items-center gap-2 mb-3 pb-2 border-b border-white/5">
                    <div className="w-2 h-2 rounded-full bg-red-500/60" />
                    <div className="w-2 h-2 rounded-full bg-yellow-500/60" />
                    <div className="w-2 h-2 rounded-full bg-green-500/60" />
                    <span className="text-[9px] text-gray-600 ml-2">terminal</span>
                </div>
                {lines.map((line, i) => (
                    <motion.div
                        key={i}
                        initial={{ opacity: 0 }}
                        animate={{ opacity: i <= step ? 1 : 0.2 }}
                        transition={{ duration: 0.3 }}
                        className={`leading-relaxed ${line.type === "comment" ? "text-gray-500"
                            : line.type === "command" ? "text-green-400"
                                : "text-cyan-400"
                            }`}
                    >
                        {i <= step && line.type === "command" && <span className="text-gray-500">$ </span>}
                        {line.text}
                    </motion.div>
                ))}
            </div>
            <div className="flex gap-2">
                <div className="flex-1 text-center text-[10px] py-1.5 rounded-lg bg-green-500/10 border border-green-500/25 text-green-400">
                    ✓ Copy & Execute
                </div>
                <div className="flex-1 text-center text-[10px] py-1.5 rounded-lg bg-white/[0.03] border border-white/10 text-gray-500">
                    ↻ Regenerate
                </div>
            </div>
        </div>
    );
}

// ─── 9. Carbon Footprint Visual ──────────────────────────────────
export function CarbonFootprintVisual() {
    return (
        <div className="space-y-3">
            <div className="flex items-center justify-between">
                <span className="text-xs text-gray-500 uppercase tracking-widest">Carbon Impact</span>
                <span className="text-[10px] text-green-400">Updated live from scans</span>
            </div>
            <div className="grid grid-cols-2 gap-2">
                {[
                    { icon: "🌍", label: "Monthly CO₂", value: "2.4 tons", sub: "from cloud usage" },
                    { icon: "📉", label: "After Cleanup", value: "1.6 tons", sub: "33% reduction" },
                    { icon: "🌳", label: "Trees Needed", value: "120", sub: "to offset annually" },
                    { icon: "🚗", label: "Car Equivalent", value: "6.2", sub: "cars off road/year" },
                ].map((item, i) => (
                    <motion.div
                        key={item.label}
                        initial={{ opacity: 0, scale: 0.9 }}
                        whileInView={{ opacity: 1, scale: 1 }}
                        viewport={{ once: true }}
                        transition={{ delay: i * 0.1 }}
                        className="p-3 rounded-xl bg-white/[0.03] border border-white/[0.06] text-center"
                    >
                        <span className="text-lg">{item.icon}</span>
                        <div className="text-sm font-semibold text-white mt-1">{item.value}</div>
                        <div className="text-[9px] text-gray-500">{item.label}</div>
                        <div className="text-[8px] text-gray-600 mt-0.5">{item.sub}</div>
                    </motion.div>
                ))}
            </div>
            <div className="h-1 rounded-full bg-white/5 overflow-hidden">
                <motion.div
                    className="h-full rounded-full bg-gradient-to-r from-green-500 to-emerald-400"
                    initial={{ width: 0 }}
                    whileInView={{ width: "67%" }}
                    viewport={{ once: true }}
                    transition={{ duration: 1, delay: 0.3 }}
                />
            </div>
            <div className="text-center text-[9px] text-gray-600">67% of carbon offset possible through optimization</div>
        </div>
    );
}

// ─── 10. Shadow IT Detection Visual ──────────────────────────────
export function ShadowITVisual() {
    const detections = [
        { resource: "rogue-dev-vm", region: "ap-southeast-1", risk: "High", provider: "AWS" },
        { resource: "test-bucket-prod", region: "eu-west-3", risk: "Medium", provider: "AWS" },
        { resource: "staging-db-unauth", region: "ap-south-1", risk: "High", provider: "Azure" },
    ];

    return (
        <div className="space-y-3">
            <div className="flex items-center justify-between">
                <span className="text-xs text-gray-500 uppercase tracking-widest">Shadow IT Alerts</span>
                <span className="text-xs text-orange-400 font-semibold">3 detections</span>
            </div>
            {detections.map((d, i) => (
                <motion.div
                    key={d.resource}
                    initial={{ opacity: 0, x: -10 }}
                    whileInView={{ opacity: 1, x: 0 }}
                    viewport={{ once: true }}
                    transition={{ delay: i * 0.12 }}
                    className="p-2.5 rounded-lg bg-orange-500/5 border border-orange-500/15 hover:border-orange-500/30 transition-colors"
                >
                    <div className="flex items-center justify-between mb-1">
                        <span className="text-xs text-gray-200 font-mono">{d.resource}</span>
                        <span className={`text-[9px] px-1.5 py-0.5 rounded-md ${d.risk === "High"
                            ? "bg-red-500/15 text-red-400 border border-red-500/25"
                            : "bg-yellow-500/15 text-yellow-400 border border-yellow-500/25"
                            }`}>{d.risk}</span>
                    </div>
                    <div className="flex items-center gap-2 text-[10px] text-gray-500">
                        <span>📍 {d.region}</span>
                        <span>·</span>
                        <span>{d.provider}</span>
                        <span>·</span>
                        <span className="text-orange-400">Unauthorized Region</span>
                    </div>
                </motion.div>
            ))}
            <div className="text-center text-[9px] text-gray-600">
                Resources outside approved regions flagged automatically
            </div>
        </div>
    );
}

// ─── 11. Action Workflow Visual ───────────────────────
export function ActionExecutionVisual() {
    const [actions, setActions] = useState([
        { id: 1, label: "Terminate idle EC2 i-0abc", savings: "₹13K/mo", status: "pending" as const },
        { id: 2, label: "Delete orphan EBS vol-xyz", savings: "₹3.7K/mo", status: "resolved" as const },
        { id: 3, label: "Stop unused RDS db-prod-2", savings: "₹19.1K/mo", status: "pending" as const },
    ]);

    useEffect(() => {
        const timer = setInterval(() => {
            setActions(prev => prev.map(a =>
                a.status === "resolved" ? { ...a, status: "pending" as const } :
                    a.id === 1 && a.status === "pending" ? { ...a, status: "resolved" as const } :
                        a
            ));
        }, 4000);
        return () => clearInterval(timer);
    }, []);

    return (
        <div className="space-y-3">
            <div className="flex items-center justify-between">
                <span className="text-xs text-gray-500 uppercase tracking-widest">Pending Actions</span>
                <span className="text-xs text-primary font-mono">3 awaiting</span>
            </div>
            {actions.map((action, i) => (
                <motion.div
                    key={action.id}
                    initial={{ opacity: 0, y: 10 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ delay: i * 0.1 }}
                    className={`p-2.5 rounded-lg border transition-all duration-500 ${action.status === "resolved"
                        ? "bg-green-500/10 border-green-500/25"
                        : "bg-white/[0.02] border-white/[0.08]"
                        }`}
                >
                    <div className="flex items-center justify-between mb-1.5">
                        <span className="text-xs text-gray-200">{action.label}</span>
                        <span className="text-[10px] text-green-400 font-mono">{action.savings}</span>
                    </div>
                    <div className="flex gap-1.5">
                        <motion.div
                            animate={{
                                backgroundColor: action.status === "resolved" ? "rgba(34, 197, 94, 0.2)" : "rgba(34, 197, 94, 0.08)",
                                borderColor: action.status === "resolved" ? "rgba(34, 197, 94, 0.4)" : "rgba(34, 197, 94, 0.15)",
                            }}
                            className="flex-1 text-center text-[10px] py-1 rounded-md text-green-400 border cursor-pointer"
                        >
                            {action.status === "resolved" ? "✓ Resolved" : "Resolve"}
                        </motion.div>
                        <div className="flex-1 text-center text-[10px] py-1 rounded-md bg-white/[0.02] border border-white/[0.08] text-gray-500 cursor-pointer">
                            Dismiss
                        </div>
                    </div>
                </motion.div>
            ))}
        </div>
    );
}

// ─── Legacy Exports (kept for compatibility) ─────────────────────
export function AnimatedChart() {
    const [values, setValues] = useState([40, 65, 45, 80, 60, 90, 75]);

    useEffect(() => {
        const interval = setInterval(() => {
            setValues(prev => prev.map(v => Math.max(20, Math.min(95, v + (Math.random() - 0.5) * 20))));
        }, 2000);
        return () => clearInterval(interval);
    }, []);

    return (
        <div className="h-32 flex items-end justify-between gap-2 px-4">
            {values.map((value, i) => (
                <motion.div
                    key={i}
                    className="flex-1 bg-gradient-to-t from-primary to-secondary rounded-t"
                    initial={{ height: 0 }}
                    animate={{ height: `${value}%` }}
                    transition={{ duration: 0.8, ease: "easeOut" }}
                />
            ))}
        </div>
    );
}

export function RadarScan() {
    return (
        <div className="relative w-32 h-32 mx-auto">
            <div className="absolute inset-0 rounded-full border border-primary/20" />
            <div className="absolute inset-4 rounded-full border border-primary/30" />
            <div className="absolute inset-8 rounded-full border border-primary/40" />
            <motion.div
                className="absolute top-1/2 left-1/2 w-1/2 h-0.5 bg-gradient-to-r from-primary to-transparent origin-left"
                animate={{ rotate: 360 }}
                transition={{ duration: 3, repeat: Infinity, ease: "linear" }}
                style={{ transformOrigin: "0% 50%" }}
            />
            <div className="absolute top-1/2 left-1/2 w-2 h-2 -translate-x-1/2 -translate-y-1/2 bg-primary rounded-full" />
        </div>
    );
}

export function AIChatBubbles() {
    return <ClouSyChat />;
}

export function SecurityScan() {
    return <SecurityVisual />;
}

export function DashboardMockup() {
    return <ExecutiveReport />;
}
