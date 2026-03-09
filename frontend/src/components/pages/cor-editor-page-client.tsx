"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowLeft, Download, Plus, Save, Trash2 } from "lucide-react";
import {
  fetchQuotes,
  generateCorDoc,
  loadCorState,
  saveCorState,
  type CorDocumentState,
  type CorLineItem,
  type QuoteRow,
} from "@/lib/api";
import { uid } from "@/lib/doc-utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

interface CorEditorPageClientProps {
  corDocumentId: string;
}

function parsePositiveId(raw: string | null | undefined): number | null {
  const parsed = Number(raw);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
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

function todayDateValue(): string {
  const now = new Date();
  const year = String(now.getFullYear());
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function emptyCorLine(): CorLineItem {
  return { id: uid("cor-line"), qty: "", reqDescription: "", unitCost: "", selectedItems: "" };
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

const COR_STATUS_OPTIONS = [
  "Approved",
  "Declined",
  "For your files",
  "Not Submitted",
  "See revision",
  "Waiting for approval",
];

const CAPMATIC_PM_OPTIONS = [
  "Mike Rossi",
  "Paul Clark",
  "Robert D'addario",
  "Bruno C. Girard",
];

const INITIATOR_OF_CHANGE_OPTIONS = [
  { value: "contact_person", label: "Contact Person (company)" },
  { value: "capmatic_pm", label: "Capmatic PM" },
];

const SALES_REP_OPTIONS = [
  "Christian Normandin",
  "Declan Coleman",
  "Jairo Martinez",
  "Nick Perugini",
  "Wendy Ocean",
  "Michel Mosseau",
];

const PAYMENT_TERMS_OPTIONS = [
  "50% w/PO, 50% Prior to Ship",
  "100% w/PO",
  "100% Prior to Ship",
  "No Charge",
];

const CURRENCY_OPTIONS = ["CAD", "EUR", "USD"];
const YES_NO_OPTIONS = ["Yes", "No"];

export default function CorEditorPageClient({ corDocumentId }: CorEditorPageClientProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const corIdFromRoute = useMemo(() => parsePositiveId(corDocumentId), [corDocumentId]);
  const quoteIdFromQuery = useMemo(() => parsePositiveId(searchParams.get("quote")), [searchParams]);
  const hasValidRouteParams = corIdFromRoute != null && quoteIdFromQuery != null;

  const [quotes, setQuotes] = useState<QuoteRow[]>([]);
  const [state, setState] = useState<CorDocumentState | null>(null);
  const [loadedCorDocumentId, setLoadedCorDocumentId] = useState<number | null>(null);
  const [loadingQuotes, setLoadingQuotes] = useState(true);
  const [loadingState, setLoadingState] = useState(hasValidRouteParams);
  const [saving, setSaving] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    void fetchQuotes()
      .then((rows) => {
        if (!active) return;
        setQuotes(rows);
      })
      .catch(() => {
        // machine list enrichment is optional for editor loading
      })
      .finally(() => {
        if (active) setLoadingQuotes(false);
      });

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (corIdFromRoute == null || quoteIdFromQuery == null) return;

    let active = true;
    void loadCorState(quoteIdFromQuery, corIdFromRoute)
      .then((loaded) => {
        if (!active) return;
        if (!loaded) {
          throw new Error("Selected COR record was not found.");
        }
        setLoadedCorDocumentId(loaded.corDocumentId);
        setState({
          ...loaded.corData,
          approvalDate: todayDateValue(),
          lineItems: loaded.corData.lineItems.length > 0 ? loaded.corData.lineItems : [emptyCorLine()],
        });
        setStatus(`Loaded COR ${loaded.corNo || loaded.corDocumentId}.`);
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Failed to load COR data.");
        setState(null);
      })
      .finally(() => {
        if (active) setLoadingState(false);
      });

    return () => {
      active = false;
    };
  }, [corIdFromRoute, quoteIdFromQuery]);

  const machineOptions = useMemo(() => {
    const quoteId = state?.quoteId ?? quoteIdFromQuery ?? NaN;
    return getMachineNamesForQuote(quotes, quoteId);
  }, [quotes, quoteIdFromQuery, state?.quoteId]);

  const machineSelectOptions = useMemo<string[]>(() => {
    const options = [...machineOptions];
    const selected = state?.client.machine?.trim() ?? "";
    if (selected && !options.includes(selected)) {
      options.unshift(selected);
    }
    return options;
  }, [machineOptions, state?.client.machine]);

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
      lineItems: [...prev.lineItems, emptyCorLine()],
    }));
  }

  function removeLineItem(lineId: string) {
    patchState((prev) => ({
      ...prev,
      lineItems:
        prev.lineItems.length > 1
          ? prev.lineItems.filter((line) => line.id !== lineId)
          : [emptyCorLine()],
    }));
  }

  function saveDraft() {
    if (!state) return;
    const targetCorDocumentId = loadedCorDocumentId ?? corIdFromRoute;
    if (!targetCorDocumentId) {
      setError("Invalid COR document id.");
      return;
    }

    setSaving(true);
    setError(null);
    setStatus(null);

    void saveCorState(state.quoteId, state, { corDocumentId: targetCorDocumentId, createNew: false })
      .then((saved) => {
        setState(saved.corData);
        setLoadedCorDocumentId(saved.corDocumentId);
        setStatus(`Updated COR ${saved.corNo || saved.corDocumentId} at ${saved.savedAt}.`);
        if (saved.corDocumentId !== targetCorDocumentId) {
          router.replace(`/cor/${saved.corDocumentId}?quote=${saved.quoteId}`);
        }
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to save COR draft."))
      .finally(() => setSaving(false));
  }

  function downloadCor() {
    if (!state) return;
    const targetCorDocumentId = loadedCorDocumentId ?? corIdFromRoute;
    if (!targetCorDocumentId) {
      setError("Invalid COR document id.");
      return;
    }

    setDownloading(true);
    setError(null);
    setStatus(null);

    void generateCorDoc(state.quoteId, { corData: state, corDocumentId: targetCorDocumentId })
      .then((result) => {
        downloadBlob(result.blob, result.filename);
        setStatus(`Generated ${result.filename}.`);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to generate COR document."))
      .finally(() => setDownloading(false));
  }

  if (!corIdFromRoute || !quoteIdFromQuery) {
    return (
      <div className="space-y-4">
        <Button variant="ghost" size="sm" asChild>
          <Link href="/cor-documents">
            <ArrowLeft className="mr-1 size-4" />
            Back to COR Dashboard
          </Link>
        </Button>
        <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          Missing or invalid route parameters. Open this page from the COR dashboard or COR new flow.
        </div>
      </div>
    );
  }

  if (loadingState) {
    return (
      <div className="space-y-4">
        <Button variant="ghost" size="sm" asChild>
          <Link href="/cor-documents">
            <ArrowLeft className="mr-1 size-4" />
            Back to COR Dashboard
          </Link>
        </Button>
        <div className="rounded-md border bg-white p-8 text-sm text-muted-foreground">Loading COR form...</div>
      </div>
    );
  }

  if (!state) {
    return (
      <div className="space-y-4">
        <Button variant="ghost" size="sm" asChild>
          <Link href="/cor-documents">
            <ArrowLeft className="mr-1 size-4" />
            Back to COR Dashboard
          </Link>
        </Button>
        <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error || "COR record not found."}
        </div>
      </div>
    );
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
            <h2 className="text-2xl font-semibold tracking-tight">COR Editor</h2>
            <p className="text-sm text-muted-foreground">
              Quote #{state.quoteId} - COR {state.corNo.trim() || loadedCorDocumentId || corIdFromRoute}
              {loadingQuotes ? " (loading quote metadata...)" : ""}
            </p>
          </div>
        </div>
      </div>

      {error ? <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div> : null}
      {status ? <div className="rounded-md border border-green-200 bg-green-50 p-3 text-sm text-green-700">{status}</div> : null}

      <Card>
        <CardHeader>
          <CardTitle>COR Details</CardTitle>
          <CardDescription>
            Edit the COR form fields, save draft updates, and generate the final COR document.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
            <div className="space-y-1">
              <label className="text-sm font-medium">Description</label>
              <Input
                value={state.revisionDescription}
                onChange={(e) => patchState((prev) => ({ ...prev, revisionDescription: e.target.value }))}
                placeholder="Short note (e.g. Rev B - client requested pump update)"
              />
            </div>
          </div>
          <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
            <div className="space-y-1">
              <label className="text-sm font-medium">COR Status</label>
              <Select
                value={state.corStatus || "__none__"}
                onValueChange={(value) => patchState((prev) => ({ ...prev, corStatus: value === "__none__" ? "" : value }))}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select COR status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none__">Select option</SelectItem>
                  {COR_STATUS_OPTIONS.map((option) => (
                    <SelectItem key={option} value={option}>
                      {option}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium">Capmatic PM</label>
              <Select
                value={state.capmaticPM || "__none__"}
                onValueChange={(value) => patchState((prev) => ({ ...prev, capmaticPM: value === "__none__" ? "" : value }))}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select Capmatic PM" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none__">Select option</SelectItem>
                  {CAPMATIC_PM_OPTIONS.map((option) => (
                    <SelectItem key={option} value={option}>
                      {option}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium">Initiator Of Change</label>
              <Select
                value={state.initiatorOfChange || "contact_person"}
                onValueChange={(value) => patchState((prev) => ({ ...prev, initiatorOfChange: value }))}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select initiator source" />
                </SelectTrigger>
                <SelectContent>
                  {INITIATOR_OF_CHANGE_OPTIONS.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium">Sales Rep</label>
              <Select
                value={state.salesRep || "__none__"}
                onValueChange={(value) => patchState((prev) => ({ ...prev, salesRep: value === "__none__" ? "" : value }))}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select Sales Rep" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none__">Select option</SelectItem>
                  {SALES_REP_OPTIONS.map((option) => (
                    <SelectItem key={option} value={option}>
                      {option}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium">Payment Terms</label>
              <Select
                value={state.paymentTerms || "__none__"}
                onValueChange={(value) => patchState((prev) => ({ ...prev, paymentTerms: value === "__none__" ? "" : value }))}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select Payment Terms" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none__">Select option</SelectItem>
                  {PAYMENT_TERMS_OPTIONS.map((option) => (
                    <SelectItem key={option} value={option}>
                      {option}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium">Currency</label>
              <Select
                value={state.currency || "__none__"}
                onValueChange={(value) => patchState((prev) => ({ ...prev, currency: value === "__none__" ? "" : value }))}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select Currency" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none__">Select option</SelectItem>
                  {CURRENCY_OPTIONS.map((option) => (
                    <SelectItem key={option} value={option}>
                      {option}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium">Impact Of Change To Deliverables</label>
              <Select
                value={state.impactDeliverables || "__none__"}
                onValueChange={(value) =>
                  patchState((prev) => ({ ...prev, impactDeliverables: value === "__none__" ? "" : value }))
                }
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select Yes or No" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none__">Select option</SelectItem>
                  {YES_NO_OPTIONS.map((option) => (
                    <SelectItem key={option} value={option}>
                      {option}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium">Impact On Delivery Date</label>
              <Select
                value={state.impactDeliveryDate || "__none__"}
                onValueChange={(value) =>
                  patchState((prev) => ({ ...prev, impactDeliveryDate: value === "__none__" ? "" : value }))
                }
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select Yes or No" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none__">Select option</SelectItem>
                  {YES_NO_OPTIONS.map((option) => (
                    <SelectItem key={option} value={option}>
                      {option}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium">Approval Date (Auto: Today)</label>
              <Input type="date" value={todayDateValue()} readOnly />
            </div>
          </div>

          <div className="space-y-1">
            <label className="text-sm font-medium">Comments</label>
            <Input
              value={state.comments}
              onChange={(e) => patchState((prev) => ({ ...prev, comments: e.target.value }))}
              placeholder="Enter comments..."
            />
          </div>

          <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
            <div className="space-y-1">
              <label className="text-sm font-medium">Customer (Company Name) (Client Info)</label>
              <Input value={state.client.company} readOnly />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium">OX (Client Info)</label>
              <Input value={state.client.ox} readOnly />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium">AX (Client Info)</label>
              <Input value={state.client.ax} readOnly />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium">Machine</label>
              {machineSelectOptions.length > 0 ? (
                <Select
                  value={state.client.machine || "__none__"}
                  onValueChange={(value) => setClientField("machine", value === "__none__" ? "" : value)}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select machine" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__none__">Select machine</SelectItem>
                    {machineSelectOptions.map((machineName) => (
                      <SelectItem key={machineName} value={machineName}>
                        {machineName}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              ) : (
                <Input value={state.client.machine} readOnly />
              )}
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium">Customer PO (Client Info)</label>
              <Input value={state.client.customerPO} readOnly />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium">Order Date (Client Info)</label>
              <Input value={state.client.orderDate} readOnly />
            </div>
            <div className="space-y-1">
              <label className="text-sm font-medium">COR No.</label>
              <Input value={state.corNo} onChange={(e) => patchState((prev) => ({ ...prev, corNo: e.target.value }))} />
            </div>
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
                <Input
                  className="col-span-1"
                  value={line.qty}
                  onChange={(e) => setLineItem(line.id, (prev) => ({ ...prev, qty: e.target.value }))}
                />
                <Input
                  className="col-span-5"
                  value={line.reqDescription}
                  onChange={(e) => setLineItem(line.id, (prev) => ({ ...prev, reqDescription: e.target.value }))}
                />
                <Input
                  className="col-span-2"
                  value={line.unitCost}
                  onChange={(e) => setLineItem(line.id, (prev) => ({ ...prev, unitCost: e.target.value }))}
                />
                <Input
                  className="col-span-3"
                  value={line.selectedItems}
                  onChange={(e) => setLineItem(line.id, (prev) => ({ ...prev, selectedItems: e.target.value }))}
                />
                <Button type="button" size="icon" variant="outline" className="col-span-1" onClick={() => removeLineItem(line.id)}>
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            ))}
          </div>

          <div className="flex flex-wrap gap-2">
            <Button type="button" variant="secondary" disabled={saving} onClick={saveDraft}>
              <Save className="mr-2 h-4 w-4" />
              {saving ? "Saving..." : "Save Draft"}
            </Button>
            <Button type="button" disabled={downloading} onClick={downloadCor}>
              <Download className="mr-2 h-4 w-4" />
              {downloading ? "Generating..." : "Download COR"}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
