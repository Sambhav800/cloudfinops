"use client";

import { useEffect, useRef, useState } from "react";
import {
    animate,
    motion,
    useInView,
    useMotionValue,
    useMotionValueEvent,
    useTransform,
} from "framer-motion";
import { SectionHeading } from "@/components/landing/section-heading";
import { EASE } from "@/components/landing/tokens";

type CountKind = "percent" | "money" | "integer";

type MetricItem = {
    value: number;
    kind?: CountKind;
    staticValue?: string;
    label: string;
    accentClassName: string;
    delay: number;
};

const METRICS: MetricItem[] = [
    {
        value: 42,
        kind: "percent",
        label: "average monthly cloud spend reduction across deployed accounts",
        accentClassName: "bg-indigo-500",
        delay: 0,
    },
    {
        value: 18.4,
        kind: "money",
        label: "in cloud waste identified and eliminated across customer base",
        accentClassName: "bg-emerald-500",
        delay: 0.08,
    },
    {
        value: 0,
        staticValue: "< 5 min",
        label: "from first connection to first actionable insight — no agents",
        accentClassName: "bg-amber-500",
        delay: 0.16,
    },
    {
        value: 3,
        kind: "integer",
        label: "hyperscalers unified under a single cost and governance plane",
        accentClassName: "bg-rose-500",
        delay: 0.24,
    },
];

function formatCount(kind: CountKind, value: number) {
    switch (kind) {
        case "percent":
            return `${Math.round(value)}%`;
        case "money":
            return `$${value.toFixed(1)}M+`;
        case "integer":
            return `${Math.round(value)}`;
        default:
            return `${value}`;
    }
}

function CountUp({
    value,
    kind,
    staticValue,
}: Pick<MetricItem, "value" | "kind" | "staticValue">) {
    const ref = useRef<HTMLSpanElement | null>(null);
    const inView = useInView(ref, { once: true, margin: "-100px" });
    const motionValue = useMotionValue(0);
    const transformed = useTransform(motionValue, (latest) =>
        formatCount(kind ?? "integer", latest),
    );
    const [displayValue, setDisplayValue] = useState(
        staticValue ?? formatCount(kind ?? "integer", 0),
    );

    useMotionValueEvent(transformed, "change", (latest) => {
        setDisplayValue(latest);
    });

    useEffect(() => {
        if (!inView || staticValue || !kind) {
            return;
        }

        const controls = animate(motionValue, value, {
            duration: 2,
            delay: 0.65,
            ease: EASE,
        });

        return () => {
            controls.stop();
        };
    }, [inView, kind, motionValue, staticValue, value]);

    useEffect(() => {
        if (staticValue && inView) {
            setDisplayValue(staticValue);
        }
    }, [inView, staticValue]);

    return (
        <motion.span
            ref={ref}
            initial={staticValue ? { opacity: 0, y: 16 } : undefined}
            whileInView={staticValue ? { opacity: 1, y: 0 } : undefined}
            viewport={{ once: true, margin: "-100px" }}
            transition={staticValue ? { duration: 0.7, ease: EASE, delay: 0.25 } : undefined}
        >
            {displayValue}
        </motion.span>
    );
}

function MetricCard({
    value,
    kind,
    staticValue,
    label,
    accentClassName,
    delay,
}: MetricItem) {
    return (
        <motion.div
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-100px" }}
            transition={{ duration: 0.7, delay, ease: EASE }}
            className="text-left"
        >
            <motion.div
                initial={{ width: 0, opacity: 0 }}
                whileInView={{ width: 40, opacity: 1 }}
                viewport={{ once: true, margin: "-100px" }}
                transition={{ duration: 0.6, delay, ease: EASE }}
                className={`mb-6 h-0.5 ${accentClassName}`}
            />
            <div className="text-[64px] font-medium leading-none tracking-[-0.04em] text-white md:text-[80px]">
                <CountUp value={value} kind={kind} staticValue={staticValue} />
            </div>
            <p className="mt-3 max-w-[200px] text-[13px] leading-relaxed text-zinc-400">
                {label}
            </p>
        </motion.div>
    );
}

export function Metrics() {
    return (
        <section className="px-6 py-32">
            <div className="mx-auto max-w-7xl">
                <SectionHeading
                    eyebrow="BY THE NUMBERS"
                    align="center"
                    title={
                        <>
                            Built to deliver <span className="text-zinc-500">measurable</span>{" "}
                            impact.
                        </>
                    }
                />

                <div className="mt-20 grid grid-cols-2 gap-x-8 gap-y-16 md:grid-cols-4">
                    {METRICS.map((metric) => (
                        <MetricCard key={metric.label} {...metric} />
                    ))}
                </div>
            </div>
        </section>
    );
}
