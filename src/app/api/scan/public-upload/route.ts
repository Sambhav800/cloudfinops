import { NextRequest, NextResponse } from "next/server";
import { BACKEND_URL } from "@/lib/config";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const MAX_BYTES = 20 * 1024 * 1024; // 20 MB — matches free-tier backend cap
const TIMEOUT_MS = 65_000; // slightly longer than the backend 60s parse timeout

/**
 * POST /api/scan/public-upload
 *
 * Public (unauthenticated) proxy that forwards the multipart file upload
 * directly to the Python backend's public endpoint.
 *
 * Intentionally does NOT call getBackendAuthContext() — this is a
 * lead-gen route open to anonymous users.
 */
export async function POST(request: NextRequest) {
  try {
    const incomingForm = await request.formData();
    const file = incomingForm.get("file");

    if (!(file instanceof File)) {
      return NextResponse.json({ detail: "No file provided." }, { status: 400 });
    }

    if (file.size > MAX_BYTES) {
      return NextResponse.json(
        { detail: `File too large. Free tier limit is ${MAX_BYTES / (1024 * 1024)} MB.` },
        { status: 413 },
      );
    }

    // Forward multipart data to Python backend
    const outgoingForm = new FormData();
    const fileBuffer = await file.arrayBuffer();
    const blob = new Blob([fileBuffer], { type: file.type || "application/octet-stream" });
    outgoingForm.append("file", blob, file.name);

    // Propagate the real client IP for backend rate limiting
    const clientIp =
      request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ??
      request.headers.get("x-real-ip") ??
      "unknown";

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), TIMEOUT_MS);

    let response: Response;
    try {
      response = await fetch(`${BACKEND_URL}/api/scan/public-upload`, {
        method: "POST",
        body: outgoingForm,
        headers: {
          // Forward client IP header to the backend for rate limiting
          "x-forwarded-for": clientIp,
        },
        signal: controller.signal,
      });
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") {
        return NextResponse.json(
          {
            detail:
              "Analysis timed out. Try uploading a CSV/Excel export, or a smaller text-based PDF.",
          },
          { status: 504 },
        );
      }
      throw err;
    } finally {
      clearTimeout(timeoutId);
    }

    const data = await response.json();
    if (!response.ok) {
      return NextResponse.json(
        { detail: data?.detail ?? "Analysis failed" },
        { status: response.status },
      );
    }

    return NextResponse.json(data);
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unknown error";
    return NextResponse.json(
      { detail: `Could not reach the analysis engine: ${message}` },
      { status: 503 },
    );
  }
}
