"use client";

import {
    Bell,
    AlertTriangle,
    Info,
    AlertCircle,
    Check,
    Trash2,
    Clock,
    Stars,
} from "lucide-react";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import type { AlertItem } from "@/lib/dashboard/data";
import { WatchdogModal } from "@/components/dashboard/watchdog-modal";

const severityIcons: Record<string, typeof Bell> = {
    critical: AlertCircle,
    warning: AlertTriangle,
    info: Info,
};

const severityColors: Record<string, { bg: string; text: string; border: string }> = {
    critical: { bg: "bg-red-500/10", text: "text-red-400", border: "border-red-500/30" },
    warning: { bg: "bg-yellow-500/10", text: "text-yellow-400", border: "border-yellow-500/30" },
    info: { bg: "bg-blue-500/10", text: "text-blue-400", border: "border-blue-500/30" },
};

export function AlertsView({ initialAlerts }: { initialAlerts: AlertItem[] }) {
    const router = useRouter();
    const [serverAlerts, setServerAlerts] = useState(initialAlerts);
    const [filter, setFilter] = useState<"all" | "unread" | "critical" | "warning" | "info">("all");
    const [showWatchdog, setShowWatchdog] = useState(false);
    const [selectedAlertForAI, setSelectedAlertForAI] = useState<AlertItem | null>(null);
    const [pendingAlertId, setPendingAlertId] = useState<string | null>(null);
    const [requestError, setRequestError] = useState<string | null>(null);

    useEffect(() => {
        setServerAlerts(initialAlerts);
    }, [initialAlerts]);

    const mutateAlert = async (id: string, method: "PATCH" | "DELETE") => {
        setPendingAlertId(id);
        setRequestError(null);

        try {
            const response = await fetch(`/api/notifications/${encodeURIComponent(id)}`, {
                method,
            });
            const data = await response.json().catch(() => ({}));
            if (!response.ok) {
                throw new Error(
                    typeof data?.detail === "string"
                        ? data.detail
                        : "Alert update failed."
                );
            }
            return true;
        } catch (error) {
            setRequestError(error instanceof Error ? error.message : "Alert update failed.");
            return false;
        } finally {
            setPendingAlertId(null);
        }
    };

    const markAsRead = async (id: string) => {
        const success = await mutateAlert(id, "PATCH");
        if (!success) {
            return;
        }

        setServerAlerts((current) =>
            current.map((alert) => alert.id === id ? { ...alert, is_read: true } : alert)
        );
        router.refresh();
    };

    const markAllAsRead = async () => {
        const unreadAlerts = serverAlerts.filter((alert) => !alert.is_read);
        for (const alert of unreadAlerts) {
            const success = await mutateAlert(alert.id, "PATCH");
            if (!success) {
                return;
            }
        }

        setServerAlerts((current) => current.map((alert) => ({ ...alert, is_read: true })));
        router.refresh();
    };

    const deleteAlert = async (id: string) => {
        const success = await mutateAlert(id, "DELETE");
        if (!success) {
            return;
        }

        setServerAlerts((current) => current.filter((alert) => alert.id !== id));
        router.refresh();
    };

    const filteredAlerts = serverAlerts.filter((a) => {
        if (filter === "all") return true;
        if (filter === "unread") return !a.is_read;
        return a.severity === filter;
    });

    const unreadCount = serverAlerts.filter(a => !a.is_read).length;
    const criticalCount = serverAlerts.filter(a => a.severity === "critical" && !a.is_read).length;

    return (
        <div className="p-6 space-y-6">
            {requestError && (
                <div className="rounded-2xl border border-rose-500/20 bg-rose-500/10 p-4 text-sm text-rose-200">
                    {requestError}
                </div>
            )}

            {/* Stats */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="bg-gray-900/50 border border-white/10 rounded-xl p-4">
                    <p className="text-sm text-gray-400">Total Alerts</p>
                    <p className="text-2xl font-bold text-white">{serverAlerts.length}</p>
                </div>
                <div className="bg-gray-900/50 border border-white/10 rounded-xl p-4">
                    <p className="text-sm text-gray-400">Unread</p>
                    <p className="text-2xl font-bold text-primary">{unreadCount}</p>
                </div>
                <div className="bg-gray-900/50 border border-white/10 rounded-xl p-4">
                    <p className="text-sm text-gray-400">Critical</p>
                    <p className="text-2xl font-bold text-red-400">{criticalCount}</p>
                </div>
                <div className="bg-gray-900/50 border border-white/10 rounded-xl p-4">
                    <p className="text-sm text-gray-400">Warnings</p>
                    <p className="text-2xl font-bold text-yellow-400">{serverAlerts.filter(a => a.severity === "warning").length}</p>
                </div>
            </div>

            {/* Actions & Filters */}
            <div className="flex flex-wrap gap-4 items-center justify-between">
                <div className="flex gap-2">
                    {(["all", "unread", "critical", "warning", "info"] as const).map((tab) => (
                        <button
                            key={tab}
                            onClick={() => setFilter(tab)}
                            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${filter === tab
                                ? "bg-primary text-black"
                                : "bg-gray-900/50 text-gray-400 hover:text-white border border-white/10"
                                }`}
                        >
                            {tab.charAt(0).toUpperCase() + tab.slice(1)}
                        </button>
                    ))}
                </div>
                {unreadCount > 0 && (
                    <button
                        onClick={() => void markAllAsRead()}
                        className="flex items-center gap-2 px-4 py-2 text-gray-400 hover:text-white transition-colors"
                    >
                        <Check className="h-4 w-4" />
                        Mark all as read
                    </button>
                )}
            </div>

            {/* Alerts List */}
            <div className="space-y-3">
                {filteredAlerts.length === 0 ? (
                    <div className="text-center py-12">
                        <Bell className="h-12 w-12 text-gray-600 mx-auto mb-4" />
                        <p className="text-gray-400">No alerts found</p>
                    </div>
                ) : (
                    filteredAlerts.map((alert) => {
                        const Icon = severityIcons[alert.severity] || Bell;
                        const colors = severityColors[alert.severity] || severityColors.info;
                        return (
                            <div
                                key={alert.id}
                                className={`bg-gray-900/50 border rounded-xl p-4 transition-all ${alert.is_read ? "border-white/5 opacity-60" : `${colors.border}`
                                    }`}
                            >
                                <div className="flex items-start gap-4">
                                    <div className={`p-2 rounded-lg ${colors.bg}`}>
                                        <Icon className={`h-5 w-5 ${colors.text}`} />
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <div className="flex items-center gap-2 mb-1">
                                            <h3 className={`font-medium ${alert.is_read ? "text-gray-400" : "text-white"}`}>
                                                {alert.title}
                                            </h3>
                                            {!alert.is_read && (
                                                <span className="w-2 h-2 bg-primary rounded-full" />
                                            )}
                                        </div>
                                        <p className="text-gray-500 text-sm mb-2">{alert.message}</p>
                                        <div className="flex items-center gap-4 text-xs text-gray-600">
                                            <span className="flex items-center gap-1">
                                                <Clock className="h-3 w-3" />
                                                {alert.created_at}
                                            </span>
                                            <span className={`px-2 py-0.5 rounded-full ${colors.bg} ${colors.text}`}>
                                                {alert.severity}
                                            </span>
                                            <span className="px-2 py-0.5 rounded-full bg-white/5 text-gray-400">
                                                {alert.alert_type}
                                            </span>
                                        </div>
                                    </div>
                                    <div className="flex gap-1">
                                        <button
                                            onClick={() => {
                                                setSelectedAlertForAI(alert);
                                                setShowWatchdog(true);
                                            }}
                                            className="p-2 text-indigo-400 hover:text-white hover:bg-indigo-500/20 rounded-lg transition-colors group"
                                            title="Analyze with Antiigravity AI"
                                        >
                                            <Stars className="h-4 w-4 group-hover:scale-110 transition-transform" />
                                        </button>
                                        {!alert.is_read && (
                                            <button
                                                onClick={() => void markAsRead(alert.id)}
                                                className="p-2 text-gray-500 hover:text-white hover:bg-white/5 rounded-lg transition-colors"
                                                title="Mark as read"
                                                disabled={pendingAlertId === alert.id}
                                            >
                                                <Check className="h-4 w-4" />
                                            </button>
                                        )}
                                        <button
                                            onClick={() => void deleteAlert(alert.id)}
                                            className="p-2 text-gray-500 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors"
                                            title="Delete"
                                            disabled={pendingAlertId === alert.id}
                                        >
                                            <Trash2 className="h-4 w-4" />
                                        </button>
                                    </div>
                                </div>
                            </div>
                        );
                    })
                )}
            </div>

            <WatchdogModal
                isOpen={showWatchdog}
                onClose={() => setShowWatchdog(false)}
                context={(selectedAlertForAI || {}) as Record<string, unknown>}
            />
        </div>
    );
}
