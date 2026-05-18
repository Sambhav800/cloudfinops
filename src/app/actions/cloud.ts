'use server'

import { auth } from '@clerk/nextjs/server';
import { revalidatePath } from 'next/cache';

import { createBackendIntegration, triggerBackendScan } from '@/lib/api';

type CloudProvider = 'aws' | 'azure' | 'gcp';

interface CloudActionState {
    error?: string;
    success: boolean;
    message?: string;
    provider?: CloudProvider;
}

function isCloudProvider(value: string): value is CloudProvider {
    return value === 'aws' || value === 'azure' || value === 'gcp';
}

function failCloudConnect(error: string, provider?: CloudProvider): CloudActionState {
    return { error, success: false, provider };
}

function parseRegions(rawValue: FormDataEntryValue | null, fallback: string): string[] {
    const raw = typeof rawValue === "string" ? rawValue : fallback;
    return raw
        .split(",")
        .map((value) => value.trim())
        .filter(Boolean);
}

async function startInitialScan(integrationId: string, userId: string) {
    try {
        await triggerBackendScan(integrationId, { userId });
    } catch {
        // Initial scan failures are surfaced by the backend scan status and notifications.
    }
}

export async function connectCloudAccount(_prevState: CloudActionState | null, formData: FormData) {
    const { userId } = await auth();
    if (!userId) {
        return failCloudConnect('Unauthorized: Please ensure you are signed in.');
    }

    const name = String(formData.get('name') || '').trim();
    const submittedProvider = String(formData.get('provider') || '').trim().toLowerCase();
    const provider = isCloudProvider(submittedProvider) ? submittedProvider : undefined;

    if (!name) return failCloudConnect('Account Name is required', provider);
    if (!provider) {
        return failCloudConnect('Provider is required');
    }

    try {
        if (provider === 'aws') {
            const authType = (String(formData.get('auth_type') || 'keys').trim().toLowerCase() as 'role' | 'keys') || 'keys';
            const roleArn = String(formData.get('role_arn') || '').trim();
            const externalId = String(formData.get('external_id') || '').trim();
            const accessKeyId = String(formData.get('access_key_id') || '').trim();
            const secretAccessKey = String(formData.get('secret_access_key') || '').trim();

            if (authType === 'role' && !roleArn) {
                return failCloudConnect('Role ARN is required', provider);
            }
            if (authType === 'keys' && (!accessKeyId || !secretAccessKey)) {
                return failCloudConnect('Access Key ID and Secret Access Key are required', provider);
            }

            const result = await createBackendIntegration({
                provider: 'aws',
                name,
                regions: parseRegions(formData.get('regions'), 'us-east-1'),
                auth_type: authType,
                role_arn: roleArn || undefined,
                external_id: externalId || undefined,
                access_key_id: accessKeyId || undefined,
                secret_access_key: secretAccessKey || undefined,
            });

            if (result.error || !result.integration) {
                return failCloudConnect(result.error || 'Failed to save integration', provider);
            }

            void startInitialScan(result.integration.id, userId);
            revalidatePath('/dashboard/settings');
            revalidatePath('/dashboard/resources');
            return { success: true, message: 'AWS Account Connected & Scanned Successfully!' };
        }

        if (provider === 'azure') {
            const tenantId = String(formData.get('tenant_id') || '').trim();
            const clientId = String(formData.get('client_id') || '').trim();
            const clientSecret = String(formData.get('client_secret') || '').trim();
            const subscriptionId = String(formData.get('subscription_id') || '').trim();

            if (!tenantId || !clientId || !clientSecret || !subscriptionId) {
                return failCloudConnect('All Azure credentials are required (Tenant ID, Client ID, Client Secret, Subscription ID)', provider);
            }

            const result = await createBackendIntegration({
                provider: 'azure',
                name,
                regions: ['eastus'],
                tenant_id: tenantId,
                client_id: clientId,
                client_secret: clientSecret,
                subscription_id: subscriptionId,
            });

            if (result.error || !result.integration) {
                return failCloudConnect(result.error || 'Failed to save integration', provider);
            }

            void startInitialScan(result.integration.id, userId);
            revalidatePath('/dashboard/settings');
            revalidatePath('/dashboard/resources');
            return { success: true, message: 'Azure Account Connected & Scanned Successfully!' };
        }

        const projectId = String(formData.get('project_id') || '').trim();
        const serviceAccountEmail = String(formData.get('service_account_email') || '').trim();
        const privateKey = String(formData.get('private_key') || '').trim();
        const billingExportTable = String(formData.get('billing_export_table') || '').trim();

        if (!projectId || !serviceAccountEmail || !privateKey) {
            return failCloudConnect('All GCP credentials are required (Project ID, Service Account Email, Private Key)', provider);
        }
        if (billingExportTable && billingExportTable.split('.').filter(Boolean).length !== 3) {
            return failCloudConnect('Billing Export Table must be in `project.dataset.table` format (or leave it blank).', provider);
        }

        const result = await createBackendIntegration({
            provider: 'gcp',
            name,
            regions: ['us-central1'],
            project_id: projectId,
            service_account_email: serviceAccountEmail,
            private_key: privateKey,
            billing_export_table: billingExportTable || undefined,
        });

        if (result.error || !result.integration) {
            return failCloudConnect(result.error || 'Failed to save integration', provider);
        }

        void startInitialScan(result.integration.id, userId);
        revalidatePath('/dashboard/settings');
        revalidatePath('/dashboard/resources');
        return { success: true, message: 'GCP Account Connected & Scanned Successfully!' };
    } catch (error) {
        const message = error instanceof Error ? error.message : 'Failed to connect cloud account';
        return failCloudConnect(message, provider);
    }
}
