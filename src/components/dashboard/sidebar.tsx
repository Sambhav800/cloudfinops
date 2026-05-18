"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
    Bell,
    Bot,
    Calculator,
    CalendarClock,
    ChevronLeft,
    Coins,
    Cpu,
    FileBarChart2,
    GitCompare,
    LayoutDashboard,
    Layers,
    LogOut,
    Menu,
    Network,
    Percent,
    PiggyBank,
    Receipt,
    ScrollText,
    Server,
    Settings,
    ShieldAlert,
    ShieldCheck,
    Telescope,
    TrendingDown,
    X,
} from "lucide-react";
import { useEffect, useState } from "react";
import Image from "next/image";
import { useClerk } from "@clerk/nextjs";
import { useSidebar } from "@/components/dashboard/sidebar-context";
import {
    buildBillScanHref,
    getBillAnalysisId,
    LAST_ANALYSIS_STORAGE_KEY,
    shouldEnableBillAnalysisNav,
} from "@/lib/bill-analysis-client-state";

type NavItem = {
    activePrefixes?: string[];
    badge?: string;
    href: string;
    icon: typeof LayoutDashboard;
    key: string;
    name: string;
};

type NavSection = {
    icon: typeof LayoutDashboard;
    items: NavItem[];
    name: string;
};

const navigationSections: NavSection[] = [
    {
        name: "Discover",
        icon: Telescope,
        items: [
            { key: "dashboard", name: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
            { key: "resources", name: "Resources", href: "/dashboard/resources", icon: Server },
            { key: "total-bill", name: "Total Bill", href: "/dashboard/totalbill", icon: Layers, badge: "Multi-cloud" },
            { key: "multi-cloud", name: "Multi-Cloud", href: "/dashboard/multicloud", icon: GitCompare },
        ],
    },
    {
        name: "Govern",
        icon: Coins,
        items: [
            {
                key: "savings",
                name: "Savings",
                href: "/dashboard/pending-actions",
                icon: TrendingDown,
            },
            { key: "forecast", name: "Forecast", href: "/dashboard/forecast", icon: CalendarClock },
            { key: "commitments", name: "Commitments", href: "/dashboard/commitments", icon: PiggyBank },
            { key: "discount-manager", name: "Discounts", href: "/dashboard/discount-manager", icon: Percent },
            { key: "reports", name: "Reports", href: "/dashboard/reports", icon: FileBarChart2 },
        ],
    },
    {
        name: "Secure",
        icon: ShieldCheck,
        items: [
            { key: "governance", name: "Governance", href: "/dashboard/governance", icon: ShieldCheck },
            { key: "security", name: "Security", href: "/dashboard/security", icon: ShieldAlert },
            { key: "audit", name: "Audit Logs", href: "/dashboard/audit", icon: ScrollText },
        ],
    },
    {
        name: "Intelligence",
        icon: Bot,
        items: [
            { key: "architecture", name: "Architecture", href: "/dashboard/architecture", icon: Network },
            {
                key: "bill-scanner",
                name: "Bill Scanner",
                href: "/dashboard/arbitrage",
                icon: Receipt,
                activePrefixes: ["/dashboard/arbitrage"],
            },
            { key: "simulator", name: "Simulator", href: "/dashboard/simulator", icon: Calculator },
            { key: "alerts", name: "Alerts", href: "/dashboard/alerts", icon: Bell },
            { key: "gpu", name: "GPU Intelligence", href: "/dashboard/gpu", icon: Cpu },
        ],
    },
];

const bottomNavigation: NavItem[] = [
    { key: "settings", name: "Settings", href: "/dashboard/settings", icon: Settings },
];

function isPathActive(pathname: string, prefixes: string[]) {
    return prefixes.some((prefix) => {
        if (prefix === "/dashboard") {
            return pathname === prefix;
        }

        return pathname === prefix || pathname.startsWith(`${prefix}/`);
    });
}

function readPersistedBillAnalysisId(): string | null {
    if (typeof window === "undefined") {
        return null;
    }

    try {
        return getBillAnalysisId(window.localStorage.getItem(LAST_ANALYSIS_STORAGE_KEY));
    } catch {
        return null;
    }
}

export function Sidebar() {
    const pathname = usePathname();
    const { collapsed, setCollapsed } = useSidebar();
    const [mobileOpen, setMobileOpen] = useState(false);
    const [billFeatureEnabled, setBillFeatureEnabled] = useState<boolean | null>(null);
    const [persistedAnalysisId, setPersistedAnalysisId] = useState<string | null>(readPersistedBillAnalysisId);
    const [latestBillAnalysisId, setLatestBillAnalysisId] = useState<string | null>(null);
    const { signOut } = useClerk();

    useEffect(() => {
        if (typeof window === "undefined") {
            return;
        }

        let active = true;

        const syncPersistedAnalysisId = () => {
            if (!active) {
                return;
            }
            setPersistedAnalysisId(readPersistedBillAnalysisId());
        };

        const loadBillFeatureState = async () => {
            try {
                const [featuresResponse, billAnalysesResponse] = await Promise.all([
                    fetch("/api/user/features", {
                        cache: "no-store",
                    }),
                    fetch("/api/bill-analyses?limit=1", {
                        cache: "no-store",
                    }),
                ]);

                let enabled: boolean | null = null;
                if (featuresResponse.ok) {
                    const featuresPayload = await featuresResponse.json() as {
                        features?: string[];
                        feature_details?: Record<string, { enabled?: boolean }>;
                    };
                    enabled = Array.isArray(featuresPayload.features) && featuresPayload.features.includes("bill_analysis")
                        || Boolean(featuresPayload.feature_details?.bill_analysis?.enabled);
                }

                let latestAnalysisId: string | null = null;
                if (billAnalysesResponse.ok) {
                    const billAnalysesPayload = await billAnalysesResponse.json() as {
                        analyses?: Array<{ analysis_id?: string | null; id?: string | null }>;
                    };
                    latestAnalysisId = getBillAnalysisId(billAnalysesPayload.analyses?.[0]);
                }

                if (active) {
                    setBillFeatureEnabled(enabled);
                    setLatestBillAnalysisId(latestAnalysisId);
                }
            } catch {
                if (active) {
                    setBillFeatureEnabled(null);
                    setLatestBillAnalysisId(null);
                }
            }
        };

        const handleStorage = (event: StorageEvent) => {
            if (!event.key || event.key === LAST_ANALYSIS_STORAGE_KEY) {
                syncPersistedAnalysisId();
            }
        };

        syncPersistedAnalysisId();
        void loadBillFeatureState();
        window.addEventListener("storage", handleStorage);

        return () => {
            active = false;
            window.removeEventListener("storage", handleStorage);
        };
    }, [pathname]);

    const effectiveBillAnalysisId = persistedAnalysisId || latestBillAnalysisId;
    const billHasResult = shouldEnableBillAnalysisNav({
        featureEnabled: billFeatureEnabled === true || Boolean(latestBillAnalysisId),
        persistedAnalysisId: effectiveBillAnalysisId,
        pathname,
    });
    const billHref = billFeatureEnabled === false && !latestBillAnalysisId && !billHasResult
        ? "/dashboard/settings"
        : buildBillScanHref(effectiveBillAnalysisId);
    const itemClassName = (isActive: boolean) => `flex w-full items-center gap-3 rounded-xl border px-3 py-2.5 text-sm transition-all duration-150 ${isActive
        ? "border-indigo-500/30 bg-indigo-500/10 text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]"
        : "border-transparent text-slate-400 hover:border-white/10 hover:bg-white/[0.03] hover:text-slate-200"
        } ${collapsed ? "lg:justify-center lg:px-2" : ""}`;
    const renderTooltip = (label: string) => {
        if (!collapsed) {
            return null;
        }

        return (
            <span className="pointer-events-none absolute left-full top-1/2 z-50 ml-3 hidden -translate-y-1/2 whitespace-nowrap rounded-md border border-white/10 bg-slate-800 px-2 py-1 text-xs text-white opacity-0 transition-opacity duration-150 group-hover:opacity-100 lg:block">
                {label}
            </span>
        );
    };

    return (
        <>
            {/* Mobile menu button */}
            <button
                className="fixed left-4 top-4 z-50 rounded-xl border border-white/10 bg-slate-900/90 p-2 text-white shadow-lg backdrop-blur-xl lg:hidden"
                onClick={() => setMobileOpen(!mobileOpen)}
            >
                {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </button>

            {/* Sidebar */}
            <aside
                className={`fixed left-0 top-0 z-40 h-full border-r border-white/10 bg-slate-950/95 shadow-2xl shadow-black/30 backdrop-blur-xl transition-all duration-300
          ${mobileOpen ? "translate-x-0" : "-translate-x-full"} 
          lg:translate-x-0
          ${collapsed ? "lg:w-20" : "lg:w-64"}
        `}
            >
                <div className="flex flex-col h-full">
                    <Link href="/" className={`flex items-center gap-3 border-b border-white/10 px-4 py-5 ${collapsed ? "lg:justify-center" : ""}`}>
                        <div className="relative h-12 w-12 flex-shrink-0">
                            <Image
                                src="/logo-main.png"
                                alt="CloudFinOps"
                                fill
                                className="object-contain"
                            />
                        </div>
                        <div className={`${collapsed ? "lg:hidden" : "block"}`}>
                            <span className="text-sm font-semibold tracking-tight text-white">CloudFinOps</span>
                            <div className="mt-1 flex items-center gap-2">
                                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                                <p className="text-[11px] text-slate-500">Enterprise workspace</p>
                            </div>
                        </div>
                    </Link>

                    <nav className="flex-1 overflow-y-auto py-3">
                        {navigationSections.map((section, index) => (
                            <div
                                key={section.name}
                                className={`${index === 0 ? "" : "mt-3 border-t border-white/5"}`}
                            >
                                {!collapsed && (
                                    <div className={`flex items-center gap-2 px-4 pb-1 ${index === 0 ? "pt-1" : "pt-5"}`}>
                                        <section.icon className="h-3.5 w-3.5 text-slate-500" />
                                        <span className="text-[10px] font-semibold uppercase tracking-[0.24em] text-slate-500">
                                            {section.name}
                                        </span>
                                    </div>
                                )}

                                <div className={`space-y-1 px-4 ${collapsed ? (index === 0 ? "pt-2" : "pt-3") : ""}`}>
                                    {section.items.map((item) => {
                                        const isBillScanner = item.key === "bill-scanner";
                                        const href = isBillScanner ? billHref : item.href;
                                        const isActive = isPathActive(pathname, item.activePrefixes ?? [item.href]);
                                        const showBillStatusDot = isBillScanner && billHasResult;

                                        return (
                                            <div key={item.key} className="relative group">
                                                <Link
                                                    href={href}
                                                    aria-label={item.name}
                                                    onClick={() => setMobileOpen(false)}
                                                    className={itemClassName(isActive)}
                                                >
                                                    <item.icon className="h-4 w-4 flex-shrink-0" />
                                                    <span className={`${collapsed ? "lg:hidden" : "block"}`}>{item.name}</span>
                                                    {!collapsed && (item.badge || showBillStatusDot) ? (
                                                        <span className="ml-auto flex items-center gap-2">
                                                            {showBillStatusDot ? (
                                                                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" />
                                                            ) : null}
                                                            {item.badge ? (
                                                                <span className="rounded-full border border-indigo-500/20 bg-indigo-500/10 px-2 py-0.5 text-[10px] font-medium text-indigo-400">
                                                                    {item.badge}
                                                                </span>
                                                            ) : null}
                                                        </span>
                                                    ) : null}
                                                </Link>
                                                {renderTooltip(item.name)}
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>
                        ))}
                    </nav>

                    {/* Collapse button (desktop only) */}
                    <button
                        onClick={() => setCollapsed(!collapsed)}
                        className="hidden items-center justify-center border-t border-white/10 p-4 text-slate-400 transition-colors hover:text-white lg:flex"
                    >
                        <ChevronLeft className={`h-5 w-5 transition-transform duration-300 ${collapsed ? "rotate-180" : ""}`} />
                        {!collapsed && <span className="ml-2 text-sm">Collapse</span>}
                    </button>

                    <div className="space-y-1 border-t border-white/10 bg-slate-950/40 p-4">
                        {bottomNavigation.map((item) => {
                            const isActive = isPathActive(pathname, [item.href]);

                            return (
                                <div key={item.key} className="relative group">
                                    <Link
                                        href={item.href}
                                        aria-label={item.name}
                                        onClick={() => setMobileOpen(false)}
                                        className={itemClassName(isActive)}
                                    >
                                        <item.icon className="h-4 w-4 flex-shrink-0" />
                                        <span className={`${collapsed ? "lg:hidden" : "block"}`}>{item.name}</span>
                                    </Link>
                                    {renderTooltip(item.name)}
                                </div>
                            );
                        })}

                        <div className="relative group">
                            <button
                                onClick={() => signOut({ redirectUrl: "/" })}
                                aria-label="Sign Out"
                                className={itemClassName(false)}
                            >
                                <LogOut className="h-4 w-4 flex-shrink-0" />
                                <span className={`${collapsed ? "lg:hidden" : "block"}`}>Sign Out</span>
                            </button>
                            {renderTooltip("Sign Out")}
                        </div>
                    </div>
                </div>
            </aside>

            {/* Mobile overlay */}
            {mobileOpen && (
                <div
                    className="lg:hidden fixed inset-0 bg-black/50 z-30"
                    onClick={() => setMobileOpen(false)}
                />
            )}
        </>
    );
}
