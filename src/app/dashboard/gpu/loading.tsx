export default function Loading() {
    return (
        <div className="space-y-6 p-4 md:p-8 animate-pulse">
            <div className="h-8 w-64 bg-white/10 rounded-lg" />
            <div className="h-4 w-80 bg-white/5 rounded" />
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                {[...Array(4)].map((_, i) => (
                    <div key={i} className="h-28 rounded-xl bg-white/5 border border-white/10" />
                ))}
            </div>
            <div className="h-24 rounded-xl bg-white/5 border border-white/10" />
            <div className="space-y-3">
                {[...Array(3)].map((_, i) => (
                    <div key={i} className="h-20 rounded-xl bg-white/5 border border-white/10" />
                ))}
            </div>
        </div>
    );
}
