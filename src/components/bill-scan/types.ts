/**
 * Types for the public/unauthenticated Bill Scanner feature.
 * Spec §3 redaction map shapes what the backend returns.
 */

/** Waste grade letter from the backend heuristic (savings% of total spend). */
export type WasteGrade = "A" | "B" | "C" | "D" | "F";

/** A single finding teaser with real insights — resource IDs and fix scripts are locked. */
export interface FindingTeaser {
  service: string;
  cost: number;
  pct_of_total: number;
  what_we_found: string;
  optimization_options: string;
  risk_level: "high" | "medium" | "low";
  category: string;
  estimated_impact: number;
}

/**
 * Enriched payload returned by `POST /api/scan/public-upload`.
 * Shows real analysis value — locks remediation scripts and resource IDs behind signup.
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
  top_findings_teaser: FindingTeaser[];
  remediation_status: "SIGNUP_REQUIRED";
  rows_parsed: number;
  total_services_detected: number;
  services_above_5pct: number;
  cost_concentration_top3_pct: number;
  cloudfront_insights?: {
    total_cost?: number;
    cache_hit_opportunity?: string;
    top_recommendation?: string;
  };
  gpu_insights?: {
    total_gpu_cost?: number;
    instance_types_detected?: string[];
    spot_savings_opportunity?: number;
  };
  existing_credits_detected: number;
  analysis_depth: string;
  annual_waste_so_far?: number;
  cost_of_waiting_30d?: number;
  benchmark_percentile?: number;
  benchmark_label?: string;
  quick_win?: {
    title: string;
    saving_estimate: number;
    time_required: string;
    risk: string;
    description: string;
  };
  cross_cloud_hint?: {
    message: string;
    provider_compared: string;
    potential_saving_pct: number;
  };
}

/** All possible states the page can be in. */
export type ScanState =
  | { status: "idle" }
  | { status: "uploading"; file: File }
  | { status: "results"; data: TeaserReportPayload; fileName: string }
  | { status: "error"; message: string };
