import { Skeleton } from "@/components/ui/skeleton";

export default function ResourcesLoading() {
    return (
        <div className="min-h-screen">
            <div className="px-6 py-4">
                <Skeleton className="h-8 w-40 bg-slate-800 mb-2" />
                <Skeleton className="h-4 w-64 bg-slate-800" />
            </div>

            <div className="p-6 space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                    {[1, 2, 3, 4].map((i) => (
                        <div key={i} className="rounded-2xl border border-white/10 bg-slate-900/50 p-4 backdrop-blur-xl">
                            <Skeleton className="h-4 w-32 bg-slate-800 mb-2" />
                            <Skeleton className="h-8 w-16 bg-slate-700" />
                        </div>
                    ))}
                </div>

                <div className="overflow-hidden rounded-2xl border border-white/10 bg-slate-900/50 backdrop-blur-xl">
                    <div className="flex flex-col gap-4 border-b border-white/10 p-5 sm:flex-row sm:items-center sm:justify-between">
                        <Skeleton className="h-5 w-40 bg-slate-800" />
                        <Skeleton className="h-10 w-full max-w-xs rounded-lg bg-slate-800" />
                    </div>

                    <div className="px-5 pt-4">
                        <div className="flex w-fit flex-wrap gap-2 rounded-xl border border-white/10 bg-white/5 p-1">
                            {[1, 2, 3, 4].map((tab) => (
                                <Skeleton
                                    key={tab}
                                    className={`h-9 rounded-lg ${tab === 1 ? "w-28 bg-blue-500/20" : "w-32 bg-slate-800"}`}
                                />
                            ))}
                        </div>
                    </div>

                    <div className="p-5">
                        <div className="mb-4 flex items-center gap-3 rounded-lg border border-rose-500/10 bg-rose-500/5 p-3">
                            <Skeleton className="h-4 w-4 rounded-full bg-slate-800" />
                            <Skeleton className="h-4 w-96 max-w-full bg-slate-800" />
                        </div>

                        <div className="overflow-x-auto rounded-xl border border-white/5">
                            <div className="grid grid-cols-7 gap-4 border-b border-white/10 bg-white/5 px-4 py-3">
                                {[1, 2, 3, 4, 5, 6, 7].map((column) => (
                                    <Skeleton key={column} className="h-4 w-full bg-slate-800" />
                                ))}
                            </div>

                            {[1, 2, 3, 4, 5, 6].map((row) => (
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
                </div>
            </div>
        </div>
    );
}
