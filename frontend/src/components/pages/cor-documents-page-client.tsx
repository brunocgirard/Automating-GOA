"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Download, Plus, Save, Trash2 } from "lucide-react";
import {
  fetchCorPrefill,
  fetchQuotes,
  generateCorDoc,
  loadCorState,
  saveCorState,
  type CorDocumentState,
  type CorLineItem,
  type QuoteRow,
} from "@/lib/api";
import { useClientFilter } from "@/components/layout/client-filter-context";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

type QuoteOption = { id: string; label: string };

function uid(prefix: string): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return `${prefix}-${crypto.randomUUID()}`;
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`;
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export default function CorDocumentsPageClient() {
  const { selectedClientId } = useClientFilter();
  const [quotes, setQuotes] = useState<QuoteRow[]>([]);
  const [selectedQuoteId, setSelectedQuoteId] = useState("");
  const [state, setState] = useState<CorDocumentState | null>(null);
  const [loadingQuotes, setLoadingQuotes] = useState(true);
  const [loadingState, setLoadingState] = useState(false);
  const [saving, setSaving] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const latestQuote = useRef("");

  useEffect(() => {
    let active = true;
    setLoadingQuotes(true);
    setError(null);
    void fetchQuotes(selectedClientId ?? undefined)
      .then((rows) => {
        if (active) setQuotes(rows);
      })
      .catch((err) => {
        if (active) setError(err instanceof Error ? err.message : "Failed to load quotes.");
      })
      .finally(() => {
        if (active) setLoadingQuotes(false);
      });
    return () => {
      active = false;
    };
  }, [selectedClientId]);

  const quoteOptions = useMemo<QuoteOption[]>(() => {
    const map = new Map<number, QuoteOption>();
    for (const row of quotes) {
      if (!map.has(row.quoteId)) {
        map.set(row.quoteId, { id: String(row.quoteId), label: `${row.quoteRef} - ${row.clientName}` });
      }
    }
    return Array.from(map.values());
  }, [quotes]);

  async function selectQuote(rawId: string) {
    if (!rawId) return;
    const quoteId = Number(rawId);
    if (!Number.isFinite(quoteId)) return;
    latestQuote.current = rawId;
    setSelectedQuoteId(rawId);
    setLoadingState(true);
    setError(null);
    setStatus(null);

    try {
      const loaded = await loadCorState(quoteId);
      if (latestQuote.current !== rawId) return;
      if (loaded) {
        setState(loaded.corData);
        setStatus(`Loaded draft ${loaded.modifiedDate ?? loaded.createdDate ?? ""}.`);
      } else {
        const prefill = await fetchCorPrefill(quoteId);
        if (latestQuote.current !== rawId) return;
        setState(prefill);
      }
    } catch (err) {
      if (latestQuote.current !== rawId) return;
      setError(err instanceof Error ? err.message : "Failed to load COR data.");
      setState(null);
    } finally {
      if (latestQuote.current === rawId) setLoadingState(false);
    }
  }

  function patchState(fn: (prev: CorDocumentState) => CorDocumentState) {
    setState((prev) => (prev ? fn(prev) : prev));
  }

  function setClientField(key: keyof CorDocumentState["client"], value: string) {
    patchState((prev) => ({ ...prev, client: { ...prev.client, [key]: value } }));
  }

  function setLineItem(lineId: string, updater: (line: CorLineItem) => CorLineItem) {
    patchState((prev) => ({
      ...prev,
      lineItems: prev.lineItems.map((line) => (line.id === lineId ? updater(line) : line)),
    }));
  }

  function addLineItem() {
    patchState((prev) => ({
      ...prev,
      lineItems: [
        ...prev.lineItems,
        { id: uid("cor-line"), qty: "", reqDescription: "", unitCost: "", selectedItems: "" },
      ],
    }));
  }

  function removeLineItem(lineId: string) {
    patchState((prev) => ({
      ...prev,
      lineItems:
        prev.lineItems.length > 1
          ? prev.lineItems.filter((line) => line.id !== lineId)
          : [{ id: uid("cor-line"), qty: "", reqDescription: "", unitCost: "", selectedItems: "" }],
    }));
  }

  function saveDraft() {
    if (!state) return;
    setSaving(true);
    setError(null);
    setStatus(null);
    void saveCorState(state.quoteId, state)
      .then((saved) => {
        setState(saved.corData);
        setStatus(`Draft saved at ${saved.savedAt}.`);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to save COR draft."))
      .finally(() => setSaving(false));
  }

  function downloadCor() {
    if (!state) return;
    setDownloading(true);
    setError(null);
    setStatus(null);
    void generateCorDoc(state.quoteId, { corData: state })
      .then((result) => {
        downloadBlob(result.blob, result.filename);
        setStatus(`Generated ${result.filename}.`);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to generate COR document."))
      .finally(() => setDownloading(false));
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">COR Documents</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Build Change Order Request documents using quote client info and editable line items.
        </p>
      </div>

      {error ? <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div> : null}
      {status ? <div className="rounded-md border border-green-200 bg-green-50 p-3 text-sm text-green-700">{status}</div> : null}

      <Card>
        <CardHeader>
          <CardTitle>Select Quote</CardTitle>
          <CardDescription>Load prefilled COR data or continue from a saved draft.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-sm font-medium">Quote</label>
            <Select value={selectedQuoteId} onValueChange={(value) => void selectQuote(value)}>
              <SelectTrigger>
                <SelectValue placeholder={loadingQuotes ? "Loading quotes..." : "Select a quote"} />
              </SelectTrigger>
              <SelectContent>
                {quoteOptions.map((option) => (
                  <SelectItem key={option.id} value={option.id}>{option.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          {loadingState ? <div className="rounded-md border bg-neutral-50 p-3 text-sm text-muted-foreground">Loading COR data...</div> : null}
          {!loadingState && !state ? <div className="rounded-md border bg-neutral-50 p-3 text-sm text-muted-foreground">Select a quote to start.</div> : null}
        </CardContent>
      </Card>

      {state ? (
        <Card>
          <CardHeader>
            <CardTitle>COR Details</CardTitle>
            <CardDescription>Fill justification and line items, then generate the COR DOCX.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
              <div className="space-y-1"><label className="text-sm font-medium">Company</label><Input value={state.client.company} onChange={(e) => setClientField("company", e.target.value)} /></div>
              <div className="space-y-1"><label className="text-sm font-medium">OX</label><Input value={state.client.ox} onChange={(e) => setClientField("ox", e.target.value)} /></div>
              <div className="space-y-1"><label className="text-sm font-medium">AX</label><Input value={state.client.ax} onChange={(e) => setClientField("ax", e.target.value)} /></div>
              <div className="space-y-1"><label className="text-sm font-medium">Machine</label><Input value={state.client.machine} onChange={(e) => setClientField("machine", e.target.value)} /></div>
              <div className="space-y-1"><label className="text-sm font-medium">Customer PO</label><Input value={state.client.customerPO} onChange={(e) => setClientField("customerPO", e.target.value)} /></div>
              <div className="space-y-1"><label className="text-sm font-medium">Order Date</label><Input value={state.client.orderDate} onChange={(e) => setClientField("orderDate", e.target.value)} /></div>
              <div className="space-y-1"><label className="text-sm font-medium">COR No.</label><Input value={state.corNo} onChange={(e) => patchState((prev) => ({ ...prev, corNo: e.target.value }))} /></div>
            </div>

            <div className="space-y-1">
              <label className="text-sm font-medium">Justification For Change</label>
              <textarea
                className="min-h-28 w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm outline-none"
                value={state.justificationForChange}
                onChange={(e) => patchState((prev) => ({ ...prev, justificationForChange: e.target.value }))}
                placeholder="Enter change justification..."
              />
            </div>

            <div className="space-y-2 rounded-md border p-3">
              <div className="flex items-center justify-between">
                <p className="text-sm font-semibold">Line Items</p>
                <Button type="button" size="sm" variant="outline" onClick={addLineItem}>
                  <Plus className="mr-1 h-3.5 w-3.5" />Add Line
                </Button>
              </div>
              <div className="grid grid-cols-12 gap-2 text-xs font-medium text-neutral-500">
                <div className="col-span-1">Qty</div>
                <div className="col-span-5">ReqDescription</div>
                <div className="col-span-2">Unit Cost</div>
                <div className="col-span-3">Selected Items</div>
                <div className="col-span-1"> </div>
              </div>
              {state.lineItems.map((line) => (
                <div key={line.id} className="grid grid-cols-12 gap-2">
                  <Input className="col-span-1" value={line.qty} onChange={(e) => setLineItem(line.id, (prev) => ({ ...prev, qty: e.target.value }))} />
                  <Input className="col-span-5" value={line.reqDescription} onChange={(e) => setLineItem(line.id, (prev) => ({ ...prev, reqDescription: e.target.value }))} />
                  <Input className="col-span-2" value={line.unitCost} onChange={(e) => setLineItem(line.id, (prev) => ({ ...prev, unitCost: e.target.value }))} />
                  <Input className="col-span-3" value={line.selectedItems} onChange={(e) => setLineItem(line.id, (prev) => ({ ...prev, selectedItems: e.target.value }))} />
                  <Button type="button" size="icon" variant="outline" className="col-span-1" onClick={() => removeLineItem(line.id)}>
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              ))}
            </div>

            <div className="flex flex-wrap gap-2">
              <Button type="button" variant="secondary" disabled={saving} onClick={saveDraft}>
                <Save className="mr-2 h-4 w-4" />{saving ? "Saving..." : "Save Draft"}
              </Button>
              <Button type="button" disabled={downloading} onClick={downloadCor}>
                <Download className="mr-2 h-4 w-4" />{downloading ? "Generating..." : "Download COR"}
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
