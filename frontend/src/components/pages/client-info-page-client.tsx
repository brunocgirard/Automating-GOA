"use client";

import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  fetchQuotes,
  getQuoteDetail,
  updateQuoteClientInfo,
  type QuoteDetail,
  type QuoteRow,
} from "@/lib/api";
import { useClientFilter } from "@/components/layout/client-filter-context";
import { QuoteClientInfo } from "@/components/quotes/quote-details";
import { ItemsTable } from "@/components/quotes/items-table";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Save } from "lucide-react";

interface QuoteSummary {
  quoteId: number;
  quoteRef: string;
  clientId: string;
  clientName: string;
  machineName: string;
  status: QuoteRow["status"];
  date: string;
}

interface ClientOption {
  id: string;
  name: string;
  quoteCount: number;
}

function buildQuoteSummaries(rows: QuoteRow[]): QuoteSummary[] {
  const deduped = new Map<number, QuoteSummary>();

  for (const row of rows) {
    if (deduped.has(row.quoteId)) continue;
    deduped.set(row.quoteId, {
      quoteId: row.quoteId,
      quoteRef: row.quoteRef,
      clientId: row.clientId,
      clientName: row.clientName,
      machineName: row.machineName,
      status: row.status,
      date: row.date,
    });
  }

  return Array.from(deduped.values());
}

function buildClientOptions(quotes: QuoteSummary[]): ClientOption[] {
  const grouped = new Map<string, ClientOption>();

  for (const quote of quotes) {
    const existing = grouped.get(quote.clientId);
    if (!existing) {
      grouped.set(quote.clientId, {
        id: quote.clientId,
        name: quote.clientName,
        quoteCount: 1,
      });
    } else {
      existing.quoteCount += 1;
    }
  }

  return Array.from(grouped.values()).sort((a, b) => a.name.localeCompare(b.name));
}

function QuoteEditor({ quoteId }: { quoteId: number }) {
  const [detail, setDetail] = useState<QuoteDetail | null>(null);
  const [clientInfo, setClientInfo] = useState<QuoteDetail["clientInfo"] | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    void getQuoteDetail(quoteId)
      .then((response) => {
        if (!active) return;
        setDetail(response);
        setClientInfo(response.clientInfo);
        setError(null);
        setStatusMessage(null);
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Failed to load quote detail.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [quoteId]);

  function handleClientChange(key: keyof QuoteDetail["clientInfo"], value: string) {
    setClientInfo((prev) => (prev ? { ...prev, [key]: value } : prev));
  }

  async function handleSave() {
    if (!detail || !clientInfo) return;

    setSaving(true);
    setError(null);
    setStatusMessage(null);
    try {
      await updateQuoteClientInfo(detail.quoteId, clientInfo);
      setStatusMessage("Changes saved.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save changes.");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="rounded-md border bg-white p-8 text-sm text-muted-foreground">
        Loading quote...
      </div>
    );
  }

  if (error && !detail) {
    return (
      <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
        Failed to load quote: {error}
      </div>
    );
  }

  if (!detail || !clientInfo) {
    return (
      <div className="rounded-md border bg-white p-8 text-sm text-muted-foreground">
        Quote not found.
      </div>
    );
  }

  const statusConfig = {
    draft: { label: "Draft", className: "bg-neutral-200 text-neutral-700" },
    processed: { label: "Processed", className: "bg-yellow-100 text-yellow-800" },
    ready: { label: "Ready", className: "bg-green-100 text-green-800" },
  } as const;
  const cfg = statusConfig[detail.status];

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-2xl font-semibold tracking-tight">{detail.quoteRef}</h2>
            <Badge className={cfg.className} variant="secondary">
              {cfg.label}
            </Badge>
          </div>
          <p className="text-sm text-muted-foreground">{detail.machineName}</p>
        </div>
        <Button onClick={handleSave} disabled={saving} className="w-full sm:w-auto">
          <Save className="mr-1 size-4" />
          {saving ? "Saving..." : "Save"}
        </Button>
      </div>

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          Save failed: {error}
        </div>
      )}
      {statusMessage && (
        <div className="rounded-md border border-green-200 bg-green-50 p-3 text-sm text-green-700">
          {statusMessage}
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Client Information</CardTitle>
        </CardHeader>
        <CardContent>
          <QuoteClientInfo clientInfo={clientInfo} onChange={handleClientChange} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Line Items</CardTitle>
        </CardHeader>
        <CardContent>
          <ItemsTable items={detail.lineItems} />
        </CardContent>
      </Card>
    </div>
  );
}

export default function ClientInfoPageClient() {
  const { selectedClientId, setSelectedClientId } = useClientFilter();
  const searchParams = useSearchParams();
  const [quotes, setQuotes] = useState<QuoteRow[]>([]);
  const [selectedQuoteId, setSelectedQuoteId] = useState<string>("");
  const [loadingQuotes, setLoadingQuotes] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const quoteIdFromQuery = useMemo(() => {
    const raw = searchParams.get("quote");
    const parsed = Number(raw);
    return Number.isFinite(parsed) ? parsed : null;
  }, [searchParams]);

  useEffect(() => {
    let active = true;

    void fetchQuotes()
      .then((rows) => {
        if (!active) return;
        setQuotes(rows);
        setError(null);

        const summaries = buildQuoteSummaries(rows);
        if (summaries.length === 0) {
          return;
        }

        if (quoteIdFromQuery != null) {
          const requested = summaries.find((quote) => quote.quoteId === quoteIdFromQuery);
          if (requested) {
            setSelectedQuoteId(String(requested.quoteId));
            setSelectedClientId(requested.clientId);
            return;
          }
        }

        const preferred =
          (selectedClientId
            ? summaries.find((quote) => quote.clientId === selectedClientId)
            : undefined) ?? summaries[0];

        setSelectedQuoteId(String(preferred.quoteId));
        if (!selectedClientId) {
          setSelectedClientId(preferred.clientId);
        }
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Failed to load quotes.");
      })
      .finally(() => {
        if (active) setLoadingQuotes(false);
      });

    return () => {
      active = false;
    };
  }, [quoteIdFromQuery, selectedClientId, setSelectedClientId]);

  const quoteOptions = useMemo(() => buildQuoteSummaries(quotes), [quotes]);
  const clientOptions = useMemo(() => buildClientOptions(quoteOptions), [quoteOptions]);
  const visibleQuoteOptions = useMemo(() => {
    if (!selectedClientId) return quoteOptions;
    return quoteOptions.filter((quote) => quote.clientId === selectedClientId);
  }, [quoteOptions, selectedClientId]);

  const activeQuote =
    visibleQuoteOptions.find((quote) => String(quote.quoteId) === selectedQuoteId) ??
    visibleQuoteOptions[0] ??
    null;

  function handleClientSelection(clientId: string) {
    setSelectedClientId(clientId);
    const firstQuoteForClient = quoteOptions.find((quote) => quote.clientId === clientId);
    if (firstQuoteForClient) {
      setSelectedQuoteId(String(firstQuoteForClient.quoteId));
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">Client Info</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Select a client and quote to edit customer details and review line items.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Selection</CardTitle>
        </CardHeader>
        <CardContent>
          {loadingQuotes ? (
            <div className="rounded-md border bg-white p-4 text-sm text-muted-foreground">
              Loading clients...
            </div>
          ) : error ? (
            <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
              Failed to load clients: {error}
            </div>
          ) : quoteOptions.length === 0 ? (
            <div className="rounded-md border bg-white p-4 text-sm text-muted-foreground">
              No quotes found.
            </div>
          ) : (
            <div className="grid gap-4 md:grid-cols-2">
              <div className="space-y-2">
                <label className="text-sm font-medium">Client</label>
                <Select value={selectedClientId ?? undefined} onValueChange={handleClientSelection}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select a client..." />
                  </SelectTrigger>
                  <SelectContent>
                    {clientOptions.map((client) => (
                      <SelectItem key={client.id} value={client.id}>
                        {client.name} ({client.quoteCount})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Quote</label>
                <Select
                  value={activeQuote ? String(activeQuote.quoteId) : undefined}
                  onValueChange={setSelectedQuoteId}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select a quote..." />
                  </SelectTrigger>
                  <SelectContent>
                    {visibleQuoteOptions.map((quote) => (
                      <SelectItem key={quote.quoteId} value={String(quote.quoteId)}>
                        {quote.quoteRef} - {quote.machineName}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {activeQuote ? <QuoteEditor key={activeQuote.quoteId} quoteId={activeQuote.quoteId} /> : null}
    </div>
  );
}
