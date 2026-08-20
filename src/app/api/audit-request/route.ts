import { NextRequest, NextResponse } from 'next/server';
import type { AuditFormData } from '@/lib/emails/audit-emails';

export const runtime = 'nodejs';

const GENERIC_SUCCESS_MESSAGE = 'Your audit request has been received! Our team will contact you within 24 hours.';
const DIRECT_EMAIL_FALLBACK = 'Please email sambhav@cloudfinops.solutions directly.';
const HONEYPOT_FIELD = 'website';
const MIN_FORM_AGE_MS = 800;

type AuditRequestBody = Record<string, unknown>;

type AuditRequestMetadata = {
    referrer: string;
    userAgent: string;
};

type EmailDeliveryResult = {
    leadNotificationStatus: 'sent';
    thankYouStatus: 'sent' | 'failed';
};

class AuditPipelineError extends Error {
    constructor(
        public readonly statusCode: number,
        public readonly publicMessage: string,
    ) {
        super(publicMessage);
    }
}

function isRecord(value: unknown): value is AuditRequestBody {
    return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function normalizeStringField(
    body: AuditRequestBody,
    key: string,
    label: string,
    maxLength: number,
    required = false,
): string {
    const rawValue = body[key];
    const value = typeof rawValue === 'string' ? rawValue.trim().replace(/[<>"`&]/g, '') : '';

    if (required && value.length === 0) {
        throw new AuditPipelineError(400, `${label} is required.`);
    }

    if (value.length > maxLength) {
        throw new AuditPipelineError(400, `${label} is too long.`);
    }

    return value;
}

function normalizeWebsiteField(body: AuditRequestBody): string {
    const value = normalizeStringField(body, 'companyWebsite', 'Company website', 250);
    if (value.length === 0) {
        return '';
    }

    const withProtocol = /^https?:\/\//i.test(value) ? value : `https://${value}`;
    try {
        const url = new URL(withProtocol);
        if (url.protocol !== 'http:' && url.protocol !== 'https:') {
            throw new Error('Unsupported URL protocol.');
        }
        return url.toString();
    } catch {
        throw new AuditPipelineError(400, 'Please provide a valid company website.');
    }
}

function normalizeCloudProviders(value: unknown): string[] {
    if (!Array.isArray(value)) {
        throw new AuditPipelineError(400, 'At least one cloud provider is required.');
    }

    const providers: string[] = [];
    for (const entry of value) {
        if (typeof entry !== 'string') continue;

        const provider = entry.trim().replace(/[<>"`&]/g, '');
        if (provider.length === 0 || providers.includes(provider)) continue;
        if (provider.length > 80) {
            throw new AuditPipelineError(400, 'Cloud provider value is too long.');
        }

        providers.push(provider);
    }

    if (providers.length === 0) {
        throw new AuditPipelineError(400, 'At least one cloud provider is required.');
    }

    if (providers.length > 6) {
        throw new AuditPipelineError(400, 'Too many cloud providers selected.');
    }

    return providers;
}

function shouldSilentlyAcceptSpam(body: AuditRequestBody): boolean {
    const honeypot = body[HONEYPOT_FIELD];
    if (typeof honeypot === 'string' && honeypot.trim().length > 0) {
        return true;
    }

    const startedAt = Number(body.formStartedAt);
    return Number.isFinite(startedAt) && Date.now() - startedAt < MIN_FORM_AGE_MS;
}

function buildAuditFormData(body: AuditRequestBody): AuditFormData {
    const firstName = normalizeStringField(body, 'firstName', 'First name', 80, true);
    const lastName = normalizeStringField(body, 'lastName', 'Last name', 80, true);
    const email = normalizeStringField(body, 'email', 'Email', 254, true).toLowerCase();

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
        throw new AuditPipelineError(400, 'Please provide a valid email address.');
    }

    return {
        firstName,
        lastName,
        email,
        phone: normalizeStringField(body, 'phone', 'Phone number', 40),
        jobTitle: normalizeStringField(body, 'jobTitle', 'Job title', 120, true),
        department: normalizeStringField(body, 'department', 'Department', 80),
        companyName: normalizeStringField(body, 'companyName', 'Company name', 160, true),
        companyWebsite: normalizeWebsiteField(body),
        companySize: normalizeStringField(body, 'companySize', 'Company size', 50, true),
        industry: normalizeStringField(body, 'industry', 'Industry', 80),
        cloudProviders: normalizeCloudProviders(body.cloudProviders),
        monthlySpend: normalizeStringField(body, 'monthlySpend', 'Estimated monthly cloud spend', 50, true),
        primaryConcern: normalizeStringField(body, 'primaryConcern', 'Primary concern', 120),
        notes: normalizeStringField(body, 'notes', 'Notes', 2000),
    };
}

async function saveAuditRequest(formData: AuditFormData, metadata: AuditRequestMetadata): Promise<string> {
    try {
        const { createClient } = await import('@/lib/mongodb/client');
        const db = createClient(process.env.MONGODB_URI);

        const result = await db
            .from('audit_requests')
            .insert({
                first_name: formData.firstName,
                last_name: formData.lastName,
                email: formData.email,
                phone: formData.phone,
                job_title: formData.jobTitle,
                department: formData.department,
                company_name: formData.companyName,
                company_website: formData.companyWebsite,
                company_size: formData.companySize,
                industry: formData.industry,
                cloud_providers: formData.cloudProviders,
                monthly_spend: formData.monthlySpend,
                primary_concern: formData.primaryConcern,
                notes: formData.notes,
                status: 'new',
                source: 'public_audit_page',
                submitted_at: new Date().toISOString(),
                lead_notification_status: 'pending',
                thank_you_status: 'pending',
                referrer: metadata.referrer,
                user_agent: metadata.userAgent,
            })
            .select('id')
            .single();

        if (result.error) {
            throw new Error(result.error.message);
        }

        const row = result.data as { id?: unknown } | null;
        if (!row || typeof row.id !== 'string' || row.id.length === 0) {
            throw new Error('Audit request insert did not return an id.');
        }

        return row.id;
    } catch (error: unknown) {
        console.error('[AuditRequest] persistence failed:', error);
        throw new AuditPipelineError(
            503,
            `We could not save your audit request right now. ${DIRECT_EMAIL_FALLBACK}`,
        );
    }
}

async function updateAuditRequestDelivery(
    leadId: string,
    data: Record<string, string>,
): Promise<void> {
    try {
        const { createClient } = await import('@/lib/mongodb/client');
        const db = createClient(process.env.MONGODB_URI);

        const result = await db
            .from('audit_requests')
            .update({
                ...data,
                delivery_checked_at: new Date().toISOString(),
            })
            .eq('id', leadId);

        if (result.error) {
            throw new Error(result.error.message);
        }
    } catch (error: unknown) {
        console.error('[AuditRequest] delivery status update failed:', error);
    }
}

function sendEmailWithTimeout(fn: () => Promise<void>, label: string): Promise<void> {
    const timeoutPromise = new Promise<void>((_, reject) =>
        setTimeout(() => reject(new Error(`${label} timed out`)), 8000),
    );

    return Promise.race([fn(), timeoutPromise]);
}

async function sendAuditEmails(formData: AuditFormData): Promise<EmailDeliveryResult> {
    try {
        const {
            sendLeadNotificationEmail,
            sendThankYouEmail,
        } = await import('@/lib/emails/audit-emails');

        await sendEmailWithTimeout(
            () => sendLeadNotificationEmail(formData),
            'Lead notification',
        );

        let thankYouStatus: EmailDeliveryResult['thankYouStatus'] = 'sent';
        try {
            await sendEmailWithTimeout(
                () => sendThankYouEmail(formData),
                'Thank-you email',
            );
        } catch (error: unknown) {
            thankYouStatus = 'failed';
            console.error('[AuditRequest] thank-you email failed after lead notification:', error);
        }

        return {
            leadNotificationStatus: 'sent',
            thankYouStatus,
        };
    } catch (error: unknown) {
        console.error('[AuditRequest] lead notification failed:', error);
        throw new AuditPipelineError(
            502,
            `We could not notify our audit team right now. ${DIRECT_EMAIL_FALLBACK}`,
        );
    }
}

export async function POST(request: NextRequest) {
    let leadId: string | null = null;

    try {
        const parsedBody: unknown = await request.json();
        if (!isRecord(parsedBody)) {
            throw new AuditPipelineError(400, 'Invalid audit request payload.');
        }

        if (shouldSilentlyAcceptSpam(parsedBody)) {
            return NextResponse.json({
                success: true,
                message: GENERIC_SUCCESS_MESSAGE,
            });
        }

        const formData = buildAuditFormData(parsedBody);
        leadId = await saveAuditRequest(formData, {
            referrer: request.headers.get('referer')?.slice(0, 500) ?? '',
            userAgent: request.headers.get('user-agent')?.slice(0, 500) ?? '',
        });
        const delivery = await sendAuditEmails(formData);

        await updateAuditRequestDelivery(leadId, {
            status: 'new',
            lead_notification_status: delivery.leadNotificationStatus,
            thank_you_status: delivery.thankYouStatus,
        });

        return NextResponse.json({
            success: true,
            message: GENERIC_SUCCESS_MESSAGE,
            confirmationEmailSent: delivery.thankYouStatus === 'sent',
        });

    } catch (error: unknown) {
        if (leadId) {
            await updateAuditRequestDelivery(leadId, {
                status: 'delivery_failed',
                lead_notification_status: 'failed',
                thank_you_status: 'not_sent',
            });
        }

        if (error instanceof AuditPipelineError) {
            return NextResponse.json(
                { error: error.publicMessage },
                { status: error.statusCode },
            );
        }

        console.error('[AuditRequest] unexpected failure:', error);
        return NextResponse.json(
            { error: `Something went wrong while receiving your request. ${DIRECT_EMAIL_FALLBACK}` },
            { status: 500 }
        );
    }
}
