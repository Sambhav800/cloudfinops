import { Skeleton } from "@/components/ui/skeleton";

const tabs = Array.from({ length: 2 }, (_, index) => index);
const financeCards = Array.from({ length: 2 }, (_, index) => index);
const accountRows = Array.from({ length: 3 }, (_, index) => index);
const surfaceClassName = "bg-slate-900/50 backdrop-blur-xl border border-white/10 rounded-2xl";

export default function SettingsLoading() {
    return (
        <div className="min-h-screen p-6">
            <div className="flex flex-col gap-6 lg:flex-row">
                <div className="lg:w-64 lg:flex-shrink-0">
                    <nav className={`${surfaceClassName} space-y-1 p-2`}>
                        {tabs.map((tab) => (
                            <div
                                key={tab}
                                className={`flex items-center gap-3 rounded-xl px-4 py-3 ${tab === 0 ? "bg-primary/15" : ""}`}
                            >
                                <Skeleton className="h-5 w-5 rounded-lg bg-slate-800" />
                                <Skeleton className="h-4 w-28 bg-slate-800" />
                            </div>
                        ))}
                    </nav>
                </div>

                <div className="flex-1">
                    <div className={`${surfaceClassName} p-6`}>
                        <div className="mb-6">
                            <Skeleton className="mb-2 h-7 w-48 bg-slate-800" />
                            <Skeleton className="h-4 w-80 bg-slate-800" />
                        </div>

                        <div className="grid gap-6 xl:grid-cols-[1.35fr_1fr]">
                            {financeCards.map((card) => (
                                <div key={card} className="rounded-2xl border border-white/5 bg-black/20 p-5">
                                    <Skeleton className="mb-3 h-6 w-40 bg-slate-800" />
                                    <Skeleton className="mb-2 h-4 w-full bg-slate-800" />
                                    <Skeleton className="mb-5 h-4 w-5/6 bg-slate-800" />
                                    <div className="space-y-4">
                                        <Skeleton className="h-4 w-32 bg-slate-800" />
                                        <Skeleton className="h-12 w-full rounded-xl bg-slate-800" />
                                        <Skeleton className="h-4 w-28 bg-slate-800" />
                                        <Skeleton className="h-12 w-full rounded-xl bg-slate-800" />
                                    </div>
                                </div>
                            ))}
                        </div>

                        <div className="mt-6 rounded-2xl border border-white/5 bg-black/20 p-5">
                            <Skeleton className="mb-3 h-6 w-44 bg-slate-800" />
                            <Skeleton className="mb-2 h-4 w-full bg-slate-800" />
                            <Skeleton className="mb-5 h-4 w-2/3 bg-slate-800" />
                            <div className="grid gap-4 md:grid-cols-2">
                                <Skeleton className="h-12 w-full rounded-xl bg-slate-800" />
                                <Skeleton className="h-12 w-full rounded-xl bg-slate-800" />
                            </div>
                        </div>

                        <div className="mt-8 flex justify-end">
                            <Skeleton className="h-11 w-44 rounded-xl bg-primary/20" />
                        </div>

                        <div className="mt-10 space-y-3">
                            {accountRows.map((row) => (
                                <div
                                    key={row}
                                    className="flex flex-col gap-4 rounded-2xl border border-white/5 bg-black/30 p-4 lg:flex-row lg:items-center lg:justify-between"
                                >
                                    <div className="flex items-start gap-4">
                                        <Skeleton className="h-8 w-16 rounded-full bg-slate-800" />
                                        <div className="space-y-2">
                                            <Skeleton className="h-5 w-40 bg-slate-800" />
                                            <Skeleton className="h-4 w-48 bg-slate-800" />
                                            <div className="flex gap-2">
                                                <Skeleton className="h-6 w-24 rounded-full bg-slate-800" />
                                                <Skeleton className="h-6 w-28 rounded-full bg-slate-800" />
                                                <Skeleton className="h-6 w-24 rounded-full bg-slate-800" />
                                            </div>
                                        </div>
                                    </div>

                                    <div className="flex items-center gap-4">
                                        <div className="space-y-2 text-right">
                                            <Skeleton className="ml-auto h-6 w-20 rounded-full bg-slate-800" />
                                            <Skeleton className="ml-auto h-3 w-28 bg-slate-800" />
                                        </div>
                                        <Skeleton className="h-9 w-9 rounded-lg bg-slate-800" />
                                        <Skeleton className="h-9 w-9 rounded-lg bg-slate-800" />
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
