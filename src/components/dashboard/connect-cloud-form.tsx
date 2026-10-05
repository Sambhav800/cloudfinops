'use client';

import { useActionState, useEffect, useState } from 'react';
import { connectCloudAccount } from '@/app/actions/cloud';
import { Loader2, AlertCircle, CheckCircle, Key, Shield, Cloud } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useScan } from '@/components/dashboard/scan-provider';

type Provider = 'aws' | 'azure' | 'gcp';
type AwsAuthType = 'role' | 'keys';
type CloudActionState = { success: boolean; error?: string; message?: string; provider?: Provider };

export function ConnectCloudForm({ onCancel }: { onCancel: () => void }) {
    const [state, formAction, isPending] = useActionState<CloudActionState | null, FormData>(connectCloudAccount, null);
    const [provider, setProvider] = useState<Provider>('aws');
    const [awsAuthType, setAwsAuthType] = useState<AwsAuthType>('keys');
    const router = useRouter();
    const { showScanProgress } = useScan();

    useEffect(() => {
        if (state?.provider) {
            setProvider(state.provider);
        }
    }, [state?.provider]);

    // On success: close modal and show scan progress popup
    useEffect(() => {
        if (state?.success) {
            const timer = setTimeout(() => {
                onCancel();
                router.refresh();
                showScanProgress();
            }, 500);
            return () => clearTimeout(timer);
        }
    }, [state, onCancel, router, showScanProgress]);

    return (
        <form action={formAction} className="space-y-4 text-left">
            {state?.error && (
                <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg flex items-center gap-2 text-red-400 text-sm">
                    <AlertCircle className="h-4 w-4 shrink-0" />
                    <p>{state.error}</p>
                </div>
            )}

            {state?.success && (
                <div className="p-3 bg-green-500/10 border border-green-500/20 rounded-lg flex items-center gap-2 text-green-400 text-sm">
                    <CheckCircle className="h-4 w-4 shrink-0" />
                    <p>{state?.message || 'Connected successfully'}</p>
                </div>
            )}

            {/* Provider Selection */}
            <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Provider</label>
                <select
                    name="provider"
                    value={provider}
                    onChange={(e) => setProvider(e.target.value as Provider)}
                    className="w-full bg-black/50 border border-white/10 rounded-lg px-4 py-2 text-white focus:border-primary focus:outline-none"
                >
                    <option value="aws">Amazon Web Services (AWS)</option>
                    <option value="azure">Microsoft Azure</option>
                    <option value="gcp">Google Cloud Platform (GCP)</option>
                </select>
            </div>

            {/* Account Name - Common for all providers */}
            <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">Account Name</label>
                <input
                    name="name"
                    type="text"
                    required
                    placeholder={
                        provider === 'aws' ? 'e.g., Production AWS' :
                            provider === 'azure' ? 'e.g., Production Azure' :
                                'e.g., Production GCP'
                    }
                    className="w-full bg-black/50 border border-white/10 rounded-lg px-4 py-2 text-white placeholder-gray-500 focus:border-primary focus:outline-none"
                />
            </div>

            {/* AWS-specific fields */}
            {provider === 'aws' && (
                <>
                    <div>
                        <label className="block text-sm font-medium text-gray-300 mb-2">Authentication Method</label>
                        <div className="flex gap-2 p-1 bg-black/50 border border-white/10 rounded-lg">
                            <button
                                type="button"
                                onClick={() => setAwsAuthType('keys')}
                                className={`flex-1 flex items-center justify-center gap-2 py-2 rounded-md text-sm font-medium transition-all ${awsAuthType === 'keys'
                                    ? 'bg-primary text-black shadow-lg'
                                    : 'text-gray-400 hover:text-white'
                                    }`}
                            >
                                <Key className="h-4 w-4" />
                                Access Keys
                            </button>
                            <button
                                type="button"
                                onClick={() => setAwsAuthType('role')}
                                className={`flex-1 flex items-center justify-center gap-2 py-2 rounded-md text-sm font-medium transition-all ${awsAuthType === 'role'
                                    ? 'bg-primary text-black shadow-lg'
                                    : 'text-gray-400 hover:text-white'
                                    }`}
                            >
                                <Shield className="h-4 w-4" />
                                IAM Role
                            </button>
                        </div>
                        <input type="hidden" name="auth_type" value={awsAuthType} />
                    </div>

                    {awsAuthType === 'role' ? (
                        <>
                            <div>
                                <label className="block text-sm font-medium text-gray-300 mb-2">Role ARN</label>
                                <input
                                    name="role_arn"
                                    type="text"
                                    required
                                    placeholder="arn:aws:iam::123456789012:role/CloudFinOpsRole"
                                    className="w-full bg-black/50 border border-white/10 rounded-lg px-4 py-2 text-white placeholder-gray-500 focus:border-primary focus:outline-none"
                                />
                                <p className="text-xs text-gray-500 mt-1">Best for cross-account access.</p>
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-gray-300 mb-2">External ID (Optional)</label>
                                <input
                                    name="external_id"
                                    type="text"
                                    placeholder="Security token if configured"
                                    className="w-full bg-black/50 border border-white/10 rounded-lg px-4 py-2 text-white placeholder-gray-500 focus:border-primary focus:outline-none"
                                />
                            </div>
                        </>
                    ) : (
                        <>
                            <div>
                                <label className="block text-sm font-medium text-gray-300 mb-2">Access Key ID</label>
                                <input
                                    name="access_key_id"
                                    type="text"
                                    required
                                    placeholder="AKIA..."
                                    className="w-full bg-black/50 border border-white/10 rounded-lg px-4 py-2 text-white placeholder-gray-500 focus:border-primary focus:outline-none font-mono"
                                />
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-gray-300 mb-2">Secret Access Key</label>
                                <input
                                    name="secret_access_key"
                                    type="password"
                                    required
                                    placeholder="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
                                    className="w-full bg-black/50 border border-white/10 rounded-lg px-4 py-2 text-white placeholder-gray-500 focus:border-primary focus:outline-none font-mono"
                                />
                                <p className="text-xs text-gray-500 mt-1">Stored securely using AES-256 encryption.</p>
                            </div>
                        </>
                    )}
                </>
            )}

            {/* Azure-specific fields */}
            {provider === 'azure' && (
                <>
                    <div className="p-3 bg-blue-500/10 border border-blue-500/20 rounded-lg flex items-center gap-2 text-blue-400 text-sm">
                        <Cloud className="h-4 w-4 shrink-0" />
                        <p>Use a Service Principal with Reader + Cost Management Reader roles.</p>
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-gray-300 mb-2">Tenant ID</label>
                        <input
                            name="tenant_id"
                            type="text"
                            required
                            placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                            className="w-full bg-black/50 border border-white/10 rounded-lg px-4 py-2 text-white placeholder-gray-500 focus:border-primary focus:outline-none font-mono"
                        />
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-gray-300 mb-2">Client ID (Application ID)</label>
                        <input
                            name="client_id"
                            type="text"
                            required
                            placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                            className="w-full bg-black/50 border border-white/10 rounded-lg px-4 py-2 text-white placeholder-gray-500 focus:border-primary focus:outline-none font-mono"
                        />
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-gray-300 mb-2">Client Secret</label>
                        <input
                            name="client_secret"
                            type="password"
                            required
                            placeholder="Your client secret"
                            className="w-full bg-black/50 border border-white/10 rounded-lg px-4 py-2 text-white placeholder-gray-500 focus:border-primary focus:outline-none font-mono"
                        />
                        <p className="text-xs text-gray-500 mt-1">Stored securely using AES-256 encryption.</p>
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-gray-300 mb-2">Subscription ID</label>
                        <input
                            name="subscription_id"
                            type="text"
                            required
                            placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                            className="w-full bg-black/50 border border-white/10 rounded-lg px-4 py-2 text-white placeholder-gray-500 focus:border-primary focus:outline-none font-mono"
                        />
                    </div>
                </>
            )}

            {/* GCP-specific fields */}
            {provider === 'gcp' && (
                <>
                    <div className="p-3 bg-yellow-500/10 border border-yellow-500/20 rounded-lg flex items-center gap-2 text-yellow-400 text-sm">
                        <Cloud className="h-4 w-4 shrink-0" />
                        <p>Use a Service Account with Viewer + Billing Account Viewer roles.</p>
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-gray-300 mb-2">Project ID</label>
                        <input
                            name="project_id"
                            type="text"
                            required
                            placeholder="my-gcp-project-123456"
                            className="w-full bg-black/50 border border-white/10 rounded-lg px-4 py-2 text-white placeholder-gray-500 focus:border-primary focus:outline-none font-mono"
                        />
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-gray-300 mb-2">Service Account Email</label>
                        <input
                            name="service_account_email"
                            type="email"
                            required
                            placeholder="my-service-account@my-project.iam.gserviceaccount.com"
                            className="w-full bg-black/50 border border-white/10 rounded-lg px-4 py-2 text-white placeholder-gray-500 focus:border-primary focus:outline-none font-mono text-sm"
                        />
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-gray-300 mb-2">Private Key</label>
                        <textarea
                            name="private_key"
                            required
                            rows={4}
                            placeholder="Paste the private_key value from your GCP service account JSON"
                            className="w-full bg-black/50 border border-white/10 rounded-lg px-4 py-2 text-white placeholder-gray-500 focus:border-primary focus:outline-none font-mono text-xs"
                        />
                        <p className="text-xs text-gray-500 mt-1">From your service account JSON key file. Stored securely using AES-256 encryption.</p>
                    </div>

                    <div>
                        <label className="block text-sm font-medium text-gray-300 mb-2">Billing Export Table (Optional)</label>
                        <input
                            name="billing_export_table"
                            type="text"
                            placeholder="project_id.dataset_id.table_id"
                            className="w-full bg-black/50 border border-white/10 rounded-lg px-4 py-2 text-white placeholder-gray-500 focus:border-primary focus:outline-none font-mono text-sm"
                        />
                        <p className="text-xs text-gray-500 mt-1">
                            Optional, but recommended for exact cost from GCP Billing Export. If left empty, CloudFinOps uses scanner-estimated costs.
                        </p>
                    </div>
                </>
            )}

            <div className="flex gap-3 mt-6">
                <button
                    type="button"
                    onClick={onCancel}
                    disabled={isPending}
                    className="flex-1 px-4 py-2 border border-white/10 text-gray-400 rounded-lg hover:text-white hover:border-white/20 transition-colors disabled:opacity-50"
                >
                    Cancel
                </button>
                <button
                    type="submit"
                    disabled={isPending}
                    className="flex-1 px-4 py-2 bg-primary text-black rounded-lg font-medium hover:bg-primary/90 transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
                >
                    {isPending ? (
                        <>
                            <Loader2 className="h-4 w-4 animate-spin" />
                            Connecting...
                        </>
                    ) : (
                        'Connect'
                    )}
                </button>
            </div>
        </form>
    );
}
