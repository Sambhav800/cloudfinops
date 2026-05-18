import { Resend } from 'resend';
import fs from 'fs';
import path from 'path';

// Lazy-loaded at runtime (not build time) to avoid Netlify build errors
let _resend: Resend | null = null;
let _logoBase64: string | null = null;

function getResend() {
    if (!_resend) _resend = new Resend(process.env.RESEND_API_KEY);
    return _resend;
}

function getLogoBase64() {
    if (!_logoBase64) {
        const logoPath = path.join(process.cwd(), 'public', 'logo-main.png');
        _logoBase64 = fs.readFileSync(logoPath).toString('base64');
    }
    return _logoBase64;
}

const BUSINESS_EMAIL = 'sambhav@cloudfinops.solutions';
const SITE_URL = 'https://cloudfinops.solutions';

export interface AuditFormData {
    firstName: string;
    lastName: string;
    email: string;
    phone?: string;
    jobTitle?: string;
    department?: string;
    companyName?: string;
    companyWebsite?: string;
    companySize?: string;
    industry?: string;
    cloudProviders: string[];
    monthlySpend?: string;
    primaryConcern?: string;
    notes?: string;
}

// ══════════════════════════════════════════════════════════════════
//  THANK-YOU EMAIL — Sent to the person who submitted the form
// ══════════════════════════════════════════════════════════════════
export async function sendThankYouEmail(data: AuditFormData) {
    const year = new Date().getFullYear();

    const { error } = await getResend().emails.send({
        from: process.env.RESEND_FROM_EMAIL || 'CloudFinOps <noreply@cloudfinops.solutions>',
        to: data.email,
        subject: 'Welcome to CloudFinOps — Your Cloud Audit Request is Confirmed ✅',
        attachments: [
            {
                content: getLogoBase64(),
                filename: 'logo.png',
                contentId: 'cfs-logo',
            },
        ],
        html: `
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CloudFinOps — Audit Request Confirmed</title>
</head>
<body style="margin:0;padding:0;background-color:#0a0a0a;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;-webkit-font-smoothing:antialiased;">
    
    <!-- Outer wrapper -->
    <table width="100%" cellpadding="0" cellspacing="0" role="presentation" style="background-color:#0a0a0a;padding:32px 16px;">
        <tr>
            <td align="center">

                <!-- Main card -->
                <table width="600" cellpadding="0" cellspacing="0" role="presentation" style="background-color:#111111;border-radius:16px;border:1px solid rgba(255,255,255,0.08);overflow:hidden;max-width:600px;width:100%;">
                    
                    <!-- ═══ HEADER with Logo ═══ -->
                    <tr>
                        <td style="background:linear-gradient(135deg,#0d1117 0%,#161b22 50%,#0d1117 100%);padding:32px 40px;text-align:center;border-bottom:1px solid rgba(255,255,255,0.06);">
                            <a href="${SITE_URL}" style="text-decoration:none;">
                                <img src="cid:cfs-logo" alt="CloudFinOps" width="64" height="auto" style="display:block;margin:0 auto 12px;max-width:64px;" />
                                <span style="font-size:22px;font-weight:800;color:#ffffff;letter-spacing:-0.5px;">CloudFinOps</span>
                            </a>
                            <p style="margin:4px 0 0;font-size:12px;color:#555555;letter-spacing:1.5px;text-transform:uppercase;">AI-Powered Cloud Cost Optimization</p>
                        </td>
                    </tr>

                    <!-- ═══ HERO SECTION ═══ -->
                    <tr>
                        <td style="padding:40px 40px 24px;">
                            <h1 style="margin:0 0 4px;font-size:26px;font-weight:700;color:#ffffff;line-height:1.3;">
                                Welcome, ${data.firstName}! 🎉
                            </h1>
                            <p style="margin:0 0 24px;font-size:15px;color:#8b949e;line-height:1.7;">
                                Thank you for choosing CloudFinOps. Your cloud audit request has been received and our team is already on it.
                            </p>

                            <!-- Accent divider -->
                            <table width="100%" cellpadding="0" cellspacing="0" role="presentation">
                                <tr>
                                    <td style="height:2px;background:linear-gradient(90deg,#00d2ff 0%,#7b2ff7 50%,#00d2ff 100%);border-radius:2px;"></td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- ═══ WHAT HAPPENS NEXT ═══ -->
                    <tr>
                        <td style="padding:0 40px 32px;">
                            <table width="100%" cellpadding="0" cellspacing="0" role="presentation" style="background-color:#161b22;border-radius:12px;border:1px solid rgba(255,255,255,0.06);">
                                <tr>
                                    <td style="padding:24px 28px;">
                                        <h2 style="margin:0 0 20px;font-size:15px;font-weight:700;color:#00d2ff;text-transform:uppercase;letter-spacing:1px;">What Happens Next</h2>
                                        
                                        <!-- Step 1 -->
                                        <table width="100%" cellpadding="0" cellspacing="0" role="presentation" style="margin-bottom:16px;">
                                            <tr>
                                                <td width="36" valign="top">
                                                    <div style="width:28px;height:28px;background:linear-gradient(135deg,#00d2ff,#0099cc);border-radius:50%;text-align:center;line-height:28px;font-size:13px;font-weight:700;color:#000000;">1</div>
                                                </td>
                                                <td style="padding-left:12px;">
                                                    <p style="margin:0;font-size:14px;color:#e6edf3;font-weight:600;">Infrastructure Review</p>
                                                    <p style="margin:2px 0 0;font-size:13px;color:#7d8590;">We analyze your cloud setup across ${data.cloudProviders?.length ? data.cloudProviders.join(', ') : 'your providers'}</p>
                                                </td>
                                            </tr>
                                        </table>

                                        <!-- Step 2 -->
                                        <table width="100%" cellpadding="0" cellspacing="0" role="presentation" style="margin-bottom:16px;">
                                            <tr>
                                                <td width="36" valign="top">
                                                    <div style="width:28px;height:28px;background:linear-gradient(135deg,#00d2ff,#0099cc);border-radius:50%;text-align:center;line-height:28px;font-size:13px;font-weight:700;color:#000000;">2</div>
                                                </td>
                                                <td style="padding-left:12px;">
                                                    <p style="margin:0;font-size:14px;color:#e6edf3;font-weight:600;">Custom Audit Report</p>
                                                    <p style="margin:2px 0 0;font-size:13px;color:#7d8590;">Detailed cost breakdown with optimization recommendations</p>
                                                </td>
                                            </tr>
                                        </table>

                                        <!-- Step 3 -->
                                        <table width="100%" cellpadding="0" cellspacing="0" role="presentation">
                                            <tr>
                                                <td width="36" valign="top">
                                                    <div style="width:28px;height:28px;background:linear-gradient(135deg,#00d2ff,#0099cc);border-radius:50%;text-align:center;line-height:28px;font-size:13px;font-weight:700;color:#000000;">3</div>
                                                </td>
                                                <td style="padding-left:12px;">
                                                    <p style="margin:0;font-size:14px;color:#e6edf3;font-weight:600;">Expert Consultation</p>
                                                    <p style="margin:2px 0 0;font-size:13px;color:#7d8590;">30-minute call to review findings and savings plan</p>
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- ═══ YOUR REQUEST SUMMARY ═══ -->
                    <tr>
                        <td style="padding:0 40px 32px;">
                            <table width="100%" cellpadding="0" cellspacing="0" role="presentation" style="background-color:#161b22;border-radius:12px;border:1px solid rgba(255,255,255,0.06);">
                                <tr>
                                    <td style="padding:24px 28px;">
                                        <h2 style="margin:0 0 16px;font-size:15px;font-weight:700;color:#ffffff;text-transform:uppercase;letter-spacing:1px;">Your Request Summary</h2>
                                        <table width="100%" cellpadding="0" cellspacing="0" role="presentation">
                                            <tr>
                                                <td style="padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.04);">
                                                    <span style="font-size:12px;color:#7d8590;text-transform:uppercase;letter-spacing:0.5px;">Company</span><br/>
                                                    <span style="font-size:14px;color:#e6edf3;font-weight:500;">${data.companyName || '—'}</span>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td style="padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.04);">
                                                    <span style="font-size:12px;color:#7d8590;text-transform:uppercase;letter-spacing:0.5px;">Cloud Providers</span><br/>
                                                    <span style="font-size:14px;color:#e6edf3;font-weight:500;">${data.cloudProviders?.length ? data.cloudProviders.join(' · ') : '—'}</span>
                                                </td>
                                            </tr>
                                            <tr>
                                                <td style="padding:8px 0;">
                                                    <span style="font-size:12px;color:#7d8590;text-transform:uppercase;letter-spacing:0.5px;">Monthly Cloud Spend</span><br/>
                                                    <span style="font-size:14px;color:#00d2ff;font-weight:700;">${data.monthlySpend || '—'}</span>
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- ═══ TIMELINE BADGE ═══ -->
                    <tr>
                        <td style="padding:0 40px 32px;text-align:center;">
                            <table width="100%" cellpadding="0" cellspacing="0" role="presentation" style="background:linear-gradient(135deg,rgba(0,210,255,0.08),rgba(123,47,247,0.08));border-radius:12px;border:1px solid rgba(0,210,255,0.15);">
                                <tr>
                                    <td style="padding:20px 28px;text-align:center;">
                                        <p style="margin:0;font-size:13px;color:#7d8590;">Expected response time</p>
                                        <p style="margin:4px 0 0;font-size:20px;font-weight:800;color:#00d2ff;">Within 24 Hours</p>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- ═══ CONTACT ═══ -->
                    <tr>
                        <td style="padding:0 40px 32px;">
                            <p style="margin:0;font-size:13px;color:#7d8590;line-height:1.7;text-align:center;">
                                Questions? Reach us at
                                <a href="mailto:sambhav@cloudfinops.solutions" style="color:#00d2ff;text-decoration:none;font-weight:600;">sambhav@cloudfinops.solutions</a>
                            </p>
                        </td>
                    </tr>

                    <!-- ═══ FOOTER ═══ -->
                    <tr>
                        <td style="padding:20px 40px;border-top:1px solid rgba(255,255,255,0.06);text-align:center;">
                            <a href="${SITE_URL}" style="text-decoration:none;">
                                <img src="cid:cfs-logo" alt="CloudFinOps" width="24" height="auto" style="display:inline-block;vertical-align:middle;margin-right:6px;max-width:24px;" />
                                <span style="font-size:13px;font-weight:600;color:#555555;vertical-align:middle;">CloudFinOps</span>
                            </a>
                            <p style="margin:8px 0 0;font-size:11px;color:#3d3d3d;">
                                © ${year} CloudFinOps Solutions
                            </p>
                            <p style="margin:4px 0 0;font-size:11px;color:#3d3d3d;">
                                Zirakpur, Punjab, India
                            </p>
                        </td>
                    </tr>

                </table>
            </td>
        </tr>
    </table>
</body>
</html>
        `.trim(),
    });

    if (error) {
        console.error('[Email] Thank-you email failed:', error);
        throw error;
    }
}

// ══════════════════════════════════════════════════════════════════
//  LEAD NOTIFICATION — Sent to sambhav@cloudfinops.solutions
// ══════════════════════════════════════════════════════════════════
export async function sendLeadNotificationEmail(data: AuditFormData) {
    const timestamp = new Date().toLocaleString('en-IN', {
        timeZone: 'Asia/Kolkata',
        dateStyle: 'medium',
        timeStyle: 'short',
    });
    const year = new Date().getFullYear();

    const { error } = await getResend().emails.send({
        from: process.env.RESEND_FROM_EMAIL || 'CloudFinOps <noreply@cloudfinops.solutions>',
        to: BUSINESS_EMAIL,
        subject: `🔔 New Audit Lead: ${data.firstName} ${data.lastName} — ${data.companyName || 'Unknown'} (${data.monthlySpend || 'Spend N/A'})`,
        attachments: [
            {
                content: getLogoBase64(),
                filename: 'logo.png',
                contentId: 'cfs-logo',
            },
        ],
        html: `
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>New Audit Lead</title>
</head>
<body style="margin:0;padding:0;background-color:#f6f8fa;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;-webkit-font-smoothing:antialiased;">
    
    <table width="100%" cellpadding="0" cellspacing="0" role="presentation" style="background-color:#f6f8fa;padding:32px 16px;">
        <tr>
            <td align="center">

                <table width="600" cellpadding="0" cellspacing="0" role="presentation" style="background-color:#ffffff;border-radius:16px;overflow:hidden;max-width:600px;width:100%;box-shadow:0 1px 3px rgba(0,0,0,0.08),0 8px 24px rgba(0,0,0,0.04);">
                    
                    <!-- ═══ HEADER ═══ -->
                    <tr>
                        <td style="background:linear-gradient(135deg,#0d1117 0%,#161b22 100%);padding:24px 32px;">
                            <table width="100%" cellpadding="0" cellspacing="0" role="presentation">
                                <tr>
                                    <td>
                                        <img src="cid:cfs-logo" alt="CloudFinOps" width="32" height="auto" style="display:inline-block;vertical-align:middle;margin-right:8px;max-width:32px;" />
                                        <span style="font-size:16px;font-weight:700;color:#ffffff;vertical-align:middle;">New Audit Lead</span>
                                    </td>
                                    <td align="right">
                                        <span style="font-size:12px;color:#7d8590;">${timestamp}</span>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- ═══ LEAD SUMMARY BANNER ═══ -->
                    <tr>
                        <td style="padding:24px 32px 16px;">
                            <table width="100%" cellpadding="0" cellspacing="0" role="presentation" style="background:linear-gradient(135deg,#f0f9ff,#e0f2fe);border-radius:12px;border:1px solid #bae6fd;">
                                <tr>
                                    <td style="padding:20px 24px;">
                                        <h2 style="margin:0 0 4px;font-size:20px;font-weight:700;color:#0c4a6e;">${data.firstName} ${data.lastName}</h2>
                                        <p style="margin:0;font-size:14px;color:#0369a1;">
                                            ${data.jobTitle || 'Role N/A'} · ${data.companyName || 'Company N/A'}
                                        </p>
                                        <p style="margin:8px 0 0;font-size:12px;color:#0c4a6e;">
                                            <strong style="background-color:#0369a1;color:#ffffff;padding:2px 8px;border-radius:4px;font-size:11px;">${data.monthlySpend || 'Spend N/A'}</strong>
                                            &nbsp;&nbsp;
                                            <span>${data.cloudProviders?.length ? data.cloudProviders.join(' · ') : 'Providers N/A'}</span>
                                        </p>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- ═══ CONTACT DETAILS ═══ -->
                    <tr>
                        <td style="padding:8px 32px 16px;">
                            <h3 style="margin:0 0 12px;font-size:11px;font-weight:700;color:#57606a;text-transform:uppercase;letter-spacing:1.5px;">Contact Information</h3>
                            <table width="100%" cellpadding="0" cellspacing="0" role="presentation" style="border:1px solid #d0d7de;border-radius:8px;overflow:hidden;">
                                <tr style="background-color:#f6f8fa;">
                                    <td style="padding:10px 16px;font-size:13px;color:#57606a;width:35%;border-bottom:1px solid #d0d7de;">Email</td>
                                    <td style="padding:10px 16px;font-size:13px;border-bottom:1px solid #d0d7de;">
                                        <a href="mailto:${data.email}" style="color:#0969da;text-decoration:none;font-weight:600;">${data.email}</a>
                                    </td>
                                </tr>
                                <tr>
                                    <td style="padding:10px 16px;font-size:13px;color:#57606a;border-bottom:1px solid #d0d7de;">Phone</td>
                                    <td style="padding:10px 16px;font-size:13px;color:#1f2328;border-bottom:1px solid #d0d7de;">${data.phone || '—'}</td>
                                </tr>
                                <tr style="background-color:#f6f8fa;">
                                    <td style="padding:10px 16px;font-size:13px;color:#57606a;border-bottom:1px solid #d0d7de;">Job Title</td>
                                    <td style="padding:10px 16px;font-size:13px;color:#1f2328;border-bottom:1px solid #d0d7de;">${data.jobTitle || '—'}</td>
                                </tr>
                                <tr>
                                    <td style="padding:10px 16px;font-size:13px;color:#57606a;">Department</td>
                                    <td style="padding:10px 16px;font-size:13px;color:#1f2328;">${data.department || '—'}</td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- ═══ COMPANY DETAILS ═══ -->
                    <tr>
                        <td style="padding:8px 32px 16px;">
                            <h3 style="margin:0 0 12px;font-size:11px;font-weight:700;color:#57606a;text-transform:uppercase;letter-spacing:1.5px;">Company Details</h3>
                            <table width="100%" cellpadding="0" cellspacing="0" role="presentation" style="border:1px solid #d0d7de;border-radius:8px;overflow:hidden;">
                                <tr style="background-color:#f6f8fa;">
                                    <td style="padding:10px 16px;font-size:13px;color:#57606a;width:35%;border-bottom:1px solid #d0d7de;">Company</td>
                                    <td style="padding:10px 16px;font-size:13px;color:#1f2328;font-weight:600;border-bottom:1px solid #d0d7de;">${data.companyName || '—'}</td>
                                </tr>
                                <tr>
                                    <td style="padding:10px 16px;font-size:13px;color:#57606a;border-bottom:1px solid #d0d7de;">Website</td>
                                    <td style="padding:10px 16px;font-size:13px;border-bottom:1px solid #d0d7de;">
                                        ${data.companyWebsite ? `<a href="${data.companyWebsite}" style="color:#0969da;text-decoration:none;">${data.companyWebsite}</a>` : '—'}
                                    </td>
                                </tr>
                                <tr style="background-color:#f6f8fa;">
                                    <td style="padding:10px 16px;font-size:13px;color:#57606a;border-bottom:1px solid #d0d7de;">Size</td>
                                    <td style="padding:10px 16px;font-size:13px;color:#1f2328;border-bottom:1px solid #d0d7de;">${data.companySize || '—'} employees</td>
                                </tr>
                                <tr>
                                    <td style="padding:10px 16px;font-size:13px;color:#57606a;">Industry</td>
                                    <td style="padding:10px 16px;font-size:13px;color:#1f2328;">${data.industry || '—'}</td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- ═══ CLOUD INFRASTRUCTURE ═══ -->
                    <tr>
                        <td style="padding:8px 32px 16px;">
                            <h3 style="margin:0 0 12px;font-size:11px;font-weight:700;color:#57606a;text-transform:uppercase;letter-spacing:1.5px;">Cloud Infrastructure</h3>
                            <table width="100%" cellpadding="0" cellspacing="0" role="presentation" style="border:1px solid #d0d7de;border-radius:8px;overflow:hidden;">
                                <tr style="background-color:#f6f8fa;">
                                    <td style="padding:10px 16px;font-size:13px;color:#57606a;width:35%;border-bottom:1px solid #d0d7de;">Providers</td>
                                    <td style="padding:10px 16px;font-size:13px;color:#1f2328;font-weight:600;border-bottom:1px solid #d0d7de;">${data.cloudProviders?.length ? data.cloudProviders.join(', ') : '—'}</td>
                                </tr>
                                <tr>
                                    <td style="padding:10px 16px;font-size:13px;color:#57606a;border-bottom:1px solid #d0d7de;">Monthly Spend</td>
                                    <td style="padding:10px 16px;font-size:13px;color:#1f2328;font-weight:700;border-bottom:1px solid #d0d7de;">${data.monthlySpend || '—'}</td>
                                </tr>
                                <tr style="background-color:#f6f8fa;">
                                    <td style="padding:10px 16px;font-size:13px;color:#57606a;border-bottom:1px solid #d0d7de;">Primary Concern</td>
                                    <td style="padding:10px 16px;font-size:13px;color:#1f2328;border-bottom:1px solid #d0d7de;">${data.primaryConcern || '—'}</td>
                                </tr>
                                <tr>
                                    <td style="padding:10px 16px;font-size:13px;color:#57606a;">Additional Notes</td>
                                    <td style="padding:10px 16px;font-size:13px;color:#1f2328;">${data.notes || '—'}</td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- ═══ QUICK ACTION ═══ -->
                    <tr>
                        <td style="padding:16px 32px 24px;text-align:center;">
                            <a href="mailto:${data.email}?subject=Re: Your CloudFinOps Audit Request&body=Hi ${data.firstName},%0D%0A%0D%0AThank you for your interest in CloudFinOps. I'm Sambhav, and I'll be personally handling your cloud audit.%0D%0A%0D%0A" 
                               style="display:inline-block;padding:12px 32px;background-color:#0969da;color:#ffffff;text-decoration:none;border-radius:8px;font-size:14px;font-weight:600;">
                                📧 Reply to ${data.firstName}
                            </a>
                        </td>
                    </tr>

                    <!-- ═══ FOOTER ═══ -->
                    <tr>
                        <td style="padding:16px 32px;border-top:1px solid #d0d7de;text-align:center;">
                            <p style="margin:0;font-size:11px;color:#8b949e;">
                                CloudFinOps Lead Notification · © ${year}
                            </p>
                        </td>
                    </tr>

                </table>
            </td>
        </tr>
    </table>
</body>
</html>
        `.trim(),
    });

    if (error) {
        console.error('[Email] Lead notification email failed:', error);
        throw error;
    }
}


