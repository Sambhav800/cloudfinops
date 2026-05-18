'use client';

import React, { useEffect, useMemo, useRef, useState } from 'react';
import mermaid from 'mermaid';
import { AlertCircle, Loader2 } from 'lucide-react';

interface ArchitectureMermaidProps {
    mermaidCode: string;
    id: string;
    provider?: string;
    viewKey?: string;
}

interface Palette {
    accent: string;
    accentSoft: string;
    clusterFill: string;
    clusterBorder: string;
    line: string;
    text: string;
}

function getPalette(provider?: string): Palette {
    const normalized = provider?.trim().toLowerCase();

    if (normalized === 'aws') {
        return {
            accent: '#f59e0b',
            accentSoft: '#451a03',
            clusterFill: '#111827',
            clusterBorder: '#f59e0b',
            line: '#fbbf24',
            text: '#e5edf6',
        };
    }

    if (normalized === 'azure') {
        return {
            accent: '#38bdf8',
            accentSoft: '#082f49',
            clusterFill: '#0f172a',
            clusterBorder: '#38bdf8',
            line: '#7dd3fc',
            text: '#e5edf6',
        };
    }

    if (normalized === 'gcp') {
        return {
            accent: '#34d399',
            accentSoft: '#052e2b',
            clusterFill: '#0f172a',
            clusterBorder: '#34d399',
            line: '#6ee7b7',
            text: '#e5edf6',
        };
    }

    return {
        accent: '#22d3ee',
        accentSoft: '#083344',
        clusterFill: '#0f172a',
        clusterBorder: '#22d3ee',
        line: '#67e8f9',
        text: '#e5edf6',
    };
}

function getLineColor(viewKey: string | undefined, palette: Palette): string {
    if (!viewKey) {
        return palette.line;
    }

    if (viewKey === 'cost_hotspots' || viewKey === 'proposed_cost') {
        return '#fb7185';
    }

    if (viewKey === 'proposed_reliability') {
        return '#60a5fa';
    }

    if (viewKey === 'microservices') {
        return '#34d399';
    }

    return palette.line;
}

function buildSvgStyles(palette: Palette, lineColor: string): string {
    return `
<style>
    .cloudfinops-architecture-svg {
        max-width: 100%;
        height: auto;
    }

    .cloudfinops-architecture-svg .cluster rect {
        fill: ${palette.clusterFill} !important;
        stroke: ${palette.clusterBorder} !important;
        stroke-width: 1.2px !important;
        rx: 22px;
        ry: 22px;
        filter: drop-shadow(0 18px 28px rgba(2, 6, 23, 0.32));
    }

    .cloudfinops-architecture-svg .node rect,
    .cloudfinops-architecture-svg .node circle,
    .cloudfinops-architecture-svg .node ellipse,
    .cloudfinops-architecture-svg .node polygon,
    .cloudfinops-architecture-svg .node path {
        stroke-width: 1.25px !important;
        filter: drop-shadow(0 16px 26px rgba(2, 6, 23, 0.28));
    }

    .cloudfinops-architecture-svg .edgePath .path,
    .cloudfinops-architecture-svg .flowchart-link {
        stroke: ${lineColor} !important;
        stroke-width: 1.6px !important;
        opacity: 0.92;
    }

    .cloudfinops-architecture-svg .marker path {
        fill: ${lineColor} !important;
        stroke: ${lineColor} !important;
    }

    .cloudfinops-architecture-svg .edgeLabel,
    .cloudfinops-architecture-svg .labelBkg {
        fill: rgba(15, 23, 42, 0.92) !important;
        background: rgba(15, 23, 42, 0.92) !important;
    }

    .cloudfinops-architecture-svg .edgeLabel p,
    .cloudfinops-architecture-svg .edgeLabel span,
    .cloudfinops-architecture-svg .cluster-label text,
    .cloudfinops-architecture-svg .cluster-label span,
    .cloudfinops-architecture-svg .nodeLabel p,
    .cloudfinops-architecture-svg .nodeLabel span,
    .cloudfinops-architecture-svg .label text,
    .cloudfinops-architecture-svg tspan {
        fill: ${palette.text} !important;
        color: ${palette.text} !important;
        font-weight: 600;
        letter-spacing: 0.01em;
    }

    .cloudfinops-architecture-svg .cluster-label text,
    .cloudfinops-architecture-svg .cluster-label span {
        font-weight: 700;
    }
</style>`;
}

function injectSvgStyles(svg: string, palette: Palette, lineColor: string): string {
    return svg.replace(/<svg([^>]*)>/, (_match, attrs: string) => {
        const patchedAttrs = /class="/.test(attrs)
            ? attrs.replace(/class="([^"]*)"/, 'class="$1 cloudfinops-architecture-svg"')
            : `${attrs} class="cloudfinops-architecture-svg"`;

        return `${buildSvgStyles(palette, lineColor)}<svg${patchedAttrs}>`;
    });
}

export function ArchitectureMermaid({
    mermaidCode,
    id,
    provider,
    viewKey,
}: ArchitectureMermaidProps) {
    const containerRef = useRef<HTMLDivElement>(null);
    const [error, setError] = useState<string | null>(null);
    const [rendering, setRendering] = useState<boolean>(true);

    const palette = useMemo(() => getPalette(provider), [provider]);
    const lineColor = useMemo(() => getLineColor(viewKey, palette), [palette, viewKey]);

    useEffect(() => {
        let isMounted = true;

        const renderDiagram = async () => {
            if (!containerRef.current || !mermaidCode) {
                setRendering(false);
                return;
            }

            setRendering(true);
            setError(null);

            mermaid.initialize({
                startOnLoad: false,
                securityLevel: 'strict',
                theme: 'base',
                themeVariables: {
                    background: 'transparent',
                    primaryColor: palette.accentSoft,
                    primaryTextColor: palette.text,
                    primaryBorderColor: palette.accent,
                    lineColor,
                    textColor: palette.text,
                    secondaryColor: '#0f172a',
                    tertiaryColor: '#020617',
                    clusterBkg: palette.clusterFill,
                    clusterBorder: palette.clusterBorder,
                    mainBkg: 'rgba(15, 23, 42, 0.92)',
                    edgeLabelBackground: '#0f172a',
                    fontFamily: 'ui-sans-serif, system-ui, sans-serif',
                },
            });

            try {
                const svgId = `mermaid-svg-${id}`;
                containerRef.current.innerHTML = '';

                const { svg } = await mermaid.render(svgId, mermaidCode);

                if (isMounted && containerRef.current) {
                    containerRef.current.innerHTML = injectSvgStyles(svg, palette, lineColor);
                    setRendering(false);
                }
            } catch (err: unknown) {
                console.error('Mermaid rendering failed:', err);
                if (isMounted) {
                    const message = err instanceof Error ? err.message : 'Failed to render diagram';
                    setError(message);
                    setRendering(false);
                }
            }
        };

        void renderDiagram();

        return () => {
            isMounted = false;
        };
    }, [id, lineColor, mermaidCode, palette]);

    if (error) {
        return (
            <div className="flex min-h-[420px] flex-col items-center justify-center rounded-2xl border border-rose-500/20 bg-rose-500/10 p-8">
                <AlertCircle className="mb-3 h-10 w-10 text-rose-500" />
                <h3 className="mb-1 text-base font-semibold text-white">Diagram Rendering Error</h3>
                <p className="max-w-md break-all text-center font-mono text-sm text-rose-300">
                    {error}
                </p>
            </div>
        );
    }

    return (
        <div className="relative flex min-h-[460px] w-full items-center justify-center overflow-auto rounded-2xl border border-white/10 bg-[linear-gradient(160deg,rgba(15,23,42,0.92),rgba(2,6,23,0.96))] p-6 shadow-[0_28px_70px_rgba(2,6,23,0.45)]">
            <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(255,255,255,0.06),transparent_30%),radial-gradient(circle_at_bottom_right,rgba(34,211,238,0.1),transparent_32%)]" />

            {rendering ? (
                <div className="absolute inset-0 z-10 flex flex-col items-center justify-center rounded-2xl bg-slate-950/70 backdrop-blur-sm">
                    <Loader2 className="mb-3 h-8 w-8 animate-spin text-indigo-400" />
                    <p className="text-sm font-medium tracking-wide text-slate-200">Rendering Architecture</p>
                </div>
            ) : null}

            <div
                ref={containerRef}
                className="relative z-[1] flex w-full items-center justify-center overflow-visible"
            />
        </div>
    );
}
