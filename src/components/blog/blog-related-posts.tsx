import type { BlogPostMeta } from "@/lib/blog";
import { BlogCard } from "./blog-card";

export function BlogRelatedPosts({ posts }: { posts: BlogPostMeta[] }) {
  if (posts.length === 0) return null;

  return (
    <section className="mt-20 pt-12 border-t border-white/[0.06]">
      <h2 className="text-xl font-semibold text-white mb-8">Related articles</h2>
      <div className="grid md:grid-cols-3 gap-5">
        {posts.map((post) => (
          <BlogCard key={post.slug} post={post} />
        ))}
      </div>
    </section>
  );
}
