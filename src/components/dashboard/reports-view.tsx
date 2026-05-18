"use client";

import {
    Calendar,
    Clock,
    Download,
    FileJson,
    FileSpreadsheet,
    FileText,
    Loader2,
    PieChart,
    Plus,
    Sheet,
    TrendingDown,
    X,
} from "lucide-react";
import { useEffect, useState, useTransition } from "react";

import { generateReportAction } from "@/app/actions/reports";
import type { BackendReportRecord, BackendReportType } from "@/lib/api";

const reportTypes = [
    {
        id: "monthly_executive_summary",
        name: "Monthly Executive Summary",
        icon: FileSpreadsheet,
        description: "Portfolio spend, forecast, budget posture, and board-ready highlights.",
    },
    {
        id: "budget_variance",
        name: "Budget Variance Report",
        icon: TrendingDown,
        description: "Accounts forecasted over budget, variance sizing, and readiness flags.",
    },
    {
        id: "provider_spend_summary",
        name: "Provider Spend Summary",
        icon: PieChart,
        description: "AWS, Azure, and GCP mix by spend, share, and active account coverage.",
    },
    {
        id: "board_pack",
        name: "Board Pack",
        icon: FileText,
        description: "Executive pack combining portfolio, provider, and budget exposure views.",
    },
] as const;

const reportTypeIcons: Record<BackendReportType, typeof FileText> = {
    monthly_executive_summary: FileSpreadsheet,
    budget_variance: TrendingDown,
    provider_spend_summary: PieChart,
    board_pack: FileText,
};

const reportTypeNameMap = new Map<BackendReportType, string>(
    reportTypes.map((type) => [type.id, type.name]),
);

function formatDateLabel(value: string) {
    if (!value) return "—";
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return value;
    return parsed.toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
        year: "numeric",
    });
}

function formatDateTimeLabel(value: string) {
    if (!value) return "—";
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return value;
    return parsed.toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
        year: "numeric",
    });
}

function formatDateRange(start: string, end: string) {
    return `${formatDateLabel(start)} to ${formatDateLabel(end)}`;
}

function formatFileSize(bytes: number) {
    if (!bytes || bytes <= 0) return "—";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatStatusLabel(status: string) {
    return status
        .split("_")
        .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
        .join(" ");
}

function getStatusClasses(status: string) {
    if (status === "ready") {
        return "bg-emerald-500/10 text-emerald-400";
    }
    if (status === "attention_needed") {
        return "bg-amber-500/10 text-amber-400";
    }
    if (status === "generating") {
        return "bg-sky-500/10 text-sky-400";
    }
    return "bg-slate-500/10 text-slate-400";
}

function downloadAsJSON(report: BackendReportRecord) {
    const blob = new Blob(
        [
            JSON.stringify(
                report.data || {
                    title: report.title,
                    summary: report.summary,
                },
                null,
                2,
            ),
        ],
        { type: "application/json" },
    );
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${report.title.replace(/\s+/g, "_")}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
}

function downloadAsCSV(report: BackendReportRecord) {
    const rows: string[][] = [
        ["Field", "Value"],
        ["Title", report.title],
        ["Type", reportTypeNameMap.get(report.report_type) || report.report_type],
        ["Period", `${report.period_start} - ${report.period_end}`],
        ["Generated", report.generated_at],
        ["Status", report.status],
    ];

    Object.entries(report.data || {}).forEach(([key, value]) => {
        rows.push([key, typeof value === "object" ? JSON.stringify(value) : String(value)]);
    });

    const csv = rows.map((row) => row.map((cell) => `"${cell}"`).join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${report.title.replace(/\s+/g, "_")}.csv`;
    anchor.click();
    URL.revokeObjectURL(url);
}

export function ReportsView({ initialReports }: { initialReports: BackendReportRecord[] }) {
    const [showCreateModal, setShowCreateModal] = useState(false);
    const [selectedType, setSelectedType] = useState<BackendReportType | "">("");
    const [reports, setReports] = useState(initialReports);
    const [isPending, startTransition] = useTransition();
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        setReports(initialReports);
    }, [initialReports]);

    const openCreateModal = (reportType?: BackendReportType) => {
        setSelectedType(reportType || "");
        setError(null);
        setShowCreateModal(true);
    };

    const handleGenerate = async (event: React.FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        setError(null);

        const form = event.currentTarget;
        const formData = new FormData(form);
        if (!formData.get("reportType")) {
            formData.set("reportType", selectedType);
        }

        startTransition(async () => {
            const result = await generateReportAction(formData);
            if (!result.success || !result.report) {
                setError(result.error || "Generation failed");
                return;
            }

            setReports((current) => [
                result.report as BackendReportRecord,
                ...current.filter((item) => item.id !== result.report?.id),
            ]);
            form.reset();
            setSelectedType("");
            setShowCreateModal(false);
        });
    };

    return (
        <div className="p-6 space-y-6">
            <div className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-white/10 bg-slate-900/50 p-5 backdrop-blur-xl">
                <div>
                    <h2 className="text-lg font-semibold text-white">Executive Pack</h2>
                    <p className="mt-1 text-sm text-slate-400">
                        Generate deterministic finance reports from billing history and forecast data.
                    </p>
                </div>
                <button
                    onClick={() => openCreateModal()}
                    className="flex items-center gap-2 rounded-xl bg-primary px-5 py-2.5 font-medium text-black transition-colors hover:bg-primary/90"
                >
                    <Plus className="h-4 w-4" />
                    Generate Report
                </button>
            </div>

            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
                {reportTypes.map((type) => (
                    <button
                        key={type.id}
                        onClick={() => openCreateModal(type.id)}
                        className="rounded-2xl border border-white/10 bg-slate-900/50 p-5 text-left backdrop-blur-xl transition-all hover:border-primary/40 hover:bg-slate-900/70"
                    >
                        <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-primary/10">
                            <type.icon className="h-5 w-5 text-primary" />
                        </div>
                        <h3 className="text-base font-semibold text-white">{type.name}</h3>
                        <p className="mt-2 text-sm leading-6 text-slate-400">{type.description}</p>
                    </button>
                ))}
            </div>

            <div className="overflow-hidden rounded-2xl border border-white/10 bg-slate-900/50 backdrop-blur-xl">
                <div className="border-b border-white/10 px-5 py-4">
                    <h3 className="text-lg font-semibold text-white">Recent Reports</h3>
                    <p className="mt-1 text-xs text-slate-500">{reports.length} reports generated</p>
                </div>
                <div className="divide-y divide-white/5">
                    {reports.length === 0 ? (
                        <div className="p-12 text-center">
                            <FileText className="mx-auto mb-3 h-12 w-12 text-slate-700" />
                            <p className="text-slate-300">No reports generated yet.</p>
                            <p className="mt-1 text-xs text-slate-500">
                                Start with a Monthly Executive Summary or Budget Variance Report.
                            </p>
                        </div>
                    ) : (
                        reports.map((report) => {
                            const Icon = reportTypeIcons[report.report_type] || FileText;
                            return (
                                <div
                                    key={report.id}
                                    className="flex flex-col gap-4 px-5 py-4 transition-colors hover:bg-white/5 xl:flex-row xl:items-center xl:justify-between"
                                >
                                    <div className="flex min-w-0 items-start gap-4">
                                        <div className="mt-1 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white/5">
                                            <Icon className="h-5 w-5 text-primary" />
                                        </div>
                                        <div className="min-w-0">
                                            <div className="flex flex-wrap items-center gap-3">
                                                <h4 className="text-sm font-semibold text-white">{report.title}</h4>
                                                <span className={`rounded-full px-2 py-1 text-[11px] font-medium ${getStatusClasses(report.status)}`}>
                                                    {formatStatusLabel(report.status)}
                                                </span>
                                            </div>
                                            <p className="mt-1 text-sm text-slate-400">{report.summary}</p>
                                            <div className="mt-3 flex flex-wrap items-center gap-4 text-xs text-slate-500">
                                                <span className="flex items-center gap-1">
                                                    <Calendar className="h-3.5 w-3.5" />
                                                    {formatDateRange(report.period_start, report.period_end)}
                                                </span>
                                                <span className="flex items-center gap-1">
                                                    <Clock className="h-3.5 w-3.5" />
                                                    {formatDateTimeLabel(report.generated_at)}
                                                </span>
                                                <span>{formatFileSize(report.file_size_bytes)}</span>
                                            </div>
                                        </div>
                                    </div>
                                    <div className="flex shrink-0 items-center gap-2">
                                        <button
                                            onClick={() => downloadAsCSV(report)}
                                            className="flex items-center gap-1 rounded-lg px-2 py-1.5 text-xs text-slate-400 transition-colors hover:bg-emerald-500/10 hover:text-emerald-400"
                                            title="Download CSV"
                                        >
                                            <Sheet className="h-3.5 w-3.5" />
                                            CSV
                                        </button>
                                        <button
                                            onClick={() => downloadAsJSON(report)}
                                            className="flex items-center gap-1 rounded-lg px-2 py-1.5 text-xs text-slate-400 transition-colors hover:bg-blue-500/10 hover:text-blue-400"
                                            title="Download JSON"
                                        >
                                            <FileJson className="h-3.5 w-3.5" />
                                            JSON
                                        </button>
                                        <button
                                            onClick={() => downloadAsJSON(report)}
                                            className="rounded-lg p-2 text-slate-400 transition-colors hover:bg-white/5 hover:text-white"
                                            title="Download"
                                        >
                                            <Download className="h-4 w-4" />
                                        </button>
                                    </div>
                                </div>
                            );
                        })
                    )}
                </div>
            </div>

            {showCreateModal && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm">
                    <div className="w-full max-w-md rounded-2xl border border-white/10 bg-slate-900 p-6 shadow-2xl">
                        <div className="mb-4 flex items-center justify-between">
                            <div>
                                <h2 className="text-xl font-bold text-white">Generate New Report</h2>
                                <p className="mt-1 text-sm text-slate-400">Leave the dates blank to use the current calendar month.</p>
                            </div>
                            <button
                                onClick={() => setShowCreateModal(false)}
                                className="p-1 text-slate-400 transition-colors hover:text-white"
                            >
                                <X className="h-5 w-5" />
                            </button>
                        </div>
                        {error && (
                            <div className="mb-4 rounded-lg border border-rose-500/20 bg-rose-500/10 p-3 text-sm text-rose-400">
                                {error}
                            </div>
                        )}
                        <form onSubmit={handleGenerate} className="space-y-4">
                            <div>
                                <label className="mb-2 block text-sm font-medium text-slate-300">Report Type</label>
                                <select
                                    name="reportType"
                                    value={selectedType}
                                    onChange={(event) => setSelectedType(event.target.value as BackendReportType | "")}
                                    className="w-full rounded-xl border border-white/10 bg-black/50 px-4 py-2 text-white outline-none transition-colors focus:border-primary"
                                >
                                    <option value="">Select type...</option>
                                    {reportTypes.map((type) => (
                                        <option key={type.id} value={type.id}>
                                            {type.name}
                                        </option>
                                    ))}
                                </select>
                            </div>
                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <label className="mb-2 block text-sm font-medium text-slate-300">Start Date</label>
                                    <input
                                        name="startDate"
                                        type="date"
                                        className="w-full rounded-xl border border-white/10 bg-black/50 px-4 py-2 text-white outline-none transition-colors focus:border-primary [color-scheme:dark]"
                                    />
                                </div>
                                <div>
                                    <label className="mb-2 block text-sm font-medium text-slate-300">End Date</label>
                                    <input
                                        name="endDate"
                                        type="date"
                                        className="w-full rounded-xl border border-white/10 bg-black/50 px-4 py-2 text-white outline-none transition-colors focus:border-primary [color-scheme:dark]"
                                    />
                                </div>
                            </div>
                            <div className="flex gap-3 pt-2">
                                <button
                                    type="button"
                                    onClick={() => setShowCreateModal(false)}
                                    className="flex-1 rounded-xl border border-white/10 px-4 py-2 text-slate-400 transition-colors hover:border-white/20 hover:text-white"
                                >
                                    Cancel
                                </button>
                                <button
                                    type="submit"
                                    disabled={isPending || !selectedType}
                                    className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-primary px-4 py-2 font-medium text-black transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
                                >
                                    {isPending ? (
                                        <>
                                            <Loader2 className="h-4 w-4 animate-spin" />
                                            Generating...
                                        </>
                                    ) : (
                                        "Generate"
                                    )}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
}
