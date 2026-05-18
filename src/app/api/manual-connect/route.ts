import { NextRequest, NextResponse } from 'next/server';
import { auth } from '@clerk/nextjs/server';

import { createBackendIntegration, triggerBackendScan } from '@/lib/api';

export async function GET() {
    return NextResponse.json(
        { error: 'Use POST. Credentials in URL query params are blocked for security.' },
        { status: 405 }
    );
}

export async function POST(request: NextRequest) {
    if (process.env.NODE_ENV === 'production' && process.env.ENABLE_MANUAL_CONNECT_ROUTE !== 'true') {
        return NextResponse.json(
            { error: 'manual-connect route is disabled in production' },
            { status: 403 }
        );
    }

    const body = await request.json().catch(() => ({}));
    const accessKeyId = typeof body.access_key_id === 'string' ? body.access_key_id.trim() : '';
    const secretAccessKey = typeof body.secret_access_key === 'string' ? body.secret_access_key.trim() : '';
    const name = typeof body.name === 'string' && body.name.trim() ? body.name.trim() : 'AWS Integration';

    if (!accessKeyId || !secretAccessKey) {
        return NextResponse.json({ error: 'Missing credentials' }, { status: 400 });
    }

    const { userId } = await auth();
    if (!userId) {
        return NextResponse.json({ error: 'Unauthorized: Please log in first' }, { status: 401 });
    }

    try {
        const result = await createBackendIntegration({
            provider: 'aws',
            name,
            regions: ['us-east-1'],
            auth_type: 'keys',
            access_key_id: accessKeyId,
            secret_access_key: secretAccessKey,
        });

        if (result.error || !result.integration) {
            return NextResponse.json(
                { error: result.error || 'Failed to connect AWS integration' },
                { status: result.status >= 400 ? result.status : 500 }
            );
        }

        await triggerBackendScan(result.integration.id, { userId });

        return NextResponse.json({
            success: true,
            message: 'Connected and Scanned Successfully! You can close this tab and return to the dashboard.'
        });
    } catch (error: unknown) {
        const message =
            error instanceof Error
                ? error.message
                : (error && typeof error === 'object' && 'message' in error)
                    ? String((error as Record<string, unknown>).message)
                    : 'Unknown error';
        return NextResponse.json({ error: message }, { status: 500 });
    }
}
