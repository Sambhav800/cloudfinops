import { Skeleton } from "@/components/ui/skeleton";

export default function DashboardLoading() {
    return (
        <main className="min-h-screen w-full bg-slate-950 p-6 md:p-10">
            <div className="mb-8 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
                <div>
                    <Skeleton className="mb-2 h-7 w-32 bg-slate-800" />
                    <Skeleton className="h-5 w-64 bg-slate-800" />
                </div>
                <Skeleton className="h-10 w-32 rounded-lg bg-slate-800" />
            </div>

            <div className="mb-8 space-y-4">
                <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
                    <div>
                        <Skeleton className="h-3 w-36 bg-slate-800" />
                        <Skeleton className="mt-3 h-7 w-64 bg-slate-800" />
                        <Skeleton className="mt-2 h-4 w-80 bg-slate-800" />
                    </div>
                    <Skeleton className="h-10 w-44 rounded-xl bg-slate-800" />
                </div>

                <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
                    {[1, 2, 3, 4].map((card) => (
                        <div
                            key={card}
                            className="rounded-2xl border border-white/10 bg-slate-900/50 p-5 backdrop-blur-xl"
                        >
                            <div className="flex items-start justify-between">
                                <div className="space-y-3">
                                    <Skeleton className="h-4 w-28 bg-slate-800" />
                                    <Skeleton className="h-10 w-36 bg-slate-700" />
                                </div>
                                <Skeleton className="h-11 w-11 rounded-xl bg-slate-800" />
                            </div>
                            <Skeleton className="mt-4 h-4 w-52 bg-slate-800" />
                            <Skeleton className="mt-3 h-3 w-40 bg-slate-800" />
                        </div>
                    ))}
                </div>
            </div>

            <div className="mb-8 grid grid-cols-1 gap-4 md:grid-cols-4">
                <div className="rounded-2xl border border-amber-500/20 bg-gradient-to-br from-amber-500/10 to-slate-900/50 p-5">
                    <div className="flex h-full flex-col items-center justify-center gap-4">
                        <Skeleton className="h-28 w-28 rounded-full bg-slate-800" />
                        <div className="space-y-2 text-center">
                            <Skeleton className="mx-auto h-3 w-24 bg-slate-800" />
                            <Skeleton className="mx-auto h-5 w-28 bg-slate-800" />
                        </div>
                    </div>
                </div>

                <div className="space-y-4 md:col-span-3">
                    <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                        {[1, 2, 3].map((card) => (
                            <div
                                key={card}
                                className="rounded-2xl border border-white/10 bg-slate-900/60 p-4 backdrop-blur-xl"
                            >
                                <div className="mb-2 flex items-center justify-between">
                                    <Skeleton className="h-4 w-28 bg-slate-800" />
                                    <Skeleton className="h-4 w-4 rounded-full bg-slate-800" />
                                </div>
                                <Skeleton className="mb-2 h-9 w-32 bg-slate-700" />
                                <Skeleton className="h-3 w-48 bg-slate-800" />
                            </div>
                        ))}
                    </div>

                    <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                        {[1, 2, 3].map((provider) => (
                            <div
                                key={provider}
                                className="rounded-2xl border border-white/10 bg-slate-900/40 p-4 backdrop-blur-xl"
                            >
                                <div className="mb-3 flex items-center justify-between">
                                    <div className="flex items-center gap-2">
                                        <Skeleton className="h-5 w-5 rounded-full bg-slate-800" />
                                        <Skeleton className="h-4 w-16 bg-slate-800" />
                                    </div>
                                    <Skeleton className="h-5 w-16 rounded-full bg-slate-800" />
                                </div>
                                <Skeleton className="mb-2 h-7 w-28 bg-slate-800" />
                                <Skeleton className="mb-2 h-3 w-28 bg-slate-800" />
                                <Skeleton className="h-1.5 w-full rounded-full bg-slate-800" />
                            </div>
                        ))}
                    </div>
                </div>
            </div>

            <div className="mb-8 grid grid-cols-1 gap-6 md:grid-cols-2 lg:grid-cols-4">
                {[1, 2, 3, 4].map((card) => (
                    <div
                        key={card}
                        className="rounded-2xl border border-white/10 bg-slate-900/50 p-6 backdrop-blur-xl"
                    >
                        <div className="mb-4 flex items-center gap-3">
                            <Skeleton className="h-10 w-10 rounded-xl bg-slate-800" />
                            <Skeleton className="h-5 w-32 bg-slate-800" />
                        </div>
                        <div className="space-y-3">
                            <Skeleton className="h-8 w-24 bg-slate-700" />
                            <Skeleton className="h-4 w-full bg-slate-800" />
                            <Skeleton className="h-4 w-5/6 bg-slate-800" />
                        </div>
                    </div>
                ))}
            </div>

            <div className="grid gap-8 lg:grid-cols-2">
                {[1, 2].map((panel) => (
                    <div
                        key={panel}
                        className="rounded-2xl border border-white/10 bg-slate-900/50 p-6 backdrop-blur-xl"
                    >
                        <div className="mb-6 flex items-center justify-between">
                            <div className="space-y-2">
                                <Skeleton className="h-6 w-44 bg-slate-800" />
                                <Skeleton className="h-4 w-36 bg-slate-800" />
                            </div>
                            <Skeleton className="h-6 w-14 rounded-full bg-slate-800" />
                        </div>
                        <Skeleton className="h-72 w-full rounded-2xl bg-slate-800/70" />
                    </div>
                ))}
            </div>

            <div className="mt-8">
                <div className="mb-6 flex items-center gap-3">
                    <Skeleton className="h-6 w-6 rounded-full bg-slate-800" />
                    <div>
                        <Skeleton className="mb-2 h-6 w-56 bg-slate-800" />
                        <Skeleton className="h-4 w-44 bg-slate-800" />
                    </div>
                </div>

                <div className="mb-6 flex w-fit flex-wrap gap-2 rounded-xl border border-white/10 bg-white/5 p-1">
                    {["All", "Zombie", "Shadow", "Orphaned"].map((tab, index) => (
                        <Skeleton
                            key={tab}
                            className={`h-9 rounded-lg ${index === 0 ? "w-28 bg-blue-500/20" : "w-32 bg-slate-800"}`}
                        />
                    ))}
                </div>

                <div className="overflow-hidden rounded-2xl border border-white/10 bg-slate-900/50 backdrop-blur-xl">
                    <div className="flex flex-col gap-4 border-b border-white/10 p-5 sm:flex-row sm:items-center sm:justify-between">
                        <Skeleton className="h-5 w-36 bg-slate-800" />
                        <Skeleton className="h-10 w-full max-w-xs rounded-lg bg-slate-800" />
                    </div>

                    <div className="p-5">
                        <div className="mb-4 rounded-lg border border-rose-500/10 bg-rose-500/5 p-3">
                            <Skeleton className="h-4 w-96 max-w-full bg-slate-800" />
                        </div>

                        <div className="overflow-x-auto rounded-xl border border-white/5">
                            <div className="grid grid-cols-7 gap-4 border-b border-white/10 bg-white/5 px-4 py-3">
                                {[1, 2, 3, 4, 5, 6, 7].map((column) => (
                                    <Skeleton key={column} className="h-4 w-full bg-slate-800" />
                                ))}
                            </div>

                            {[1, 2, 3, 4, 5].map((row) => (
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
        </main>
    );
}
