'use client';

import {
    Bar,
    BarChart,
    CartesianGrid,
    Cell,
    ReferenceLine,
    ResponsiveContainer,
    Tooltip,
    XAxis,
    YAxis,
} from 'recharts';

import type { SimulatorData } from './cost-delta-view';
import { formatInrCurrency, toDisplayInrAmount } from '@/lib/resources/contract';

type MonthlyAnnualWaterfallProps = {
    data: SimulatorData;
};

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

export function MonthlyAnnualWaterfall({ data }: MonthlyAnnualWaterfallProps) {
    const monthlyData = [
        { label: 'Current', value: Number(data.monthly.before.toFixed(2)), type: 'before' },
        {
            label: 'Projected',
            value: Number(data.monthly.after.toFixed(2)),
            type: data.monthly.delta > 0 ? 'increase' : 'saving',
        },
    ];
    const annualData = [
        { label: 'Current', value: Number(data.annual.before.toFixed(2)), type: 'before' },
        {
            label: 'Projected',
            value: Number(data.annual.after.toFixed(2)),
            type: data.annual.delta > 0 ? 'increase' : 'saving',
        },
    ];

    const colors = {
        before: '#64748b',
        increase: '#fb7185',
        saving: '#34d399',
    } as const;

    const renderChart = (
        title: string,
        delta: number,
        chartData: Array<{ label: string; value: number; type: string }>,
        className = '',
    ) => (
        <div className={`min-w-0 ${className}`}>
            <div className="mb-3 flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
                <div>
                    <p className="text-sm font-medium text-white">{title}</p>
                    <p className="text-xs text-slate-500">Current vs projected</p>
                </div>
                <p className={`text-sm font-semibold ${delta > 0 ? 'text-rose-400' : delta < 0 ? 'text-emerald-400' : 'text-slate-400'}`}>
                    {delta > 0 ? '+' : ''}
                    {formatSimulatorMoney(delta)}
                </p>
            </div>
            <div className="h-[240px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={chartData} margin={{ top: 16, right: 12, bottom: 8, left: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke={CHART_STYLE.gridColor} vertical={false} />
                        <XAxis
                            dataKey="label"
                            tick={{ fontSize: 11, fill: CHART_STYLE.tickColor }}
                            interval={0}
                            tickMargin={8}
                        />
                        <YAxis
                            width={58}
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
                            formatter={(value) => [formatSimulatorMoney(Number(value)), 'Cost']}
                        />
                        <ReferenceLine y={0} stroke="rgba(255,255,255,0.16)" />
                        <Bar dataKey="value" barSize={64} radius={[4, 4, 0, 0]}>
                            {chartData.map((entry) => (
                                <Cell key={`${title}-${entry.label}`} fill={colors[entry.type as keyof typeof colors]} />
                            ))}
                        </Bar>
                    </BarChart>
                </ResponsiveContainer>
            </div>
        </div>
    );

    return (
        <div className="grid grid-cols-1 gap-5 2xl:grid-cols-2">
            {renderChart('Monthly impact', data.monthly.delta, monthlyData)}
            {renderChart(
                'Annual impact',
                data.annual.delta,
                annualData,
                'border-t border-white/10 pt-5 2xl:border-l 2xl:border-t-0 2xl:pl-5 2xl:pt-0',
            )}
        </div>
    );
}
