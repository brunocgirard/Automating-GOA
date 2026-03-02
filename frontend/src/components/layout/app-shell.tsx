"use client";

import { useState, useCallback, useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";

import { Header } from "./header";
import { Sidebar } from "./sidebar";
import { ClientFilterProvider } from "./client-filter-context";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { ApiError, fetchCurrentUser } from "@/lib/api";
import type { User } from "@/lib/types";

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();

  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [selectedClientId, setSelectedClientId] = useState<string | null>(null);
  const [currentUser, setCurrentUser] = useState<User | null>(null);

  const isPublicAuthRoute = pathname === "/login" || pathname === "/register";

  useEffect(() => {
    if (isPublicAuthRoute) return;

    let active = true;

    void fetchCurrentUser()
      .then((user) => {
        if (!active) return;
        setCurrentUser(user);
      })
      .catch((error) => {
        if (!active) return;
        setCurrentUser(null);

        const nextPath = `${pathname}`;
        if (error instanceof ApiError && error.status === 401) {
          router.replace(`/login?next=${encodeURIComponent(nextPath)}`);
          return;
        }
        router.replace(`/login?next=${encodeURIComponent(nextPath)}`);
      });

    return () => {
      active = false;
    };
  }, [isPublicAuthRoute, pathname, router]);

  const toggleSidebar = useCallback(() => {
    if (window.innerWidth < 768) {
      setMobileOpen((value) => !value);
    } else {
      setSidebarOpen((value) => !value);
    }
  }, []);

  if (isPublicAuthRoute) {
    return <>{children}</>;
  }

  if (!currentUser) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-neutral-100 px-4">
        <p className="rounded-md border border-neutral-200 bg-white px-4 py-3 text-sm text-neutral-600">
          Checking session...
        </p>
      </div>
    );
  }

  return (
    <ClientFilterProvider value={{ selectedClientId, setSelectedClientId }}>
      <div className="flex h-screen flex-col overflow-hidden">
        <Header onToggleSidebar={toggleSidebar} currentUser={currentUser} onUserChange={setCurrentUser} />
        <div className="flex flex-1 overflow-hidden">
          <div className="hidden md:flex">
            <Sidebar
              open={sidebarOpen}
              onClose={() => setSidebarOpen(false)}
              selectedClientId={selectedClientId}
              onSelectClient={setSelectedClientId}
            />
          </div>

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

          <main className="flex-1 overflow-auto bg-neutral-100 p-3 sm:p-4 lg:p-6">{children}</main>
        </div>
      </div>
    </ClientFilterProvider>
  );
}
