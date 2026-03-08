"use client";

import { useState } from "react";
import { Loader2, Plus } from "lucide-react";
import { createProject, fetchQuotes } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface CreateProjectDialogProps {
  onCreated?: () => Promise<void> | void;
}

interface QuoteOption {
  id: string;
  quoteId: number;
  quoteRef: string;
  clientName: string;
  machineName: string;
}

function compactMachineName(value: string): string {
  const firstLine = (value || "").split(/\r?\n/, 1)[0] ?? "";
  return firstLine.replace(/\s+/g, " ").trim() || "Machine";
}

function todayDate(): string {
  const now = new Date();
  return now.toISOString().slice(0, 10);
}

export function CreateProjectDialog({ onCreated }: CreateProjectDialogProps) {
  const [open, setOpen] = useState(false);
  const [loadingQuotes, setLoadingQuotes] = useState(false);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [quotes, setQuotes] = useState<QuoteOption[]>([]);
  const [selectedQuoteId, setSelectedQuoteId] = useState<string>("");
  const [projectName, setProjectName] = useState("");
  const [customerName, setCustomerName] = useState("");
  const [quoteRef, setQuoteRef] = useState("");
  const [machineSummary, setMachineSummary] = useState("");
  const [startDate, setStartDate] = useState(todayDate());
  const [targetEndDate, setTargetEndDate] = useState("");

  function resetForm() {
    setSelectedQuoteId("");
    setProjectName("");
    setCustomerName("");
    setQuoteRef("");
    setMachineSummary("");
    setStartDate(todayDate());
    setTargetEndDate("");
    setError(null);
    setCreating(false);
  }

  async function ensureQuotesLoaded() {
    if (quotes.length > 0) return;
    setLoadingQuotes(true);
    setError(null);
    try {
      const rows = await fetchQuotes();
      const map = new Map<number, QuoteOption>();
      for (const row of rows) {
        if (!map.has(row.quoteId)) {
          map.set(row.quoteId, {
            id: String(row.quoteId),
            quoteId: row.quoteId,
            quoteRef: row.quoteRef,
            clientName: row.clientName,
            machineName: compactMachineName(row.machineName),
          });
        }
      }
      setQuotes(Array.from(map.values()).sort((a, b) => b.quoteId - a.quoteId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load quotes.");
    } finally {
      setLoadingQuotes(false);
    }
  }

  function applyQuote(quote: QuoteOption | null) {
    if (!quote) return;
    setCustomerName(quote.clientName);
    setQuoteRef(quote.quoteRef);
    setMachineSummary(quote.machineName);
    setProjectName((current) =>
      current.trim() ? current : `${quote.clientName} - ${quote.machineName}`
    );
  }

  async function handleCreate() {
    const resolvedProjectName = projectName.trim();
    const resolvedCustomerName = customerName.trim();
    if (!resolvedProjectName || !resolvedCustomerName) {
      setError("Project name and customer are required.");
      return;
    }

    setCreating(true);
    setError(null);
    try {
      await createProject({
        project_name: resolvedProjectName,
        customer_name: resolvedCustomerName,
        quote_ref: quoteRef.trim() || null,
        machine_summary: machineSummary.trim() || null,
        start_date: startDate.trim() || null,
        target_end_date: targetEndDate.trim() || null,
      });
      await onCreated?.();
      setOpen(false);
      resetForm();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create project.");
    } finally {
      setCreating(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(nextOpen) => {
        setOpen(nextOpen);
        if (nextOpen) {
          void ensureQuotesLoaded();
        } else {
          resetForm();
        }
      }}
    >
      <DialogTrigger asChild>
        <Button>
          <Plus className="mr-2 size-4" />
          New Project
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Create PM Project</DialogTitle>
          <DialogDescription>
            Link a project to an existing quote or create one manually.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <div className="space-y-1.5">
            <label className="text-sm font-medium">Quote (optional)</label>
            <Select
              value={selectedQuoteId}
              onValueChange={(value) => {
                setSelectedQuoteId(value);
                applyQuote(quotes.find((entry) => entry.id === value) ?? null);
              }}
              disabled={loadingQuotes}
            >
              <SelectTrigger>
                <SelectValue placeholder={loadingQuotes ? "Loading quotes..." : "Select a quote"} />
              </SelectTrigger>
              <SelectContent>
                {quotes.map((quote) => (
                  <SelectItem key={quote.id} value={quote.id}>
                    {quote.quoteRef} - {quote.clientName}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <label className="text-sm font-medium">Project Name</label>
            <Input value={projectName} onChange={(event) => setProjectName(event.target.value)} />
          </div>

          <div className="space-y-1.5">
            <label className="text-sm font-medium">Customer Name</label>
            <Input value={customerName} onChange={(event) => setCustomerName(event.target.value)} />
          </div>

          <div className="space-y-1.5">
            <label className="text-sm font-medium">Quote Ref</label>
            <Input value={quoteRef} onChange={(event) => setQuoteRef(event.target.value)} />
          </div>

          <div className="space-y-1.5">
            <label className="text-sm font-medium">Machine Summary</label>
            <Input value={machineSummary} onChange={(event) => setMachineSummary(event.target.value)} />
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Start Date</label>
              <Input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} />
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Target End Date</label>
              <Input
                type="date"
                value={targetEndDate}
                onChange={(event) => setTargetEndDate(event.target.value)}
              />
            </div>
          </div>
        </div>

        {error ? (
          <div className="rounded-md border border-red-200 bg-red-50 p-2 text-sm text-red-700">
            {error}
          </div>
        ) : null}

        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => setOpen(false)} disabled={creating}>
            Cancel
          </Button>
          <Button type="button" onClick={() => void handleCreate()} disabled={creating}>
            {creating ? <Loader2 className="mr-2 size-4 animate-spin" /> : null}
            {creating ? "Creating..." : "Create Project"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
