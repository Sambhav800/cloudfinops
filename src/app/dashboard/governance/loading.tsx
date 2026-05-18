import { Skeleton } from "@/components/ui/skeleton";

export default function GovernanceLoading() {
    return (
        <div className="min-h-screen">
            <div className="px-6 py-4">
                <Skeleton className="h-8 w-64 bg-slate-800 mb-2" />
                <Skeleton className="h-4 w-96 bg-slate-800" />
            </div>

            <div className="p-6 space-y-8">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-6">
                        <div className="flex justify-between items-center mb-4">
                            <Skeleton className="h-6 w-36 bg-slate-800" />
                            <Skeleton className="h-6 w-6 rounded-full bg-slate-800" />
                        </div>
                        <div className="flex items-end gap-4">
                            <Skeleton className="h-12 w-20 bg-slate-800" />
                            <div className="space-y-2 mb-1">
                                <Skeleton className="h-4 w-12 bg-slate-800" />
                                <Skeleton className="h-5 w-16 bg-slate-800 rounded-full" />
                            </div>
                        </div>
                        <Skeleton className="h-4 w-32 bg-slate-800 mt-4" />
                    </div>

                    <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-6">
                        <div className="flex justify-between items-center mb-4">
                            <Skeleton className="h-6 w-32 bg-slate-800" />
                            <Skeleton className="h-6 w-6 rounded-full bg-slate-800" />
                        </div>
                        <div className="space-y-4">
                            <div className="flex justify-between">
                                <Skeleton className="h-4 w-24 bg-slate-800" />
                                <Skeleton className="h-4 w-20 bg-slate-800" />
                            </div>
                            <Skeleton className="h-2 w-full bg-slate-800 rounded-full" />
                            <div className="flex justify-between">
                                <Skeleton className="h-3 w-24 bg-slate-800" />
                                <Skeleton className="h-3 w-16 bg-slate-800" />
                            </div>
                        </div>
                    </div>

                    <div className="rounded-2xl border border-white/10 bg-slate-900/50 p-6">
                        <div className="flex justify-between items-center mb-4">
                            <Skeleton className="h-6 w-32 bg-slate-800" />
                            <Skeleton className="h-6 w-6 rounded-full bg-slate-800" />
                        </div>
                        <div className="flex flex-col justify-between h-[120px]">
                            <div className="space-y-2">
                                <Skeleton className="h-10 w-32 bg-slate-800" />
                                <Skeleton className="h-4 w-48 bg-slate-800" />
                            </div>
                            <Skeleton className="h-6 w-32 bg-slate-800 rounded-lg" />
                        </div>
                    </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                    {[1, 2, 3, 4].map((i) => (
                        <div key={i} className="rounded-2xl border border-white/10 bg-slate-900/50 p-6">
                            <div className="flex items-center gap-3 mb-6">
                                <Skeleton className="h-10 w-10 rounded-lg bg-slate-800" />
                                <div className="space-y-2">
                                    <Skeleton className="h-6 w-48 bg-slate-800" />
                                    <Skeleton className="h-3 w-32 bg-slate-800" />
                                </div>
                            </div>

                            <div className="space-y-4">
                                {[1, 2, 3].map((row) => (
                                    <div key={row} className="flex justify-between items-center p-3 rounded-lg border border-slate-800/60 bg-slate-900/30">
                                        <div className="flex items-center gap-3">
                                            <Skeleton className="h-8 w-8 rounded-full bg-slate-800" />
                                            <Skeleton className="h-4 w-32 bg-slate-800" />
                                        </div>
                                        <Skeleton className="h-4 w-16 bg-slate-800" />
                                    </div>
                                ))}
                            </div>
                        </div>
                    ))}
                </div>

                <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
                    {[1, 2].map((panel) => (
                        <div
                            key={panel}
                            className="rounded-2xl border border-white/10 bg-slate-900/50 p-6"
                        >
                            <div className="mb-6 flex items-center gap-3">
                                <Skeleton className="h-10 w-10 rounded-lg bg-slate-800" />
                                <div className="space-y-2">
                                    <Skeleton className="h-5 w-44 bg-slate-800" />
                                    <Skeleton className="h-4 w-40 bg-slate-800" />
                                </div>
                            </div>
                            {panel === 1 ? (
                                <div className="space-y-3">
                                    <div className="flex h-24 items-end gap-2">
                                        {Array.from({ length: 7 }, (_, index) => (
                                            <Skeleton
                                                key={index}
                                                className="w-full rounded-t-sm bg-slate-800"
                                                style={{ height: `${36 + (index % 4) * 16}px` }}
                                            />
                                        ))}
                                    </div>
                                    <Skeleton className="h-4 w-48 bg-slate-800" />
                                </div>
                            ) : (
                                <div className="space-y-4">
                                    {Array.from({ length: 4 }, (_, index) => (
                                        <div key={index} className="space-y-2">
                                            <div className="flex items-center justify-between">
                                                <Skeleton className="h-4 w-32 bg-slate-800" />
                                                <Skeleton className="h-4 w-16 bg-slate-800" />
                                            </div>
                                            <Skeleton className="h-2 w-full rounded-full bg-slate-800" />
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    ))}
                </div>

                <div className="overflow-hidden rounded-2xl border border-white/10 bg-slate-900/50">
                    <div className="flex items-center gap-3 border-b border-white/10 p-6">
                        <Skeleton className="h-10 w-10 rounded-lg bg-slate-800" />
                        <div className="space-y-2">
                            <Skeleton className="h-5 w-64 bg-slate-800" />
                            <Skeleton className="h-4 w-72 bg-slate-800" />
                        </div>
                    </div>

                    <div className="grid grid-cols-[1.1fr_0.8fr_0.8fr_1.5fr_1fr] gap-4 border-b border-white/10 bg-white/5 px-4 py-3">
                        {[1, 2, 3, 4, 5].map((column) => (
                            <Skeleton key={column} className="h-4 w-full bg-slate-800" />
                        ))}
                    </div>

                    <div className="divide-y divide-white/5">
                        {Array.from({ length: 5 }, (_, row) => (
                            <div key={row} className="grid grid-cols-[1.1fr_0.8fr_0.8fr_1.5fr_1fr] gap-4 px-4 py-4">
                                <Skeleton className="h-4 w-40 bg-slate-800" />
                                <Skeleton className="h-6 w-20 rounded-full bg-slate-800" />
                                <Skeleton className="h-6 w-16 rounded-full bg-slate-800" />
                                <Skeleton className="h-4 w-full bg-slate-800" />
                                <Skeleton className="h-6 w-24 rounded-md bg-slate-800" />
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
}
