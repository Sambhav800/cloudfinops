import Link from "next/link";

export function BlogCtaInline() {
  return (
    <div className="my-10 rounded-xl border border-indigo-500/20 bg-gradient-to-r from-indigo-500/[0.06] to-purple-500/[0.04] p-6 md:p-8">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <p className="text-white font-semibold text-lg mb-1">
            See how much you&apos;re wasting
          </p>
          <p className="text-zinc-400 text-sm">
            Get a free 7-day cloud audit. No credit card, no agents, read-only
            access.
          </p>
        </div>
        <Link
          href="/audit"
          className="shrink-0 inline-flex items-center justify-center gap-2 bg-indigo-500 text-white font-medium px-6 py-3 rounded-lg hover:bg-indigo-400 transition-colors text-sm"
        >
          Start Free Audit
        </Link>
      </div>
    </div>
  );
}
