import { Skeleton } from "@/components/ui/skeleton";

const railItems = Array.from({ length: 5 }, (_, index) => index);
const coverageRows = Array.from({ length: 3 }, (_, index) => index);
const tableRows = Array.from({ length: 5 }, (_, index) => index);
const surfaceClassName = "bg-slate-900/50 backdrop-blur-xl border border-white/10 rounded-2xl";

export default function ArchitectureLoading() {
    return (
        <main className="min-h-screen w-full bg-slate-950 p-6 text-slate-200 md:p-10">
            <div className="mb-6 flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
                <div>
                    <Skeleton className="mb-2 h-8 w-60 bg-slate-800" />
                    <Skeleton className="h-4 w-80 bg-slate-800" />
                </div>
            </div>

            <div className={`${surfaceClassName} p-4`}>
                <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
                    <div className="space-y-2">
                        <Skeleton className="h-6 w-52 bg-slate-800" />
                        <Skeleton className="h-4 w-40 bg-slate-800" />
                    </div>
                    <div className="flex flex-wrap gap-3">
                        <Skeleton className="h-10 w-40 rounded-xl bg-slate-800" />
                        <Skeleton className="h-10 w-36 rounded-xl bg-slate-800" />
                    </div>
                </div>

                <div className="mt-4 flex flex-wrap gap-3">
                    {coverageRows.map((row) => (
                        <div
                            key={row}
                            className="rounded-xl border border-white/10 bg-black/20 px-4 py-3"
                        >
                            <Skeleton className="mb-2 h-3 w-20 bg-slate-800" />
                            <Skeleton className="h-4 w-28 bg-slate-800" />
                        </div>
                    ))}
                </div>
            </div>

            <div className="mt-3 flex flex-col gap-0 overflow-hidden rounded-2xl border border-white/5 bg-slate-900/30 xl:flex-row">
                <div className="border-b border-white/5 p-4 xl:w-64 xl:border-b-0 xl:border-r">
                    <Skeleton className="mb-4 h-4 w-24 bg-slate-800" />
                    <div className="space-y-2">
                        {railItems.map((item) => (
                            <div key={item} className="rounded-xl border border-white/5 bg-black/20 p-3">
                                <Skeleton className="mb-2 h-4 w-28 bg-slate-800" />
                                <Skeleton className="h-3 w-20 bg-slate-800" />
                            </div>
                        ))}
                    </div>
                </div>

                <div className="flex-1 border-b border-white/5 p-4 xl:border-b-0 xl:border-r">
                    <div className="mb-4 flex flex-wrap gap-2">
                        <Skeleton className="h-9 w-28 rounded-lg bg-slate-800" />
                        <Skeleton className="h-9 w-24 rounded-lg bg-slate-800" />
                        <Skeleton className="h-9 w-32 rounded-lg bg-slate-800" />
                    </div>
                    <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
                        <Skeleton className="h-[420px] w-full rounded-2xl bg-slate-800/70" />
                    </div>
                </div>

                <div className="p-4 xl:w-80">
                    <Skeleton className="mb-4 h-5 w-32 bg-slate-800" />
                    <div className="space-y-3">
                        {Array.from({ length: 4 }, (_, index) => (
                            <div
                                key={index}
                                className="rounded-xl border border-white/5 bg-black/20 p-4"
                            >
                                <Skeleton className="mb-2 h-4 w-24 bg-slate-800" />
                                <Skeleton className="mb-2 h-4 w-full bg-slate-800" />
                                <Skeleton className="h-4 w-5/6 bg-slate-800" />
                            </div>
                        ))}
                    </div>
                </div>
            </div>

            <div className={`${surfaceClassName} mt-4 overflow-hidden`}>
                <div className="border-b border-white/10 p-4">
                    <Skeleton className="mb-2 h-5 w-40 bg-slate-800" />
                    <Skeleton className="h-4 w-64 bg-slate-800" />
                </div>
                <div className="grid grid-cols-[1.2fr_repeat(3,minmax(0,1fr))] gap-4 border-b border-white/5 px-4 py-3">
                    {Array.from({ length: 4 }, (_, index) => (
                        <Skeleton key={index} className="h-4 w-full bg-slate-800" />
                    ))}
                </div>
                <div className="divide-y divide-white/5">
                    {tableRows.map((row) => (
                        <div key={row} className="grid grid-cols-[1.2fr_repeat(3,minmax(0,1fr))] gap-4 px-4 py-4">
                            {Array.from({ length: 4 }, (_, index) => (
                                <Skeleton key={index} className="h-4 w-full bg-slate-800" />
                            ))}
                        </div>
                    ))}
                </div>
            </div>
        </main>
    );
}
