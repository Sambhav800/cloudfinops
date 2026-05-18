"use client";

import React, { useState } from "react";
import { AlertCircle, CheckCircle, Loader2, Shield, UploadCloud } from "lucide-react";
import { useRouter } from "next/navigation";
import type { BillAnalysisRecord } from "@/lib/api";
import { getBillAnalysisId } from "@/lib/bill-analysis-client-state";

type Mode = "manual" | "automated";
type Provider = "aws" | "azure" | "gcp";

type Props = {
    onCancel: () => void;
};

export function BillUploadForm({ onCancel }: Props) {
    const router = useRouter();
    const uploadTimeoutMs = 240_000;
    const [mode, setMode] = useState<Mode>("manual");
    const [provider, setProvider] = useState<Provider>("aws");
    const [storagePath, setStoragePath] = useState("");
    const [credential, setCredential] = useState("");
    const [file, setFile] = useState<File | null>(null);
    const [showDiscounts, setShowDiscounts] = useState(false);
    const [awsDiscount, setAwsDiscount] = useState("0");
    const [gcpDiscount, setGcpDiscount] = useState("0");
    const [azureDiscount, setAzureDiscount] = useState("0");
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<string | null>(null);

    const acceptedExtensions = [".csv", ".xlsx", ".xls", ".pdf"];

    const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        const selected = event.target.files?.[0] ?? null;
        if (!selected) {
            return;
        }
        const extension = `.${selected.name.split(".").pop()?.toLowerCase() ?? ""}`;
        if (!acceptedExtensions.includes(extension)) {
            setError("Please upload a CSV, XLSX, XLS, or PDF file.");
            setFile(null);
            return;
        }
        setError(null);
        setFile(selected);
    };

    const handleSubmit = async (event: React.FormEvent) => {
        event.preventDefault();
        setError(null);
        setSuccess(null);

        if (mode === "manual" && !file) {
            setError("Select a billing file first.");
            return;
        }
        if (mode === "automated" && (!storagePath.trim() || !credential.trim())) {
            setError("Storage path and credentials are required.");
            return;
        }

        setIsSubmitting(true);
        try {
            if (mode === "manual") {
                const payload = new FormData();
                payload.append("file", file as File);
                payload.append("aws_discount_pct", awsDiscount);
                payload.append("gcp_discount_pct", gcpDiscount);
                payload.append("azure_discount_pct", azureDiscount);

                const controller = new AbortController();
                const timeoutId = window.setTimeout(() => controller.abort(), uploadTimeoutMs);
                let response: Response;
                try {
                    response = await fetch("/api/upload-bill", {
                        method: "POST",
                        body: payload,
                        signal: controller.signal,
                    });
                } catch (requestError) {
                    if (requestError instanceof Error && requestError.name === "AbortError") {
                        throw new Error(
                            "Bill analysis timed out. Try a CSV/Excel export, or use a smaller text-based PDF if this was a scanned invoice.",
                        );
                    }
                    throw requestError;
                } finally {
                    window.clearTimeout(timeoutId);
                }

                const data = await response.json() as Partial<BillAnalysisRecord> & {
                    analysis_id?: string;
                    detail?: string;
                };
                if (!response.ok) {
                    throw new Error(data?.detail || "Bill upload failed");
                }
                const analysisId = getBillAnalysisId(data);
                if (!analysisId) {
                    throw new Error("Bill analysis completed but no analysis record was returned.");
                }

                setSuccess("Bill analyzed and stored. Redirecting to the dashboard...");
                setTimeout(() => {
                    onCancel();
                    router.push(`/dashboard/arbitrage?id=${encodeURIComponent(analysisId)}&tab=executive`);
                }, 900);
                return;
            }

            const response = await fetch("/api/automated-billing-setup", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    provider,
                    storagePath,
                    credential,
                    awsDiscount,
                    gcpDiscount,
                    azureDiscount,
                }),
            });
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data?.error || "Automated setup failed");
            }

            setSuccess("Automated billing sync configured.");
            setTimeout(() => {
                onCancel();
                router.refresh();
            }, 1100);
        } catch (submitError) {
            setError(submitError instanceof Error ? submitError.message : "Unexpected error");
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <form onSubmit={handleSubmit} className="space-y-5">
            {error && (
                <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-300 flex items-start gap-2">
                    <AlertCircle className="h-4 w-4 mt-0.5 shrink-0" />
                    <p>{error}</p>
                </div>
            )}
            {success && (
                <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm text-emerald-300 flex items-start gap-2">
                    <CheckCircle className="h-4 w-4 mt-0.5 shrink-0" />
                    <p>{success}</p>
                </div>
            )}

            <div className="inline-flex rounded-lg border border-white/10 bg-black/30 p-1">
                <button
                    type="button"
                    onClick={() => setMode("manual")}
                    className={`px-3 py-2 text-sm rounded-md ${mode === "manual" ? "bg-indigo-600 text-white" : "text-slate-300"}`}
                >
                    Manual Upload
                </button>
                <button
                    type="button"
                    onClick={() => setMode("automated")}
                    className={`px-3 py-2 text-sm rounded-md ${mode === "automated" ? "bg-indigo-600 text-white" : "text-slate-300"}`}
                >
                    Automated Sync
                </button>
            </div>

            {mode === "manual" ? (
                <div className="rounded-xl border-2 border-dashed border-white/20 bg-black/20 p-6 text-center">
                    <input
                        id="bill-file-upload"
                        type="file"
                        accept=".csv,.xlsx,.xls,.pdf"
                        className="hidden"
                        onChange={handleFileChange}
                    />
                    <label htmlFor="bill-file-upload" className="cursor-pointer">
                        <div className="mx-auto mb-3 inline-flex rounded-full bg-white/5 p-3">
                            <UploadCloud className="h-6 w-6 text-slate-300" />
                        </div>
                        <p className="text-white text-sm font-medium">
                            {file ? file.name : "Click to upload cloud billing export"}
                        </p>
                        <p className="text-xs text-slate-400 mt-1">CSV / XLSX / XLS / PDF</p>
                    </label>
                </div>
            ) : (
                <div className="space-y-4 rounded-xl border border-white/10 bg-black/20 p-4">
                    <div className="flex gap-2">
                        {(["aws", "azure", "gcp"] as Provider[]).map((item) => (
                            <button
                                key={item}
                                type="button"
                                onClick={() => setProvider(item)}
                                className={`rounded px-3 py-1.5 text-xs uppercase border ${provider === item
                                    ? "border-indigo-400 bg-indigo-500/20 text-indigo-300"
                                    : "border-white/15 text-slate-300"
                                    }`}
                            >
                                {item}
                            </button>
                        ))}
                    </div>

                    <div>
                        <label className="block text-sm text-slate-300 mb-1">
                            {provider === "aws"
                                ? "S3 Bucket Name"
                                : provider === "azure"
                                    ? "Blob Container Name"
                                    : "BigQuery Table (project.dataset.table)"}
                        </label>
                        <input
                            type="text"
                            value={storagePath}
                            onChange={(event) => setStoragePath(event.target.value)}
                            className="w-full rounded-lg border border-white/10 bg-black/40 px-3 py-2 text-sm text-white"
                        />
                    </div>

                    <div>
                        <label className="block text-sm text-slate-300 mb-1">
                            {provider === "aws"
                                ? "Credential (access_key_id::secret_access_key)"
                                : provider === "azure"
                                    ? "Azure Connection String"
                                    : "Service Account JSON"}
                        </label>
                        <textarea
                            value={credential}
                            onChange={(event) => setCredential(event.target.value)}
                            rows={provider === "gcp" ? 4 : 2}
                            className="w-full rounded-lg border border-white/10 bg-black/40 px-3 py-2 text-sm text-white"
                        />
                    </div>
                </div>
            )}

            <div className="rounded-xl border border-white/10 bg-black/30 p-4">
                <button
                    type="button"
                    onClick={() => setShowDiscounts((current) => !current)}
                    className="text-sm text-indigo-300"
                >
                    {showDiscounts ? "Hide" : "Configure"} enterprise discounts
                </button>

                {showDiscounts && (
                    <div className="mt-3 grid grid-cols-1 sm:grid-cols-3 gap-3">
                        <input
                            type="number"
                            min={0}
                            max={100}
                            value={awsDiscount}
                            onChange={(event) => setAwsDiscount(event.target.value)}
                            className="rounded-lg border border-white/10 bg-black/40 px-3 py-2 text-sm text-white"
                            placeholder="AWS %"
                        />
                        <input
                            type="number"
                            min={0}
                            max={100}
                            value={gcpDiscount}
                            onChange={(event) => setGcpDiscount(event.target.value)}
                            className="rounded-lg border border-white/10 bg-black/40 px-3 py-2 text-sm text-white"
                            placeholder="GCP %"
                        />
                        <input
                            type="number"
                            min={0}
                            max={100}
                            value={azureDiscount}
                            onChange={(event) => setAzureDiscount(event.target.value)}
                            className="rounded-lg border border-white/10 bg-black/40 px-3 py-2 text-sm text-white"
                            placeholder="Azure %"
                        />
                    </div>
                )}
            </div>

            <div className="rounded-lg border border-indigo-500/30 bg-indigo-500/10 p-4 text-xs text-slate-300">
                <div className="flex items-center gap-2 text-indigo-300 mb-1">
                    <Shield className="h-4 w-4" />
                    Zero-Risk Reminder
                </div>
                {mode === "manual"
                    ? "Uploaded billing files are parsed, converted into a durable dashboard analysis record, and the original source file is retained privately for internal analysis and reprocessing when storage is configured."
                    : "Automated sync uses read-only billing storage credentials only (no compute write access)."}
            </div>

            <div className="flex justify-end gap-3">
                <button type="button" onClick={onCancel} className="px-4 py-2 text-slate-400">
                    Cancel
                </button>
                <button
                    type="submit"
                    disabled={isSubmitting || (mode === "manual" ? !file : !storagePath || !credential)}
                    className="px-5 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white disabled:opacity-60 flex items-center gap-2"
                >
                    {isSubmitting ? (
                        <>
                            <Loader2 className="h-4 w-4 animate-spin" />
                            Processing...
                        </>
                    ) : mode === "manual" ? (
                        "Analyze Bill"
                    ) : (
                        "Enable Sync"
                    )}
                </button>
            </div>
        </form>
    );
}
