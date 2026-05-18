"use client";
// Force HMR Update


import dynamic from "next/dynamic";
import { SidebarProvider, useSidebar } from "@/components/dashboard/sidebar-context";
import { ScanProvider } from "@/components/dashboard/scan-provider";
import { NotificationProvider } from "@/components/dashboard/notification-provider";


const Sidebar = dynamic(
    () => import("@/components/dashboard/sidebar").then((mod) => mod.Sidebar),
    { ssr: false },
);

const Header = dynamic(
    () => import("@/components/dashboard/header").then((mod) => mod.Header),
    { ssr: false },
);

const GlobalAssistant = dynamic(
    () => import("@/components/dashboard/global-assistant").then((mod) => mod.GlobalAssistant),
    { ssr: false },
);

function DashboardContent({ children }: { children: React.ReactNode }) {
    const { collapsed } = useSidebar();

    return (
        <div className="min-h-screen bg-slate-950">
            <Sidebar />
            <main
                className={`transition-all duration-300 ${collapsed ? "lg:ml-20" : "lg:ml-64"
                    }`}
            >
                <Header />
                {children}
            </main>
        </div>
    );
}

export default function DashboardLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return (
        <NotificationProvider>
            <ScanProvider>
                <SidebarProvider>
                    <DashboardContent>{children}</DashboardContent>
                    <GlobalAssistant />
                </SidebarProvider>
            </ScanProvider>
        </NotificationProvider>
    );
}
