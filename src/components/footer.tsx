import Link from "next/link";
import Image from "next/image";
import { Twitter, Linkedin, Github } from "lucide-react";

export function Footer() {
    return (
        <footer className="bg-black border-t border-white/10">
            <div className="mx-auto max-w-7xl px-6 py-16 lg:px-8">
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-12">

                    {/* Column 1: Logo */}
                    <div className="lg:col-span-1">
                        <Link href="/" className="flex items-center gap-2 mb-4">
                            <div className="relative h-8 w-8">
                                <Image
                                    src="/images/logo/wh-logo.png"
                                    alt="CloudFinOps"
                                    fill
                                    className="object-contain"
                                />
                            </div>
                            <span className="font-semibold text-lg text-white">CloudFinOps</span>
                        </Link>
                        <p className="text-sm text-gray-400 mb-6">
                            Automate Smarter, Optimize Faster, and Grow Stronger.
                        </p>
                    </div>

                    {/* Column 2: Links */}
                    <div>
                        <h4 className="text-sm font-semibold text-white mb-4">Product</h4>
                        <ul className="space-y-3">
                            <li><Link href="/features" className="text-sm text-gray-400 hover:text-white transition-colors">Features</Link></li>
                            <li><Link href="/how-it-works" className="text-sm text-gray-400 hover:text-white transition-colors">Process</Link></li>
                            <li><Link href="/security" className="text-sm text-gray-400 hover:text-white transition-colors">Security</Link></li>
                        </ul>
                    </div>

                    {/* Column 3: Company */}
                    <div>
                        <h4 className="text-sm font-semibold text-white mb-4">Company</h4>
                        <ul className="space-y-3">
                            <li><Link href="/about" className="text-sm text-gray-400 hover:text-white transition-colors">About</Link></li>
                            <li><Link href="/privacy" className="text-sm text-gray-400 hover:text-white transition-colors">Privacy</Link></li>
                            <li><Link href="/terms" className="text-sm text-gray-400 hover:text-white transition-colors">Terms</Link></li>
                        </ul>
                    </div>

                    {/* Column 4: Socials */}
                    <div>
                        <h4 className="text-sm font-semibold text-white mb-4">Socials</h4>
                        <ul className="space-y-3">
                            <li>
                                <a href="https://x.com/sambhavpal5" target="_blank" rel="noopener noreferrer" className="flex items-center gap-2 text-sm text-gray-400 hover:text-white transition-colors">
                                    <Twitter className="w-4 h-4" /> Twitter
                                </a>
                            </li>
                            <li>
                                <a href="https://www.linkedin.com/in/sambhav-pal050405" target="_blank" rel="noopener noreferrer" className="flex items-center gap-2 text-sm text-gray-400 hover:text-white transition-colors">
                                    <Linkedin className="w-4 h-4" /> LinkedIn
                                </a>
                            </li>

                        </ul>
                    </div>
                </div>

                {/* Bottom Bar */}
                <div className="mt-12 pt-8 border-t border-white/10 flex flex-col md:flex-row items-center justify-between gap-4">
                    <p className="text-xs text-gray-500">
                        © 2026 CloudFinOps. All rights reserved.
                    </p>
                    <div className="flex items-center gap-6">
                        {/* Links moved to main columns */}
                    </div>
                </div>
            </div>
        </footer>
    );
}
