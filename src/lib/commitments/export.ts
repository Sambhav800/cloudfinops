import type { CommitmentRecommendationResponse, CommitmentScenario } from "../api";
import { formatCommitmentDate, formatCommitmentMoney, formatCommitmentPercent, RECOMMENDATION_STATUS_LABELS } from "./presentation";

function escapeHtml(value: string): string {
    return value.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#39;");
}

export function buildCommitmentExport(data: CommitmentRecommendationResponse, scenarios: CommitmentScenario[]): string {
    const text = escapeHtml;
    const money = (value: number) => text(formatCommitmentMoney(value, data.currency));
    const rows = scenarios.map((option) => `<tr>
        <td>${text(option.account_id)}<br>${text(option.integration_id)}</td>
        <td>${text(option.label)}<br>${option.term_years}-year, ${text(option.payment_option)}<br>Lookback: ${option.lookback_days} days</td>
        <td>${money(option.hourly_commitment_usd)}</td>
        <td>${money(option.monthly_commitment_usd)}</td>
        <td>${money(option.monthly_saving_usd)}</td>
        <td>${money(option.annual_saving_usd)}</td>
        <td>${text(formatCommitmentPercent(option.provider_estimated_savings_pct))}</td>
        <td>${text(formatCommitmentPercent(option.estimated_utilization_pct))}</td>
        <td>Not measured</td>
        <td>${text(formatCommitmentDate(option.generated_at, true))}</td>
    </tr>`).join("");
    const notes = (data.important_notes ?? []).map((note) => `<li>${text(note)}</li>`).join("");
    return `<!doctype html><html><head><meta charset="utf-8"><title>CloudFinOps provider purchase estimates</title>
        <style>@page { size: landscape; margin: 12mm; } body { font: 12px Arial, sans-serif; color: #111827; } table { width: 100%; border-collapse: collapse; table-layout: fixed; } th, td { border: 1px solid #d1d5db; padding: 8px; text-align: left; overflow-wrap: anywhere; } th { background: #f3f4f6; } tr { break-inside: avoid; } h1 { font-size: 22px; }</style></head><body>
        <h1>AWS Compute Savings Plan purchase estimates</h1>
        <p>Source: AWS Cost Explorer | Status: ${text(RECOMMENDATION_STATUS_LABELS[data.status])}</p>
        <p>Fetched: ${text(formatCommitmentDate(data.fetched_at, true))} | Generated: ${text(formatCommitmentDate(data.generated_at, true))} | Pricing basis: ${data.pricing_basis === "live_api" ? "Provider API" : "Not measured"}</p>
        ${data.message ? `<p>${text(data.message)}</p>` : ""}
        <table><thead><tr><th>Account / integration</th><th>Alternative</th><th>Hourly commitment</th><th>Monthly equivalent</th><th>Estimated monthly savings</th><th>Estimated annual savings</th><th>Estimated savings %</th><th>Estimated utilization</th><th>Over-commitment risk</th><th>Generated</th></tr></thead><tbody>${rows}</tbody></table>
        <h2>Important notes</h2><ul>${notes}</ul></body></html>`;
}
