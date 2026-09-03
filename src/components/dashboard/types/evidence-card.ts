export type SignalStatus = 'passed' | 'warning' | 'failed' | 'missing';
export type VetoCheckStatus = 'cleared' | 'vetoed' | 'unassessed';
export type RiskLevel = 'low' | 'medium' | 'high';

export interface ResourceSummary {
  resource_name: string;
  cloud_resource_id: string;
  provider: 'aws' | 'azure' | 'gcp' | string;
  resource_type: string;
  monthly_cost: number;
  recommended_action: string;
  estimated_monthly_savings: number;
  region?: string;
}

export interface CorroboratingSignalDetail {
  key: 'cpu' | 'network' | 'disk' | 'memory' | 'state' | 'connections' | string;
  name: string;
  status: SignalStatus;
  observed_value: unknown;
  observed_display: string;
  threshold_display: string;
  description: string;
  is_missing?: boolean;
}

export interface SafetyClearanceItem {
  check_key: 'dr_tag' | 'asg_fleet' | 'blue_green' | 'recent_state_change' | 'backup_replication' | string;
  title: string;
  status: VetoCheckStatus;
  description: string;
  details?: string | null;
}

export interface EvidenceCardData {
  recommendation_id: string;
  resource_summary: ResourceSummary;
  corroborating_signals: Record<string, CorroboratingSignalDetail>;
  safety_clearance: SafetyClearanceItem[];
  risk_level: RiskLevel;
  risk_explanation: string;
  why_flagged_explanation: string;
  missing_data_warnings: string[];
  created_at?: string;
}
