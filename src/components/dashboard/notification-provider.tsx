"use client";

import React, { createContext, useContext, useState, ReactNode } from "react";

export interface Notification {
    id: number;
    title: string;
    message: string;
    time: string;
    type: "warning" | "alert" | "success" | "info";
    isRead: boolean;
}

interface NotificationContextType {
    notifications: Notification[];
    unreadCount: number;
    addNotification: (notification: Omit<Notification, "id" | "time" | "isRead">) => void;
    markAllRead: () => void;
    clearAllNotifications: () => void;
}

const defaultNotificationContext: NotificationContextType = {
    notifications: [],
    unreadCount: 0,
    addNotification: () => { },
    markAllRead: () => { },
    clearAllNotifications: () => { },
};

const NotificationContext = createContext<NotificationContextType>(defaultNotificationContext);

export function useNotifications() {
    return useContext(NotificationContext);
}

export function NotificationProvider({ children }: { children: ReactNode }) {
    const [notifications, setNotifications] = useState<Notification[]>([]);

    const unreadCount = notifications.filter(n => !n.isRead).length;

    const addNotification = (notif: Omit<Notification, "id" | "time" | "isRead">) => {
        const newNotif: Notification = {
            id: Date.now(),
            ...notif,
            time: "Just now",
            isRead: false,
        };
        setNotifications(prev => [newNotif, ...prev]);
    };

    const markAllRead = () => {
        setNotifications(prev => prev.map(n => ({ ...n, isRead: true })));
    };

    const clearAllNotifications = () => {
        setNotifications([]);
    };

    return (
        <NotificationContext.Provider value={{ notifications, unreadCount, addNotification, markAllRead, clearAllNotifications }}>
            {children}
        </NotificationContext.Provider>
    );
}
