"use client";

import { useState, useMemo, useEffect, useCallback } from "react";
import { fetchQuotes, type QuoteRow } from "@/lib/api";
import { MachineTable } from "@/components/dashboard/quote-table";
import { QuoteFilters } from "@/components/dashboard/quote-filters";
import { UploadDialog } from "@/components/dashboard/upload-dialog";
import { useClientFilter } from "@/components/layout/client-filter-context";

export default function DashboardPage() {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [quotes, setQuotes] = useState<QuoteRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { selectedClientId } = useClientFilter();

  const loadQuotes = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchQuotes();
      setQuotes(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load quotes.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadQuotes();
  }, [loadQuotes]);

  const filtered = useMemo(() => {
    const s = search.toLowerCase();
    return quotes.filter((q) => {
      if (statusFilter !== "all" && q.status !== statusFilter) return false;
      if (selectedClientId && q.clientId !== selectedClientId) return false;
      if (
        s &&
        !q.quoteRef.toLowerCase().includes(s) &&
        !q.clientName.toLowerCase().includes(s) &&
        !q.machineName.toLowerCase().includes(s)
      )
        return false;
      return true;
    });
  }, [quotes, search, selectedClientId, statusFilter]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">Dashboard</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Overview of machines by customer and processing status.
          </p>
        </div>
        <UploadDialog onUploaded={loadQuotes} />
      </div>
      <QuoteFilters
        search={search}
        onSearchChange={setSearch}
        statusFilter={statusFilter}
        onStatusFilterChange={setStatusFilter}
      />
      {loading ? (
        <div className="rounded-md border bg-white p-8 text-sm text-muted-foreground">
          Loading quotes...
        </div>
      ) : error ? (
        <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          Failed to load dashboard data: {error}
        </div>
      ) : (
        <MachineTable quotes={filtered} />
      )}
    </div>
  );
}
