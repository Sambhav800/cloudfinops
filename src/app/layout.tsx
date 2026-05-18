import type { Metadata } from "next";
import type { CSSProperties, ReactNode } from "react";
import { Inter } from "next/font/google";
import "./globals.css";
import { ClerkProvider } from "@clerk/nextjs";
import { LayoutWrapper } from "@/components/layout-wrapper";
import { UserSync } from "@/components/auth/user-sync";

const inter = Inter({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-inter",
});

const rootFontStyles = {
  fontFamily: "var(--font-inter), var(--font-figtree), sans-serif",
  fontFeatureSettings: '"ss01", "cv11", "tnum"',
  "--font-figtree": "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
  "--font-geist-mono": "'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace",
} as CSSProperties;

export const metadata: Metadata = {
  title: "CloudFinOps - AI for Cloud Costs",
  description: "AI-driven Cloud Financial Operations",
  verification: {
    google: "GtYMZQFYo1dgmNIckrh5URBG0GL_yefcN-bAD-1ZhRk",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: ReactNode;
}>) {
  return (
    <ClerkProvider>
      <html lang="en" suppressHydrationWarning>
        <body
          className={`${inter.variable} antialiased min-h-screen flex flex-col`}
          style={rootFontStyles}
        >
          <UserSync />
          <LayoutWrapper>{children}</LayoutWrapper>
        </body>
      </html>
    </ClerkProvider>
  );
}
