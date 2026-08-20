const {
  pres, W, H, NAVY_DEEP, NAVY, BLUE, ICE, ICE_LINE, GREEN, GREEN_SOFT,
  SLATE, INK, WHITE, AMBER, ROSE, ROSE_SOFT, FONT, FONT_HEAD, ICON, LOGO,
  eyebrow, pageNum, lightBg, miniLogo,
} = require("./build_part1.js");

// =====================================================================
// SLIDE 13 — TEAM
// =====================================================================
{
  const s = pres.addSlide();
  lightBg(s);
  eyebrow(s, "12", "Team");
  miniLogo(s);

  s.addText("Two founders. One obsession. Zero fluff.", {
    x: 0.6, y: 0.85, w: 11.8, h: 0.75, fontFace: FONT_HEAD, bold: true,
    fontSize: 26, color: NAVY_DEEP,
  });
  s.addText(
    "A technical founder who built the entire platform solo, paired with a business founder " +
    "driving enterprise relationships and capital strategy.",
    { x: 0.6, y: 1.55, w: 11.6, h: 0.5, fontFace: FONT, fontSize: 12.5, color: SLATE, lineSpacing: 16 }
  );

  const founders = [
    {
      name: "Nishant Jain",
      role: "Co-Founder & CTO",
      photo: "nishant.png",
      points: [
        "Built the full platform solo — 15+ modules, 50K+ lines across frontend, backend, AI, and infra",
        "Full-stack: Next.js, FastAPI, MongoDB, GCP Cloud Run, Gemini AI, Docker",
        "Shipped multi-cloud scanning, GPU intelligence, AI bill parser, governance engine, and on-premises edition",
        "Security-first: conducted internal audit, fixed SSRF, XSS, CORS, CSP vulnerabilities",
      ],
      fit: "Why him: Technical depth to build enterprise-grade infrastructure software without a 20-person team.",
    },
    {
      name: "Sambhav Pal",
      role: "Co-Founder & CEO",
      photo: "sambhav.png",
      points: [
        "Driving enterprise business development and fundraising pipeline",
        "Secured TBI NIT Jalandhar incubation with mentor network access",
        "Managing IFFCO Finance on-premises pilot conversation",
        "Capital strategy: investor outreach across India, GCC, and global programs",
      ],
      fit: "Why him: Enterprise relationships and commercial execution to convert technology into revenue.",
    },
  ];

  const cw = 5.9, ch = 3.55, gx = 0.35, startX = 0.6, startY = 2.2;
  founders.forEach((f, i) => {
    const x = startX + i * (cw + gx);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x, y: startY, w: cw, h: ch, rectRadius: 0.1,
      fill: { color: WHITE }, line: { color: ICE_LINE, width: 1 },
      shadow: { type: "outer", color: "9AA7B5", blur: 7, offset: 2, angle: 90, opacity: 0.15 },
    });

    // Photo placeholder circle
    s.addShape(pres.shapes.OVAL, {
      x: x + 0.28, y: startY + 0.28, w: 0.72, h: 0.72,
      fill: { color: ICE }, line: { color: BLUE, width: 1.5 },
    });
    s.addText(f.name[0], {
      x: x + 0.28, y: startY + 0.28, w: 0.72, h: 0.72, align: "center", valign: "middle",
      fontFace: FONT_HEAD, bold: true, fontSize: 22, color: NAVY,
    });

    // Name and role
    s.addText(f.name, {
      x: x + 1.15, y: startY + 0.3, w: cw - 1.4, h: 0.35, fontFace: FONT,
      bold: true, fontSize: 15, color: NAVY_DEEP,
    });
    s.addText(f.role, {
      x: x + 1.15, y: startY + 0.62, w: cw - 1.4, h: 0.28, fontFace: FONT,
      fontSize: 10.5, color: BLUE, bold: true,
    });

    // Bullet points
    let py = startY + 1.1;
    f.points.forEach((p) => {
      s.addText("•", {
        x: x + 0.28, y: py, w: 0.2, h: 0.35, fontFace: FONT, fontSize: 10, color: BLUE,
      });
      s.addText(p, {
        x: x + 0.48, y: py, w: cw - 0.76, h: 0.42, fontFace: FONT,
        fontSize: 9.8, color: "2C3846", lineSpacing: 12,
      });
      py += 0.45;
    });

    // Founder-market fit callout
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x: x + 0.22, y: startY + ch - 0.58, w: cw - 0.44, h: 0.42, rectRadius: 0.06,
      fill: { color: ICE }, line: { type: "none" },
    });
    s.addText(f.fit, {
      x: x + 0.35, y: startY + ch - 0.58, w: cw - 0.7, h: 0.42, fontFace: FONT,
      italic: true, fontSize: 9.2, color: NAVY, valign: "middle", lineSpacing: 11,
    });
  });

  // advisor strip
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x: 0.6, y: 6.0, w: 12.15, h: 0.75, rectRadius: 0.08,
    fill: { color: NAVY_DEEP }, line: { type: "none" },
  });
  s.addImage({ path: ICON("award", "green"), x: 0.88, y: 6.18, w: 0.36, h: 0.36 });
  s.addText([
    { text: "Advisory network: ", options: { bold: true, color: "6FCF87" } },
    { text: "Rajiv Sikka (ex-CEO, IndianOil–Adani Gas), Sanjay Kumar Suri (ex-CISO, BPCL; CEO, Future IT Advisory), and senior FinOps practitioners from Zenoti ($40M cloud base) and Revvity (multi-cloud enterprise).", options: { color: "C7D6E5" } },
  ], {
    x: 1.4, y: 6.0, w: 11.2, h: 0.75, valign: "middle", fontFace: FONT, fontSize: 10.5, lineSpacing: 13,
  });

  pageNum(s, 13);
}

// =====================================================================
// SLIDE 14 — FUNDRAISING ASK
// =====================================================================
{
  const s = pres.addSlide();
  lightBg(s);
  eyebrow(s, "13", "The Ask");
  miniLogo(s);

  s.addText("Raising ₹2.5 Crore (~US $300K) to land 10 paying enterprise customers.", {
    x: 0.6, y: 0.85, w: 11.8, h: 0.75, fontFace: FONT_HEAD, bold: true,
    fontSize: 24, color: NAVY_DEEP, lineSpacing: 27,
  });
  s.addText(
    "This capital bridges us from “product built, pilot in progress” to " +
    "“repeatable enterprise revenue” within 12 months.",
    { x: 0.6, y: 1.6, w: 11.6, h: 0.5, fontFace: FONT, fontSize: 12.5, color: SLATE, lineSpacing: 16 }
  );

  // Use of funds breakdown
  const funds = [
    { pct: "40%", label: "Enterprise Sales & GTM", detail: "Dedicated enterprise BD hires for India and GCC. Conference presence. Partner onboarding.", color: NAVY },
    { pct: "30%", label: "Engineering & Product", detail: "SOC2 audit preparation, on-premises hardening, advanced AI models, and platform scaling.", color: BLUE },
    { pct: "15%", label: "GCC Market Entry", detail: "Qatar/UAE entity setup, local partnerships, sovereign-cloud compliance certifications.", color: GREEN },
    { pct: "15%", label: "Operations & Runway", detail: "Legal, compliance, infrastructure costs, and 18-month operational buffer.", color: AMBER },
  ];

  const cw = 2.85, ch = 2.65, gx = 0.2, startX = 0.6, startY = 2.3;
  funds.forEach((f, i) => {
    const x = startX + i * (cw + gx);
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x, y: startY, w: cw, h: ch, rectRadius: 0.1,
      fill: { color: WHITE }, line: { color: ICE_LINE, width: 1 },
      shadow: { type: "outer", color: "9AA7B5", blur: 7, offset: 2, angle: 90, opacity: 0.15 },
    });
    // percentage header
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x, y: startY, w: cw, h: 0.75, rectRadius: 0.1,
      fill: { color: f.color }, line: { type: "none" },
    });
    s.addShape(pres.shapes.RECTANGLE, {
      x, y: startY + 0.4, w: cw, h: 0.35,
      fill: { color: f.color }, line: { type: "none" },
    });
    s.addText(f.pct, {
      x, y: startY + 0.08, w: cw, h: 0.45, align: "center", fontFace: FONT_HEAD,
      bold: true, fontSize: 22, color: WHITE,
    });
    s.addText(f.label, {
      x: x + 0.2, y: startY + 0.9, w: cw - 0.4, h: 0.55, fontFace: FONT,
      bold: true, fontSize: 11.5, color: NAVY_DEEP, lineSpacing: 13,
    });
    s.addText(f.detail, {
      x: x + 0.2, y: startY + 1.48, w: cw - 0.4, h: 1.05, fontFace: FONT,
      fontSize: 9.6, color: SLATE, lineSpacing: 12.5,
    });
  });

  // Key metrics strip
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x: 0.6, y: 5.2, w: 12.15, h: 1.55, rectRadius: 0.09,
    fill: { color: ICE }, line: { color: ICE_LINE, width: 1 },
  });

  const metrics = [
    { label: "Raise", value: "₹2.5 Cr", sub: "(~US $300K)" },
    { label: "Runway", value: "18 months", sub: "post-raise" },
    { label: "Target", value: "10 customers", sub: "in 12 months" },
    { label: "Break-even", value: "Month 14", sub: "at ₹15L ACV × 10" },
  ];

  const mw = 2.85, mx0 = 0.85;
  metrics.forEach((m, i) => {
    const x = mx0 + i * (mw + 0.2);
    s.addText(m.label, {
      x, y: 5.35, w: mw, h: 0.28, fontFace: FONT, fontSize: 9.5,
      color: SLATE, charSpacing: 0.5, bold: true,
    });
    s.addText(m.value, {
      x, y: 5.62, w: mw, h: 0.45, fontFace: FONT_HEAD, bold: true,
      fontSize: 20, color: NAVY_DEEP,
    });
    s.addText(m.sub, {
      x, y: 6.08, w: mw, h: 0.28, fontFace: FONT, fontSize: 9.5,
      color: SLATE, italic: true,
    });
  });

  pageNum(s, 14);
}

// =====================================================================
// SLIDE 15 — VISION (CLOSING)
// =====================================================================
{
  const s = pres.addSlide();
  s.background = { color: NAVY_DEEP };

  // Decorative shapes
  s.addShape(pres.shapes.OVAL, {
    x: -2.0, y: -2.5, w: 6.5, h: 6.5, fill: { color: "0F3358", transparency: 35 },
    line: { type: "none" },
  });
  s.addShape(pres.shapes.OVAL, {
    x: 9.5, y: 4.0, w: 5.5, h: 5.5, fill: { color: GREEN, transparency: 88 },
    line: { type: "none" },
  });
  s.addShape(pres.shapes.OVAL, {
    x: 11.0, y: -1.5, w: 4.0, h: 4.0, fill: { color: BLUE, transparency: 90 },
    line: { type: "none" },
  });

  s.addImage({ path: LOGO, x: 0.85, y: 0.85, w: 0.85, h: 0.85 * (250/262) });
  s.addText("CloudFinOps", {
    x: 1.85, y: 0.88, w: 4, h: 0.42, fontFace: FONT_HEAD, bold: true,
    fontSize: 18, color: WHITE,
  });

  // Vision statement
  s.addText([
    { text: "Every enterprise deserves to know\n", options: { breakLine: true } },
    { text: "exactly where its cloud budget goes —\n", options: { breakLine: true } },
    { text: "and act on it the same day.", options: {} },
  ], {
    x: 0.85, y: 2.0, w: 11.5, h: 2.2, fontFace: FONT_HEAD, bold: true,
    fontSize: 36, color: WHITE, lineSpacing: 42,
  });

  s.addText(
    "We are building the financial intelligence layer for multi-cloud infrastructure — " +
    "deployed wherever data sovereignty demands, powered by AI that finds what humans miss, " +
    "and trusted by the enterprises and governments that cannot afford to get it wrong.",
    {
      x: 0.85, y: 4.3, w: 10.5, h: 0.95, fontFace: FONT, fontSize: 13.5,
      color: "C7D6E5", lineSpacing: 19,
    }
  );

  // Contact info
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x: 0.85, y: 5.65, w: 6.5, h: 1.1, rectRadius: 0.1,
    fill: { color: "0F2740" }, line: { color: "2A4A68", width: 1 },
  });
  s.addText([
    { text: "cloudfinops.solutions", options: { bold: true, color: "6FCF87", fontSize: 13 } },
    { text: "\n" },
    { text: "Nishant Jain, CTO  ·  nishant@cloudfinops.solutions\n", options: { color: "9FB6CC", fontSize: 10.5 } },
    { text: "Sambhav Pal, CEO  ·  sambhav@cloudfinops.solutions", options: { color: "9FB6CC", fontSize: 10.5 } },
  ], {
    x: 1.05, y: 5.75, w: 6.1, h: 0.9, fontFace: FONT, lineSpacing: 15, valign: "middle",
  });

  // CTA badges
  const ctas = ["Let’s talk", "Request a demo", "Pilot ready"];
  let cx = 8.0;
  ctas.forEach((c) => {
    const tw = c.length * 0.09 + 0.5;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x: cx, y: 5.85, w: tw, h: 0.42, rectRadius: 0.21,
      fill: { color: GREEN }, line: { type: "none" },
    });
    s.addText(c, {
      x: cx, y: 5.85, w: tw, h: 0.42, align: "center", valign: "middle",
      fontFace: FONT, bold: true, fontSize: 10, color: WHITE,
    });
    cx += tw + 0.15;
  });

  pageNum(s, 15, true);
}

// =====================================================================
// EXPORT — write the final file
// =====================================================================
pres.writeFile({ fileName: "CloudFinOps_Seed_Pitch_Deck.pptx" })
  .then(() => console.log("Deck generated: CloudFinOps_Seed_Pitch_Deck.pptx"))
  .catch((err) => console.error("Error:", err));
