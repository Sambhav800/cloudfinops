import { Skeleton } from "@/components/ui/skeleton";

const stats = Array.from({ length: 3 }, (_, index) => index);
const categories = Array.from({ length: 4 }, (_, index) => index);
const opportunities = Array.from({ length: 3 }, (_, index) => index);
const surfaceClassName = "bg-slate-900/50 backdrop-blur-xl border border-white/10 rounded-2xl";

export default function ArbitrageLoading() {
    return (
        <div className="space-y-6 p-4 md:p-8">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                <div>
                    <Skeleton className="mb-2 h-8 w-60 bg-slate-800" />
                    <Skeleton className="h-4 w-80 bg-slate-800" />
                </div>
                <Skeleton className="h-8 w-40 rounded-full bg-slate-800" />
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                {stats.map((stat) => (
                    <div key={stat} className={`${surfaceClassName} p-5`}>
                        <Skeleton className="mb-2 h-4 w-32 bg-slate-800" />
                        <Skeleton className="mb-2 h-9 w-28 bg-slate-800" />
                        <Skeleton className="h-3 w-24 bg-slate-800" />
                    </div>
                ))}
            </div>

            <div className={`${surfaceClassName} p-5`}>
                <Skeleton className="mb-4 h-4 w-36 bg-slate-800" />
                <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                    {categories.map((category) => (
                        <div key={category} className="rounded-xl border border-white/5 bg-black/20 p-4">
                            <Skeleton className="mb-2 h-3 w-20 bg-slate-800" />
                            <Skeleton className="h-6 w-24 bg-slate-800" />
                        </div>
                    ))}
                </div>
            </div>

            <div className="grid gap-4 xl:grid-cols-2">
                {Array.from({ length: 2 }, (_, index) => (
                    <div key={index} className={`${surfaceClassName} p-5`}>
                        <Skeleton className="mb-3 h-5 w-40 bg-slate-800" />
                        <Skeleton className="mb-2 h-4 w-full bg-slate-800" />
                        <Skeleton className="h-4 w-5/6 bg-slate-800" />
                    </div>
                ))}
            </div>

            <div className="space-y-3">
                <Skeleton className="h-6 w-52 bg-slate-800" />
                {opportunities.map((opportunity) => (
                    <div key={opportunity} className={`${surfaceClassName} p-5`}>
                        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                            <div className="space-y-2">
                                <Skeleton className="h-5 w-40 bg-slate-800" />
                                <Skeleton className="h-4 w-32 bg-slate-800" />
                            </div>
                            <div className="space-y-2 lg:text-right">
                                <Skeleton className="h-5 w-28 bg-slate-800" />
                                <Skeleton className="h-4 w-20 bg-slate-800" />
                            </div>
                        </div>

                        <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
                            {Array.from({ length: 2 }, (_, index) => (
                                <div
                                    key={index}
                                    className="rounded-xl border border-white/10 bg-black/20 p-4"
                                >
                                    <Skeleton className="mb-2 h-3 w-24 bg-slate-800" />
                                    <Skeleton className="h-5 w-20 bg-slate-800" />
                                </div>
                            ))}
                        </div>

                        <Skeleton className="mt-4 h-4 w-full bg-slate-800" />
                        <Skeleton className="mt-2 h-6 w-20 rounded-full bg-slate-800" />
                    </div>
                ))}
            </div>
        </div>
    );
}
