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

const SITE_URL = "https://cloudfinops.solutions";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: "CloudFinOps — AI-Powered Cloud Cost Optimization for AWS, Azure & GCP",
    template: "%s | CloudFinOps",
  },
  description:
    "CloudFinOps is an AI-powered FinOps platform that detects idle cloud resources, reduces waste by up to 30%, and automates governance across AWS, Azure, and GCP. Read-only, agentless, setup in 5 minutes.",
  keywords: [
    "cloud cost optimization",
    "FinOps platform",
    "AWS cost management",
    "Azure cost optimization",
    "GCP cost reduction",
    "cloud waste detection",
    "idle resource detection",
    "cloud governance",
    "AI cloud optimization",
    "multi-cloud cost management",
  ],
  authors: [{ name: "CloudFinOps", url: SITE_URL }],
  creator: "CloudFinOps",
  publisher: "CloudFinOps",
  verification: {
    google: "GtYMZQFYo1dgmNIckrh5URBG0GL_yefcN-bAD-1ZhRk",
  },
  openGraph: {
    type: "website",
    locale: "en_US",
    url: SITE_URL,
    siteName: "CloudFinOps",
    title: "CloudFinOps — AI-Powered Cloud Cost Optimization",
    description:
      "Detect idle cloud resources, reduce waste by up to 30%, and automate governance across AWS, Azure, and GCP. Read-only, agentless, setup in 5 minutes.",
    images: [
      {
        url: "/images/og-image.png",
        width: 1200,
        height: 630,
        alt: "CloudFinOps — AI-Powered Cloud Cost Optimization Platform",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "CloudFinOps — AI-Powered Cloud Cost Optimization",
    description:
      "Detect idle cloud resources, reduce waste by up to 30%, and automate governance across AWS, Azure, and GCP.",
    images: ["/images/og-image.png"],
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-video-preview": -1,
      "max-image-preview": "large",
      "max-snippet": -1,
    },
  },
  alternates: {
    canonical: SITE_URL,
  },
};

const organizationJsonLd = {
  "@context": "https://schema.org",
  "@type": "Organization",
  name: "CloudFinOps",
  url: SITE_URL,
  logo: `${SITE_URL}/images/logo/wh-logo.png`,
  description:
    "AI-powered FinOps platform that detects idle cloud resources, reduces waste by up to 30%, and automates governance across AWS, Azure, and GCP.",
  foundingDate: "2025",
  founders: [
    {
      "@type": "Person",
      name: "Sambhav Pal",
      jobTitle: "Founder & CEO",
      sameAs: "https://www.linkedin.com/company/cloudfinops-official/",
    },
  ],
  contactPoint: {
    "@type": "ContactPoint",
    email: "sambhav@cloudfinops.solutions",
    contactType: "sales",
  },
  address: {
    "@type": "PostalAddress",
    addressLocality: "Zirakpur",
    addressRegion: "Punjab",
    addressCountry: "IN",
  },
  sameAs: [
    "https://www.linkedin.com/company/cloudfinops-official/",
    "https://github.com/CloudFinOps-Official",
  ],
  knowsAbout: [
    "Cloud Cost Optimization",
    "FinOps",
    "Cloud Governance",
    "AWS Cost Management",
    "Azure Cost Management",
    "GCP Billing",
    "Idle Resource Detection",
  ],
  areaServed: "Worldwide",
};

const websiteJsonLd = {
  "@context": "https://schema.org",
  "@type": "WebSite",
  name: "CloudFinOps",
  url: SITE_URL,
  description: "AI-powered cloud cost optimization and governance platform",
  publisher: {
    "@type": "Organization",
    name: "CloudFinOps",
  },
  inLanguage: "en",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: ReactNode;
}>) {
  return (
    <ClerkProvider>
      <html lang="en" suppressHydrationWarning>
        <head>
          <script
            type="application/ld+json"
            dangerouslySetInnerHTML={{
              __html: JSON.stringify(organizationJsonLd),
            }}
          />
          <script
            type="application/ld+json"
            dangerouslySetInnerHTML={{
              __html: JSON.stringify(websiteJsonLd),
            }}
          />
        </head>
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
