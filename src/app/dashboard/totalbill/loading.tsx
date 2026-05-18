import { Skeleton } from "@/components/ui/skeleton";

export default function TotalBillLoading() {
    return (
        <div className="min-h-screen bg-slate-950 px-4 py-8 text-slate-200 md:px-8 lg:px-12">
            <div className="mx-auto max-w-7xl space-y-12">
                <section className="flex flex-col gap-8 lg:flex-row lg:items-end lg:justify-between">
                    <div>
                        <Skeleton className="h-7 w-48 bg-slate-800/70" />
                        <Skeleton className="mt-3 h-12 w-64 bg-slate-700/80" />
                        <Skeleton className="mt-3 h-4 w-96 max-w-full bg-slate-800/60" />
                    </div>

                    <div className="grid gap-6 sm:grid-cols-3 lg:min-w-[480px]">
                        {[1, 2, 3].map((item) => (
                            <div key={item} className="h-16 rounded-lg bg-slate-800/50 p-3">
                                <div className="flex items-center gap-2">
                                    <Skeleton className="h-4 w-4 rounded bg-slate-700/80" />
                                    <Skeleton className="h-3 w-20 bg-slate-700/70" />
                                </div>
                                <Skeleton className="mt-3 h-5 w-24 bg-slate-700/80" />
                            </div>
                        ))}
                    </div>
                </section>

                <section className="space-y-3">
                    <div className="flex items-center justify-between gap-4">
                        <Skeleton className="h-3 w-28 bg-slate-800/70" />
                        <Skeleton className="h-3 w-40 bg-slate-800/50" />
                    </div>
                    <Skeleton className="h-2 w-full rounded-full bg-slate-800" />
                </section>

                <section className="space-y-4">
                    <Skeleton className="h-4 w-32 bg-slate-800/70" />
                    <div className="h-[320px] rounded-xl bg-slate-900/20 p-4">
                        <Skeleton className="h-full w-full rounded-lg bg-slate-800/40" />
                    </div>
                </section>

                <section className="grid gap-6 xl:grid-cols-2">
                    {[1, 2].map((item) => (
                        <div key={item} className="space-y-4">
                            <Skeleton className="h-4 w-40 bg-slate-800/70" />
                            <div className="h-[320px] rounded-xl bg-slate-900/20 p-4">
                                <Skeleton className="h-full w-full rounded-lg bg-slate-800/40" />
                            </div>
                        </div>
                    ))}
                </section>

                <section className="space-y-4">
                    <Skeleton className="h-4 w-36 bg-slate-800/70" />
                    <div className="grid grid-cols-7 gap-2">
                        {Array.from({ length: 35 }, (_, index) => (
                            <Skeleton key={index} className="h-8 w-8 rounded-md bg-slate-800/60" />
                        ))}
                    </div>
                </section>

                <section className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
                    {[1, 2, 3].map((item) => (
                        <div key={item} className="h-32 rounded-xl bg-slate-900/20 p-5">
                            <div className="flex items-center gap-3">
                                <Skeleton className="h-6 w-6 rounded-full bg-slate-800/70" />
                                <Skeleton className="h-4 w-20 bg-slate-800/70" />
                            </div>
                            <Skeleton className="mt-4 h-7 w-32 bg-slate-700/70" />
                            <div className="mt-4 grid grid-cols-3 gap-4">
                                {[1, 2, 3].map((metric) => (
                                    <Skeleton key={metric} className="h-4 w-full bg-slate-800/50" />
                                ))}
                            </div>
                        </div>
                    ))}
                </section>

                <section className="space-y-0 overflow-hidden rounded-xl bg-slate-900/20">
                    <div className="grid h-10 grid-cols-5 gap-4 border-b border-white/5 bg-slate-900/30 px-4 py-3">
                        {[1, 2, 3, 4, 5].map((col) => (
                            <Skeleton key={col} className="h-3 w-full bg-slate-800/70" />
                        ))}
                    </div>
                    {[1, 2, 3, 4].map((row) => (
                        <div key={row} className="grid h-12 grid-cols-5 gap-4 border-b border-white/5 px-4 py-3 last:border-b-0">
                            {[1, 2, 3, 4, 5].map((cell) => (
                                <Skeleton key={cell} className="h-3 w-full bg-slate-800/50" />
                            ))}
                        </div>
                    ))}
                </section>

                <section className="flex gap-4 rounded-lg bg-indigo-500/5 p-4">
                    <Skeleton className="h-8 w-8 rounded-full bg-indigo-500/20" />
                    <div className="flex-1 space-y-2">
                        <Skeleton className="h-4 w-48 bg-slate-800/70" />
                        <Skeleton className="h-4 w-full max-w-2xl bg-slate-800/50" />
                    </div>
                </section>
            </div>
        </div>
    );
}
