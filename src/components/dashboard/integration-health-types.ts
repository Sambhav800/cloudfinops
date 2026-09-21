/**
 * Types mirroring the backend IntegrationHealthResponse Pydantic schema.
 * See: backend/app/api/routes.py  →  /api/integration-health
 */

export interface InventoryHealth {
  /** ISO-8601 timestamp of the most recent successful inventory scan, or null */
  last_success_at: string | null;
  /** ISO-8601 timestamp of the most recent scan attempt (success OR failure), or null */
  last_attempt_at: string | null;
  /**
   * ISO-8601 timestamp when the inventory data was actually observed at the
   * provider (may differ from last_success_at for cached results)
   */
  data_observed_at: string | null;
  /** One of: "ok" | "stale" | "partial" | "failed" | "never" */
  status: "ok" | "stale" | "partial" | "failed" | "never";
  /** Allowlisted reason code — never a raw SDK error string */
  reason_code: string | null;
  /** Safe, user-facing error message (no SDK / credential details) */
  display_message: string | null;
  /** Number of resources that were successfully scanned */
  resource_count: number;
}

export interface BillingHealth {
  /** ISO-8601 timestamp of the most recent successful billing refresh */
  last_success_at: string | null;
  /** ISO-8601 timestamp of the most recent billing refresh attempt */
  last_attempt_at: string | null;
  /**
   * ISO-8601 timestamp of the billing data that was last successfully
   * retrieved (may be older than last_success_at when data is cached)
   */
  data_observed_at: string | null;
  /** One of: "ok" | "stale" | "failed" | "never" */
  status: "ok" | "stale" | "failed" | "never";
  /** Allowlisted reason code */
  reason_code: string | null;
  /** Safe display message */
  display_message: string | null;
  /** ISO-8601 timestamp before which a retry should NOT be attempted */
  retry_at: string | null;
  /** Whether the last billing cost value is being preserved from a prior run */
  using_cached_costs: boolean;
}

export interface AIEnrichmentHealth {
  /** ISO-8601 timestamp of the most recent successful enrichment job */
  last_success_at: string | null;
  /** Counts across all enrichment jobs for this integration */
  queued: number;
  running: number;
  enriched: number;
  failed: number;
}

export interface IntegrationHealth {
  integration_id: string;
  provider: string;
  name: string;
  inventory: InventoryHealth;
  billing: BillingHealth;
  ai_enrichment: AIEnrichmentHealth;
}

export interface IntegrationHealthBatchResponse {
  integrations: IntegrationHealth[];
  fetched_at: string;
}
