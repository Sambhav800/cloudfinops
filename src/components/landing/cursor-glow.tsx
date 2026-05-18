"use client";

import { motion, useMotionValue, useSpring } from "framer-motion";
import { useEffect, useState } from "react";

const GLOW_SIZE = 600;

export function CursorGlow() {
    const [enabled, setEnabled] = useState(false);
    const x = useMotionValue(-GLOW_SIZE);
    const y = useMotionValue(-GLOW_SIZE);
    const springX = useSpring(x, { stiffness: 50, damping: 20 });
    const springY = useSpring(y, { stiffness: 50, damping: 20 });

    useEffect(() => {
        if (typeof window === "undefined") {
            return undefined;
        }

        const mediaQuery = window.matchMedia("(pointer: coarse)");
        const updateEnabled = () => setEnabled(!mediaQuery.matches);

        updateEnabled();
        mediaQuery.addEventListener("change", updateEnabled);

        const handlePointerMove = (event: MouseEvent) => {
            x.set(event.clientX - GLOW_SIZE / 2);
            y.set(event.clientY - GLOW_SIZE / 2);
        };

        window.addEventListener("mousemove", handlePointerMove, { passive: true });

        return () => {
            mediaQuery.removeEventListener("change", updateEnabled);
            window.removeEventListener("mousemove", handlePointerMove);
        };
    }, [x, y]);

    if (!enabled) {
        return null;
    }

    return (
        <motion.div
            aria-hidden="true"
            className="pointer-events-none fixed left-0 top-0 z-0 h-[600px] w-[600px] blur-3xl"
            style={{
                x: springX,
                y: springY,
                background:
                    "radial-gradient(circle, rgba(99,102,241,0.08) 0%, transparent 70%)",
            }}
        />
    );
}
