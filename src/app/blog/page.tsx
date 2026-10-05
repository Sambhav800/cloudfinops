import type { Metadata } from "next";
import { getAllPosts } from "@/lib/blog";
import { BlogHeroCard } from "@/components/blog/blog-hero-card";
import { BlogListClient } from "@/components/blog/blog-list-client";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Blog — Cloud Cost Optimization Guides, Tips & FinOps Best Practices",
  description:
    "Expert guides on reducing your AWS, Azure, and GCP cloud bill. Learn FinOps best practices, detect idle resources, and optimize cloud spend.",
  alternates: { canonical: "/blog" },
  openGraph: {
    title: "CloudFinOps Blog — Cloud Cost Optimization Insights",
    description:
      "Expert guides on reducing your AWS, Azure, and GCP cloud bill.",
    type: "website",
  },
};

const blogListingJsonLd = {
  "@context": "https://schema.org",
  "@type": "Blog",
  name: "CloudFinOps Blog",
  description:
    "Expert guides on cloud cost optimization, FinOps best practices, and multi-cloud governance.",
  url: "https://cloudfinops.solutions/blog",
  publisher: {
    "@type": "Organization",
    name: "CloudFinOps",
    url: "https://cloudfinops.solutions",
  },
};

export default function BlogPage() {
  const allPosts = getAllPosts();
  const featuredPost = allPosts.find((p) => p.featured) || allPosts[0];
  const otherPosts = allPosts.filter((p) => p.slug !== featuredPost?.slug);

  return (
    <div className="bg-[#07080c] min-h-screen pt-28 pb-16">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(blogListingJsonLd) }}
      />

      <div className="mx-auto max-w-6xl px-6 lg:px-8">
        {/* Header */}
        <div className="text-center mb-14">
          <p className="text-[11px] font-medium uppercase tracking-widest text-indigo-400 mb-3">
            Insights & Guides
          </p>
          <h1 className="text-4xl md:text-5xl font-bold text-white tracking-tight mb-4">
            Cloud Cost Optimization Blog
          </h1>
          <p className="text-lg text-zinc-500 max-w-2xl mx-auto">
            Actionable guides on reducing cloud waste, FinOps frameworks, and
            multi-cloud governance for engineering teams.
          </p>
        </div>

        {/* Featured Post */}
        {featuredPost && (
          <div className="mb-14">
            <BlogHeroCard post={featuredPost} />
          </div>
        )}

        {/* Post Grid with Tabs */}
        <BlogListClient posts={otherPosts} />

        {/* Bottom CTA */}
        <div className="mt-20 text-center rounded-2xl border border-white/[0.06] bg-gradient-to-br from-indigo-500/[0.04] to-transparent p-10 md:p-14">
          <h2 className="text-2xl font-semibold text-white mb-3">
            Stop paying for idle cloud resources
          </h2>
          <p className="text-zinc-400 mb-6 max-w-lg mx-auto">
            Get a free 7-day audit of your AWS, Azure, or GCP account. See
            exactly where you&apos;re wasting money.
          </p>
          <Link
            href="/audit"
            className="inline-flex items-center gap-2 bg-indigo-500 text-white font-medium px-6 py-3 rounded-lg hover:bg-indigo-400 transition-colors"
          >
            Start Free Audit
          </Link>
        </div>
      </div>
    </div>
  );
}
