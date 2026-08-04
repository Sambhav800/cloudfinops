"use client";

const CATEGORIES = [
  "All",
  "Cloud Cost Optimization",
  "AWS",
  "GCP",
  "Azure",
  "FinOps",
];

export function BlogCategoryTabs({
  active,
  onChange,
}: {
  active: string;
  onChange: (category: string) => void;
}) {
  return (
    <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-hide">
      {CATEGORIES.map((cat) => (
        <button
          key={cat}
          onClick={() => onChange(cat)}
          className={`shrink-0 rounded-full px-4 py-2 text-[13px] font-medium transition-all duration-200 ${
            active === cat
              ? "bg-indigo-500/[0.15] border border-indigo-500/40 text-indigo-300"
              : "bg-white/[0.03] border border-white/[0.08] text-zinc-500 hover:text-zinc-300 hover:border-white/[0.15]"
          }`}
        >
          {cat}
        </button>
      ))}
    </div>
  );
}
