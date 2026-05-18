"use client";

import dynamic from "next/dynamic";
import { ErrorBanner } from "@/components/dashboard/error-banner";

const ArchitecturePageV2 = dynamic(
    () => import("@/components/dashboard/architecture/architecture-page-v2").then((mod) => mod.ArchitecturePageV2),
    { ssr: false },
);

export function ArchitecturePageV2Client({
    integrations,
    loadError,
}: {
    integrations: Array<{
        id: string;
        provider: string;
        name: string | null;
        last_scan?: string | null;
    }>;
    loadError: string | null;
}) {
    return (
        <div className="space-y-4">
            {loadError && <ErrorBanner message={loadError} />}
            <ArchitecturePageV2
                integrations={integrations}
            />
        </div>
    );
}
