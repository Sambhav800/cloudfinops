'use server'

import { auth } from '@clerk/nextjs/server';
import { revalidatePath } from 'next/cache';

import { createBackendIntegration, triggerBackendScan } from '@/lib/api';

export async function connectAwsAccount(_prevState: unknown, formData: FormData) {
    const { userId } = await auth();
    if (!userId) {
        return { error: 'Unauthorized', success: false };
    }

    const name = String(formData.get('name') || '').trim();
    const authType = (String(formData.get('auth_type') || 'keys').trim().toLowerCase() as 'role' | 'keys') || 'keys';
    const regions = String(formData.get('regions') || 'us-east-1')
        .split(',')
        .map((region) => region.trim())
        .filter(Boolean);
    const roleArn = String(formData.get('role_arn') || '').trim();
    const externalId = String(formData.get('external_id') || '').trim();
    const accessKeyId = String(formData.get('access_key_id') || '').trim();
    const secretAccessKey = String(formData.get('secret_access_key') || '').trim();

    if (!name) return { error: 'Account Name is required', success: false };
    if (authType === 'role' && !roleArn) return { error: 'Role ARN is required', success: false };
    if (authType === 'keys' && (!accessKeyId || !secretAccessKey)) {
        return { error: 'Access Key ID and Secret Access Key are required', success: false };
    }

    try {
        const result = await createBackendIntegration({
            provider: 'aws',
            name,
            regions,
            auth_type: authType,
            role_arn: roleArn || undefined,
            external_id: externalId || undefined,
            access_key_id: accessKeyId || undefined,
            secret_access_key: secretAccessKey || undefined,
        });

        if (result.error || !result.integration) {
            return { error: result.error || 'Failed to save integration', success: false };
        }

        void triggerBackendScan(result.integration.id, { userId });

        revalidatePath('/dashboard/settings');
        revalidatePath('/dashboard/resources');
        return { success: true, message: 'AWS Account Connected & Scanned Successfully!' };
    } catch (error) {
        const message = error instanceof Error ? error.message : 'Failed to save integration';
        return { error: message, success: false };
    }
}
