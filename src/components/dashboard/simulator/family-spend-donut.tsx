'use client';

import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';

import type { SimulatorResourceItem } from './cost-delta-view';
import { formatInrCurrency, toDisplayInrAmount } from '@/lib/resources/contract';

type FamilySpendDonutProps = {
    resources: SimulatorResourceItem[];
};

const FAMILY_COLORS: Record<string, string> = {
    compute: '#6366f1',
    storage: '#34d399',
    network: '#f59e0b',
    database: '#a78bfa',
    serverless: '#f472b6',
    kubernetes: '#38bdf8',
    other: '#94a3b8',
};

function formatSimulatorMoney(value: number): string {
    return formatInrCurrency(toDisplayInrAmount(value, 'USD'), {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    });
}

export function FamilySpendDonut({ resources }: FamilySpendDonutProps) {
    if (resources.length === 0) {
        return (
            <div className="flex h-[220px] items-center justify-center rounded-2xl border border-dashed border-white/10 bg-white/[0.02] px-6 text-center">
                <p className="text-sm text-slate-500">No priced resource families to chart.</p>
            </div>
        );
    }

    const familyTotals = resources.reduce<Record<string, number>>((totals, resource) => {
        const family = resource.resource_family || 'other';
        totals[family] = (totals[family] ?? 0) + resource.after_monthly;
        return totals;
    }, {});

    const chartData = Object.entries(familyTotals)
        .filter(([, value]) => value > 0)
        .sort(([, left], [, right]) => right - left)
        .map(([name, value]) => ({
            name,
            value: Number(value.toFixed(2)),
        }));

    if (chartData.length === 0) {
        return (
            <div className="flex h-[220px] items-center justify-center rounded-2xl border border-dashed border-white/10 bg-white/[0.02] px-6 text-center">
                <p className="text-sm text-slate-500">Projected priced spend is zero for this plan.</p>
            </div>
        );
    }

    const total = chartData.reduce((sum, item) => sum + item.value, 0);

    return (
        <div className="flex flex-col gap-6 lg:flex-row lg:items-center">
            <div className="mx-auto h-[220px] w-full max-w-[260px] flex-shrink-0 lg:h-[240px] lg:max-w-[260px]">
                <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                        <Pie
                            data={chartData}
                            cx="50%"
                            cy="50%"
                            innerRadius={54}
                            outerRadius={82}
                            dataKey="value"
                            strokeWidth={0}
                        >
                            {chartData.map((entry) => (
                                <Cell key={entry.name} fill={FAMILY_COLORS[entry.name] ?? FAMILY_COLORS.other} />
                            ))}
                        </Pie>
                        <Tooltip
                            contentStyle={{
                                background: '#0f172a',
                                border: '1px solid rgba(255,255,255,0.12)',
                                borderRadius: 12,
                                color: '#e2e8f0',
                            }}
                            formatter={(value) => [`${formatSimulatorMoney(Number(value))}/mo`, 'Projected']}
                        />
                    </PieChart>
                </ResponsiveContainer>
            </div>
            <div className="min-w-0 flex-1">
                <p className="text-xs uppercase tracking-wide text-slate-500">Total projected</p>
                <p className="mt-1 break-words text-[clamp(1.5rem,2vw,2rem)] font-semibold leading-tight text-white">
                    {formatSimulatorMoney(total)}/mo
                </p>
                <div className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-1">
                    {chartData.map((item) => (
                        <div key={item.name} className="flex items-center gap-2 text-sm">
                            <span
                                className="h-2.5 w-2.5 rounded-sm"
                                style={{ backgroundColor: FAMILY_COLORS[item.name] ?? FAMILY_COLORS.other }}
                            />
                            <span className="flex-1 capitalize text-slate-400">{item.name}</span>
                            <span className="font-medium text-slate-200">{formatSimulatorMoney(item.value)}</span>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}
