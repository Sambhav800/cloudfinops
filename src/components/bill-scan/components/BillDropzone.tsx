"use client";

import { useCallback, useRef, useState } from "react";
import { UploadCloud, FileText, X, AlertCircle } from "lucide-react";
import { ACCEPTED_EXTENSIONS, MAX_FILE_BYTES, MAX_FILE_SIZE_LABEL } from "../constants";

interface BillDropzoneProps {
  onFileReady: (file: File) => void;
  disabled?: boolean;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function validateFile(file: File): string | null {
  const ext = `.${file.name.split(".").pop()?.toLowerCase() ?? ""}`;
  if (!ACCEPTED_EXTENSIONS.includes(ext)) {
    return `Unsupported format "${ext}". Please upload a CSV, XLSX, XLS, or PDF file.`;
  }
  if (file.size > MAX_FILE_BYTES) {
    return `File is too large (${formatBytes(file.size)}). Free tier limit is ${MAX_FILE_SIZE_LABEL}.`;
  }
  return null;
}

export function BillDropzone({ onFileReady, disabled = false }: BillDropzoneProps) {
  const [isDragOver, setIsDragOver] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = useCallback(
    (file: File) => {
      const validationError = validateFile(file);
      if (validationError) {
        setError(validationError);
        setSelectedFile(null);
        return;
      }
      setError(null);
      setSelectedFile(file);
      onFileReady(file);
    },
    [onFileReady],
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragOver(false);
      if (disabled) return;
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [disabled, handleFile],
  );

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) handleFile(file);
      // Reset so the same file can be re-selected
      e.target.value = "";
    },
    [handleFile],
  );

  const clearFile = useCallback(() => {
    setSelectedFile(null);
    setError(null);
  }, []);

  const openPicker = useCallback(() => {
    if (!disabled) inputRef.current?.click();
  }, [disabled]);

  return (
    <div className="space-y-3">
      {/* Hidden file input */}
      <input
        ref={inputRef}
        id="bill-file-input"
        type="file"
        accept={ACCEPTED_EXTENSIONS.join(",")}
        className="hidden"
        onChange={handleInputChange}
        disabled={disabled}
        aria-label="Upload cloud billing file"
      />

      {/* Dropzone surface */}
      <div
        role="button"
        tabIndex={disabled ? -1 : 0}
        aria-disabled={disabled}
        onClick={openPicker}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") openPicker();
        }}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={[
          "relative flex min-h-[220px] cursor-pointer flex-col items-center justify-center gap-4",
          "rounded-2xl border-2 border-dashed p-8 text-center transition-all duration-300",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950",
          disabled
            ? "cursor-not-allowed border-white/10 opacity-50"
            : isDragOver
              ? "border-indigo-500 bg-indigo-500/10 shadow-[0_0_40px_rgba(99,102,241,0.2)]"
              : selectedFile
                ? "border-emerald-500/50 bg-emerald-500/5"
                : "border-white/20 bg-white/[0.03] hover:border-indigo-400/60 hover:bg-indigo-500/5",
        ].join(" ")}
      >
        {/* Glow overlay on drag */}
        {isDragOver && (
          <div className="pointer-events-none absolute inset-0 rounded-2xl bg-indigo-500/5" />
        )}

        {selectedFile ? (
          <>
            {/* File selected state */}
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-emerald-500/10 ring-1 ring-emerald-500/30">
              <FileText className="h-7 w-7 text-emerald-400" />
            </div>
            <div className="space-y-1">
              <p className="font-semibold text-white">{selectedFile.name}</p>
              <p className="text-sm text-slate-400">{formatBytes(selectedFile.size)}</p>
            </div>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                clearFile();
              }}
              className="absolute right-4 top-4 flex h-7 w-7 items-center justify-center rounded-full bg-white/10 text-slate-400 transition hover:bg-white/20 hover:text-white"
              aria-label="Remove selected file"
            >
              <X className="h-4 w-4" />
            </button>
          </>
        ) : (
          <>
            {/* Idle / drag-over state */}
            <div
              className={[
                "flex h-14 w-14 items-center justify-center rounded-2xl transition-all duration-300",
                isDragOver
                  ? "bg-indigo-500/20 ring-1 ring-indigo-500/50"
                  : "bg-white/5 ring-1 ring-white/10",
              ].join(" ")}
            >
              <UploadCloud
                className={[
                  "h-7 w-7 transition-colors duration-300",
                  isDragOver ? "text-indigo-400" : "text-slate-400",
                ].join(" ")}
              />
            </div>

            <div className="space-y-1.5">
              <p className="text-base font-semibold text-white">
                {isDragOver ? "Drop your bill here" : "Drag & drop your cloud billing file"}
              </p>
              <p className="text-sm text-slate-400">
                or{" "}
                <span className="font-medium text-indigo-400 underline underline-offset-2">
                  browse to upload
                </span>
              </p>
            </div>

            {/* Format badges */}
            <div className="flex items-center gap-2">
              {["PDF", "CSV", "XLSX"].map((fmt) => (
                <span
                  key={fmt}
                  className="rounded-md border border-white/10 bg-white/5 px-2.5 py-0.5 text-xs font-mono font-medium text-slate-400"
                >
                  {fmt}
                </span>
              ))}
              <span className="text-xs text-slate-500">· up to {MAX_FILE_SIZE_LABEL}</span>
            </div>
          </>
        )}
      </div>

      {/* Validation error */}
      {error && (
        <div className="flex items-start gap-2 rounded-xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-300">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}
    </div>
  );
}
