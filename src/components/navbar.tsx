import Link from "next/link";
import Image from "next/image";
import { SignInButton, SignUpButton, SignedIn, SignedOut, UserButton } from "@clerk/nextjs";

const navigation = [
    { label: "Home", href: "/" },
    { label: "About", href: "/about" },
    { label: "Security", href: "/security" },
];

export function Navbar() {
    return (
        <nav className="fixed top-0 left-0 right-0 z-50 border-b border-white/10 bg-black/60 backdrop-blur-xl">
            <div className="mx-auto max-w-7xl px-6">
                <div className="flex h-16 items-center justify-between">
                    <div className="flex items-center gap-8">
                        <Link href="/" className="flex items-center gap-2">
                            <div className="relative h-8 w-8">
                                <Image
                                    src="/images/logo/wh-logo.png"
                                    alt="CloudFinOps"
                                    fill
                                    className="object-contain"
                                />
                            </div>
                            <span className="font-semibold text-lg hidden sm:block text-white">CloudFinOps</span>
                        </Link>

                        <div className="hidden md:flex items-center gap-6 text-sm font-medium text-gray-400">
                            {navigation.map((item) => (
                                <Link key={item.href} href={item.href} className="hover:text-white transition-colors">
                                    {item.label}
                                </Link>
                            ))}
                        </div>
                    </div>

                    <div className="flex items-center gap-3">
                        <SignedOut>
                            <SignInButton mode="modal">
                                <button className="rounded-md border border-primary/50 px-4 py-2 text-sm font-semibold text-primary hover:bg-primary/10 transition-colors">
                                    Login
                                </button>
                            </SignInButton>
                            <SignUpButton mode="modal">
                                <button className="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-white hover:bg-primary/90 transition-all hover:scale-105">
                                    Sign Up
                                </button>
                            </SignUpButton>
                        </SignedOut>

                        <SignedIn>
                            <Link
                                href="/dashboard"
                                className="rounded-md bg-primary px-4 py-2 text-sm font-semibold text-white hover:bg-primary/90 transition-all"
                            >
                                Dashboard
                            </Link>
                            <UserButton
                                appearance={{
                                    elements: {
                                        avatarBox: "w-9 h-9 border border-white/20",
                                    },
                                }}
                            />
                        </SignedIn>
                    </div>
                </div>
            </div>
        </nav>
    );
}
