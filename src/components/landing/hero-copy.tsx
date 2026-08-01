"use client";

import { SignedIn, SignedOut } from "@clerk/nextjs";
import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowRight } from "lucide-react";
import { EASE } from "@/components/landing/tokens";

const containerVariants = {
    hidden: {},
    visible: {
        transition: {
            staggerChildren: 0.08,
            delayChildren: 0.1,
        },
    },
};

const itemVariants = {
    hidden: { opacity: 0, y: 24 },
    visible: {
        opacity: 1,
        y: 0,
        transition: {
            duration: 0.8,
            ease: EASE,
        },
    },
};

export function HeroCopy() {
    return (
        <motion.div
            className="mx-auto max-w-4xl text-center"
            variants={containerVariants}
            initial="hidden"
            animate="visible"
        >
            <motion.div variants={itemVariants} className="inline-flex items-center gap-2 rounded-full border border-white/[0.08] bg-white/[0.02] px-3 py-1">
                <span className="relative flex h-2 w-2 items-center justify-center" aria-hidden="true">
                    <span className="absolute inset-0 rounded-full bg-emerald-400 opacity-75 animate-ping" />
                    <span className="relative h-2 w-2 rounded-full bg-emerald-400" />
                </span>
                <span className="text-[12px] text-zinc-400">Live on cloudfinops.solutions</span>
            </motion.div>

            <motion.h1
                variants={itemVariants}
                className="mt-6 text-[56px] font-medium leading-[1.02] tracking-[-0.04em] text-white md:text-[72px] lg:text-[88px]"
            >
                The FinOps platform
                <br />
                <span className="text-zinc-500">engineers actually want to use.</span>
            </motion.h1>

            <motion.p
                variants={itemVariants}
                className="mx-auto mt-8 max-w-2xl text-[17px] leading-[1.6] text-zinc-400 md:text-[19px]"
            >
                CloudFinOps is an AI-powered cloud cost optimization platform that detects idle resources, eliminates waste, and automates governance across AWS, Azure, and GCP — with read-only, agentless access that sets up in under 5 minutes.
            </motion.p>

            <motion.div variants={itemVariants} className="mt-10 flex flex-col justify-center gap-3 sm:flex-row">
                <SignedOut>
                    <Link
                        href="/login"
                        aria-label="Start free"
                        className="group inline-flex items-center justify-center gap-2 rounded-lg bg-white px-5 py-2.5 text-[14px] font-medium text-black transition-all duration-200 hover:bg-zinc-200"
                    >
                        <span>Start free</span>
                        <ArrowRight className="h-[14px] w-[14px] transition-transform duration-200 group-hover:translate-x-0.5" />
                    </Link>
                </SignedOut>
                <SignedIn>
                    <Link
                        href="/dashboard"
                        aria-label="Open dashboard"
                        className="group inline-flex items-center justify-center gap-2 rounded-lg bg-white px-5 py-2.5 text-[14px] font-medium text-black transition-all duration-200 hover:bg-zinc-200"
                    >
                        <span>Dashboard</span>
                        <ArrowRight className="h-[14px] w-[14px] transition-transform duration-200 group-hover:translate-x-0.5" />
                    </Link>
                </SignedIn>
                <Link
                    href="/how-it-works"
                    aria-label="See how it works"
                    className="inline-flex items-center justify-center rounded-lg border border-white/[0.08] bg-white/[0.04] px-5 py-2.5 text-[14px] font-medium text-white transition duration-200 hover:border-white/[0.12] hover:bg-white/[0.08]"
                >
                    See how it works
                </Link>
            </motion.div>
        </motion.div>
    );
}
