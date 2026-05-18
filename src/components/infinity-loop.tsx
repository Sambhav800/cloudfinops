"use client";

import { useMemo } from "react";
import { motion } from "framer-motion";
import Image from "next/image";

const AGENTS = [
  { name: "DevOps", color: "#3b82f6", delay: 0, position: 0.1 },
  { name: "SRE", color: "#8b5cf6", delay: 0, position: 0.35 },
  { name: "AppSec", color: "#ef4444", delay: 0, position: 0.6 },
  { name: "FinOps", color: "#10b981", delay: 0, position: 0.85 },
  { name: "Release", color: "#f59e0b", delay: 0, position: 0.22 },
  { name: "Test", color: "#ec4899", delay: 0, position: 0.48 },
  { name: "Reliability", color: "#06b6d4", delay: 0, position: 0.72 },
];

export function InfinityLoop() {
  const pathDefinition = "M 400 200 C 550 200, 650 350, 700 300 C 750 250, 750 150, 700 100 C 650 50, 550 200, 400 200 C 250 200, 150 50, 100 100 C 50 150, 50 250, 100 300 C 150 350, 250 200, 400 200 Z";

  // Pre-compute deterministic packet values to avoid impure Math.random() during render
  const packets = useMemo(() =>
    [...Array(8)].map((_, i) => ({
      r: i % 2 === 0 ? 3 : 2,
      duration: 1.5 + (((i * 7 + 3) % 10) / 10),
      delay: ((i * 13 + 5) % 20) / 10,
    })), []);

  return (
    <div className="relative w-full aspect-[2/1] flex items-center justify-center select-none" style={{ perspective: "1000px" }}>
      {/* Ambient Background Glow */}
      <div className="absolute inset-0 bg-gradient-radial from-blue-500/10 via-transparent to-transparent blur-[80px] pointer-events-none" />

      {/* 3D Tilted Container */}
      <motion.div
        className="relative w-full max-w-4xl h-full flex items-center justify-center"
        initial={{ rotateX: 20 }}
        animate={{ rotateX: [20, 25, 20] }}
        transition={{ duration: 8, repeat: Infinity, ease: "easeInOut" }}
        style={{ transformStyle: "preserve-3d" }}
      >
        <svg
          viewBox="0 0 800 400"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="w-full h-full overflow-visible drop-shadow-[0_0_30px_rgba(60,130,246,0.2)]"
        >
          <defs>
            <linearGradient id="infinity-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.1" />
              <stop offset="50%" stopColor="#8b5cf6" stopOpacity="0.6" />
              <stop offset="100%" stopColor="#3b82f6" stopOpacity="0.1" />
            </linearGradient>

            <filter id="glow" x="-40%" y="-40%" width="180%" height="180%">
              <feGaussianBlur stdDeviation="12" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>
          </defs>

          {/* Base Path (Dim) */}
          <path
            d={pathDefinition}
            stroke="url(#infinity-gradient)"
            strokeWidth="6"
            className="opacity-20"
            strokeLinecap="round"
          />

          {/* Glowing Path (Bright) */}
          <path
            d={pathDefinition}
            stroke="url(#infinity-gradient)"
            strokeWidth="2"
            filter="url(#glow)"
            className="opacity-70"
          />

          {/* High-speed Data Packets - Enhanced */}
          {packets.map((packet, i) => (
            <motion.circle
              key={`packet-${i}`}
              r={packet.r}
              fill="#fff"
              initial={{ offsetDistance: "0%" }}
              animate={{ offsetDistance: "100%" }}
              transition={{
                duration: packet.duration,
                repeat: Infinity,
                ease: "linear",
                delay: packet.delay
              }}
              style={{
                offsetPath: `path("${pathDefinition}")`,
                filter: "drop-shadow(0 0 4px #fff)"
              }}
            />
          ))}
        </svg>

        {/* Center Logo Core - Transparent & Glowing */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 flex flex-col items-center z-20" style={{ transform: "translateZ(50px)" }}>
          <div className="relative group cursor-pointer">
            {/* Pulse Rings - Intense */}
            <div className="absolute inset-0 bg-blue-500/20 blur-[60px] rounded-full animate-pulse-slow" />
            <div className="absolute -inset-8 border border-blue-400/30 rounded-full animate-[spin_8s_linear_infinite]" />
            <div className="absolute -inset-16 border border-dashed border-indigo-500/20 rounded-full animate-[spin_12s_linear_infinite_reverse]" />

            {/* Logo Container - Minimalist/Transparent */}
            <div className="relative w-32 h-32 flex items-center justify-center transition-transform duration-500 group-hover:scale-110">
              <div className="relative w-28 h-28">
                <Image
                  src="/images/logo/wh-logo.png"
                  alt="Core"
                  fill
                  className="object-contain drop-shadow-[0_0_25px_rgba(59,130,246,0.6)]"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Orbiting Agent Nodes */}
        <div className="absolute inset-0 overflow-visible pointer-events-none">
          {AGENTS.map((agent, i) => (
            <AgentNode key={agent.name} agent={agent} index={i} total={AGENTS.length} path={pathDefinition} />
          ))}
        </div>
      </motion.div>
    </div>
  );
}

function AgentNode({ agent, index, total, path }: { agent: typeof AGENTS[0], index: number, total: number, path: string }) {
  return (
    <div className="absolute top-0 left-0 w-full h-full">
      {/* Node Dot */}
      <svg className="w-full h-full overflow-visible absolute top-0 left-0">
        <motion.circle
          r="4"
          fill="#fff"
          initial={{ offsetDistance: `${(index / total) * 100}%` }}
          animate={{ offsetDistance: ["0%", "100%"] }}
          transition={{
            duration: 12,
            repeat: Infinity,
            ease: "linear",
            delay: -index * (12 / total)
          }}
          style={{
            offsetPath: `path("${path}")`,
            filter: `drop-shadow(0 0 10px ${agent.color})`
          }}
        />
      </svg>

      {/* Holographic Label - Enhanced */}
      <motion.div
        className="absolute top-0 left-0 flex flex-col items-center justify-center -ml-16 -mt-16 w-32"
        initial={{ offsetDistance: `${(index / total) * 100}%` }}
        animate={{ offsetDistance: ["0%", "100%"] }}
        transition={{
          duration: 12,
          repeat: Infinity,
          ease: "linear",
          delay: -index * (12 / total)
        }}
        style={{
          offsetPath: `path("${path}")`,
          offsetRotate: "0deg",
          zIndex: 30
        }}
      >
        <div
          className="bg-black/60 backdrop-blur-sm border border-white/5 px-3 py-1 rounded-full shadow-[0_0_15px_rgba(0,0,0,0.5)] flex items-center gap-2 transform transition-all group-hover:scale-110"
          style={{ borderLeftColor: agent.color, borderLeftWidth: "2px" }}
        >
          <span className="text-[10px] font-bold text-gray-200 tracking-wider uppercase">{agent.name}</span>
        </div>
      </motion.div>
    </div>
  );
}
