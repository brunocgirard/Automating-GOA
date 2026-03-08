"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Pencil, RotateCcw, WandSparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { HtmlPreviewFrame } from "@/components/ui/html-preview-frame";
import {
  fillGoaForm,
  type GoaFormSchemaField,
  type GoaFormSchemaResponse,
  type GoaOutputOptions,
} from "@/lib/api";

type FieldDisplayMode = "all" | "filled";

interface BuilderField {
  key: string;
  label: string;
  type: GoaFormSchemaField["type"];
  value: string;
  filled: boolean;
  sectionId: string;
  sectionTitle: string;
}

interface BuilderSection {
  id: string;
  title: string;
  totalCount: number;
  filledCount: number;
  fields: BuilderField[];
}

interface DocumentBuilderProps {
  schema: GoaFormSchemaResponse;
  data: Record<string, string>;
  initialOptions?: GoaOutputOptions | null;
  onOptionsChange?: (options: GoaOutputOptions) => void;
  className?: string;
}

const CHECKBOX_TRUE_VALUES = new Set(["YES", "TRUE", "ON", "1", "Y", "CHECKED"]);

function fieldHasValue(field: GoaFormSchemaField, value: string | undefined): boolean {
  const normalized = (value ?? "").trim();
  if (!normalized) return false;
  if (field.type !== "checkbox") return true;
  return CHECKBOX_TRUE_VALUES.has(normalized.toUpperCase());
}

function buildSections(schema: GoaFormSchemaResponse, data: Record<string, string>): BuilderSection[] {
  const sections: BuilderSection[] = [];

  for (const section of schema.sections) {
    const fields: BuilderField[] = [];
    let filledCount = 0;

    for (const group of section.groups) {
      for (const field of group.fields) {
        const value = data[field.key] ?? "";
        const filled = fieldHasValue(field, value);
        if (filled) filledCount += 1;
        fields.push({
          key: field.key,
          label: field.label,
          type: field.type,
          value,
          filled,
          sectionId: section.id,
          sectionTitle: section.title,
        });
      }
    }

    sections.push({
      id: section.id,
      title: section.title,
      totalCount: fields.length,
      filledCount,
      fields,
    });
  }

  return sections;
}

function normalizeLabelOverrides(overrides: Record<string, string>): Record<string, string> {
  const result: Record<string, string> = {};
  for (const [key, value] of Object.entries(overrides)) {
    const cleanKey = key.trim();
    const cleanValue = value.trim();
    if (!cleanKey || !cleanValue) continue;
    result[cleanKey] = cleanValue;
  }
  return result;
}

function setBodyClass(html: string, className: string, enabled: boolean): string {
  if (!html || typeof DOMParser === "undefined") return html;
  try {
    const parser = new DOMParser();
    const parsed = parser.parseFromString(html, "text/html");
    if (enabled) {
      parsed.body.classList.add(className);
    } else {
      parsed.body.classList.remove(className);
    }
    return `<!doctype html>\n${parsed.documentElement.outerHTML}`;
  } catch {
    return html;
  }
}

export function DocumentBuilder({
  schema,
  data,
  initialOptions,
  onOptionsChange,
  className,
}: DocumentBuilderProps) {
  const sections = useMemo(() => buildSections(schema, data), [data, schema]);
  const defaultSectionIds = useMemo(
    () => sections.filter((section) => section.filledCount > 0).map((section) => section.id),
    [sections]
  );
  const schemaSignature = useMemo(
    () => sections.map((section) => `${section.id}:${section.totalCount}`).join("|"),
    [sections]
  );
  const normalizedInitialOptions = useMemo<{
    includedSections: string[];
    fieldDisplayMode: FieldDisplayMode;
    labelOverrides: Record<string, string>;
  }>(
    () => ({
      includedSections: (initialOptions?.includedSections ?? []).filter((sectionId) => sectionId.trim().length > 0),
      fieldDisplayMode: initialOptions?.hideEmptyFields === false ? "all" : "filled",
      labelOverrides: normalizeLabelOverrides(initialOptions?.labelOverrides ?? {}),
    }),
    [initialOptions]
  );
  const initialOptionsSignature = useMemo(
    () =>
      JSON.stringify({
        includedSections: normalizedInitialOptions.includedSections,
        fieldDisplayMode: normalizedInitialOptions.fieldDisplayMode,
        labelOverrides: normalizedInitialOptions.labelOverrides,
      }),
    [normalizedInitialOptions]
  );
  const computedInitialBuilderState = useMemo(() => {
    const availableSectionIds = new Set(sections.map((section) => section.id));
    const requestedSections = normalizedInitialOptions.includedSections.filter((sectionId) =>
      availableSectionIds.has(sectionId)
    );
    return {
      includedSectionIds: requestedSections.length > 0 ? requestedSections : defaultSectionIds,
      fieldDisplayMode: normalizedInitialOptions.fieldDisplayMode,
      labelOverrides: normalizedInitialOptions.labelOverrides,
    };
  }, [defaultSectionIds, normalizedInitialOptions, sections]);
  const computedInitialBuilderStateRef = useRef(computedInitialBuilderState);
  useEffect(() => {
    computedInitialBuilderStateRef.current = computedInitialBuilderState;
  }, [computedInitialBuilderState]);
  const [includedSectionIds, setIncludedSectionIds] = useState<string[]>(
    () => computedInitialBuilderState.includedSectionIds
  );
  const [fieldDisplayMode, setFieldDisplayMode] = useState<FieldDisplayMode>(
    () => computedInitialBuilderState.fieldDisplayMode
  );
  const [labelOverrides, setLabelOverrides] = useState<Record<string, string>>(
    () => computedInitialBuilderState.labelOverrides
  );
  const [editingSectionId, setEditingSectionId] = useState<string | null>(null);
  const [editingFieldKey, setEditingFieldKey] = useState<string | null>(null);
  const [sectionQuery, setSectionQuery] = useState("");
  const [fieldQuery, setFieldQuery] = useState("");
  const [fieldSectionFilter, setFieldSectionFilter] = useState("__all__");
  const [previewHtml, setPreviewHtml] = useState("");
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [printPreviewMode, setPrintPreviewMode] = useState(false);
  const previewRequestRef = useRef(0);

  useEffect(() => {
    const nextState = computedInitialBuilderStateRef.current;
    const resetId = window.setTimeout(() => {
      setIncludedSectionIds(nextState.includedSectionIds);
      setFieldDisplayMode(nextState.fieldDisplayMode);
      setLabelOverrides(nextState.labelOverrides);
      setEditingSectionId(null);
      setEditingFieldKey(null);
      setSectionQuery("");
      setFieldQuery("");
      setFieldSectionFilter("__all__");
    }, 0);

    return () => {
      clearTimeout(resetId);
    };
  }, [initialOptionsSignature, schemaSignature]);

  const includedSectionIdSet = useMemo(() => new Set(includedSectionIds), [includedSectionIds]);

  const cleanLabelOverrides = useMemo(() => normalizeLabelOverrides(labelOverrides), [labelOverrides]);
  const visibleSections = useMemo(() => {
    const query = sectionQuery.trim().toLowerCase();
    if (!query) return sections;

    return sections.filter((section) => {
      const sectionLabel = (cleanLabelOverrides[section.id] ?? section.title).trim() || section.title;
      return (
        section.id.toLowerCase().includes(query) ||
        section.title.toLowerCase().includes(query) ||
        sectionLabel.toLowerCase().includes(query)
      );
    });
  }, [cleanLabelOverrides, sectionQuery, sections]);
  const fieldSectionOptions = useMemo(
    () => sections.filter((section) => includedSectionIdSet.has(section.id)),
    [includedSectionIdSet, sections]
  );
  const effectiveFieldSectionFilter = useMemo(() => {
    if (fieldSectionFilter === "__all__") return "__all__";
    if (fieldSectionOptions.some((section) => section.id === fieldSectionFilter)) {
      return fieldSectionFilter;
    }
    return "__all__";
  }, [fieldSectionFilter, fieldSectionOptions]);

  const builderOptions = useMemo<GoaOutputOptions>(
    () => ({
      includedSections: includedSectionIds,
      hideEmptySections: false,
      hideEmptyFields: fieldDisplayMode === "filled",
      labelOverrides: cleanLabelOverrides,
      format: "html",
    }),
    [cleanLabelOverrides, fieldDisplayMode, includedSectionIds]
  );
  const optionsSignature = useMemo(() => JSON.stringify(builderOptions), [builderOptions]);

  useEffect(() => {
    onOptionsChange?.(builderOptions);
  }, [builderOptions, onOptionsChange, optionsSignature]);

  const visibleFields = useMemo(() => {
    const query = fieldQuery.trim().toLowerCase();
    const fields = sections
      .filter((section) => includedSectionIdSet.has(section.id))
      .filter((section) => effectiveFieldSectionFilter === "__all__" || section.id === effectiveFieldSectionFilter)
      .flatMap((section) => section.fields)
      .filter((field) => (fieldDisplayMode === "filled" ? field.filled : true));

    if (!query) return fields;
    return fields.filter((field) => {
      const label = (cleanLabelOverrides[field.key] ?? field.label).toLowerCase();
      return (
        field.key.toLowerCase().includes(query) ||
        label.includes(query) ||
        field.sectionTitle.toLowerCase().includes(query) ||
        field.value.toLowerCase().includes(query)
      );
    });
  }, [cleanLabelOverrides, effectiveFieldSectionFilter, fieldDisplayMode, fieldQuery, includedSectionIdSet, sections]);

  useEffect(() => {
    const requestId = previewRequestRef.current + 1;
    previewRequestRef.current = requestId;

    const timeout = window.setTimeout(() => {
      setPreviewLoading(true);
      setPreviewError(null);
      void fillGoaForm(data, builderOptions)
        .then((response) => {
          if (previewRequestRef.current !== requestId) return;
          setPreviewHtml(response.html);
        })
        .catch((err) => {
          if (previewRequestRef.current !== requestId) return;
          setPreviewError(err instanceof Error ? err.message : "Failed to render preview.");
        })
        .finally(() => {
          if (previewRequestRef.current !== requestId) return;
          setPreviewLoading(false);
        });
    }, 240);

    return () => {
      clearTimeout(timeout);
    };
  }, [builderOptions, data]);

  const previewFrameHtml = useMemo(
    () => setBodyClass(previewHtml, "print-preview", printPreviewMode),
    [previewHtml, printPreviewMode]
  );

  function toggleSection(sectionId: string, checked: boolean) {
    setIncludedSectionIds((current) => {
      if (checked) {
        if (current.includes(sectionId)) return current;
        return [...current, sectionId];
      }
      return current.filter((value) => value !== sectionId);
    });
  }

  function applyAutoHideEmptySections() {
    setIncludedSectionIds(sections.filter((section) => section.filledCount > 0).map((section) => section.id));
  }

  function selectAllSections() {
    setIncludedSectionIds(sections.map((section) => section.id));
  }

  function clearOverrides() {
    setLabelOverrides({});
    setEditingSectionId(null);
    setEditingFieldKey(null);
  }

  function updateOverride(key: string, value: string) {
    setLabelOverrides((current) => ({
      ...current,
      [key]: value,
    }));
  }

  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle className="text-base">Document Builder</CardTitle>
      </CardHeader>
      <CardContent>
        <Tabs defaultValue="sections" className="space-y-4">
          <TabsList>
            <TabsTrigger value="sections">Sections</TabsTrigger>
            <TabsTrigger value="fields">Field Labels</TabsTrigger>
            <TabsTrigger value="preview">Preview</TabsTrigger>
          </TabsList>

          <TabsContent value="sections" className="space-y-3">
            <div className="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
              <div className="flex flex-wrap items-center gap-2">
                <Button type="button" variant="outline" size="sm" onClick={selectAllSections}>
                  Select All
                </Button>
                <Button type="button" variant="outline" size="sm" onClick={applyAutoHideEmptySections}>
                  <WandSparkles className="mr-1 h-4 w-4" />
                  Auto (hide empty)
                </Button>
                <Button type="button" variant="ghost" size="sm" onClick={clearOverrides}>
                  <RotateCcw className="mr-1 h-4 w-4" />
                  Clear Renames
                </Button>
              </div>
              <Input
                value={sectionQuery}
                onChange={(event) => setSectionQuery(event.target.value)}
                placeholder="Filter sections..."
                className="h-8 w-full lg:w-64"
              />
            </div>

            <div className="space-y-2">
              {visibleSections.length === 0 ? (
                <div className="rounded-md border bg-neutral-50 p-3 text-sm text-muted-foreground">
                  No sections match the current filter.
                </div>
              ) : (
                visibleSections.map((section) => {
                  const sectionOverride = labelOverrides[section.id] ?? "";
                  const sectionLabel = sectionOverride.trim() || section.title;
                  const isIncluded = includedSectionIdSet.has(section.id);

                  return (
                    <div key={section.id} className="rounded-md border p-3">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <label className="inline-flex items-center gap-2 text-sm font-medium">
                          <Checkbox
                            checked={isIncluded}
                            onCheckedChange={(checked) => toggleSection(section.id, checked === true)}
                          />
                          <span>{sectionLabel}</span>
                        </label>
                        <span className="text-xs text-muted-foreground">
                          {section.filledCount}/{section.totalCount} fields
                        </span>
                      </div>
                      <div className="mt-2 flex flex-wrap items-center gap-2">
                        <Button
                          type="button"
                          size="sm"
                          variant="ghost"
                          onClick={() =>
                            setEditingSectionId((current) => (current === section.id ? null : section.id))
                          }
                        >
                          <Pencil className="mr-1 h-4 w-4" />
                          Rename
                        </Button>
                        {editingSectionId === section.id ? (
                          <Input
                            value={sectionOverride}
                            onChange={(event) => updateOverride(section.id, event.target.value)}
                            placeholder={section.title}
                            className="h-8 w-full max-w-sm"
                          />
                        ) : null}
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </TabsContent>

          <TabsContent value="fields" className="space-y-3">
            <div className="flex flex-col gap-2 lg:flex-row lg:items-center lg:justify-between">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium">Field Display</span>
                  <Select
                    value={fieldDisplayMode}
                    onValueChange={(value) => setFieldDisplayMode(value as FieldDisplayMode)}
                  >
                    <SelectTrigger className="h-8 w-44">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All fields</SelectItem>
                      <SelectItem value="filled">Filled only</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium">Section</span>
                  <Select value={effectiveFieldSectionFilter} onValueChange={setFieldSectionFilter}>
                    <SelectTrigger className="h-8 w-56">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="__all__">All included sections</SelectItem>
                      {fieldSectionOptions.map((section) => {
                        const sectionLabel = (cleanLabelOverrides[section.id] ?? section.title).trim() || section.title;
                        return (
                          <SelectItem key={section.id} value={section.id}>
                            {sectionLabel}
                          </SelectItem>
                        );
                      })}
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <Input
                value={fieldQuery}
                onChange={(event) => setFieldQuery(event.target.value)}
                placeholder="Search fields..."
                className="h-8 w-full lg:w-64"
              />
            </div>

            <ScrollArea className="h-72 rounded-md border p-2">
              <div className="space-y-2">
                {visibleFields.length === 0 ? (
                  <div className="rounded-md border bg-neutral-50 p-3 text-sm text-muted-foreground">
                    No fields match the current filter.
                  </div>
                ) : (
                  visibleFields.map((field) => {
                    const fieldOverride = labelOverrides[field.key] ?? "";
                    const fieldLabel = fieldOverride.trim() || field.label;
                    return (
                      <div key={field.key} className="rounded-md border p-2">
                        <div className="flex flex-wrap items-start justify-between gap-2">
                          <div className="min-w-0 flex-1">
                            <p className="text-sm font-medium">{fieldLabel}</p>
                            <p className="text-xs text-muted-foreground">
                              {field.sectionTitle} - {field.key}
                            </p>
                            <p className="truncate text-xs text-neutral-600">
                              {field.value.trim() || "(empty)"}
                            </p>
                          </div>
                          <Button
                            type="button"
                            size="sm"
                            variant="ghost"
                            onClick={() =>
                              setEditingFieldKey((current) => (current === field.key ? null : field.key))
                            }
                          >
                            <Pencil className="mr-1 h-4 w-4" />
                            Rename
                          </Button>
                        </div>
                        {editingFieldKey === field.key ? (
                          <Input
                            value={fieldOverride}
                            onChange={(event) => updateOverride(field.key, event.target.value)}
                            placeholder={field.label}
                            className="mt-2 h-8"
                          />
                        ) : null}
                      </div>
                    );
                  })
                )}
              </div>
            </ScrollArea>
          </TabsContent>

          <TabsContent value="preview">
            {previewLoading ? (
              <div className="rounded-md border bg-neutral-50 p-4 text-sm text-muted-foreground">
                Rendering preview...
              </div>
            ) : previewError ? (
              <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
                {previewError}
              </div>
            ) : (
              <div className="space-y-3">
                <div className="flex justify-end">
                  <Button
                    type="button"
                    size="sm"
                    variant={printPreviewMode ? "default" : "outline"}
                    onClick={() => setPrintPreviewMode((current) => !current)}
                    className="mr-2"
                  >
                    {printPreviewMode ? "Print Preview: On" : "Print Preview: Off"}
                  </Button>
                </div>
                <HtmlPreviewFrame
                  html={previewFrameHtml}
                  title="GOA Document Builder Preview"
                  className="rounded-md"
                  minHeight={760}
                />
              </div>
            )}
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  );
}
