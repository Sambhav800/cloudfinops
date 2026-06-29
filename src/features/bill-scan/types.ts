/**
 * Types for the public/unauthenticated Bill Scanner feature.
 * Spec §3 redaction map shapes what the backend returns.
 */

/** Waste grade letter from the backend heuristic (savings% of total spend). */
export type WasteGrade = "A" | "B" | "C" | "D" | "F";

/** A single top-level finding teaser — resource IDs and fix steps are redacted. */
export interface FindingTeaser {
  /** Service / product name (e.g. "Amazon EC2", "Azure Blob Storage"). */
  service: string;
  /** Truncated description of the waste pattern. No raw evidence rows. */
  what_we_found: string;
  /** High-level infrastructure category (Compute, Storage, Networking, …). */
  category: string;
  /** Estimated monthly cost impact in `currency` units. */
  estimated_impact: number;
}

/**
 * Redacted payload returned by `POST /api/scan/public-upload`.
 * Full details (resource IDs, scripts, all findings) require an account.
 */
export interface TeaserReportPayload {
  provider_detected: "aws" | "azure" | "gcp" | "generic";
  total_analyzed_spend: number;
  currency: string;
  by_category: Record<string, number>;
  waste_grade: WasteGrade;
  waste_grade_label: string;
  estimated_monthly_savings_min: number;
  estimated_monthly_savings_max: number;
  /** Top 3 findings only — no evidence_lines, no how_to_fix. */
  top_findings_teaser: FindingTeaser[];
  /** Always "SIGNUP_REQUIRED" — signals the paywall in the frontend. */
  remediation_status: "SIGNUP_REQUIRED";
  rows_parsed: number;
}

/** All possible states the page can be in. */
export type ScanState =
  | { status: "idle" }
  | { status: "uploading"; file: File }
  | { status: "results"; data: TeaserReportPayload; fileName: string }
  | { status: "error"; message: string };
