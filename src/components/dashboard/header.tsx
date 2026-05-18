"use client";

import {
    Bell,
    Bot,
    Calculator,
    CalendarClock,
    ChevronRight,
    Cpu,
    FileText,
    GitCompare,
    LayoutDashboard,
    Layers,
    Network,
    PiggyBank,
    Receipt,
    ScrollText,
    Search,
    Server,
    Settings,
    Shield,
    TrendingUp,
    type LucideIcon,
    X,
} from "lucide-react";
import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { UserButton } from "@clerk/nextjs";
import { usePathname, useRouter } from "next/navigation";

import { useNotifications } from "@/components/dashboard/notification-provider";

type DashboardRoute = {
    description: string;
    href: string;
    icon: LucideIcon;
    id: string;
    label: string;
    matchPrefixes?: string[];
    pageTitle: string;
    section: string;
};

const DASHBOARD_ROUTES: DashboardRoute[] = [
    {
        id: "dashboard",
        label: "Dashboard",
        href: "/dashboard",
        section: "Discover",
        pageTitle: "Portfolio Command Center",
        description: "Review spend, waste, budget drift, and operating priorities across connected cloud accounts.",
        icon: LayoutDashboard,
    },
    {
        id: "resources",
        label: "Resources",
        href: "/dashboard/resources",
        section: "Discover",
        pageTitle: "Resource Inventory",
        description: "Inspect utilization, ownership, and risk signals across the live cloud estate.",
        icon: Server,
    },
    {
        id: "total-bill",
        label: "Total Bill",
        href: "/dashboard/totalbill",
        section: "Discover",
        pageTitle: "Normalized Bill View",
        description: "Compare normalized spend across providers, services, and billing periods.",
        icon: Layers,
    },
    {
        id: "multi-cloud",
        label: "Multi-Cloud",
        href: "/dashboard/multicloud",
        section: "Discover",
        pageTitle: "Multi-Cloud Analysis",
        description: "Review cross-provider posture, concentration, and cost distribution in one place.",
        icon: GitCompare,
    },
    {
        id: "savings",
        label: "Savings",
        href: "/dashboard/pending-actions",
        section: "Govern",
        pageTitle: "Savings Pipeline",
        description: "Prioritize cost actions by impact, effort, and operational risk.",
        icon: TrendingUp,
    },
    {
        id: "forecast",
        label: "Forecast",
        href: "/dashboard/forecast",
        section: "Govern",
        pageTitle: "Budget Copilot",
        description: "Track month-end spend risk with portfolio and account-level projections.",
        icon: CalendarClock,
    },
    {
        id: "commitments",
        label: "Commitments",
        href: "/dashboard/commitments",
        section: "Govern",
        pageTitle: "Commitment Planning",
        description: "Evaluate commitment coverage and recommended purchase scenarios.",
        icon: PiggyBank,
    },
    {
        id: "reports",
        label: "Reports",
        href: "/dashboard/reports",
        section: "Govern",
        pageTitle: "Reporting Center",
        description: "Access executive summaries, exports, and scheduled reporting outputs.",
        icon: FileText,
    },
    {
        id: "governance",
        label: "Governance",
        href: "/dashboard/governance",
        section: "Secure",
        pageTitle: "Governance Posture",
        description: "Monitor policy adherence, violations, and governance coverage across accounts.",
        icon: Shield,
    },
    {
        id: "security",
        label: "Security",
        href: "/dashboard/security",
        section: "Secure",
        pageTitle: "Security Posture",
        description: "Review exposed resources, findings, and cloud security status signals.",
        icon: Shield,
    },
    {
        id: "audit",
        label: "Audit Logs",
        href: "/dashboard/audit",
        section: "Secure",
        pageTitle: "Audit Trail",
        description: "Trace user actions, recommendation approvals, and compliance events.",
        icon: ScrollText,
    },
    {
        id: "architecture",
        label: "Architecture",
        href: "/dashboard/architecture",
        section: "Intelligence",
        pageTitle: "Architecture Workspace",
        description: "Understand topology, dependencies, and generated change proposals.",
        icon: Network,
    },
    {
        id: "bill-scanner",
        label: "Bill Scanner",
        href: "/dashboard/arbitrage",
        matchPrefixes: ["/dashboard/arbitrage"],
        section: "Intelligence",
        pageTitle: "Bill Intelligence",
        description: "Analyze invoices, compare cloud pricing, and surface arbitrage opportunities.",
        icon: Receipt,
    },
    {
        id: "simulator",
        label: "Simulator",
        href: "/dashboard/simulator",
        section: "Intelligence",
        pageTitle: "Change Simulator",
        description: "Model cost deltas before approving infrastructure changes.",
        icon: Calculator,
    },
    {
        id: "alerts",
        label: "Alerts",
        href: "/dashboard/alerts",
        section: "Intelligence",
        pageTitle: "Alert Center",
        description: "Triages workflow alerts, recommendations, and operational exceptions.",
        icon: Bell,
    },
    {
        id: "gpu",
        label: "GPU Intelligence",
        href: "/dashboard/gpu",
        section: "Intelligence",
        pageTitle: "GPU Intelligence",
        description: "Track accelerator utilization, spend concentration, and scheduling opportunities.",
        icon: Cpu,
    },
    {
        id: "settings",
        label: "Settings",
        href: "/dashboard/settings",
        section: "Workspace",
        pageTitle: "Workspace Settings",
        description: "Manage integrations, feature access, and workspace-level configuration.",
        icon: Settings,
    },
];

const DEFAULT_ROUTE_META = {
    section: "Workspace",
    pageTitle: "CloudFinOps Workspace",
    description: "Monitor cloud cost, governance, and automation workflows across the platform.",
};

function isPathActive(pathname: string, prefixes: string[]) {
    return prefixes.some((prefix) => {
        if (prefix === "/dashboard") {
            return pathname === prefix;
        }

        return pathname === prefix || pathname.startsWith(`${prefix}/`);
    });
}

function getActiveRoute(pathname: string) {
    return DASHBOARD_ROUTES.find((route) => isPathActive(pathname, route.matchPrefixes ?? [route.href]));
}

export function Header() {
    const [showSearch, setShowSearch] = useState(false);
    const [searchQuery, setSearchQuery] = useState("");
    const [showNotifications, setShowNotifications] = useState(false);
    const router = useRouter();
    const pathname = usePathname();
    const { notifications, unreadCount, markAllRead } = useNotifications();

    const activeRoute = getActiveRoute(pathname);
    const pageMeta = activeRoute ?? DEFAULT_ROUTE_META;
    const notifRef = useRef<HTMLDivElement>(null);
    const searchRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        function handleClickOutside(event: MouseEvent) {
            if (notifRef.current && !notifRef.current.contains(event.target as Node)) {
                setShowNotifications(false);
            }

            if (searchRef.current && !searchRef.current.contains(event.target as Node)) {
                setShowSearch(false);
                setSearchQuery("");
            }
        }

        function handleKeyDown(event: KeyboardEvent) {
            if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
                event.preventDefault();
                setShowSearch((current) => {
                    if (current) {
                        setSearchQuery("");
                    }

                    return !current;
                });
            }

            if (event.key === "Escape") {
                setShowSearch(false);
                setSearchQuery("");
                setShowNotifications(false);
            }
        }

        document.addEventListener("mousedown", handleClickOutside);
        document.addEventListener("keydown", handleKeyDown);

        return () => {
            document.removeEventListener("mousedown", handleClickOutside);
            document.removeEventListener("keydown", handleKeyDown);
        };
    }, []);

    useEffect(() => {
        setShowSearch(false);
        setSearchQuery("");
        setShowNotifications(false);
    }, [pathname]);

    const normalizedQuery = searchQuery.trim().toLowerCase();
    const filteredItems = DASHBOARD_ROUTES.filter((item) => {
        if (!normalizedQuery) {
            return true;
        }

        return [item.label, item.description, item.section, item.pageTitle].some((value) =>
            value.toLowerCase().includes(normalizedQuery)
        );
    });

    const handleSearchSelect = (href: string) => {
        router.push(href);
        setShowSearch(false);
        setSearchQuery("");
    };

    return (
        <header className="sticky top-0 z-20 border-b border-white/10 bg-slate-950/85 backdrop-blur-xl">
            <div className="flex items-center justify-between gap-4 px-6 py-4">
                <div className="ml-12 min-w-0 lg:ml-0">
                    <motion.div initial={{ opacity: 0, x: -16 }} animate={{ opacity: 1, x: 0 }}>
                        <p className="text-[10px] font-semibold uppercase tracking-[0.28em] text-indigo-300/80">
                            {pageMeta.section}
                        </p>
                        <div className="mt-1 flex flex-wrap items-center gap-2">
                            <h1 className="text-lg font-semibold tracking-tight text-white sm:text-xl">
                                {pageMeta.pageTitle}
                            </h1>
                            <span className="hidden rounded-full border border-white/10 bg-white/[0.04] px-2.5 py-1 text-[10px] font-medium uppercase tracking-wide text-slate-400 sm:inline-flex">
                                CloudFinOps
                            </span>
                        </div>
                        <p className="mt-1 max-w-2xl text-sm text-slate-400">
                            {pageMeta.description}
                        </p>
                    </motion.div>
                </div>

                <div className="flex items-center gap-3">
                    <div className="relative" ref={searchRef}>
                        <AnimatePresence>
                            {showSearch ? (
                                <motion.div
                                    initial={{ opacity: 0, y: 12, scale: 0.98 }}
                                    animate={{ opacity: 1, y: 0, scale: 1 }}
                                    exit={{ opacity: 0, y: 12, scale: 0.98 }}
                                    transition={{ duration: 0.18 }}
                                    className="absolute right-0 top-14 z-50 w-[min(26rem,calc(100vw-1.5rem))] overflow-hidden rounded-2xl border border-white/10 bg-slate-900/95 shadow-2xl shadow-black/40 backdrop-blur-xl"
                                >
                                    <div className="border-b border-white/10 px-4 py-3">
                                        <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-slate-500">
                                            Route Launcher
                                        </p>
                                        <p className="mt-1 text-xs text-slate-400">
                                            Jump between dashboard views without hunting through the sidebar.
                                        </p>
                                    </div>

                                    <div className="p-3">
                                        <div className="relative">
                                            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
                                            <input
                                                type="text"
                                                value={searchQuery}
                                                onChange={(event) => setSearchQuery(event.target.value)}
                                                placeholder="Search pages, workflows, and tools"
                                                className="w-full rounded-xl border border-white/10 bg-slate-950/70 py-2.5 pl-10 pr-10 text-sm text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                                                autoFocus
                                            />
                                            {searchQuery ? (
                                                <button
                                                    type="button"
                                                    onClick={() => setSearchQuery("")}
                                                    className="absolute right-2 top-1/2 flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-lg text-slate-500 transition hover:bg-white/5 hover:text-white"
                                                >
                                                    <X className="h-4 w-4" />
                                                </button>
                                            ) : null}
                                        </div>
                                    </div>

                                    <div className="max-h-80 space-y-1 overflow-y-auto px-3 pb-3">
                                        {filteredItems.length > 0 ? (
                                            filteredItems.map((item) => {
                                                const isCurrent = isPathActive(pathname, item.matchPrefixes ?? [item.href]);

                                                return (
                                                    <button
                                                        key={item.id}
                                                        type="button"
                                                        onClick={() => handleSearchSelect(item.href)}
                                                        className={`flex w-full items-start gap-3 rounded-xl border px-3 py-3 text-left transition ${isCurrent
                                                            ? "border-indigo-500/30 bg-indigo-500/10"
                                                            : "border-transparent hover:border-white/10 hover:bg-white/[0.03]"
                                                            }`}
                                                    >
                                                        <span className="mt-0.5 rounded-xl border border-white/10 bg-white/[0.04] p-2 text-slate-400">
                                                            <item.icon className="h-4 w-4" />
                                                        </span>
                                                        <span className="min-w-0 flex-1">
                                                            <span className="flex flex-wrap items-center gap-2">
                                                                <span className="text-sm font-medium text-white">
                                                                    {item.label}
                                                                </span>
                                                                <span className="rounded-full border border-white/10 bg-white/[0.03] px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-slate-400">
                                                                    {item.section}
                                                                </span>
                                                                {isCurrent ? (
                                                                    <span className="rounded-full border border-emerald-400/20 bg-emerald-400/10 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-emerald-300">
                                                                        Current
                                                                    </span>
                                                                ) : null}
                                                            </span>
                                                            <span className="mt-1 block text-xs leading-5 text-slate-400">
                                                                {item.description}
                                                            </span>
                                                        </span>
                                                        <ChevronRight className="mt-1 h-4 w-4 flex-shrink-0 text-slate-600" />
                                                    </button>
                                                );
                                            })
                                        ) : (
                                            <div className="rounded-2xl border border-dashed border-white/10 bg-white/[0.03] px-5 py-10 text-center">
                                                <Bot className="mx-auto h-5 w-5 text-slate-600" />
                                                <p className="mt-3 text-sm font-medium text-white">No matching views</p>
                                                <p className="mt-1 text-xs text-slate-500">
                                                    Try a page name like Forecast, Governance, or Architecture.
                                                </p>
                                            </div>
                                        )}
                                    </div>
                                </motion.div>
                            ) : null}
                        </AnimatePresence>

                        <button
                            type="button"
                            onClick={() => {
                                if (showSearch) {
                                    setShowSearch(false);
                                    setSearchQuery("");
                                    return;
                                }

                                setShowSearch(true);
                            }}
                            className="flex h-10 w-10 items-center justify-center rounded-xl border border-white/10 bg-slate-900/70 text-slate-300 transition hover:border-white/20 hover:bg-white/[0.04] hover:text-white sm:h-auto sm:w-[320px] sm:justify-between sm:px-4 sm:py-2.5"
                            aria-label="Open route launcher"
                        >
                            <span className="flex items-center gap-3">
                                <Search className="h-4 w-4" />
                                <span className="hidden text-sm text-slate-400 sm:inline">
                                    Jump to a dashboard view
                                </span>
                            </span>
                            <span className="hidden rounded-lg border border-white/10 bg-white/[0.03] px-2 py-1 text-[11px] font-medium text-slate-400 lg:inline-flex">
                                Ctrl/⌘ K
                            </span>
                        </button>
                    </div>

                    <div className="relative" ref={notifRef}>
                        <button
                            type="button"
                            onClick={() => setShowNotifications((current) => !current)}
                            className="relative flex h-10 w-10 items-center justify-center rounded-xl border border-white/10 bg-slate-900/70 text-slate-300 transition hover:border-white/20 hover:bg-white/[0.04] hover:text-white"
                            aria-label="View notifications"
                        >
                            <Bell className="h-5 w-5" />
                            {unreadCount > 0 ? (
                                <span className="absolute -right-1 -top-1 inline-flex min-w-5 items-center justify-center rounded-full bg-rose-500 px-1.5 py-0.5 text-[10px] font-semibold text-white">
                                    {unreadCount > 9 ? "9+" : unreadCount}
                                </span>
                            ) : null}
                        </button>

                        <AnimatePresence>
                            {showNotifications ? (
                                <motion.div
                                    initial={{ opacity: 0, y: 12, scale: 0.98 }}
                                    animate={{ opacity: 1, y: 0, scale: 1 }}
                                    exit={{ opacity: 0, y: 12, scale: 0.98 }}
                                    transition={{ duration: 0.18 }}
                                    className="absolute right-0 mt-2 w-80 origin-top-right overflow-hidden rounded-2xl border border-white/10 bg-slate-900/95 shadow-2xl shadow-black/40 backdrop-blur-xl"
                                >
                                    <div className="flex items-center justify-between border-b border-white/10 px-4 py-3">
                                        <div>
                                            <span className="font-semibold text-white">Notifications</span>
                                            <p className="mt-1 text-xs text-slate-500">
                                                Approval requests, budget warnings, and scan events.
                                            </p>
                                        </div>
                                        {notifications.length > 0 ? (
                                            <button
                                                type="button"
                                                onClick={markAllRead}
                                                className="text-xs text-indigo-300 transition hover:text-white"
                                            >
                                                Mark all read
                                            </button>
                                        ) : null}
                                    </div>

                                    {notifications.length > 0 ? (
                                        <div className="max-h-[320px] overflow-y-auto">
                                            {notifications.map((notification) => (
                                                <div
                                                    key={notification.id}
                                                    className={`border-b border-white/5 px-4 py-3 transition hover:bg-white/[0.03] ${!notification.isRead ? "bg-white/[0.02]" : ""}`}
                                                >
                                                    <div className="mb-1 flex items-start justify-between gap-3">
                                                        <span
                                                            className={`text-sm font-medium ${notification.type === "alert"
                                                                ? "text-rose-400"
                                                                : notification.type === "warning"
                                                                    ? "text-amber-400"
                                                                    : notification.type === "success"
                                                                        ? "text-emerald-400"
                                                                        : "text-indigo-300"
                                                                }`}
                                                        >
                                                            {notification.title}
                                                        </span>
                                                        <span className="text-[10px] text-slate-500">
                                                            {notification.time}
                                                        </span>
                                                    </div>
                                                    <p className="text-xs leading-5 text-slate-400">
                                                        {notification.message}
                                                    </p>
                                                </div>
                                            ))}
                                        </div>
                                    ) : (
                                        <div className="px-6 py-10 text-center">
                                            <Bell className="mx-auto h-5 w-5 text-slate-600" />
                                            <p className="mt-3 text-sm font-medium text-white">
                                                No workflow alerts right now
                                            </p>
                                            <p className="mt-1 text-xs text-slate-500">
                                                New recommendations and budget events will appear here.
                                            </p>
                                        </div>
                                    )}

                                    <div className="border-t border-white/10 bg-slate-950/40 p-3 text-center">
                                        <button
                                            type="button"
                                            onClick={() => {
                                                setShowNotifications(false);
                                                router.push("/dashboard/alerts");
                                            }}
                                            className="w-full rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2 text-xs font-medium text-slate-300 transition hover:bg-white/[0.06] hover:text-white"
                                        >
                                            Open alert center
                                        </button>
                                    </div>
                                </motion.div>
                            ) : null}
                        </AnimatePresence>
                    </div>

                    <div className="relative">
                        <div className="min-h-[36px] min-w-[36px]">
                            <ClientOnlyUserButton />
                        </div>
                    </div>
                </div>
            </div>
        </header>
    );
}

const emptySubscribe = () => () => {};

function ClientOnlyUserButton() {
    const mounted = useSyncExternalStore(emptySubscribe, () => true, () => false);

    if (!mounted) {
        return null;
    }

    return (
        <UserButton
            appearance={{
                elements: {
                    avatarBox: "h-9 w-9 border border-white/20",
                },
            }}
        />
    );
}
