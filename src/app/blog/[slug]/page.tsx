import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Image from "next/image";
import {
  getAllPosts,
  getPostBySlug,
  getRelatedPosts,
  extractHeadings,
} from "@/lib/blog";
import { BlogMarkdown } from "@/components/blog/blog-markdown";
import { BlogToc } from "@/components/blog/blog-toc";
import { BlogBreadcrumb } from "@/components/blog/blog-breadcrumb";
import { BlogCtaInline } from "@/components/blog/blog-cta-inline";
import { BlogRelatedPosts } from "@/components/blog/blog-related-posts";

const SITE_URL = "https://cloudfinops.solutions";

export async function generateStaticParams() {
  return getAllPosts().map((post) => ({ slug: post.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const post = getPostBySlug(slug);
  if (!post) return { title: "Post Not Found" };

  return {
    title: post.title,
    description: post.excerpt,
    alternates: { canonical: `/blog/${post.slug}` },
    openGraph: {
      type: "article",
      title: post.title,
      description: post.excerpt,
      publishedTime: post.publishedAt,
      modifiedTime: post.updatedAt || post.publishedAt,
      authors: [post.author.name],
      images: post.ogImage ? [{ url: post.ogImage, width: 1200, height: 630 }] : [],
    },
    twitter: {
      card: "summary_large_image",
      title: post.title,
      description: post.excerpt,
      images: post.ogImage ? [post.ogImage] : [],
    },
  };
}

export default async function BlogPostPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const post = getPostBySlug(slug);
  if (!post) notFound();

  const headings = extractHeadings(post.content);
  const related = getRelatedPosts(slug, 3);

  const blogPostingJsonLd = {
    "@context": "https://schema.org",
    "@type": "BlogPosting",
    headline: post.title,
    description: post.excerpt,
    author: {
      "@type": "Person",
      name: post.author.name,
      jobTitle: post.author.role,
    },
    publisher: {
      "@type": "Organization",
      name: "CloudFinOps",
      url: SITE_URL,
      logo: {
        "@type": "ImageObject",
        url: `${SITE_URL}/images/logo/wh-logo.png`,
      },
    },
    datePublished: post.publishedAt,
    dateModified: post.updatedAt || post.publishedAt,
    mainEntityOfPage: {
      "@type": "WebPage",
      "@id": `${SITE_URL}/blog/${post.slug}`,
    },
    image: post.ogImage ? `${SITE_URL}${post.ogImage}` : undefined,
    wordCount: post.content.split(/\s+/).length,
    articleSection: post.category,
    keywords: post.tags.join(", "),
  };

  const breadcrumbJsonLd = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      {
        "@type": "ListItem",
        position: 1,
        name: "Home",
        item: SITE_URL,
      },
      {
        "@type": "ListItem",
        position: 2,
        name: "Blog",
        item: `${SITE_URL}/blog`,
      },
      {
        "@type": "ListItem",
        position: 3,
        name: post.title,
        item: `${SITE_URL}/blog/${post.slug}`,
      },
    ],
  };

  // Split content at 3rd H2 to inject CTA
  const sections = post.content.split(/(?=^## )/m);
  const beforeCta = sections.slice(0, 3).join("");
  const afterCta = sections.slice(3).join("");

  return (
    <div className="bg-[#07080c] min-h-screen pt-28 pb-16">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(blogPostingJsonLd) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbJsonLd) }}
      />

      <div className="mx-auto max-w-6xl px-6 lg:px-8">
        {/* Breadcrumb */}
        <BlogBreadcrumb
          items={[
            { label: "Home", href: "/" },
            { label: "Blog", href: "/blog" },
            { label: post.category, href: `/blog?category=${encodeURIComponent(post.category)}` },
            { label: post.title },
          ]}
        />

        {/* Post Header */}
        <header className="max-w-3xl mb-10">
          <div className="mb-4">
            <span className="inline-flex rounded-full px-3 py-1 text-[11px] font-medium uppercase tracking-widest border border-indigo-500/30 bg-indigo-500/[0.08] text-indigo-300">
              {post.category}
            </span>
          </div>

          <h1 className="text-3xl md:text-4xl font-bold text-white tracking-tight leading-tight mb-5">
            {post.title}
          </h1>

          <div className="flex items-center gap-3">
            <div className="relative w-9 h-9 rounded-full overflow-hidden border border-white/10">
              <Image
                src={post.author.avatar}
                alt={post.author.name}
                fill
                className="object-cover"
              />
            </div>
            <div>
              <p className="text-sm text-white">{post.author.name}</p>
              <p className="text-xs text-zinc-500">
                {post.author.role}
                {" · "}
                <time dateTime={post.publishedAt}>
                  {new Date(post.publishedAt).toLocaleDateString("en-US", {
                    month: "long",
                    day: "numeric",
                    year: "numeric",
                  })}
                </time>
                {" · "}
                {post.readTime} min read
              </p>
            </div>
          </div>
        </header>

        {/* Content + ToC */}
        <div className="flex gap-10">
          {/* Main Content */}
          <article className="min-w-0 flex-1 max-w-3xl">
            <BlogMarkdown content={beforeCta} />
            {afterCta && <BlogCtaInline />}
            {afterCta && <BlogMarkdown content={afterCta} />}
          </article>

          {/* Sidebar ToC */}
          {headings.length > 2 && (
            <aside className="hidden lg:block w-64 shrink-0">
              <BlogToc headings={headings} />
            </aside>
          )}
        </div>

        {/* Related Posts */}
        <BlogRelatedPosts posts={related} />
      </div>
    </div>
  );
}
