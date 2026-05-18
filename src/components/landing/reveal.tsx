"use client";

import { motion } from "framer-motion";
import type { ReactNode } from "react";
import { EASE } from "@/components/landing/tokens";

type RevealProps = {
    children: ReactNode;
    delay?: number;
    y?: number;
    once?: boolean;
};

export function Reveal({
    children,
    delay = 0,
    y = 24,
    once = true,
}: RevealProps) {
    return (
        <motion.div
            initial={{ opacity: 0, y }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once, margin: "-80px" }}
            transition={{ duration: 0.7, delay, ease: EASE }}
        >
            {children}
        </motion.div>
    );
}
