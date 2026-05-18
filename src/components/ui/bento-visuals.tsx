"use client";

import { motion } from "framer-motion";
import { useEffect, useState } from "react";

export function MiniChart() {
    return (
        <div className="flex items-end gap-1 h-20 w-full px-4 pb-2">
            {[40, 65, 30, 80, 50, 90, 45, 70, 60, 95].map((h, i) => (
                <motion.div
                    key={i}
                    className="flex-1 bg-gradient-to-t from-primary/20 to-primary rounded-t-sm"
                    initial={{ height: "10%" }}
                    animate={{ height: `${h}%` }}
                    transition={{
                        duration: 1,
                        repeat: Infinity,
                        repeatType: "reverse",
                        delay: i * 0.1,
                        ease: "easeInOut"
                    }}
                />
            ))}
        </div>
    );
}

export function ScanningGrid() {
    return (
        <div className="relative w-full h-32 overflow-hidden rounded-lg border border-green-500/20 bg-green-950/20">
            <div className="absolute inset-0 grid grid-cols-6 grid-rows-3 gap-1 p-1">
                {[...Array(18)].map((_, i) => (
                    <div key={i} className="bg-green-500/10 rounded-sm" />
                ))}
            </div>
            <motion.div
                className="absolute top-0 left-0 w-full h-1 bg-green-400 blur-[2px] shadow-[0_0_10px_#4ade80]"
                animate={{ top: ["0%", "100%"] }}
                transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
            />
        </div>
    );
}

const LOGS = [
    { text: "scanning cloud_infrastructure...", color: "text-white" },
    { text: "✔ connected to aws_us_east_1", color: "text-green-400" },
    { text: "✔ connected to azure_central_us", color: "text-green-400" },
    { text: "⚠ analyzing ebs_volumes...", color: "text-yellow-400" },
    { text: "➜ found 3 idle instances (cost: ₹34.9K/mo)", color: "text-gray-300" },
    { text: "➜ found 12 unattached volumes (cost: ₹14.9K/mo)", color: "text-gray-300" },
    { text: "optimizing resources...", color: "text-blue-400" },
    { text: "✔ applying auto-stop rules", color: "text-green-400" },
    { text: "✔ snapshots compressed", color: "text-green-400" },
    { text: "✨ total savings potential: ₹49.8K/mo", color: "text-primary font-bold" },
];

export function TerminalMockup() {
    const [lines, setLines] = useState<typeof LOGS>([]);

    useEffect(() => {
        let currentIndex = 0;
        const interval = setInterval(() => {
            setLines((prev) => {
                const next = [...prev, LOGS[currentIndex]];
                // Keep only last 6 lines to prevent scrolling out of view
                if (next.length > 7) return next.slice(next.length - 7);
                return next;
            });
            currentIndex = (currentIndex + 1) % LOGS.length;
        }, 1500);

        return () => clearInterval(interval);
    }, []);

    return (
        <div className="w-full h-full bg-black/90 font-mono text-[10px] p-4 text-gray-300 overflow-hidden leading-relaxed shadow-inner">
            <div className="flex gap-1.5 mb-3 opacity-50">
                <div className="w-2.5 h-2.5 rounded-full bg-red-500" />
                <div className="w-2.5 h-2.5 rounded-full bg-yellow-500" />
                <div className="w-2.5 h-2.5 rounded-full bg-green-500" />
            </div>
            <div className="space-y-1">
                {lines.map((line, i) => (
                    <motion.div
                        key={i}
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        className={line.color}
                    >
                        <span className="opacity-50 mr-2">$</span>
                        {line.text}
                    </motion.div>
                ))}
                <motion.div
                    animate={{ opacity: [0, 1] }}
                    transition={{ duration: 0.8, repeat: Infinity }}
                    className="text-primary mt-1"
                >
                    _
                </motion.div>
            </div>
        </div>
    );
}
