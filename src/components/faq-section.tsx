"use client";

import { motion, AnimatePresence } from "framer-motion";
import { useState } from "react";
import { ChevronDown } from "lucide-react";

const faqs = [
    {
        question: "How does CloudFinOps connect to my cloud accounts?",
        answer: "We use read-only IAM roles with minimal permissions — we never modify, delete, or write to your infrastructure. You provide read-only credentials, we encrypt them with AES-256-GCM, and our scanner discovers resources across all regions. The entire setup takes under 2 minutes."
    },
    {
        question: "Is my data secure?",
        answer: "Security is foundational, not an afterthought. All credentials are encrypted at rest with AES-256-GCM (with auth tags for tamper detection). MongoDB Tenant-Level Security ensures complete tenant isolation — no other customer can ever see your data. All connections use TLS 1.3 encryption in transit."
    },
    {
        question: "How long does the first scan take?",
        answer: "Just a few minutes. Once you connect your cloud account, our scanner sweeps all 17+ AWS regions (or equivalent Azure/GCP scopes), identifies every resource, calculates costs, and flags waste — while you grab a coffee."
    },
    {
        question: "What cloud providers do you support?",
        answer: "We currently support AWS, Microsoft Azure, and Google Cloud Platform with dedicated scanners for each. Each provider has its own scanning engine built to understand provider-specific resource types, pricing models, and region structures."
    },
    {
        question: "Can I try before I commit?",
        answer: "Absolutely. Run a free cloud audit to see your waste, shadow IT, and savings potential. No credit card required, no sales call needed. You'll see real results from your first scan — then decide if you want to keep going."
    },
    {
        question: "How does the AI analysis work?",
        answer: "Our AI engine analyzes your actual resource metadata — utilization rates, attachment status, region placement, and spend patterns — to surface waste you'd never catch manually. Instead of generic PDF reports, it generates specific recommendations with the exact CLI commands to fix each issue. Copy, paste, save."
    }
];

export function FAQSection() {
    const [openIndex, setOpenIndex] = useState<number | null>(0);

    return (
        <section className="py-24 bg-black relative overflow-hidden">
            <div className="mx-auto max-w-3xl px-6 lg:px-8 relative z-10">
                {/* Header */}
                <motion.div
                    initial={{ opacity: 0, y: 40 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ duration: 0.6 }}
                    className="text-center mb-12"
                >
                    <span className="pill-badge mb-4">FAQ</span>
                    <h2 className="text-4xl md:text-5xl font-semibold text-white tracking-tight mt-4">
                        Frequently Asked{" "}
                        <span className="text-gradient">Questions</span>
                    </h2>
                </motion.div>

                {/* Accordion */}
                <div className="space-y-4">
                    {faqs.map((faq, index) => (
                        <motion.div
                            key={index}
                            initial={{ opacity: 0, y: 20 }}
                            whileInView={{ opacity: 1, y: 0 }}
                            viewport={{ once: true }}
                            transition={{ duration: 0.4, delay: index * 0.05 }}
                        >
                            <button
                                onClick={() => setOpenIndex(openIndex === index ? null : index)}
                                className="w-full text-left p-5 rounded-xl border border-white/10 bg-white/5 hover:bg-white/10 transition-colors"
                            >
                                <div className="flex items-center justify-between">
                                    <span className="text-white font-medium pr-4">{faq.question}</span>
                                    <ChevronDown
                                        className={`w-5 h-5 text-gray-400 flex-shrink-0 transition-transform duration-300 ${openIndex === index ? "rotate-180" : ""
                                            }`}
                                    />
                                </div>

                                <AnimatePresence>
                                    {openIndex === index && (
                                        <motion.div
                                            initial={{ height: 0, opacity: 0 }}
                                            animate={{ height: "auto", opacity: 1 }}
                                            exit={{ height: 0, opacity: 0 }}
                                            transition={{ duration: 0.3 }}
                                            className="overflow-hidden"
                                        >
                                            <p className="text-gray-400 text-sm mt-4 leading-relaxed">
                                                {faq.answer}
                                            </p>
                                        </motion.div>
                                    )}
                                </AnimatePresence>
                            </button>
                        </motion.div>
                    ))}
                </div>
            </div>
        </section>
    );
}
