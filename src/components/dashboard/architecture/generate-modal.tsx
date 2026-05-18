'use client';

import { motion } from 'framer-motion';
import { Sparkles, AlertCircle, X } from 'lucide-react';
import type { ProposedMode } from '@/lib/architecture-types';

interface Props {
    mode: ProposedMode;
    onConfirm: () => void;
    onCancel: () => void;
}

const MODE_LABELS: Record<ProposedMode, string> = {
    cost_optimized: 'Cost-Optimized',
    reliability_security_optimized: 'Reliability & Security',
};

export function GenerateModal({ mode, onConfirm, onCancel }: Props) {
    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
            <motion.div
                initial={{ scale: 0.95, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                exit={{ scale: 0.95, opacity: 0 }}
                className="mx-4 w-full max-w-md overflow-hidden rounded-2xl border border-white/10 bg-slate-900 shadow-2xl"
            >
                {/* Header */}
                <div className="flex items-center justify-between border-b border-white/10 p-4">
                    <div className="flex items-center gap-2">
                        <Sparkles className="w-5 h-5 text-indigo-400" />
                        <h3 className="text-white font-medium">Generate {MODE_LABELS[mode]} Architecture</h3>
                    </div>
                    <button onClick={onCancel} className="rounded-xl p-1 text-slate-500 transition hover:bg-white/5 hover:text-white">
                        <X className="w-4 h-4" />
                    </button>
                </div>

                {/* Body */}
                <div className="p-6 space-y-4">
                    <p className="text-sm text-slate-300 leading-relaxed">
                        This will analyze your scanned resources and produce architecture recommendations using AI.
                    </p>

                    <div className="flex gap-2.5 rounded-xl border border-indigo-500/20 bg-indigo-500/10 p-3">
                        <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-indigo-400" />
                        <div className="space-y-1 text-xs text-indigo-200">
                            <p>• Does <strong>NOT</strong> modify any resources</p>
                            <p>• May use AI credits (~5 seconds)</p>
                            <p>• Results cached for this session</p>
                        </div>
                    </div>
                </div>

                {/* Actions */}
                <div className="flex items-center justify-end gap-3 border-t border-white/10 bg-slate-950/30 p-4">
                    <button
                        onClick={onCancel}
                        className="rounded-xl border border-white/10 bg-slate-800 px-4 py-2 text-sm text-slate-300 transition-colors hover:bg-slate-700 hover:text-white"
                    >
                        Cancel
                    </button>
                    <button
                        onClick={onConfirm}
                        className="flex items-center gap-2 rounded-xl bg-indigo-600 px-5 py-2 text-sm font-medium text-white transition-colors hover:bg-indigo-500"
                    >
                        <Sparkles className="w-4 h-4" />
                        Generate
                    </button>
                </div>
            </motion.div>
        </div>
    );
}
