export default function ApiIntelligenceLoading() {
    return (
        <div className="space-y-6 p-4 md:p-8 animate-pulse">
            <div className="flex items-center gap-3">
                <div className="h-8 w-8 rounded-lg bg-slate-800" />
                <div className="h-7 w-52 rounded-lg bg-slate-800" />
            </div>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                {[1, 2, 3, 4].map((i) => (
                    <div key={i} className="rounded-2xl border border-white/10 bg-slate-900/40 p-5">
                        <div className="h-3 w-20 rounded bg-slate-800" />
                        <div className="mt-3 h-8 w-16 rounded bg-slate-800" />
                        <div className="mt-2 h-3 w-28 rounded bg-slate-800" />
                    </div>
                ))}
            </div>
            <div className="h-16 rounded-2xl border border-white/10 bg-slate-900/40" />
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="h-72 rounded-2xl border border-white/10 bg-slate-900/40" />
                <div className="h-72 rounded-2xl border border-white/10 bg-slate-900/40" />
            </div>
            <div className="h-56 rounded-2xl border border-white/10 bg-slate-900/40" />
            <div className="h-80 rounded-2xl border border-white/10 bg-slate-900/40" />
        </div>
    );
}
