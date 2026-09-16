export type CommitmentRiskLevel = "low" | "medium" | "high";

export interface MathBreakdown {
  on_demand_hourly?: number;
  p10_hourly?: number;
  p50_hourly?: number;
  p75_hourly?: number;
  coverage_target_pct?: number;
  committed_hourly?: number;
  discount_rate?: number;
  monthly_on_demand?: number;
  monthly_committed?: number;
  monthly_savings?: number;
  break_even_months?: number;
  observation_days?: number;
  instance_family?: string;
  region?: string;
  [key: string]: unknown;
}

export interface CommitmentRecommendation {
  commitment_type: string;
  provider: "aws" | "azure" | "gcp" | string;
  region: string;
  instance_family: string;
  term: "1_year" | "3_year" | string;
  payment_option: "all_upfront" | "partial_upfront" | "no_upfront" | string;
  hourly_commitment: number;
  monthly_commitment: number;
  discount_rate: number;
  estimated_monthly_savings: number;
  estimated_annual_savings: number;
  coverage_pct: number;
  utilization_confidence: number;
  risk_level: CommitmentRiskLevel;
  explanation: string;
  math_breakdown: MathBreakdown;
  priority?: number;
}

export interface UnderutilizedCommitment {
  id?: string;
  name?: string;
  type?: string;
  utilization_pct: number;
  commitment_amount: number;
  wasted_monthly: number;
  action: string;
}

export interface ExpiringCommitment {
  id?: string;
  name?: string;
  type?: string;
  end_date: string;
  days_left: number;
  utilization_pct: number;
  action: string;
}

export interface CommitmentPortfolio {
  recommendations: CommitmentRecommendation[];
  total_monthly_savings: number;
  total_annual_savings: number;
  current_monthly_on_demand: number;
  projected_monthly_after_commitments: number;
  overall_coverage_pct: number;
  overall_savings_pct: number;
  existing_commitment_utilization: number;
  underutilized_commitments: UnderutilizedCommitment[];
  expiring_soon: ExpiringCommitment[];
  strategy_summary: string;
}
