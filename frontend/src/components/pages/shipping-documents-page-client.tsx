"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Check, Copy, Download, Plus, Save, Trash2 } from "lucide-react";
import {
  fetchQuotes,
  fetchShippingPrefill,
  generateShippingDocs,
  loadShippingState,
  saveShippingState,
  type QuoteRow,
  type ShippingDocumentState,
  type ShippingDocumentType,
  type ShippingMachine,
} from "@/lib/api";
import { useClientFilter } from "@/components/layout/client-filter-context";
import { PackingSlipPreview } from "@/components/shipping/packing-slip-preview";
import { CommercialInvoicePreview } from "@/components/shipping/commercial-invoice-preview";
import { CertificateOriginPreview } from "@/components/shipping/certificate-origin-preview";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

const steps = ["select", "configure", "preview"] as const;
type Step = (typeof steps)[number];
type QuoteOption = { id: string; label: string };

function toAmount(v: string): number {
  const n = Number(v.replace(/[^0-9.-]/g, ""));
  return Number.isFinite(n) ? n : 0;
}

function fmt(n: number): string {
  return Number.isFinite(n) ? n.toFixed(2) : "0.00";
}

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

function StepIndicator({ current }: { current: Step }) {
  const currentIndex = steps.indexOf(current);
  const labels: Record<Step, string> = {
    select: "Select & Review",
    configure: "Machines & Trucks",
    preview: "Preview & Generate",
  };

  return (
    <div className="mb-6 flex items-center gap-3">
      {steps.map((step, index) => {
        const done = index < currentIndex;
        const active = index === currentIndex;
        return (
          <div key={step} className="flex items-center gap-2">
            <div
              className={`flex h-8 w-8 items-center justify-center rounded-full border text-xs ${
                done
                  ? "border-green-600 bg-green-600 text-white"
                  : active
                    ? "border-[#c00000] bg-[#c00000] text-white"
                    : "border-neutral-300 text-neutral-400"
              }`}
            >
              {done ? <Check className="h-4 w-4" /> : index + 1}
            </div>
            <span className={`text-xs ${active ? "text-[#c00000]" : "text-neutral-500"}`}>{labels[step]}</span>
            {index < steps.length - 1 ? <div className="h-px w-8 bg-neutral-200" /> : null}
          </div>
        );
      })}
    </div>
  );
}

export default function ShippingDocumentsPageClient() {
  const { selectedClientId } = useClientFilter();
  const [quotes, setQuotes] = useState<QuoteRow[]>([]);
  const [selectedQuoteId, setSelectedQuoteId] = useState("");
  const [step, setStep] = useState<Step>("select");
  const [state, setState] = useState<ShippingDocumentState | null>(null);
  const [loadingQuotes, setLoadingQuotes] = useState(true);
  const [loadingState, setLoadingState] = useState(false);
  const [saving, setSaving] = useState(false);
  const [downloading, setDownloading] = useState<ShippingDocumentType | null>(null);
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

  const invoiceTotal = useMemo(() => {
    if (!state) return 0;
    const manual = toAmount(state.meta.totalInvoiceAmount);
    const computed = state.machines.reduce((sum, machine) => sum + machine.unitPrice, 0);
    return manual > 0 ? manual : computed;
  }, [state]);

  const unitPrice = useMemo(() => {
    if (!state || state.machines.length === 0) return 0;
    return invoiceTotal / state.machines.length;
  }, [invoiceTotal, state]);

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
      const loaded = await loadShippingState(quoteId);
      if (latestQuote.current !== rawId) return;
      if (loaded) {
        setState(loaded.shippingData);
        setStatus(`Loaded draft ${loaded.modifiedDate ?? loaded.createdDate ?? ""}.`);
      } else {
        const prefill = await fetchShippingPrefill(quoteId);
        if (latestQuote.current !== rawId) return;
        setState(prefill);
      }
      setStep("select");
    } catch (err) {
      if (latestQuote.current !== rawId) return;
      setError(err instanceof Error ? err.message : "Failed to load shipping data.");
      setState(null);
    } finally {
      if (latestQuote.current === rawId) setLoadingState(false);
    }
  }

  function patchState(fn: (prev: ShippingDocumentState) => ShippingDocumentState) {
    setState((prev) => (prev ? fn(prev) : prev));
  }

  function setClientField(key: keyof ShippingDocumentState["client"], value: string) {
    patchState((prev) => ({ ...prev, client: { ...prev.client, [key]: value } }));
  }

  function setMetaField(key: keyof ShippingDocumentState["meta"], value: string) {
    patchState((prev) => ({ ...prev, meta: { ...prev.meta, [key]: value } }));
  }

  function setMachine(machineId: string, updater: (machine: ShippingMachine) => ShippingMachine) {
    patchState((prev) => ({
      ...prev,
      machines: prev.machines.map((machine) => (machine.id === machineId ? updater(machine) : machine)),
    }));
  }

  function addMachine() {
    patchState((prev) => ({
      ...prev,
      machines: [
        ...prev.machines,
        {
          id: uid("machine"),
          machineId: null,
          machineName: `Machine ${prev.machines.length + 1}`,
          model: "",
          hsCode: "",
          serialNumber: "",
          unitPrice: 0,
          truckId: prev.trucks[0]?.id ?? "truck-1",
          crates: [{ id: uid("crate"), lengthIn: "", widthIn: "", heightIn: "", weightLbs: "" }],
        },
      ],
    }));
  }

  function addTruck() {
    patchState((prev) => ({
      ...prev,
      trucks: [...prev.trucks, { id: `truck-${prev.trucks.length + 1}`, name: `Truck ${prev.trucks.length + 1}` }],
    }));
  }

  function saveDraft() {
    if (!state) return;
    setSaving(true);
    setError(null);
    setStatus(null);
    void saveShippingState(state.quoteId, state)
      .then((saved) => {
        setState(saved.shippingData);
        setStatus(`Draft saved at ${saved.savedAt}.`);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to save draft."))
      .finally(() => setSaving(false));
  }

  function generate(documentType: ShippingDocumentType) {
    if (!state) return;
    setDownloading(documentType);
    setError(null);
    setStatus(null);
    void generateShippingDocs(state.quoteId, { documentType, shippingData: state })
      .then((result) => {
        downloadBlob(result.blob, result.filename);
        setStatus(`Generated ${result.filename}.`);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to generate documents."))
      .finally(() => setDownloading(null));
  }

  const fieldRows: Array<{ key: keyof ShippingDocumentState["client"]; label: string }> = [
    { key: "customerPO", label: "Customer PO" },
    { key: "incoterm", label: "Incoterm" },
    { key: "taxId", label: "Tax ID" },
    { key: "orderDate", label: "Order Date" },
    { key: "ox", label: "Order Number (OX)" },
    { key: "customerNumber", label: "Customer Number" },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">Shipping Documents</h2>
        <p className="mt-1 text-sm text-muted-foreground">Build packing slip, commercial invoice, and certificate of origin.</p>
      </div>

      <StepIndicator current={step} />

      {error ? <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div> : null}
      {status ? <div className="rounded-md border border-green-200 bg-green-50 p-3 text-sm text-green-700">{status}</div> : null}

      {step === "select" ? (
      <Card>
        <CardHeader>
          <CardTitle>Step 1: Select Quote & Review Info</CardTitle>
          <CardDescription>Load prefilled data, adjust addresses and customer fields.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_auto] md:items-end">
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
            <Button
              type="button"
              variant="outline"
              disabled={!state}
              onClick={() =>
                patchState((prev) => ({
                  ...prev,
                  client: {
                    ...prev.client,
                    shipToAddress1: prev.client.soldToAddress1,
                    shipToAddress2: prev.client.soldToAddress2,
                    shipToAddress3: prev.client.soldToAddress3,
                  },
                }))
              }
            >
              <Copy className="mr-2 h-4 w-4" />
              Copy Sold-To to Ship-To
            </Button>
          </div>

          {loadingState ? <div className="rounded-md border bg-neutral-50 p-3 text-sm text-muted-foreground">Loading quote shipping data...</div> : null}
          {!loadingState && !state ? <div className="rounded-md border bg-neutral-50 p-3 text-sm text-muted-foreground">Select a quote to start.</div> : null}

          {state ? (
            <>
              <div className="grid gap-3 md:grid-cols-2">
                <div className="space-y-1"><label className="text-sm font-medium">Company</label><Input value={state.client.company} onChange={(e) => setClientField("company", e.target.value)} /></div>
                <div className="space-y-1"><label className="text-sm font-medium">Customer Name</label><Input value={state.client.customerName} onChange={(e) => setClientField("customerName", e.target.value)} /></div>
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2 rounded-md border p-3">
                  <p className="text-sm font-semibold">Sold-To</p>
                  <Input value={state.client.soldToAddress1} onChange={(e) => setClientField("soldToAddress1", e.target.value)} placeholder="Address line 1" />
                  <Input value={state.client.soldToAddress2} onChange={(e) => setClientField("soldToAddress2", e.target.value)} placeholder="Address line 2" />
                  <Input value={state.client.soldToAddress3} onChange={(e) => setClientField("soldToAddress3", e.target.value)} placeholder="Address line 3" />
                </div>
                <div className="space-y-2 rounded-md border p-3">
                  <p className="text-sm font-semibold">Ship-To</p>
                  <Input value={state.client.shipToAddress1} onChange={(e) => setClientField("shipToAddress1", e.target.value)} placeholder="Address line 1" />
                  <Input value={state.client.shipToAddress2} onChange={(e) => setClientField("shipToAddress2", e.target.value)} placeholder="Address line 2" />
                  <Input value={state.client.shipToAddress3} onChange={(e) => setClientField("shipToAddress3", e.target.value)} placeholder="Address line 3" />
                </div>
              </div>
              <div className="grid gap-3 md:grid-cols-3">
                {fieldRows.map((field) => (
                  <div key={field.key} className="space-y-1">
                    <label className="text-sm font-medium">{field.label}</label>
                    <Input value={state.client[field.key]} onChange={(e) => setClientField(field.key, e.target.value)} />
                  </div>
                ))}
              </div>
              <div className="flex justify-end"><Button type="button" onClick={() => setStep("configure")}>Next: Configure Machines</Button></div>
            </>
          ) : null}
        </CardContent>
      </Card>
      ) : null}

      {state && step === "configure" ? (
        <Card>
          <CardHeader>
            <CardTitle>Step 2: Configure Machines & Trucks</CardTitle>
            <CardDescription>Set serial/HS/model, crate dimensions, truck assignment, and shipping metadata.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap gap-2">
              <Button type="button" variant="outline" onClick={addMachine}><Plus className="mr-2 h-4 w-4" />Add Machine</Button>
              <Button type="button" variant="outline" onClick={addTruck}><Plus className="mr-2 h-4 w-4" />Add Truck</Button>
            </div>

            {state.machines.map((machine, index) => (
              <div key={machine.id} className="space-y-3 rounded-md border p-3">
                <div className="flex items-center justify-between">
                  <p className="font-medium">Machine {index + 1}</p>
                  <Button type="button" size="sm" variant="outline" onClick={() => patchState((prev) => ({ ...prev, machines: prev.machines.filter((entry) => entry.id !== machine.id) }))}>
                    <Trash2 className="mr-1 h-3.5 w-3.5" />Remove
                  </Button>
                </div>
                <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
                  <div className="space-y-1"><label className="text-sm font-medium">Machine Name</label><Input value={machine.machineName} onChange={(e) => setMachine(machine.id, (v) => ({ ...v, machineName: e.target.value }))} /></div>
                  <div className="space-y-1"><label className="text-sm font-medium">Model</label><Input value={machine.model} onChange={(e) => setMachine(machine.id, (v) => ({ ...v, model: e.target.value }))} /></div>
                  <div className="space-y-1"><label className="text-sm font-medium">Serial Number</label><Input value={machine.serialNumber} onChange={(e) => setMachine(machine.id, (v) => ({ ...v, serialNumber: e.target.value }))} /></div>
                  <div className="space-y-1"><label className="text-sm font-medium">HS Code</label><Input value={machine.hsCode} onChange={(e) => setMachine(machine.id, (v) => ({ ...v, hsCode: e.target.value }))} /></div>
                  <div className="space-y-1"><label className="text-sm font-medium">Truck</label>
                    <Select value={machine.truckId} onValueChange={(value) => setMachine(machine.id, (v) => ({ ...v, truckId: value }))}>
                      <SelectTrigger><SelectValue placeholder="Select truck" /></SelectTrigger>
                      <SelectContent>{state.trucks.map((truck) => <SelectItem key={truck.id} value={truck.id}>{truck.name}</SelectItem>)}</SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-1"><label className="text-sm font-medium">Unit Price (USD)</label><Input value={fmt(machine.unitPrice)} onChange={(e) => setMachine(machine.id, (v) => ({ ...v, unitPrice: toAmount(e.target.value) }))} /></div>
                </div>

                <div className="space-y-2 rounded-md border p-3">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-semibold">Crates</p>
                    <Button type="button" size="sm" variant="outline" onClick={() => setMachine(machine.id, (v) => ({ ...v, crates: [...v.crates, { id: uid("crate"), lengthIn: "", widthIn: "", heightIn: "", weightLbs: "" }] }))}>
                      <Plus className="mr-1 h-3.5 w-3.5" />Add Crate
                    </Button>
                  </div>
                  {machine.crates.map((crate) => (
                    <div key={crate.id} className="grid gap-2 md:grid-cols-[1fr_1fr_1fr_1fr_auto]">
                      <Input placeholder="Length" value={crate.lengthIn} onChange={(e) => setMachine(machine.id, (v) => ({ ...v, crates: v.crates.map((entry) => entry.id === crate.id ? { ...entry, lengthIn: e.target.value } : entry) }))} />
                      <Input placeholder="Width" value={crate.widthIn} onChange={(e) => setMachine(machine.id, (v) => ({ ...v, crates: v.crates.map((entry) => entry.id === crate.id ? { ...entry, widthIn: e.target.value } : entry) }))} />
                      <Input placeholder="Height" value={crate.heightIn} onChange={(e) => setMachine(machine.id, (v) => ({ ...v, crates: v.crates.map((entry) => entry.id === crate.id ? { ...entry, heightIn: e.target.value } : entry) }))} />
                      <Input placeholder="Weight (lbs)" value={crate.weightLbs} onChange={(e) => setMachine(machine.id, (v) => ({ ...v, crates: v.crates.map((entry) => entry.id === crate.id ? { ...entry, weightLbs: e.target.value } : entry) }))} />
                      <Button type="button" size="icon" variant="outline" onClick={() => setMachine(machine.id, (v) => ({ ...v, crates: v.crates.filter((entry) => entry.id !== crate.id) }))}><Trash2 className="h-4 w-4" /></Button>
                    </div>
                  ))}
                </div>
              </div>
            ))}

            <div className="grid gap-3 rounded-md border p-3 md:grid-cols-2 lg:grid-cols-4">
              <div className="space-y-1"><label className="text-sm font-medium">Invoice Total (USD)</label><Input value={state.meta.totalInvoiceAmount} onChange={(e) => setMetaField("totalInvoiceAmount", e.target.value)} placeholder="0.00" /></div>
              <div className="space-y-1"><label className="text-sm font-medium">Unit Price (Auto)</label><Input value={fmt(unitPrice)} readOnly disabled /></div>
              <div className="space-y-1"><label className="text-sm font-medium">Broker Info</label><Input value={state.meta.brokerInfo} onChange={(e) => setMetaField("brokerInfo", e.target.value)} /></div>
              <div className="space-y-1"><label className="text-sm font-medium">Country of Origin</label><Input value={state.meta.countryOfOrigin} onChange={(e) => setMetaField("countryOfOrigin", e.target.value)} /></div>
              <div className="space-y-1"><label className="text-sm font-medium">Certifier Name</label><Input value={state.meta.certifierName} onChange={(e) => setMetaField("certifierName", e.target.value)} /></div>
              <div className="space-y-1"><label className="text-sm font-medium">Certifier Title</label><Input value={state.meta.certifierTitle} onChange={(e) => setMetaField("certifierTitle", e.target.value)} /></div>
              <div className="space-y-1"><label className="text-sm font-medium">Origin Criterion</label><Input value={state.meta.originCriterion} onChange={(e) => setMetaField("originCriterion", e.target.value)} /></div>
              <div className="space-y-1"><label className="text-sm font-medium">Certifier Date</label><Input value={state.meta.certifierDate} onChange={(e) => setMetaField("certifierDate", e.target.value)} /></div>
              <div className="space-y-1"><label className="text-sm font-medium">Certifier Contact</label><Input value={state.meta.certifierContact} onChange={(e) => setMetaField("certifierContact", e.target.value)} /></div>
              <div className="space-y-1"><label className="text-sm font-medium">Blanket From</label><Input value={state.meta.blanketFrom} onChange={(e) => setMetaField("blanketFrom", e.target.value)} placeholder="DD/MM/YYYY" /></div>
              <div className="space-y-1"><label className="text-sm font-medium">Blanket To</label><Input value={state.meta.blanketTo} onChange={(e) => setMetaField("blanketTo", e.target.value)} placeholder="DD/MM/YYYY" /></div>
            </div>

            <div className="flex justify-between">
              <Button type="button" variant="outline" onClick={() => setStep("select")}>Back</Button>
              <Button type="button" onClick={() => setStep("preview")}>Next: Preview & Generate</Button>
            </div>
          </CardContent>
        </Card>
      ) : null}

      {state && step === "preview" ? (
        <Card>
          <CardHeader>
            <CardTitle>Step 3: Preview & Generate</CardTitle>
            <CardDescription>Review all three documents, save draft, and download DOCX outputs.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Tabs defaultValue="packing_slip" className="space-y-4">
              <TabsList className="grid w-full grid-cols-3">
                <TabsTrigger value="packing_slip">Packing Slip</TabsTrigger>
                <TabsTrigger value="commercial_invoice">Commercial Invoice</TabsTrigger>
                <TabsTrigger value="certificate_origin">Certificate of Origin</TabsTrigger>
              </TabsList>
              <TabsContent value="packing_slip" className="mt-0"><PackingSlipPreview state={state} /></TabsContent>
              <TabsContent value="commercial_invoice" className="mt-0"><CommercialInvoicePreview state={state} /></TabsContent>
              <TabsContent value="certificate_origin" className="mt-0"><CertificateOriginPreview state={state} /></TabsContent>
            </Tabs>

            <div className="flex flex-wrap gap-2">
              <Button type="button" variant="outline" disabled={Boolean(downloading)} onClick={() => generate("packing_slip")}><Download className="mr-2 h-4 w-4" />{downloading === "packing_slip" ? "Generating..." : "Download Packing Slip"}</Button>
              <Button type="button" variant="outline" disabled={Boolean(downloading)} onClick={() => generate("commercial_invoice")}><Download className="mr-2 h-4 w-4" />{downloading === "commercial_invoice" ? "Generating..." : "Download Commercial Invoice"}</Button>
              <Button type="button" variant="outline" disabled={Boolean(downloading)} onClick={() => generate("certificate_origin")}><Download className="mr-2 h-4 w-4" />{downloading === "certificate_origin" ? "Generating..." : "Download Certificate"}</Button>
              <Button type="button" disabled={Boolean(downloading)} onClick={() => generate("all")}><Download className="mr-2 h-4 w-4" />{downloading === "all" ? "Generating ZIP..." : "Download All (ZIP)"}</Button>
              <Button type="button" variant="secondary" disabled={saving} onClick={saveDraft}><Save className="mr-2 h-4 w-4" />{saving ? "Saving..." : "Save Draft"}</Button>
            </div>
            <div className="flex justify-start"><Button type="button" variant="outline" onClick={() => setStep("configure")}>Back</Button></div>
          </CardContent>
        </Card>
      ) : null}

      {loadingQuotes && quoteOptions.length === 0 ? <div className="rounded-md border bg-white p-8 text-sm text-muted-foreground">Loading quotes...</div> : null}
      {!loadingQuotes && quoteOptions.length === 0 ? <div className="rounded-md border bg-white p-8 text-sm text-muted-foreground">No quotes available for current client filter.</div> : null}
      {state ? <div className="text-xs text-neutral-500">Machines: {state.machines.length} | Invoice total: {fmt(invoiceTotal)} USD</div> : null}
    </div>
  );
}
