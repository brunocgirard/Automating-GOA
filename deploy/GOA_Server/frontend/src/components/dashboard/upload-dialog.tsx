"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Loader2, Search, Upload } from "lucide-react";
import {
  fetchQuoteClientInfo,
  fetchProcessingArtifacts,
  fetchQuotes,
  groupProcessingItems,
  identifyProcessingMachines,
  updateQuoteClientInfo,
  uploadQuotePdf,
  type QuoteClientInfo as QuoteClientInfoValues,
} from "@/lib/api";
import { FileUploadPicker } from "@/components/shared/file-upload-picker";
import { QuoteClientInfo } from "@/components/quotes/quote-details";
import type { LineItem } from "@/lib/types";
import { cn } from "@/lib/utils";

type UploadStep = "upload" | "client-info" | "identify" | "options" | "done";

interface UploadDialogProps {
  onUploaded?: () => void;
}

interface OptionCandidate {
  item: LineItem;
  index: number;
}

function sameItem(a: LineItem, b: LineItem): boolean {
  const bDescription = b.description ?? "";
  const bPrice = b.item_price_numeric ?? null;
  return (
    a.description.trim() === bDescription.trim() &&
    (a.item_price_numeric ?? null) === bPrice
  );
}

function formatPrice(value: number | null): string {
  if (value == null) return "-";
  return `$${value.toLocaleString()}`;
}

function createEmptyClientInfo(): QuoteClientInfoValues {
  return {
    quoteNo: "",
    ax: "",
    customerName: "",
    company: "",
    machine: "",
    serialNumber: "",
    soldToAddress1: "",
    soldToAddress2: "",
    soldToAddress3: "",
    shipToAddress1: "",
    shipToAddress2: "",
    shipToAddress3: "",
    telephone: "",
    customerPO: "",
    orderDate: "",
    ox: "",
    via: "",
    incoterm: "",
    taxId: "",
    hsCode: "",
    customerNumber: "",
    clientContact: "",
  };
}

function summarizeDescription(description: string): string {
  return description.replace(/\s+/g, " ").trim();
}

function itemMatchesSearch(item: LineItem, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  const haystack = [
    item.description ?? "",
    item.quantity_text ?? "",
    item.selection_text ?? "",
    item.item_price_numeric != null ? String(item.item_price_numeric) : "",
  ]
    .join(" ")
    .toLowerCase();
  return haystack.includes(q);
}

function toggleIndex(indices: number[], index: number): number[] {
  if (indices.includes(index)) {
    return indices.filter((value) => value !== index);
  }
  return [...indices, index].sort((a, b) => a - b);
}

function ItemSelectionList({
  title,
  countLabel,
  searchValue,
  onSearchChange,
  entries,
  selectedIndices,
  onToggle,
}: {
  title: string;
  countLabel: string;
  searchValue: string;
  onSearchChange: (value: string) => void;
  entries: OptionCandidate[];
  selectedIndices: number[];
  onToggle: (index: number) => void;
}) {
  return (
    <div className="space-y-3">
      <div className="sticky top-0 z-10 rounded-md border bg-background/95 p-3 backdrop-blur">
        <div className="mb-2 flex items-center justify-between gap-3">
          <h3 className="text-sm font-semibold">{title}</h3>
          <span className="text-sm font-medium text-[#c00000]">{countLabel}</span>
        </div>
        <div className="relative">
          <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={searchValue}
            onChange={(event) => onSearchChange(event.target.value)}
            className="pl-8"
            placeholder="Search line items..."
          />
        </div>
      </div>

      <div className="max-h-[55vh] space-y-2 overflow-y-auto rounded-md border p-3">
        {entries.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">No matching line items.</p>
        ) : (
          entries.map((entry) => {
            const selected = selectedIndices.includes(entry.index);
            return (
              <label
                key={entry.index}
                className={cn(
                  "block cursor-pointer rounded-md border p-3 transition-colors",
                  selected
                    ? "border-[#c00000] bg-[#c00000]/5"
                    : "border-neutral-200 hover:border-neutral-300"
                )}
              >
                <div className="flex items-start gap-3">
                  <Checkbox
                    checked={selected}
                    onCheckedChange={() => onToggle(entry.index)}
                    className="mt-0.5"
                  />
                  <div className="min-w-0 space-y-2">
                    <p className="whitespace-pre-line text-sm font-medium leading-5 text-foreground">
                      {entry.item.description}
                    </p>
                    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
                      <span>Qty: {entry.item.quantity_text || "-"}</span>
                      <span>Price: {formatPrice(entry.item.item_price_numeric)}</span>
                    </div>
                  </div>
                </div>
              </label>
            );
          })
        )}
      </div>
    </div>
  );
}

function SelectedSummary({
  title,
  entries,
}: {
  title: string;
  entries: OptionCandidate[];
}) {
  return (
    <div className="rounded-md border p-3">
      <h3 className="text-sm font-semibold">{title}</h3>
      <div className="mt-3 max-h-[55vh] space-y-2 overflow-y-auto">
        {entries.length === 0 ? (
          <p className="text-sm text-muted-foreground">No items selected yet.</p>
        ) : (
          entries.map((entry) => (
            <div key={entry.index} className="rounded-md border bg-neutral-50 p-3">
              <p className="text-sm font-medium">{summarizeDescription(entry.item.description)}</p>
              <p className="mt-1 text-xs text-muted-foreground">
                Qty: {entry.item.quantity_text || "-"} | Price: {formatPrice(entry.item.item_price_numeric)}
              </p>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

export function UploadDialog({ onUploaded }: UploadDialogProps) {
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState<UploadStep>("upload");
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [savingClientInfo, setSavingClientInfo] = useState(false);
  const [grouping, setGrouping] = useState(false);
  const [identifying, setIdentifying] = useState(false);
  const [quoteRef, setQuoteRef] = useState("");
  const [quoteId, setQuoteId] = useState<number | null>(null);
  const [clientInfo, setClientInfo] = useState<QuoteClientInfoValues | null>(null);
  const [items, setItems] = useState<LineItem[]>([]);
  const [mainMachineIndices, setMainMachineIndices] = useState<number[]>([]);
  const [commonOptionIndices, setCommonOptionIndices] = useState<number[]>([]);
  const [suggestedMachineIndices, setSuggestedMachineIndices] = useState<number[]>([]);
  const [groupedMachinesCount, setGroupedMachinesCount] = useState(0);
  const [commonItemsCount, setCommonItemsCount] = useState(0);
  const [identifySearch, setIdentifySearch] = useState("");
  const [optionsSearch, setOptionsSearch] = useState("");
  const [error, setError] = useState<string | null>(null);

  const optionCandidates = useMemo(
    () =>
      items
        .map((item, index) => ({ item, index }))
        .filter(({ index }) => !mainMachineIndices.includes(index)),
    [items, mainMachineIndices]
  );

  const filteredIdentifyEntries = useMemo(
    () =>
      items
        .map((item, index) => ({ item, index }))
        .filter(({ item }) => itemMatchesSearch(item, identifySearch)),
    [identifySearch, items]
  );

  const filteredOptionEntries = useMemo(
    () => optionCandidates.filter(({ item }) => itemMatchesSearch(item, optionsSearch)),
    [optionCandidates, optionsSearch]
  );

  const selectedMachineEntries = useMemo(
    () =>
      mainMachineIndices
        .map((index) => ({ index, item: items[index] }))
        .filter((entry): entry is OptionCandidate => Boolean(entry.item)),
    [items, mainMachineIndices]
  );

  const selectedOptionEntries = useMemo(
    () =>
      commonOptionIndices
        .map((index) => optionCandidates.find((entry) => entry.index === index))
        .filter((entry): entry is OptionCandidate => Boolean(entry)),
    [commonOptionIndices, optionCandidates]
  );

  useEffect(() => {
    setCommonOptionIndices((prev) => prev.filter((index) => !mainMachineIndices.includes(index)));
  }, [mainMachineIndices]);

  function resetDialogState() {
    setStep("upload");
    setFile(null);
    setUploading(false);
    setSavingClientInfo(false);
    setGrouping(false);
    setIdentifying(false);
    setQuoteRef("");
    setQuoteId(null);
    setClientInfo(null);
    setItems([]);
    setMainMachineIndices([]);
    setCommonOptionIndices([]);
    setSuggestedMachineIndices([]);
    setGroupedMachinesCount(0);
    setCommonItemsCount(0);
    setIdentifySearch("");
    setOptionsSearch("");
    setError(null);
  }

  async function autoIdentify(itemsToScan: LineItem[]): Promise<number[]> {
    const result = await identifyProcessingMachines(itemsToScan);
    const indices = new Set<number>();
    for (const machine of result.machines) {
      const idx = itemsToScan.findIndex((item) => sameItem(item, machine.main_item));
      if (idx >= 0) indices.add(idx);
    }
    return Array.from(indices).sort((a, b) => a - b);
  }

  async function runAutoIdentify() {
    setIdentifying(true);
    setError(null);
    try {
      const detectedIndices = await autoIdentify(items);
      setSuggestedMachineIndices(detectedIndices);
      setMainMachineIndices(detectedIndices);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Auto-identification failed.");
    } finally {
      setIdentifying(false);
    }
  }

  async function handleUpload() {
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const uploaded = await uploadQuotePdf(file);
      setQuoteRef(uploaded.quote_ref);

      const [artifacts, rows] = await Promise.all([
        fetchProcessingArtifacts(uploaded.quote_ref),
        fetchQuotes(),
      ]);

      setItems(artifacts.items);
      const detectedIndices = await autoIdentify(artifacts.items);
      setSuggestedMachineIndices(detectedIndices);
      setMainMachineIndices(detectedIndices);
      setCommonOptionIndices([]);

      const uploadedRow = rows.find((row) => row.quoteRef === uploaded.quote_ref);
      const resolvedQuoteId = uploadedRow?.quoteId ?? null;
      setQuoteId(resolvedQuoteId);

      if (resolvedQuoteId != null) {
        try {
          const loadedClientInfo = await fetchQuoteClientInfo(resolvedQuoteId);
          setClientInfo(loadedClientInfo);
        } catch {
          setClientInfo(createEmptyClientInfo());
        }
      } else {
        setClientInfo(createEmptyClientInfo());
      }

      setStep("client-info");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setUploading(false);
    }
  }

  function handleClientInfoChange(
    key: keyof QuoteClientInfoValues,
    value: string
  ) {
    setClientInfo((prev) => (prev ? { ...prev, [key]: value } : prev));
  }

  async function handleClientInfoContinue() {
    if (!clientInfo) return;

    setSavingClientInfo(true);
    setError(null);
    try {
      if (quoteId != null) {
        await updateQuoteClientInfo(quoteId, clientInfo);
      }
      setStep("identify");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save client information.");
    } finally {
      setSavingClientInfo(false);
    }
  }

  async function handleConfirmOptions() {
    setGrouping(true);
    setError(null);
    try {
      const grouped = await groupProcessingItems(
        items,
        mainMachineIndices,
        commonOptionIndices,
        quoteRef
      );
      setGroupedMachinesCount(grouped.machines.length);
      setCommonItemsCount(grouped.common_items.length);
      onUploaded?.();
      setStep("done");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to group items.");
    } finally {
      setGrouping(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(value) => {
        setOpen(value);
        if (!value) resetDialogState();
      }}
    >
      <DialogTrigger asChild>
        <Button>
          <Upload className="mr-2 size-4" />
          Upload + Identify
        </Button>
      </DialogTrigger>
      <DialogContent
        className={cn(
          "max-h-[90vh] overflow-y-auto",
          step === "identify" || step === "options" ? "sm:max-w-6xl" : "sm:max-w-lg"
        )}
      >
        <DialogHeader>
          <DialogTitle>
            {step === "upload" && "Upload Quote"}
            {step === "client-info" && "Client Information"}
            {step === "identify" && "Confirm Main Machines"}
            {step === "options" && "Confirm Common Options"}
            {step === "done" && "Upload Flow Complete"}
          </DialogTitle>
          <DialogDescription>
            {step === "upload" &&
              "Upload a quote PDF, then confirm main machines and common options before saving grouped data."}
            {step === "client-info" &&
              "Confirm customer details before selecting the main machine items."}
            {step === "identify" &&
              "Review auto-detected machines and confirm which line items are main machines."}
            {step === "options" &&
              "Select items that should be shared across all machines. Unselected items become machine-specific add-ons."}
            {step === "done" && "Machine grouping is complete and saved."}
          </DialogDescription>
        </DialogHeader>

        {error && <p className="text-sm text-red-600">{error}</p>}

        {step === "upload" && (
          <>
            <FileUploadPicker
              file={file}
              onSelect={setFile}
              emptyLabel="Click to select a PDF file"
              accept=".pdf"
              variant="dropzone"
            />

            <DialogFooter>
              <Button variant="outline" onClick={() => setOpen(false)} disabled={uploading}>
                Cancel
              </Button>
              <Button disabled={!file || uploading} onClick={handleUpload}>
                {uploading ? "Uploading..." : "Upload and Continue"}
              </Button>
            </DialogFooter>
          </>
        )}

        {step === "client-info" && (
          <div className="space-y-4">
            {clientInfo ? (
              <QuoteClientInfo clientInfo={clientInfo} onChange={handleClientInfoChange} />
            ) : (
              <div className="rounded-md border bg-neutral-50 p-4 text-sm text-muted-foreground">
                Loading client information...
              </div>
            )}

            <div className="flex flex-col gap-2 sm:flex-row sm:justify-between">
              <Button variant="outline" onClick={() => setStep("upload")} disabled={savingClientInfo}>
                Back
              </Button>
              <Button
                className="bg-[#c00000] hover:bg-[#a00000]"
                disabled={savingClientInfo || !clientInfo}
                onClick={() => void handleClientInfoContinue()}
              >
                {savingClientInfo ? "Saving..." : "Save and Continue"}
              </Button>
            </div>
          </div>
        )}

        {step === "identify" && (
          <div className="space-y-4">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm text-muted-foreground">
                Suggested: {suggestedMachineIndices.length} machine
                {suggestedMachineIndices.length === 1 ? "" : "s"}
              </p>
              <Button variant="outline" onClick={runAutoIdentify} disabled={identifying}>
                {identifying ? <Loader2 className="mr-2 size-4 animate-spin" /> : null}
                Auto-Identify
              </Button>
            </div>

            <div className="grid gap-4 lg:grid-cols-[1.8fr_1fr]">
              <ItemSelectionList
                title="All Line Items"
                countLabel={`${mainMachineIndices.length} machines selected`}
                searchValue={identifySearch}
                onSearchChange={setIdentifySearch}
                entries={filteredIdentifyEntries}
                selectedIndices={mainMachineIndices}
                onToggle={(index) =>
                  setMainMachineIndices((current) => toggleIndex(current, index))
                }
              />
              <SelectedSummary
                title={`Selected Machines (${mainMachineIndices.length})`}
                entries={selectedMachineEntries}
              />
            </div>

            <div className="flex flex-col gap-2 sm:flex-row sm:justify-between">
              <Button variant="outline" onClick={() => setStep("client-info")}>
                Back
              </Button>
              <Button
                className="bg-[#c00000] hover:bg-[#a00000]"
                disabled={mainMachineIndices.length === 0}
                onClick={() => setStep("options")}
              >
                Continue to Common Options
              </Button>
            </div>
          </div>
        )}

        {step === "options" && (
          <div className="space-y-4">
            {grouping && <p className="text-sm text-muted-foreground">Grouping items...</p>}
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm text-muted-foreground">
                Select shared options. Unselected entries become machine-specific add-ons.
              </p>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  onClick={() => setCommonOptionIndices(optionCandidates.map((entry) => entry.index))}
                >
                  Select All
                </Button>
                <Button variant="outline" onClick={() => setCommonOptionIndices([])}>
                  Clear
                </Button>
              </div>
            </div>

            <div className="grid gap-4 lg:grid-cols-[1.8fr_1fr]">
              <ItemSelectionList
                title="Remaining Items"
                countLabel={`${commonOptionIndices.length} common options selected`}
                searchValue={optionsSearch}
                onSearchChange={setOptionsSearch}
                entries={filteredOptionEntries}
                selectedIndices={commonOptionIndices}
                onToggle={(index) =>
                  setCommonOptionIndices((current) => toggleIndex(current, index))
                }
              />
              <SelectedSummary
                title={`Common Options (${commonOptionIndices.length})`}
                entries={selectedOptionEntries}
              />
            </div>

            <div className="flex flex-col gap-2 sm:flex-row sm:justify-between">
              <Button variant="outline" onClick={() => setStep("identify")} disabled={grouping}>
                Back
              </Button>
              <Button
                className="bg-[#c00000] hover:bg-[#a00000]"
                onClick={handleConfirmOptions}
                disabled={grouping || mainMachineIndices.length === 0}
              >
                Group + Save
              </Button>
            </div>
          </div>
        )}

        {step === "done" && (
          <div className="space-y-4">
            <div className="rounded-md border bg-green-50 p-4 text-sm text-green-700">
              Quote <span className="font-semibold">{quoteRef}</span> uploaded and grouped.
            </div>
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="rounded-md border bg-white p-3">
                <p className="text-xs text-muted-foreground">Items</p>
                <p className="text-lg font-semibold">{items.length}</p>
              </div>
              <div className="rounded-md border bg-white p-3">
                <p className="text-xs text-muted-foreground">Machines</p>
                <p className="text-lg font-semibold">{groupedMachinesCount}</p>
              </div>
              <div className="rounded-md border bg-white p-3">
                <p className="text-xs text-muted-foreground">Common Options</p>
                <p className="text-lg font-semibold">{commonItemsCount}</p>
              </div>
            </div>
            <div className="flex flex-col gap-2 sm:flex-row sm:justify-end">
              <Button variant="outline" onClick={() => setOpen(false)}>
                Close
              </Button>
              <Button asChild>
                <Link href={quoteId ? `/processing?quote=${quoteId}` : "/processing"}>
                  Open Processing
                </Link>
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
