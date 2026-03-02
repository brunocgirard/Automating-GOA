"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Download, Plus, Save, Trash2 } from "lucide-react";
import {
  fetchCorPrefill,
  fetchCorRevisions,
  fetchQuotes,
  generateCorDoc,
  loadCorState,
  saveCorState,
  type CorDocumentState,
  type CorLineItem,
  type CorRevisionSummary,
  type QuoteRow,
} from "@/lib/api";
import { uid } from "@/lib/doc-utils";
import { useClientFilter } from "@/components/layout/client-filter-context";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

type QuoteOption = { id: string; label: string };

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

function parseCorDocumentId(raw: string): number | null {
  const parsed = Number(raw);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

function nextCorNumber(revisions: CorRevisionSummary[]): string {
  const numbers = revisions
    .map((entry) => Number(entry.corNo))
    .filter((value) => Number.isFinite(value) && value > 0);
  return numbers.length > 0 ? String(Math.max(...numbers) + 1) : "1";
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
  const searchParams = useSearchParams();
  const [quotes, setQuotes] = useState<QuoteRow[]>([]);
  const [selectedQuoteId, setSelectedQuoteId] = useState("");
  const [revisions, setRevisions] = useState<CorRevisionSummary[]>([]);
  const [selectedCorDocumentId, setSelectedCorDocumentId] = useState("");
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

  const quoteIdFromQuery = useMemo(() => {
    const raw = searchParams.get("quote");
    const parsed = Number(raw);
    return Number.isFinite(parsed) ? String(parsed) : null;
  }, [searchParams]);

  const machineOptions = useMemo<string[]>(() => {
    const quoteId = Number(selectedQuoteId);
    return getMachineNamesForQuote(quotes, quoteId);
  }, [quotes, selectedQuoteId]);

  const machineSelectOptions = useMemo<string[]>(() => {
    const options = [...machineOptions];
    const selected = state?.client.machine?.trim() ?? "";
    if (selected && !options.includes(selected)) {
      options.unshift(selected);
    }
    return options;
  }, [machineOptions, state?.client.machine]);

  const refreshRevisions = useCallback(async (quoteId: number): Promise<CorRevisionSummary[]> => {
    const list = await fetchCorRevisions(quoteId);
    if (latestQuote.current !== String(quoteId)) return [];
    setRevisions(list.revisions);
    return list.revisions;
  }, []);

  const selectQuote = useCallback(async (rawId: string) => {
    if (!rawId) return;
    const quoteId = Number(rawId);
    if (!Number.isFinite(quoteId)) return;
    latestQuote.current = rawId;
    setSelectedQuoteId(rawId);
    setSelectedCorDocumentId("");
    setRevisions([]);
    setLoadingState(true);
    setError(null);
    setStatus(null);

    try {
      const machineNames = getMachineNamesForQuote(quotes, quoteId);
      const [revisionList, loaded] = await Promise.all([
        refreshRevisions(quoteId),
        loadCorState(quoteId),
      ]);
      if (latestQuote.current !== rawId) return;
      if (loaded) {
        const selectedMachine = loaded.corData.client.machine || machineNames[0] || "";
        setState({
          ...loaded.corData,
          approvalDate: todayDateValue(),
          client: {
            ...loaded.corData.client,
            machine: selectedMachine,
          },
        });
        setSelectedCorDocumentId(String(loaded.corDocumentId));
        setStatus(`Loaded draft ${loaded.modifiedDate ?? loaded.createdDate ?? ""}.`);
      } else {
        const prefill = await fetchCorPrefill(quoteId);
        if (latestQuote.current !== rawId) return;
        prefill.corNo = nextCorNumber(revisionList);
        prefill.revisionDescription = "";
        prefill.approvalDate = todayDateValue();
        prefill.client.machine = prefill.client.machine || machineNames[0] || "";
        setState(prefill);
        setSelectedCorDocumentId("");
      }
    } catch (err) {
      if (latestQuote.current !== rawId) return;
      setError(err instanceof Error ? err.message : "Failed to load COR data.");
      setState(null);
      setRevisions([]);
      setSelectedCorDocumentId("");
    } finally {
      if (latestQuote.current === rawId) setLoadingState(false);
    }
  }, [quotes, refreshRevisions]);

  useEffect(() => {
    if (!quoteIdFromQuery || selectedQuoteId || loadingQuotes) return;
    if (!quoteOptions.some((option) => option.id === quoteIdFromQuery)) return;
    void selectQuote(quoteIdFromQuery);
  }, [loadingQuotes, quoteIdFromQuery, quoteOptions, selectedQuoteId, selectQuote]);

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
        emptyCorLine(),
      ],
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

  async function createNewCorDraft() {
    if (!selectedQuoteId) return;
    const quoteId = Number(selectedQuoteId);
    if (!Number.isFinite(quoteId)) return;
    setLoadingState(true);
    setError(null);
    setStatus(null);
    try {
      let baseState = state;
      if (!baseState || baseState.quoteId !== quoteId) {
        baseState = await fetchCorPrefill(quoteId);
      }
      if (latestQuote.current !== selectedQuoteId) return;

      const corNo = nextCorNumber(revisions);
      const machineNames = getMachineNamesForQuote(quotes, quoteId);
      const sourceLines =
        baseState.lineItems.length > 0
          ? baseState.lineItems
          : [{ id: "cor-line-1", qty: "", reqDescription: "", unitCost: "", selectedItems: "" }];

      setState({
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
      });
      setSelectedCorDocumentId("");
      setStatus("Started a new COR draft. Save to create it.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start a new COR draft.");
    } finally {
      setLoadingState(false);
    }
  }

  function editRevision(corDocumentId: number) {
    if (!selectedQuoteId) return;
    const quoteId = Number(selectedQuoteId);
    if (!Number.isFinite(quoteId) || corDocumentId <= 0) return;
    setLoadingState(true);
    setError(null);
    setStatus(null);
    void loadCorState(quoteId, corDocumentId)
      .then((loaded) => {
        if (latestQuote.current !== selectedQuoteId) return;
        if (!loaded) {
          throw new Error("Selected COR record was not found.");
        }
        setState({
          ...loaded.corData,
          approvalDate: todayDateValue(),
        });
        setSelectedCorDocumentId(String(loaded.corDocumentId));
        setStatus(`Loaded COR ${loaded.corNo || loaded.corDocumentId}.`);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Failed to load selected COR.");
      })
      .finally(() => setLoadingState(false));
  }

  function saveDraft() {
    if (!state) return;
    setSaving(true);
    setError(null);
    setStatus(null);
    const corDocumentId = parseCorDocumentId(selectedCorDocumentId);
    const createNew = corDocumentId == null;
    void saveCorState(state.quoteId, state, { corDocumentId, createNew })
      .then((saved) => {
        setState(saved.corData);
        setSelectedCorDocumentId(String(saved.corDocumentId));
        setStatus(
          createNew
            ? `Created COR ${saved.corNo || saved.corDocumentId} at ${saved.savedAt}.`
            : `Updated COR ${saved.corNo || saved.corDocumentId} at ${saved.savedAt}.`
        );
        void refreshRevisions(state.quoteId).catch(() => undefined);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to save COR draft."))
      .finally(() => setSaving(false));
  }

  function downloadCor() {
    if (!state) return;
    setDownloading(true);
    setError(null);
    setStatus(null);
    const corDocumentId = parseCorDocumentId(selectedCorDocumentId);
    void generateCorDoc(state.quoteId, { corData: state, corDocumentId })
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

      {selectedQuoteId ? (
        <Card>
          <CardHeader>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <CardTitle>COR List</CardTitle>
                <CardDescription>
                  All COR entries for the selected quote. Use Edit to open one below.
                </CardDescription>
              </div>
              <Button type="button" variant="outline" onClick={() => void createNewCorDraft()} disabled={loadingState}>
                <Plus className="mr-2 h-4 w-4" />New COR
              </Button>
            </div>
          </CardHeader>
          <CardContent>
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
                        No saved COR entries yet.
                      </TableCell>
                    </TableRow>
                  ) : (
                    revisions.map((entry) => {
                      const isSelected = selectedCorDocumentId === String(entry.corDocumentId);
                      const corLabel = entry.corNo.trim() || String(entry.corDocumentId);
                      return (
                        <TableRow key={entry.corDocumentId} data-state={isSelected ? "selected" : undefined}>
                          <TableCell className="font-semibold">COR {corLabel}</TableCell>
                          <TableCell>{entry.description.trim() || "-"}</TableCell>
                          <TableCell>{entry.modifiedDate ?? entry.createdDate ?? "-"}</TableCell>
                          <TableCell className="text-right">
                            <div className="flex items-center justify-end gap-2">
                              {isSelected ? (
                                <Badge variant="secondary">Editing</Badge>
                              ) : null}
                              <Button
                                type="button"
                                variant="ghost"
                                size="sm"
                                onClick={() => editRevision(entry.corDocumentId)}
                                disabled={loadingState}
                              >
                                Edit
                              </Button>
                            </div>
                          </TableCell>
                        </TableRow>
                      );
                    })
                  )}
                </TableBody>
              </Table>
            </div>
            {!selectedCorDocumentId && state ? (
              <p className="mt-3 text-xs text-muted-foreground">
                You are editing a new unsaved COR draft.
              </p>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      {state ? (
        <Card>
          <CardHeader>
            <CardTitle>COR Details</CardTitle>
            <CardDescription>
              Keep multiple COR entries per quote. Use COR No. and Description so users can identify each one quickly.
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
                <Input
                  type="date"
                  value={todayDateValue()}
                  readOnly
                />
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
