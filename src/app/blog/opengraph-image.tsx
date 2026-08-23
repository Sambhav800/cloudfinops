import { ImageResponse } from "next/og";

export const runtime = "edge";
export const alt = "CloudFinOps Blog — Cloud Cost Optimization Insights";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OgImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          alignItems: "center",
          padding: "60px 80px",
          background: "linear-gradient(135deg, #07080c 0%, #0f1419 50%, #1a1f2e 100%)",
          fontFamily: "system-ui, -apple-system, sans-serif",
        }}
      >
        <div
          style={{
            width: "56px",
            height: "56px",
            borderRadius: "14px",
            background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            marginBottom: "24px",
          }}
        >
          <span style={{ fontSize: "28px", fontWeight: 800, color: "white" }}>C</span>
        </div>
        <h1
          style={{
            fontSize: "52px",
            fontWeight: 700,
            color: "#ffffff",
            textAlign: "center",
            margin: 0,
            letterSpacing: "-0.02em",
          }}
        >
          Cloud Cost Optimization Blog
        </h1>
        <p
          style={{
            fontSize: "22px",
            color: "#a1a1aa",
            textAlign: "center",
            marginTop: "16px",
            maxWidth: "700px",
          }}
        >
          Actionable guides on reducing AWS, Azure & GCP spend for engineering teams
        </p>
        <div
          style={{
            marginTop: "32px",
            padding: "8px 20px",
            borderRadius: "20px",
            border: "1px solid rgba(99, 102, 241, 0.3)",
            background: "rgba(99, 102, 241, 0.08)",
          }}
        >
          <span style={{ fontSize: "14px", color: "#818cf8", fontWeight: 500 }}>
            cloudfinops.solutions/blog
          </span>
        </div>
      </div>
    ),
    { ...size }
  );
}
