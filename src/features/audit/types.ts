export type WasteGrade = 'A' | 'B' | 'C' | 'D' | 'F';

export interface TeaserReportPayload {
  provider_detected: string;
  total_analyzed_spend: number;
  currency: string;
  by_category: Record<string, number>;
  top_services_teaser: Array<{ service: string; what_we_found: string }>;
  waste_grade: WasteGrade;
  remediation_status: 'SIGNUP_REQUIRED';
}