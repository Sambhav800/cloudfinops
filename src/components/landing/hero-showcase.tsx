"use client";

import { motion, useScroll, useSpring, useTransform } from "framer-motion";
import { useRef } from "react";
import { DashboardMockup } from "@/components/landing/mockups/dashboard-mockup";
import { ResourcesMockup } from "@/components/landing/mockups/resources-mockup";
import { SavingsMockup } from "@/components/landing/mockups/savings-mockup";

export function HeroShowcase() {
    const containerRef = useRef<HTMLDivElement | null>(null);
    const { scrollYProgress } = useScroll({
        target: containerRef,
        offset: ["start end", "end start"],
    });

    const springConfig = { stiffness: 80, damping: 20, restDelta: 0.001 };

    const mainRotate = useTransform(scrollYProgress, [0, 0.3], [12, 0]);
    const mainScale = useTransform(scrollYProgress, [0, 0.3], [0.92, 1]);
    const mainY = useTransform(scrollYProgress, [0, 0.3], [80, 0]);

    const leftX = useTransform(scrollYProgress, [0, 0.4], [0, -40]);
    const leftY = useTransform(scrollYProgress, [0, 0.4], [120, 20]);
    const leftRotate = useTransform(scrollYProgress, [0, 0.4], [18, -4]);

    const rightX = useTransform(scrollYProgress, [0, 0.4], [0, 40]);
    const rightY = useTransform(scrollYProgress, [0, 0.4], [120, 40]);
    const rightRotate = useTransform(scrollYProgress, [0, 0.4], [18, -4]);

    const mainRotateSpring = useSpring(mainRotate, springConfig);
    const mainScaleSpring = useSpring(mainScale, springConfig);
    const mainYSpring = useSpring(mainY, springConfig);

    const leftXSpring = useSpring(leftX, springConfig);
    const leftYSpring = useSpring(leftY, springConfig);
    const leftRotateSpring = useSpring(leftRotate, springConfig);

    const rightXSpring = useSpring(rightX, springConfig);
    const rightYSpring = useSpring(rightY, springConfig);
    const rightRotateSpring = useSpring(rightRotate, springConfig);

    return (
        <div ref={containerRef} className="relative mt-32">
            <div className="pointer-events-none absolute inset-x-0 bottom-0 z-10 h-64 bg-[radial-gradient(ellipse_50%_50%_at_50%_100%,rgba(99,102,241,0.3),transparent_70%)] blur-2xl" />

            <div className="relative h-[460px] w-full [perspective:1600px] sm:h-[520px] md:h-[700px]">
                <motion.div
                    className="absolute inset-x-0 top-0 z-20 mx-auto w-full max-w-5xl"
                    style={{
                        rotateX: mainRotateSpring,
                        scale: mainScaleSpring,
                        y: mainYSpring,
                        transformStyle: "preserve-3d",
                    }}
                >
                    <DashboardMockup />
                </motion.div>

                <motion.div
                    className="absolute bottom-0 left-0 z-30 hidden w-[340px] md:block"
                    style={{
                        x: leftXSpring,
                        y: leftYSpring,
                        rotate: leftRotateSpring,
                    }}
                >
                    <ResourcesMockup />
                </motion.div>

                <motion.div
                    className="absolute bottom-8 right-0 z-30 hidden w-[340px] md:block"
                    style={{
                        x: rightXSpring,
                        y: rightYSpring,
                        rotate: rightRotateSpring,
                    }}
                >
                    <SavingsMockup />
                </motion.div>
            </div>
        </div>
    );
}
