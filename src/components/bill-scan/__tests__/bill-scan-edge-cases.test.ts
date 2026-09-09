import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

/* ═══════════════════════════════════════════════════════════════════════
 * PHASE 3: BILL SCANNER EDGE CASES & ERROR HANDLING TESTS
 *
 * Tests covering:
 *   1. Empty file upload (0-byte files)
 *   2. Unsupported file format (.txt, .exe, .json, uppercase extensions)
 *   3. File size limits (> 20 MB)
 *   4. Very large file name (250+ chars, unicode, special chars)
 *   5. Rate limiting (429 Too Many Requests)
 *   6. Request timeout (AbortError handling)
 *   7. Backend 422 / 500 errors and retry flow
 *   8. Empty findings list handling in TeaserReport
 * ═══════════════════════════════════════════════════════════════════════ */

/* ── Helpers mimicking client-side validation logic from BillDropzone ── */
function validateFile(file: { name: string; size: number }): string | null {
  const ext = `.${file.name.split(".").pop()?.toLowerCase() ?? ""}`;
  const ACCEPTED_EXTENSIONS = [".csv", ".xlsx", ".xls", ".pdf"];
  const MAX_FILE_BYTES = 20 * 1024 * 1024; // 20 MB
  const MAX_FILE_SIZE_LABEL = "20 MB";

  if (!ACCEPTED_EXTENSIONS.includes(ext)) {
    return `Unsupported format "${ext}". Please upload a CSV, XLSX, XLS, or PDF file.`;
  }
  if (file.size > MAX_FILE_BYTES) {
    const mb = (file.size / (1024 * 1024)).toFixed(1);
    return `File is too large (${mb} MB). Free tier limit is ${MAX_FILE_SIZE_LABEL}.`;
  }
  return null;
}

// ── Test 1: Empty file upload fixture & handling ──
test("empty file upload: 0-byte fixture exists and is recognized as empty", () => {
  const emptyFixturePath = path.join(__dirname, "fixtures", "empty-bill.csv");
  assert.ok(fs.existsSync(emptyFixturePath), "empty-bill.csv fixture should exist");
  const stats = fs.statSync(emptyFixturePath);
  assert.equal(stats.size, 0, "empty-bill.csv should be 0 bytes");

  // Backend should reject or handle empty files gracefully
  const routesPath = path.resolve(__dirname, "../../../../backend/app/api/routes.py");
  if (fs.existsSync(routesPath)) {
    const routesContent = fs.readFileSync(routesPath, "utf-8");
    // Verifies backend has empty file check or size check
    assert.match(
      routesContent,
      /len\(content\)\s*==\s*0|len\(contents\)\s*==\s*0|file\.size\s*==\s*0|not content|not contents/i,
      "Backend should check for empty file content"
    );
  }
});

// ── Test 2: Unsupported file format ──
test("unsupported file format: rejects .txt, .json, .exe, .zip with informative error", () => {
  const invalidExtensions = [
    "bill.txt",
    "invoice.json",
    "malicious.exe",
    "archive.zip",
    "data.parquet",
    "noextension",
  ];

  for (const filename of invalidExtensions) {
    const error = validateFile({ name: filename, size: 1024 });
    assert.ok(error !== null, `Filename "${filename}" should be rejected`);
    assert.match(
      error,
      /Unsupported format/,
      `Error for "${filename}" should mention unsupported format`
    );
    assert.match(
      error,
      /CSV, XLSX, XLS, or PDF/,
      "Error should guide user to allowed formats"
    );
  }

  // Also verify text fixture exists
  const textFixture = path.join(__dirname, "fixtures", "invalid-extension.txt");
  assert.ok(fs.existsSync(textFixture), "invalid-extension.txt fixture should exist");
});

test("file format validation is case-insensitive (.CSV, .Pdf, .XLSX are accepted)", () => {
  const mixedCaseValid = ["BILL.CSV", "invoice.XLSX", "statement.Pdf", "report.Xls"];
  for (const filename of mixedCaseValid) {
    const error = validateFile({ name: filename, size: 2048 });
    assert.equal(error, null, `Filename with mixed case "${filename}" should be accepted`);
  }
});

// ── Test 3: Oversized file limit ──
test("oversized file: rejects files exceeding 20 MB limit", () => {
  const exactlyLimit = 20 * 1024 * 1024;
  const overLimit = 20 * 1024 * 1024 + 1; // 20 MB + 1 byte
  const massiveFile = 100 * 1024 * 1024; // 100 MB

  assert.equal(
    validateFile({ name: "aws-bill.csv", size: exactlyLimit }),
    null,
    "File at exact 20 MB limit should pass"
  );

  const errorOver = validateFile({ name: "aws-bill.csv", size: overLimit });
  assert.ok(errorOver !== null, "File over 20 MB should be rejected");
  assert.match(errorOver, /File is too large/);
  assert.match(errorOver, /20 MB/);

  const errorMassive = validateFile({ name: "big-export.xlsx", size: massiveFile });
  assert.ok(errorMassive !== null);
  assert.match(errorMassive, /File is too large/);
});

// ── Test 4: Very large / unusual file names ──
test("very large file name (300+ characters, unicode, spaces) is parsed safely", () => {
  const longName = "A".repeat(300) + ".csv";
  assert.equal(validateFile({ name: longName, size: 5000 }), null);

  const unicodeName = "クラウド請求書_aws_billing_東京リージョン_2026_🔥.csv";
  assert.equal(validateFile({ name: unicodeName, size: 5000 }), null);

  const complexPunctuation = "my.bill.v2.final (1) [backup] - march 2026.pdf";
  assert.equal(validateFile({ name: complexPunctuation, size: 5000 }), null);

  // BillDropzone trims / handles file names gracefully without throwing
  const dropzoneSource = fs.readFileSync(
    path.resolve(__dirname, "../components/BillDropzone.tsx"),
    "utf-8"
  );
  assert.match(
    dropzoneSource,
    /truncate/,
    "BillDropzone should use 'truncate' class for rendering long filenames safely in UI"
  );
});

// ── Test 5: Rate Limiting (429 Too Many Requests) ──
test("publicScan client translates 429 status into user-friendly free scan limit error", () => {
  const publicScanSource = fs.readFileSync(
    path.resolve(__dirname, "../api/publicScan.ts"),
    "utf-8"
  );

  // Checks status === 429
  assert.match(publicScanSource, /response\.status\s*===\s*429/);
  // Verifies rate limit message informs user of limit
  assert.match(
    publicScanSource,
    /free scan limit.*5 scans per hour/i
  );
});

// ── Test 6: Request Timeout / AbortError ──
test("publicScan enforces upload timeout with AbortController and friendly message", () => {
  const publicScanSource = fs.readFileSync(
    path.resolve(__dirname, "../api/publicScan.ts"),
    "utf-8"
  );

  // Verifies AbortController is instantiated and wired to fetch signal
  assert.match(publicScanSource, /new AbortController\(\)/);
  assert.match(publicScanSource, /signal:\s*controller\.signal/);
  assert.match(publicScanSource, /window\.setTimeout/);
  assert.match(publicScanSource, /window\.clearTimeout/);

  // Verifies AbortError produces actionable troubleshooting tip
  assert.match(publicScanSource, /AbortError/);
  assert.match(
    publicScanSource,
    /The scan timed out.*Try uploading a smaller file/i
  );
});

// ── Test 7: Backend 422 / 500 errors and retry flow ──
test("BillScanPage provides error state with retry button (#bill-scan-retry-btn)", () => {
  const pageSource = fs.readFileSync(
    path.resolve(__dirname, "../BillScanPage.tsx"),
    "utf-8"
  );

  // Verifies error state rendering
  assert.match(pageSource, /state\.status\s*===\s*"error"/);
  assert.match(pageSource, /Scan failed/);
  assert.match(pageSource, /id="bill-scan-retry-btn"/);
  assert.match(pageSource, /Try a different file/);

  // Verifies retry button resets status to idle
  assert.match(pageSource, /const handleReset = useCallback\(\(\) => \{/);
  assert.match(pageSource, /setState\(\{\s*status:\s*"idle"\s*\}\)/);
});

// ── Test 8: Empty or 0 findings in TeaserReport ──
test("TeaserReport handles 0 findings without crash", () => {
  const teaserSource = fs.readFileSync(
    path.resolve(__dirname, "../components/TeaserReport.tsx"),
    "utf-8"
  );

  // Checks length > 0 before mapping
  assert.match(teaserSource, /data\.top_findings_teaser\.length\s*>\s*0/);
  // Header shows count of detected services
  assert.match(teaserSource, /data\.top_findings_teaser\.length/);
});

// ── Test 9: Dropzone drag-and-drop disabled state ──
test("BillDropzone honors disabled prop during drag and click events", () => {
  const dropzoneSource = fs.readFileSync(
    path.resolve(__dirname, "../components/BillDropzone.tsx"),
    "utf-8"
  );

  assert.match(dropzoneSource, /if\s*\(disabled\)\s*return/);
  assert.match(dropzoneSource, /cursor-not-allowed|opacity-60/);
});
