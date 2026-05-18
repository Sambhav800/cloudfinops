import { redirect } from "next/navigation";

export const dynamic = "force-dynamic";

type BillAnalysisPageProps = {
    params: Promise<{
        analysisId: string;
    }>;
};

export default async function BillAnalysisPage({ params }: BillAnalysisPageProps) {
    const { analysisId } = await params;
    redirect(`/dashboard/arbitrage?id=${encodeURIComponent(analysisId)}`);
}
