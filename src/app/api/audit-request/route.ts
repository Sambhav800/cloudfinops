import { NextRequest, NextResponse } from 'next/server';
import type { AuditFormData } from '@/lib/emails/audit-emails';

export const runtime = 'nodejs';

async function saveAuditRequest(formData: AuditFormData): Promise<void> {
    try {
        const { createClient } = await import('@/lib/mongodb/client');
        const db = createClient(process.env.MONGODB_URI);

        await db
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
            });
    } catch {
        // Email delivery is the user-visible success path. DB persistence is best-effort here.
    }
}

async function sendAuditEmails(formData: AuditFormData): Promise<void> {
    const {
        sendLeadNotificationEmail,
        sendThankYouEmail,
    } = await import('@/lib/emails/audit-emails');

    const sendEmailWithTimeout = async (fn: () => Promise<void>, label: string) => {
        const timeoutPromise = new Promise((_, reject) =>
            setTimeout(() => reject(new Error(`${label} timed out`)), 8000),
        );
        return Promise.race([fn(), timeoutPromise]);
    };

    await Promise.allSettled([
        sendEmailWithTimeout(() => sendThankYouEmail(formData), 'Thank-you email'),
        sendEmailWithTimeout(() => sendLeadNotificationEmail(formData), 'Lead notification'),
    ]);
}

export async function POST(request: NextRequest) {
    try {
        const body = await request.json();

        // Validate required fields
        const { firstName, lastName, email } = body;
        if (!firstName || !lastName || !email) {
            return NextResponse.json(
                { error: 'First name, last name, and email are required.' },
                { status: 400 }
            );
        }

        // Basic email validation
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test(email)) {
            return NextResponse.json(
                { error: 'Please provide a valid email address.' },
                { status: 400 }
            );
        }

        const formData: AuditFormData = {
            firstName: body.firstName,
            lastName: body.lastName,
            email: body.email,
            phone: body.phone || '',
            jobTitle: body.jobTitle || '',
            department: body.department || '',
            companyName: body.companyName || '',
            companyWebsite: body.companyWebsite || '',
            companySize: body.companySize || '',
            industry: body.industry || '',
            cloudProviders: body.cloudProviders || [],
            monthlySpend: body.monthlySpend || '',
            primaryConcern: body.primaryConcern || '',
            notes: body.notes || '',
        };

        await saveAuditRequest(formData);
        await sendAuditEmails(formData);

        return NextResponse.json({
            success: true,
            message: 'Your audit request has been received! Check your email for confirmation.',
        });

    } catch (error: unknown) {
        const message = error instanceof Error ? error.message : 'Something went wrong';
        return NextResponse.json(
            { error: message },
            { status: 500 }
        );
    }
}
