import Link from "next/link";
import type { BlogPostMeta } from "@/lib/blog";

export function BlogHeroCard({ post }: { post: BlogPostMeta }) {
  return (
    <Link href={`/blog/${post.slug}`} className="group block">
      <article className="relative rounded-2xl border border-white/[0.08] bg-gradient-to-br from-indigo-500/[0.06] via-white/[0.02] to-transparent p-8 md:p-12 transition-all duration-300 hover:border-indigo-500/30 overflow-hidden">
        <div className="absolute top-0 right-0 w-72 h-72 bg-indigo-500/[0.04] rounded-full blur-[100px] pointer-events-none" />

        <div className="relative z-10">
          <div className="flex items-center gap-3 mb-5">
            <span className="inline-flex rounded-full px-3 py-1 text-[11px] font-medium uppercase tracking-widest border border-indigo-500/30 bg-indigo-500/[0.08] text-indigo-300">
              Featured
            </span>
            <span className="inline-flex rounded-full px-3 py-1 text-[11px] font-medium uppercase tracking-widest border border-white/[0.08] bg-white/[0.04] text-zinc-400">
              {post.category}
            </span>
          </div>

          <h2 className="text-2xl md:text-3xl font-bold text-white leading-tight mb-4 group-hover:text-indigo-300 transition-colors">
            {post.title}
          </h2>

          <p className="text-zinc-400 text-[16px] leading-relaxed mb-6 max-w-2xl">
            {post.excerpt}
          </p>

          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-full bg-gradient-to-br from-indigo-500 to-purple-500 flex items-center justify-center text-[11px] font-bold text-white">
                {post.author.name
                  .split(" ")
                  .map((n) => n[0])
                  .join("")}
              </div>
              <div>
                <span className="text-sm text-white">{post.author.name}</span>
                <span className="text-xs text-zinc-600 ml-2">
                  {new Date(post.publishedAt).toLocaleDateString("en-US", {
                    month: "short",
                    day: "numeric",
                  })}
                  {" · "}
                  {post.readTime} min read
                </span>
              </div>
            </div>
          </div>
        </div>
      </article>
    </Link>
  );
}
