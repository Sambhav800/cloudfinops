"use client";

import { useRef, useState, MouseEvent } from "react";
import { motion, useMotionValue, useSpring } from "framer-motion";
import { clsx } from "clsx";

export function SpotlightCard({
    children,
    className = "",
    spotlightColor = "rgba(0, 210, 255, 0.15)",
    enableTilt = true
}: {
    children: React.ReactNode;
    className?: string;
    spotlightColor?: string;
    enableTilt?: boolean;
}) {
    const divRef = useRef<HTMLDivElement>(null);
    const [isFocused, setIsFocused] = useState(false);
    const [position, setPosition] = useState({ x: 0, y: 0 });
    const [opacity, setOpacity] = useState(0);

    // 3D Tilt State
    const _mouseX = useMotionValue(0);
    const _mouseY = useMotionValue(0);

    const rotateX = useSpring(useMotionValue(0), { stiffness: 150, damping: 20 });
    const rotateY = useSpring(useMotionValue(0), { stiffness: 150, damping: 20 });

    const handleMouseMove = (e: MouseEvent<HTMLDivElement>) => {
        if (!divRef.current) return;

        const div = divRef.current;
        const rect = div.getBoundingClientRect();

        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        setPosition({ x, y });

        if (enableTilt) {
            // Calculate tilt based on center of card
            const centerX = rect.width / 2;
            const centerY = rect.height / 2;

            // Normalize values (-1 to 1)
            const rotateXValue = ((y - centerY) / centerY) * -10; // Max tilt 10deg
            const rotateYValue = ((x - centerX) / centerX) * 10;

            rotateX.set(rotateXValue);
            rotateY.set(rotateYValue);
        }
    };

    const handleMouseEnter = () => {
        setOpacity(1);
        setIsFocused(true);
    };

    const handleMouseLeave = () => {
        setOpacity(0);
        setIsFocused(false);
        rotateX.set(0);
        rotateY.set(0);
    };

    return (
        <motion.div
            ref={divRef}
            onMouseMove={handleMouseMove}
            onMouseEnter={handleMouseEnter}
            onMouseLeave={handleMouseLeave}
            style={{
                perspective: 1000,
                rotateX: enableTilt ? rotateX : 0,
                rotateY: enableTilt ? rotateY : 0,
                scale: isFocused && enableTilt ? 1.02 : 1,
            }}
            className={clsx(
                "relative rounded-3xl border border-white/10 bg-white/5 overflow-hidden transition-all duration-200 ease-out",
                className
            )}
        >
            <div
                className="pointer-events-none absolute -inset-px opacity-0 transition duration-300"
                style={{
                    opacity,
                    background: `radial-gradient(600px circle at ${position.x}px ${position.y}px, ${spotlightColor}, transparent 40%)`,
                }}
            />
            <div className="relative h-full">{children}</div>
        </motion.div>
    );
}
