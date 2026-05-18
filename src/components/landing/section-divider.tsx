"use client";

export function SectionDivider() {
    return (
        <section aria-hidden="true" className="py-16">
            <div className="mx-auto max-w-7xl px-6">
                <div className="relative overflow-hidden">
                    <div className="h-px bg-gradient-to-r from-transparent via-white/[0.08] to-transparent" />
                    <div className="absolute top-1/2 h-[2px] w-24 -translate-y-1/2 bg-gradient-to-r from-transparent via-indigo-400 to-transparent animate-[beam_4s_ease-in-out_infinite]" />
                </div>
            </div>
        </section>
    );
}
