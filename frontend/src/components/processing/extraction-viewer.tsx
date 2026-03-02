"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { CheckCircle2, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  extractMachineFields,
  fetchGoaForm,
  fetchGoaFormSchema,
  generateDocumentWithOptions,
  listGoaForms,
  saveGoaForm,
  upsertMachineTemplateData,
  type GoaOutputOptions,
  type GoaFormSchemaResponse,
} from "@/lib/api";
import type { LineItem, MachineData } from "@/lib/types";
import { GoaFieldEditor } from "@/components/processing/goa-field-editor";
import { buildSortstarSchema } from "@/components/processing/schema-builders";

interface ExtractionViewerProps {
  machines: MachineData[];
  commonItems: LineItem[];
  fullPdfText: string;
  quoteId?: number;
}

type GoaEditorMode = "needs-review" | "all";

const REVIEW_THRESHOLD = 0.6;
const HIGH_CONFIDENCE_THRESHOLD = 0.8;

function hasTextValue(value: string | undefined): boolean {
  return (value ?? "").trim().length > 0;
}

export function ExtractionViewer(props: ExtractionViewerProps) {
  const { machines, commonItems, fullPdfText } = props;
  const [selectedMachineName, setSelectedMachineName] = useState(
    machines[0]?.machine_name ?? ""
  );
  const [running, setRunning] = useState(false);
  const [saving, setSaving] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [goaSchema, setGoaSchema] = useState<GoaFormSchemaResponse | null>(null);
  const [schemaError, setSchemaError] = useState<string | null>(null);
  const [goaData, setGoaData] = useState<Record<string, string> | null>(null);
  const [sortstarData, setSortstarData] = useState<Record<string, string> | null>(null);
  const [sortstarFieldLabels, setSortstarFieldLabels] = useState<Record<string, string>>({});
  const [goaEditorMode, setGoaEditorMode] = useState<GoaEditorMode>("needs-review");
  const [confidenceScores, setConfidenceScores] = useState<Record<string, number>>({});
  const [machineTemplateId, setMachineTemplateId] = useState<number | null>(null);
  const [savedFilePath, setSavedFilePath] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [builderOptions, setBuilderOptions] = useState<GoaOutputOptions | null>(null);

  const selectedMachine = useMemo(
    () => machines.find((machine) => machine.machine_name === selectedMachineName) ?? machines[0],
    [machines, selectedMachineName]
  );
  const isSortstarMachine = useMemo(
    () =>
      !!selectedMachine?.machine_name &&
      /(sortstar|unscrambler|bottle unscrambler)/i.test(selectedMachine.machine_name),
    [selectedMachine?.machine_name]
  );
  const hasEditorData = isSortstarMachine ? !!sortstarData : !!goaData;
  const sortstarSchema = useMemo(
    () => buildSortstarSchema(sortstarData ?? {}, sortstarFieldLabels, "Sortstar Fields"),
    [sortstarData, sortstarFieldLabels]
  );

  useEffect(() => {
    let active = true;
    setSchemaError(null);
    void fetchGoaFormSchema()
      .then((schema) => {
        if (!active) return;
        setGoaSchema(schema);
      })
      .catch((err) => {
        if (!active) return;
        setSchemaError(err instanceof Error ? err.message : "Failed to load GOA form schema.");
      });

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    setGoaData(null);
    setSortstarData(null);
    setSortstarFieldLabels({});
    setGoaEditorMode("needs-review");
    setConfidenceScores({});
    setSavedFilePath(null);
    setStatusMessage(null);
    setError(null);
    setBuilderOptions(null);
  }, [selectedMachineName]);

  useEffect(() => {
    if (!selectedMachine?.id) {
      setMachineTemplateId(null);
      return;
    }

    let active = true;
    void listGoaForms({ machineId: selectedMachine.id })
      .then(async (forms) => {
        if (!active) return;
        const goaForm =
          forms.find((form) => form.templateType.toUpperCase() === "GOA") ?? forms[0] ?? null;
        setMachineTemplateId(goaForm?.machineTemplateId ?? null);
        if (!goaForm) return;

        try {
          const detail = await fetchGoaForm(goaForm.machineTemplateId);
          if (!active) return;
          setBuilderOptions(detail.outputOptions ?? null);
        } catch {
          if (active) setBuilderOptions(null);
        }
      })
      .catch(() => {
        if (active) {
          setMachineTemplateId(null);
          setBuilderOptions(null);
        }
      });

    return () => {
      active = false;
    };
  }, [selectedMachine?.id]);

  const goaFieldKeys = useMemo(() => {
    if (goaSchema) {
      const keys: string[] = [];
      for (const section of goaSchema.sections) {
        for (const group of section.groups) {
          for (const field of group.fields) {
            keys.push(field.key);
          }
        }
      }
      return keys;
    }
    return Object.keys(goaData ?? {}).sort((a, b) => a.localeCompare(b));
  }, [goaData, goaSchema]);

  const reviewFieldKeys = useMemo(() => {
    if (!goaData) return [];
    return goaFieldKeys
      .filter((key) => {
        const score = confidenceScores[key];
        return typeof score === "number" && score < REVIEW_THRESHOLD;
      })
      .sort((a, b) => a.localeCompare(b));
  }, [confidenceScores, goaData, goaFieldKeys]);

  const populatedFieldCount = useMemo(() => {
    if (!goaData) return 0;
    return goaFieldKeys.reduce((count, key) => {
      const value = goaData[key];
      return hasTextValue(value) ? count + 1 : count;
    }, 0);
  }, [goaData, goaFieldKeys]);

  const highConfidenceCount = useMemo(() => {
    return goaFieldKeys.reduce((count, key) => {
      const score = confidenceScores[key];
      return typeof score === "number" && score >= HIGH_CONFIDENCE_THRESHOLD ? count + 1 : count;
    }, 0);
  }, [confidenceScores, goaFieldKeys]);

  const totalGoaFields = goaFieldKeys.length;
  const showingNeedsReviewOnly = goaEditorMode === "needs-review" && reviewFieldKeys.length > 0;

  const runExtraction = async () => {
    if (!selectedMachine) return;
    setRunning(true);
    setError(null);
    setStatusMessage(null);
    setSavedFilePath(null);
    try {
      const extraction = await extractMachineFields({
        machine_data: selectedMachine,
        common_items: commonItems,
        full_pdf_text: fullPdfText,
        template_contexts: null,
      });
      if (extraction.queued) {
        const queueMessage =
          extraction.queue_message ?? "Processing queued, other extractions in progress.";
        const waitMs =
          typeof extraction.queue_wait_ms === "number" && extraction.queue_wait_ms > 0
            ? extraction.queue_wait_ms
            : null;
        const waitSuffix = waitMs ? ` Waited ${(waitMs / 1000).toFixed(1)}s for an available slot.` : "";
        setStatusMessage(`${queueMessage}${waitSuffix}`);
      }

      const filledData: Record<string, string> = {};
      for (const [key, value] of Object.entries(extraction.filled_data)) {
        filledData[key] = value ?? "";
      }

      const nextConfidenceScores = extraction.confidence_scores ?? {};
      setConfidenceScores(nextConfidenceScores);

      if (isSortstarMachine) {
        setSortstarData(filledData);
        setSortstarFieldLabels(extraction.field_labels ?? {});
        setGoaData(null);
      } else {
        setGoaData(filledData);
        setSortstarData(null);
        setSortstarFieldLabels({});
        const hasReviewFields = Object.values(nextConfidenceScores).some(
          (score) => typeof score === "number" && score < REVIEW_THRESHOLD
        );
        setGoaEditorMode(hasReviewFields ? "needs-review" : "all");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Extraction failed.");
      setSortstarData(null);
      setSortstarFieldLabels({});
      setGoaData(null);
    } finally {
      setRunning(false);
    }
  };

  function getCurrentFormData(): Record<string, string> {
    if (isSortstarMachine) {
      if (!sortstarData || Object.keys(sortstarData).length === 0) {
        throw new Error("Sortstar form data is empty.");
      }
      return sortstarData;
    }

    if (!goaData || Object.keys(goaData).length === 0) {
      throw new Error("GOA form data is empty.");
    }
    return goaData;
  }

  async function ensureMachineTemplateId(currentData: Record<string, string>): Promise<number> {
    if (machineTemplateId) return machineTemplateId;
    if (!selectedMachine?.id) {
      throw new Error("Unable to resolve machine id for GOA save.");
    }

    const upserted = await upsertMachineTemplateData(selectedMachine.id, currentData);
    setMachineTemplateId(upserted.templateId);
    if (upserted.generatedFilePath) {
      setSavedFilePath(upserted.generatedFilePath);
    }
    return upserted.templateId;
  }

  const saveDraft = async () => {
    if (!selectedMachine) return;
    setSaving(true);
    setError(null);
    setStatusMessage(null);
    try {
      const currentData = getCurrentFormData();
      const templateId = await ensureMachineTemplateId(currentData);
      const saved = await saveGoaForm({
        machineTemplateId: templateId,
        filledData: currentData,
        generateOutput: false,
        outputOptions: builderOptions ?? undefined,
      });
      setMachineTemplateId(saved.machineTemplateId);
      setSavedFilePath(saved.filePath || null);
      setStatusMessage(`Draft saved at ${saved.savedAt}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save GOA form.");
    } finally {
      setSaving(false);
    }
  };

  const saveAndGenerate = async () => {
    if (!selectedMachine) return;
    setGenerating(true);
    setError(null);
    setStatusMessage(null);
    try {
      const currentData = getCurrentFormData();
      const templateId = await ensureMachineTemplateId(currentData);
      const outputOptions: GoaOutputOptions = {
        ...(builderOptions ?? {}),
        format: "html",
      };

      await saveGoaForm({
        machineTemplateId: templateId,
        filledData: currentData,
        generateOutput: false,
        outputOptions,
      });

      const generated = await generateDocumentWithOptions({
        machineTemplateId: templateId,
        filledData: currentData,
        options: outputOptions,
      });
      setMachineTemplateId(generated.machineTemplateId);
      setSavedFilePath(generated.filePath || null);
      setStatusMessage(`${generated.format.toUpperCase()} generated at ${generated.generatedAt}.`);

      if (typeof window !== "undefined") {
        window.open(generated.downloadUrl, "_blank", "noopener,noreferrer");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate output document.");
    } finally {
      setGenerating(false);
    }
  };

  const busy = saving || generating;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        {machines.length > 1 && (
          <Select value={selectedMachineName} onValueChange={setSelectedMachineName}>
            <SelectTrigger className="w-full sm:w-80">
              <SelectValue placeholder="Select machine" />
            </SelectTrigger>
            <SelectContent>
              {machines.map((machine, index) => (
                <SelectItem key={`${machine.machine_name}-${index}`} value={machine.machine_name}>
                  {machine.machine_name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
        <Button
          onClick={runExtraction}
          disabled={running || !selectedMachine}
          className="w-full bg-[#c00000] hover:bg-[#a00000] sm:w-auto"
        >
          {running && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
          Run Extraction
        </Button>
      </div>
      {running ? (
        <p className="text-xs text-amber-700">
          Extraction in progress. If other extractions are active, this request waits in queue automatically.
        </p>
      ) : null}

      {schemaError && !isSortstarMachine && (
        <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-800">
          {schemaError}
        </div>
      )}

      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {statusMessage && (
        <div className="rounded-md border border-green-200 bg-green-50 p-3 text-sm text-green-700">
          {statusMessage}
        </div>
      )}

      {hasEditorData ? (
        <>
          {isSortstarMachine ? (
            <div className="rounded-md border bg-white p-4">
              <p className="text-sm font-medium">Sortstar Processing</p>
              <p className="mt-1 text-sm text-muted-foreground">
                Save draft data first, then generate the output document when ready.
              </p>
              <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-center">
                {machineTemplateId && (
                  <Link
                    href={`/goa/${machineTemplateId}`}
                    className="text-sm font-medium text-[#c00000] underline"
                  >
                    Open saved form
                  </Link>
                )}
              </div>
              <div className="mt-3">
                <GoaFieldEditor
                  schema={sortstarSchema}
                  data={sortstarData ?? {}}
                  onChange={setSortstarData}
                  showFieldKeys={false}
                />
              </div>
              <div className="sticky bottom-0 z-10 mt-4 border-t bg-white/95 py-3 backdrop-blur supports-[backdrop-filter]:bg-white/80">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-end">
                  <button
                    type="button"
                    onClick={saveDraft}
                    disabled={busy}
                    className="w-fit text-sm font-medium text-[#c00000] underline underline-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {saving ? "Saving..." : "Save Draft"}
                  </button>
                  <Button
                    onClick={saveAndGenerate}
                    disabled={busy}
                    className="bg-[#c00000] hover:bg-[#a00000]"
                  >
                    {generating && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                    Save & Generate
                  </Button>
                </div>
              </div>
            </div>
          ) : goaSchema ? (
            <div className="space-y-4">
              <div className="flex flex-col gap-2 rounded-md border bg-neutral-50 px-3 py-2 sm:flex-row sm:items-center sm:justify-between">
                <p className="text-sm font-medium">
                  {reviewFieldKeys.length} fields need review | {highConfidenceCount} high confidence
                  {" | "}
                  {populatedFieldCount}/{totalGoaFields} populated
                </p>
                {reviewFieldKeys.length > 0 ? (
                  <button
                    type="button"
                    onClick={() => setGoaEditorMode(showingNeedsReviewOnly ? "all" : "needs-review")}
                    className="w-fit text-sm font-medium text-[#c00000] underline underline-offset-2"
                  >
                    {showingNeedsReviewOnly ? "Show all fields" : "Show only needs review"}
                  </button>
                ) : (
                  <p className="text-sm text-muted-foreground">Showing all fields.</p>
                )}
              </div>

              <GoaFieldEditor
                schema={goaSchema}
                data={goaData ?? {}}
                onChange={setGoaData}
                confidenceScores={confidenceScores}
                visibleFieldKeys={showingNeedsReviewOnly ? reviewFieldKeys : undefined}
              />

              <div className="sticky bottom-0 z-10 border-t bg-white/95 py-3 backdrop-blur supports-[backdrop-filter]:bg-white/80">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-end">
                  <button
                    type="button"
                    onClick={saveDraft}
                    disabled={busy}
                    className="w-fit text-sm font-medium text-[#c00000] underline underline-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {saving ? "Saving..." : "Save Draft"}
                  </button>
                  <Button
                    onClick={saveAndGenerate}
                    disabled={busy}
                    className="bg-[#c00000] hover:bg-[#a00000]"
                  >
                    {generating && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                    Save & Generate
                  </Button>
                </div>
              </div>
            </div>
          ) : (
            <div className="rounded-md border bg-neutral-50 p-4 text-sm text-muted-foreground">
              Loading GOA schema...
            </div>
          )}

          {savedFilePath && (
            <div className="flex items-center gap-2 text-green-700">
              <CheckCircle2 className="h-5 w-5" />
              <span className="text-sm font-medium">Output path: {savedFilePath}</span>
            </div>
          )}
        </>
      ) : (
        <div className="rounded-md border bg-neutral-50 p-4 text-sm text-muted-foreground">
          Run extraction to load editable fields.
        </div>
      )}
    </div>
  );
}
