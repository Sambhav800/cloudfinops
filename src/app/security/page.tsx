
import { Shield, Lock, FileText, CheckCircle, Server, Globe, AlertTriangle, Eye, Database, Cloud } from "lucide-react";
import Link from "next/link";

export default function SecurityPage() {
    return (
        <div className="bg-black min-h-screen pt-24 pb-12">
            <div className="mx-auto max-w-6xl px-6 lg:px-8">
                {/* Header */}
                <div className="border-b border-white/10 pb-12 mb-16">
                    <div className="flex items-center gap-3 mb-6">
                        <div className="p-2 rounded-lg bg-primary/10 border border-primary/20">
                            <Shield className="h-6 w-6 text-primary" />
                        </div>
                        <span className="text-sm font-mono text-primary tracking-wider uppercase">Security Center</span>
                    </div>
                    <h1 className="text-4xl font-bold tracking-tight text-white sm:text-6xl mb-6">
                        Enterprise-Grade Security <br />
                        <span className="text-gray-500">Built into Every Scan.</span>
                    </h1>
                    <p className="text-xl text-gray-400 max-w-3xl leading-relaxed">
                        CloudFinOps operates on a Zero-Trust, Read-Only architecture. We provide deep financial visibility without ever compromising your infrastructure's integrity.
                    </p>
                    <div className="mt-8 flex items-center gap-4 text-sm text-gray-500 font-mono">
                        <span>Version 5.1 (Enterprise)</span>
                        <span className="w-1 h-1 rounded-full bg-gray-700" />
                        <span>ISO 27001 Aligned</span>
                        <span className="w-1 h-1 rounded-full bg-gray-700" />
                        <span>SOC 2 Type II Controls</span>
                    </div>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-12 gap-12">
                    {/* Sidebar Navigation (Sticky) */}
                    <div className="hidden lg:block lg:col-span-3">
                        <div className="sticky top-32 space-y-1">
                            {["Architecture", "Shared Responsibility", "IAM & Access", "Data Protection", "App Security", "Compliance"].map((item) => (
                                <a
                                    key={item}
                                    href={`#${item.toLowerCase().replace(/ /g, "-").replace(/&/g, "")}`}
                                    className="block px-4 py-2 text-sm text-gray-400 hover:text-white hover:bg-white/5 rounded-lg transition-colors"
                                >
                                    {item}
                                </a>
                            ))}
                            <div className="pt-6 mt-6 border-t border-white/10">
                                <a
                                    href="mailto:sambhav@cloudfinops.solutions"
                                    className="flex items-center gap-2 px-4 py-2 text-sm text-primary hover:text-primary/80 transition-colors"
                                >
                                    <AlertTriangle className="h-4 w-4" />
                                    Report Vulnerability
                                </a>
                            </div>
                        </div>
                    </div>

                    {/* Main Content */}
                    <div className="lg:col-span-9 space-y-20">

                        {/* 1. Architecture Overview */}
                        <section id="architecture" className="scroll-mt-32">
                            <h2 className="text-2xl font-semibold text-white mb-6 flex items-center gap-3">
                                <Server className="h-6 w-6 text-primary" />
                                1. Architecture Overview
                            </h2>
                            <div className="prose prose-invert max-w-none text-gray-300">
                                <p className="leading-relaxed">
                                    Our platform is engineered to be strictly non-intrusive. We use a unidirectional, read-only data flow ensuring client infrastructure remains isolated, immutable, and secure. Data flows from Client Cloud (AWS/Azure/GCP) to our Encrypted Storage via TLS 1.3 using a Secure Connector with Read-Only Roles.
                                </p>
                                <div className="mt-8 p-6 bg-white/5 rounded-xl border border-white/10">
                                    <h3 className="text-white font-medium mb-4">Zero-Trust Principles</h3>
                                    <div className="grid md:grid-cols-2 gap-6">
                                        <div className="flex gap-3">
                                            <div className="mt-1"><CheckCircle className="h-4 w-4 text-green-500" /></div>
                                            <div>
                                                <strong className="text-white block text-sm">Assume Breach</strong>
                                                <span className="text-sm text-gray-400">We verify every request as if it originates from an open network.</span>
                                            </div>
                                        </div>
                                        <div className="flex gap-3">
                                            <div className="mt-1"><CheckCircle className="h-4 w-4 text-green-500" /></div>
                                            <div>
                                                <strong className="text-white block text-sm">Least Privilege Access</strong>
                                                <span className="text-sm text-gray-400">Services operate with the minimum permissions necessary.</span>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </section>

                        {/* 2. Shared Responsibility */}
                        <section id="shared-responsibility" className="scroll-mt-32">
                            <h2 className="text-2xl font-semibold text-white mb-6">2. Shared Responsibility Model</h2>
                            <div className="grid md:grid-cols-2 gap-6">
                                <div className="bg-gradient-to-br from-white/5 to-transparent p-6 rounded-2xl border border-white/10">
                                    <div className="flex items-center gap-2 mb-4">
                                        <Shield className="h-5 w-5 text-primary" />
                                        <h3 className="text-lg font-bold text-white">CloudFinOps Responsibilities</h3>
                                    </div>
                                    <ul className="space-y-3 text-sm text-gray-300">
                                        <li className="flex gap-2"><CheckCircle className="h-4 w-4 text-primary shrink-0" /> Security of SaaS application & code</li>
                                        <li className="flex gap-2"><CheckCircle className="h-4 w-4 text-primary shrink-0" /> Encryption of data (At-rest & Transit)</li>
                                        <li className="flex gap-2"><CheckCircle className="h-4 w-4 text-primary shrink-0" /> Patch management of infrastructure</li>
                                        <li className="flex gap-2"><CheckCircle className="h-4 w-4 text-primary shrink-0" /> Supply chain security of dependencies</li>
                                    </ul>
                                </div>
                                <div className="bg-gradient-to-br from-white/5 to-transparent p-6 rounded-2xl border border-white/10">
                                    <div className="flex items-center gap-2 mb-4">
                                        <Globe className="h-5 w-5 text-blue-400" />
                                        <h3 className="text-lg font-bold text-white">Customer Responsibilities</h3>
                                    </div>
                                    <ul className="space-y-3 text-sm text-gray-300">
                                        <li className="flex gap-2"><div className="w-1.5 h-1.5 rounded-full bg-blue-400 mt-1.5" /> Management of IAM Roles (Granting/Revoking)</li>
                                        <li className="flex gap-2"><div className="w-1.5 h-1.5 rounded-full bg-blue-400 mt-1.5" /> Reviewing cost recommendations</li>
                                        <li className="flex gap-2"><div className="w-1.5 h-1.5 rounded-full bg-blue-400 mt-1.5" /> Managing internal user access to dashboard</li>
                                    </ul>
                                </div>
                            </div>
                        </section>

                        {/* 3. IAM */}
                        <section id="iam-access" className="scroll-mt-32">
                            <h2 className="text-2xl font-semibold text-white mb-6 flex items-center gap-3">
                                <Lock className="h-6 w-6 text-primary" />
                                3. Identity & Access Management (IAM)
                            </h2>
                            <div className="bg-white/5 p-8 rounded-2xl border border-white/10">
                                <h3 className="text-xl font-bold text-white mb-2">3.1 Zero-Trust Integration</h3>
                                <p className="text-gray-300 mb-6 max-w-2xl">
                                    We strictly use temporary credentials and role assumption. We never store long-term keys.
                                    For AWS, we utilize the External ID condition key to prevent the &quot;Confused Deputy&quot; problem.
                                </p>
                                <div className="grid md:grid-cols-3 gap-4 mb-8">
                                    {[
                                        { title: "AWS", desc: "Cross-Account Role assumption (STS). Requires SecurityAudit role only.", color: "text-[#FF9900]" },
                                        { title: "Azure", desc: "Service Principal with built-in Reader role. No write access.", color: "text-[#0078D4]" },
                                        { title: "GCP", desc: "Service Account with Viewer role. Non-interactive access.", color: "text-[#4285F4]" },
                                    ].map((cloud) => (
                                        <div key={cloud.title} className="bg-black/50 p-5 rounded-xl border border-white/5 hover:border-white/10 transition-colors">
                                            <strong className={`block text-lg mb-2 ${cloud.color}`}>{cloud.title}</strong>
                                            <p className="text-xs text-gray-400 leading-relaxed">{cloud.desc}</p>
                                        </div>
                                    ))}
                                </div>
                                <div className="flex items-start gap-3 p-4 bg-green-500/10 border border-green-500/20 rounded-lg">
                                    <Shield className="h-5 w-5 text-green-400 shrink-0 mt-0.5" />
                                    <div>
                                        <strong className="text-green-400 text-sm block mb-1">Technical Guarantee</strong>
                                        <p className="text-green-200/80 text-sm">The system is technically incapable of provisioning, modifying, or deleting resources. Any write attempt is rejected by the cloud provider APIs.</p>
                                    </div>
                                </div>
                            </div>
                        </section>

                        {/* 4. Data Protection */}
                        <section id="data-protection" className="scroll-mt-32">
                            <h2 className="text-2xl font-semibold text-white mb-6 flex items-center gap-3">
                                <Database className="h-6 w-6 text-primary" />
                                4. Data Protection & Governance
                            </h2>
                            <div className="grid md:grid-cols-2 gap-8">
                                <div className="space-y-6">
                                    <div>
                                        <h3 className="text-lg font-medium text-white mb-3">Encryption Standards</h3>
                                        <ul className="space-y-4">
                                            <li className="flex gap-3">
                                                <div className="p-2 rounded bg-white/5"><Lock className="h-4 w-4 text-white" /></div>
                                                <div>
                                                    <strong className="text-white text-sm block">Data At Rest</strong>
                                                    <span className="text-sm text-gray-400">AES-256-GCM encryption. Keys managed via AWS KMS with annual rotation.</span>
                                                </div>
                                            </li>
                                            <li className="flex gap-3">
                                                <div className="p-2 rounded bg-white/5"><Globe className="h-4 w-4 text-white" /></div>
                                                <div>
                                                    <strong className="text-white text-sm block">Data In Transit</strong>
                                                    <span className="text-sm text-gray-400">Strictly enforced TLS 1.3 (HSTS enabled). No plaintext connections allowed.</span>
                                                </div>
                                            </li>
                                        </ul>
                                    </div>
                                </div>
                                <div className="bg-white/5 p-6 rounded-xl border border-white/10">
                                    <h3 className="text-lg font-medium text-white mb-4">Data Retention & Deletion</h3>
                                    <p className="text-sm text-gray-400 mb-4 leading-relaxed">
                                        Upon account termination, data deletion follows strict NIST SP 800-88 guidelines:
                                    </p>
                                    <div className="space-y-3">
                                        <div className="flex items-center justify-between text-sm py-2 border-b border-white/5">
                                            <span className="text-gray-300">0-30 Days</span>
                                            <span className="text-yellow-400">Soft Delete (Recovery Window)</span>
                                        </div>
                                        <div className="flex items-center justify-between text-sm py-2 border-b border-white/5">
                                            <span className="text-gray-300">30+ Days</span>
                                            <span className="text-red-400">Permanent Cryptographic Erasure</span>
                                        </div>
                                        <div className="flex items-center justify-between text-sm py-2">
                                            <span className="text-gray-300">Backups</span>
                                            <span className="text-gray-500">Purged after 90 days</span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </section>

                        {/* 5. App Security */}
                        <section id="app-security" className="scroll-mt-32">
                            <h2 className="text-2xl font-semibold text-white mb-6 flex items-center gap-3">
                                <Eye className="h-6 w-6 text-primary" />
                                5. Application Security
                            </h2>
                            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                                {[
                                    { title: "SDLC Security", desc: "Code goes through SAST/DAST scanning before every deployment." },
                                    { title: "Vulnerability Management", desc: "Automated dependency scanning (SCA) for all libraries." },
                                    { title: "Penetration Testing", desc: "Annual third-party black-box penetration tests." },
                                    { title: "DDoS Protection", desc: "Enterprise-grade protection via AWS Shield & Cloudflare." },
                                    { title: "WAF Rules", desc: "Managed rulesets for SQLi, XSS, and common exploits." },
                                    { title: "Audit Logging", desc: "Immutable logs for all system access and actions." },
                                ].map((item) => (
                                    <div key={item.title} className="p-4 rounded-lg bg-white/[0.03] border border-white/[0.06]">
                                        <h3 className="text-sm font-semibold text-white mb-1.5">{item.title}</h3>
                                        <p className="text-xs text-gray-400 leading-normal">{item.desc}</p>
                                    </div>
                                ))}
                            </div>
                        </section>

                        {/* 6. Compliance */}
                        <section id="compliance" className="scroll-mt-32">
                            <h2 className="text-2xl font-semibold text-white mb-6 flex items-center gap-3">
                                <FileText className="h-6 w-6 text-primary" />
                                6. Compliance & Certifications
                            </h2>
                            <div className="bg-white/5 rounded-2xl p-8 border border-white/10">
                                <div className="grid md:grid-cols-2 gap-8 mb-8">
                                    <div>
                                        <h3 className="text-lg font-bold text-white mb-2">SOC 2 Type II</h3>
                                        <p className="text-sm text-gray-400">
                                            Our infrastructure providers (AWS, Vercel, MongoDB) are SOC 2 Type II certified. We inherit critical physical and network security controls.
                                        </p>
                                    </div>
                                    <div>
                                        <h3 className="text-lg font-bold text-white mb-2">ISO 27001</h3>
                                        <p className="text-sm text-gray-400">
                                            Security management aligned with ISO/IEC 27001:2022 standards. Regular internal audits ensure continuous compliance.
                                        </p>
                                    </div>
                                </div>
                                <div className="flex flex-wrap gap-3">
                                    {["GDPR Ready", "CCPA Compliant", "DPDP Act 2023", "PCI-DSS Level 1 (Payment)", "HIPAA Eligible"].map((tag) => (
                                        <span key={tag} className="px-3 py-1 rounded-full bg-white/5 border border-white/10 text-xs text-gray-300">
                                            {tag}
                                        </span>
                                    ))}
                                </div>
                            </div>
                        </section>

                        {/* Contact */}
                        <section className="border-t border-white/10 pt-12">
                            <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
                                <div>
                                    <h2 className="text-xl font-bold text-white mb-2">Contact Security Team</h2>
                                    <p className="text-gray-400 text-sm">
                                        For security inquiries, audit reports, or responsible disclosure.
                                    </p>
                                    <a href="mailto:sambhav@cloudfinops.solutions" className="text-primary hover:underline mt-1 inline-block text-sm">
                                        sambhav@cloudfinops.solutions
                                    </a>
                                </div>
                                <div className="flex gap-4">
                                    <button className="flex items-center gap-2 bg-white text-black px-6 py-3 rounded-lg font-bold hover:bg-gray-200 transition-colors text-sm">
                                        <FileText className="h-4 w-4" />
                                        Download Security Whitepaper
                                    </button>
                                </div>
                            </div>
                            <p className="text-xs text-gray-600 mt-12">
                                © 2026 CloudFinOps Inc. All rights reserved.
                            </p>
                        </section>

                    </div>
                </div>
            </div>
        </div>
    );
}
