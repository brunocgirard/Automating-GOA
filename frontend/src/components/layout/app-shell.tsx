"use client";

import { useState, useCallback } from "react";
import { Header } from "./header";
import { Sidebar } from "./sidebar";
import { ClientFilterProvider } from "./client-filter-context";
import {
  Sheet,
  SheetContent,
  SheetTitle,
} from "@/components/ui/sheet";

export function AppShell({ children }: { children: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [selectedClientId, setSelectedClientId] = useState<string | null>(null);

  const toggleSidebar = useCallback(() => {
    // On mobile (<768px) open sheet, on desktop toggle sidebar
    if (window.innerWidth < 768) {
      setMobileOpen((v) => !v);
    } else {
      setSidebarOpen((v) => !v);
    }
  }, []);

  return (
    <ClientFilterProvider value={{ selectedClientId, setSelectedClientId }}>
      <div className="flex h-screen flex-col overflow-hidden">
        <Header onToggleSidebar={toggleSidebar} />
        <div className="flex flex-1 overflow-hidden">
          {/* Desktop sidebar */}
          <div className="hidden md:flex">
            <Sidebar
              open={sidebarOpen}
              onClose={() => setSidebarOpen(false)}
              selectedClientId={selectedClientId}
              onSelectClient={setSelectedClientId}
            />
          </div>

          {/* Mobile sidebar */}
          <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
            <SheetContent side="left" className="w-64 p-0">
              <SheetTitle className="sr-only">Navigation</SheetTitle>
              <Sidebar
                open={true}
                onClose={() => setMobileOpen(false)}
                selectedClientId={selectedClientId}
                onSelectClient={setSelectedClientId}
              />
            </SheetContent>
          </Sheet>

          {/* Main content */}
          <main className="flex-1 overflow-auto bg-neutral-100 p-3 sm:p-4 lg:p-6">
            {children}
          </main>
        </div>
      </div>
    </ClientFilterProvider>
  );
}
