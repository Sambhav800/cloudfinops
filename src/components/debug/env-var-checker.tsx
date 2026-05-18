"use client";

import { useEffect } from "react";

export function EnvVarChecker() {
    useEffect(() => {
        const requiredVars = {
            "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY": process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY,
            "NEXT_PUBLIC_BACKEND_URL": process.env.NEXT_PUBLIC_BACKEND_URL,
        };

        const missingVars = Object.entries(requiredVars)
            .filter(([_, value]) => !value)
            .map(([key]) => key);

        if (missingVars.length > 0) {
            console.error(
                "%c[CRITICAL CONFIG ERROR] Missing Environment Variables:",
                "background: red; color: white; padding: 4px; font-weight: bold;"
            );
            console.error("The following keys are missing in your Netlify configuration:");
            missingVars.forEach((key) => {
                console.error(`- ${key}`);
            });
            console.warn(
                "Please add these to Netlify Site Settings > Environment Variables."
            );
        } else {
            console.log(
                "%c[Config Check] All required public environment variables are present.",
                "color: green; font-weight: bold;"
            );
        }
    }, []);

    return null; // This component renders nothing visually
}
