"use client";

import { useEffect, useMemo, useState } from "react";
import { Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import type { GoaFormSchemaField, GoaFormSchemaResponse } from "@/lib/api";

interface GoaFieldEditorProps {
  schema: GoaFormSchemaResponse;
  data: Record<string, string>;
  onChange: (next: Record<string, string>) => void;
  confidenceScores?: Record<string, number>;
  visibleFieldKeys?: string[];
  showFieldKeys?: boolean;
  showTableOfContents?: boolean;
  labelOverrides?: Record<string, string>;
  onLabelOverridesChange?: (next: Record<string, string>) => void;
  editableLabels?: boolean;
  className?: string;
}

function isChecked(value: string | undefined): boolean {
  const normalized = (value ?? "").trim().toUpperCase();
  return normalized === "YES" || normalized === "TRUE" || normalized === "ON" || normalized === "1";
}

function confidenceClasses(score: number | undefined): string {
  if (typeof score !== "number") return "border-border bg-background";
  if (score < 0.55) return "border-red-300 bg-red-50/40";
  if (score < 0.8) return "border-amber-300 bg-amber-50/40";
  return "border-green-300 bg-green-50/40";
}

function scoreText(score: number | undefined): string | null {
  if (typeof score !== "number") return null;
  return `${Math.round(score * 100)}%`;
}

function hasFieldValue(field: GoaFormSchemaField, value: string | undefined): boolean {
  if (field.type === "checkbox") {
    return isChecked(value);
  }
  return (value ?? "").trim().length > 0;
}

function sectionAnchorId(sectionId: string): string {
  return `goa-section-${sectionId}`;
}

export function GoaFieldEditor({
  schema,
  data,
  onChange,
  confidenceScores,
  visibleFieldKeys,
  showFieldKeys = true,
  showTableOfContents = false,
  labelOverrides,
  onLabelOverridesChange,
  editableLabels = false,
  className,
}: GoaFieldEditorProps) {
  const [query, setQuery] = useState("");
  const [editingLabels, setEditingLabels] = useState(false);
  const [activeSectionId, setActiveSectionId] = useState<string | null>(null);
  const resolvedLabelOverrides = useMemo(() => labelOverrides ?? {}, [labelOverrides]);
  const canEditLabels = editableLabels && typeof onLabelOverridesChange === "function";

  const allowedFieldKeys = useMemo(() => {
    if (!visibleFieldKeys || visibleFieldKeys.length === 0) return null;
    return new Set(visibleFieldKeys);
  }, [visibleFieldKeys]);

  const normalizedQuery = query.trim().toLowerCase();

  const schemaFieldKeys = useMemo(() => {
    const keys = new Set<string>();
    for (const section of schema.sections) {
      for (const group of section.groups) {
        for (const field of group.fields) {
          keys.add(field.key);
        }
      }
    }
    return keys;
  }, [schema.sections]);

  const sectionStats = useMemo(() => {
    return schema.sections
      .map((section) => {
        const displayTitle = (resolvedLabelOverrides[section.id] ?? section.title).trim() || section.title;
        let totalCount = 0;
        let filledCount = 0;

        for (const group of section.groups) {
          for (const field of group.fields) {
            if (allowedFieldKeys && !allowedFieldKeys.has(field.key)) continue;
            totalCount += 1;
            if (hasFieldValue(field, data[field.key])) {
              filledCount += 1;
            }
          }
        }

        return {
          id: section.id,
          title: section.title,
          displayTitle,
          totalCount,
          filledCount,
        };
      })
      .filter((section) => section.totalCount > 0);
  }, [allowedFieldKeys, data, resolvedLabelOverrides, schema.sections]);

  const filteredSections = useMemo(() => {
    return schema.sections
      .map((section) => {
        const sectionLabel = (resolvedLabelOverrides[section.id] ?? section.title).trim() || section.title;
        const groups = section.groups
          .map((group) => {
            const fields = group.fields.filter((field) => {
              if (allowedFieldKeys && !allowedFieldKeys.has(field.key)) return false;
              const fieldLabel = (resolvedLabelOverrides[field.key] ?? field.label).trim() || field.label;
              if (!normalizedQuery) return true;
              const valueText = (data[field.key] ?? "").toLowerCase();
              return (
                field.key.toLowerCase().includes(normalizedQuery) ||
                fieldLabel.toLowerCase().includes(normalizedQuery) ||
                sectionLabel.toLowerCase().includes(normalizedQuery) ||
                valueText.includes(normalizedQuery)
              );
            });

            if (fields.length === 0) return null;
            return {
              ...group,
              fields,
            };
          })
          .filter((group): group is NonNullable<typeof group> => group !== null);

        if (groups.length === 0) return null;
        return {
          ...section,
          displayTitle: sectionLabel,
          groups,
        };
      })
      .filter((section): section is NonNullable<typeof section> => section !== null);
  }, [allowedFieldKeys, data, normalizedQuery, resolvedLabelOverrides, schema.sections]);

  const visibleSectionIds = useMemo(() => {
    return new Set(filteredSections.map((section) => section.id));
  }, [filteredSections]);

  const tocSections = useMemo(() => {
    return sectionStats.filter((section) => visibleSectionIds.has(section.id));
  }, [sectionStats, visibleSectionIds]);

  const currentActiveSectionId = useMemo(() => {
    if (!showTableOfContents || tocSections.length === 0) return null;
    if (activeSectionId && tocSections.some((section) => section.id === activeSectionId)) {
      return activeSectionId;
    }
    return tocSections[0].id;
  }, [activeSectionId, showTableOfContents, tocSections]);

  const overallProgressText = useMemo(() => {
    const totals = sectionStats.reduce(
      (acc, section) => {
        acc.filled += section.filledCount;
        acc.total += section.totalCount;
        return acc;
      },
      { filled: 0, total: 0 }
    );
    return `${totals.filled} of ${totals.total} fields filled`;
  }, [sectionStats]);

  const extraFields = useMemo(() => {
    const extras: GoaFormSchemaField[] = [];
    const keys = Object.keys(data).sort((a, b) => a.localeCompare(b));
    for (const key of keys) {
      if (schemaFieldKeys.has(key)) continue;
      if (allowedFieldKeys && !allowedFieldKeys.has(key)) continue;
      if (normalizedQuery) {
        const valueText = (data[key] ?? "").toLowerCase();
        const labelText = (resolvedLabelOverrides[key] ?? key).toLowerCase();
        if (
          !key.toLowerCase().includes(normalizedQuery) &&
          !labelText.includes(normalizedQuery) &&
          !valueText.includes(normalizedQuery)
        ) {
          continue;
        }
      }
      extras.push({
        key,
        label: key,
        type: "text",
      });
    }
    return extras;
  }, [allowedFieldKeys, data, normalizedQuery, resolvedLabelOverrides, schemaFieldKeys]);

  const renderedFieldCount = useMemo(() => {
    let total = extraFields.length;
    for (const section of filteredSections) {
      for (const group of section.groups) {
        total += group.fields.length;
      }
    }
    return total;
  }, [extraFields.length, filteredSections]);

  const totalFieldCount = allowedFieldKeys ? allowedFieldKeys.size : schema.fieldCount + extraFields.length;

  function updateField(key: string, value: string) {
    onChange({
      ...data,
      [key]: value,
    });
  }

  function setLabelOverride(key: string, baseLabel: string, nextLabel: string) {
    if (!onLabelOverridesChange) return;

    const normalizedBase = baseLabel.trim();
    const normalizedNext = nextLabel.trim();
    const nextOverrides = { ...resolvedLabelOverrides };

    if (!normalizedNext || normalizedNext === normalizedBase) {
      delete nextOverrides[key];
    } else {
      nextOverrides[key] = normalizedNext;
    }
    onLabelOverridesChange(nextOverrides);
  }

  function renderField(field: GoaFormSchemaField) {
    const value = data[field.key] ?? "";
    const score = confidenceScores?.[field.key];
    const id = `goa-field-${field.key}`;
    const effectiveLabel = (resolvedLabelOverrides[field.key] ?? field.label).trim() || field.label;
    const labelInputValue = resolvedLabelOverrides[field.key] ?? "";

    return (
      <div key={field.key} className={cn("rounded-md border p-3", confidenceClasses(score))}>
        <div className="mb-2 flex items-start justify-between gap-2">
          <label htmlFor={id} className="text-sm font-medium">
            {effectiveLabel}
          </label>
          {showFieldKeys ? <div className="text-xs text-muted-foreground">{field.key}</div> : null}
        </div>

        {field.type === "checkbox" ? (
          <label className="inline-flex items-center gap-2 text-sm" htmlFor={id}>
            <Checkbox
              id={id}
              checked={isChecked(value)}
              onCheckedChange={(checked) => updateField(field.key, checked === true ? "YES" : "NO")}
            />
            <span>{isChecked(value) ? "YES" : "NO"}</span>
          </label>
        ) : field.type === "textarea" ? (
          <textarea
            id={id}
            value={value}
            onChange={(event) => updateField(field.key, event.target.value)}
            className="min-h-24 w-full rounded-md border border-input px-3 py-2 text-sm"
            rows={4}
          />
        ) : (
          <Input
            id={id}
            value={value}
            type="text"
            inputMode={field.type === "number" ? "decimal" : undefined}
            onChange={(event) => updateField(field.key, event.target.value)}
            className="h-9"
          />
        )}

        {scoreText(score) ? (
          <p className="mt-2 text-xs text-muted-foreground">Confidence: {scoreText(score)}</p>
        ) : null}

        {canEditLabels && editingLabels ? (
          <div className="mt-2">
            <Input
              value={labelInputValue}
              onChange={(event) => setLabelOverride(field.key, field.label, event.target.value)}
              placeholder={field.label}
              className="h-8"
            />
          </div>
        ) : null}
      </div>
    );
  }

  function scrollToSection(sectionId: string) {
    const target = document.getElementById(sectionAnchorId(sectionId));
    if (!target) return;
    target.scrollIntoView({ behavior: "smooth", block: "start" });
    setActiveSectionId(sectionId);
  }

  useEffect(() => {
    if (!showTableOfContents || tocSections.length === 0 || typeof window === "undefined") return;

    const observer = new IntersectionObserver(
      (entries) => {
        const visibleEntries = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        const nextSectionId = visibleEntries[0]?.target.getAttribute("data-section-id");
        if (nextSectionId) {
          setActiveSectionId(nextSectionId);
        }
      },
      {
        root: null,
        rootMargin: "-18% 0px -62% 0px",
        threshold: [0.1, 0.35, 0.65],
      }
    );

    const targets: Element[] = [];
    for (const section of tocSections) {
      const el = document.getElementById(sectionAnchorId(section.id));
      if (!el) continue;
      targets.push(el);
      observer.observe(el);
    }

    return () => {
      for (const target of targets) {
        observer.unobserve(target);
      }
      observer.disconnect();
    };
  }, [showTableOfContents, tocSections]);

  return (
    <div className={cn("space-y-4", className)}>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-muted-foreground">
          Editing {renderedFieldCount} of {totalFieldCount} fields
        </p>
        <div className="flex w-full items-center gap-2 sm:w-auto">
          {canEditLabels ? (
            <Button
              type="button"
              size="sm"
              variant={editingLabels ? "default" : "outline"}
              onClick={() => setEditingLabels((current) => !current)}
            >
              {editingLabels ? "Done Editing Labels" : "Edit Labels"}
            </Button>
          ) : null}
          <div className="relative w-full sm:w-80">
            <Search className="pointer-events-none absolute top-2.5 left-3 size-4 text-muted-foreground" />
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search by label, key, or value..."
              className="pl-9"
            />
          </div>
        </div>
      </div>

      {renderedFieldCount === 0 ? (
        <div className="rounded-md border bg-neutral-50 p-4 text-sm text-muted-foreground">
          No fields match the current filter.
        </div>
      ) : (
        <div className={cn(showTableOfContents ? "grid items-start gap-4 xl:grid-cols-[280px_minmax(0,1fr)]" : "")}>
          {showTableOfContents ? (
            <aside className="xl:sticky xl:top-28 xl:max-h-[calc(100vh-8rem)] xl:overflow-auto">
              <div className="rounded-lg border bg-white p-3 shadow-sm">
                <p className="text-xs font-bold tracking-wide text-muted-foreground uppercase">
                  Table of Contents
                </p>
                <p className="mt-2 rounded-md border bg-slate-50 px-2 py-1.5 text-xs font-semibold text-slate-700">
                  {overallProgressText}
                </p>
                <nav className="mt-3 flex flex-col gap-1.5">
                  {tocSections.map((section) => (
                    <button
                      key={section.id}
                      type="button"
                      onClick={() => scrollToSection(section.id)}
                      className={cn(
                        "flex items-center justify-between gap-2 rounded-md border px-2 py-1.5 text-left text-xs transition-colors",
                        currentActiveSectionId === section.id
                          ? "border-red-300 bg-red-50 text-red-900"
                          : "border-slate-200 bg-white text-slate-800 hover:bg-slate-50"
                      )}
                    >
                      <span className="min-w-0 truncate">{section.displayTitle}</span>
                      <span className="shrink-0 text-[11px] font-semibold text-slate-600">
                        {section.filledCount}/{section.totalCount}
                      </span>
                    </button>
                  ))}
                </nav>
              </div>
            </aside>
          ) : null}

          <div className="space-y-4">
            {filteredSections.map((section) => (
              <section
                key={section.id}
                id={sectionAnchorId(section.id)}
                data-section-id={section.id}
                className="scroll-mt-28 rounded-lg border bg-white p-4"
              >
                <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                  <h3 className="text-base font-semibold">{section.displayTitle}</h3>
                  {canEditLabels && editingLabels ? (
                    <Input
                      value={resolvedLabelOverrides[section.id] ?? ""}
                      onChange={(event) => setLabelOverride(section.id, section.title, event.target.value)}
                      placeholder={section.title}
                      className="h-8 w-full sm:w-72"
                    />
                  ) : null}
                </div>
                <div className="mt-3 space-y-3">
                  {section.groups.map((group, groupIndex) => (
                    <div key={`${section.title}-group-${groupIndex}`} className="space-y-3">
                      {group.title ? (
                        <p className="text-sm font-medium text-muted-foreground">{group.title}</p>
                      ) : null}
                      <div className="grid gap-3 lg:grid-cols-2">{group.fields.map(renderField)}</div>
                    </div>
                  ))}
                </div>
              </section>
            ))}

            {extraFields.length > 0 ? (
              <section className="rounded-lg border bg-white p-4">
                <h3 className="text-base font-semibold">Additional Fields</h3>
                <p className="mt-1 text-sm text-muted-foreground">
                  Fields present in saved data but not in the current GOA schema.
                </p>
                <div className="mt-3 grid gap-3 lg:grid-cols-2">{extraFields.map(renderField)}</div>
              </section>
            ) : null}
          </div>
        </div>
      )}
    </div>
  );
}
