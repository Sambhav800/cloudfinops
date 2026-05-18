import { Skeleton } from "@/components/ui/skeleton";

export default function ForecastLoading() {
    return (
        <div className="min-h-screen">
            <div className="px-6 py-4">
                <Skeleton className="mb-2 h-8 w-40 bg-slate-800" />
                <Skeleton className="h-4 w-80 bg-slate-800" />
            </div>

            <div className="space-y-6 p-6">
                <div className="rounded-2xl border border-white/10 bg-slate-900/50 px-4 py-3 backdrop-blur-xl">
                    <Skeleton className="h-4 w-72 bg-slate-800" />
                </div>

                <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
                    {[1, 2, 3, 4].map((item) => (
                        <div
                            key={item}
                            className="rounded-2xl border border-white/10 bg-slate-900/50 p-6 backdrop-blur-xl shadow-2xl shadow-black/20"
                        >
                            <div className="flex items-start justify-between">
                                <div className="space-y-3">
                                    <Skeleton className="h-4 w-28 bg-slate-800" />
                                    <Skeleton className="h-10 w-32 bg-slate-700" />
                                </div>
                                <Skeleton className="h-11 w-11 rounded-xl bg-slate-800" />
                            </div>
                            <Skeleton className="mt-5 h-3 w-44 bg-slate-800" />
                        </div>
                    ))}
                </div>

                <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1.35fr_0.9fr]">
                    <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-6 backdrop-blur-xl shadow-2xl shadow-black/20">
                        <div className="mb-5 flex items-start justify-between gap-4">
                            <div className="space-y-2">
                                <Skeleton className="h-6 w-52 bg-slate-800" />
                                <Skeleton className="h-4 w-72 bg-slate-800" />
                            </div>
                            <Skeleton className="h-7 w-28 rounded-full bg-slate-800" />
                        </div>
                        <Skeleton className="h-80 w-full rounded-2xl bg-slate-800/70" />
                    </div>

                    <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-6 backdrop-blur-xl shadow-2xl shadow-black/20">
                        <div className="space-y-5">
                            <div className="space-y-2">
                                <Skeleton className="h-6 w-44 bg-slate-800" />
                                <Skeleton className="h-4 w-32 bg-slate-800" />
                            </div>
                            <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
                                <div className="flex items-center justify-between gap-3">
                                    <Skeleton className="h-4 w-40 bg-slate-800" />
                                    <Skeleton className="h-7 w-24 rounded-full bg-slate-800" />
                                </div>
                                <Skeleton className="mt-4 h-2 w-full rounded-full bg-slate-800" />
                                <div className="mt-3 flex items-center justify-between">
                                    <Skeleton className="h-3 w-24 bg-slate-800" />
                                    <Skeleton className="h-3 w-14 bg-slate-800" />
                                </div>
                            </div>
                            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                                {[1, 2].map((item) => (
                                    <div key={item} className="rounded-2xl border border-white/10 bg-black/20 p-4">
                                        <Skeleton className="h-3 w-20 bg-slate-800" />
                                        <Skeleton className="mt-3 h-6 w-28 bg-slate-800" />
                                    </div>
                                ))}
                            </div>
                            <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
                                <Skeleton className="h-4 w-full bg-slate-800" />
                                <Skeleton className="mt-2 h-4 w-5/6 bg-slate-800" />
                            </div>
                        </div>
                    </div>
                </div>

                <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1.15fr_1fr]">
                    <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-6 backdrop-blur-xl shadow-2xl shadow-black/20">
                        <div className="mb-5 space-y-2">
                            <Skeleton className="h-6 w-40 bg-slate-800" />
                            <Skeleton className="h-4 w-80 bg-slate-800" />
                        </div>
                        <Skeleton className="h-72 w-full rounded-2xl bg-slate-800/70" />
                    </div>

                    <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-6 backdrop-blur-xl shadow-2xl shadow-black/20">
                        <div className="mb-5 flex items-start justify-between gap-4">
                            <div className="space-y-2">
                                <Skeleton className="h-6 w-36 bg-slate-800" />
                                <Skeleton className="h-4 w-56 bg-slate-800" />
                            </div>
                            <Skeleton className="h-7 w-24 rounded-full bg-slate-800" />
                        </div>
                        <div className="space-y-3">
                            {[1, 2, 3].map((item) => (
                                <div key={item} className="rounded-2xl border border-white/10 bg-black/20 p-4">
                                    <div className="flex items-center justify-between gap-3">
                                        <div className="flex items-center gap-3">
                                            <Skeleton className="h-9 w-9 rounded-xl bg-slate-800" />
                                            <div className="space-y-2">
                                                <Skeleton className="h-4 w-16 bg-slate-800" />
                                                <Skeleton className="h-3 w-24 bg-slate-800" />
                                            </div>
                                        </div>
                                        <Skeleton className="h-6 w-20 rounded-full bg-slate-800" />
                                    </div>
                                    <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
                                        {[1, 2, 3].map((metric) => (
                                            <div key={metric} className="space-y-2">
                                                <Skeleton className="h-3 w-16 bg-slate-800" />
                                                <Skeleton className="h-4 w-20 bg-slate-800" />
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>

                <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-6 backdrop-blur-xl shadow-2xl shadow-black/20">
                    <div className="mb-5 flex items-start justify-between gap-4">
                        <div className="space-y-2">
                            <Skeleton className="h-6 w-44 bg-slate-800" />
                            <Skeleton className="h-4 w-72 bg-slate-800" />
                        </div>
                        <Skeleton className="h-9 w-28 rounded-xl bg-slate-800" />
                    </div>
                    <div className="overflow-hidden rounded-2xl border border-white/5">
                        <div className="grid grid-cols-7 gap-4 border-b border-white/10 bg-black/20 px-4 py-3">
                            {[1, 2, 3, 4, 5, 6, 7].map((item) => (
                                <Skeleton key={item} className="h-4 w-full bg-slate-800" />
                            ))}
                        </div>
                        {[1, 2, 3, 4].map((row) => (
                            <div key={row} className="grid grid-cols-7 gap-4 border-b border-white/5 px-4 py-4 last:border-b-0">
                                {[1, 2, 3, 4, 5, 6, 7].map((cell) => (
                                    <Skeleton
                                        key={cell}
                                        className={`h-4 ${cell === 7 ? "rounded-full" : ""} w-full bg-slate-800`}
                                    />
                                ))}
                            </div>
                        ))}
                    </div>
                </div>

                <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-6 backdrop-blur-xl shadow-2xl shadow-black/20">
                    <div className="mb-5 space-y-2">
                        <Skeleton className="h-6 w-48 bg-slate-800" />
                        <Skeleton className="h-4 w-80 bg-slate-800" />
                    </div>
                    <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                        {[1, 2, 3].map((item) => (
                            <div key={item} className="rounded-2xl border border-white/10 bg-black/20 p-4">
                                <Skeleton className="h-3 w-16 bg-slate-800" />
                                <Skeleton className="mt-3 h-5 w-24 bg-slate-800" />
                                <Skeleton className="mt-4 h-4 w-20 bg-slate-800" />
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
}
