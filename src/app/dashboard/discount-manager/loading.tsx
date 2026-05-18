import { Skeleton } from "@/components/ui/skeleton";

export default function DiscountManagerLoading() {
    return (
        <main className="p-6 md:p-10 w-full bg-slate-950 min-h-screen text-slate-200">
            <div className="mb-8">
                <Skeleton className="h-9 w-72 bg-slate-800 mb-3" />
                <Skeleton className="h-5 w-96 bg-slate-800" />
            </div>
            <div className="flex gap-2 mb-8">
                {[1, 2, 3, 4].map((i) => (
                    <Skeleton key={i} className="h-10 w-32 bg-slate-800 rounded-lg" />
                ))}
            </div>
            <div className="grid grid-cols-1 md:grid-cols-5 gap-4 mb-8">
                {[1, 2, 3, 4, 5].map((i) => (
                    <Skeleton key={i} className="h-24 bg-slate-800 rounded-2xl" />
                ))}
            </div>
            <Skeleton className="h-96 bg-slate-800 rounded-2xl" />
        </main>
    );
}
