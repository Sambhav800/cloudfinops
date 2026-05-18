
import { Shield, Database, Globe, Lock, Cookie, User, Clock, Mail, CheckCircle, Server } from "lucide-react";

export default function PrivacyPage() {
    return (
        <div className="bg-black min-h-screen pt-24 pb-12">
            <div className="mx-auto max-w-4xl px-6 lg:px-8">
                <div className="border-b border-white/10 pb-12">
                    <h1 className="text-4xl font-bold tracking-tight text-white sm:text-6xl mb-4">
                        Privacy Policy
                    </h1>
                    <p className="text-xl text-gray-400">
                        Effective Date: January 1, 2026
                    </p>
                    <div className="flex flex-wrap gap-3 mt-6">
                        <span className="bg-green-500/20 text-green-400 px-3 py-1 rounded-full text-sm font-medium">SOC 2 Aligned</span>
                        <span className="bg-blue-500/20 text-blue-400 px-3 py-1 rounded-full text-sm font-medium">GDPR Compliant</span>
                        <span className="bg-purple-500/20 text-purple-400 px-3 py-1 rounded-full text-sm font-medium">CCPA Ready</span>
                    </div>
                </div>

                <div className="mt-8 bg-white/5 border border-white/10 rounded-2xl p-6">
                    <p className="text-gray-300">
                        CloudFinOps (&quot;we&quot;, &quot;us&quot;) processes data strictly as a <strong className="text-white">Data Processor</strong> on behalf of our customers. We adhere to the principle of <strong className="text-white">Data Minimization</strong>: we only access the metadata necessary to identify cost savings.
                    </p>
                </div>

                <div className="mt-12 space-y-16">
                    {/* What We Collect - STRICT */}
                    <section>
                        <h2 className="text-2xl font-semibold text-primary mb-6 flex items-center gap-2">
                            <Database className="h-6 w-6" />
                            1. Data We Collect (Strictly Metadata)
                        </h2>
                        <div className="space-y-6">
                            <div className="bg-white/5 p-6 rounded-2xl border border-white/10">
                                <h3 className="text-lg font-bold text-white mb-3">1.1 Infrastructure Metadata Only</h3>
                                <p className="text-gray-300 mb-4">
                                    Our access is technically limited to configuration data. We collect:
                                </p>
                                <ul className="grid md:grid-cols-2 gap-4 text-gray-300">
                                    <li className="flex gap-2"><CheckCircle className="h-5 w-5 text-green-400 flex-shrink-0" /> Resource IDs (e.g., i-0abc123)</li>
                                    <li className="flex gap-2"><CheckCircle className="h-5 w-5 text-green-400 flex-shrink-0" /> Utilization Metrics (CPU %)</li>
                                    <li className="flex gap-2"><CheckCircle className="h-5 w-5 text-green-400 flex-shrink-0" /> Configuration (Instance Type)</li>
                                    <li className="flex gap-2"><CheckCircle className="h-5 w-5 text-green-400 flex-shrink-0" /> Cost & Billing Tags</li>
                                </ul>
                            </div>

                            <div className="bg-red-500/10 border border-red-500/20 p-6 rounded-2xl">
                                <h3 className="text-lg font-bold text-red-400 mb-3 flex items-center gap-2">
                                    <Shield className="h-5 w-5" />
                                    1.2 What We DO NOT Access
                                </h3>
                                <p className="text-gray-300 mb-2">To prevent any liability or data leakage, our system is architected to be blind to:</p>
                                <ul className="list-disc list-inside text-gray-300 space-y-1 ml-4">
                                    <li><strong className="text-white">Source Code:</strong> We cannot read your repositories.</li>
                                    <li><strong className="text-white">Database Content:</strong> We cannot query tables or view records.</li>
                                    <li><strong className="text-white">S3/Blob Objects:</strong> We cannot view file contents.</li>
                                    <li><strong className="text-white">User PII:</strong> We do not access your end-user data.</li>
                                </ul>
                            </div>
                        </div>
                    </section>

                    {/* Subprocessors */}
                    <section>
                        <h2 className="text-2xl font-semibold text-white mb-6 flex items-center gap-2">
                            <Globe className="h-6 w-6 text-primary" />
                            2. Subprocessors & Data Residency
                        </h2>
                        <div className="grid md:grid-cols-2 gap-4">
                            <div className="bg-white/5 p-4 rounded-xl border border-white/10">
                                <strong className="text-white block mb-1">AWS (Amazon Web Services)</strong>
                                <span className="text-gray-400 text-sm">Primary Infrastructure Hosting.</span>
                            </div>
                            <div className="bg-white/5 p-4 rounded-xl border border-white/10">
                                <strong className="text-white block mb-1">MongoDB</strong>
                                <span className="text-gray-400 text-sm">Encrypted Metadata Storage (PostgreSQL).</span>
                            </div>
                            <div className="bg-white/5 p-4 rounded-xl border border-white/10">
                                <strong className="text-white block mb-1">Google Gemini</strong>
                                <span className="text-gray-400 text-sm">AI Analysis (Zero-Retention Policy enabled).</span>
                            </div>
                            <div className="bg-white/5 p-4 rounded-xl border border-white/10">
                                <strong className="text-white block mb-1">Clerk</strong>
                                <span className="text-gray-400 text-sm">Secure Authentication & Identity.</span>
                            </div>
                        </div>
                    </section>

                    {/* Data Security */}
                    <section>
                        <h2 className="text-2xl font-semibold text-white mb-6 flex items-center gap-2">
                            <Lock className="h-6 w-6 text-primary" />
                            3. Security & Encryption
                        </h2>
                        <div className="grid md:grid-cols-3 gap-4">
                            <div className="bg-white/5 p-4 rounded-xl border border-white/10 text-center">
                                <Server className="h-8 w-8 text-primary mx-auto mb-2" />
                                <strong className="text-white block mb-1">At Rest</strong>
                                <span className="text-gray-400 text-sm">ASE-256 Encryption for all db volumes.</span>
                            </div>
                            <div className="bg-white/5 p-4 rounded-xl border border-white/10 text-center">
                                <Globe className="h-8 w-8 text-blue-400 mx-auto mb-2" />
                                <strong className="text-white block mb-1">In Transit</strong>
                                <span className="text-gray-400 text-sm">TLS 1.3 Strict Enforcement.</span>
                            </div>
                            <div className="bg-white/5 p-4 rounded-xl border border-white/10 text-center">
                                <Shield className="h-8 w-8 text-green-400 mx-auto mb-2" />
                                <strong className="text-white block mb-1">Keys</strong>
                                <span className="text-gray-400 text-sm">Rotated annually via AWS KMS.</span>
                            </div>
                        </div>
                    </section>

                    {/* Contact - Updated */}
                    <section className="border-t border-white/10 pt-12">
                        <h2 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
                            <Mail className="h-5 w-5 text-primary" />
                            4. Data Protection Officer (DPO)
                        </h2>
                        <div className="bg-white/5 p-6 rounded-2xl border border-white/10">
                            <p className="text-gray-300 mb-4">
                                For data deletion requests (&quot;Right to be Forgotten&quot;) or compliance inquiries:
                            </p>
                            <div className="text-gray-400">
                                <p><strong className="text-white">Email:</strong> <a href="mailto:sambhav@cloudfinops.solutions" className="text-primary hover:underline">sambhav@cloudfinops.solutions</a></p>
                                <p><strong className="text-white">Response Time:</strong> Within 48 hours.</p>
                            </div>
                        </div>
                    </section>
                </div>
            </div>
        </div>
    );
}
