"use client";

import { useState } from "react";
import { CheckCircle, Lock, ChevronDown, Loader2 } from "lucide-react";
import Link from "next/link";

export default function AuditPage() {
    const [submitted, setSubmitted] = useState(false);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");

    const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        setLoading(true);
        setError("");

        const form = e.currentTarget;
        const formData = new FormData(form);

        // Collect checkbox values for cloud providers
        const cloudProviders: string[] = [];
        form.querySelectorAll<HTMLInputElement>('input[name="cloudProvider"]:checked').forEach((cb) => {
            cloudProviders.push(cb.value);
        });

        const payload = {
            firstName: formData.get("firstName") as string,
            lastName: formData.get("lastName") as string,
            email: formData.get("email") as string,
            phone: formData.get("phone") as string,
            jobTitle: formData.get("jobTitle") as string,
            department: formData.get("department") as string,
            companyName: formData.get("companyName") as string,
            companyWebsite: formData.get("companyWebsite") as string,
            companySize: formData.get("companySize") as string,
            industry: formData.get("industry") as string,
            cloudProviders,
            monthlySpend: formData.get("monthlySpend") as string,
            primaryConcern: formData.get("primaryConcern") as string,
            notes: formData.get("notes") as string,
        };

        try {
            const res = await fetch("/api/audit-request", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });

            const data = await res.json();

            if (!res.ok) {
                // If the server returns an error, specifically show it
                const errorMessage = data.error || "Submission failed. Please try again or email us directly.";
                setError(errorMessage);
                // Scroll to top to see error
                window.scrollTo({ top: 0, behavior: 'smooth' });
                return;
            }

            // Success: clear everything and show success message
            setSubmitted(true);
            window.scrollTo({ top: 0, behavior: 'smooth' });

        } catch (err) {
            console.error("Form submission error:", err);
            setError("Network error. Please check your connection and try again.");
            window.scrollTo({ top: 0, behavior: 'smooth' });
        } finally {
            setLoading(false);
        }
    };

    if (submitted) {
        return (
            <div className="min-h-screen bg-black flex items-center justify-center p-6">
                <div className="bg-white/10 border border-white/20 p-12 rounded-3xl text-center max-w-lg w-full backdrop-blur-md">
                    <div className="flex justify-center mb-6">
                        <div className="h-20 w-20 bg-green-500/20 rounded-full flex items-center justify-center">
                            <CheckCircle className="h-10 w-10 text-green-500" />
                        </div>
                    </div>
                    <h2 className="text-3xl font-bold text-white mb-4">Request Received!</h2>
                    <p className="text-gray-300 mb-2">
                        We&apos;ve sent a confirmation to your email.
                    </p>
                    <p className="text-gray-400 text-sm mb-8">
                        Our team will review your cloud setup and get back to you within 24 hours with the next steps for your free audit.
                    </p>
                    <Link href="/" className="bg-white text-black font-bold py-3 px-8 rounded-full hover:bg-gray-200 transition-colors">
                        Return Home
                    </Link>
                </div>
            </div>
        );
    }

    return (
        <div className="bg-black min-h-screen pt-24 pb-12">
            <div className="mx-auto max-w-7xl px-6 lg:px-8 flex flex-col lg:flex-row gap-16">

                {/* Left Side: Info */}
                <div className="lg:w-1/2">
                    <h1 className="text-4xl font-bold text-white mb-6">
                        Free 7-Day Cloud Audit
                    </h1>
                    <p className="text-xl text-gray-400 mb-12">
                        Get expert analysis of your cloud spending and discover your savings potential.
                    </p>

                    <div className="space-y-8 mb-12">
                        <Feature
                            title="Cost Analysis Report"
                            desc="Detailed breakdown of your cloud spending"
                        />
                        <Feature
                            title="Optimization Recommendations"
                            desc="Actionable steps to reduce costs"
                        />
                        <Feature
                            title="Savings Projection"
                            desc="Estimated annual savings potential"
                        />
                        <Feature
                            title="Expert Consultation"
                            desc="30-minute call with our cloud specialist"
                        />
                    </div>

                    <div className="bg-white/5 border border-white/10 p-6 rounded-2xl flex items-start gap-4">
                        <Lock className="h-6 w-6 text-green-400 flex-shrink-0 mt-1" />
                        <div>
                            <h3 className="text-white font-bold mb-1">Your Data is Safe</h3>
                            <p className="text-sm text-gray-400">
                                We never ask for access keys, credentials, or any sensitive information during the audit request process.
                            </p>
                        </div>
                    </div>
                </div>

                {/* Right Side: Form */}
                <div className="lg:w-1/2">
                    <div className="bg-white/5 border border-white/10 p-8 rounded-3xl backdrop-blur-sm">
                        <h2 className="text-2xl font-bold text-white mb-6">Tell Us About Your Cloud Setup</h2>
                        <p className="text-gray-400 text-sm mb-8">Fill out the form below and we&apos;ll get back to you within 24 hours</p>

                        {error && (
                            <div className="mb-6 p-4 rounded-xl bg-red-500/10 border border-red-500/50 text-red-200 text-sm font-medium flex items-center gap-3">
                                <div className="h-2 w-2 rounded-full bg-red-500 animate-pulse" />
                                {error}
                            </div>
                        )}

                        <form onSubmit={handleSubmit} className="space-y-6">
                            {/* Name */}
                            <div className="grid grid-cols-2 gap-4">
                                <Input name="firstName" label="First Name" placeholder="John" required />
                                <Input name="lastName" label="Last Name" placeholder="Doe" required />
                            </div>

                            {/* Contact */}
                            <div className="grid grid-cols-1 gap-4">
                                <Input name="email" label="Work Email" type="email" placeholder="john@company.com" required />
                                <Input name="phone" label="Phone Number" placeholder="+1 (555) 123-4567" />
                            </div>

                            {/* Role */}
                            <div className="grid grid-cols-2 gap-4">
                                <Input name="jobTitle" label="Job Title" placeholder="Cloud Architect" required />
                                <Select name="department" label="Department" options={["Engineering", "DevOps", "Finance", "Leadership"]} />
                            </div>

                            {/* Company */}
                            <div className="space-y-4">
                                <Input name="companyName" label="Company Name" placeholder="Acme Inc." required />
                                <Input name="companyWebsite" label="Company Website" placeholder="https://www.company.com" />
                                <div className="grid grid-cols-2 gap-4">
                                    <Select name="companySize" label="Company Size" options={["1-50", "51-200", "201-1000", "1000+"]} required />
                                    <Select name="industry" label="Industry" options={["SaaS", "FinTech", "Healthcare", "E-commerce", "Other"]} />
                                </div>
                            </div>

                            {/* Cloud Info */}
                            <div>
                                <label className="block text-sm font-medium text-gray-300 mb-2">Cloud Providers You Use *</label>
                                <div className="space-y-2">
                                    <Checkbox name="cloudProvider" value="Amazon Web Services (AWS)" label="Amazon Web Services (AWS)" />
                                    <Checkbox name="cloudProvider" value="Microsoft Azure" label="Microsoft Azure" />
                                    <Checkbox name="cloudProvider" value="Google Cloud Platform" label="Google Cloud Platform" />
                                    <Checkbox name="cloudProvider" value="Other" label="Other" />
                                </div>
                            </div>

                            <Select
                                name="monthlySpend"
                                label="Estimated Monthly Cloud Spend *"
                                options={["<₹8L", "₹8L - ₹40L", "₹40L - ₹80L", "₹80L+"]}
                                required
                            />

                            <Select
                                name="primaryConcern"
                                label="Primary Concern"
                                options={["Rising Costs", "Waste/Idle Resources", "Budget Forecasting", "Other"]}
                            />

                            <div>
                                <label className="block text-sm font-medium text-gray-300 mb-2">Anything else you&apos;d like us to know?</label>
                                <textarea
                                    name="notes"
                                    rows={3}
                                    className="w-full bg-black/50 border border-white/20 rounded-lg p-3 text-white focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary transition-colors resize-none"
                                    placeholder="Tell us about your specific challenges or goals..."
                                ></textarea>
                            </div>

                            <div className="pt-4">
                                <button
                                    type="submit"
                                    disabled={loading}
                                    className="w-full bg-primary text-black font-bold py-4 rounded-full text-lg hover:brightness-110 transition-all shadow-[0_0_20px_rgba(0,210,255,0.3)] disabled:opacity-60 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                                >
                                    {loading ? (
                                        <>
                                            <Loader2 className="h-5 w-5 animate-spin" />
                                            Submitting...
                                        </>
                                    ) : (
                                        "Start My Free Audit"
                                    )}
                                </button>
                                <p className="text-center text-xs text-gray-500 mt-4 flex items-center justify-center gap-1">
                                    <Lock className="h-3 w-3" /> Your information is secure and will never be shared.
                                </p>
                            </div>
                        </form>
                    </div>
                </div>
            </div>
        </div>
    );
}

function Feature({ title, desc }: { title: string, desc: string }) {
    return (
        <div className="flex gap-4">
            <div className="h-10 w-10 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0">
                <CheckCircle className="h-5 w-5 text-primary" />
            </div>
            <div>
                <h3 className="text-white font-bold">{title}</h3>
                <p className="text-gray-400 text-sm">{desc}</p>
            </div>
        </div>
    );
}

function Input({ name, label, type = "text", placeholder, required = false }: { name: string; label: string; type?: string; placeholder?: string; required?: boolean }) {
    return (
        <div>
            <label className="block text-sm font-medium text-gray-300 mb-1.5">
                {label} {required && <span className="text-red-500">*</span>}
            </label>
            <input
                name={name}
                type={type}
                placeholder={placeholder}
                required={required}
                className="w-full bg-black/50 border border-white/20 rounded-lg p-3 text-white focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary transition-colors"
            />
        </div>
    );
}

function Select({ name, label, options, required = false }: { name: string; label: string; options: string[]; required?: boolean }) {
    return (
        <div>
            <label className="block text-sm font-medium text-gray-300 mb-1.5">
                {label} {required && <span className="text-red-500">*</span>}
            </label>
            <div className="relative">
                <select
                    name={name}
                    required={required}
                    defaultValue=""
                    className="w-full bg-black/50 border border-white/20 rounded-lg p-3 text-white appearance-none focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary transition-colors"
                >
                    <option value="" disabled>Select...</option>
                    {options.map((opt: string) => <option key={opt} value={opt}>{opt}</option>)}
                </select>
                <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400 pointer-events-none" />
            </div>
        </div>
    );
}

function Checkbox({ name, value, label }: { name: string; value: string; label: string }) {
    return (
        <label className="flex items-center gap-3 cursor-pointer group">
            <input name={name} value={value} type="checkbox" className="w-5 h-5 rounded border-white/20 bg-black/50 text-primary focus:ring-primary" />
            <span className="text-gray-300 group-hover:text-white transition-colors text-sm">{label}</span>
        </label>
    );
}
