"use client";

import dynamic from "next/dynamic";
import type { CloudResource } from "@/lib/dashboard/data";
import { ErrorBanner } from "@/components/dashboard/error-banner";

const ResourcesView = dynamic(() => import("@/components/dashboard/resources-view").then((mod) => mod.ResourcesView), { ssr: false });

export function ResourcesViewClient({ initialResources, loadError }: { initialResources: CloudResource[]; loadError: string | null }) {
    return (
        <div className="space-y-4">
            {loadError && <ErrorBanner message={loadError} />}
            <ResourcesView initialResources={initialResources} />
        </div>
    );
}
