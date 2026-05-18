"use client";

import { motion } from "framer-motion";

// Active Regions (Visual representation)
const REGIONS = [
    { lat: 38, lon: -78 }, // US East
    { lat: 37, lon: -121 }, // US West
    { lat: 50, lon: 8 }, // Europe Central
    { lat: 1, lon: 103 }, // Singapore
    { lat: 35, lon: 139 }, // Tokyo
    { lat: -23, lon: -46 }, // Sao Paulo
    { lat: -33, lon: 151 }, // Sydney
    { lat: 19, lon: 72 }, // Mumbai
    { lat: 51, lon: 0 }, // London
    { lat: 55, lon: 12 }, // Europe North
    { lat: 25, lon: 55 }, // Middle East
    { lat: -26, lon: 28 }, // Cape Town
];

export function GlobalMap() {
    return (
        <section className="relative py-24 bg-black overflow-hidden perspective-2000">
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,_var(--tw-gradient-stops))] from-blue-900/10 via-black to-black pointer-events-none" />

            <div className="mx-auto max-w-7xl px-6 lg:px-8 text-center relative z-10 mb-12">
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                >
                    <h2 className="text-blue-400 font-mono text-xs uppercase tracking-[0.2em] mb-4">
                        Planetary-Scale Observability
                    </h2>
                    <p className="text-3xl sm:text-5xl font-bold text-white tracking-tight mb-4">
                        Your Infrastructure. <br className="hidden sm:block" />
                        <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 via-purple-400 to-green-400">
                            Live. Global. Under Control.
                        </span>
                    </p>
                    <p className="text-gray-400 text-base max-w-2xl mx-auto leading-relaxed">
                        This isn&apos;t just a map—it&apos;s your <strong>Operational Command Center</strong>.
                        Visualize traffic, track latency, and secure assets across AWS, Azure, and Google Cloud in one unified, cinematic view.
                    </p>
                </motion.div>
            </div>

            <div className="relative w-full h-[450px] flex items-center justify-center">
                <Globe />
            </div>
        </section>
    );
}

function Globe() {
    return (
        <div className="relative w-[320px] h-[320px] sm:w-[420px] sm:h-[420px] flex items-center justify-center">
            <motion.div
                className="relative w-full h-full preserve-3d"
                initial={{ rotateY: 0, rotateZ: 20 }}
                animate={{ rotateY: 360, rotateZ: 20 }}
                transition={{ duration: 25, repeat: Infinity, ease: "linear" }}
                style={{ transformStyle: "preserve-3d" }}
            >
                {/* 1. Structural Rings (Defined Wireframe) - Increased Visibility */}
                {[...Array(8)].map((_, i) => (
                    <div
                        key={`lat-${i}`}
                        className="absolute inset-0 border border-blue-500/40 rounded-full" // Increased opacity from /10 to /40
                        style={{ transform: `rotateX(${i * 22.5}deg)` }}
                    />
                ))}
                {[...Array(8)].map((_, i) => (
                    <div
                        key={`lon-${i}`}
                        className="absolute inset-0 border border-blue-500/40 rounded-full" // Increased opacity from /10 to /40
                        style={{ transform: `rotateY(${i * 22.5}deg)` }}
                    />
                ))}

                {/* 2. The Core Glow - Brighter */}
                <div className="absolute inset-0 bg-blue-600/20 blur-[60px] rounded-full transform scale-90" />

                {/* 3. Active Regions */}
                {REGIONS.map((region, i) => (
                    <motion.div
                        key={i}
                        className="absolute top-1/2 left-1/2 flex items-center justify-center"
                        style={{
                            width: "0px", height: "0px",
                            transform: `rotateY(${region.lon}deg) rotateX(${-region.lat}deg) translateZ(210px)`, // Adjusted Z for smaller globe
                            transformStyle: "preserve-3d"
                        }}
                    >
                        {/* Connection Line to Core - Lighter */}
                        <div className="absolute top-1/2 left-1/2 w-[210px] h-[1px] bg-gradient-to-l from-blue-400/50 to-transparent origin-right -translate-x-full" />

                        {/* Pulse Effect */}
                        <div className="absolute w-3 h-3 bg-blue-400/40 rounded-full animate-ping" />

                        {/* Core Dot (Color coded for multi-cloud feel) - Brighter */}
                        <div className={`w-2 h-2 rounded-full shadow-[0_0_10px_currentColor] scale-125 ${i % 3 === 0 ? 'bg-orange-400 text-orange-400' : i % 3 === 1 ? 'bg-blue-400 text-blue-400' : 'bg-green-400 text-green-400'}`} />
                    </motion.div>
                ))}

                {/* 4. Orbital Satellites - Closer orbit */}
                <div className="absolute inset-0 rounded-full border border-blue-300/20 rotate-12 scale-110">
                    <motion.div
                        className="absolute top-0 left-1/2 w-2 h-2 bg-white rounded-full shadow-[0_0_10px_white]"
                        animate={{ offsetDistance: "100%" }}
                        style={{ offsetPath: "path('M 0,210 a 210,210 0 1,0 420,0 a 210,210 0 1,0 -420,0')", offsetRotate: "auto" }} // Adjusted path for smaller size (approx radius 210)
                        transition={{ duration: 5, repeat: Infinity, ease: "linear" }}
                    />
                </div>

            </motion.div>
        </div>
    );
}
