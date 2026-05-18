"use client";

import type { ReactNode } from "react";
import { Reveal } from "@/components/landing/reveal";

type SectionHeadingProps = {
    eyebrow: string;
    title: ReactNode;
    description?: string;
    align?: "left" | "center";
};

export function SectionHeading({
    eyebrow,
    title,
    description,
    align = "left",
}: SectionHeadingProps) {
    const wrapperClassName =
        align === "center"
            ? "mx-auto max-w-3xl text-center"
            : "max-w-3xl";

    return (
        <Reveal>
            <div className={wrapperClassName}>
                <p className="mb-4 text-[11px] font-medium uppercase tracking-[0.2em] text-indigo-400">
                    {eyebrow}
                </p>
                <h2 className="text-[40px] font-medium leading-[1.1] tracking-tight text-white md:text-[48px]">
                    {title}
                </h2>
                {description ? (
                    <p className="mt-4 max-w-2xl text-[16px] leading-relaxed text-zinc-400">
                        {description}
                    </p>
                ) : null}
            </div>
        </Reveal>
    );
}
