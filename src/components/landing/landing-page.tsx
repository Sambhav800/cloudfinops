"use client";

import { Comparison } from "@/components/landing/comparison";
import { Footer } from "@/components/landing/footer";
import { FinalCTA } from "@/components/landing/final-cta";
import { CursorGlow } from "@/components/landing/cursor-glow";
import { CapabilitiesBento } from "@/components/landing/features/capabilities-bento";
import { FeatureGovernance } from "@/components/landing/features/feature-governance";
import { FeatureUnify } from "@/components/landing/features/feature-unify";
import { FeatureWaste } from "@/components/landing/features/feature-waste";
import { Hero } from "@/components/landing/hero";
import { HorizontalShowcase } from "@/components/landing/horizontal-showcase";
import { Metrics } from "@/components/landing/metrics";
import { Navbar } from "@/components/landing/navbar";
import { ScrollProgress } from "@/components/landing/scroll-progress";
import { SectionDivider } from "@/components/landing/section-divider";
import { Testimonials } from "@/components/landing/testimonials";
import { WorkflowSection } from "@/components/landing/workflow-section";

export function LandingPage() {
    return (
        <main className="relative min-h-screen overflow-x-clip bg-[#07080c] text-zinc-100 antialiased selection:bg-indigo-500/30 selection:text-white">
            <ScrollProgress />
            <CursorGlow />
            <Navbar />

            <div className="relative z-10">
                <Hero />

                <SectionDivider />
                <HorizontalShowcase />
                <FeatureUnify />
                <FeatureWaste />
                <FeatureGovernance />
                <WorkflowSection />
                <CapabilitiesBento />
                <SectionDivider />
                <Metrics />
                <Testimonials />
                <Comparison />
                <FinalCTA />

                <Footer />
            </div>
        </main>
    );
}
