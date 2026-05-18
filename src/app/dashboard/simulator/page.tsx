import { ShiftLeftSimulator } from '@/components/dashboard/simulator/shift-left-simulator';
import { ShieldAlert } from 'lucide-react';

export const metadata = {
    title: 'Shift-Left Cost Simulator | CloudFinOps',
    description: 'Estimate cloud cost changes from Terraform plans before deployment.',
};

type SimulatorPageSearchParams = {
    id?: string;
    action?: string;
    mode?: string;
};

export default async function SimulatorPage({
    searchParams,
}: {
    searchParams?: Promise<SimulatorPageSearchParams>;
}) {
    const params = (await searchParams) ?? {};
    const commitmentMode =
        params.mode === 'commitment' || (Boolean(params.id) && params.action === 'renew');
    const mode = commitmentMode ? 'commitment' : 'terraform_plan';

    return (
        <main className="p-6 md:p-10 w-full bg-slate-950 min-h-screen text-slate-200">
            <div className="mb-8">
                <div className="flex items-center gap-3 mb-2">
                    <div className="p-2 bg-indigo-500/20 rounded-xl text-indigo-400">
                        <ShieldAlert className="w-6 h-6" />
                    </div>
                    <h1 className="text-white text-3xl font-bold">Shift-Left Cost Simulator</h1>
                </div>
                <p className="text-slate-400 text-lg">
                    Analyze Terraform plans to understand budget impact before you commit code.
                </p>
            </div>

            <ShiftLeftSimulator
                commitmentId={params.id}
                action={params.action}
                mode={mode}
            />
            
            <div className="mt-12 p-6 bg-slate-900/30 border border-white/5 rounded-2xl">
                <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
                    <span className="w-2 h-2 bg-indigo-500 rounded-full animate-pulse"></span>
                    How it works
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
                    <div className="space-y-2">
                        <div className="text-indigo-400 font-bold text-xl font-mono">01.</div>
                        <h4 className="text-slate-200 font-medium">Export Plan</h4>
                        <p className="text-slate-500 text-sm">Run `terraform plan -out=tfplan` then `terraform show -json tfplan {'>'} plan.json` in your CLI.</p>
                    </div>
                    <div className="space-y-2">
                        <div className="text-indigo-400 font-bold text-xl font-mono">02.</div>
                        <h4 className="text-slate-200 font-medium">Upload JSON</h4>
                        <p className="text-slate-500 text-sm">Upload the generated `plan.json` file or paste its content into the simulator.</p>
                    </div>
                    <div className="space-y-2">
                        <div className="text-indigo-400 font-bold text-xl font-mono">03.</div>
                        <h4 className="text-slate-200 font-medium">Review Impact</h4>
                        <p className="text-slate-500 text-sm">
                            CloudFinOps uses exact catalog pricing where it can and provider-aware
                            estimates where it cannot, so unsupported resource types still stay visible.
                        </p>
                    </div>
                </div>
            </div>
        </main>
    );
}
