"use client";


/**
 * IntegrationHealthPanel
 *
 * Renders per-integration telemetry: inventory scan, billing refresh, and
 * AI-enrichment status.  Data is fetched from GET /api/integration-health
 * and auto-refreshed every 60 s while the component is mounted.
 *
 * Rules:
 * - Never invent timestamps — all timestamps come verbatim from the API.
 * - Use persisted retry_at for billing cooldown; never compute a fake one.
 * - Display cached cost notice when using_cached_costs === true.
 * - Show AI enrichment counts (queued / running / enriched / failed).
 * - Billing stale threshold is the 6-hour cache contract; the API signals it.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Activity,
  AlertTriangle,
  Bot,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Clock,
  CreditCard,
  RefreshCw,
  ServerCrash,
  Wifi,
  WifiOff,
} from "lucide-react";

import type {
  AIEnrichmentHealth,
  BillingHealth,
  IntegrationHealth,
  IntegrationHealthBatchResponse,
  InventoryHealth,
} from "@/components/dashboard/integration-health-types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function relativeTime(iso: string | null): string {
  if (!iso) return "—";
  const delta = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(delta / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

function retryCountdown(retryAt: string | null): string | null {
  if (!retryAt) return null;
  const delta = new Date(retryAt).getTime() - Date.now();
  if (delta <= 0) return null;
  const mins = Math.ceil(delta / 60_000);
  if (mins < 60) return `retry in ${mins}m`;
  const hrs = Math.ceil(delta / 3_600_000);
  return `retry in ${hrs}h`;
}

type StatusLevel = "ok" | "stale" | "failed" | "never" | "partial";

function statusColors(status: StatusLevel) {
  switch (status) {
    case "ok":
      return {
        dot: "bg-emerald-400",
        badge: "bg-emerald-500/10 text-emerald-300 border-emerald-500/20",
        text: "text-emerald-300",
      };
    case "stale":
    case "partial":
      return {
        dot: "bg-amber-400",
        badge: "bg-amber-500/10 text-amber-300 border-amber-500/20",
        text: "text-amber-300",
      };
    case "failed":
      return {
        dot: "bg-red-400",
        badge: "bg-red-500/10 text-red-300 border-red-500/20",
        text: "text-red-300",
      };
    case "never":
    default:
      return {
        dot: "bg-gray-500",
        badge: "bg-white/5 text-gray-400 border-white/10",
        text: "text-gray-400",
      };
  }
}

// ---------------------------------------------------------------------------
// Sub-rows
// ---------------------------------------------------------------------------

function StatusDot({ status }: { status: StatusLevel }) {
  const { dot } = statusColors(status);
  const pulse = status === "ok" ? " animate-pulse" : "";
  return (
    <span
      className={`inline-block h-2 w-2 rounded-full flex-shrink-0 ${dot}${pulse}`}
    />
  );
}

function SectionLabel({ label }: { label: string }) {
  return (
    <span className="text-[11px] uppercase tracking-widest text-gray-500 font-semibold">
      {label}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Inventory sub-panel
// ---------------------------------------------------------------------------

function InventoryRow({ inv }: { inv: InventoryHealth }) {
  const colors = statusColors(inv.status);
  const countdown = null; // inventory has no retry_at

  return (
    <div className="rounded-xl border border-white/5 bg-black/20 p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Wifi className="h-4 w-4 text-sky-400" />
          <SectionLabel label="Inventory Scan" />
        </div>
        <span
          className={`rounded-full border px-2.5 py-0.5 text-xs font-medium flex items-center gap-1.5 ${colors.badge}`}
        >
          <StatusDot status={inv.status} />
          {inv.status}
        </span>
      </div>

      <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
        <div>
          <dt className="text-gray-500">Last success</dt>
          <dd className="font-medium text-gray-200">{relativeTime(inv.last_success_at)}</dd>
        </div>
        <div>
          <dt className="text-gray-500">Last attempt</dt>
          <dd className="font-medium text-gray-200">{relativeTime(inv.last_attempt_at)}</dd>
        </div>
        <div>
          <dt className="text-gray-500">Data observed</dt>
          <dd className="font-medium text-gray-200">{relativeTime(inv.data_observed_at)}</dd>
        </div>
        <div>
          <dt className="text-gray-500">Resources</dt>
          <dd className="font-medium text-gray-200">
            {inv.resource_count > 0 ? inv.resource_count.toLocaleString() : "—"}
          </dd>
        </div>
      </dl>

      {inv.display_message && (
        <p className="rounded-lg bg-red-500/5 border border-red-500/10 px-3 py-2 text-xs text-red-300 flex items-start gap-2">
          <AlertTriangle className="h-3.5 w-3.5 flex-shrink-0 mt-0.5" />
          {inv.display_message}
          {inv.reason_code && (
            <code className="ml-auto rounded bg-white/5 px-1.5 py-0.5 font-mono text-[10px] text-gray-400">
              {inv.reason_code}
            </code>
          )}
        </p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Billing sub-panel
// ---------------------------------------------------------------------------

function BillingRow({ billing }: { billing: BillingHealth }) {
  const colors = statusColors(billing.status);
  const countdown = retryCountdown(billing.retry_at);

  return (
    <div className="rounded-xl border border-white/5 bg-black/20 p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <CreditCard className="h-4 w-4 text-violet-400" />
          <SectionLabel label="Billing Refresh" />
        </div>
        <div className="flex items-center gap-2">
          {billing.using_cached_costs && (
            <span className="rounded-full border border-amber-500/20 bg-amber-500/10 px-2.5 py-0.5 text-xs text-amber-300 flex items-center gap-1">
              <Clock className="h-3 w-3" />
              cached costs
            </span>
          )}
          <span
            className={`rounded-full border px-2.5 py-0.5 text-xs font-medium flex items-center gap-1.5 ${colors.badge}`}
          >
            <StatusDot status={billing.status} />
            {billing.status}
          </span>
        </div>
      </div>

      <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
        <div>
          <dt className="text-gray-500">Last success</dt>
          <dd className="font-medium text-gray-200">{relativeTime(billing.last_success_at)}</dd>
        </div>
        <div>
          <dt className="text-gray-500">Last attempt</dt>
          <dd className="font-medium text-gray-200">{relativeTime(billing.last_attempt_at)}</dd>
        </div>
        <div>
          <dt className="text-gray-500">Data observed</dt>
          <dd className="font-medium text-gray-200">{relativeTime(billing.data_observed_at)}</dd>
        </div>
        <div>
          <dt className="text-gray-500">
            {countdown ? "Retry cooldown" : "Next eligible"}
          </dt>
          <dd className={`font-medium ${countdown ? "text-amber-300" : "text-gray-200"}`}>
            {countdown ?? "now"}
          </dd>
        </div>
      </dl>

      {billing.display_message && (
        <p className="rounded-lg bg-red-500/5 border border-red-500/10 px-3 py-2 text-xs text-red-300 flex items-start gap-2">
          <AlertTriangle className="h-3.5 w-3.5 flex-shrink-0 mt-0.5" />
          {billing.display_message}
          {billing.reason_code && (
            <code className="ml-auto rounded bg-white/5 px-1.5 py-0.5 font-mono text-[10px] text-gray-400">
              {billing.reason_code}
            </code>
          )}
        </p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// AI Enrichment sub-panel
// ---------------------------------------------------------------------------

function AIEnrichmentRow({ ai }: { ai: AIEnrichmentHealth }) {
  const hasActivity = ai.running > 0 || ai.queued > 0;
  const hasFailures = ai.failed > 0;

  return (
    <div className="rounded-xl border border-white/5 bg-black/20 p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Bot className="h-4 w-4 text-fuchsia-400" />
          <SectionLabel label="AI Enrichment" />
        </div>
        <span className="text-xs text-gray-500">
          {relativeTime(ai.last_success_at)}
        </span>
      </div>

      <div className="flex flex-wrap gap-2 text-xs">
        <span className="rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-gray-300">
          {ai.enriched.toLocaleString()} enriched
        </span>
        {ai.queued > 0 && (
          <span className="rounded-full border border-sky-500/20 bg-sky-500/10 px-2.5 py-1 text-sky-300">
            {ai.queued} queued
          </span>
        )}
        {ai.running > 0 && (
          <span className="rounded-full border border-violet-500/20 bg-violet-500/10 px-2.5 py-1 text-violet-300 flex items-center gap-1">
            <Activity className="h-3 w-3 animate-pulse" />
            {ai.running} running
          </span>
        )}
        {ai.failed > 0 && (
          <span className="rounded-full border border-red-500/20 bg-red-500/10 px-2.5 py-1 text-red-300">
            {ai.failed} failed
          </span>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Per-integration accordion card
// ---------------------------------------------------------------------------

function IntegrationHealthCard({ integration }: { integration: IntegrationHealth }) {
  const [expanded, setExpanded] = useState(false);

  const worstStatus: StatusLevel = (() => {
    const statuses = [integration.inventory.status, integration.billing.status];
    if (statuses.some((s) => s === "failed")) return "failed";
    if (statuses.some((s) => s === "stale" || s === "partial")) return "stale";
    if (statuses.every((s) => s === "ok")) return "ok";
    if (statuses.some((s) => s === "never")) return "never";
    return "ok";
  })();

  const { badge } = statusColors(worstStatus);

  const providerColor =
    integration.provider === "aws"
      ? "bg-orange-500/10 text-orange-300"
      : integration.provider === "azure"
        ? "bg-sky-500/10 text-sky-300"
        : "bg-emerald-500/10 text-emerald-300";

  return (
    <div className="rounded-2xl border border-white/5 bg-black/20 overflow-hidden">
      {/* Header row — always visible */}
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center gap-3 p-4 text-left hover:bg-white/5 transition-colors"
        aria-expanded={expanded}
        id={`health-card-${integration.integration_id}`}
      >
        <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${providerColor}`}>
          {integration.provider.toUpperCase()}
        </span>
        <span className="flex-1 font-medium text-white truncate">{integration.name}</span>
        <span className={`rounded-full border px-2.5 py-0.5 text-xs font-medium flex items-center gap-1.5 ${badge}`}>
          <StatusDot status={worstStatus} />
          {worstStatus}
        </span>
        {expanded ? (
          <ChevronUp className="h-4 w-4 text-gray-400 flex-shrink-0" />
        ) : (
          <ChevronDown className="h-4 w-4 text-gray-400 flex-shrink-0" />
        )}
      </button>

      {/* Expanded detail rows */}
      {expanded && (
        <div className="border-t border-white/5 p-4 space-y-3">
          <InventoryRow inv={integration.inventory} />
          <BillingRow billing={integration.billing} />
          <AIEnrichmentRow ai={integration.ai_enrichment} />
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main panel — fetches and renders all integrations
// ---------------------------------------------------------------------------

interface IntegrationHealthPanelProps {
  /** Auth token getter from useAuth() — passed in so the component stays testable */
  getToken: () => Promise<string | null>;
}

export function IntegrationHealthPanel({ getToken }: IntegrationHealthPanelProps) {
  const [data, setData] = useState<IntegrationHealthBatchResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchHealth = useCallback(async () => {
    try {
      const token = await getToken();
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const res = await fetch("/api/integration-health", { headers });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body?.detail ?? `HTTP ${res.status}`);
      }
      const json: IntegrationHealthBatchResponse = await res.json();
      setData(json);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load health data");
    } finally {
      setLoading(false);
    }
  }, [getToken]);

  useEffect(() => {
    fetchHealth();
    // Auto-refresh every 60 seconds
    intervalRef.current = setInterval(fetchHealth, 60_000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [fetchHealth]);

  // ---------- Loading ----------
  if (loading) {
    return (
      <div className="space-y-3" aria-label="Loading integration health">
        {[1, 2].map((i) => (
          <div
            key={i}
            className="h-16 animate-pulse rounded-2xl border border-white/5 bg-black/20"
          />
        ))}
      </div>
    );
  }

  // ---------- Error ----------
  if (error) {
    return (
      <div
        className="rounded-2xl border border-red-500/20 bg-red-500/5 px-4 py-6 flex items-center gap-3 text-sm text-red-300"
        role="alert"
        id="integration-health-error"
      >
        <ServerCrash className="h-5 w-5 flex-shrink-0" />
        <span>Could not load integration health: {error}</span>
        <button
          type="button"
          onClick={fetchHealth}
          className="ml-auto rounded-lg border border-red-500/20 px-3 py-1 text-xs hover:bg-red-500/10 transition-colors"
        >
          Retry
        </button>
      </div>
    );
  }

  // ---------- No integrations ----------
  if (!data || data.integrations.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-white/10 bg-black/20 px-6 py-8 text-center text-gray-500 text-sm">
        No connected integrations to show health for.
      </div>
    );
  }

  return (
    <section aria-label="Integration health" id="integration-health-panel" className="space-y-4">
      {/* Panel header with refresh */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-base font-semibold text-white">Integration Health</h3>
          <p className="mt-0.5 text-xs text-gray-500">
            Inventory scan · Billing refresh · AI enrichment — updated{" "}
            {relativeTime(data.fetched_at)}
          </p>
        </div>
        <button
          type="button"
          onClick={fetchHealth}
          title="Refresh health status"
          className="rounded-lg p-2 text-gray-500 hover:bg-white/5 hover:text-gray-300 transition-colors"
          id="refresh-integration-health-btn"
        >
          <RefreshCw className="h-4 w-4" />
        </button>
      </div>

      {/* Per-integration cards */}
      <div className="space-y-3">
        {data.integrations.map((integration) => (
          <IntegrationHealthCard
            key={integration.integration_id}
            integration={integration}
          />
        ))}
      </div>
    </section>
  );
}

