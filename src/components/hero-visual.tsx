"use client";

import { useMemo } from "react";

export function HeroVisual() {
  // Deterministic node positions (normalized 0-100)
  const nodes = useMemo(() => [
    { id: 1, x: 20, y: 30 },
    { id: 2, x: 35, y: 15 },
    { id: 3, x: 50, y: 40 },
    { id: 4, x: 65, y: 20 },
    { id: 5, x: 80, y: 35 },
    { id: 6, x: 25, y: 60 },
    { id: 7, x: 40, y: 75 },
    { id: 8, x: 55, y: 55 },
    { id: 9, x: 70, y: 70 },
    { id: 10, x: 85, y: 55 },
    { id: 11, x: 15, y: 80 },
    { id: 12, x: 30, y: 90 },
    { id: 13, x: 45, y: 85 },
    { id: 14, x: 60, y: 90 },
    { id: 15, x: 75, y: 80 },
  ], []);

  // Connections between nodes (hand-picked for visual appeal)
  const connections = useMemo(() => [
    { from: 1, to: 2 },
    { from: 2, to: 3 },
    { from: 3, to: 4 },
    { from: 4, to: 5 },
    { from: 1, to: 6 },
    { from: 6, to: 7 },
    { from: 7, to: 8 },
    { from: 8, to: 9 },
    { from: 9, to: 10 },
    { from: 3, to: 8 },
    { from: 4, to: 9 },
    { from: 6, to: 11 },
    { from: 11, to: 12 },
    { from: 12, to: 13 },
    { from: 13, to: 14 },
    { from: 14, to: 15 },
    { from: 8, to: 13 },
    { from: 9, to: 14 },
    { from: 10, to: 15 },
  ], []);

  // Create SVG paths for connections
  const connectionPaths = useMemo(() => {
    return connections.map((conn) => {
      const fromNode = nodes.find((n) => n.id === conn.from);
      const toNode = nodes.find((n) => n.id === conn.to);
      if (!fromNode || !toNode) return null;
      return {
        id: `conn-${conn.from}-${conn.to}`,
        d: `M ${fromNode.x} ${fromNode.y} L ${toNode.x} ${toNode.y}`,
        delay: (conn.from + conn.to) * 0.1,
      };
    }).filter((p): p is NonNullable<typeof p> => p !== null);
  }, [connections, nodes]);

  // Pulse animations (small circles moving along paths)
  const pulses = useMemo(() => {
    return connectionPaths.map((path, i) => {
      if (!path) return null;
      return {
        id: `pulse-${i}`,
        pathId: path.id,
        duration: 3 + (i % 5) * 0.5,
        delay: path.delay,
        color: i % 3 === 0 ? "#814AC8" : i % 3 === 1 ? "#60A5FA" : "#34D399",
      };
    }).filter((p): p is NonNullable<typeof p> => p !== null);
  }, [connectionPaths]);

  return (
    <div className="relative w-full aspect-[4/3] md:aspect-video lg:aspect-[3/2] overflow-hidden">
      <svg
        viewBox="0 0 100 100"
        className="w-full h-full"
        preserveAspectRatio="xMidYMid meet"
        aria-hidden="true"
      >
        <defs>
          {/* Grid pattern */}
          <pattern id="grid" width="10" height="10" patternUnits="userSpaceOnUse">
            <path
              d="M 10 0 L 0 0 0 10"
              fill="none"
              stroke="rgba(255,255,255,0.02)"
              strokeWidth="0.2"
            />
          </pattern>
          {/* Glow filter */}
          <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="0.8" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          {/* Gradient for pulses */}
          <linearGradient id="pulseGradient" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#814AC8" stopOpacity="0" />
            <stop offset="50%" stopColor="#814AC8" stopOpacity="1" />
            <stop offset="100%" stopColor="#814AC8" stopOpacity="0" />
          </linearGradient>
        </defs>

        {/* Background grid */}
        <rect width="100" height="100" fill="url(#grid)" />

        {/* Connection lines */}
        {connectionPaths.map((path) => (
          <g key={path.id}>
            <path
              d={path.d}
              fill="none"
              stroke="rgba(129, 74, 200, 0.15)"
              strokeWidth="0.4"
              strokeLinecap="round"
            />
            {/* Glow line */}
            <path
              d={path.d}
              fill="none"
              stroke="rgba(129, 74, 200, 0.08)"
              strokeWidth="1.2"
              strokeLinecap="round"
              filter="url(#glow)"
            />
          </g>
        ))}

        {/* Nodes */}
        {nodes.map((node) => (
          <g key={node.id}>
            {/* Outer glow */}
            <circle
              cx={node.x}
              cy={node.y}
              r="2"
              fill="rgba(129, 74, 200, 0.1)"
              filter="url(#glow)"
            />
            {/* Inner core */}
            <circle
              cx={node.x}
              cy={node.y}
              r="1"
              fill="#814AC8"
              opacity="0.8"
            />
            {/* Pulsing ring */}
            <circle
              cx={node.x}
              cy={node.y}
              r="1.5"
              fill="none"
              stroke="#814AC8"
              strokeWidth="0.2"
              opacity="0.3"
            >
              <animate
                attributeName="r"
                values="1.5;3;1.5"
                dur="4s"
                repeatCount="indefinite"
                begin={`${node.id * 0.2}s`}
              />
              <animate
                attributeName="opacity"
                values="0.3;0.1;0.3"
                dur="4s"
                repeatCount="indefinite"
                begin={`${node.id * 0.2}s`}
              />
            </circle>
          </g>
        ))}

        {/* Animated pulses along connections */}
        {pulses.map((pulse) => (
          <circle
            key={pulse.id}
            r="0.8"
            fill={pulse.color}
            filter="url(#glow)"
          >
            <animateMotion
              dur={`${pulse.duration}s`}
              repeatCount="indefinite"
              begin={`${pulse.delay}s`}
            >
              <mpath href={`#${pulse.pathId}`} />
            </animateMotion>
            <animate
              attributeName="opacity"
              values="0;1;0"
              dur={`${pulse.duration}s`}
              repeatCount="indefinite"
              begin={`${pulse.delay}s`}
            />
          </circle>
        ))}

        {/* Subtle radial gradient overlay */}
        <radialGradient id="overlay" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="rgba(129, 74, 200, 0.05)" />
          <stop offset="100%" stopColor="transparent" />
        </radialGradient>
        <rect width="100" height="100" fill="url(#overlay)" />
      </svg>


    </div>
  );
}
