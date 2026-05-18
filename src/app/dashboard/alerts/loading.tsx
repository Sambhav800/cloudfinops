import { Skeleton } from "@/components/ui/skeleton";

export default function AlertsLoading() {
    return (
        <div className="min-h-screen">
            <div className="px-6 py-4">
                <Skeleton className="mb-2 h-8 w-24 bg-slate-800" />
                <Skeleton className="h-4 w-48 bg-slate-800" />
            </div>

            <div className="p-6 space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                    {[1, 2, 3, 4].map((i) => (
                        <div key={i} className="rounded-2xl border border-white/10 bg-slate-900/50 p-4 backdrop-blur-xl">
                            <Skeleton className="h-4 w-20 bg-slate-800 mb-2" />
                            <Skeleton className="h-8 w-12 bg-slate-700" />
                        </div>
                    ))}
                </div>

                <div className="flex flex-wrap gap-4 items-center justify-between">
                    <div className="flex gap-2">
                        {[1, 2, 3, 4, 5].map((i) => (
                            <Skeleton key={i} className="h-10 w-24 rounded-lg bg-slate-800" />
                        ))}
                    </div>
                    <Skeleton className="h-10 w-32 rounded-lg bg-slate-800" />
                </div>

                <div className="space-y-3">
                    {[1, 2, 3, 4, 5, 6].map((i) => (
                        <div
                            key={i}
                            className="rounded-2xl border border-white/10 bg-slate-900/50 p-4 backdrop-blur-xl"
                        >
                            <div className="flex items-start gap-4">
                                <Skeleton className="h-10 w-10 shrink-0 rounded-xl bg-slate-800" />

                                <div className="min-w-0 flex-1">
                                    <div className="mb-2 flex items-center gap-2">
                                        <Skeleton className="h-5 w-56 bg-slate-800" />
                                        <Skeleton className="h-2 w-2 rounded-full bg-primary/40" />
                                    </div>

                                    <div className="mb-3 space-y-2">
                                        <Skeleton className="h-4 w-full max-w-2xl bg-slate-800" />
                                        <Skeleton className="h-4 w-4/5 bg-slate-800" />
                                    </div>

                                    <div className="flex flex-wrap items-center gap-3">
                                        <Skeleton className="h-4 w-24 bg-slate-800" />
                                        <Skeleton className="h-6 w-20 rounded-full bg-slate-800" />
                                        <Skeleton className="h-6 w-16 rounded-full bg-slate-800" />
                                    </div>
                                </div>

                                <div className="flex gap-2">
                                    <Skeleton className="h-9 w-9 rounded-lg bg-slate-800" />
                                    <Skeleton className="h-9 w-9 rounded-lg bg-slate-800" />
                                    <Skeleton className="h-9 w-9 rounded-lg bg-slate-800" />
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}
