"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, Plus } from "lucide-react";
import {
  fetchCorPrefill,
  fetchCorRevisions,
  fetchQuotes,
  saveCorState,
  type CorDocumentState,
  type CorRevisionSummary,
  type QuoteRow,
} from "@/lib/api";
import { uid } from "@/lib/doc-utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

type QuoteOption = { id: string; label: string };

function todayDateValue(): string {
  const now = new Date();
  const year = String(now.getFullYear());
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function getMachineNamesForQuote(rows: QuoteRow[], quoteId: number): string[] {
  if (!Number.isFinite(quoteId)) return [];
  const unique = new Set<string>();
  for (const row of rows) {
    if (row.quoteId !== quoteId) continue;
    const name = row.machineName.trim();
    if (!name) continue;
    unique.add(name);
  }
  return Array.from(unique.values());
}

function nextCorNumber(revisions: CorRevisionSummary[]): string {
  const numbers = revisions
    .map((entry) => Number(entry.corNo))
    .filter((value) => Number.isFinite(value) && value > 0);
  return numbers.length > 0 ? String(Math.max(...numbers) + 1) : "1";
}

function buildNewCorDraft(
  baseState: CorDocumentState,
  quoteId: number,
  machineNames: string[],
  revisions: CorRevisionSummary[]
): CorDocumentState {
  const corNo = nextCorNumber(revisions);
  const sourceLines =
    baseState.lineItems.length > 0
      ? baseState.lineItems
      : [{ id: "cor-line-1", qty: "", reqDescription: "", unitCost: "", selectedItems: "" }];

  return {
    ...baseState,
    quoteId,
    client: {
      ...baseState.client,
      machine: baseState.client.machine || machineNames[0] || "",
    },
    corNo,
    revisionDescription: "",
    corStatus: "",
    capmaticPM: "",
    initiatorOfChange: "contact_person",
    salesRep: "",
    contactPerson: baseState.contactPerson,
    impactDeliverables: "",
    impactDeliveryDate: "",
    paymentTerms: "",
    currency: "",
    approvalDate: todayDateValue(),
    comments: "",
    lineItems: sourceLines.map((line) => ({ ...line, id: uid("cor-line") })),
  };
}

export default function CorNewPageClient() {
  const router = useRouter();
  const [quotes, setQuotes] = useState<QuoteRow[]>([]);
  const [selectedQuoteId, setSelectedQuoteId] = useState("");
  const [revisions, setRevisions] = useState<CorRevisionSummary[]>([]);
  const [loadingQuotes, setLoadingQuotes] = useState(true);
  const [loadingRevisions, setLoadingRevisions] = useState(false);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoadingQuotes(true);
    setError(null);
    void fetchQuotes()
      .then((rows) => {
        if (!active) return;
        setQuotes(rows);
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
  }, []);

  const quoteOptions = useMemo<QuoteOption[]>(() => {
    const map = new Map<number, QuoteOption>();
    for (const row of quotes) {
      if (map.has(row.quoteId)) continue;
      map.set(row.quoteId, { id: String(row.quoteId), label: `${row.quoteRef} - ${row.clientName}` });
    }
    return Array.from(map.values());
  }, [quotes]);

  const selectedQuoteIdNumber = useMemo(() => {
    const parsed = Number(selectedQuoteId);
    return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
  }, [selectedQuoteId]);

  const machineNames = useMemo(() => {
    if (!selectedQuoteIdNumber) return [];
    return getMachineNamesForQuote(quotes, selectedQuoteIdNumber);
  }, [quotes, selectedQuoteIdNumber]);

  useEffect(() => {
    if (!selectedQuoteIdNumber) {
      setRevisions([]);
      return;
    }

    let active = true;
    setLoadingRevisions(true);
    setError(null);
    setStatus(null);

    void fetchCorRevisions(selectedQuoteIdNumber)
      .then((result) => {
        if (!active) return;
        setRevisions(result.revisions);
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Failed to load COR revisions.");
      })
      .finally(() => {
        if (active) setLoadingRevisions(false);
      });

    return () => {
      active = false;
    };
  }, [selectedQuoteIdNumber]);

  async function handleCreateNewCor() {
    if (!selectedQuoteIdNumber) return;
    setCreating(true);
    setError(null);
    setStatus(null);

    try {
      const quoteId = selectedQuoteIdNumber;
      const [prefill, revisionResult] = await Promise.all([
        fetchCorPrefill(quoteId),
        fetchCorRevisions(quoteId),
      ]);
      const newDraft = buildNewCorDraft(prefill, quoteId, machineNames, revisionResult.revisions);
      const saved = await saveCorState(quoteId, newDraft, { createNew: true });
      setStatus(`Created COR ${saved.corNo || saved.corDocumentId}. Redirecting to editor...`);
      router.push(`/cor/${saved.corDocumentId}?quote=${quoteId}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create COR draft.");
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-3">
          <Button variant="ghost" size="sm" asChild>
            <Link href="/cor-documents">
              <ArrowLeft className="mr-1 size-4" />
              Back
            </Link>
          </Button>
          <div>
            <h2 className="text-2xl font-semibold tracking-tight">New COR</h2>
            <p className="text-sm text-muted-foreground">
              Select a quote, review existing revisions, and create a new COR draft.
            </p>
          </div>
        </div>
      </div>

      {error ? <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div> : null}
      {status ? <div className="rounded-md border border-green-200 bg-green-50 p-3 text-sm text-green-700">{status}</div> : null}

      <Card>
        <CardHeader>
          <CardTitle>Step 1: Select Quote</CardTitle>
          <CardDescription>Choose the quote that this COR belongs to.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="max-w-xl space-y-1.5">
            <label className="text-sm font-medium">Quote</label>
            <Select value={selectedQuoteId} onValueChange={setSelectedQuoteId}>
              <SelectTrigger>
                <SelectValue placeholder={loadingQuotes ? "Loading quotes..." : "Select a quote"} />
              </SelectTrigger>
              <SelectContent>
                {quoteOptions.map((option) => (
                  <SelectItem key={option.id} value={option.id}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <CardTitle>Step 2: Existing Revisions</CardTitle>
              <CardDescription>
                Review existing COR revisions for the selected quote, then create a new one.
              </CardDescription>
            </div>
            <Button
              type="button"
              onClick={handleCreateNewCor}
              disabled={!selectedQuoteIdNumber || creating || loadingRevisions}
              className="bg-[#c00000] hover:bg-[#a00000]"
            >
              <Plus className="mr-2 h-4 w-4" />
              {creating ? "Creating..." : "New COR"}
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {!selectedQuoteIdNumber ? (
            <div className="rounded-md border bg-neutral-50 p-3 text-sm text-muted-foreground">
              Select a quote to view existing COR revisions.
            </div>
          ) : loadingRevisions ? (
            <div className="rounded-md border bg-neutral-50 p-3 text-sm text-muted-foreground">
              Loading revisions...
            </div>
          ) : (
            <div className="rounded-md border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>COR No.</TableHead>
                    <TableHead>Description</TableHead>
                    <TableHead>Updated</TableHead>
                    <TableHead className="text-right">Action</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {revisions.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={4} className="h-16 text-center text-muted-foreground">
                        No saved COR revisions yet for this quote.
                      </TableCell>
                    </TableRow>
                  ) : (
                    revisions.map((entry) => {
                      const corLabel = entry.corNo.trim() || String(entry.corDocumentId);
                      return (
                        <TableRow key={entry.corDocumentId}>
                          <TableCell className="font-semibold">COR {corLabel}</TableCell>
                          <TableCell>{entry.description.trim() || "-"}</TableCell>
                          <TableCell>{entry.modifiedDate ?? entry.createdDate ?? "-"}</TableCell>
                          <TableCell className="text-right">
                            <Button variant="ghost" size="sm" asChild>
                              <Link href={`/cor/${entry.corDocumentId}?quote=${selectedQuoteIdNumber}`}>Edit</Link>
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
