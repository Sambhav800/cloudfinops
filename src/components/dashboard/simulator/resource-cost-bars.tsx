'use client';

import {
    Bar,
    BarChart,
    CartesianGrid,
    Cell,
    LabelList,
    Legend,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis,
} from 'recharts';

import type { SimulatorResourceItem } from './cost-delta-view';
import { formatInrCurrency, toDisplayInrAmount } from '@/lib/resources/contract';

type ResourceCostBarsProps = {
    resources: SimulatorResourceItem[];
};

const MAX_DISPLAY = 12;
const CHART_STYLE = {
    gridColor: 'rgba(255,255,255,0.08)',
    tickColor: '#94a3b8',
    tooltipBg: '#0f172a',
} as const;

function formatSimulatorMoney(value: number): string {
    if (!Number.isFinite(value)) {
        return formatInrCurrency(0, { minimumFractionDigits: 0, maximumFractionDigits: 0 });
    }
    return formatInrCurrency(toDisplayInrAmount(value, 'USD'), {
        minimumFractionDigits: 0,
        maximumFractionDigits: 0,
    });
}

export function ResourceCostBars({ resources }: ResourceCostBarsProps) {
    if (resources.length === 0) {
        return null;
    }

    const sorted = [...resources]
        .sort((left, right) => Math.abs(right.delta_monthly) - Math.abs(left.delta_monthly))
        .slice(0, MAX_DISPLAY);

    const chartData = sorted.map((resource) => {
        const delta = Number(resource.delta_monthly.toFixed(2));
        return {
            name:
                resource.resource_address.length > 24
                    ? `...${resource.resource_address.slice(-21)}`
                    : resource.resource_address,
            fullName: resource.resource_address,
            before: Number(resource.before_monthly.toFixed(2)),
            after: Number(resource.after_monthly.toFixed(2)),
            isIncrease: resource.delta_monthly > 0,
            deltaLabel: delta === 0 ? '' : `${delta > 0 ? '+' : '-'}${formatSimulatorMoney(Math.abs(delta))}`,
        };
    });

    return (
        <div className="min-w-0">
            {resources.length > MAX_DISPLAY ? (
                <p className="mb-3 text-xs text-slate-500">
                    Showing top {MAX_DISPLAY} of {resources.length} resources by cost impact
                </p>
            ) : null}
            <div className="h-[380px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={chartData} margin={{ top: 28, right: 20, bottom: 88, left: 4 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke={CHART_STYLE.gridColor} vertical={false} />
                        <XAxis
                            dataKey="name"
                            tick={{ fontSize: 11, fill: CHART_STYLE.tickColor }}
                            angle={-35}
                            textAnchor="end"
                            interval={0}
                            height={86}
                            tickMargin={12}
                        />
                        <YAxis
                            width={64}
                            tickFormatter={(value) => formatSimulatorMoney(Number(value))}
                            tick={{ fontSize: 11, fill: CHART_STYLE.tickColor }}
                        />
                        <Tooltip
                            contentStyle={{
                                background: CHART_STYLE.tooltipBg,
                                border: '1px solid rgba(255,255,255,0.12)',
                                borderRadius: 12,
                                color: '#e2e8f0',
                            }}
                            formatter={(value, name) => [`${formatSimulatorMoney(Number(value))}/mo`, String(name)]}
                            labelFormatter={(label) => String(label)}
                        />
                        <Legend wrapperStyle={{ color: '#cbd5e1', fontSize: 12 }} />
                        <Bar dataKey="before" name="Before" fill="#64748b" radius={[4, 4, 0, 0]} />
                        <Bar dataKey="after" name="After" radius={[4, 4, 0, 0]}>
                            {chartData.map((entry) => (
                                <Cell
                                    key={entry.fullName}
                                    fill={entry.isIncrease ? '#fb7185' : '#34d399'}
                                />
                            ))}
                            <LabelList
                                dataKey="deltaLabel"
                                position="top"
                                style={{ fill: '#cbd5e1', fontSize: 10 }}
                            />
                        </Bar>
                    </BarChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
}
