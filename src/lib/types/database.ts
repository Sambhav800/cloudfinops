// Database types for MongoDB collections

export interface Profile {
    id: string;
    email: string | null;
    full_name: string | null;
    company_name: string | null;
    avatar_url: string | null;
    created_at: string;
    updated_at: string;
}

export interface CloudAccount {
    id: string;
    user_id: string;
    provider: 'aws' | 'azure';
    account_id: string;
    account_name: string | null;
    role_arn: string | null;
    status: 'pending' | 'active' | 'error';
    last_scan_at: string | null;
    created_at: string;
}

export interface Resource {
    id: string;
    cloud_account_id: string;
    resource_id: string;
    resource_type: string;
    resource_name: string | null;
    region: string | null;
    monthly_cost: number | null;
    utilization: number | null;
    status: string;
    tags: Record<string, string> | null;
    metadata: Record<string, unknown> | null;
    last_updated: string;
}

export interface PendingAction {
    id: string;
    resource_id: string | null;
    cloud_account_id: string;
    action_type: string;
    title: string;
    description: string | null;
    estimated_savings: number | null;
    risk_level: 'low' | 'medium' | 'high';
    status: 'pending' | 'approved' | 'rejected' | 'completed';
    created_at: string;
    resolved_at: string | null;
}

export interface Report {
    id: string;
    user_id: string;
    report_type: string;
    title: string;
    period_start: string | null;
    period_end: string | null;
    data: Record<string, unknown> | null;
    file_url: string | null;
    status: string;
    created_at: string;
}

export interface GovernancePolicy {
    id: string;
    user_id: string;
    name: string;
    description: string | null;
    policy_type: string;
    rules: Record<string, unknown> | null;
    is_active: boolean;
    created_at: string;
}

export interface Alert {
    id: string;
    user_id: string;
    cloud_account_id: string | null;
    alert_type: string;
    severity: 'info' | 'warning' | 'critical';
    title: string;
    message: string | null;
    is_read: boolean;
    created_at: string;
}

export interface UserSettings {
    id: string;
    user_id: string;
    email_notifications: boolean;
    alert_threshold: number | null;
    timezone: string;
    preferences: Record<string, unknown>;
    created_at: string;
    updated_at: string;
}

// Database helper type
export interface Database {
    profiles: Profile;
    cloud_accounts: CloudAccount;
    resources: Resource;
    pending_actions: PendingAction;
    reports: Report;
    governance_policies: GovernancePolicy;
    alerts: Alert;
    user_settings: UserSettings;
}
