'use client';

import React, { useState } from 'react';
import {
  ShieldCheck,
  ShieldAlert,
  AlertTriangle,
  Cpu,
  Network,
  HardDrive,
  Activity,
  Server,
  Zap,
  CheckCircle2,
  XCircle,
  HelpCircle,
  ChevronDown,
  ChevronUp,
  Info,
  DollarSign,
} from 'lucide-react';
import { EvidenceCardData, CorroboratingSignalDetail, SafetyClearanceItem } from './types/evidence-card';

interface EvidenceCardProps {
  cardData: EvidenceCardData;
  className?: string;
}

export function EvidenceCard({ cardData, className = '' }: EvidenceCardProps) {
  const [showClearanceDetails, setShowClearanceDetails] = useState(true);
  const { resource_summary, corroborating_signals, safety_clearance, risk_level, risk_explanation, why_flagged_explanation, missing_data_warnings } = cardData;

  // Provider colors
  const providerColor = (provider: string) => {
    switch (provider.toLowerCase()) {
      case 'aws':
        return 'bg-amber-500/10 text-amber-400 border-amber-500/20';
      case 'azure':
        return 'bg-blue-500/10 text-blue-400 border-blue-500/20';
      case 'gcp':
        return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20';
      default:
        return 'bg-purple-500/10 text-purple-400 border-purple-500/20';
    }
  };

  // Risk badge colors
  const riskBadgeColor = (risk: string) => {
    switch (risk.toLowerCase()) {
      case 'low':
        return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30';
      case 'medium':
        return 'bg-amber-500/10 text-amber-400 border-amber-500/30';
      case 'high':
        return 'bg-rose-500/10 text-rose-400 border-rose-500/30';
      default:
        return 'bg-slate-500/10 text-slate-400 border-slate-500/30';
    }
  };

  // Signal status icon
  const getSignalIcon = (key: string) => {
    switch (key.toLowerCase()) {
      case 'cpu':
        return <Cpu className="w-4 h-4 text-cyan-400" />;
      case 'network':
        return <Network className="w-4 h-4 text-indigo-400" />;
      case 'disk':
        return <HardDrive className="w-4 h-4 text-purple-400" />;
      case 'memory':
        return <Activity className="w-4 h-4 text-emerald-400" />;
      case 'state':
        return <Server className="w-4 h-4 text-amber-400" />;
      case 'connections':
        return <Zap className="w-4 h-4 text-sky-400" />;
      default:
        return <Info className="w-4 h-4 text-slate-400" />;
    }
  };

  const getSignalStatusBadge = (status: string, isMissing?: boolean) => {
    if (isMissing || status === 'missing') {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded border bg-slate-800/80 text-slate-400 border-slate-700">
          <HelpCircle className="w-3 h-3 text-slate-400" /> Missing
        </span>
      );
    }
    if (status === 'passed') {
      return (
        <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded border bg-emerald-500/10 text-emerald-400 border-emerald-500/30">
          <CheckCircle2 className="w-3 h-3 text-emerald-400" /> Corroborated
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 text-xs rounded border bg-amber-500/10 text-amber-400 border-amber-500/30">
        <AlertTriangle className="w-3 h-3 text-amber-400" /> Warning
      </span>
    );
  };

  return (
    <div className={`rounded-xl border border-slate-800 bg-slate-900/90 backdrop-blur-md p-6 space-y-6 text-slate-100 shadow-2xl ${className}`}>
      {/* HEADER: Resource & Action Summary */}
      <div className="flex flex-wrap items-start justify-between gap-4 pb-5 border-b border-slate-800/80">
        <div className="space-y-1.5">
          <div className="flex items-center gap-2.5">
            <span className={`px-2.5 py-0.5 text-xs font-semibold uppercase rounded-md border ${providerColor(resource_summary.provider)}`}>
              {resource_summary.provider}
            </span>
            <h3 className="text-lg font-bold text-slate-100 tracking-tight">{resource_summary.resource_name}</h3>
            {resource_summary.region && (
              <span className="text-xs text-slate-400 bg-slate-800 px-2 py-0.5 rounded border border-slate-700">
                {resource_summary.region}
              </span>
            )}
          </div>
          <p className="text-xs font-mono text-slate-400">ID: {resource_summary.cloud_resource_id}</p>
          <div className="text-xs text-slate-300">
            Type: <span className="font-medium text-slate-200">{resource_summary.resource_type}</span>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {/* Action Badge */}
          <div className="px-3 py-1.5 rounded-lg border bg-cyan-500/10 border-cyan-500/30 text-cyan-300 text-xs font-semibold uppercase tracking-wide">
            Action: {resource_summary.recommended_action}
          </div>

          {/* Monthly Savings Badge */}
          <div className="px-3 py-1 rounded-lg border bg-emerald-500/10 border-emerald-500/30 text-emerald-400 text-sm font-bold flex items-center gap-1">
            <DollarSign className="w-4 h-4 text-emerald-400" />
            <span>${resource_summary.estimated_monthly_savings.toFixed(2)}/mo savings</span>
          </div>

          {/* Risk Level Badge */}
          <div className={`px-3 py-1 rounded-lg border text-xs font-bold uppercase tracking-wider flex items-center gap-1.5 ${riskBadgeColor(risk_level)}`}>
            {risk_level.toLowerCase() === 'low' ? <ShieldCheck className="w-4 h-4" /> : <ShieldAlert className="w-4 h-4" />}
            <span>Risk: {risk_level}</span>
          </div>
        </div>
      </div>

      {/* MISSING DATA WARNING BANNER */}
      {missing_data_warnings && missing_data_warnings.length > 0 && (
        <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3.5 space-y-1">
          <div className="flex items-center gap-2 text-amber-300 font-semibold text-xs uppercase tracking-wider">
            <AlertTriangle className="w-4 h-4 text-amber-400" />
            <span>Telemetry Completeness Warning</span>
          </div>
          <ul className="text-xs text-amber-200/90 space-y-1 list-disc list-inside">
            {missing_data_warnings.map((warning, idx) => (
              <li key={idx}>{warning}</li>
            ))}
          </ul>
        </div>
      )}

      {/* "WHY WE FLAGGED THIS" EXPLANATION */}
      <div className="rounded-xl border border-indigo-500/20 bg-indigo-950/20 p-4 space-y-1.5">
        <div className="flex items-center gap-2 text-indigo-300 font-semibold text-xs uppercase tracking-wider">
          <Info className="w-4 h-4 text-indigo-400" />
          <span>Why We Flagged This</span>
        </div>
        <p className="text-sm text-indigo-100/90 leading-relaxed font-normal">
          {why_flagged_explanation}
        </p>
      </div>

      {/* CORROBORATING TELEMETRY SIGNALS GRID (6 Core Signals) */}
      <div className="space-y-3">
        <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center justify-between">
          <span>Corroborating Telemetry Signals ({Object.keys(corroborating_signals).length})</span>
          <span className="text-[11px] font-normal text-slate-500">Multi-Signal Bottleneck Verification</span>
        </h4>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {Object.entries(corroborating_signals).map(([key, signal]: [string, CorroboratingSignalDetail]) => (
            <div
              key={key}
              className={`rounded-lg border p-3.5 space-y-2 transition-colors ${
                signal.is_missing
                  ? 'border-slate-800 bg-slate-900/40 opacity-75'
                  : 'border-slate-800/90 bg-slate-950/60 hover:border-slate-700'
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  {getSignalIcon(signal.key)}
                  <span className="text-xs font-semibold text-slate-200">{signal.name}</span>
                </div>
                {getSignalStatusBadge(signal.status, signal.is_missing)}
              </div>
              <div className="space-y-0.5">
                <div className="text-xs font-mono font-medium text-slate-100">{signal.observed_display}</div>
                <div className="text-[11px] text-slate-400 flex items-center justify-between">
                  <span>Threshold: {signal.threshold_display}</span>
                </div>
              </div>
              <p className="text-[11px] text-slate-400 leading-snug">{signal.description}</p>
            </div>
          ))}
        </div>
      </div>

      {/* SAFETY CLEARANCE CHECKLIST (5 Core Veto Checks) */}
      <div className="rounded-xl border border-slate-800 bg-slate-950/80 overflow-hidden">
        <button
          onClick={() => setShowClearanceDetails(!showClearanceDetails)}
          className="w-full px-4 py-3 bg-slate-900/80 hover:bg-slate-800/80 flex items-center justify-between transition-colors border-b border-slate-800"
        >
          <div className="flex items-center gap-2.5">
            <ShieldCheck className="w-5 h-5 text-emerald-400" />
            <span className="text-sm font-semibold text-slate-200">Safety Clearance Audit Checklist</span>
            <span className="text-xs text-slate-400 bg-slate-800 px-2 py-0.5 rounded border border-slate-700 font-mono">
              {safety_clearance.filter((i) => i.status === 'cleared').length}/{safety_clearance.length} Cleared
            </span>
          </div>
          {showClearanceDetails ? (
            <ChevronUp className="w-4 h-4 text-slate-400" />
          ) : (
            <ChevronDown className="w-4 h-4 text-slate-400" />
          )}
        </button>

        {showClearanceDetails && (
          <div className="p-4 space-y-2.5 divide-y divide-slate-800/60">
            {safety_clearance.map((item: SafetyClearanceItem, idx: number) => (
              <div key={item.check_key || idx} className={`${idx > 0 ? 'pt-2.5' : ''} flex items-start justify-between gap-4`}>
                <div className="space-y-0.5">
                  <div className="flex items-center gap-2">
                    {item.status === 'cleared' ? (
                      <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                    ) : (
                      <XCircle className="w-4 h-4 text-rose-400 shrink-0" />
                    )}
                    <span className="text-xs font-semibold text-slate-200">{item.title}</span>
                  </div>
                  <p className="text-xs text-slate-300 pl-6">{item.description}</p>
                  {item.details && <p className="text-[11px] font-mono text-slate-400 pl-6">{item.details}</p>}
                </div>

                <div>
                  {item.status === 'cleared' ? (
                    <span className="px-2 py-0.5 text-[11px] font-semibold rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                      CLEARED
                    </span>
                  ) : (
                    <span className="px-2 py-0.5 text-[11px] font-semibold rounded bg-rose-500/10 text-rose-400 border border-rose-500/30">
                      VETOED
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* FOOTER: Risk Explanation & Audit Trail */}
      <div className="pt-2 text-xs text-slate-400 flex flex-wrap items-center justify-between gap-2 border-t border-slate-800/60">
        <span>{risk_explanation}</span>
        <span className="font-mono text-[11px] text-slate-500">Deterministic Safety Engine v2.0</span>
      </div>
    </div>
  );
}
