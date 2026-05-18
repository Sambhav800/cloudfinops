export default function Loading() {
    return (
        <main className="animate-pulse px-4 py-8 md:px-8 lg:px-12">
            <div className="flex flex-col gap-8 lg:flex-row lg:items-end lg:justify-between">
                <div>
                    <div className="h-3 w-36 rounded bg-slate-800/70" />
                    <div className="mt-4 h-7 w-72 rounded bg-slate-800/60" />
                    <div className="mt-3 h-4 w-full max-w-prose rounded bg-slate-800/40" />
                </div>
                <div className="grid w-full grid-cols-1 gap-6 sm:grid-cols-3 lg:max-w-2xl">
                    {[1, 2, 3].map((item) => (
                        <div key={item} className="h-20 rounded-lg bg-slate-900/20" />
                    ))}
                </div>
            </div>

            <div className="mt-16 grid grid-cols-1 gap-6 xl:grid-cols-2">
                <div className="h-[360px] rounded-xl bg-slate-900/20" />
                <div className="h-[360px] rounded-xl bg-slate-900/20" />
            </div>

            <div className="mt-16 grid grid-cols-1 gap-6 xl:grid-cols-[0.95fr_1.05fr]">
                <div className="h-[340px] rounded-xl bg-slate-900/20" />
                <div className="h-[340px] rounded-xl bg-slate-900/20" />
            </div>

            <div className="mt-16 overflow-hidden rounded-xl bg-slate-900/20">
                <div className="h-11 bg-slate-800/30" />
                {[1, 2, 3, 4, 5].map((item) => (
                    <div key={item} className="h-14 border-b border-white/5" />
                ))}
            </div>
        </main>
    );
}
