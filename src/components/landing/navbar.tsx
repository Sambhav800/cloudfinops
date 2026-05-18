"use client";

import Image from "next/image";
import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, Menu, X } from "lucide-react";
import { useEffect, useState } from "react";
import { SignedIn, SignedOut, UserButton } from "@clerk/nextjs";
import { EASE } from "@/components/landing/tokens";

const navLinks = [
    { label: "Features", href: "/features" },
    { label: "How it works", href: "/how-it-works" },
    { label: "Security", href: "/security" },
    { label: "About", href: "/about" },
];

export function Navbar() {
    const [isScrolled, setIsScrolled] = useState(false);
    const [isMenuOpen, setIsMenuOpen] = useState(false);

    useEffect(() => {
        const handleScroll = () => {
            setIsScrolled(window.scrollY > 20);
        };

        handleScroll();
        window.addEventListener("scroll", handleScroll, { passive: true });

        return () => {
            window.removeEventListener("scroll", handleScroll);
        };
    }, []);

    useEffect(() => {
        const closeMenu = () => setIsMenuOpen(false);
        window.addEventListener("resize", closeMenu);

        return () => {
            window.removeEventListener("resize", closeMenu);
        };
    }, []);

    return (
        <header
            className={`fixed inset-x-0 top-0 z-50 transition-all duration-200 ${
                isScrolled
                    ? "border-b border-white/[0.06] bg-[#07080c]/80 backdrop-blur-xl"
                    : "border-b border-transparent bg-transparent"
            }`}
        >
            <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6">
                <Link href="/" className="flex items-center gap-2.5" aria-label="CloudFinOps home">
                    <div className="relative h-7 w-7 overflow-hidden rounded-lg border border-white/[0.08] bg-white/[0.02] p-1">
                        <Image
                            src="/images/logo/wh-logo.png"
                            alt="CloudFinOps logo"
                            fill
                            className="object-contain p-1"
                            sizes="28px"
                        />
                        <motion.span
                            aria-hidden="true"
                            className="absolute -right-0.5 -top-0.5 h-2.5 w-2.5 rounded-full bg-indigo-500 ring-2 ring-[#07080c]"
                            animate={{ opacity: [0.6, 1, 0.6] }}
                            transition={{
                                duration: 2,
                                ease: "easeInOut",
                                repeat: Number.POSITIVE_INFINITY,
                            }}
                        />
                    </div>
                    <span className="text-[15px] font-semibold tracking-[-0.02em] text-white">
                        CloudFinOps
                    </span>
                </Link>

                <nav
                    aria-label="Primary navigation"
                    className="hidden items-center gap-8 md:flex"
                >
                    {navLinks.map((link) => (
                        <Link
                            key={link.href}
                            href={link.href}
                            className="text-[13px] text-zinc-400 transition-colors duration-200 hover:text-white"
                        >
                            {link.label}
                        </Link>
                    ))}
                </nav>

                <div className="hidden items-center gap-2 md:flex">
                    <SignedOut>
                        <Link
                            href="/login"
                            className="rounded-lg px-3 py-2 text-[13px] text-zinc-400 transition-colors duration-200 hover:text-white"
                            aria-label="Sign in"
                        >
                            Sign in
                        </Link>
                        <Link
                            href="/login"
                            className="group inline-flex items-center gap-2 rounded-lg bg-white px-4 py-2 text-[13px] font-medium text-black transition-colors duration-200 hover:bg-zinc-200"
                            aria-label="Start free"
                        >
                            <span>Start free</span>
                            <ArrowRight className="h-[14px] w-[14px] transition-transform duration-200 group-hover:translate-x-0.5" />
                        </Link>
                    </SignedOut>
                    <SignedIn>
                        <Link
                            href="/dashboard"
                            className="rounded-lg px-3 py-2 text-[13px] text-zinc-400 transition-colors duration-200 hover:text-white"
                            aria-label="Open dashboard"
                        >
                            Dashboard
                        </Link>
                        <UserButton
                            appearance={{
                                elements: {
                                    avatarBox:
                                        "h-9 w-9 border border-white/10 shadow-none ring-0",
                                },
                            }}
                        />
                    </SignedIn>
                </div>

                <button
                    type="button"
                    className="inline-flex items-center justify-center rounded-lg p-2 text-zinc-400 transition-colors duration-200 hover:text-white md:hidden"
                    onClick={() => setIsMenuOpen((open) => !open)}
                    aria-expanded={isMenuOpen}
                    aria-label={isMenuOpen ? "Close menu" : "Open menu"}
                >
                    {isMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
                </button>
            </div>

            <AnimatePresence initial={false}>
                {isMenuOpen ? (
                    <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.3, ease: EASE }}
                        className="overflow-hidden border-b border-white/[0.06] bg-[#07080c]/95 backdrop-blur-xl md:hidden"
                    >
                        <div className="mx-auto flex max-w-7xl flex-col gap-2 px-6 py-5">
                            {navLinks.map((link) => (
                                <Link
                                    key={link.href}
                                    href={link.href}
                                    onClick={() => setIsMenuOpen(false)}
                                    className="rounded-lg px-2 py-3 text-[14px] text-zinc-300 transition-colors duration-200 hover:text-white"
                                >
                                    {link.label}
                                </Link>
                            ))}
                            <div className="mt-4 flex flex-col gap-3 border-t border-white/[0.06] pt-4">
                                <SignedOut>
                                    <Link
                                        href="/login"
                                        onClick={() => setIsMenuOpen(false)}
                                        className="rounded-lg px-2 py-3 text-[14px] text-zinc-400 transition-colors duration-200 hover:text-white"
                                    >
                                        Sign in
                                    </Link>
                                    <Link
                                        href="/login"
                                        onClick={() => setIsMenuOpen(false)}
                                        className="inline-flex items-center justify-center gap-2 rounded-lg bg-white px-4 py-3 text-[14px] font-medium text-black transition-colors duration-200 hover:bg-zinc-200"
                                    >
                                        <span>Start free</span>
                                        <ArrowRight className="h-[14px] w-[14px]" />
                                    </Link>
                                </SignedOut>
                                <SignedIn>
                                    <Link
                                        href="/dashboard"
                                        onClick={() => setIsMenuOpen(false)}
                                        className="inline-flex items-center justify-center rounded-lg border border-white/[0.08] bg-white/[0.04] px-4 py-3 text-[14px] font-medium text-white transition-colors duration-200 hover:bg-white/[0.08]"
                                    >
                                        Dashboard
                                    </Link>
                                    <div className="flex justify-center pt-1">
                                        <UserButton
                                            appearance={{
                                                elements: {
                                                    avatarBox: "h-10 w-10 border border-white/10",
                                                },
                                            }}
                                        />
                                    </div>
                                </SignedIn>
                            </div>
                        </div>
                    </motion.div>
                ) : null}
            </AnimatePresence>
        </header>
    );
}
