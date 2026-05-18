import { Skeleton } from "@/components/ui/skeleton";

const stats = Array.from({ length: 4 }, (_, index) => index);
const severities = Array.from({ length: 3 }, (_, index) => index);
const filters = Array.from({ length: 4 }, (_, index) => index);
const actions = Array.from({ length: 3 }, (_, index) => index);
const surfaceClassName = "bg-slate-900/50 backdrop-blur-xl border border-white/10 rounded-2xl";

export default function PendingActionsLoading() {
    return (
        <div className="min-h-screen">
            <div className="px-6 py-4">
                <Skeleton className="mb-2 h-8 w-52 bg-slate-800" />
                <Skeleton className="h-4 w-72 bg-slate-800" />
            </div>

            <div className="space-y-6 p-6">
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
                    {stats.map((stat) => (
                        <div key={stat} className={`${surfaceClassName} p-4`}>
                            <Skeleton className="mb-2 h-4 w-28 bg-slate-800" />
                            <Skeleton className="mb-2 h-9 w-16 bg-slate-700" />
                            <Skeleton className="h-3 w-24 bg-slate-800" />
                        </div>
                    ))}
                </div>

                <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                    {severities.map((severity) => (
                        <div
                            key={severity}
                            className="flex items-center gap-3 rounded-2xl border border-white/10 bg-slate-900/40 p-4"
                        >
                            <Skeleton className="h-10 w-10 rounded-xl bg-slate-800" />
                            <div className="space-y-2">
                                <Skeleton className="h-6 w-12 bg-slate-800" />
                                <Skeleton className="h-3 w-20 bg-slate-800" />
                            </div>
                        </div>
                    ))}
                </div>

                <div className="flex flex-wrap gap-2">
                    {filters.map((filter) => (
                        <Skeleton
                            key={filter}
                            className={`h-10 rounded-lg ${filter === 0 ? "w-20 bg-primary/20" : "w-24 bg-slate-800"}`}
                        />
                    ))}
                </div>

                <div className="space-y-4">
                    {actions.map((action) => (
                        <div key={action} className={`${surfaceClassName} p-6`}>
                            <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
                                <div className="flex flex-1 items-start gap-4">
                                    <Skeleton className="h-12 w-12 rounded-2xl bg-slate-800" />
                                    <div className="w-full space-y-3">
                                        <div className="flex flex-wrap items-center gap-2">
                                            <Skeleton className="h-5 w-48 bg-slate-800" />
                                            <Skeleton className="h-6 w-20 rounded-full bg-slate-800" />
                                        </div>
                                        <Skeleton className="h-4 w-full max-w-2xl bg-slate-800" />
                                        <div className="flex flex-wrap gap-4">
                                            <Skeleton className="h-4 w-40 bg-slate-800" />
                                            <Skeleton className="h-4 w-36 bg-slate-800" />
                                            <Skeleton className="h-4 w-28 bg-slate-800" />
                                        </div>
                                    </div>
                                </div>

                                <div className="flex flex-col gap-4 xl:items-end">
                                    <div className="space-y-2 xl:text-right">
                                        <Skeleton className="h-3 w-20 bg-slate-800" />
                                        <Skeleton className="h-8 w-28 bg-slate-800" />
                                    </div>
                                    <div className="flex flex-wrap gap-2">
                                        <Skeleton className="h-10 w-32 rounded-lg bg-slate-800" />
                                        <Skeleton className="h-10 w-24 rounded-lg bg-slate-800" />
                                        <Skeleton className="h-10 w-24 rounded-lg bg-slate-800" />
                                    </div>
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}
