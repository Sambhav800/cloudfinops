import { ImageResponse } from "next/og";
import { getPostBySlug, getAllPosts } from "@/lib/blog";

export const runtime = "nodejs";
export const alt = "CloudFinOps Blog";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export function generateStaticParams() {
  return getAllPosts().map((post) => ({ slug: post.slug }));
}

export default async function OgImage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const post = getPostBySlug(slug);

  const title = post?.title || "CloudFinOps Blog";
  const category = post?.category || "Cloud Cost Optimization";
  const readTime = post?.readTime || 10;
  const author = post?.author?.name || "CloudFinOps Team";

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: "60px 80px",
          background: "linear-gradient(135deg, #07080c 0%, #0f1419 50%, #1a1f2e 100%)",
          fontFamily: "system-ui, -apple-system, sans-serif",
        }}
      >
        {/* Top: category + branding */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              padding: "8px 16px",
              borderRadius: "20px",
              border: "1px solid rgba(99, 102, 241, 0.4)",
              background: "rgba(99, 102, 241, 0.1)",
            }}
          >
            <span style={{ fontSize: "14px", color: "#818cf8", fontWeight: 600, letterSpacing: "0.05em", textTransform: "uppercase" }}>
              {category}
            </span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <div
              style={{
                width: "32px",
                height: "32px",
                borderRadius: "8px",
                background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <span style={{ fontSize: "16px", fontWeight: 800, color: "white" }}>C</span>
            </div>
            <span style={{ fontSize: "18px", fontWeight: 600, color: "#e4e4e7" }}>
              CloudFinOps
            </span>
          </div>
        </div>

        {/* Middle: title */}
        <div style={{ display: "flex", flexDirection: "column", gap: "16px", maxWidth: "900px" }}>
          <h1
            style={{
              fontSize: title.length > 70 ? "38px" : "46px",
              fontWeight: 700,
              color: "#ffffff",
              lineHeight: 1.2,
              margin: 0,
              letterSpacing: "-0.02em",
            }}
          >
            {title}
          </h1>
        </div>

        {/* Bottom: author + read time */}
        <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
          <div
            style={{
              width: "40px",
              height: "40px",
              borderRadius: "20px",
              background: "linear-gradient(135deg, #6366f1, #a855f7)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <span style={{ fontSize: "16px", fontWeight: 700, color: "white" }}>
              {author.split(" ").map((n) => n[0]).join("")}
            </span>
          </div>
          <div style={{ display: "flex", flexDirection: "column" }}>
            <span style={{ fontSize: "16px", color: "#e4e4e7", fontWeight: 500 }}>{author}</span>
            <span style={{ fontSize: "14px", color: "#71717a" }}>{readTime} min read</span>
          </div>
          <div
            style={{
              marginLeft: "auto",
              padding: "6px 14px",
              borderRadius: "6px",
              background: "rgba(255,255,255,0.05)",
              border: "1px solid rgba(255,255,255,0.1)",
            }}
          >
            <span style={{ fontSize: "13px", color: "#a1a1aa" }}>cloudfinops.solutions/blog</span>
          </div>
        </div>
      </div>
    ),
    { ...size }
  );
}
