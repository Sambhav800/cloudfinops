'use client';

import React, { createContext, useContext, useState, useEffect, ReactNode, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { CheckCircle2, AlertCircle, Loader2, X, Minimize2, Maximize2 } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useNotifications } from '@/components/dashboard/notification-provider';
import { useAuth, useUser } from '@clerk/nextjs';

import { buildBackendAuthHeaders } from '@/app/api/_shared/fetch-with-backend-auth-fallback';

interface ScanContextType {
    isScanning: boolean;
    startScan: () => Promise<void>;
    showScanProgress: () => void;
    resetScan: () => void;
    lastScanResult: Record<string, unknown> | null;
}

const defaultScanContext: ScanContextType = {
    isScanning: false,
    startScan: async () => { },
    showScanProgress: () => { },
    resetScan: () => { },
    lastScanResult: null,
};

const ScanContext = createContext<ScanContextType>(defaultScanContext);

export function useScan() {
    return useContext(ScanContext);
}

export function ScanProvider({ children }: { children: ReactNode }) {
    const { user } = useUser();
    const { getToken } = useAuth();
    const [isScanning, setIsScanning] = useState(false);
    const [lastScanResult, setLastScanResult] = useState<Record<string, unknown> | null>(null);
    const [progress, setProgress] = useState(0);
    const [status, setStatus] = useState("Idle");
    const [step, setStep] = useState<"processing" | "success" | "error" | "idle">("idle");
    const [errorMsg, setErrorMsg] = useState("");
    const [isMinimized, setIsMinimized] = useState(false);
    const router = useRouter();
    const { addNotification } = useNotifications();

    // WebSocket Ref
    const wsRef = useRef<WebSocket | null>(null);
    const isScanningRef = useRef(false);
    const activeScansRef = useRef<Set<string>>(new Set());

    // Keep ref in sync with state for polling
    useEffect(() => {
        isScanningRef.current = isScanning;
    }, [isScanning]);

    // HTTP polling fallback — runs during scanning to catch progress when WebSocket drops.
    // Uses relative URL to go through Next.js rewrites (which proxy to backend).
    useEffect(() => {
        if (!isScanning || !user) return;

        let stopped = false;
        let idleCount = 0;

        const fetchProgress = async () => {
            let token = await getToken();
            if (!token) {
                try {
                    token = await getToken({ template: "default" });
                } catch {
                    token = null;
                }
            }

            const headers = buildBackendAuthHeaders(
                new URL("/api/scan-progress", window.location.origin).toString(),
                {
                    token,
                    userId: user.id,
                },
                { "Content-Type": "application/json" },
            );

            // Use relative URL — Next.js rewrites proxy /api/* to backend
            const res = await fetch(`/api/scan-progress?t=${Date.now()}`, {
                headers,
                cache: "no-store",
            });
            if (!res.ok) {
                throw new Error(`Scan progress request failed: ${res.status}`);
            }
            return res.json() as Promise<{
                type: string;
                percent: number;
                message: string;
                status: string;
            }>;
        };

        const poll = async () => {
            // Wait 5s before first poll to give the scan time to register
            await new Promise(r => setTimeout(r, 5000));

            while (!stopped && isScanningRef.current) {
                try {
                    const data = await fetchProgress();
                    if (data.status === 'scanning') {
                        idleCount = 0;
                        setProgress(typeof data.percent === "number" ? data.percent : 0);
                        setStatus(data.message || "Scan in progress...");
                        setStep("processing");
                    } else if (data.status === 'complete') {
                        setProgress(100);
                        setStatus("Analysis Complete — Dashboard Updated");
                        setStep("success");
                        router.refresh();
                        setTimeout(() => {
                            setIsScanning(false);
                            setStep("idle");
                        }, 5000);
                        stopped = true;
                        return;
                    } else if (data.status === 'idle') {
                        idleCount++;
                        // If backend returns idle 5+ times, the server likely restarted
                        // Data is already saved to DB, so auto-complete gracefully
                        if (idleCount >= 5) {
                            setProgress(100);
                            setStatus("Analysis Complete");
                            setStep("success");
                            router.refresh();
                            setTimeout(() => {
                                setIsScanning(false);
                                setStep("idle");
                            }, 3000);
                            stopped = true;
                            return;
                        }
                    }
                } catch {
                    // Polling failed — will retry
                }
                await new Promise(r => setTimeout(r, 3000));
            }
        };

        poll();
        return () => { stopped = true; };
    }, [getToken, isScanning, user, router]);

    // Initialize WebSocket
    useEffect(() => {
        if (!user) return;

        const backendHttpUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://127.0.0.1:8000';
        const backendWsUrl = backendHttpUrl
            .replace('https://', 'wss://')
            .replace('http://', 'ws://');

        let retryCount = 0;
        const maxRetries = 5;
        let disposed = false;
        let ws: WebSocket | null = null;
        let pingInterval: ReturnType<typeof setInterval> | null = null;
        let reconnectTimeout: ReturnType<typeof setTimeout> | null = null;

        const clearTimers = () => {
            if (pingInterval) {
                clearInterval(pingInterval);
                pingInterval = null;
            }
            if (reconnectTimeout) {
                clearTimeout(reconnectTimeout);
                reconnectTimeout = null;
            }
        };

        const scheduleReconnect = () => {
            if (disposed || retryCount >= maxRetries) {
                return;
            }
            retryCount += 1;
            reconnectTimeout = setTimeout(() => {
                void connect();
            }, 3000);
        };

        const connect = async () => {
            let token: string | null = null;
            try {
                token = await getToken();
            } catch {
                token = null;
            }
            if (!token) {
                try {
                    token = await getToken({ template: "default" });
                } catch {
                    token = null;
                }
            }

            if (disposed) {
                return;
            }

            if (!token) {
                scheduleReconnect();
                return;
            }

            const wsUrl = `${backendWsUrl}/ws/${encodeURIComponent(user.id)}?token=${encodeURIComponent(token)}`;
            ws = new WebSocket(wsUrl);

            ws.onopen = () => {
                retryCount = 0;
                pingInterval = setInterval(() => {
                    if (ws && ws.readyState === WebSocket.OPEN) ws.send('ping');
                }, 25000);
            };

            ws.onmessage = (event) => {
                if (event.data === 'pong') return;

                try {
                    const data = JSON.parse(event.data);

                    if (data.type === 'scan_progress') {
                        if (data.integration_id) {
                            activeScansRef.current.add(data.integration_id);
                        }
                        setIsScanning(true);
                        setStep("processing");
                        setStatus(data.message || "Scan in progress...");
                        setProgress(typeof data.percent === "number" ? data.percent : 0);
                    } else if (data.type === 'scan_complete') {
                        if (data.integration_id) {
                            activeScansRef.current.delete(data.integration_id);
                        }

                        addNotification({
                            title: "Scan Completed",
                            message: `Found ${data.resources_found} resources.`,
                            type: "success"
                        });

                        if (activeScansRef.current.size === 0) {
                            setProgress(100);
                            setStatus("Analysis Complete");
                            setStep("success");

                            setLastScanResult({
                                resourcesFound: data.resources_found || 0,
                                wasteFound: data.waste_found || 0,
                                potentialSavings: data.potential_savings || 0
                            });

                            router.refresh();
                            setTimeout(() => {
                                setIsScanning(false);
                                setStep("idle");
                            }, 3000);
                        } else {
                            setStatus("Waiting for remaining scans...");
                        }
                    } else if (data.type === 'scan_failed') {
                        if (data.integration_id) {
                            activeScansRef.current.delete(data.integration_id);
                        }
                        addNotification({
                            title: "Scan Failed",
                            message: data.message,
                            type: "alert"
                        });

                        if (activeScansRef.current.size === 0) {
                            setStep("error");
                            setStatus("Scan Failed");
                            setErrorMsg(data.message);
                            setIsScanning(false);
                        }
                    }
                } catch (e) {
                    console.error('WS Parse Error:', e);
                }
            };

            ws.onerror = () => {
                // Silent — polling fallback handles progress
            };

            ws.onclose = (event) => {
                clearTimers();

                if (!disposed && event.code !== 1000) {
                    scheduleReconnect();
                }
            };

            wsRef.current = ws;
        };

        void connect();

        return () => {
            disposed = true;
            clearTimers();
            if (wsRef.current) {
                wsRef.current.close(1000);
            }
        };
    }, [user, addNotification, router, getToken]);

    const resetScan = () => {
        setLastScanResult(null);
        setStep("idle");
        setStatus("Initializing...");
        setProgress(0);
    };

    const startScan = async () => {
        if (isScanning) return;
        setIsScanning(true);
        setStep("processing");
        setProgress(0);
        setStatus("Starting Scan...");
        setErrorMsg("");
        setIsMinimized(false);
        setLastScanResult(null);

        try {
            const { triggerRescan } = await import('@/app/actions/scan');
            const result = await triggerRescan();

            if (!result.success) {
                setStep("error");
                setStatus("Start Failed");
                setErrorMsg(result.error || "Unknown error");
                setIsScanning(false);
                addNotification({
                    title: "Scan Failed",
                    message: result.error || "Could not start scan",
                    type: "alert"
                });
            } else {
                // Success - wait for WebSocket updates
                setStatus("Request Sent...");
            }
        } catch (e) {
            setStep("error");
            setStatus("System Error");
            setErrorMsg(e instanceof Error ? e.message : "Network failure");
            setIsScanning(false);
        }
    };

    const showScanProgress = () => {
        if (isScanning) return;
        setIsScanning(true);
        setStep("processing");
        setProgress(5);
        setStatus("Scan in progress...");
        setErrorMsg("");
        setIsMinimized(false);
        setLastScanResult(null);
    };

    return (
        <ScanContext.Provider value={{ isScanning, startScan, showScanProgress, resetScan, lastScanResult }}>
            {children}
            <AnimatePresence>
                {isScanning && (
                    <motion.div
                        initial={{ y: 100, opacity: 0 }}
                        animate={{ y: 0, opacity: 1 }}
                        exit={{ y: 100, opacity: 0 }}
                        className="fixed bottom-24 right-6 z-50 pointer-events-auto"
                    >
                        <div className={`
                                bg-slate-900 border border-white/10 shadow-2xl overflow-hidden transition-all duration-300
                                ${isMinimized ? 'w-64 rounded-lg p-4 flex items-center justify-between' : 'w-80 rounded-2xl p-6'}
                            `}>
                            {isMinimized && (
                                <div className="absolute bottom-0 left-0 h-1 bg-emerald-500 transition-all duration-300" style={{ width: `${progress}%` }} />
                            )}

                            {!isMinimized ? (
                                <div className="flex flex-col items-center text-center space-y-4">
                                    <div className="absolute top-2 right-2 flex gap-2">
                                        <button onClick={() => setIsMinimized(true)} className="p-1 hover:bg-white/10 rounded text-slate-400">
                                            <Minimize2 className="w-4 h-4" />
                                        </button>
                                        <button onClick={() => setIsScanning(false)} className="p-1 hover:bg-white/10 rounded text-slate-400">
                                            <X className="w-4 h-4" />
                                        </button>
                                    </div>

                                    <div className="relative w-20 h-20 flex items-center justify-center">
                                        <svg className="w-full h-full transform -rotate-90">
                                            <circle cx="40" cy="40" r="36" stroke="currentColor" strokeWidth="6" fill="transparent" className="text-slate-800" />
                                            <circle
                                                cx="40" cy="40" r="36"
                                                stroke="currentColor" strokeWidth="6" fill="transparent"
                                                className={`${step === 'error' ? 'text-rose-500' : 'text-emerald-500'} transition-all duration-300 ease-linear`}
                                                strokeDasharray="226.2"
                                                strokeDashoffset={226.2 - (226.2 * progress) / 100}
                                                strokeLinecap="round"
                                            />
                                        </svg>
                                        <div className="absolute inset-0 flex items-center justify-center">
                                            {step === 'processing' && <span className="text-lg font-bold text-white font-mono">{progress}%</span>}
                                            {step === 'success' && <CheckCircle2 className="w-8 h-8 text-emerald-400" />}
                                            {step === 'error' && <AlertCircle className="w-8 h-8 text-rose-500" />}
                                        </div>
                                    </div>

                                    <div className="space-y-1 w-full">
                                        <h4 className="font-bold text-white text-sm">{status}</h4>
                                        {errorMsg && <p className="text-xs text-rose-400 bg-rose-900/20 p-1 rounded">{errorMsg}</p>}
                                    </div>
                                </div>
                            ) : (
                                <div className="flex items-center gap-3 w-full">
                                    {step === 'processing' ? <Loader2 className="w-5 h-5 text-emerald-400 animate-spin" /> :
                                        step === 'success' ? <CheckCircle2 className="w-5 h-5 text-emerald-400" /> : <AlertCircle className="w-5 h-5 text-rose-500" />}
                                    <div className="flex-1 text-left">
                                        <p className="text-sm font-bold text-white">{step === 'processing' ? `Scanning... ${progress}%` : status}</p>
                                    </div>
                                    <button onClick={() => setIsMinimized(false)} className="p-1 hover:bg-white/10 rounded text-slate-400">
                                        <Maximize2 className="w-4 h-4" />
                                    </button>
                                </div>
                            )}
                        </div>
                    </motion.div>
                )}
            </AnimatePresence>
        </ScanContext.Provider>
    );
}
