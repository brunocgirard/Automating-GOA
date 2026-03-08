"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Save } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { GoaFieldEditor } from "@/components/processing/goa-field-editor";
import { buildSortstarSchema } from "@/components/processing/schema-builders";
import {
  fetchGoaForm,
  fetchGoaFormSchema,
  generateDocumentWithOptions,
  saveGoaForm,
  type GoaOutputOptions,
  type GoaFormDetail,
  type GoaFormSchemaResponse,
} from "@/lib/api";

interface GoaFormPageClientProps {
  machineTemplateId: string;
}

export default function GoaFormPageClient({ machineTemplateId }: GoaFormPageClientProps) {
  const parsedId = Number(machineTemplateId);
  const [detail, setDetail] = useState<GoaFormDetail | null>(null);
  const [goaSchema, setGoaSchema] = useState<GoaFormSchemaResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [schemaError, setSchemaError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [goaData, setGoaData] = useState<Record<string, string>>({});
  const [sortstarData, setSortstarData] = useState<Record<string, string>>({});
  const [builderOptions, setBuilderOptions] = useState<GoaOutputOptions | null>(null);

  const isSortstarEditor =
    !!detail &&
    (detail.generatedFilePath?.toLowerCase().endsWith(".docx") ||
      detail.templateType.toLowerCase().includes("sortstar") ||
      /(sortstar|unscrambler|bottle unscrambler)/i.test(detail.machineName));
  const sortstarSchema = useMemo(
    () => buildSortstarSchema(sortstarData, detail?.fieldLabels, "Sortstar Fields"),
    [detail?.fieldLabels, sortstarData]
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
        setSchemaError(err instanceof Error ? err.message : "Failed to load GOA schema.");
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!Number.isFinite(parsedId)) {
      setError("Invalid GOA form id.");
      setLoading(false);
      return;
    }

    let active = true;
    setLoading(true);
    setError(null);
    setStatusMessage(null);

    void fetchGoaForm(parsedId)
      .then((response) => {
        if (!active) return;
        setDetail(response);
        setGoaData(response.templateData ?? {});
        setSortstarData(response.templateData ?? {});
        setBuilderOptions(response.outputOptions ?? null);
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Failed to load GOA form.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [parsedId]);

  function getCurrentData(): Record<string, string> {
    const data = isSortstarEditor ? sortstarData : goaData;
    if (!data || Object.keys(data).length === 0) {
      throw new Error("GOA form data is empty.");
    }
    return data;
  }

  function withEditorOutputDefaults(
    current: GoaOutputOptions | null | undefined
  ): GoaOutputOptions {
    return {
      includedSections: current?.includedSections,
      hideEmptySections: current?.hideEmptySections ?? false,
      hideEmptyFields: current?.hideEmptyFields ?? false,
      pureOutput: current?.pureOutput ?? false,
      labelOverrides: current?.labelOverrides ?? {},
      format: "html",
    };
  }

  function handleLabelOverridesChange(nextLabelOverrides: Record<string, string>) {
    setBuilderOptions((current) => ({
      ...withEditorOutputDefaults(current),
      labelOverrides: nextLabelOverrides,
      format: "html",
    }));
  }

  function handlePureOutputToggle(checked: boolean) {
    setBuilderOptions((current) => ({
      ...withEditorOutputDefaults(current),
      pureOutput: checked,
      format: "html",
    }));
  }

  async function handleSave() {
    if (!detail) return;
    setSaving(true);
    setError(null);
    setStatusMessage(null);
    try {
      const filledData = getCurrentData();
      const saved = await saveGoaForm({
        machineTemplateId: detail.machineTemplateId,
        filledData,
        generateOutput: false,
        outputOptions: builderOptions ?? undefined,
      });

      setDetail((prev) =>
        prev
          ? {
              ...prev,
              processingDate: saved.savedAt,
              templateData: filledData,
              html: saved.html,
            }
          : prev
      );
      setStatusMessage(`Draft saved at ${saved.savedAt}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save GOA form.");
    } finally {
      setSaving(false);
    }
  }

  async function handleGenerate() {
    if (!detail) return;
    setGenerating(true);
    setError(null);
    setStatusMessage(null);
    try {
      const filledData = getCurrentData();
      const outputOptions: GoaOutputOptions = isSortstarEditor
        ? { format: "html" }
        : withEditorOutputDefaults(builderOptions);
      await saveGoaForm({
        machineTemplateId: detail.machineTemplateId,
        filledData,
        generateOutput: false,
        outputOptions,
      });

      const generated = await generateDocumentWithOptions({
        machineTemplateId: detail.machineTemplateId,
        filledData,
        options: outputOptions,
      });
      setDetail((prev) =>
        prev
          ? {
              ...prev,
              processingDate: generated.generatedAt,
              generatedFilePath: generated.filePath,
              templateData: filledData,
            }
          : prev
      );
      const generatedFormat = generated.format.toUpperCase();
      setStatusMessage(`${generatedFormat} generated at ${generated.generatedAt}.`);
      if (typeof window !== "undefined") {
        window.open(generated.downloadUrl, "_blank", "noopener,noreferrer");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate document.");
    } finally {
      setGenerating(false);
    }
  }

  if (loading) {
    return (
      <div className="rounded-md border bg-white p-8 text-sm text-muted-foreground">
        Loading GOA form...
      </div>
    );
  }

  if (error && !detail) {
    return (
      <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
        Failed to load GOA form: {error}
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="rounded-md border bg-white p-8 text-sm text-muted-foreground">
        GOA form not found.
      </div>
    );
  }

  const busy = saving || generating;
  const pureOutputEnabled = builderOptions?.pureOutput === true;

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <Button variant="ghost" size="sm" asChild>
            <Link href="/">
              <ArrowLeft className="mr-1 size-4" />
              Back
            </Link>
          </Button>
          <div>
            <h2 className="text-2xl font-semibold tracking-tight">{detail.machineName}</h2>
            <p className="text-sm text-muted-foreground">
              {detail.quoteRef} - Template #{detail.machineTemplateId}
            </p>
          </div>
        </div>
        <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row sm:items-center">
          <Button onClick={handleSave} disabled={busy} variant="outline" className="w-full sm:w-auto">
            <Save className="mr-1 size-4" />
            {saving ? "Saving..." : "Save Draft"}
          </Button>
          <Button onClick={handleGenerate} disabled={busy} className="w-full bg-[#c00000] hover:bg-[#a00000] sm:w-auto">
            {generating
              ? "Generating..."
              : isSortstarEditor
                ? "Generate & Download DOCX"
                : "Generate & Download HTML"}
          </Button>
        </div>
      </div>

      {schemaError && !isSortstarEditor && (
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

      {!isSortstarEditor ? (
        <div className="rounded-md border bg-white p-3">
          <label className="inline-flex items-start gap-2 text-sm">
            <Checkbox
              checked={pureOutputEnabled}
              onCheckedChange={(checked) => handlePureOutputToggle(checked === true)}
            />
            <span>
              Generate pure output HTML (strip edit UI, autosave, and localStorage scripts).
              <span className="block text-xs text-muted-foreground">
                When enabled, a backup is also saved as <code>.interactive.backup.html</code>.
              </span>
            </span>
          </label>
        </div>
      ) : null}

      {isSortstarEditor ? (
        <div className="space-y-4">
          <div className="rounded-md border bg-white p-3">
            <p className="text-sm text-muted-foreground">Edit Sortstar fields directly below.</p>
            <div className="mt-3">
              <GoaFieldEditor
                schema={sortstarSchema}
                data={sortstarData}
                onChange={setSortstarData}
                showFieldKeys={false}
              />
            </div>
          </div>
        </div>
      ) : goaSchema ? (
        <GoaFieldEditor
          schema={goaSchema}
          data={goaData}
          onChange={setGoaData}
          showTableOfContents
          labelOverrides={builderOptions?.labelOverrides}
          onLabelOverridesChange={handleLabelOverridesChange}
          editableLabels
        />
      ) : (
        <div className="rounded-md border bg-neutral-50 p-4 text-sm text-muted-foreground">
          Loading GOA schema...
        </div>
      )}
    </div>
  );
}
