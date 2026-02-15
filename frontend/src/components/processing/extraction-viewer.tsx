"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, Loader2, SlidersHorizontal } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  extractMachineFields,
  fetchGoaForm,
  fetchGoaFormSchema,
  generateDocumentWithOptions,
  listGoaForms,
  saveGoaForm,
  upsertMachineTemplateData,
  type GoaFormSchemaField,
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

type GoaEditorMode = "summary" | "needs-review" | "all";

const REVIEW_THRESHOLD = 0.6;
const HIGH_CONFIDENCE_THRESHOLD = 0.8;

function formatSuggestion(suggestion: Record<string, unknown>): string {
  const reason = suggestion.reason;
  const field = suggestion.field;
  if (typeof field === "string" && typeof reason === "string") {
    return `${field}: ${reason}`;
  }
  if (typeof reason === "string") return reason;
  return JSON.stringify(suggestion);
}

function hasTextValue(value: string | undefined): boolean {
  return (value ?? "").trim().length > 0;
}

export function ExtractionViewer({
  machines,
  commonItems,
  fullPdfText,
  quoteId,
}: ExtractionViewerProps) {
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
  const [goaEditorMode, setGoaEditorMode] = useState<GoaEditorMode>("summary");
  const [confidenceScores, setConfidenceScores] = useState<Record<string, number>>({});
  const [suggestions, setSuggestions] = useState<string[]>([]);
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
    () => buildSortstarSchema(sortstarData ?? {}, undefined, "Sortstar Fields"),
    [sortstarData]
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
    setGoaEditorMode("summary");
    setConfidenceScores({});
    setSuggestions([]);
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

  const fieldMetaByKey = useMemo(() => {
    const map = new Map<string, GoaFormSchemaField>();
    if (!goaSchema) return map;
    for (const section of goaSchema.sections) {
      for (const group of section.groups) {
        for (const field of group.fields) {
          map.set(field.key, field);
        }
      }
    }
    return map;
  }, [goaSchema]);

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

  const reviewFields = useMemo(() => {
    if (!goaData) return [];
    return goaFieldKeys
      .filter((key) => {
        const score = confidenceScores[key];
        return typeof score === "number" && score < REVIEW_THRESHOLD;
      })
      .map((key) => ({
        key,
        label: fieldMetaByKey.get(key)?.label ?? key,
        value: goaData[key] ?? "",
        confidence: confidenceScores[key] ?? null,
      }));
  }, [confidenceScores, fieldMetaByKey, goaData, goaFieldKeys]);

  const reviewFieldKeys = useMemo(() => reviewFields.map((field) => field.key), [reviewFields]);

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

      const filledData: Record<string, string> = {};
      for (const [key, value] of Object.entries(extraction.filled_data)) {
        filledData[key] = value ?? "";
      }

      setConfidenceScores(extraction.confidence_scores ?? {});
      setSuggestions(extraction.suggestions.map(formatSuggestion));

      if (isSortstarMachine) {
        setSortstarData(filledData);
        setGoaData(null);
      } else {
        setGoaData(filledData);
        setSortstarData(null);
        setGoaEditorMode("summary");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Extraction failed.");
      setSortstarData(null);
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
            </div>
          ) : goaSchema ? (
            <>
              {goaEditorMode === "summary" ? (
                <Card>
                  <CardHeader>
                    <CardTitle className="text-base">
                      Extraction Complete - {populatedFieldCount}/{totalGoaFields} fields populated
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="flex flex-col gap-3 rounded-md border bg-neutral-50 p-3 sm:flex-row sm:items-center sm:justify-between">
                      <div className="flex items-start gap-2">
                        <AlertTriangle className="mt-0.5 size-4 text-amber-600" />
                        <div className="text-sm">
                          <p className="font-medium">
                            {reviewFields.length} fields need review
                          </p>
                          <p className="text-muted-foreground">
                            Low-confidence fields are highlighted for quick correction.
                          </p>
                        </div>
                      </div>
                      <Button
                        variant="outline"
                        onClick={() =>
                          setGoaEditorMode(reviewFields.length > 0 ? "needs-review" : "all")
                        }
                      >
                        {reviewFields.length > 0 ? "Review Now" : "Edit All Fields"}
                      </Button>
                    </div>

                    <div className="flex flex-col gap-3 rounded-md border bg-neutral-50 p-3 sm:flex-row sm:items-center sm:justify-between">
                      <div className="flex items-start gap-2">
                        <CheckCircle2 className="mt-0.5 size-4 text-green-600" />
                        <div className="text-sm">
                          <p className="font-medium">{highConfidenceCount} fields are high confidence</p>
                          <p className="text-muted-foreground">
                            Open the full editor to inspect every GOA field.
                          </p>
                        </div>
                      </div>
                      <Button variant="outline" onClick={() => setGoaEditorMode("all")}>
                        Show All Fields
                      </Button>
                    </div>

                    {reviewFields.length > 0 ? (
                      <div className="rounded-md border p-3">
                        <p className="mb-2 text-sm font-medium">Needs Review</p>
                        <div className="space-y-2">
                          {reviewFields.slice(0, 8).map((field) => (
                            <div
                              key={field.key}
                              className="flex flex-col gap-1 rounded border bg-amber-50/40 p-2 text-sm sm:flex-row sm:items-center sm:justify-between"
                            >
                              <div>
                                <p className="font-medium">{field.label}</p>
                                <p className="text-xs text-muted-foreground">{field.value || "(empty)"}</p>
                              </div>
                              <div className="text-xs text-amber-700">
                                conf:{" "}
                                {typeof field.confidence === "number"
                                  ? field.confidence.toFixed(2)
                                  : "n/a"}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : (
                      <div className="rounded-md border bg-green-50 p-3 text-sm text-green-700">
                        No low-confidence fields were flagged in this extraction.
                      </div>
                    )}

                    <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
                      <Button onClick={saveDraft} disabled={busy} variant="outline">
                        {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                        Save Draft
                      </Button>
                      {machineTemplateId && !isSortstarMachine && (
                        <Button variant="outline" asChild>
                          <Link href={`/goa/${machineTemplateId}/builder`}>
                            <SlidersHorizontal className="mr-2 h-4 w-4" />
                            Open Document Builder
                          </Link>
                        </Button>
                      )}
                      <Button
                        onClick={saveAndGenerate}
                        disabled={busy}
                        className="bg-[#c00000] hover:bg-[#a00000]"
                      >
                        {generating && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                        {isSortstarMachine ? "Save & Download DOCX" : "Save & Download HTML"}
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ) : (
                <div className="space-y-4">
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                    <p className="text-sm text-muted-foreground">
                      {goaEditorMode === "needs-review"
                        ? "Showing low-confidence fields only."
                        : "Showing all GOA fields."}
                    </p>
                    <Button variant="ghost" onClick={() => setGoaEditorMode("summary")}>
                      Back to Review Summary
                    </Button>
                  </div>
                  <GoaFieldEditor
                    schema={goaSchema}
                    data={goaData ?? {}}
                    onChange={setGoaData}
                    confidenceScores={confidenceScores}
                    visibleFieldKeys={
                      goaEditorMode === "needs-review" && reviewFieldKeys.length > 0
                        ? reviewFieldKeys
                        : undefined
                    }
                  />
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
                    <Button onClick={saveDraft} disabled={busy} variant="outline">
                      {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                      Save Draft
                    </Button>
                    {machineTemplateId && !isSortstarMachine && (
                      <Button variant="outline" asChild>
                        <Link href={`/goa/${machineTemplateId}/builder`}>
                          <SlidersHorizontal className="mr-2 h-4 w-4" />
                          Open Document Builder
                        </Link>
                      </Button>
                    )}
                    <Button
                      onClick={saveAndGenerate}
                      disabled={busy}
                      className="bg-[#c00000] hover:bg-[#a00000]"
                    >
                      {generating && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                      {isSortstarMachine ? "Save & Download DOCX" : "Save & Download HTML"}
                    </Button>
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="rounded-md border bg-neutral-50 p-4 text-sm text-muted-foreground">
              Loading GOA schema...
            </div>
          )}

          {suggestions.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Suggestions</CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="list-inside list-disc space-y-1 text-sm text-neutral-600">
                  {suggestions.map((suggestion, index) => (
                    <li key={`${suggestion}-${index}`}>{suggestion}</li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}

          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            {machineTemplateId && (
              <>
                <Link
                  href={`/goa/${machineTemplateId}`}
                  className="text-sm font-medium text-[#c00000] underline"
                >
                  Open saved form
                </Link>
                {!isSortstarMachine && (
                  <Link
                    href={`/goa/${machineTemplateId}/builder`}
                    className="text-sm font-medium text-[#c00000] underline"
                  >
                    Open document builder
                  </Link>
                )}
              </>
            )}

            {quoteId && (
              <Link
                href={`/quotes/${quoteId}/preview`}
                className="text-sm font-medium text-[#c00000] underline"
              >
                View quote preview
              </Link>
            )}
          </div>

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
