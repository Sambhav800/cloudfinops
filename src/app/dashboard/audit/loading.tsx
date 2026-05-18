import { Skeleton } from "@/components/ui/skeleton";

const rows = Array.from({ length: 6 }, (_, index) => index);
const surfaceClassName = "bg-slate-900/50 backdrop-blur-xl border border-white/10 rounded-2xl";

export default function AuditLoading() {
    return (
        <div className="mx-auto flex w-full max-w-7xl flex-col gap-6 p-6 pb-20">
            <div className="space-y-2">
                <Skeleton className="h-9 w-64 bg-slate-800" />
                <Skeleton className="h-4 w-[32rem] max-w-full bg-slate-800" />
            </div>

            <div className={`${surfaceClassName} overflow-hidden`}>
                <div className="border-b border-white/10 p-6">
                    <Skeleton className="mb-2 h-6 w-36 bg-slate-800" />
                    <Skeleton className="h-4 w-56 bg-slate-800" />
                </div>

                <div className="border-b border-white/5 bg-black/10 px-6 py-4">
                    <div className="grid grid-cols-[1.1fr_1fr_1fr_1.2fr] gap-4">
                        {Array.from({ length: 4 }, (_, index) => (
                            <Skeleton key={index} className="h-4 w-full bg-slate-800" />
                        ))}
                    </div>
                </div>

                <div className="divide-y divide-white/5">
                    {rows.map((row) => (
                        <div key={row} className="grid grid-cols-[1.1fr_1fr_1fr_1.2fr] gap-4 px-6 py-4">
                            <Skeleton className="h-4 w-32 bg-slate-800" />
                            <div className="flex items-center gap-2">
                                <Skeleton className="h-8 w-8 rounded-lg bg-slate-800" />
                                <Skeleton className="h-6 w-28 rounded-full bg-slate-800" />
                            </div>
                            <Skeleton className="h-4 w-40 bg-slate-800" />
                            <Skeleton className="h-4 w-full bg-slate-800" />
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}
