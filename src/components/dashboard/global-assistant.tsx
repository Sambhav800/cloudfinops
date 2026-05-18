'use client';

import { useEffect, useState } from "react";
import { CloudLightning } from "lucide-react";
import { motion } from "framer-motion";
import { WatchdogModal } from "@/components/dashboard/watchdog-modal";
import { useScan } from "@/components/dashboard/scan-provider";

// Pages can ask the assistant to open by dispatching this CustomEvent
// on the window. Optionally include `detail.prompt` to seed the chat.
//   window.dispatchEvent(new CustomEvent("cloudfinops:open-assistant", {
//       detail: { prompt: "..." }
//   }));
const OPEN_EVENT = "cloudfinops:open-assistant";

type OpenEventDetail = { prompt?: string };

export function GlobalAssistant() {
    const [isOpen, setIsOpen] = useState(false);
    const [seedPrompt, setSeedPrompt] = useState<string | null>(null);
    const { isScanning } = useScan();

    useEffect(() => {
        const handler = (event: Event) => {
            const detail = (event as CustomEvent<OpenEventDetail>).detail;
            if (detail && typeof detail.prompt === "string") {
                setSeedPrompt(detail.prompt);
            }
            setIsOpen(true);
        };
        window.addEventListener(OPEN_EVENT, handler as EventListener);
        return () => window.removeEventListener(OPEN_EVENT, handler as EventListener);
    }, []);

    // Pass any seeded prompt through `context` — the WatchdogModal reads
    // its `context` record and dashboards can extend it later to prefill
    // the input. We also keep the minimal scan status flag.
    const aiContext: Record<string, unknown> = {
        systemStatus: isScanning ? "Scan in progress" : "Monitoring active",
    };
    if (seedPrompt) {
        aiContext.seedPrompt = seedPrompt;
    }

    return (
        <>
            <motion.button
                initial={{ scale: 0, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                onClick={() => {
                    setSeedPrompt(null);
                    setIsOpen(true);
                }}
                className="fixed bottom-6 right-6 z-40 p-3.5 bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white rounded-full shadow-lg shadow-cyan-500/20 border border-white/10 flex items-center justify-center"
            >
                <CloudLightning className="w-5 h-5" />
            </motion.button>

            <WatchdogModal
                isOpen={isOpen}
                onClose={() => {
                    setIsOpen(false);
                    setSeedPrompt(null);
                }}
                context={aiContext}
            />
        </>
    );
}
