"use client";

import { createContext, useContext, useState, type ReactNode } from "react";

export const SidebarContext = createContext<{
    collapsed: boolean;
    setCollapsed: (value: boolean) => void;
}>({
    collapsed: false,
    setCollapsed: () => { },
});

export function useSidebar() {
    return useContext(SidebarContext);
}

export function SidebarProvider({ children }: { children: ReactNode }) {
    const [collapsed, setCollapsed] = useState(false);

    return (
        <SidebarContext.Provider value={{ collapsed, setCollapsed }}>
            {children}
        </SidebarContext.Provider>
    );
}
