"use client";

import Image from "next/image";
import Link from "next/link";

const footerColumns = [
    {
        title: "Product",
        links: [
            { label: "Features", href: "/features" },
            { label: "How it works", href: "/how-it-works" },
            { label: "Security", href: "/security" },
            { label: "Dashboard", href: "/dashboard" },
        ],
    },
    {
        title: "Company",
        links: [
            { label: "About", href: "/about" },
        ],
    },
    {
        title: "Legal",
        links: [
            { label: "Privacy", href: "/privacy" },
            { label: "Terms", href: "/terms" },
            { label: "Refund", href: "/refund" },
        ],
    },
];

export function Footer() {
    return (
        <footer className="border-t border-white/[0.06] bg-[#07080c] px-6 py-20">
            <div className="mx-auto max-w-7xl">
                <div className="grid grid-cols-2 gap-12 md:grid-cols-5">
                    <div className="md:col-span-2">
                        <Link href="/" className="flex items-center gap-2.5" aria-label="CloudFinOps home">
                            <div className="relative h-7 w-7 overflow-hidden rounded-lg border border-white/[0.08] bg-white/[0.02] p-1">
                                <Image
                                    src="/images/logo/wh-logo.png"
                                    alt="CloudFinOps logo"
                                    fill
                                    className="object-contain p-1"
                                    sizes="28px"
                                />
                            </div>
                            <span className="text-[15px] font-semibold tracking-[-0.02em] text-white">
                                CloudFinOps
                            </span>
                        </Link>
                        <p className="mt-4 max-w-xs text-[13px] leading-6 text-zinc-500">
                            Cloud financial operations for engineers.
                        </p>
                        <div className="mt-6 flex items-center gap-2">
                            <span className="h-2 w-2 rounded-full bg-emerald-500" aria-hidden="true" />
                            <span className="text-[12px] text-zinc-500">All systems operational</span>
                        </div>
                    </div>

                    {footerColumns.map((column) => (
                        <div key={column.title}>
                            <p className="mb-4 text-[12px] font-medium uppercase tracking-widest text-zinc-500">
                                {column.title}
                            </p>
                            <div>
                                {column.links.map((link) => (
                                    <Link
                                        key={link.href}
                                        href={link.href}
                                        className="block py-1 text-[13px] text-zinc-400 transition-colors duration-200 hover:text-white"
                                    >
                                        {link.label}
                                    </Link>
                                ))}
                            </div>
                        </div>
                    ))}
                </div>

                <div className="mt-16 flex flex-col items-start justify-between gap-4 border-t border-white/[0.06] pt-8 md:flex-row md:items-center">
                    <p className="text-[12px] text-zinc-600">© 2025 CloudFinOps. All rights reserved.</p>
                    <p className="text-[12px] text-zinc-600">UDYAM-PB-20-0114306 · Made in India</p>
                </div>
            </div>
        </footer>
    );
}
