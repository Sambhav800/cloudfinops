"use client";

import { motion } from "framer-motion";
import { Children, ReactNode } from "react";

interface FeatureBlockProps {
    badge: string;
    title: string;
    description: string;
    tags?: string[];
    visual: ReactNode;
    reversed?: boolean;
    accentColor?: string;
}

export function FeatureBlock({
    badge,
    title,
    description,
    tags = [],
    visual,
    reversed = false,
    accentColor = "primary"
}: FeatureBlockProps) {
    return (
        <section className="py-16 relative overflow-hidden">
            <div className="mx-auto max-w-7xl px-6 lg:px-8">
                <div className={`grid lg:grid-cols-2 gap-12 items-center ${reversed ? "lg:flex-row-reverse" : ""}`}>

                    {/* Text Content */}
                    <motion.div
                        initial={{ opacity: 0, x: reversed ? 40 : -40 }}
                        whileInView={{ opacity: 1, x: 0 }}
                        viewport={{ once: true }}
                        transition={{ duration: 0.6 }}
                        className={`${reversed ? "lg:order-2" : "lg:order-1"}`}
                    >
                        <span className={`text-xs font-medium text-${accentColor} uppercase tracking-widest`}>
                            {badge}
                        </span>

                        <h3 className="text-3xl md:text-4xl font-semibold text-white mt-3 mb-4">
                            {title}
                        </h3>

                        <p className="text-gray-400 text-lg leading-relaxed max-w-lg">
                            {description}
                        </p>

                        {tags.length > 0 && (
                            <div className="flex flex-wrap gap-2 mt-6">
                                {tags.map((tag) => (
                                    <span
                                        key={`${badge}-${tag}`}
                                        className="text-xs bg-white/5 border border-white/10 rounded-full px-4 py-2 text-gray-400 hover:bg-white/10 transition-colors cursor-default"
                                    >
                                        {tag}
                                    </span>
                                ))}
                            </div>
                        )}
                    </motion.div>

                    {/* Visual Content */}
                    <motion.div
                        initial={{ opacity: 0, x: reversed ? -40 : 40 }}
                        whileInView={{ opacity: 1, x: 0 }}
                        viewport={{ once: true }}
                        transition={{ duration: 0.6, delay: 0.1 }}
                        className={`relative ${reversed ? "lg:order-1" : "lg:order-2"}`}
                    >
                        <div className="glass-card p-6 relative overflow-hidden">
                            {Children.toArray(visual)}
                            {/* Background glow */}
                            <div className={`absolute -top-10 -right-10 w-40 h-40 bg-${accentColor}/20 blur-[60px] rounded-full pointer-events-none`} />
                        </div>
                    </motion.div>

                </div>
            </div>
        </section>
    );
}
