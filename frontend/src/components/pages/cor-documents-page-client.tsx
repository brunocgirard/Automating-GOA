"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Plus } from "lucide-react";
import { fetchCorDashboard, type CorDashboardEntry } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

type ClientOption = { id: string; name: string; corCount: number };

function corStatusBadgeConfig(rawStatus: string): { label: string; className: string } {
  const cleanStatus = rawStatus.trim();
  const normalized = cleanStatus.toLowerCase();
  if (!cleanStatus || normalized === "not submitted") {
    return { label: cleanStatus || "Draft", className: "bg-neutral-200 text-neutral-700" };
  }
  if (normalized === "approved" || normalized === "for your files") {
    return { label: cleanStatus, className: "bg-green-100 text-green-800" };
  }
  return { label: cleanStatus, className: "bg-yellow-100 text-yellow-800" };
}

export default function CorDocumentsPageClient() {
  const [dashboardEntries, setDashboardEntries] = useState<CorDashboardEntry[]>([]);
  const [dashboardClientFilter, setDashboardClientFilter] = useState<string>("__all__");
  const [loadingDashboard, setLoadingDashboard] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    void fetchCorDashboard()
      .then((rows) => {
        if (!active) return;
        setDashboardEntries(rows);
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Failed to load COR dashboard.");
      })
      .finally(() => {
        if (active) setLoadingDashboard(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const dashboardClientOptions = useMemo<ClientOption[]>(() => {
    const map = new Map<string, ClientOption>();
    for (const entry of dashboardEntries) {
      const existing = map.get(entry.clientId);
      if (existing) {
        existing.corCount += 1;
      } else {
        map.set(entry.clientId, {
          id: entry.clientId,
          name: entry.clientName,
          corCount: 1,
        });
      }
    }
    return Array.from(map.values()).sort((a, b) => a.name.localeCompare(b.name));
  }, [dashboardEntries]);

  const filteredDashboardEntries = useMemo(() => {
    if (dashboardClientFilter === "__all__") return dashboardEntries;
    return dashboardEntries.filter((entry) => entry.clientId === dashboardClientFilter);
  }, [dashboardClientFilter, dashboardEntries]);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">COR Documents</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Manage all Change Order Request revisions and jump directly into editing.
          </p>
        </div>
        <Button asChild className="bg-[#c00000] hover:bg-[#a00000]">
          <Link href="/cor/new">
            <Plus className="mr-2 h-4 w-4" />
            New COR
          </Link>
        </Button>
      </div>

      {error ? (
        <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>COR Dashboard</CardTitle>
          <CardDescription>
            Filter by client and open any COR directly in the dedicated editor page.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="max-w-sm space-y-1.5">
            <label className="text-sm font-medium">Client Filter</label>
            <Select value={dashboardClientFilter} onValueChange={setDashboardClientFilter}>
              <SelectTrigger>
                <SelectValue placeholder="All clients" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__all__">All clients</SelectItem>
                {dashboardClientOptions.map((option) => (
                  <SelectItem key={option.id} value={option.id}>
                    {option.name} ({option.corCount})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {loadingDashboard ? (
            <div className="rounded-md border bg-neutral-50 p-3 text-sm text-muted-foreground">
              Loading COR dashboard...
            </div>
          ) : (
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Client</TableHead>
                    <TableHead>Quote</TableHead>
                    <TableHead>COR No.</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Description</TableHead>
                    <TableHead>Updated</TableHead>
                    <TableHead className="text-right">Action</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredDashboardEntries.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={7} className="h-16 text-center text-muted-foreground">
                        No COR entries found for this filter.
                      </TableCell>
                    </TableRow>
                  ) : (
                    filteredDashboardEntries.map((entry) => {
                      const corLabel = entry.corNo.trim() || String(entry.corDocumentId);
                      const statusBadge = corStatusBadgeConfig(entry.corStatus);
                      return (
                        <TableRow key={`${entry.quoteId}:${entry.corDocumentId}`}>
                          <TableCell>{entry.clientName}</TableCell>
                          <TableCell>{entry.quoteRef}</TableCell>
                          <TableCell className="font-semibold">COR {corLabel}</TableCell>
                          <TableCell>
                            <Badge className={statusBadge.className} variant="secondary">
                              {statusBadge.label}
                            </Badge>
                          </TableCell>
                          <TableCell>{entry.description.trim() || "-"}</TableCell>
                          <TableCell>{entry.modifiedDate ?? entry.createdDate ?? "-"}</TableCell>
                          <TableCell className="text-right">
                            <Button type="button" variant="ghost" size="sm" asChild>
                              <Link href={`/cor/${entry.corDocumentId}?quote=${entry.quoteId}`}>Edit</Link>
                            </Button>
                          </TableCell>
                        </TableRow>
                      );
                    })
                  )}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
