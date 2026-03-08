"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowLeft, Loader2, Save } from "lucide-react";
import { Button } from "@/components/ui/button";
import { DocumentBuilder } from "@/components/processing/document-builder";
import {
  fetchGoaForm,
  fetchGoaFormSchema,
  generateDocumentWithOptions,
  saveGoaForm,
  type GoaFormDetail,
  type GoaOutputOptions,
  type GoaFormSchemaResponse,
} from "@/lib/api";

interface GoaDocumentBuilderPageClientProps {
  machineTemplateId: string;
}

export default function GoaDocumentBuilderPageClient({
  machineTemplateId,
}: GoaDocumentBuilderPageClientProps) {
  const parsedId = Number(machineTemplateId);
  const [detail, setDetail] = useState<GoaFormDetail | null>(null);
  const [goaSchema, setGoaSchema] = useState<GoaFormSchemaResponse | null>(null);
  const [builderOptions, setBuilderOptions] = useState<GoaOutputOptions | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const isSortstarTemplate =
    !!detail &&
    (detail.generatedFilePath?.toLowerCase().endsWith(".docx") ||
      detail.templateType.toLowerCase().includes("sortstar") ||
      /(sortstar|unscrambler|bottle unscrambler)/i.test(detail.machineName));

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

    void Promise.all([fetchGoaForm(parsedId), fetchGoaFormSchema()])
      .then(([formDetail, schema]) => {
        if (!active) return;
        setDetail(formDetail);
        setGoaSchema(schema);
        setBuilderOptions(formDetail.outputOptions ?? null);
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Failed to load document builder.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [parsedId]);

  async function handleSaveSettings() {
    if (!detail) return;
    setSaving(true);
    setError(null);
    setStatusMessage(null);
    try {
      const options: GoaOutputOptions = {
        ...(builderOptions ?? {}),
        format: "html",
      };

      const saved = await saveGoaForm({
        machineTemplateId: detail.machineTemplateId,
        filledData: detail.templateData,
        generateOutput: false,
        outputOptions: options,
      });

      setStatusMessage(`Builder settings saved at ${saved.savedAt}.`);
      setBuilderOptions(options);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save builder settings.");
    } finally {
      setSaving(false);
    }
  }

  async function handleGenerateHtml() {
    if (!detail) return;
    setGenerating(true);
    setError(null);
    setStatusMessage(null);
    try {
      const outputOptions: GoaOutputOptions = {
        ...(builderOptions ?? {}),
        format: "html",
      };

      await saveGoaForm({
        machineTemplateId: detail.machineTemplateId,
        filledData: detail.templateData,
        generateOutput: false,
        outputOptions,
      });

      const generated = await generateDocumentWithOptions({
        machineTemplateId: detail.machineTemplateId,
        filledData: detail.templateData,
        options: outputOptions,
      });

      setStatusMessage(`HTML generated at ${generated.generatedAt}.`);
      if (typeof window !== "undefined") {
        window.open(generated.downloadUrl, "_blank", "noopener,noreferrer");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate HTML.");
    } finally {
      setGenerating(false);
    }
  }

  if (loading) {
    return (
      <div className="rounded-md border bg-white p-8 text-sm text-muted-foreground">
        Loading document builder...
      </div>
    );
  }

  if (error && !detail) {
    return (
      <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
        Failed to load document builder: {error}
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

  if (isSortstarTemplate) {
    return (
      <div className="space-y-4">
        <Button variant="ghost" size="sm" asChild>
          <Link href={`/goa/${detail.machineTemplateId}`}>
            <ArrowLeft className="mr-1 size-4" />
            Back to GOA Form
          </Link>
        </Button>
        <div className="rounded-md border bg-neutral-50 p-4 text-sm text-muted-foreground">
          Document Builder is currently available for standard GOA templates. Sortstar uses
          its dedicated output layout.
        </div>
      </div>
    );
  }

  if (!goaSchema) {
    return (
      <div className="rounded-md border bg-white p-8 text-sm text-muted-foreground">
        GOA schema not available.
      </div>
    );
  }

  const busy = saving || generating;

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="sm" asChild>
            <Link href={`/goa/${detail.machineTemplateId}`}>
              <ArrowLeft className="mr-1 size-4" />
              Back to GOA Form
            </Link>
          </Button>
          <div>
            <h2 className="text-2xl font-semibold tracking-tight">Document Builder</h2>
            <p className="text-sm text-muted-foreground">
              {detail.machineName} - Template #{detail.machineTemplateId}
            </p>
          </div>
        </div>
        <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row sm:items-center">
          <Button onClick={handleSaveSettings} disabled={busy} variant="outline">
            {saving ? <Loader2 className="mr-1 size-4 animate-spin" /> : <Save className="mr-1 size-4" />}
            Save Builder Settings
          </Button>
          <Button onClick={handleGenerateHtml} disabled={busy} className="bg-[#c00000] hover:bg-[#a00000]">
            {generating && <Loader2 className="mr-1 size-4 animate-spin" />}
            Generate & Download HTML
          </Button>
        </div>
      </div>

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

      <DocumentBuilder
        schema={goaSchema}
        data={detail.templateData}
        initialOptions={builderOptions}
        onOptionsChange={setBuilderOptions}
      />
    </div>
  );
}
