"use client";

import React, { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";

export interface Notification {
    id: string;
    title: string;
    message: string;
    time: string;
    type: "warning" | "alert" | "success" | "info";
    severity: string;
    alert_type: string;
    isRead: boolean;
    isEphemeral?: boolean;
}

interface NotificationContextType {
    notifications: Notification[];
    unreadCount: number;
    addNotification: (notification: Omit<Notification, "id" | "time" | "isRead" | "severity" | "alert_type">) => void;
    markAllRead: () => Promise<void>;
    markAsRead: (id: string) => Promise<void>;
    deleteNotification: (id: string) => Promise<void>;
    clearAllNotifications: () => void;
    refetch: () => Promise<void>;
}

const defaultNotificationContext: NotificationContextType = {
    notifications: [],
    unreadCount: 0,
    addNotification: () => { },
    markAllRead: async () => { },
    markAsRead: async () => { },
    deleteNotification: async () => { },
    clearAllNotifications: () => { },
    refetch: async () => { },
};

const NotificationContext = createContext<NotificationContextType>(defaultNotificationContext);

export function useNotifications() {
    return useContext(NotificationContext);
}

function mapSeverityToType(severity: string): Notification["type"] {
    if (severity === "high" || severity === "critical") return "alert";
    if (severity === "medium" || severity === "warning") return "warning";
    return "info";
}

function formatTimeAgo(isoDate: string): string {
    const date = new Date(isoDate);
    if (Number.isNaN(date.getTime())) return isoDate;

    const now = Date.now();
    const diffMs = now - date.getTime();
    const diffMin = Math.floor(diffMs / 60000);

    if (diffMin < 1) return "Just now";
    if (diffMin < 60) return `${diffMin}m ago`;

    const diffHours = Math.floor(diffMin / 60);
    if (diffHours < 24) return `${diffHours}h ago`;

    const diffDays = Math.floor(diffHours / 24);
    if (diffDays < 30) return `${diffDays}d ago`;

    return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

const POLL_INTERVAL_MS = 60_000;

export function NotificationProvider({ children }: { children: ReactNode }) {
    const [backendNotifications, setBackendNotifications] = useState<Notification[]>([]);
    const [ephemeralNotifications, setEphemeralNotifications] = useState<Notification[]>([]);
    const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const fetchedRef = useRef(false);

    const fetchNotifications = useCallback(async () => {
        try {
            const res = await fetch("/api/notifications");
            if (!res.ok) return;
            const raw = await res.json();
            const data: unknown[] = Array.isArray(raw) ? raw : Array.isArray(raw?.notifications) ? raw.notifications : [];
            if (data.length === 0 && !Array.isArray(raw) && !raw?.notifications) return;

            const mapped: Notification[] = data.map((item: unknown) => {
                const n = item as Record<string, unknown>;
                const severity = String(n.severity ?? n.priority ?? "info").toLowerCase();
                const status = String(n.status ?? "").toLowerCase();
                const isRead = status !== "pending" || Boolean(n.is_read);

                return {
                    id: String(n.id ?? n._id ?? ""),
                    title: String(n.title ?? n.recommendation ?? n.type ?? "Notification"),
                    message: String(n.message ?? n.description ?? n.details ?? ""),
                    time: formatTimeAgo(String(n.created_at ?? n.timestamp ?? "")),
                    type: mapSeverityToType(severity),
                    severity,
                    alert_type: String(n.type ?? n.alert_type ?? "general"),
                    isRead,
                };
            });

            setBackendNotifications(mapped);
        } catch {
            // Silent fail — notifications are non-critical
        }
    }, []);

    useEffect(() => {
        if (!fetchedRef.current) {
            fetchedRef.current = true;
            // eslint-disable-next-line react-hooks/set-state-in-effect
            void fetchNotifications();
        }

        const startPolling = () => {
            pollRef.current = setInterval(() => {
                if (document.visibilityState === "visible") {
                    void fetchNotifications();
                }
            }, POLL_INTERVAL_MS);
        };

        startPolling();

        const handleVisibility = () => {
            if (document.visibilityState === "visible") {
                void fetchNotifications();
            }
        };
        document.addEventListener("visibilitychange", handleVisibility);

        return () => {
            if (pollRef.current) clearInterval(pollRef.current);
            document.removeEventListener("visibilitychange", handleVisibility);
        };
    }, [fetchNotifications]);

    const notifications = [...ephemeralNotifications, ...backendNotifications];
    const unreadCount = notifications.filter(n => !n.isRead).length;

    const addNotification = (notif: Omit<Notification, "id" | "time" | "isRead" | "severity" | "alert_type">) => {
        const newNotif: Notification = {
            id: String(Date.now()),
            ...notif,
            time: "Just now",
            severity: notif.type === "alert" ? "critical" : notif.type === "warning" ? "warning" : "info",
            alert_type: "ephemeral",
            isRead: false,
            isEphemeral: true,
        };
        setEphemeralNotifications(prev => [newNotif, ...prev]);
    };

    const markAllRead = async () => {
        const unread = backendNotifications.filter(n => !n.isRead && !n.isEphemeral);
        for (const n of unread) {
            try {
                await fetch(`/api/notifications/${encodeURIComponent(n.id)}`, { method: "PATCH" });
            } catch { /* continue */ }
        }
        setBackendNotifications(prev => prev.map(n => ({ ...n, isRead: true })));
        setEphemeralNotifications(prev => prev.map(n => ({ ...n, isRead: true })));
    };

    const markAsRead = async (id: string) => {
        const target = backendNotifications.find(n => n.id === id);
        if (target && !target.isEphemeral) {
            try {
                const res = await fetch(`/api/notifications/${encodeURIComponent(id)}`, { method: "PATCH" });
                if (!res.ok) return;
            } catch { return; }
        }
        setBackendNotifications(prev => prev.map(n => n.id === id ? { ...n, isRead: true } : n));
        setEphemeralNotifications(prev => prev.map(n => n.id === id ? { ...n, isRead: true } : n));
    };

    const deleteNotification = async (id: string) => {
        const target = backendNotifications.find(n => n.id === id);
        if (target && !target.isEphemeral) {
            try {
                const res = await fetch(`/api/notifications/${encodeURIComponent(id)}`, { method: "DELETE" });
                if (!res.ok) return;
            } catch { return; }
        }
        setBackendNotifications(prev => prev.filter(n => n.id !== id));
        setEphemeralNotifications(prev => prev.filter(n => n.id !== id));
    };

    const clearAllNotifications = () => {
        setEphemeralNotifications([]);
    };

    const refetch = fetchNotifications;

    return (
        <NotificationContext.Provider value={{
            notifications,
            unreadCount,
            addNotification,
            markAllRead,
            markAsRead,
            deleteNotification,
            clearAllNotifications,
            refetch,
        }}>
            {children}
        </NotificationContext.Provider>
    );
}
