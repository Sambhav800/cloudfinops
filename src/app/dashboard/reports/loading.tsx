import { Skeleton } from "@/components/ui/skeleton";

const reportCards = Array.from({ length: 4 }, (_, index) => index);
const reportRows = Array.from({ length: 4 }, (_, index) => index);
const surfaceClassName = "bg-slate-900/50 backdrop-blur-xl border border-white/10 rounded-2xl";

export default function ReportsLoading() {
    return (
        <div className="min-h-screen">
            <div className="px-6 py-4">
                <Skeleton className="mb-2 h-8 w-40 bg-slate-800" />
                <Skeleton className="h-4 w-72 bg-slate-800" />
            </div>

            <div className="space-y-6 p-6">
                <div className="flex flex-wrap gap-4">
                    <Skeleton className="h-11 w-40 rounded-lg bg-primary/20" />
                </div>

                <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
                    {reportCards.map((card) => (
                        <div key={card} className={`${surfaceClassName} p-5`}>
                            <Skeleton className="mb-4 h-10 w-10 rounded-xl bg-slate-800" />
                            <Skeleton className="mb-2 h-5 w-32 bg-slate-800" />
                            <Skeleton className="mb-1 h-4 w-full bg-slate-800" />
                            <Skeleton className="h-4 w-5/6 bg-slate-800" />
                        </div>
                    ))}
                </div>

                <div className={`${surfaceClassName} overflow-hidden`}>
                    <div className="border-b border-white/10 p-5">
                        <Skeleton className="mb-2 h-6 w-36 bg-slate-800" />
                        <Skeleton className="h-4 w-32 bg-slate-800" />
                    </div>

                    <div className="divide-y divide-white/5">
                        {reportRows.map((row) => (
                            <div
                                key={row}
                                className="flex flex-col gap-4 p-5 lg:flex-row lg:items-center lg:justify-between"
                            >
                                <div className="flex items-start gap-4">
                                    <Skeleton className="h-10 w-10 rounded-xl bg-slate-800" />
                                    <div className="space-y-3">
                                        <Skeleton className="h-5 w-56 bg-slate-800" />
                                        <div className="flex flex-wrap gap-3">
                                            <Skeleton className="h-4 w-28 bg-slate-800" />
                                            <Skeleton className="h-4 w-32 bg-slate-800" />
                                            <Skeleton className="h-4 w-16 bg-slate-800" />
                                        </div>
                                    </div>
                                </div>

                                <div className="flex flex-wrap items-center gap-2">
                                    <Skeleton className="h-7 w-20 rounded-full bg-slate-800" />
                                    <Skeleton className="h-8 w-16 rounded-lg bg-slate-800" />
                                    <Skeleton className="h-8 w-16 rounded-lg bg-slate-800" />
                                    <Skeleton className="h-9 w-9 rounded-lg bg-slate-800" />
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </div>
    );
}
