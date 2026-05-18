import {
    fetchWithBackendAuthFallback,
    getBackendAuthContext,
    hasBackendAuthCandidate,
} from "@/app/api/_shared/backend-auth";
import { BACKEND_URL } from "@/lib/config";
import { TotalBillExperience, type TotalBillResponse } from "@/components/dashboard/total-bill-experience";

export const dynamic = "force-dynamic";

async function getTotalBillData(): Promise<TotalBillResponse | null> {
    const authContext = await getBackendAuthContext();
    const totalBillUrl = `${BACKEND_URL}/api/totalbill`;
    if (!authContext?.userId || !hasBackendAuthCandidate(totalBillUrl, authContext)) {
        return null;
    }

    try {
        const response = await fetchWithBackendAuthFallback(fetch, totalBillUrl, {
            cache: "no-store",
        }, authContext);

        if (!response.ok) {
            const errorText = await response.text().catch(() => "");
            if (process.env.NODE_ENV === "development") {
                console.error(`[TotalBill] backend request failed (${response.status}): ${errorText}`);
            }
            return null;
        }

        return await response.json() as TotalBillResponse;
    } catch (error) {
        if (process.env.NODE_ENV === "development") {
            console.error("[TotalBill] failed to load total bill data:", error);
        }
        return null;
    }
}

export default async function TotalBillPage() {
    const data = await getTotalBillData();

    if (!data) {
        return (
            <main className="min-h-screen bg-slate-950 px-4 py-8 text-slate-200 md:px-8 lg:px-12">
                <div className="mx-auto max-w-7xl">
                    <h1 className="text-2xl font-semibold tracking-tight text-white">Total Bill</h1>
                    <p className="mt-2 max-w-prose text-sm leading-relaxed text-slate-400">
                        CloudFinOps could not load your unified multi-cloud bill. Refresh the page or verify the backend connection.
                    </p>
                    <p className="mt-4 border-l-2 border-indigo-500/50 bg-indigo-500/5 px-4 py-3 text-sm text-slate-300">
                        The dashboard will stay empty until an authenticated backend response is available.
                    </p>
                </div>
            </main>
        );
    }

    return <TotalBillExperience data={data} />;
}
