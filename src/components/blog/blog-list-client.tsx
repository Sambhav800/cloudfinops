"use client";

import { useState } from "react";
import type { BlogPostMeta } from "@/lib/blog";
import { BlogCard } from "./blog-card";
import { BlogCategoryTabs } from "./blog-category-tabs";

const POSTS_PER_PAGE = 9;

export function BlogListClient({ posts }: { posts: BlogPostMeta[] }) {
  const [category, setCategory] = useState("All");
  const [visibleCount, setVisibleCount] = useState(POSTS_PER_PAGE);

  const filtered =
    category === "All"
      ? posts
      : posts.filter(
          (p) => p.category.toLowerCase() === category.toLowerCase()
        );

  const visible = filtered.slice(0, visibleCount);
  const hasMore = visibleCount < filtered.length;

  return (
    <div>
      <div className="mb-8">
        <BlogCategoryTabs active={category} onChange={(c) => {
          setCategory(c);
          setVisibleCount(POSTS_PER_PAGE);
        }} />
      </div>

      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-5">
        {visible.map((post) => (
          <BlogCard key={post.slug} post={post} />
        ))}
      </div>

      {filtered.length === 0 && (
        <p className="text-center text-zinc-500 py-16">
          No articles in this category yet.
        </p>
      )}

      {hasMore && (
        <div className="text-center mt-10">
          <button
            onClick={() => setVisibleCount((c) => c + 6)}
            className="inline-flex items-center gap-2 rounded-full px-6 py-3 text-sm font-medium border border-white/[0.08] bg-white/[0.03] text-zinc-400 hover:text-white hover:border-white/[0.15] transition-all"
          >
            Show more
            <span className="text-zinc-600">
              ({filtered.length - visibleCount} remaining)
            </span>
          </button>
        </div>
      )}
    </div>
  );
}
