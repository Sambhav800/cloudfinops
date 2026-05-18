"use client";

import { motion } from "framer-motion";

const techStack = [
    {
        name: "AWS",
        svg: (
            <svg width="32" height="32" viewBox="0 0 48 48" fill="none">
                <path d="M13.527 21.529c0 .597.064 1.08.176 1.435.128.355.288.742.512 1.161.08.129.112.258.112.37 0 .161-.096.322-.304.484l-1.008.672a.77.77 0 01-.416.145c-.16 0-.32-.08-.48-.225a4.957 4.957 0 01-.576-.749 12.47 12.47 0 01-.496-.93c-1.248 1.47-2.816 2.206-4.704 2.206-1.344 0-2.416-.384-3.2-1.15-.784-.768-1.184-1.792-1.184-3.072 0-1.36.48-2.464 1.456-3.296.976-.832 2.272-1.248 3.92-1.248.544 0 1.104.048 1.696.128.592.08 1.2.208 1.84.368v-1.168c0-1.216-.256-2.064-.752-2.56-.512-.496-1.376-.736-2.608-.736-.56 0-1.136.064-1.728.208a12.726 12.726 0 00-1.728.544 4.588 4.588 0 01-.56.208.984.984 0 01-.256.048c-.224 0-.336-.16-.336-.496v-.784c0-.258.032-.45.112-.562a1.18 1.18 0 01.448-.337 9.22 9.22 0 011.984-.72A9.532 9.532 0 019.527 11c2.016 0 3.488.458 4.432 1.374.928.917 1.4 2.31 1.4 4.178v5.504h.168z" fill="#FF9900" />
                <path d="M43.527 33.95c-5.216 3.872-12.784 5.936-19.296 5.936-9.12 0-17.344-3.376-23.552-8.993-.496-.449-.048-1.057.544-.706 6.72 3.904 15.008 6.257 23.584 6.257 5.792 0 12.144-1.2 18-3.68.88-.385 1.616.577.72 1.185z" fill="#FF9900" />
            </svg>
        ),
    },
    {
        name: "Azure",
        svg: (
            <svg width="32" height="32" viewBox="0 0 48 48" fill="none">
                <path d="M17.28 5.25h12.45L16.74 42.75H5.25L17.28 5.25z" fill="#0078D4" />
                <path d="M33.48 15.75H21.9l-5.16 27h12.54l4.2-27z" fill="#0078D4" opacity="0.8" />
                <path d="M28.5 28.5L16.74 42.75h26.01L28.5 28.5z" fill="#0078D4" opacity="0.6" />
            </svg>
        ),
    },
    {
        name: "GCP",
        svg: (
            <svg width="32" height="32" viewBox="0 -25 256 256" preserveAspectRatio="xMidYMid meet">
                <path d="M170.252 56.819L192.505 34.566L193.988 25.196C153.437-11.677 88.976-7.496 52.421 33.92C42.267 45.423 34.734 59.764 30.717 74.573L38.687 73.45L83.192 66.111L86.628 62.597C106.425 40.855 139.898 37.93 162.756 56.429L170.252 56.819Z" fill="#EA4335" />
                <path d="M224.205 73.918C219.09 55.082 208.589 38.149 193.988 25.196L162.756 56.428C175.944 67.204 183.457 83.438 183.135 100.465V106.009C198.486 106.009 210.932 118.454 210.932 133.805C210.932 149.157 198.486 161.29 183.135 161.29H127.464L121.998 167.224V200.564L127.464 205.795H183.135C223.065 206.106 255.687 174.301 255.998 134.371C256.186 110.168 244.253 87.478 224.205 73.918" fill="#4285F4" />
                <path d="M71.87 205.796H127.463V161.29H71.87C67.909 161.289 64.073 160.438 60.471 158.792L52.584 161.212L30.175 183.465L28.223 191.039C40.79 200.528 56.123 205.864 71.87 205.796" fill="#34A853" />
                <path d="M71.87 61.426C31.939 61.664-0.237 94.228 0.001 134.158C0.134 156.456 10.548 177.446 28.223 191.039L60.471 158.792C46.48 152.471 40.263 136.006 46.584 122.016C52.904 108.026 69.37 101.809 83.359 108.129C89.524 110.914 94.461 115.852 97.246 122.016L129.494 89.769C115.773 71.832 94.453 61.345 71.87 61.426" fill="#FBBC05" />
            </svg>
        ),
    },
    {
        name: "MongoDB",
        svg: (
            <svg width="32" height="32" viewBox="0 0 109 113" fill="none">
                <path d="M63.708 110.284c-2.86 3.602-8.986 1.654-8.986-2.855V68.467h53.24c6.033 0 9.37 6.99 5.54 11.592l-49.794 30.225z" fill="#3ECF8E" />
                <path d="M63.708 110.284c-2.86 3.602-8.986 1.654-8.986-2.855V68.467h53.24c6.033 0 9.37 6.99 5.54 11.592l-49.794 30.225z" fill="url(#a)" fillOpacity=".2" />
                <path d="M45.318 2.072C48.177-1.53 54.303.418 54.303 4.927v38.962H1.062c-6.033 0-9.37-6.99-5.539-11.592L45.318 2.072z" fill="#3ECF8E" opacity=".7" />
                <defs><linearGradient id="a" x1="54.722" y1="82.326" x2="89.27" y2="99.148" gradientUnits="userSpaceOnUse"><stop stopColor="#249361" /><stop offset="1" stopColor="#3ECF8E" /></linearGradient></defs>
            </svg>
        ),
    },
    {
        name: "Next.js",
        svg: (
            <svg width="32" height="32" viewBox="0 0 180 180" fill="none">
                <mask id="mask0_408_139" style={{ maskType: "alpha" }} maskUnits="userSpaceOnUse" x="0" y="0" width="180" height="180">
                    <circle cx="90" cy="90" r="90" fill="black" />
                </mask>
                <g mask="url(#mask0_408_139)">
                    <circle cx="90" cy="90" r="87" fill="black" stroke="white" strokeWidth="6" />
                    <path d="M149.508 157.52L69.142 54H54V125.97H66.11V69.384L139.999 164.845C143.333 162.614 146.509 160.165 149.508 157.52Z" fill="url(#paint0)" />
                    <rect x="115" y="54" width="12" height="72" fill="url(#paint1)" />
                </g>
                <defs>
                    <linearGradient id="paint0" x1="109.5" y1="116.5" x2="144.5" y2="160.5" gradientUnits="userSpaceOnUse"><stop stopColor="white" /><stop offset="1" stopColor="white" stopOpacity="0" /></linearGradient>
                    <linearGradient id="paint1" x1="121" y1="54" x2="120.799" y2="106.875" gradientUnits="userSpaceOnUse"><stop stopColor="white" /><stop offset="1" stopColor="white" stopOpacity="0" /></linearGradient>
                </defs>
            </svg>
        ),
    },
];

export function TrustSection() {
    return (
        <section className="py-16 bg-black relative overflow-hidden border-t border-white/5">
            <div className="mx-auto max-w-5xl px-6 lg:px-8 relative z-10">
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.5 }}
                    className="text-center mb-10"
                >
                    <div className="inline-flex items-center gap-2 mb-5">
                        <span className="relative flex h-2.5 w-2.5">
                            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
                            <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-green-500" />
                        </span>
                        <span className="text-sm text-green-400 font-medium">Currently in Early Access</span>
                    </div>
                    <p className="text-gray-500 text-sm max-w-lg mx-auto">
                        Built on enterprise-grade infrastructure you already trust.
                    </p>
                </motion.div>

                {/* Tech Stack Logos */}
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.5, delay: 0.1 }}
                    className="flex flex-wrap items-center justify-center gap-8 md:gap-12"
                >
                    {techStack.map((tech, i) => (
                        <motion.div
                            key={tech.name}
                            initial={{ opacity: 0, scale: 0.8 }}
                            whileInView={{ opacity: 1, scale: 1 }}
                            viewport={{ once: true }}
                            transition={{ delay: i * 0.08 }}
                            className="flex flex-col items-center gap-2 opacity-50 hover:opacity-100 transition-opacity duration-300"
                        >
                            {tech.svg}
                            <span className="text-[10px] text-gray-600 uppercase tracking-wider">{tech.name}</span>
                        </motion.div>
                    ))}
                </motion.div>

                {/* Trust Metrics */}
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.5, delay: 0.2 }}
                    className="mt-12 grid grid-cols-2 md:grid-cols-4 gap-6 text-center"
                >
                    {[
                        { value: "AES-256", label: "Encryption Standard" },
                        { value: "Read-Only", label: "Cloud Access" },
                        { value: "SOC 2", label: "Compliance Ready" },
                        { value: "< 60s", label: "First Scan" },
                    ].map((metric, i) => (
                        <motion.div
                            key={metric.label}
                            initial={{ opacity: 0, y: 10 }}
                            whileInView={{ opacity: 1, y: 0 }}
                            viewport={{ once: true }}
                            transition={{ delay: 0.3 + i * 0.05 }}
                        >
                            <div className="text-xl font-bold text-white">{metric.value}</div>
                            <div className="text-xs text-gray-500 mt-1">{metric.label}</div>
                        </motion.div>
                    ))}
                </motion.div>
            </div>
        </section>
    );
}
