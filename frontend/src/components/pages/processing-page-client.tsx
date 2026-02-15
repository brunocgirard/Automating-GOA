"use client";

import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Card, CardContent } from "@/components/ui/card";
import { StepIndicator } from "@/components/processing/step-indicator";
import { ExtractionViewer } from "@/components/processing/extraction-viewer";
import {
  fetchProcessingArtifacts,
  fetchProcessingMachineData,
  fetchQuotes,
  type QuoteRow,
} from "@/lib/api";
import type { LineItem, MachineData, ProcessingStep } from "@/lib/types";

type MachineOption = {
  key: string;
  label: string;
  machine: MachineData;
};

function createMachineOption(machine: MachineData, index: number): MachineOption {
  const key = machine.id != null ? `id:${machine.id}` : `idx:${index}`;
  const label = machine.machine_name?.trim() || `Machine ${index + 1}`;
  return { key, label, machine };
}

export default function ProcessingPage() {
  const [step, setStep] = useState<ProcessingStep>("load-quote");
  const [quotes, setQuotes] = useState<QuoteRow[]>([]);
  const [selectedQuote, setSelectedQuote] = useState("");
  const [selectedMachineKey, setSelectedMachineKey] = useState("");
  const [quoteFromQuery, setQuoteFromQuery] = useState<string | null>(null);
  const [machineFromQuery, setMachineFromQuery] = useState<number | null>(null);
  const [disableDirectMachineMode, setDisableDirectMachineMode] = useState(false);
  const [machines, setMachines] = useState<MachineData[]>([]);
  const [commonItems, setCommonItems] = useState<LineItem[]>([]);
  const [fullPdfText, setFullPdfText] = useState("");
  const [loadingQuotes, setLoadingQuotes] = useState(true);
  const [loadingArtifacts, setLoadingArtifacts] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const directMachineMode = !disableDirectMachineMode && Boolean(quoteFromQuery && machineFromQuery != null);

  useEffect(() => {
    if (typeof window === "undefined") return;
    queueMicrotask(() => {
      const params = new URLSearchParams(window.location.search);
      const quoteValue = params.get("quote");
      const machineValue = params.get("machine");
      const parsedMachine = Number(machineValue);

      setQuoteFromQuery(quoteValue);
      setSelectedQuote((current) => current || quoteValue || "");
      if (machineValue && Number.isFinite(parsedMachine) && parsedMachine > 0) {
        setMachineFromQuery(parsedMachine);
      } else {
        setMachineFromQuery(null);
      }
    });
  }, []);

  useEffect(() => {
    let active = true;
    const loadQuotes = async () => {
      setLoadingQuotes(true);
      setError(null);
      try {
        const rows = await fetchQuotes();
        if (!active) return;
        setQuotes(rows);
      } catch (err) {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Failed to load quotes.");
      } finally {
        if (active) setLoadingQuotes(false);
      }
    };

    void loadQuotes();

    return () => {
      active = false;
    };
  }, []);

  const quoteOptions = useMemo(() => {
    const map = new Map<number, { id: string; label: string; quoteRef: string }>();
    for (const row of quotes) {
      if (!map.has(row.quoteId)) {
        map.set(row.quoteId, {
          id: String(row.quoteId),
          label: `${row.quoteRef} - ${row.clientName}`,
          quoteRef: row.quoteRef,
        });
      }
    }
    return Array.from(map.values());
  }, [quotes]);

  const machineOptions = useMemo(
    () => machines.map((machine, index) => createMachineOption(machine, index)),
    [machines]
  );
  const effectiveSelectedMachineKey =
    machineOptions.some((option) => option.key === selectedMachineKey)
      ? selectedMachineKey
      : (machineOptions[0]?.key ?? "");

  useEffect(() => {
    if (!directMachineMode || machineFromQuery == null || !quoteFromQuery) return;

    let active = true;
    const loadMachineContext = async () => {
      setStep("load-quote");
      setLoadingArtifacts(true);
      setError(null);
      setMachines([]);
      setCommonItems([]);
      setFullPdfText("");
      try {
        const machineContext = await fetchProcessingMachineData(machineFromQuery);
        if (!active) return;
        setSelectedQuote(quoteFromQuery);
        setMachines([machineContext.machine]);
        setCommonItems(machineContext.commonItems);
        setFullPdfText(machineContext.fullPdfText);
        setStep("process-machine");
      } catch (err) {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Failed to load machine context.");
        setDisableDirectMachineMode(true);
      } finally {
        if (active) setLoadingArtifacts(false);
      }
    };

    void loadMachineContext();

    return () => {
      active = false;
    };
  }, [directMachineMode, machineFromQuery, quoteFromQuery]);

  useEffect(() => {
    if (!selectedQuote || directMachineMode) return;
    const selected = quoteOptions.find((option) => option.id === selectedQuote);
    if (!selected) return;

    let active = true;
    const loadArtifacts = async () => {
      setLoadingArtifacts(true);
      setError(null);
      setMachines([]);
      setCommonItems([]);
      setFullPdfText("");
      try {
        const artifacts = await fetchProcessingArtifacts(selected.quoteRef);
        if (!active) return;
        setMachines(artifacts.machines);
        setCommonItems(artifacts.commonItems);
        setFullPdfText(artifacts.fullPdfText);
        if (quoteFromQuery && machineFromQuery == null) {
          setStep("select-machine");
        }
      } catch (err) {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Failed to load quote data.");
      } finally {
        if (active) setLoadingArtifacts(false);
      }
    };

    void loadArtifacts();

    return () => {
      active = false;
    };
  }, [directMachineMode, machineFromQuery, quoteFromQuery, quoteOptions, selectedQuote]);

  const selectedQuoteOption = useMemo(
    () => quoteOptions.find((option) => option.id === selectedQuote),
    [quoteOptions, selectedQuote]
  );

  const selectedMachine = useMemo(
    () =>
      machineOptions.find((option) => option.key === effectiveSelectedMachineKey)?.machine ??
      machineOptions[0]?.machine,
    [effectiveSelectedMachineKey, machineOptions]
  );

  const selectedQuoteIdNumber = selectedQuote ? Number(selectedQuote) : undefined;

  return (
    <div>
      <h2 className="text-2xl font-semibold tracking-tight">Processing</h2>
      <p className="mt-1 mb-6 text-sm text-neutral-500">
        Process quotes through the GOA extraction pipeline.
      </p>

      <StepIndicator current={step} variant={directMachineMode ? "machine-direct" : "full"} />

      <Card>
        <CardContent className="pt-6">
          {error && (
            <div className="mb-4 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
              {error}
            </div>
          )}

          {directMachineMode && step === "load-quote" && (
            <div className="mx-auto max-w-md space-y-2 rounded-md border bg-neutral-50 p-4 text-sm text-muted-foreground">
              <h3 className="text-base font-semibold text-foreground">Load Machine</h3>
              <p>Loading grouped machine data for direct extraction...</p>
              {loadingArtifacts ? <p className="text-xs">Please wait...</p> : null}
            </div>
          )}

          {!directMachineMode && step === "load-quote" && (
            <div className="mx-auto max-w-md space-y-6">
              <h3 className="text-lg font-semibold">Select Quote</h3>
              <div className="space-y-3">
                <label className="text-sm font-medium">Select existing quote</label>
                <Select value={selectedQuote} onValueChange={setSelectedQuote}>
                  <SelectTrigger>
                    <SelectValue placeholder="Choose a quote..." />
                  </SelectTrigger>
                  <SelectContent>
                    {quoteOptions.map((quote) => (
                      <SelectItem key={quote.id} value={quote.id}>
                        {quote.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {(loadingQuotes || loadingArtifacts) && (
                  <p className="text-xs text-muted-foreground">Loading quote data...</p>
                )}
              </div>
              <div className="flex justify-end">
                <Button
                  onClick={() => setStep("select-machine")}
                  disabled={!selectedQuote || loadingArtifacts}
                  className="w-full bg-[#c00000] hover:bg-[#a00000] sm:w-auto"
                >
                  Next
                </Button>
              </div>
            </div>
          )}

          {!directMachineMode && step === "select-machine" && (
            <div className="mx-auto max-w-md space-y-4">
              <h3 className="text-lg font-semibold">Select Machine</h3>

              {!selectedQuote && (
                <div className="rounded-md border bg-neutral-50 p-4 text-sm text-muted-foreground">
                  Choose a quote first to load available machines.
                </div>
              )}

              {selectedQuote && loadingArtifacts && (
                <div className="rounded-md border bg-neutral-50 p-4 text-sm text-muted-foreground">
                  Loading machines for the selected quote...
                </div>
              )}

              {selectedQuote && !loadingArtifacts && machineOptions.length === 0 && (
                <div className="rounded-md border bg-neutral-50 p-4 text-sm text-muted-foreground">
                  No identified machines found for this quote. Complete machine identification from
                  the dashboard first.
                </div>
              )}

              {selectedQuote && !loadingArtifacts && machineOptions.length > 0 && (
                <>
                  <div className="space-y-3">
                    <label className="text-sm font-medium">Select machine</label>
                    <Select value={effectiveSelectedMachineKey} onValueChange={setSelectedMachineKey}>
                      <SelectTrigger>
                        <SelectValue placeholder="Choose a machine..." />
                      </SelectTrigger>
                      <SelectContent>
                        {machineOptions.map((option) => (
                          <SelectItem key={option.key} value={option.key}>
                            {option.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="rounded-md border bg-neutral-50 p-3 text-sm text-muted-foreground">
                    {selectedQuoteOption?.label ?? selectedQuote}
                  </div>
                </>
              )}

              <div className="flex flex-col gap-2 sm:flex-row sm:justify-between">
                <Button variant="outline" onClick={() => setStep("load-quote")}>
                  Back
                </Button>
                <Button
                  className="bg-[#c00000] hover:bg-[#a00000]"
                  onClick={() => setStep("process-machine")}
                  disabled={!selectedMachine || loadingArtifacts}
                >
                  Continue to Process
                </Button>
              </div>
            </div>
          )}

          {step === "process-machine" &&
            (selectedMachine ? (
              <ExtractionViewer
                machines={[selectedMachine]}
                commonItems={commonItems}
                fullPdfText={fullPdfText}
                quoteId={selectedQuoteIdNumber}
              />
            ) : (
              <div className="rounded-md border bg-neutral-50 p-4 text-sm text-muted-foreground">
                No machine selected. Go back and choose a machine first.
              </div>
            ))}
        </CardContent>
      </Card>
    </div>
  );
}
