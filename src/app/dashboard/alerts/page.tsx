
import { getAllAlerts } from "@/lib/dashboard/data";
import { AlertsViewClient } from "@/components/dashboard/alerts-view-client";

export const dynamic = "force-dynamic";

export default async function AlertsPage() {
    let alerts = [] as Awaited<ReturnType<typeof getAllAlerts>>;
    let loadError: string | null = null;

    try {
        alerts = await getAllAlerts();
    } catch (error) {
        if (process.env.NODE_ENV === "development") {
            console.error("Alerts page load error:", error);
        }
        loadError = error instanceof Error ? error.message : "Failed to load alerts";
    }

    const unreadCount = alerts.filter(a => !a.is_read).length;

    return (
        <div className="min-h-screen">
            <div className="px-6 py-4">
                <h1 className="text-2xl font-bold text-white">Alerts</h1>
                <p className="text-sm text-gray-400">{`${unreadCount} unread notifications`}</p>
            </div>
            <AlertsViewClient initialAlerts={alerts} loadError={loadError} />
        </div>
    );
}
