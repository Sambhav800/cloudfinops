'use client';
// Force HMR Update


import { RefreshCw } from "lucide-react";
import { useScan } from "@/components/dashboard/scan-provider";

export function RescanButton() {
    const { startScan, isScanning } = useScan();

    return (
        <button
            onClick={startScan}
            disabled={isScanning}
            className={`
                inline-flex items-center gap-2 rounded-xl border px-4 py-2.5 text-sm font-medium transition-all duration-200
                ${isScanning
                    ? 'cursor-not-allowed border-emerald-400/20 bg-emerald-400/10 text-emerald-300'
                    : 'border-indigo-500/30 bg-indigo-600 text-white shadow-lg shadow-indigo-950/40 hover:bg-indigo-500'}
            `}
        >
            {isScanning ? (
                <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    <span>Scanning...</span>
                </>
            ) : (
                <>
                    <RefreshCw className="w-4 h-4" />
                    <span>Rescan Infra</span>
                </>
            )}
        </button>
    );
}
