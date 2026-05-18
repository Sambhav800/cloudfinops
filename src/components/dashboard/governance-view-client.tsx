"use client";

import dynamic from "next/dynamic";
import type { GovernanceData } from "@/lib/dashboard/data";
import { ErrorBanner } from "@/components/dashboard/error-banner";

const GovernanceView = dynamic(() => import("@/components/dashboard/governance-view").then((mod) => mod.GovernanceView), { ssr: false });

export function GovernanceViewClient({ initialAnalysis, loadError }: { initialAnalysis: GovernanceData; loadError: string | null }) {
    return (
        <div className="space-y-4">
            {loadError && <ErrorBanner message={loadError} />}
            <GovernanceView initialAnalysis={initialAnalysis} />
        </div>
    );
}
