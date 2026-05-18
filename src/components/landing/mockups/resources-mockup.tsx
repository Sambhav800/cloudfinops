const resources = [
    { provider: "#FF9900", name: "i-0a3b21ef4cc", cost: "₹69.9K/mo" },
    { provider: "#4285F4", name: "prod-db-primary", cost: "₹51.5K/mo" },
    { provider: "#0078D4", name: "vm-worker-eu-1", cost: "₹34K/mo" },
    { provider: "#FF9900", name: "s3-archive-2024", cost: "₹23.7K/mo" },
    { provider: "#4285F4", name: "gke-cluster-west", cost: "₹1.03L/mo" },
    { provider: "#0078D4", name: "sql-analytics-01", cost: "₹59.8K/mo" },
];

export function ResourcesMockup() {
    return (
        <div className="overflow-hidden rounded-xl border border-white/[0.08] bg-gradient-to-b from-[#0c0d12] to-[#07080c] shadow-[0_30px_60px_-15px_rgba(0,0,0,0.8),0_0_0_1px_rgba(255,255,255,0.05)] backdrop-blur-xl">
            <div className="flex h-8 items-center justify-between border-b border-white/[0.06] bg-white/[0.02] px-3">
                <span className="text-[12px] font-medium text-zinc-300">Resources</span>
                <span className="text-[11px] text-zinc-500">247 total</span>
            </div>
            <div className="relative space-y-2 p-3">
                {resources.map((resource) => (
                    <div key={resource.name} className="flex items-center gap-3 py-2">
                        <span className="h-2 w-2 rounded-full" style={{ backgroundColor: resource.provider }} />
                        <span className="min-w-0 flex-1 truncate text-[12px] text-zinc-300">{resource.name}</span>
                        <span className="text-[11px] tabular-nums text-zinc-500">{resource.cost}</span>
                    </div>
                ))}
                <div className="pointer-events-none absolute inset-x-0 bottom-0 h-10 bg-gradient-to-t from-[#07080c] to-transparent" />
            </div>
        </div>
    );
}
