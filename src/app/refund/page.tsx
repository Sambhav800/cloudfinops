import type { Metadata } from "next";
import { CreditCard, XCircle, Clock, AlertTriangle, Shield, Mail, CheckCircle } from "lucide-react";

export const metadata: Metadata = {
  title: "Refund & Cancellation Policy",
  description:
    "CloudFinOps refund and cancellation policy. 7-day pilot guarantee, transparent billing, and hassle-free cancellation.",
  alternates: { canonical: "/refund" },
};

export default function RefundPage() {
    return (
        <div className="bg-black min-h-screen pt-24 pb-12">
            <div className="mx-auto max-w-4xl px-6 lg:px-8">
                <div className="border-b border-white/10 pb-12">
                    <h1 className="text-4xl font-bold tracking-tight text-white sm:text-6xl mb-4">
                        Refund &amp; Cancellation Policy
                    </h1>
                    <p className="text-xl text-gray-400">
                        Effective Date: January 1, 2026
                    </p>
                    <p className="text-gray-500 mt-2">
                        Entity: CloudFinOps (UDYAM-PB-20-0114306), Zirakpur, Punjab, India.
                    </p>
                </div>

                <div className="mt-8 bg-white/5 border border-white/10 rounded-2xl p-6">
                    <p className="text-gray-300">
                        Thank you for choosing CloudFinOps. We are committed to transparency in our billing practices. This policy constitutes a binding agreement between You (&quot;Customer&quot;) and CloudFinOps (&quot;Provider&quot;) regarding the terms of subscription cancellation, refunds, and billing disputes.
                    </p>
                </div>

                <div className="mt-12 space-y-16">
                    {/* General Billing Terms */}
                    <section>
                        <h2 className="text-2xl font-semibold text-primary mb-6 flex items-center gap-2">
                            <CreditCard className="h-6 w-6" />
                            1. General Billing Terms
                        </h2>
                        <div className="space-y-6">
                            <div className="bg-white/5 p-6 rounded-2xl border border-white/10">
                                <h3 className="text-lg font-bold text-white mb-3">1.1 Authorization</h3>
                                <p className="text-gray-300">
                                    By adding a payment method (Credit Card/Debit Card/UPI), you explicitly authorize CloudFinOps and our payment processors (Stripe/Razorpay) to charge the applicable subscription fees, including any applicable taxes (GST), automatically on a recurring basis until you cancel.
                                </p>
                            </div>
                            <div className="bg-white/5 p-6 rounded-2xl border border-white/10">
                                <h3 className="text-lg font-bold text-white mb-3">1.2 Taxes and Levies</h3>
                                <p className="text-gray-300">
                                    All fees are exclusive of taxes unless otherwise stated. Customers in India are liable for Goods and Services Tax (GST) at the prevailing rate (18%). International customers are responsible for any local withholding taxes or VAT applicable in their jurisdiction.
                                </p>
                            </div>
                        </div>
                    </section>

                    {/* Cancellation Policy */}
                    <section>
                        <h2 className="text-2xl font-semibold text-white mb-6 flex items-center gap-2">
                            <XCircle className="h-6 w-6 text-red-400" />
                            2. Cancellation Policy
                        </h2>
                        <div className="space-y-6">
                            <div className="bg-white/5 p-6 rounded-2xl border border-white/10">
                                <h3 className="text-lg font-bold text-white mb-3">2.1 Procedure to Cancel</h3>
                                <p className="text-gray-300 mb-4">
                                    You may cancel your subscription at any time via the &quot;Billing Settings&quot; section of your dashboard. Alternatively, you may email a formal cancellation request to <a href="mailto:sambhav@cloudfinops.solutions" className="text-primary hover:underline">sambhav@cloudfinops.solutions</a>. Email requests must be received at least 48 hours prior to the next billing date to guarantee processing before the renewal.
                                </p>
                                <div className="border-l-4 border-blue-500 pl-4 bg-blue-500/10 py-3 pr-4 rounded-r">
                                    <p className="text-blue-200 text-sm font-medium">
                                        <strong>Effect of Cancellation:</strong> Cancellation is not retroactive. If you cancel mid-cycle, your subscription will remain active until the end of the current paid term. You will not be charged again, but you will not receive a refund for the unused days in the current term.
                                    </p>
                                </div>
                            </div>
                            <div className="bg-white/5 p-6 rounded-2xl border border-white/10">
                                <h3 className="text-lg font-bold text-white mb-3">2.2 Data Handling Post-Cancellation</h3>
                                <p className="text-gray-300">
                                    Upon cancellation, your account will enter a &quot;Read-Only&quot; state for <strong className="text-white">30 days</strong>, allowing you to export your historical reports. After 30 days, all configuration data, API keys, and scan logs will be permanently deleted from our servers in accordance with our Privacy Policy and Data Retention standards.
                                </p>
                            </div>
                        </div>
                    </section>

                    {/* Refund Policy */}
                    <section>
                        <h2 className="text-2xl font-semibold text-white mb-6 flex items-center gap-2">
                            <AlertTriangle className="h-6 w-6 text-yellow-500" />
                            3. Refund Policy
                        </h2>
                        <div className="space-y-6">
                            <div className="bg-red-500/10 border border-red-500/30 p-6 rounded-2xl">
                                <h3 className="text-lg font-bold text-red-400 mb-2">3.1 General Rule: Non-Refundable</h3>
                                <p className="text-gray-300">
                                    Except as explicitly provided in this policy or where required by applicable law, all payment obligations are non-cancelable and all amounts paid are non-refundable. Our service incurs immediate tangible costs (cloud infrastructure, API calls, data processing) upon activation.
                                </p>
                            </div>
                            <div className="bg-white/5 p-6 rounded-2xl border border-white/10">
                                <h3 className="text-lg font-bold text-white mb-3">3.2 Non-Refundable Items</h3>
                                <p className="text-gray-300 mb-3">The following are strictly non-refundable under any circumstances:</p>
                                <ul className="space-y-2 text-gray-300">
                                    <li className="flex gap-2"><XCircle className="h-5 w-5 text-red-400 flex-shrink-0" /> One-time &quot;Onboarding&quot; or &quot;Setup&quot; fees.</li>
                                    <li className="flex gap-2"><XCircle className="h-5 w-5 text-red-400 flex-shrink-0" /> Consulting or Professional Services hours already performed.</li>
                                    <li className="flex gap-2"><XCircle className="h-5 w-5 text-red-400 flex-shrink-0" /> Partial months of service (unused time).</li>
                                    <li className="flex gap-2"><XCircle className="h-5 w-5 text-red-400 flex-shrink-0" /> Fees paid during a promotional period or with a discount code.</li>
                                </ul>
                            </div>
                            <div className="bg-green-500/10 border border-green-500/30 p-6 rounded-2xl">
                                <h3 className="text-lg font-bold text-green-400 mb-2">3.3 The &quot;7-Day Pilot Guarantee&quot; (New Enterprise Customers Only)</h3>
                                <p className="text-gray-300 mb-3">
                                    To establish trust, we offer a conditional 7-Day Money-Back Guarantee for first-time Enterprise Plan customers only. To qualify:
                                </p>
                                <ul className="space-y-2 text-gray-300">
                                    <li className="flex gap-2"><CheckCircle className="h-5 w-5 text-green-400 flex-shrink-0" /> You must submit a refund request in writing within 7 calendar days of the initial transaction.</li>
                                    <li className="flex gap-2"><CheckCircle className="h-5 w-5 text-green-400 flex-shrink-0" /> You must demonstrate via logs/screenshots that the platform failed to function as described.</li>
                                    <li className="flex gap-2"><CheckCircle className="h-5 w-5 text-green-400 flex-shrink-0" /> This guarantee is void if the failure is caused by your own internal firewall restrictions or refusal to grant necessary IAM permissions.</li>
                                </ul>
                            </div>
                        </div>
                    </section>

                    {/* Credits & Adjustments */}
                    <section>
                        <h2 className="text-2xl font-semibold text-white mb-6">4. Credits &amp; Adjustments</h2>
                        <div className="grid md:grid-cols-2 gap-6">
                            <div className="bg-white/5 p-6 rounded-2xl border border-white/10">
                                <h3 className="text-lg font-bold text-primary mb-3">4.1 SLA Credits</h3>
                                <p className="text-gray-300">
                                    In the event of significant downtime, CloudFinOps is not liable for cash refunds. Instead, we will issue Service Credits to be applied against future invoices. Service Credits are non-transferable and expire 12 months after issuance.
                                </p>
                            </div>
                            <div className="bg-white/5 p-6 rounded-2xl border border-white/10">
                                <h3 className="text-lg font-bold text-blue-400 mb-3">4.2 Downgrades</h3>
                                <p className="text-gray-300">
                                    If you downgrade your plan, the lower rate will apply starting from the next billing cycle. You will not receive a cash refund for the price difference; however, the difference may be applied as a pro-rated credit at our sole discretion.
                                </p>
                            </div>
                        </div>
                    </section>

                    {/* Billing Disputes */}
                    <section>
                        <h2 className="text-2xl font-semibold text-white mb-6 flex items-center gap-2">
                            <Shield className="h-6 w-6 text-primary" />
                            5. Billing Disputes &amp; Fraud Protection
                        </h2>
                        <div className="space-y-6">
                            <div className="bg-white/5 p-6 rounded-2xl border border-white/10">
                                <h3 className="text-lg font-bold text-white mb-3">5.1 Dispute Window</h3>
                                <p className="text-gray-300">
                                    If you believe you have been billed in error, you must notify us in writing within <strong className="text-white">30 days</strong> of the invoice date. Disputes raised after 30 days will not be considered.
                                </p>
                            </div>
                            <div className="bg-red-500/10 border border-red-500/30 p-6 rounded-2xl">
                                <h3 className="text-lg font-bold text-red-400 mb-2">5.2 Chargebacks &amp; Friendly Fraud</h3>
                                <p className="text-gray-300">
                                    If you initiate a chargeback or payment dispute with your credit card provider or bank without first contacting our support team, we reserve the right to immediately suspend access to your account and revoke any licenses. We will submit this policy and your usage logs as evidence to the bank. Repeated chargebacks will result in a permanent ban.
                                </p>
                            </div>
                        </div>
                    </section>

                    {/* Termination for Cause */}
                    <section>
                        <h2 className="text-2xl font-semibold text-white mb-6">6. Termination for Cause</h2>
                        <div className="bg-white/5 p-6 rounded-2xl border border-white/10">
                            <p className="text-gray-300 mb-3">
                                CloudFinOps reserves the right to terminate your account immediately and without refund if you are found to be in material breach of our Master Subscription Agreement (MSA) or Terms of Service. Examples of breach include:
                            </p>
                            <ul className="list-disc list-inside text-gray-300 space-y-1 ml-4">
                                <li>Using the service for illegal activities or unauthorized vulnerability scanning.</li>
                                <li>Reverse engineering the platform.</li>
                                <li>Sharing account credentials with unauthorized third parties.</li>
                            </ul>
                        </div>
                    </section>

                    {/* Enterprise Contracts */}
                    <section>
                        <h2 className="text-2xl font-semibold text-white mb-6">7. Enterprise Contracts</h2>
                        <p className="text-gray-300">
                            If you have signed a custom Master Services Agreement (MSA) or Order Form with CloudFinOps, the cancellation and refund terms specified in that physical contract shall supersede the terms of this online policy.
                        </p>
                    </section>

                    {/* Refund Processing Timeline */}
                    <section>
                        <h2 className="text-2xl font-semibold text-white mb-6 flex items-center gap-2">
                            <Clock className="h-6 w-6 text-primary" />
                            8. Refund Processing Timeline
                        </h2>
                        <div className="bg-white/5 p-6 rounded-2xl border border-white/10">
                            <p className="text-gray-300 mb-4">If a refund is explicitly approved by our Finance Team:</p>
                            <div className="grid md:grid-cols-2 gap-4">
                                <div className="bg-black/50 p-4 rounded-lg">
                                    <strong className="text-white block mb-1">Processing Time</strong>
                                    <span className="text-gray-400 text-sm">Refunds take 5-10 business days to appear on your statement, depending on your bank.</span>
                                </div>
                                <div className="bg-black/50 p-4 rounded-lg">
                                    <strong className="text-white block mb-1">Currency</strong>
                                    <span className="text-gray-400 text-sm">Refunds are processed in the currency of the original transaction. We are not responsible for fluctuations in exchange rates.</span>
                                </div>
                            </div>
                        </div>
                    </section>

                    {/* Contact */}
                    <section className="border-t border-white/10 pt-12">
                        <h2 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
                            <Mail className="h-5 w-5 text-primary" />
                            9. Contact Us
                        </h2>
                        <div className="bg-white/5 p-6 rounded-2xl border border-white/10">
                            <p className="text-gray-300 mb-2">For any billing inquiries, cancellations, or disputes, please contact our dedicated billing support team:</p>
                            <div className="text-gray-400 mt-4">
                                <p className="font-semibold text-white">CloudFinOps Billing Dept.</p>
                                <p>Zirakpur, Punjab, India</p>
                                <p>Email: <a href="mailto:sambhav@cloudfinops.solutions" className="text-primary hover:underline">sambhav@cloudfinops.solutions</a></p>
                            </div>
                        </div>
                    </section>
                </div>
            </div>
        </div>
    );
}
