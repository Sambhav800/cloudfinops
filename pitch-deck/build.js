const pptxgen = require("pptxgenjs");

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";
pres.author = "CloudFinOps";
pres.title = "CloudFinOps — Seed Pitch Deck";

const W = 13.333, H = 7.5;

const NAVY_DEEP = "0A2540";
const NAVY = "0B3D63";
const BLUE = "1466A5";
const ICE = "EAF2F9";
const ICE_LINE = "D7E4F0";
const GREEN = "2F9E44";
const GREEN_SOFT = "E8F5EC";
const SLATE = "51617D";
const INK = "16212E";
const WHITE = "FFFFFF";
const AMBER = "B7791F";
const ROSE = "C0392B";
const ROSE_SOFT = "FDEEEE";

const FONT = "Calibri";
const FONT_HEAD = "Cambria";
const LOGO = "logo.png";

function eyebrow(slide, num, label, opts = {}) {
  const dark = opts.dark || false;
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x: opts.x ?? 0.6, y: opts.y ?? 0.42, w: 0.42, h: 0.28,
    rectRadius: 0.06, fill: { color: dark ? WHITE : NAVY }, line: { type: "none" },
  });
  slide.addText(num, {
    x: opts.x ?? 0.6, y: opts.y ?? 0.42, w: 0.42, h: 0.28,
    align: "center", valign: "middle", fontFace: FONT, fontSize: 10, bold: true,
    color: dark ? NAVY : WHITE,
  });
  slide.addText(label.toUpperCase(), {
    x: (opts.x ?? 0.6) + 0.52, y: opts.y ?? 0.42, w: 7, h: 0.28,
    fontFace: FONT, fontSize: 11, bold: true, charSpacing: 1,
    color: dark ? ICE : BLUE, valign: "middle",
  });
}

function pageNum(slide, n, dark = false) {
  slide.addText(`${n} / 15`, {
    x: W - 1.1, y: H - 0.42, w: 0.7, h: 0.28,
    fontFace: FONT, fontSize: 8.5, color: dark ? "9FB6CC" : "9AA7B5", align: "right",
  });
  slide.addText("CloudFinOps  ·  Confidential  ·  Seed Pitch Deck", {
    x: 0.6, y: H - 0.42, w: 5, h: 0.28,
    fontFace: FONT, fontSize: 8.5, color: dark ? "9FB6CC" : "9AA7B5",
  });
}

function lightBg(slide) { slide.background = { color: WHITE }; }

function miniLogo(slide) {
  try { slide.addImage({ path: LOGO, x: W - 0.85, y: 0.32, w: 0.42, h: 0.42 }); } catch {}
}

// ===================== SLIDE 1 — COVER =====================
{
  const s = pres.addSlide();
  s.background = { color: NAVY_DEEP };
  s.addShape(pres.shapes.OVAL, { x: 9.2, y: -2.5, w: 7.2, h: 7.2, fill: { color: "0F3358", transparency: 35 }, line: { type: "none" } });
  s.addShape(pres.shapes.OVAL, { x: 10.8, y: 3.8, w: 5.2, h: 5.2, fill: { color: GREEN, transparency: 88 }, line: { type: "none" } });
  try { s.addImage({ path: LOGO, x: 0.85, y: 0.85, w: 1.05, h: 1.0 }); } catch {}
  s.addText("CloudFinOps", { x: 2.05, y: 0.88, w: 6, h: 0.5, fontFace: FONT_HEAD, bold: true, fontSize: 22, color: WHITE });
  s.addText("AI CLOUD FINANCIAL INTELLIGENCE", { x: 2.05, y: 1.32, w: 6, h: 0.3, fontFace: FONT, fontSize: 10, charSpacing: 1.8, color: "9FB6CC" });

  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.85, y: 2.55, w: 4.55, h: 0.44, rectRadius: 0.22, fill: { color: "13314F" }, line: { color: GREEN, width: 1 } });
  s.addText("SEED ROUND  ·  2026  ·  CONFIDENTIAL", { x: 0.85, y: 2.55, w: 4.55, h: 0.44, align: "center", valign: "middle", fontFace: FONT, fontSize: 10.5, bold: true, color: "8BE0A0", charSpacing: 0.6 });

  s.addText("The AI financial layer\nfor multi-cloud\ninfrastructure.", { x: 0.82, y: 3.15, w: 10.5, h: 2.5, fontFace: FONT_HEAD, bold: true, fontSize: 42, color: WHITE, lineSpacing: 48 });

  s.addText("Unified visibility, AI-driven waste detection, and on-premises deployment for enterprises and governments running AWS, Azure, and GCP — across India and the Gulf.", { x: 0.85, y: 5.55, w: 9.2, h: 0.75, fontFace: FONT, fontSize: 13.5, color: "C7D6E5", lineSpacing: 19 });

  const badges = ["India", "UAE · Qatar (GCC)", "On-Premises Ready", "UDYAM Registered"];
  let bx = 0.85;
  badges.forEach((b) => {
    const tw = b.length * 0.082 + 0.4;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: bx, y: 6.7, w: tw, h: 0.4, rectRadius: 0.2, fill: { color: "0F2740" }, line: { color: "2A4A68", width: 1 } });
    s.addText(b, { x: bx, y: 6.7, w: tw, h: 0.4, align: "center", valign: "middle", fontFace: FONT, fontSize: 9.5, color: "9FB6CC" });
    bx += tw + 0.16;
  });
  pageNum(s, 1, true);
}

// ===================== SLIDE 2 — PROBLEM =====================
{
  const s = pres.addSlide(); lightBg(s); eyebrow(s, "01", "The Problem"); miniLogo(s);
  s.addText("Enterprises are bleeding cloud budget — and cannot see where.", { x: 0.6, y: 0.85, w: 11.6, h: 0.85, fontFace: FONT_HEAD, bold: true, fontSize: 26, color: NAVY_DEEP });
  s.addText("A bank spending ₹50 lakh/month across AWS, Azure, and GCP has no single view of where money goes. Nearly a third is wasted on idle GPUs, forgotten dev servers, and unused reservations — and finance notices months late.", { x: 0.6, y: 1.68, w: 11.6, h: 0.85, fontFace: FONT, fontSize: 12.8, color: "2C3846", lineSpacing: 17 });

  const pains = [
    { title: "Conflict of interest", body: "Native billing dashboards are built by the vendor selling infrastructure — no incentive to reduce your spend." },
    { title: "Bills too complex to audit", body: "Enterprise multi-cloud bills: 800–1,200+ line items across cryptic service codes. Manual review is impossible." },
    { title: "Data cannot leave the building", body: "BFSI, government, and GCC entities are legally barred from sending billing data to third-party SaaS." },
    { title: "AI/GPU spend broke forecasting", body: "98% of FinOps teams now manage AI workloads (up from 31% two years ago) — bursty GPU costs defeat reservations." },
  ];
  const cw = 2.85, startX = 0.6, startY = 2.75;
  pains.forEach((p, i) => {
    const x = startX + i * (cw + 0.22);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: startY, w: cw, h: 2.15, rectRadius: 0.09, fill: { color: WHITE }, line: { color: ICE_LINE, width: 1 } });
    s.addText(p.title, { x: x + 0.2, y: startY + 0.2, w: cw - 0.4, h: 0.55, fontFace: FONT, bold: true, fontSize: 11.5, color: NAVY_DEEP, lineSpacing: 13 });
    s.addText(p.body, { x: x + 0.2, y: startY + 0.75, w: cw - 0.4, h: 1.2, fontFace: FONT, fontSize: 9.6, color: SLATE, lineSpacing: 12 });
  });

  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.6, y: 5.15, w: 12.15, h: 0.95, rectRadius: 0.09, fill: { color: ROSE_SOFT }, line: { color: "F0C6C6", width: 1 } });
  s.addText("29% of cloud spend was wasted in 2026 — the first increase in five years, driven by AI and GPU workloads breaking traditional forecasting.  (Flexera, State of the Cloud 2026)", { x: 0.85, y: 5.15, w: 11.65, h: 0.95, valign: "middle", fontFace: FONT, fontSize: 12, color: "2C3846", lineSpacing: 16 });
  pageNum(s, 2);
}

// ===================== SLIDE 3 — WHY NOW =====================
{
  const s = pres.addSlide(); lightBg(s); eyebrow(s, "02", "Why Now"); miniLogo(s);
  s.addText("Three forces converging in 2026 — all point to us.", { x: 0.6, y: 0.85, w: 11.6, h: 0.75, fontFace: FONT_HEAD, bold: true, fontSize: 25, color: NAVY_DEEP });

  const forces = [
    { tag: "REGULATION", title: "India’s DPDPA is a board-level deadline", body: "Rules took force Nov 2025. Full enforcement from May 2027 with ₹250Cr penalties. Enterprises must know exactly where data lives." },
    { tag: "SOVEREIGNTY", title: "The Gulf mandates sovereign cloud", body: "Abu Dhabi’s AED 13B Digital Strategy requires 100% sovereign workloads by 2027. Qatar positioning as regional hub. On-prem is policy." },
    { tag: "AI WASTE", title: "AI workloads broke the old playbook", body: "Cloud waste rose to 29% in 2026 — first increase in 5 years. GPU-heavy, bursty inference defeated static reservation models." },
  ];
  const cw = 3.95, startX = 0.6, startY = 1.75;
  forces.forEach((f, i) => {
    const x = startX + i * (cw + 0.15);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: startY, w: cw, h: 3.3, rectRadius: 0.1, fill: { color: ICE }, line: { color: ICE_LINE, width: 1 } });
    s.addText(f.tag, { x: x + 0.24, y: startY + 0.3, w: cw - 0.48, h: 0.24, fontFace: FONT, bold: true, fontSize: 9, charSpacing: 1, color: BLUE });
    s.addText(f.title, { x: x + 0.24, y: startY + 0.6, w: cw - 0.48, h: 0.68, fontFace: FONT, bold: true, fontSize: 13, color: NAVY_DEEP, lineSpacing: 15 });
    s.addText(f.body, { x: x + 0.24, y: startY + 1.35, w: cw - 0.48, h: 1.8, fontFace: FONT, fontSize: 10, color: SLATE, lineSpacing: 13 });
  });

  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.6, y: 5.3, w: 12.15, h: 0.85, rectRadius: 0.09, fill: { color: NAVY_DEEP }, line: { type: "none" } });
  s.addText("Regulation forces data local. AI makes waste bigger. We built for exactly this moment.", { x: 0.9, y: 5.3, w: 11.5, h: 0.85, valign: "middle", fontFace: FONT, fontSize: 13, color: WHITE, lineSpacing: 17 });
  pageNum(s, 3);
}

// ===================== SLIDE 4 — SOLUTION =====================
{
  const s = pres.addSlide(); lightBg(s); eyebrow(s, "03", "The Solution"); miniLogo(s);
  s.addText("One AI-native command center. Deployed wherever your data must live.", { x: 0.6, y: 0.85, w: 11.8, h: 0.85, fontFace: FONT_HEAD, bold: true, fontSize: 24, color: NAVY_DEEP });

  const colW = 5.9, colY = 1.9, colH = 3.0;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.6, y: colY, w: colW, h: colH, rectRadius: 0.1, fill: { color: ROSE_SOFT }, line: { color: "F0C6C6", width: 1 } });
  s.addText("BEFORE", { x: 0.85, y: colY + 0.2, w: 2, h: 0.3, fontFace: FONT, bold: true, fontSize: 11, color: "9C2B2B", charSpacing: 1 });
  const befores = ["5+ disconnected dashboards per provider", "Waste found in quarterly reviews — months late", "No accountability — untagged ownerless resources", "Regulated data can’t touch third-party SaaS", "GPU spend is a black box"];
  let by = colY + 0.6;
  befores.forEach((b) => { s.addText("✗  " + b, { x: 0.85, y: by, w: colW - 0.5, h: 0.42, fontFace: FONT, fontSize: 10.6, color: "2C3846" }); by += 0.44; });

  const ax0 = 6.85;
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: ax0, y: colY, w: colW, h: colH, rectRadius: 0.1, fill: { color: GREEN_SOFT }, line: { color: "BFE3C6", width: 1 } });
  s.addText("AFTER — WITH CLOUDFINOPS", { x: ax0 + 0.25, y: colY + 0.2, w: colW - 0.5, h: 0.3, fontFace: FONT, bold: true, fontSize: 11, color: "237A34", charSpacing: 1 });
  const afters = ["One dashboard, all providers, role-based views", "Same-day AI waste detection with remediation scripts", "Every resource owned, tagged, and audit-ready", "On-premises / air-gapped — zero data egress", "GPU Intelligence: ghost GPU + MIG detection"];
  let ay = colY + 0.6;
  afters.forEach((a) => { s.addText("✓  " + a, { x: ax0 + 0.25, y: ay, w: colW - 0.5, h: 0.42, fontFace: FONT, fontSize: 10.6, color: "2C3846" }); ay += 0.44; });

  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.6, y: 5.15, w: 12.15, h: 0.85, rectRadius: 0.09, fill: { color: NAVY_DEEP }, line: { type: "none" } });
  s.addText("CloudFinOps turns cloud cost from a quarterly surprise into a same-day, self-service, deployable-anywhere discipline.", { x: 0.9, y: 5.15, w: 11.5, h: 0.85, valign: "middle", fontFace: FONT, fontSize: 13, color: WHITE });
  pageNum(s, 4);
}

// ===================== SLIDE 5 — PRODUCT =====================
{
  const s = pres.addSlide(); lightBg(s); eyebrow(s, "04", "Product"); miniLogo(s);
  s.addText("From a read-only IAM key to a remediation script — in one flow.", { x: 0.6, y: 0.85, w: 11.8, h: 0.75, fontFace: FONT_HEAD, bold: true, fontSize: 24, color: NAVY_DEEP });
  s.addText("No agents to install, no pipelines to maintain, no dedicated cloud engineer required.", { x: 0.6, y: 1.55, w: 11.6, h: 0.4, fontFace: FONT, fontSize: 12.5, color: SLATE });

  const steps = [
    { n: "01", title: "Connect", body: "A single read-only IAM role. No standing write access, ever." },
    { n: "02", title: "Scan", body: "Continuous discovery across AWS, Azure, GCP — every region, every resource type." },
    { n: "03", title: "Analyze", body: "AI parses bills, detects waste same-day, forecasts spend with statistical models." },
    { n: "04", title: "Act", body: "Ranked remediation scripts, governance enforcement, role-based dashboards." },
  ];
  const stw = 2.85, startX = 0.6, sty = 2.25;
  steps.forEach((st, i) => {
    const x = startX + i * (stw + 0.2);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: sty, w: stw, h: 2.7, rectRadius: 0.1, fill: { color: ICE }, line: { color: ICE_LINE, width: 1 } });
    s.addShape(pres.shapes.OVAL, { x: x + 0.22, y: sty + 0.22, w: 0.55, h: 0.55, fill: { color: NAVY }, line: { type: "none" } });
    s.addText(st.n, { x: x + 0.22, y: sty + 0.22, w: 0.55, h: 0.55, align: "center", valign: "middle", fontFace: FONT, bold: true, fontSize: 14, color: WHITE });
    s.addText(st.title, { x: x + 0.22, y: sty + 0.92, w: stw - 0.44, h: 0.4, fontFace: FONT, bold: true, fontSize: 15, color: NAVY_DEEP });
    s.addText(st.body, { x: x + 0.22, y: sty + 1.35, w: stw - 0.44, h: 1.2, fontFace: FONT, fontSize: 10.3, color: SLATE, lineSpacing: 13.5 });
  });

  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.6, y: 5.2, w: 12.15, h: 1.0, rectRadius: 0.09, fill: { color: GREEN_SOFT }, line: { color: "BFE3C6", width: 1 } });
  s.addText("Zero operational overhead: no dedicated DevOps hire required. Any team member — finance, IT, or leadership — can operate the platform from day one.", { x: 0.9, y: 5.2, w: 11.5, h: 1.0, valign: "middle", fontFace: FONT, fontSize: 12, color: "2C3846", lineSpacing: 16 });
  pageNum(s, 5);
}

// ===================== SLIDE 6 — WHY WE WIN =====================
{
  const s = pres.addSlide(); lightBg(s); eyebrow(s, "05", "Why We Win"); miniLogo(s);
  s.addText("Built with a moat competitors need years to replicate.", { x: 0.6, y: 0.85, w: 11.8, h: 0.75, fontFace: FONT_HEAD, bold: true, fontSize: 25, color: NAVY_DEEP });

  const moats = [
    { title: "GPU Intelligence", body: "Ghost GPU detection, NVIDIA MIG advisory, GPU-cloud arbitrage — a category no mainstream FinOps platform addresses." },
    { title: "On-Premises / Air-Gapped", body: "Full platform runs inside a customer’s environment. Zero data egress — built for regulated and sovereign-cloud buyers." },
    { title: "AI Bill PDF Intelligence", body: "Reads complex multi-page provider bills the way a human analyst would — no manual line-item reconciliation." },
    { title: "India + GCC Compliance DNA", body: "Built from day one for DPDPA, RBI, and Gulf sovereign-cloud mandates — not a US-first tool with compliance bolted on." },
  ];
  const cw = 5.9, ch = 2.0, startX = 0.6, startY = 1.75;
  moats.forEach((m, i) => {
    const col = i % 2, row = Math.floor(i / 2);
    const x = startX + col * (cw + 0.35);
    const y = startY + row * (ch + 0.25);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: cw, h: ch, rectRadius: 0.1, fill: { color: WHITE }, line: { color: ICE_LINE, width: 1 } });
    s.addText(m.title, { x: x + 0.25, y: y + 0.2, w: cw - 0.5, h: 0.4, fontFace: FONT, bold: true, fontSize: 14, color: NAVY_DEEP });
    s.addText(m.body, { x: x + 0.25, y: y + 0.65, w: cw - 0.5, h: 1.2, fontFace: FONT, fontSize: 10.6, color: SLATE, lineSpacing: 14 });
  });
  pageNum(s, 6);
}

// ===================== SLIDE 7 — MARKET SIZE =====================
{
  const s = pres.addSlide(); lightBg(s); eyebrow(s, "06", "Market Size"); miniLogo(s);
  s.addText("A large market, sized the way we will actually capture it.", { x: 0.6, y: 0.85, w: 11.8, h: 0.75, fontFace: FONT_HEAD, bold: true, fontSize: 25, color: NAVY_DEEP });
  s.addText("Bottom-up, tied to our pricing tiers — not a top-down industry fantasy.", { x: 0.6, y: 1.55, w: 11.6, h: 0.4, fontFace: FONT, fontSize: 12.5, color: SLATE });

  const rows = [
    { label: "TAM", value: "US$ 15.8B", sub: "Global Cloud FinOps software market, 2026 → $24.9B by 2031", w: 10.5, color: NAVY, y: 2.25 },
    { label: "SAM", value: "US$ 72M", sub: "~3,000 enterprises in India + GCC with monthly cloud spend above ₹15L", w: 7.2, color: BLUE, y: 3.35 },
    { label: "SOM", value: "US$ 3.6M ARR", sub: "150 customers by Year 3 (5% of SAM) at blended ~$24K ACV", w: 4.2, color: GREEN, y: 4.45 },
  ];
  const centerX = W / 2;
  rows.forEach((r) => {
    const x = centerX - r.w / 2;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: r.y, w: r.w, h: 0.85, rectRadius: 0.1, fill: { color: r.color }, line: { type: "none" } });
    s.addText(r.label + "  " + r.value, { x: x + 0.25, y: r.y, w: 3, h: 0.85, valign: "middle", fontFace: FONT_HEAD, bold: true, fontSize: 17, color: WHITE });
    s.addText(r.sub, { x: x + 3.2, y: r.y, w: r.w - 3.5, h: 0.85, valign: "middle", fontFace: FONT, fontSize: 10, color: "E8F1FA", lineSpacing: 12 });
  });

  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.6, y: 5.55, w: 12.15, h: 1.0, rectRadius: 0.09, fill: { color: ICE }, line: { color: ICE_LINE, width: 1 } });
  s.addText("Sources: Global FinOps market from Mordor Intelligence (2026). SAM built bottom-up: addressable org count × blended ACV from our tier pricing. SOM assumes 5% penetration — conservative for a focused vertical player.", { x: 0.85, y: 5.55, w: 11.65, h: 1.0, valign: "middle", fontFace: FONT, fontSize: 10, color: "2C3846", lineSpacing: 13 });
  pageNum(s, 7);
}

// ===================== SLIDE 8 — BUSINESS MODEL =====================
{
  const s = pres.addSlide(); lightBg(s); eyebrow(s, "07", "Business Model"); miniLogo(s);
  s.addText("Annual license, priced to cloud spend — not headcount.", { x: 0.6, y: 0.85, w: 11.8, h: 0.75, fontFace: FONT_HEAD, bold: true, fontSize: 24, color: NAVY_DEEP });
  s.addText("One number — monthly cloud spend across AWS + Azure + GCP — determines the tier. Full platform included at every tier.", { x: 0.6, y: 1.6, w: 11.8, h: 0.5, fontFace: FONT, fontSize: 12.3, color: "2C3846" });

  const tiers = [
    { name: "Starter", spend: "Up to ₹15L/mo", license: "₹10–12L/year", tag: "SMB & mid-market", color: NAVY },
    { name: "Growth", spend: "₹15L–₹50L/mo", license: "₹15–22L/year", tag: "Scaling enterprise", color: BLUE },
    { name: "Enterprise", spend: "₹50L–₹1.5Cr/mo", license: "₹30–45L/year", tag: "Large enterprise & PSU", color: "0F5499" },
  ];
  const cw = 3.85, startX = 0.6, startY = 2.5;
  tiers.forEach((t, i) => {
    const x = startX + i * (cw + 0.3);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: startY, w: cw, h: 2.9, rectRadius: 0.1, fill: { color: WHITE }, line: { color: ICE_LINE, width: 1 } });
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: startY, w: cw, h: 0.7, rectRadius: 0.1, fill: { color: t.color }, line: { type: "none" } });
    s.addShape(pres.shapes.RECTANGLE, { x, y: startY + 0.35, w: cw, h: 0.35, fill: { color: t.color }, line: { type: "none" } });
    s.addText(t.name, { x: x + 0.22, y: startY + 0.12, w: cw - 0.44, h: 0.35, fontFace: FONT, bold: true, fontSize: 16, color: WHITE });
    s.addText(t.tag, { x: x + 0.22, y: startY + 0.44, w: cw - 0.44, h: 0.24, fontFace: FONT, fontSize: 9, color: "D6E6F5" });
    s.addText(t.spend, { x: x + 0.22, y: startY + 0.88, w: cw - 0.44, h: 0.5, fontFace: FONT, fontSize: 10.6, color: SLATE });
    s.addText("Annual license", { x: x + 0.22, y: startY + 1.5, w: cw - 0.44, h: 0.24, fontFace: FONT, fontSize: 9, color: SLATE });
    s.addText(t.license, { x: x + 0.22, y: startY + 1.74, w: cw - 0.44, h: 0.4, fontFace: FONT_HEAD, bold: true, fontSize: 18, color: NAVY_DEEP });
    s.addText("+ ₹1L onboarding (flat, one-time)", { x: x + 0.22, y: startY + 2.2, w: cw - 0.44, h: 0.3, fontFace: FONT, fontSize: 9.3, italic: true, color: SLATE });
  });

  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.6, y: 5.7, w: 12.15, h: 0.75, rectRadius: 0.09, fill: { color: GREEN_SOFT }, line: { color: "BFE3C6", width: 1 } });
  s.addText("High-margin SaaS/license model. Land via zero-risk bill audit → paid pilot → annual license.", { x: 0.9, y: 5.7, w: 11.5, h: 0.75, valign: "middle", fontFace: FONT, fontSize: 12, color: "2C3846" });
  pageNum(s, 8);
}

// ===================== SLIDE 9 — GO-TO-MARKET =====================
{
  const s = pres.addSlide(); lightBg(s); eyebrow(s, "08", "Go-To-Market"); miniLogo(s);
  s.addText("Beachhead first. Expand where our moat matters most.", { x: 0.6, y: 0.85, w: 11.8, h: 0.75, fontFace: FONT_HEAD, bold: true, fontSize: 25, color: NAVY_DEEP });

  const phases = [
    { n: "PHASE 1", title: "India — BFSI, PSU & Government", body: "Direct enterprise sales + TBI NIT Jalandhar mentor network. On-premises edition removes the #1 blocker for regulated buyers.", color: NAVY },
    { n: "PHASE 2", title: "India — Enterprise Expansion", body: "SI partnerships and GeM empanelment to scale beyond direct-sales reach.", color: BLUE },
    { n: "PHASE 3", title: "GCC — UAE & Qatar", body: "Sovereign-cloud mandates align directly with our on-premises, zero-egress architecture.", color: GREEN },
  ];
  const cw = 3.95, startX = 0.6, startY = 1.75;
  phases.forEach((p, i) => {
    const x = startX + i * (cw + 0.15);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: startY, w: cw, h: 2.35, rectRadius: 0.1, fill: { color: ICE }, line: { color: ICE_LINE, width: 1 } });
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: x + 0.22, y: startY + 0.2, w: 1.05, h: 0.32, rectRadius: 0.16, fill: { color: p.color }, line: { type: "none" } });
    s.addText(p.n, { x: x + 0.22, y: startY + 0.2, w: 1.05, h: 0.32, align: "center", valign: "middle", fontFace: FONT, bold: true, fontSize: 9, color: WHITE });
    s.addText(p.title, { x: x + 0.22, y: startY + 0.62, w: cw - 0.44, h: 0.65, fontFace: FONT, bold: true, fontSize: 13, color: NAVY_DEEP, lineSpacing: 15 });
    s.addText(p.body, { x: x + 0.22, y: startY + 1.28, w: cw - 0.44, h: 1.0, fontFace: FONT, fontSize: 10, color: SLATE, lineSpacing: 13 });
  });

  s.addText("Land-and-expand: Zero-risk bill audit → Paid pilot → Annual license", { x: 0.6, y: 4.35, w: 12, h: 0.4, fontFace: FONT, bold: true, fontSize: 13, color: NAVY_DEEP });
  pageNum(s, 9);
}

// ===================== SLIDE 10 — COMPETITION =====================
{
  const s = pres.addSlide(); lightBg(s); eyebrow(s, "09", "Competition"); miniLogo(s);
  s.addText("We compete against tools not built for this moment.", { x: 0.6, y: 0.85, w: 11.8, h: 0.75, fontFace: FONT_HEAD, bold: true, fontSize: 25, color: NAVY_DEEP });

  const tdata = [
    [{ text: "Capability", options: { bold: true, color: WHITE, fill: { color: NAVY_DEEP } } }, { text: "Native\nHyperscaler", options: { bold: true, color: WHITE, fill: { color: NAVY_DEEP } } }, { text: "Global FinOps\nSaaS", options: { bold: true, color: WHITE, fill: { color: NAVY_DEEP } } }, { text: "CloudFinOps", options: { bold: true, color: WHITE, fill: { color: GREEN } } }],
    [{ text: "True multi-cloud (AWS+Azure+GCP)" }, { text: "✗", options: { color: ROSE, align: "center" } }, { text: "✓", options: { color: GREEN, align: "center" } }, { text: "✓", options: { color: GREEN, align: "center", bold: true } }],
    [{ text: "On-Premises / Air-Gapped" }, { text: "✗", options: { color: ROSE, align: "center" } }, { text: "✗", options: { color: ROSE, align: "center" } }, { text: "✓", options: { color: GREEN, align: "center", bold: true } }],
    [{ text: "AI bill PDF analysis" }, { text: "✗", options: { color: ROSE, align: "center" } }, { text: "~", options: { color: AMBER, align: "center" } }, { text: "✓", options: { color: GREEN, align: "center", bold: true } }],
    [{ text: "GPU Intelligence (ghost GPU + MIG)" }, { text: "✗", options: { color: ROSE, align: "center" } }, { text: "✗", options: { color: ROSE, align: "center" } }, { text: "✓", options: { color: GREEN, align: "center", bold: true } }],
    [{ text: "India + GCC compliance-first" }, { text: "✗", options: { color: ROSE, align: "center" } }, { text: "✗", options: { color: ROSE, align: "center" } }, { text: "✓", options: { color: GREEN, align: "center", bold: true } }],
    [{ text: "Actionable remediation scripts" }, { text: "✗", options: { color: ROSE, align: "center" } }, { text: "~", options: { color: AMBER, align: "center" } }, { text: "✓", options: { color: GREEN, align: "center", bold: true } }],
  ];
  tdata.forEach((row) => row.forEach((cell) => { cell.options = { ...cell.options, fontFace: FONT, fontSize: 11, valign: "middle" }; }));

  s.addTable(tdata, { x: 0.6, y: 1.8, w: 12.15, h: 3.8, border: { pt: 0.5, color: ICE_LINE }, colW: [5.5, 2.2, 2.2, 2.25], rowH: [0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5] });

  s.addText("✓ Full   ~ Partial   ✗ Not offered", { x: 0.6, y: 5.8, w: 12, h: 0.4, fontFace: FONT, fontSize: 10.5, color: SLATE });
  pageNum(s, 10);
}

// ===================== SLIDE 11 — TRACTION =====================
{
  const s = pres.addSlide(); lightBg(s); eyebrow(s, "10", "Traction"); miniLogo(s);
  s.addText("Early, real, and validated — not vaporware.", { x: 0.6, y: 0.85, w: 11.8, h: 0.75, fontFace: FONT_HEAD, bold: true, fontSize: 26, color: NAVY_DEEP });

  const items = [
    { title: "Full platform built and live", body: "15+ modules shipped: multi-cloud dashboard, governance, security, GPU Intelligence, AI bill scanner, Terraform simulator." },
    { title: "Active enterprise evaluation — IFFCO", body: "In technical discussions for on-premises, zero-egress deployment with a major Indian financial institution." },
    { title: "Incubated at TBI NIT Jalandhar", body: "Formal incubation with structured mentorship and path to government funding schemes." },
    { title: "UDYAM registered MSME", body: "Procurement-ready for government and enterprise contracting (UDYAM-PB-20-0114306)." },
  ];
  const cw = 5.9, ch = 1.85, startX = 0.6, startY = 1.85;
  items.forEach((it, i) => {
    const col = i % 2, row = Math.floor(i / 2);
    const x = startX + col * (cw + 0.35);
    const y = startY + row * (ch + 0.25);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: cw, h: ch, rectRadius: 0.1, fill: { color: WHITE }, line: { color: ICE_LINE, width: 1 } });
    s.addText(it.title, { x: x + 0.25, y: y + 0.2, w: cw - 0.5, h: 0.4, fontFace: FONT, bold: true, fontSize: 12.5, color: NAVY_DEEP });
    s.addText(it.body, { x: x + 0.25, y: y + 0.65, w: cw - 0.5, h: 1.0, fontFace: FONT, fontSize: 10, color: SLATE, lineSpacing: 13 });
  });

  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.6, y: 5.95, w: 12.15, h: 0.7, rectRadius: 0.08, fill: { color: NAVY_DEEP }, line: { type: "none" } });
  s.addText("Validated by: Rajiv Sikka (ex-CEO, IndianOil–Adani Gas) and Sanjay Kumar Suri (ex-CISO, BPCL) via TBI NIT Jalandhar mentor network.", { x: 0.9, y: 5.95, w: 11.5, h: 0.7, valign: "middle", fontFace: FONT, fontSize: 10.8, color: "C7D6E5" });
  pageNum(s, 11);
}

// ===================== SLIDE 12 — ROADMAP =====================
{
  const s = pres.addSlide(); lightBg(s); eyebrow(s, "11", "Roadmap"); miniLogo(s);
  s.addText("The next 24 months.", { x: 0.6, y: 0.85, w: 11.8, h: 0.75, fontFace: FONT_HEAD, bold: true, fontSize: 26, color: NAVY_DEEP });

  const milestones = [
    { when: "NOW", title: "Platform live", body: "Full product shipped. IFFCO pilot discussions. TBI incubation active.", color: NAVY },
    { when: "+6 MO", title: "First paid contracts", body: "Convert pilot(s) to annual licenses. Begin SOC2-track hardening.", color: BLUE },
    { when: "+12 MO", title: "GCC market entry", body: "First UAE/Qatar pilot aligned with sovereign-cloud mandates.", color: AMBER },
    { when: "+24 MO", title: "Series A ready", body: "100+ enterprise customers across India and GCC. Repeatable GTM proven.", color: GREEN },
  ];
  const mw = 2.85, startX = 0.6, startY = 2.0;
  milestones.forEach((m, i) => {
    const x = startX + i * (mw + 0.18);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: startY, w: mw, h: 3.2, rectRadius: 0.1, fill: { color: ICE }, line: { color: ICE_LINE, width: 1 } });
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: x + 0.18, y: startY + 0.2, w: mw - 0.36, h: 0.32, rectRadius: 0.16, fill: { color: m.color }, line: { type: "none" } });
    s.addText(m.when, { x: x + 0.18, y: startY + 0.2, w: mw - 0.36, h: 0.32, align: "center", valign: "middle", fontFace: FONT, bold: true, fontSize: 9.5, color: WHITE });
    s.addText(m.title, { x: x + 0.18, y: startY + 0.7, w: mw - 0.36, h: 0.5, fontFace: FONT, bold: true, fontSize: 12.5, color: NAVY_DEEP });
    s.addText(m.body, { x: x + 0.18, y: startY + 1.25, w: mw - 0.36, h: 1.8, fontFace: FONT, fontSize: 9.8, color: SLATE, lineSpacing: 12.5 });
  });
  pageNum(s, 12);
}

// ===================== SLIDE 13 — TEAM =====================
{
  const s = pres.addSlide(); lightBg(s); eyebrow(s, "12", "Team"); miniLogo(s);
  s.addText("Two founders. One obsession. Zero fluff.", { x: 0.6, y: 0.85, w: 11.8, h: 0.75, fontFace: FONT_HEAD, bold: true, fontSize: 26, color: NAVY_DEEP });

  const founders = [
    { name: "Nishant Jain", role: "Co-Founder & CTO", points: ["Built entire platform solo — 15+ modules, frontend + backend + AI + infra", "Full-stack: Next.js, FastAPI, MongoDB, GCP, Gemini AI, Docker", "Security-first: conducted internal audit, fixed SSRF, XSS, CORS, CSP"], fit: "Technical depth to build enterprise-grade infra software without a 20-person team." },
    { name: "Sambhav Pal", role: "Co-Founder & CEO", points: ["Enterprise BD and fundraising pipeline", "Secured TBI NIT Jalandhar incubation", "Managing IFFCO Finance pilot conversation"], fit: "Enterprise relationships and commercial execution to convert tech into revenue." },
  ];
  const cw = 5.9, ch = 3.2, startX = 0.6, startY = 1.85;
  founders.forEach((f, i) => {
    const x = startX + i * (cw + 0.35);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: startY, w: cw, h: ch, rectRadius: 0.1, fill: { color: WHITE }, line: { color: ICE_LINE, width: 1 } });
    s.addShape(pres.shapes.OVAL, { x: x + 0.28, y: startY + 0.28, w: 0.62, h: 0.62, fill: { color: ICE }, line: { color: BLUE, width: 1.5 } });
    s.addText(f.name[0], { x: x + 0.28, y: startY + 0.28, w: 0.62, h: 0.62, align: "center", valign: "middle", fontFace: FONT_HEAD, bold: true, fontSize: 20, color: NAVY });
    s.addText(f.name, { x: x + 1.05, y: startY + 0.3, w: cw - 1.3, h: 0.32, fontFace: FONT, bold: true, fontSize: 15, color: NAVY_DEEP });
    s.addText(f.role, { x: x + 1.05, y: startY + 0.6, w: cw - 1.3, h: 0.28, fontFace: FONT, fontSize: 10.5, color: BLUE, bold: true });
    let py = startY + 1.05;
    f.points.forEach((p) => { s.addText("•  " + p, { x: x + 0.28, y: py, w: cw - 0.56, h: 0.4, fontFace: FONT, fontSize: 9.8, color: "2C3846", lineSpacing: 12 }); py += 0.42; });
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: x + 0.22, y: startY + ch - 0.55, w: cw - 0.44, h: 0.4, rectRadius: 0.06, fill: { color: ICE }, line: { type: "none" } });
    s.addText(f.fit, { x: x + 0.35, y: startY + ch - 0.55, w: cw - 0.7, h: 0.4, fontFace: FONT, italic: true, fontSize: 9, color: NAVY, valign: "middle" });
  });

  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.6, y: 5.3, w: 12.15, h: 0.7, rectRadius: 0.08, fill: { color: NAVY_DEEP }, line: { type: "none" } });
  s.addText("Advisory: Rajiv Sikka (ex-CEO, IndianOil–Adani Gas), Sanjay Kumar Suri (ex-CISO BPCL), senior FinOps practitioners from Zenoti ($40M cloud) and Revvity.", { x: 0.9, y: 5.3, w: 11.5, h: 0.7, valign: "middle", fontFace: FONT, fontSize: 10.5, color: "C7D6E5" });
  pageNum(s, 13);
}

// ===================== SLIDE 14 — THE ASK =====================
{
  const s = pres.addSlide(); lightBg(s); eyebrow(s, "13", "The Ask"); miniLogo(s);
  s.addText("Raising ₹2.5 Crore (~US $300K) to land 10 enterprise customers.", { x: 0.6, y: 0.85, w: 11.8, h: 0.75, fontFace: FONT_HEAD, bold: true, fontSize: 24, color: NAVY_DEEP });
  s.addText("Bridges us from “product built, pilot in progress” to “repeatable enterprise revenue” within 12 months.", { x: 0.6, y: 1.6, w: 11.6, h: 0.5, fontFace: FONT, fontSize: 12.5, color: SLATE });

  const funds = [
    { pct: "40%", label: "Enterprise Sales & GTM", detail: "BD hires for India + GCC. Conferences. Partner onboarding.", color: NAVY },
    { pct: "30%", label: "Engineering & Product", detail: "SOC2 prep, on-prem hardening, AI model improvements.", color: BLUE },
    { pct: "15%", label: "GCC Market Entry", detail: "Qatar/UAE entity, local partnerships, certifications.", color: GREEN },
    { pct: "15%", label: "Operations & Runway", detail: "Legal, infra costs, 18-month operational buffer.", color: AMBER },
  ];
  const cw = 2.85, startX = 0.6, startY = 2.3;
  funds.forEach((f, i) => {
    const x = startX + i * (cw + 0.2);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: startY, w: cw, h: 2.4, rectRadius: 0.1, fill: { color: WHITE }, line: { color: ICE_LINE, width: 1 } });
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: startY, w: cw, h: 0.65, rectRadius: 0.1, fill: { color: f.color }, line: { type: "none" } });
    s.addShape(pres.shapes.RECTANGLE, { x, y: startY + 0.35, w: cw, h: 0.3, fill: { color: f.color }, line: { type: "none" } });
    s.addText(f.pct, { x, y: startY + 0.08, w: cw, h: 0.45, align: "center", fontFace: FONT_HEAD, bold: true, fontSize: 20, color: WHITE });
    s.addText(f.label, { x: x + 0.2, y: startY + 0.8, w: cw - 0.4, h: 0.5, fontFace: FONT, bold: true, fontSize: 11, color: NAVY_DEEP });
    s.addText(f.detail, { x: x + 0.2, y: startY + 1.35, w: cw - 0.4, h: 0.9, fontFace: FONT, fontSize: 9.6, color: SLATE, lineSpacing: 12 });
  });

  // Key metrics
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.6, y: 5.0, w: 12.15, h: 1.2, rectRadius: 0.09, fill: { color: ICE }, line: { color: ICE_LINE, width: 1 } });
  const metrics = [
    { label: "Raise", value: "₹2.5 Cr" },
    { label: "Runway", value: "18 months" },
    { label: "Target", value: "10 customers" },
    { label: "Break-even", value: "Month 14" },
  ];
  metrics.forEach((m, i) => {
    const x = 0.85 + i * 3.05;
    s.addText(m.label, { x, y: 5.15, w: 2.8, h: 0.28, fontFace: FONT, fontSize: 9.5, color: SLATE, bold: true });
    s.addText(m.value, { x, y: 5.42, w: 2.8, h: 0.45, fontFace: FONT_HEAD, bold: true, fontSize: 20, color: NAVY_DEEP });
  });
  pageNum(s, 14);
}

// ===================== SLIDE 15 — VISION (CLOSING) =====================
{
  const s = pres.addSlide();
  s.background = { color: NAVY_DEEP };
  s.addShape(pres.shapes.OVAL, { x: -2.0, y: -2.5, w: 6.5, h: 6.5, fill: { color: "0F3358", transparency: 35 }, line: { type: "none" } });
  s.addShape(pres.shapes.OVAL, { x: 9.5, y: 4.0, w: 5.5, h: 5.5, fill: { color: GREEN, transparency: 88 }, line: { type: "none" } });

  try { s.addImage({ path: LOGO, x: 0.85, y: 0.85, w: 0.85, h: 0.82 }); } catch {}
  s.addText("CloudFinOps", { x: 1.85, y: 0.88, w: 4, h: 0.42, fontFace: FONT_HEAD, bold: true, fontSize: 18, color: WHITE });

  s.addText("Every enterprise deserves to know\nexactly where its cloud budget goes —\nand act on it the same day.", { x: 0.85, y: 2.0, w: 11.5, h: 2.2, fontFace: FONT_HEAD, bold: true, fontSize: 36, color: WHITE, lineSpacing: 42 });

  s.addText("The financial intelligence layer for multi-cloud infrastructure — deployed wherever data sovereignty demands, powered by AI that finds what humans miss.", { x: 0.85, y: 4.3, w: 10.5, h: 0.75, fontFace: FONT, fontSize: 13.5, color: "C7D6E5", lineSpacing: 19 });

  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 0.85, y: 5.5, w: 6.5, h: 1.1, rectRadius: 0.1, fill: { color: "0F2740" }, line: { color: "2A4A68", width: 1 } });
  s.addText("cloudfinops.solutions\nNishant Jain, CTO  ·  nishant@cloudfinops.solutions\nSambhav Pal, CEO  ·  sambhav@cloudfinops.solutions", { x: 1.05, y: 5.6, w: 6.1, h: 0.9, fontFace: FONT, fontSize: 11, color: "9FB6CC", lineSpacing: 15 });

  const ctas = ["Let’s talk", "Request demo", "Pilot ready"];
  let cx = 8.0;
  ctas.forEach((c) => {
    const tw = c.length * 0.09 + 0.5;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: cx, y: 5.75, w: tw, h: 0.42, rectRadius: 0.21, fill: { color: GREEN }, line: { type: "none" } });
    s.addText(c, { x: cx, y: 5.75, w: tw, h: 0.42, align: "center", valign: "middle", fontFace: FONT, bold: true, fontSize: 10, color: WHITE });
    cx += tw + 0.15;
  });
  pageNum(s, 15, true);
}

// ===================== GENERATE =====================
pres.writeFile({ fileName: "CloudFinOps_Seed_Pitch_Deck.pptx" })
  .then(() => console.log("\n✅ Generated: CloudFinOps_Seed_Pitch_Deck.pptx"))
  .catch((err) => console.error("Error:", err));
