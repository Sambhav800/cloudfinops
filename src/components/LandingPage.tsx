"use client";

import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useMemo, useState } from "react";

type FaqItem = {
    question: string;
    answer: string;
};

type Testimonial = {
    quote: string;
    name: string;
    title: string;
    company: string;
    initials: string;
};

const teal = "#0891b2";
const tealHover = "#0e7490";
const textDark = "#0f172a";
const textLight = "#64748b";
const subtleBg = "#f8fafc";

const painPoints = [
    "You don't know where the money is going",
    "Spreadsheets take 40+ hours per month",
    "Your cloud team and finance team don't talk",
];

const howItWorks = [
    {
        title: "Connect",
        description: "Link your cloud accounts (AWS, GCP, Azure)",
    },
    {
        title: "Analyze",
        description: "Our AI identifies savings opportunities in minutes",
    },
    {
        title: "Optimize",
        description: "Auto-implement cost-saving rules",
    },
];

const features = [
    {
        title: "Real-time cost visibility",
        description: "See spend changes as they happen across every connected cloud account.",
    },
    {
        title: "Automated waste detection",
        description: "Catch idle resources, overprovisioned services, and hidden cost leaks fast.",
    },
    {
        title: "Team collaboration tools",
        description: "Keep engineering and finance working from the same live source of truth.",
    },
    {
        title: "AI-powered recommendations",
        description: "Get clear next steps that explain what to change and why it matters.",
    },
];

const testimonials: Testimonial[] = [
    {
        quote: "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Integer posuere erat a ante venenatis dapibus posuere velit aliquet.",
        name: "Avery Brooks",
        title: "Director of Platform",
        company: "Northstar Cloud",
        initials: "AB",
    },
    {
        quote: "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Praesent commodo cursus magna, vel scelerisque nisl consectetur et.",
        name: "Mina Patel",
        title: "VP, Finance Systems",
        company: "HelioWorks",
        initials: "MP",
    },
    {
        quote: "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Maecenas faucibus mollis interdum sed posuere consectetur est at lobortis.",
        name: "Jon Rivera",
        title: "Cloud Operations Lead",
        company: "Vector Labs",
        initials: "JR",
    },
];

const faqs: FaqItem[] = [
    {
        question: "How quickly can I see savings?",
        answer: "Most teams see their first savings opportunities within days of connecting cloud accounts and letting the platform analyze current spend patterns.",
    },
    {
        question: "What cloud providers do you support?",
        answer: "CloudFinOps supports AWS, GCP, and Azure so you can manage multi-cloud cost visibility from one dashboard.",
    },
    {
        question: "Is my data secure?",
        answer: "We use read-only cloud access patterns, clear access controls, and enterprise-grade operational practices to keep billing data protected.",
    },
    {
        question: "Do you offer onboarding?",
        answer: "Yes. We provide guided onboarding so your team can connect accounts, validate dashboards, and start acting on recommendations quickly.",
    },
    {
        question: "What's the pricing model?",
        answer: "Pricing is based on the scale of your cloud footprint and the level of support you need, with options for self-serve and guided rollout.",
    },
    {
        question: "Can finance and engineering both use it?",
        answer: "Yes. The product is designed so finance gets clear reporting while engineering gets the service-level detail needed to make changes.",
    },
];

function CheckmarkIcon() {
    return (
        <svg
            aria-label="Checkmark icon"
            className="h-4 w-4"
            viewBox="0 0 16 16"
            fill="none"
            role="img"
        >
            <path
                d="M4 8.4 6.7 11 12 5.5"
                stroke={teal}
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
            />
        </svg>
    );
}

function PhoneIcon() {
    return (
        <svg aria-label="Phone icon" className="h-5 w-5" viewBox="0 0 24 24" fill="none" role="img">
            <path
                d="M6.6 10.8a15.4 15.4 0 0 0 6.6 6.6l2.2-2.2a1 1 0 0 1 1-.25c1.08.36 2.25.55 3.46.55a1 1 0 0 1 1 1V20a1 1 0 0 1-1 1C10.85 21 3 13.15 3 3.5a1 1 0 0 1 1-1h3.5a1 1 0 0 1 1 1c0 1.21.19 2.38.55 3.46a1 1 0 0 1-.25 1z"
                stroke={teal}
                strokeWidth="1.8"
                strokeLinecap="round"
                strokeLinejoin="round"
            />
        </svg>
    );
}

function WhatsAppIcon() {
    return (
        <svg aria-label="WhatsApp icon" className="h-5 w-5" viewBox="0 0 24 24" fill="none" role="img">
            <path
                d="M20 11.5c0 4.69-3.81 8.5-8.5 8.5a8.42 8.42 0 0 1-4.1-1.05L4 20l1.14-3.18A8.44 8.44 0 0 1 3 11.5 8.5 8.5 0 1 1 20 11.5Z"
                stroke={teal}
                strokeWidth="1.8"
                strokeLinecap="round"
                strokeLinejoin="round"
            />
            <path
                d="M8.8 8.95c.18-.4.38-.42.56-.43h.48c.16 0 .4.06.6.5.2.43.67 1.48.73 1.59.06.11.1.25.02.4-.08.15-.12.25-.24.39-.12.14-.24.3-.35.4-.12.11-.24.23-.1.46.14.23.63 1.03 1.35 1.67.92.81 1.7 1.06 1.94 1.18.24.12.38.1.52-.05.14-.15.58-.67.74-.9.16-.23.32-.19.54-.11.22.08 1.38.65 1.62.76.24.12.4.18.46.28.06.1.06.57-.13 1.12-.19.55-1.1 1.06-1.5 1.12-.38.06-.87.09-1.41-.08-.32-.1-.73-.24-1.26-.47-.22-.09-.91-.39-1.73-1.09-.69-.58-1.14-1.3-1.35-1.64-.2-.34-.54-.91-.74-1.56-.2-.64-.02-.99.16-1.23Z"
                fill={teal}
            />
        </svg>
    );
}

function EmailIcon() {
    return (
        <svg aria-label="Email icon" className="h-5 w-5" viewBox="0 0 24 24" fill="none" role="img">
            <path
                d="M4 6.5h16v11H4z"
                stroke={teal}
                strokeWidth="1.8"
                strokeLinecap="round"
                strokeLinejoin="round"
            />
            <path
                d="m4 7 8 6 8-6"
                stroke={teal}
                strokeWidth="1.8"
                strokeLinecap="round"
                strokeLinejoin="round"
            />
        </svg>
    );
}

function Gauge({
    value,
    title,
    subtitle,
    centerLabel,
    large = false,
}: {
    value: number;
    title: string;
    subtitle: string;
    centerLabel: string;
    large?: boolean;
}) {
    const width = large ? 320 : 240;
    const height = large ? 190 : 150;
    const radius = large ? 118 : 84;
    const strokeWidth = large ? 18 : 14;
    const startX = width / 2 - radius;
    const endX = width / 2 + radius;
    const centerY = height - 20;
    const totalLength = Math.PI * radius;
    const fillLength = totalLength * Math.max(0, Math.min(value, 100)) / 100;
    const arcPath = `M ${startX} ${centerY} A ${radius} ${radius} 0 0 1 ${endX} ${centerY}`;

    return (
        <div className="w-full rounded-[24px] border border-slate-200 bg-white p-6 shadow-sm">
            <p className="text-sm font-medium text-slate-400">{title}</p>
            <div className="mt-6 flex items-center justify-center">
                <svg
                    aria-label={`${centerLabel} gauge`}
                    className="h-auto"
                    role="img"
                    viewBox={`0 0 ${width} ${height}`}
                    width={width}
                    height={height}
                >
                    <path
                        d={arcPath}
                        fill="none"
                        stroke="#e2e8f0"
                        strokeLinecap="round"
                        strokeWidth={strokeWidth}
                    />
                    <path
                        d={arcPath}
                        fill="none"
                        stroke={teal}
                        strokeDasharray={`${fillLength} ${totalLength}`}
                        strokeLinecap="round"
                        strokeWidth={strokeWidth}
                    />
                    <text
                        x="50%"
                        y={large ? "88" : "76"}
                        textAnchor="middle"
                        fill={textDark}
                        fontSize={large ? "42" : "30"}
                        fontWeight="700"
                    >
                        {centerLabel}
                    </text>
                    <text
                        x="50%"
                        y={large ? "114" : "98"}
                        textAnchor="middle"
                        fill={textLight}
                        fontSize={large ? "16" : "14"}
                        fontWeight="500"
                    >
                        {subtitle}
                    </text>
                </svg>
            </div>
        </div>
    );
}

function DashboardMockup() {
    return (
        <div className="mx-auto mt-12 w-full max-w-[600px] rounded-[28px] border border-slate-200 bg-white p-6 shadow-[0_30px_70px_rgba(15,23,42,0.08)]">
            <div className="grid gap-6">
                <div className="rounded-[24px] border border-slate-200 bg-slate-50 p-6">
                    <Gauge
                        value={70}
                        title="Savings Forecast"
                        subtitle="Efficiency score"
                        centerLabel="70%"
                    />
                </div>
                <div className="grid gap-4 sm:grid-cols-3">
                    {[
                        { label: "Revenue", value: "₹9.96Cr" },
                        { label: "Forecast", value: "₹1.06Cr" },
                        { label: "Savings", value: "₹28.2L" },
                    ].map((item) => (
                        <div
                            key={item.label}
                            className="rounded-2xl border border-slate-200 bg-white p-5"
                        >
                            <p className="text-sm font-medium text-slate-400">{item.label}</p>
                            <p className="mt-4 text-[28px] font-bold leading-none text-slate-900">
                                {item.value}
                            </p>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}

function SectionHeader({
    eyebrow,
    title,
    description,
}: {
    eyebrow?: string;
    title: string;
    description?: string;
}) {
    return (
        <div className="mx-auto max-w-3xl text-center">
            {eyebrow ? (
                <p className="text-sm font-medium uppercase tracking-[0.18em] text-slate-400">
                    {eyebrow}
                </p>
            ) : null}
            <h2 className="mt-4 text-[32px] font-bold leading-[1.2] text-slate-900 sm:text-[40px]">
                {title}
            </h2>
            {description ? (
                <p className="mt-6 text-base leading-[1.6] text-slate-500">{description}</p>
            ) : null}
        </div>
    );
}

function FeatureIcon() {
    return (
        <span className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-cyan-50" aria-hidden="true">
            <CheckmarkIcon />
        </span>
    );
}

function FaqAccordion({
    items,
    activeIndex,
    onToggle,
}: {
    items: FaqItem[];
    activeIndex: number | null;
    onToggle: (index: number) => void;
}) {
    return (
        <div className="mx-auto mt-12 max-w-4xl divide-y divide-slate-200 rounded-3xl border border-slate-200 bg-white">
            {items.map((item, index) => {
                const isOpen = activeIndex === index;
                return (
                    <div key={item.question} className="px-6 py-5 sm:px-8">
                        <button
                            type="button"
                            aria-controls={`faq-panel-${index}`}
                            aria-expanded={isOpen}
                            aria-label={`Toggle answer for ${item.question}`}
                            className="flex w-full items-center justify-between gap-6 text-left"
                            onClick={() => onToggle(index)}
                        >
                            <span className="text-lg font-semibold text-slate-900">
                                {item.question}
                            </span>
                            <span className="text-2xl font-medium text-cyan-700">
                                {isOpen ? "−" : "+"}
                            </span>
                        </button>
                        <AnimatePresence initial={false}>
                            {isOpen ? (
                                <motion.div
                                    key="content"
                                    id={`faq-panel-${index}`}
                                    initial={{ height: 0, opacity: 0 }}
                                    animate={{ height: "auto", opacity: 1 }}
                                    exit={{ height: 0, opacity: 0 }}
                                    transition={{ duration: 0.3, ease: "easeInOut" }}
                                    className="overflow-hidden"
                                >
                                    <p className="pt-4 text-base leading-[1.6] text-slate-500">
                                        {item.answer}
                                    </p>
                                </motion.div>
                            ) : null}
                        </AnimatePresence>
                    </div>
                );
            })}
        </div>
    );
}

export default function LandingPage() {
    const [navShadow, setNavShadow] = useState(false);
    const [openFaqIndex, setOpenFaqIndex] = useState<number | null>(0);

    useEffect(() => {
        const handleScroll = () => {
            setNavShadow(window.scrollY > 8);
        };

        handleScroll();
        window.addEventListener("scroll", handleScroll, { passive: true });
        return () => window.removeEventListener("scroll", handleScroll);
    }, []);

    const currentYear = useMemo(() => new Date().getFullYear(), []);

    return (
        <div
            className="bg-white text-slate-900"
            style={{ fontFamily: "system-ui, -apple-system, sans-serif" }}
        >
            <nav
                aria-label="Main navigation"
                className={`sticky top-0 z-50 bg-white/95 backdrop-blur ${navShadow ? "shadow-sm shadow-slate-200/80" : ""}`}
            >
                <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4 lg:px-8">
                    <Link
                        href="/"
                        aria-label="FinOps home"
                        className="text-2xl font-bold tracking-tight text-cyan-600"
                    >
                        FinOps
                    </Link>
                    <a
                        href="#pricing-cta"
                        aria-label="Book a Demo"
                        className="rounded-lg bg-cyan-600 px-6 py-3 text-base font-medium text-white transition-colors hover:bg-cyan-700"
                    >
                        Book a Demo
                    </a>
                </div>
            </nav>

            <main>
                <section
                    aria-labelledby="hero-heading"
                    className="relative overflow-hidden bg-gradient-to-b from-white to-slate-50/80"
                >
                    <div className="mx-auto flex min-h-[700px] max-w-4xl flex-col items-center justify-center px-6 py-20 text-center lg:px-8">
                        <p className="text-sm font-medium uppercase tracking-[0.18em] text-slate-400">
                            FinOps built for cloud teams
                        </p>
                        <h1
                            id="hero-heading"
                            className="mt-6 max-w-4xl text-[40px] font-bold leading-[1.2] text-slate-900 sm:text-[48px] lg:text-[56px]"
                        >
                            Stop Bleeding Money on Cloud.
                        </h1>
                        <p className="mt-6 max-w-2xl text-base leading-[1.6] text-slate-500">
                            Real-time FinOps insights that actually save you cash. No guesswork. No manual spreadsheets.
                        </p>
                        <div className="mt-8">
                            <Link
                                href="/login"
                                aria-label="Start Free Trial"
                                className="inline-flex rounded-lg bg-cyan-600 px-6 py-3 text-base font-medium text-white transition-colors hover:bg-cyan-700"
                            >
                                Start Free Trial
                            </Link>
                        </div>
                        <div className="mt-12 w-full max-w-[420px]">
                            <Gauge
                                value={34}
                                title="Savings Potential"
                                subtitle="CloudFinOps analysis"
                                centerLabel="34%"
                                large
                            />
                        </div>
                    </div>
                </section>

                <section aria-labelledby="problem-heading" className="py-20 lg:py-24">
                    <div className="mx-auto max-w-6xl px-6 lg:px-8">
                        <SectionHeader
                            title="Your Cloud Bill Is Out of Control"
                        />
                        <div className="mt-16 grid gap-8 lg:grid-cols-3">
                            {painPoints.map((point) => (
                                <article key={point} className="border-t border-slate-200 pt-6">
                                    <p className="text-2xl font-semibold leading-[1.4] text-slate-900">
                                        {point}
                                    </p>
                                </article>
                            ))}
                        </div>
                    </div>
                </section>

                <section aria-labelledby="solution-heading" className="bg-slate-50 py-20 lg:py-24">
                    <div className="mx-auto max-w-6xl px-6 lg:px-8">
                        <SectionHeader
                            title="Meet Your New Cloud Finance Dashboard"
                            description="One place to see spend, forecast, optimize, and automate. Real-time. Accurate. Simple."
                        />
                        <DashboardMockup />
                        <div className="mt-10 text-center">
                            <a
                                href="#pricing-cta"
                                aria-label="See it in action"
                                className="inline-flex rounded-lg bg-cyan-600 px-6 py-3 text-base font-medium text-white transition-colors hover:bg-cyan-700"
                            >
                                See it in action
                            </a>
                        </div>
                    </div>
                </section>

                <section aria-labelledby="how-it-works-heading" className="py-20 lg:py-24">
                    <div className="mx-auto max-w-6xl px-6 lg:px-8">
                        <SectionHeader title="3 Steps to Cloud Financial Peace" />
                        <div className="mt-16 grid overflow-hidden rounded-3xl border border-slate-200 lg:grid-cols-3">
                            {howItWorks.map((step, index) => (
                                <article
                                    key={step.title}
                                    className={`flex gap-5 p-6 sm:p-8 ${index < howItWorks.length - 1 ? "border-b border-slate-200 lg:border-b-0 lg:border-r" : ""}`}
                                >
                                    <span className="text-[40px] font-bold leading-none text-cyan-600">
                                        {index + 1}
                                    </span>
                                    <div>
                                        <h3 className="text-2xl font-semibold text-slate-900">
                                            {step.title}
                                        </h3>
                                        <p className="mt-3 text-base leading-[1.6] text-slate-500">
                                            {step.description}
                                        </p>
                                    </div>
                                </article>
                            ))}
                        </div>
                    </div>
                </section>

                <section aria-labelledby="features-heading" className="bg-slate-50 py-20 lg:py-24">
                    <div className="mx-auto max-w-6xl px-6 lg:px-8">
                        <SectionHeader title="Everything You Need" />
                        <div className="mt-16 grid gap-8 lg:grid-cols-2">
                            {features.map((feature) => (
                                <article
                                    key={feature.title}
                                    className="rounded-3xl border border-slate-200 bg-white p-8"
                                >
                                    <FeatureIcon />
                                    <h3 className="mt-6 text-2xl font-semibold text-slate-900">
                                        {feature.title}
                                    </h3>
                                    <p className="mt-3 text-base leading-[1.6] text-slate-500">
                                        {feature.description}
                                    </p>
                                </article>
                            ))}
                        </div>
                    </div>
                </section>

                <section aria-labelledby="social-proof-heading" className="py-20 lg:py-24">
                    <div className="mx-auto max-w-6xl px-6 lg:px-8">
                        <SectionHeader title="Trusted by cloud teams at leading companies" />
                        <div className="mt-16 grid gap-8 lg:grid-cols-3">
                            {testimonials.map((item) => (
                                <article
                                    key={item.name}
                                    className="rounded-3xl border border-slate-200 bg-white p-8"
                                >
                                    <p className="text-[18px] font-medium leading-[1.6] text-slate-900">
                                        {item.quote}
                                    </p>
                                    <div className="mt-8 flex items-center gap-4">
                                        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-slate-100 text-sm font-semibold text-slate-700">
                                            {item.initials}
                                        </div>
                                        <div>
                                            <p className="text-base font-semibold text-slate-900">
                                                {item.name}
                                            </p>
                                            <p className="text-sm font-medium text-slate-400">
                                                {item.title}, {item.company}
                                            </p>
                                        </div>
                                    </div>
                                </article>
                            ))}
                        </div>
                    </div>
                </section>

                <section id="pricing-cta" aria-labelledby="pricing-heading" className="bg-slate-50 py-20 lg:py-24">
                    <div className="mx-auto max-w-4xl px-6 text-center lg:px-8">
                        <SectionHeader
                            title="Ready to cut your cloud bill?"
                            description="Join companies saving ₹83L+ annually"
                        />
                        <div className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row">
                            <Link
                                href="/login"
                                aria-label="Start Free Trial"
                                className="inline-flex rounded-lg bg-cyan-600 px-6 py-3 text-base font-medium text-white transition-colors hover:bg-cyan-700"
                            >
                                Start Free Trial
                            </Link>
                            <a
                                href="#footer-cta"
                                aria-label="Book a Demo"
                                className="inline-flex rounded-lg border border-cyan-600 px-6 py-3 text-base font-medium text-cyan-600 transition-colors hover:bg-cyan-50"
                            >
                                Book a Demo
                            </a>
                        </div>
                        <p className="mt-4 text-sm font-medium text-slate-400">
                            No credit card required. 14-day free trial.
                        </p>
                    </div>
                </section>

                <section aria-labelledby="faq-heading" className="py-20 lg:py-24">
                    <div className="mx-auto max-w-6xl px-6 lg:px-8">
                        <SectionHeader title="Questions?" />
                        <FaqAccordion
                            items={faqs}
                            activeIndex={openFaqIndex}
                            onToggle={(index) => setOpenFaqIndex((current) => (current === index ? null : index))}
                        />
                    </div>
                </section>
            </main>

            <footer id="footer-cta" className="border-t border-slate-200 bg-white py-20 lg:py-24">
                <div className="mx-auto max-w-6xl px-6 lg:px-8">
                    <div className="text-center">
                        <h2 className="text-[32px] font-bold leading-[1.2] text-slate-900 sm:text-[40px]">
                            Still have questions?
                        </h2>
                    </div>
                    <div className="mt-12 grid gap-6 md:grid-cols-3">
                        <a
                            href="tel:+10000000000"
                            aria-label="Call us"
                            className="flex items-center justify-center gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-6 py-5 text-base font-medium text-cyan-600 hover:underline"
                        >
                            <PhoneIcon />
                            <span>Call us: [PHONE]</span>
                        </a>
                        <a
                            href="https://wa.me/10000000000"
                            aria-label="Message us on WhatsApp"
                            className="flex items-center justify-center gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-6 py-5 text-base font-medium text-cyan-600 hover:underline"
                            target="_blank"
                            rel="noreferrer"
                        >
                            <WhatsAppIcon />
                            <span>Message us</span>
                        </a>
                        <a
                            href="mailto:hello@example.com"
                            aria-label="Email us"
                            className="flex items-center justify-center gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-6 py-5 text-base font-medium text-cyan-600 hover:underline"
                        >
                            <EmailIcon />
                            <span>Email: [EMAIL]</span>
                        </a>
                    </div>
                    <div className="mt-12 flex flex-col items-center justify-between gap-4 border-t border-slate-200 pt-8 text-center sm:flex-row sm:text-left">
                        <p className="text-sm font-medium text-slate-400">
                            Copyright © {currentYear} FinOps. All rights reserved.
                        </p>
                        <div className="flex items-center gap-6 text-sm font-medium text-cyan-600">
                            <Link href="/privacy" aria-label="Privacy policy" className="hover:underline">
                                Privacy
                            </Link>
                            <Link href="/terms" aria-label="Terms of service" className="hover:underline">
                                Terms
                            </Link>
                        </div>
                    </div>
                </div>
            </footer>
        </div>
    );
}
