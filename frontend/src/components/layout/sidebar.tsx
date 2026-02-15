"use client";

import { useState, useMemo, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Cog,
  FileText,
  Files,
  ChevronLeft,
  Search,
  Building2,
  UserRound,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import { fetchClients, type Client } from "@/lib/api";

const navItems = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/client-info", label: "Client Info", icon: UserRound },
  { href: "/processing", label: "Processing", icon: Cog },
  { href: "/shipping-documents", label: "Shipping Docs", icon: Files },
  { href: "/reports", label: "Reports", icon: FileText },
];

interface SidebarProps {
  open: boolean;
  onClose: () => void;
  selectedClientId: string | null;
  onSelectClient: (id: string | null) => void;
}

export function Sidebar({
  open,
  onClose,
  selectedClientId,
  onSelectClient,
}: SidebarProps) {
  const pathname = usePathname();
  const [search, setSearch] = useState("");
  const [clients, setClients] = useState<Client[]>([]);

  useEffect(() => {
    let active = true;
    void fetchClients()
      .then((rows) => {
        if (active) setClients(rows);
      })
      .catch(() => {
        if (active) setClients([]);
      });
    return () => {
      active = false;
    };
  }, []);

  const filteredClients = useMemo(
    () =>
      clients.filter((c) =>
        c.name.toLowerCase().includes(search.toLowerCase())
      ),
    [clients, search]
  );

  if (!open) return null;

  return (
    <aside className="flex h-full w-64 shrink-0 flex-col border-r border-border bg-neutral-50">
      {/* Nav links */}
      <nav className="flex flex-col gap-1 p-3">
        {navItems.map((item) => {
          const active = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                active
                  ? "bg-[#c00000] text-white"
                  : "text-neutral-700 hover:bg-neutral-200"
              )}
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>

      <Separator />

      {/* Client search */}
      <div className="p-3">
        <div className="relative">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-neutral-400" />
          <Input
            placeholder="Search clients..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9 h-9 text-sm"
          />
        </div>
      </div>

      {/* Client list */}
      <ScrollArea className="flex-1 px-3 pb-3">
        <div className="flex flex-col gap-0.5">
          {filteredClients.map((client) => (
            <button
              key={client.id}
              onClick={() =>
                onSelectClient(
                  client.id === selectedClientId ? null : client.id
                )
              }
              className={cn(
                "flex items-center gap-2 rounded-md px-3 py-2 text-left text-sm transition-colors w-full",
                client.id === selectedClientId
                  ? "bg-[#c00000]/10 text-[#c00000] font-medium"
                  : "text-neutral-600 hover:bg-neutral-200"
              )}
            >
              <Building2 className="h-3.5 w-3.5 shrink-0" />
              <span className="truncate">{client.name}</span>
              <span className="ml-auto text-xs text-neutral-400">
                {client.quoteCount}
              </span>
            </button>
          ))}
        </div>
      </ScrollArea>

      <Separator />

      {/* Collapse */}
      <div className="p-2">
        <Button
          variant="ghost"
          size="sm"
          onClick={onClose}
          className="w-full justify-start gap-2 text-neutral-500"
        >
          <ChevronLeft className="h-4 w-4" />
          Collapse
        </Button>
      </div>
    </aside>
  );
}
