const config = {
    content: [
        "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
        "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
        "./node_modules/@tremor/**/*.{js,ts,jsx,tsx}", // Important for Tremor
    ],
    theme: {
        extend: {
            colors: {
                // Custom 'white' palette for Tremor charts
                white: {
                    50: "#ffffff",
                    100: "#ffffff",
                    200: "#ffffff",
                    300: "#ffffff",
                    400: "#ffffff",
                    500: "#ffffff", // Main color used by Tremor
                    600: "#e5e7eb", // Slightly darker for interaction?
                    700: "#d1d5db",
                    800: "#9ca3af",
                    900: "#6b7280",
                    950: "#374151",
                },
                // Tremor colors
                tremor: {
                    brand: {
                        faint: "#eff6ff", // blue-50
                        muted: "#bfdbfe", // blue-200
                        subtle: "#60a5fa", // blue-400
                        DEFAULT: "#3b82f6", // blue-500
                        emphasis: "#1d4ed8", // blue-700
                        inverted: "#ffffff", // white
                    },
                    background: {
                        muted: "#f9fafb", // gray-50
                        subtle: "#f3f4f6", // gray-100
                        DEFAULT: "#ffffff", // white
                        emphasis: "#374151", // gray-700
                    },
                    border: {
                        DEFAULT: "#e5e7eb", // gray-200
                    },
                    ring: {
                        DEFAULT: "#e5e7eb", // gray-200
                    },
                    content: {
                        subtle: "#9ca3af", // gray-400
                        DEFAULT: "#6b7280", // gray-500
                        emphasis: "#374151", // gray-700
                        strong: "#111827", // gray-900
                        inverted: "#ffffff", // white
                    },
                },
            },
            animation: {
                "marquee": "marquee 25s linear infinite",
                "pulse-slow": "pulse 4s cubic-bezier(0.4, 0, 0.6, 1) infinite",
                "spin-slow": "spin 8s linear infinite",
            },
            keyframes: {
                marquee: {
                    "0%": { transform: "translateX(0%)" },
                    "100%": { transform: "translateX(-100%)" },
                },
            },
        },
    },
    safelist: [
        {
            pattern:
                /^(bg|text|border|ring|stroke|fill)-(blue|cyan|sky|indigo|violet|fuchsia|rose|orange|emerald|white)-(50|100|200|300|400|500|600|700|800|900|950)$/,
        },
        {
            pattern: /^(w|h)-.+/, // Safelist width/height utils often used dynamically
        }
    ],
    plugins: [],
};

export default config;
