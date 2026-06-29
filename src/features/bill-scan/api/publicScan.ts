import type { TeaserReportPayload } from "../types";
import { PUBLIC_UPLOAD_ENDPOINT, UPLOAD_TIMEOUT_MS } from "../constants";

/**
 * Uploads a billing file to the unauthenticated public scan endpoint
 * and returns the redacted teaser report payload.
 *
 * No auth headers are attached — this is intentionally a public call.
 */
export async function executePublicScan(file: File): Promise<TeaserReportPayload> {
  const payload = new FormData();
  payload.append("file", file);

  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), UPLOAD_TIMEOUT_MS);

  let response: Response;
  try {
    response = await fetch(PUBLIC_UPLOAD_ENDPOINT, {
      method: "POST",
      body: payload,
      signal: controller.signal,
    });
  } catch (err) {
    if (err instanceof Error && err.name === "AbortError") {
      throw new Error(
        "The scan timed out. Try uploading a smaller file or a CSV/Excel export instead of a PDF."
      );
    }
    throw err;
  } finally {
    window.clearTimeout(timeoutId);
  }

  if (response.status === 429) {
    throw new Error(
      "You've reached the free scan limit (5 scans per hour). Please try again later or sign up for unlimited access."
    );
  }

  if (!response.ok) {
    let detail = "Analysis failed. Please check your file and try again.";
    try {
      const data = (await response.json()) as { detail?: string };
      if (data?.detail) detail = data.detail;
    } catch {
      // ignore JSON parse failure
    }
    throw new Error(detail);
  }

  return response.json() as Promise<TeaserReportPayload>;
}
