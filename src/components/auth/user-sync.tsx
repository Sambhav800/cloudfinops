"use client";

import { useAuth } from "@clerk/nextjs";
import { useEffect, useRef, useState } from "react";

export function UserSync() {
    const { userId, isLoaded, getToken } = useAuth();
    const lastSyncedUserIdRef = useRef<string | null>(null);
    const retryAttemptsRef = useRef<Record<string, number>>({});
    const [retryTick, setRetryTick] = useState(0);

    useEffect(() => {
        if (!isLoaded) {
            return;
        }

        if (!userId) {
            lastSyncedUserIdRef.current = null;
            return;
        }

        if (lastSyncedUserIdRef.current === userId) {
            return;
        }

        const maxAttempts = 6;
        const attemptCount = retryAttemptsRef.current[userId] ?? 0;
        if (attemptCount >= maxAttempts) {
            return;
        }

        let cancelled = false;

        const run = async () => {
            try {
                let token = await getToken();
                if (!token) {
                    try {
                        token = await getToken({ template: "default" });
                    } catch {
                        token = null;
                    }
                }

                const headers: Record<string, string> = {};
                if (token) {
                    headers.Authorization = `Bearer ${token}`;
                }

                const response = await fetch("/api/user/sync", {
                    method: "POST",
                    credentials: "same-origin",
                    headers,
                });

                const payload = await response.json().catch(() => null);
                if (!response.ok || !payload?.success) {
                    throw new Error("User sync request failed");
                }

                lastSyncedUserIdRef.current = userId;
                retryAttemptsRef.current[userId] = 0;
            } catch {
                if (cancelled) {
                    return;
                }

                const nextAttempt = attemptCount + 1;
                retryAttemptsRef.current[userId] = nextAttempt;
                const retryDelayMs = Math.min(nextAttempt * 1000, 5000);

                window.setTimeout(() => {
                    setRetryTick((value) => value + 1);
                }, retryDelayMs);
            }
        };

        run();

        return () => {
            cancelled = true;
        };
    }, [getToken, isLoaded, retryTick, userId]);

    return null;
}
