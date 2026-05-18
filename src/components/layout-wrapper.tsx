"use client";

import { usePathname } from "next/navigation";
import { Footer } from "@/components/landing/footer";
import { Navbar } from "@/components/landing/navbar";

import { EnvVarChecker } from "@/components/debug/env-var-checker";

export function LayoutWrapper({ children }: { children: React.ReactNode }) {
    const pathname = usePathname();
    const isDashboard = pathname?.startsWith("/dashboard");
    const isHome = pathname === "/";
    const showMarketingShell = !isDashboard && !isHome;

    return (
        <>
            <EnvVarChecker />
            {isDashboard ? ( // Don't show navbar and footer on dashboard pages
                <>{children}</>
            ) : (
                <>
                    {showMarketingShell ? <Navbar /> : null}
                    <main className="flex-grow">
                        {children}
                    </main>
                    {showMarketingShell ? <Footer /> : null}
                </>
            )}
        </>
    );
}
