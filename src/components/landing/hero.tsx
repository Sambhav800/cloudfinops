import { HeroBackdrop } from "@/components/landing/hero-backdrop";
import { HeroCopy } from "@/components/landing/hero-copy";
import { HeroShowcase } from "@/components/landing/hero-showcase";

export function Hero() {
    return (
        <section id="hero" className="relative min-h-screen overflow-hidden pt-32 pb-40">
            <HeroBackdrop />
            <div className="relative mx-auto max-w-7xl px-6">
                <HeroCopy />
                <HeroShowcase />
            </div>
        </section>
    );
}
