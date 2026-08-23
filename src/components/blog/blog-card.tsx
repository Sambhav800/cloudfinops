import Link from "next/link";
import type { BlogPostMeta } from "@/lib/blog";

export function BlogCard({ post }: { post: BlogPostMeta }) {
  return (
    <Link href={`/blog/${post.slug}`} className="group block">
      <article className="h-full rounded-xl border border-white/[0.08] bg-gradient-to-b from-white/[0.03] to-transparent p-6 transition-all duration-300 hover:border-white/[0.15] hover:bg-white/[0.04]">
        <div className="mb-4">
          <span className="inline-flex rounded-full px-3 py-1 text-[11px] font-medium uppercase tracking-widest border border-indigo-500/30 bg-indigo-500/[0.08] text-indigo-300">
            {post.category}
          </span>
        </div>

        <h3 className="text-[17px] font-semibold text-white leading-snug mb-3 group-hover:text-indigo-300 transition-colors line-clamp-2">
          {post.title}
        </h3>

        <p className="text-sm text-zinc-500 leading-relaxed mb-5 line-clamp-3">
          {post.excerpt}
        </p>

        <div className="flex items-center gap-2 mt-auto pt-4 border-t border-white/[0.04]">
          <div className="w-5 h-5 rounded-full bg-gradient-to-br from-indigo-500 to-purple-500 flex items-center justify-center text-[8px] font-bold text-white shrink-0">
            {post.author.name.split(" ").map((n) => n[0]).join("")}
          </div>
          <span className="text-[11px] text-zinc-500 truncate">{post.author.name}</span>
          <span className="text-[11px] text-zinc-700 ml-auto shrink-0">
            {new Date(post.publishedAt).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
            {" · "}
            {post.readTime}m
          </span>
        </div>
      </article>
    </Link>
  );
}
