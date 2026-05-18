"use client";

import dynamic from "next/dynamic";
import type { AlertItem } from "@/lib/dashboard/data";
import { ErrorBanner } from "@/components/dashboard/error-banner";

const AlertsView = dynamic(() => import("@/components/dashboard/alerts-view").then((mod) => mod.AlertsView), { ssr: false });

export function AlertsViewClient({ initialAlerts, loadError }: { initialAlerts: AlertItem[]; loadError: string | null }) {
    return (
        <div className="space-y-4">
            {loadError && <ErrorBanner message={loadError} />}
            <AlertsView initialAlerts={initialAlerts} />
        </div>
    );
}
