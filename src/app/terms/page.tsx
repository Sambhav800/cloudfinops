
import { FileText, Scale, AlertTriangle, Clock, Shield, Globe, CheckCircle } from "lucide-react";

export default function TermsPage() {
    return (
        <div className="bg-black min-h-screen pt-24 pb-12">
            <div className="mx-auto max-w-4xl px-6 lg:px-8">
                <div className="border-b border-white/10 pb-12">
                    <h1 className="text-4xl font-bold tracking-tight text-white sm:text-6xl mb-4">
                        Master Subscription Agreement
                    </h1>
                    <p className="text-xl text-gray-400">
                        Effective Date: January 1, 2026 | Version: 2.1 (Global Enterprise)
                    </p>
                </div>

                <div className="mt-8 bg-white/5 border border-white/10 rounded-2xl p-6">
                    <p className="text-gray-300">
                        This Master Subscription Agreement (this &quot;Agreement&quot;) is entered into by and between <strong className="text-white">CloudFinOps Inc.</strong> (&quot;Provider&quot;) and the entity or individual placing an order for or accessing the Service (&quot;Customer&quot;). By accessing the Service, Customer agrees to be bound by these Terms.
                    </p>
                </div>

                <div className="mt-12 space-y-16">
                    {/* Definitions */}
                    <section>
                        <h2 className="text-2xl font-semibold text-primary mb-6 flex items-center gap-2">
                            <FileText className="h-6 w-6" />
                            1. Definitions
                        </h2>
                        <div className="space-y-4 text-gray-300">
                            <p><strong className="text-white">&quot;Service&quot;</strong> means the CloudFinOps SaaS platform for cloud cost intelligence and anomaly detection.</p>
                            <p><strong className="text-white">&quot;Read-Only Access&quot;</strong> means the specific, limited permission set granted by Customer to Provider, restricted to viewing metadata and cost logs only.</p>
                            <p><strong className="text-white">&quot;Customer Data&quot;</strong> means electronic data and configuration metadata submitted by or for Customer to the Service.</p>
                        </div>
                    </section>

                    {/* Nature of Service */}
                    <section>
                        <h2 className="text-2xl font-semibold text-white mb-6 flex items-center gap-2">
                            <Shield className="h-6 w-6 text-primary" />
                            2. Nature of Service (Advisory Role)
                        </h2>
                        <div className="bg-white/5 p-6 rounded-2xl border border-white/10">
                            <div className="space-y-4">
                                <p className="text-gray-300">
                                    <strong className="text-white block mb-2">2.1 Recommendations Only.</strong>
                                    The Service uses artificial intelligence to analyze Customer&apos;s cloud infrastructure and provide cost optimization recommendations. Provider acts solely as an <strong className="text-white">advisor</strong>. The decision to implement any recommendation rests entirely with the Customer.
                                </p>
                                <p className="text-gray-300">
                                    <strong className="text-white block mb-2">2.2 No Automated Execution.</strong>
                                    Provider represents that the Service is technically incapable of modifying, provisioning, or deleting Customer resources automatically. All actions must be executed by Customer via their own authorized channels (e.g., CLI, Console).
                                </p>
                            </div>
                        </div>
                    </section>

                    {/* Access and Use */}
                    <section>
                        <h2 className="text-2xl font-semibold text-white mb-6">3. Access and Security</h2>
                        <div className="space-y-6">
                            <div className="bg-white/5 p-6 rounded-2xl border border-white/10">
                                <h3 className="text-lg font-bold text-white mb-3">3.1 Zero-Trust Architecture</h3>
                                <p className="text-gray-300">
                                    Provider shall access Customer&apos;s cloud environment strictly through:
                                </p>
                                <ul className="list-disc list-inside text-gray-300 mt-2 space-y-1 ml-4">
                                    <li>AWS: Cross-Account Role with <code className="bg-white/10 px-1 py-0.5 rounded text-xs">SecurityAudit</code> and <code className="bg-white/10 px-1 py-0.5 rounded text-xs">ViewOnlyAccess</code> policies.</li>
                                    <li>Azure: Service Principal with <code className="bg-white/10 px-1 py-0.5 rounded text-xs">Reader</code> role.</li>
                                    <li>GCP: Service Account with <code className="bg-white/10 px-1 py-0.5 rounded text-xs">Viewer</code> role.</li>
                                </ul>
                            </div>
                        </div>
                    </section>

                    {/* Indemnification */}
                    <section>
                        <h2 className="text-2xl font-semibold text-white mb-6 flex items-center gap-2">
                            <Scale className="h-6 w-6 text-primary" />
                            4. Indemnification
                        </h2>
                        <div className="bg-white/5 p-6 rounded-2xl border border-white/10">
                            <p className="text-gray-300">
                                Provider shall defend Customer against any claim demanding that the Service infringes or misappropriates the intellectual property rights of a third party, provided that such claim does not arise from Customer&apos;s misuse of the Service.
                            </p>
                        </div>
                    </section>

                    {/* Limitation of Liability */}
                    <section>
                        <h2 className="text-2xl font-semibold text-white mb-6 flex items-center gap-2">
                            <AlertTriangle className="h-6 w-6 text-yellow-500" />
                            5. Limitation of Liability
                        </h2>
                        <div className="space-y-4">
                            <div className="bg-yellow-500/10 border border-yellow-500/30 p-6 rounded-2xl">
                                <h3 className="text-lg font-bold text-yellow-400 mb-2">5.1 CAP ON LIABILITY</h3>
                                <p className="text-gray-300 uppercase text-sm leading-relaxed">
                                    IN NO EVENT SHALL EITHER PARTY&apos;S AGGREGATE LIABILITY ARISING OUT OF OR RELATED TO THIS AGREEMENT, WHETHER IN CONTRACT, TORT OR UNDER ANY OTHER THEORY OF LIABILITY, EXCEED THE TOTAL AMOUNT PAID BY CUSTOMER HEREUNDER IN THE 12 MONTHS PRECEDING THE INCIDENT.
                                </p>
                            </div>
                            <div className="bg-red-500/10 border border-red-500/30 p-6 rounded-2xl">
                                <h3 className="text-lg font-bold text-red-400 mb-2">5.2 EXCLUSION OF DAMAGES</h3>
                                <p className="text-gray-300 uppercase text-sm leading-relaxed">
                                    IN NO EVENT SHALL EITHER PARTY HAVE ANY LIABILITY TO THE OTHER PARTY FOR ANY LOST PROFITS, LOST CLOUD SAVINGS, REVENUES, OR INDIRECT, SPECIAL, INCIDENTAL, CONSEQUENTIAL, COVER OR PUNITIVE DAMAGES, WHETHER AN ACTION IS IN CONTRACT or TORT AND REGARDLESS OF THE THEORY OF LIABILITY.
                                </p>
                            </div>
                        </div>
                    </section>

                    {/* General Provisions */}
                    <section>
                        <h2 className="text-2xl font-semibold text-white mb-6 flex items-center gap-2">
                            <Globe className="h-6 w-6 text-primary" />
                            6. General Provisions
                        </h2>
                        <div className="space-y-6">
                            <div className="bg-white/5 p-6 rounded-2xl border border-white/10">
                                <h3 className="text-lg font-bold text-white mb-2">6.1 Governing Law</h3>
                                <p className="text-gray-300">
                                    This Agreement shall be governed by the laws of the State of Delaware, USA, without regard to its conflict of laws principles. (For Customers based in India: Laws of India apply).
                                </p>
                            </div>
                        </div>
                    </section>

                    {/* Contact */}
                    <section className="border-t border-white/10 pt-12">
                        <div className="text-center text-gray-400">
                            <p className="font-bold text-white text-lg mb-2">CloudFinOps Legal</p>
                            <p className="mb-4">Global HQ: Wilmington, Delaware | APAC: Zirakpur, India</p>
                            <p>For legal notices: <a href="mailto:sambhav@cloudfinops.solutions" className="text-primary hover:underline font-mono">sambhav@cloudfinops.solutions</a></p>
                        </div>
                    </section>
                </div>
            </div>
        </div>
    );
}
