import fs from "fs";
import path from "path";
// @ts-expect-error js-yaml lacks type declarations in this project
import yaml from "js-yaml";

const CONTENT_DIR = path.join(process.cwd(), "src/content/blog");

export interface BlogPost {
  slug: string;
  title: string;
  excerpt: string;
  category: string;
  author: {
    name: string;
    role: string;
    avatar: string;
  };
  publishedAt: string;
  updatedAt?: string;
  readTime: number;
  featured?: boolean;
  tags: string[];
  ogImage?: string;
  content: string;
}

export type BlogPostMeta = Omit<BlogPost, "content">;

function parseFrontmatter(fileContent: string): {
  data: Record<string, unknown>;
  content: string;
} {
  const match = fileContent.match(/^---\n([\s\S]*?)\n---\n([\s\S]*)$/);
  if (!match) return { data: {}, content: fileContent };
  return {
    data: yaml.load(match[1]) as Record<string, unknown>,
    content: match[2].trim(),
  };
}

function getPostFiles(): string[] {
  if (!fs.existsSync(CONTENT_DIR)) return [];
  return fs
    .readdirSync(CONTENT_DIR)
    .filter((f) => f.endsWith(".md"))
    .sort();
}

function parsePost(filename: string): BlogPost {
  const filePath = path.join(CONTENT_DIR, filename);
  const raw = fs.readFileSync(filePath, "utf-8");
  const { data, content } = parseFrontmatter(raw);

  return {
    slug: (data.slug as string) || filename.replace(/\.md$/, ""),
    title: (data.title as string) || "Untitled",
    excerpt: (data.excerpt as string) || "",
    category: (data.category as string) || "General",
    author: (data.author as BlogPost["author"]) || {
      name: "CloudFinOps Team",
      role: "Engineering",
      avatar: "/images/logo/wh-logo.png",
    },
    publishedAt: (data.publishedAt as string) || "2026-01-01",
    updatedAt: data.updatedAt as string | undefined,
    readTime: (data.readTime as number) || Math.ceil(content.split(/\s+/).length / 200),
    featured: (data.featured as boolean) || false,
    tags: (data.tags as string[]) || [],
    ogImage: data.ogImage as string | undefined,
    content,
  };
}

export function getAllPosts(): BlogPostMeta[] {
  return getPostFiles()
    .map((f) => {
      const post = parsePost(f);
      const { content: _, ...meta } = post;
      return meta;
    })
    .sort(
      (a, b) =>
        new Date(b.publishedAt).getTime() - new Date(a.publishedAt).getTime()
    );
}

export function getPostBySlug(slug: string): BlogPost | null {
  const files = getPostFiles();
  for (const f of files) {
    const post = parsePost(f);
    if (post.slug === slug) return post;
  }
  return null;
}

export function getPostsByCategory(category: string): BlogPostMeta[] {
  return getAllPosts().filter(
    (p) => p.category.toLowerCase() === category.toLowerCase()
  );
}

export function getAllCategories(): string[] {
  const categories = new Set(getAllPosts().map((p) => p.category));
  return Array.from(categories).sort();
}

export function getRelatedPosts(
  slug: string,
  limit = 3
): BlogPostMeta[] {
  const current = getAllPosts().find((p) => p.slug === slug);
  if (!current) return [];
  return getAllPosts()
    .filter((p) => p.slug !== slug && p.category === current.category)
    .slice(0, limit);
}

export function extractHeadings(
  content: string
): { id: string; text: string; level: number }[] {
  const headingRegex = /^(#{2,3})\s+(.+)$/gm;
  const headings: { id: string; text: string; level: number }[] = [];
  let match;
  while ((match = headingRegex.exec(content)) !== null) {
    const text = match[2].trim();
    const id = text
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/(^-|-$)/g, "");
    headings.push({ id, text, level: match[1].length });
  }
  return headings;
}
