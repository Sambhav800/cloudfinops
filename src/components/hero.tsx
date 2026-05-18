"use client";

import type { CSSProperties, MouseEvent } from "react";
import { useRef } from "react";
import Link from "next/link";

const navLinks = [
  { label: "Features", href: "#features" },
  { label: "Security", href: "#security" },
  { label: "Pricing", href: "#pricing" },
  { label: "Docs", href: "#docs" },
] as const;

const providerBadges = [
  { label: "AWS", color: "#FF9900" },
  { label: "Azure", color: "#0078D4" },
  { label: "GCP", color: "#4285F4" },
] as const;

const heroPrinciples = [
  {
    title: "Scanner-backed truth",
    detail:
      "Built for FinOps, platform engineering, governance, and procurement teams that need defensible decisions.",
  },
  {
    title: "Consulting-grade AI output",
    detail:
      "Turn live cloud telemetry into executive reports, architecture context, and guided next actions.",
  },
  {
    title: "Enterprise and public-sector ready",
    detail:
      "Read-only multi-cloud control with the posture needed for audit-heavy and procurement-sensitive environments.",
  },
] as const;

const commandPills = [
  "Waste intelligence",
  "Architecture context",
  "Executive reporting",
  "Guided remediation",
] as const;

const orbitNodes = [
  {
    label: "Scan",
    className: "left-8 top-28",
    tone: "border-cyan-400/20 bg-cyan-500/10 text-cyan-100",
    shift:
      "translate3d(var(--shift-x-soft-neg), var(--shift-y-soft-neg), 24px)",
  },
  {
    label: "Forecast",
    className: "right-12 top-24",
    tone: "border-indigo-400/20 bg-indigo-500/10 text-indigo-100",
    shift:
      "translate3d(var(--shift-x-soft), var(--shift-y-soft-neg), 28px)",
  },
  {
    label: "Security",
    className: "left-14 bottom-32",
    tone: "border-emerald-400/20 bg-emerald-500/10 text-emerald-100",
    shift:
      "translate3d(var(--shift-x-mid-neg), var(--shift-y-soft), 20px)",
  },
  {
    label: "Govern",
    className: "right-10 bottom-28",
    tone: "border-violet-400/20 bg-violet-500/10 text-violet-100",
    shift: "translate3d(var(--shift-x-mid), var(--shift-y-soft), 26px)",
  },
  {
    label: "Report",
    className: "left-1/2 top-14 -translate-x-1/2",
    tone: "border-amber-400/20 bg-amber-500/10 text-amber-100",
    shift: "translate3d(var(--shift-x-soft), var(--shift-y-soft-neg), 22px)",
  },
  {
    label: "Act",
    className: "left-1/2 bottom-16 -translate-x-1/2",
    tone: "border-rose-400/20 bg-rose-500/10 text-rose-100",
    shift:
      "translate3d(var(--shift-x-soft-neg), var(--shift-y-soft), 18px)",
  },
] as const;

type HeroStyleVars = CSSProperties & {
  "--pointer-x": string;
  "--pointer-y": string;
  "--rotate-x": string;
  "--rotate-y": string;
  "--shift-x-soft": string;
  "--shift-y-soft": string;
  "--shift-x-soft-neg": string;
  "--shift-y-soft-neg": string;
  "--shift-x-mid": string;
  "--shift-y-mid": string;
  "--shift-x-mid-neg": string;
  "--shift-y-mid-neg": string;
};

const heroStyleVars: HeroStyleVars = {
  "--pointer-x": "50%",
  "--pointer-y": "40%",
  "--rotate-x": "0deg",
  "--rotate-y": "0deg",
  "--shift-x-soft": "0px",
  "--shift-y-soft": "0px",
  "--shift-x-soft-neg": "0px",
  "--shift-y-soft-neg": "0px",
  "--shift-x-mid": "0px",
  "--shift-y-mid": "0px",
  "--shift-x-mid-neg": "0px",
  "--shift-y-mid-neg": "0px",
};

export function Hero() {
  const heroRef = useRef<HTMLElement | null>(null);

  const handleHeroMove = (event: MouseEvent<HTMLElement>) => {
    const node = heroRef.current;
    if (!node) {
      return;
    }

    const rect = node.getBoundingClientRect();
    const x = ((event.clientX - rect.left) / rect.width) * 100;
    const y = ((event.clientY - rect.top) / rect.height) * 100;
    const rotateY = (x - 50) / 5.5;
    const rotateX = (50 - y) / 7;
    const shiftXSoft = (x - 50) * 0.18;
    const shiftYSoft = (y - 50) * 0.18;
    const shiftXMid = (x - 50) * 0.34;
    const shiftYMid = (y - 50) * 0.34;

    node.style.setProperty("--pointer-x", `${x}%`);
    node.style.setProperty("--pointer-y", `${y}%`);
    node.style.setProperty("--rotate-x", `${rotateX}deg`);
    node.style.setProperty("--rotate-y", `${rotateY}deg`);
    node.style.setProperty("--shift-x-soft", `${shiftXSoft}px`);
    node.style.setProperty("--shift-y-soft", `${shiftYSoft}px`);
    node.style.setProperty("--shift-x-soft-neg", `${-shiftXSoft}px`);
    node.style.setProperty("--shift-y-soft-neg", `${-shiftYSoft}px`);
    node.style.setProperty("--shift-x-mid", `${shiftXMid}px`);
    node.style.setProperty("--shift-y-mid", `${shiftYMid}px`);
    node.style.setProperty("--shift-x-mid-neg", `${-shiftXMid}px`);
    node.style.setProperty("--shift-y-mid-neg", `${-shiftYMid}px`);
  };

  const resetHeroMove = () => {
    const node = heroRef.current;
    if (!node) {
      return;
    }

    node.style.setProperty("--pointer-x", "50%");
    node.style.setProperty("--pointer-y", "40%");
    node.style.setProperty("--rotate-x", "0deg");
    node.style.setProperty("--rotate-y", "0deg");
    node.style.setProperty("--shift-x-soft", "0px");
    node.style.setProperty("--shift-y-soft", "0px");
    node.style.setProperty("--shift-x-soft-neg", "0px");
    node.style.setProperty("--shift-y-soft-neg", "0px");
    node.style.setProperty("--shift-x-mid", "0px");
    node.style.setProperty("--shift-y-mid", "0px");
    node.style.setProperty("--shift-x-mid-neg", "0px");
    node.style.setProperty("--shift-y-mid-neg", "0px");
  };

  return (
    <>
      <nav className="fixed top-0 left-0 right-0 z-50 border-b border-white/5 bg-[#0a0f1e]/80 backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 shadow-lg shadow-indigo-500/30">
              <span className="text-sm font-bold text-white">C</span>
            </div>
            <span className="text-lg font-bold tracking-tight text-white">
              CloudFinOps
            </span>
            <span className="ml-1 hidden rounded-full border border-indigo-500/20 bg-indigo-500/15 px-2 py-0.5 text-[10px] font-medium text-indigo-400 sm:inline-flex">
              ENTERPRISE
            </span>
          </div>

          <div className="hidden items-center gap-8 md:flex">
            {navLinks.map((link) => (
              <a
                key={link.label}
                href={link.href}
                className="text-sm text-slate-400 transition-colors duration-200 hover:text-white"
              >
                {link.label}
              </a>
            ))}
          </div>

          <div className="flex items-center gap-3">
            <Link
              href="/dashboard"
              className="hidden text-sm text-slate-400 transition-colors hover:text-white sm:block"
            >
              Sign in
            </Link>
            <Link
              href="/dashboard"
              className="rounded-xl bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow-lg shadow-indigo-500/25 transition-all duration-200 hover:scale-[1.02] hover:bg-indigo-500 hover:shadow-indigo-500/40"
            >
              Get Started Free
            </Link>
          </div>
        </div>
      </nav>

      <section
        ref={heroRef}
        onMouseMove={handleHeroMove}
        onMouseLeave={resetHeroMove}
        style={heroStyleVars}
        className="group/hero relative min-h-screen overflow-hidden bg-[#0a0f1e] pt-16"
      >
        <div className="pointer-events-none absolute top-0 left-1/2 h-[600px] w-[900px] -translate-x-1/2 rounded-full bg-indigo-600/12 blur-[120px]" />
        <div className="pointer-events-none absolute bottom-0 left-0 h-[500px] w-[500px] rounded-full bg-violet-600/10 blur-[100px]" />
        <div className="pointer-events-none absolute right-0 bottom-0 h-[420px] w-[420px] rounded-full bg-blue-600/10 blur-[100px]" />
        <div
          className="pointer-events-none absolute inset-0 opacity-90"
          style={{
            background:
              "radial-gradient(560px circle at var(--pointer-x) var(--pointer-y), rgba(99,102,241,0.18), rgba(139,92,246,0.08) 28%, transparent 64%)",
          }}
        />
        <div
          className="hero-grid-drift pointer-events-none absolute inset-0"
          style={{
            backgroundImage: `
              linear-gradient(rgba(99,102,241,0.045) 1px, transparent 1px),
              linear-gradient(90deg, rgba(99,102,241,0.045) 1px, transparent 1px)
            `,
            backgroundSize: "64px 64px",
          }}
        />

        <div className="relative z-10 mx-auto w-full max-w-7xl px-6 py-24 lg:py-32">
          <div className="grid items-center gap-14 lg:grid-cols-[1fr_1.02fr]">
            <div className="max-w-3xl">
              <div className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.05] px-4 py-2 text-sm text-slate-400">
                <span className="h-2 w-2 flex-shrink-0 rounded-full bg-emerald-400 animate-pulse" />
                <span>Enterprise multi-cloud FinOps</span>
                <span className="text-slate-600">·</span>
                <span className="font-medium text-indigo-300">
                  Public-sector ready
                </span>
              </div>

              <div className="mt-8 space-y-6">
                <div className="inline-flex items-center gap-3 rounded-full border border-white/10 bg-white/[0.03] px-4 py-2 text-[11px] uppercase tracking-[0.26em] text-slate-500">
                  <span className="text-slate-300">AWS</span>
                  <span className="h-1 w-1 rounded-full bg-slate-700" />
                  <span className="text-slate-300">Azure</span>
                  <span className="h-1 w-1 rounded-full bg-slate-700" />
                  <span className="text-slate-300">GCP</span>
                </div>

                <h1 className="text-5xl leading-[0.95] font-bold tracking-tight text-white sm:text-6xl lg:text-7xl">
                  See every leak.
                  <br />
                  <span className="bg-gradient-to-r from-white via-indigo-200 to-cyan-200 bg-clip-text text-transparent">
                    Explain every spike.
                  </span>
                  <br />
                  Govern every cloud.
                </h1>

                <p className="max-w-2xl text-lg leading-relaxed text-slate-400 sm:text-xl">
                  CloudFinOps is the AI-powered FinOps operating system for
                  enterprise and government teams running AWS, Azure, and GCP
                  — combining scanner-backed cost intelligence, architecture
                  reasoning, executive reporting, and guided remediation in a
                  single command layer.
                </p>

                <p className="max-w-2xl text-sm leading-7 text-slate-500">
                  Built for platform engineering, cloud governance, finance
                  leadership, procurement, and audit-heavy environments that
                  need more than spend charts.
                </p>
              </div>

              <div className="mt-10 flex flex-col items-center gap-4 sm:flex-row">
                <Link
                  href="/dashboard"
                  className="group relative inline-flex w-full items-center justify-center gap-2 rounded-2xl bg-indigo-600 px-8 py-4 text-base font-semibold text-white shadow-[0_0_40px_rgba(99,102,241,0.35)] transition-all duration-300 hover:scale-[1.03] hover:bg-indigo-500 hover:shadow-[0_0_60px_rgba(99,102,241,0.55)] sm:w-auto"
                >
                  Open CloudFinOps
                  <svg
                    className="h-4 w-4 transition-transform duration-200 group-hover:translate-x-1"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={2.5}
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3"
                    />
                  </svg>
                </Link>

                <a
                  href="#features"
                  className="group inline-flex w-full items-center justify-center gap-2 rounded-2xl border border-white/10 bg-white/5 px-8 py-4 text-base font-medium text-white transition-all duration-300 hover:scale-[1.02] hover:border-white/20 hover:bg-white/10 sm:w-auto"
                >
                  <svg
                    className="h-4 w-4 text-slate-400"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.348a1.125 1.125 0 010 1.971l-11.54 6.347a1.125 1.125 0 01-1.667-.985V5.653z"
                    />
                  </svg>
                  See the operating model
                </a>
              </div>

              <div className="mt-10 flex flex-wrap items-center gap-3">
                <span className="text-xs uppercase tracking-wider text-slate-600">
                  Works across
                </span>
                {providerBadges.map((provider) => (
                  <div
                    key={provider.label}
                    className="flex items-center gap-1.5 rounded-xl border border-white/10 bg-white/5 px-3 py-1.5 transition-colors hover:bg-white/8"
                  >
                    <span
                      className="h-2 w-2 rounded-full"
                      style={{ backgroundColor: provider.color }}
                    />
                    <span className="text-xs font-semibold text-slate-300">
                      {provider.label}
                    </span>
                  </div>
                ))}
              </div>

              <div className="mt-10 grid gap-4 sm:grid-cols-3">
                {heroPrinciples.map((item) => (
                  <div
                    key={item.title}
                    className="rounded-2xl border border-white/10 bg-white/[0.04] p-4 backdrop-blur-xl"
                  >
                    <p className="text-sm font-semibold text-white">
                      {item.title}
                    </p>
                    <p className="mt-2 text-xs leading-6 text-slate-500">
                      {item.detail}
                    </p>
                  </div>
                ))}
              </div>
            </div>

            <div
              className="relative mx-auto w-full max-w-[660px]"
              style={{ perspective: "2400px" }}
            >
              <div
                className="relative h-[620px] transition-transform duration-300 ease-out will-change-transform"
                style={{
                  transform:
                    "translateZ(0) rotateX(var(--rotate-x)) rotateY(var(--rotate-y))",
                  transformStyle: "preserve-3d",
                }}
              >
                <div className="absolute inset-0 overflow-hidden rounded-[40px] border border-white/10 bg-white/[0.03] shadow-[0_40px_140px_rgba(2,6,23,0.72)] backdrop-blur-2xl" />
                <div
                  className="absolute inset-0 rounded-[40px] opacity-90"
                  style={{
                    background:
                      "radial-gradient(460px circle at var(--pointer-x) var(--pointer-y), rgba(99,102,241,0.26), rgba(59,130,246,0.08) 38%, transparent 68%)",
                  }}
                />
                <div className="absolute inset-7 overflow-hidden rounded-[34px] border border-white/10 bg-[linear-gradient(180deg,rgba(15,23,42,0.88),rgba(3,7,18,0.7))]" />
                <div
                  className="absolute inset-7 opacity-40"
                  style={{
                    backgroundImage:
                      "linear-gradient(rgba(148,163,184,0.08) 1px, transparent 1px), linear-gradient(90deg, rgba(148,163,184,0.08) 1px, transparent 1px)",
                    backgroundSize: "28px 28px",
                  }}
                />

                <div className="absolute top-8 left-8 right-8 flex items-center justify-between rounded-2xl border border-white/10 bg-white/[0.04] px-4 py-3 backdrop-blur-xl">
                  <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.22em] text-slate-500">
                    <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
                    Live command layer
                  </div>
                  <div className="rounded-full border border-indigo-400/15 bg-indigo-500/10 px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-indigo-200">
                    Read-only telemetry
                  </div>
                </div>

                <div
                  className="absolute inset-x-14 top-24 h-[360px] rounded-[34px] border border-white/10 bg-gradient-to-br from-white/[0.1] to-white/[0.03] shadow-[0_28px_90px_rgba(15,23,42,0.6)] backdrop-blur-2xl transition-transform duration-500"
                  style={{
                    transform:
                      "translate3d(var(--shift-x-soft), var(--shift-y-soft), 32px)",
                  }}
                >
                  <div
                    className="absolute inset-0 rounded-[34px] opacity-75"
                    style={{
                      background:
                        "radial-gradient(320px circle at 50% 44%, rgba(99,102,241,0.22), transparent 62%)",
                    }}
                  />
                  <div className="hero-ring-spin absolute inset-8 rounded-full border border-indigo-400/15 opacity-80" />
                  <div className="hero-ring-spin-reverse absolute inset-14 rounded-full border border-cyan-400/10 opacity-70" />
                  <div className="absolute top-1/2 left-1/2 h-[230px] w-[230px] -translate-x-1/2 -translate-y-1/2 rounded-full border border-white/10 bg-[radial-gradient(circle_at_50%_45%,rgba(99,102,241,0.35),rgba(15,23,42,0.88)_72%)] shadow-[0_20px_60px_rgba(99,102,241,0.22)]" />

                  {orbitNodes.map((node) => (
                    <div
                      key={node.label}
                      className={`absolute rounded-full border px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] backdrop-blur-xl ${node.className} ${node.tone}`}
                      style={{ transform: node.shift }}
                    >
                      {node.label}
                    </div>
                  ))}

                  <div className="absolute top-1/2 left-1/2 z-10 w-[250px] -translate-x-1/2 -translate-y-1/2 text-center">
                    <p className="text-[11px] uppercase tracking-[0.24em] text-indigo-200/80">
                      CloudFinOps command core
                    </p>
                    <h2 className="mt-3 text-3xl font-semibold text-white">
                      Detect. explain. govern. act.
                    </h2>
                    <p className="mt-4 text-sm leading-7 text-slate-300">
                      The control plane where scanner truth, AI reasoning,
                      architecture context, and executive output meet.
                    </p>
                  </div>
                </div>

                <div
                  className="absolute top-36 left-6 w-52 rounded-2xl border border-white/10 bg-slate-950/70 p-4 shadow-xl shadow-black/25 backdrop-blur-xl transition-transform duration-500"
                  style={{
                    transform:
                      "translate3d(var(--shift-x-mid-neg), var(--shift-y-soft-neg), 46px)",
                  }}
                >
                  <p className="text-[11px] uppercase tracking-[0.22em] text-slate-500">
                    Executive confidence
                  </p>
                  <ul className="mt-3 space-y-2 text-sm text-slate-200">
                    <li>Board-ready summaries</li>
                    <li>Procurement-friendly narratives</li>
                    <li>Defensible cost posture</li>
                  </ul>
                </div>

                <div
                  className="absolute top-36 right-6 w-56 rounded-2xl border border-white/10 bg-slate-950/70 p-4 shadow-xl shadow-black/25 backdrop-blur-xl transition-transform duration-500"
                  style={{
                    transform:
                      "translate3d(var(--shift-x-mid), var(--shift-y-soft-neg), 54px)",
                  }}
                >
                  <p className="text-[11px] uppercase tracking-[0.22em] text-slate-500">
                    Operator outcomes
                  </p>
                  <div className="mt-3 grid gap-2">
                    {commandPills.map((pill) => (
                      <div
                        key={pill}
                        className="rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2 text-sm text-slate-200"
                      >
                        {pill}
                      </div>
                    ))}
                  </div>
                </div>

                <div
                  className="group-hover/hero:-translate-y-2 absolute right-8 bottom-16 left-8 rounded-[28px] border border-white/10 bg-white/[0.05] p-5 shadow-xl shadow-black/20 backdrop-blur-xl transition-transform duration-500"
                  style={{
                    transform:
                      "translate3d(var(--shift-x-soft), var(--shift-y-mid), 38px)",
                  }}
                >
                  <div className="flex items-center justify-between gap-4">
                    <div>
                      <p className="text-[11px] uppercase tracking-[0.22em] text-slate-500">
                        Operating sequence
                      </p>
                      <p className="mt-2 text-sm text-white">
                        One workflow from scan to decision to remediation.
                      </p>
                    </div>
                    <div className="hidden rounded-2xl border border-emerald-400/20 bg-emerald-500/10 px-4 py-2 text-xs font-medium text-emerald-200 sm:block">
                      Consulting-grade, not dashboard-grade
                    </div>
                  </div>

                  <div className="mt-4 grid gap-2 sm:grid-cols-4">
                    {[
                      "Scan estate",
                      "Model spend",
                      "Brief leaders",
                      "Drive action",
                    ].map((step) => (
                      <div
                        key={step}
                        className="rounded-2xl border border-white/10 bg-slate-950/60 px-4 py-3 text-sm text-slate-200"
                      >
                        {step}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <style jsx global>{`
        @keyframes heroGridDrift {
          0% {
            background-position: 0 0, 0 0;
          }
          100% {
            background-position: 64px 64px, 64px 64px;
          }
        }

        @keyframes heroRingSpin {
          from {
            transform: rotate(0deg);
          }
          to {
            transform: rotate(360deg);
          }
        }

        @keyframes heroRingSpinReverse {
          from {
            transform: rotate(360deg);
          }
          to {
            transform: rotate(0deg);
          }
        }

        .hero-grid-drift {
          animation: heroGridDrift 22s linear infinite;
        }

        .hero-ring-spin {
          animation: heroRingSpin 24s linear infinite;
        }

        .hero-ring-spin-reverse {
          animation: heroRingSpinReverse 30s linear infinite;
        }
      `}</style>
    </>
  );
}
