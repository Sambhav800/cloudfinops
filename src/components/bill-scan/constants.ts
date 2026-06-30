/**
 * Constants for the public Bill Scanner feature.
 * Single source of truth — never hardcode these values in components.
 */

/** 20 MB free-tier file size cap (in bytes). */
export const MAX_FILE_BYTES = 20 * 1024 * 1024;

/** Human-readable size cap for display copy. */
export const MAX_FILE_SIZE_LABEL = "20 MB";

/** Accepted MIME types and extensions for the dropzone. */
export const ACCEPTED_MIME_TYPES = [
  "text/csv",
  "application/vnd.ms-excel",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "application/pdf",
];

export const ACCEPTED_EXTENSIONS = [".csv", ".xlsx", ".xls", ".pdf"];

/** Rate limit notice shown in the UI (enforced on the backend). */
export const RATE_LIMIT_COPY = "5 free scans per hour per IP";

/** Public API endpoint path — matches the Next.js rewrite. */
export const PUBLIC_UPLOAD_ENDPOINT = "/api/scan/public-upload";

/** Client-side request timeout in ms. */
export const UPLOAD_TIMEOUT_MS = 60_000;

/** Processing stage labels for the animated progress indicator. */
export const PROCESSING_STAGES = [
  "Uploading file…",
  "Parsing billing data…",
  "Detecting cloud provider…",
  "Calculating waste metrics…",
  "Generating teaser report…",
] as const;

/** Waste grade display metadata. */
export const WASTE_GRADE_META: Record<
  string,
  { label: string; color: string; bg: string; description: string }
> = {
  A: {
    label: "A",
    color: "text-emerald-400",
    bg: "bg-emerald-500/10 border-emerald-500/30",
    description: "Excellent — minimal waste detected",
  },
  B: {
    label: "B",
    color: "text-teal-400",
    bg: "bg-teal-500/10 border-teal-500/30",
    description: "Good — small optimizations available",
  },
  C: {
    label: "C",
    color: "text-amber-400",
    bg: "bg-amber-500/10 border-amber-500/30",
    description: "Moderate — significant savings on the table",
  },
  D: {
    label: "D",
    color: "text-orange-400",
    bg: "bg-orange-500/10 border-orange-500/30",
    description: "Poor — high waste detected",
  },
  F: {
    label: "F",
    color: "text-rose-400",
    bg: "bg-rose-500/10 border-rose-500/30",
    description: "Critical — severe overspend detected",
  },
};
