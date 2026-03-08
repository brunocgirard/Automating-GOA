import type { GoaFormSchemaField, GoaFormSchemaResponse } from "@/lib/api";

function normalizeCheckboxLike(value: string): boolean {
  const normalized = value.trim().toUpperCase();
  return (
    normalized === "YES" ||
    normalized === "NO" ||
    normalized === "TRUE" ||
    normalized === "FALSE" ||
    normalized === "ON" ||
    normalized === "OFF"
  );
}

function prettyLabel(fieldKey: string): string {
  const withoutSuffix = fieldKey.endsWith("_check") ? fieldKey.slice(0, -6) : fieldKey;
  return withoutSuffix
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function toSectionId(title: string): string {
  const normalized = title.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
  return normalized || "section";
}

type SortstarLocation = {
  section: string;
  group: string | null;
  fieldLabel: string;
};

const SECTION_PRIORITY: Record<string, number> = {
  "GENERAL ORDER ACKNOWLEDGEMENT": 0,
  "Order Identification": 1,
  "Utility Specifications": 2,
  "BASIC SYSTEMS": 3,
  "OPTIONAL SYSTEMS": 4,
  "Option Listing": 5,
  "Additional Fields": 6,
};

function parseHierarchicalLabel(label: string): SortstarLocation | null {
  const parts = label
    .split(">")
    .map((part) => part.trim())
    .filter((part) => part.length > 0);

  if (parts.length < 2) return null;

  return {
    section: parts[0],
    group: parts.length > 2 ? parts.slice(1, -1).join(" / ") : null,
    fieldLabel: parts[parts.length - 1],
  };
}

function inferLocationFromKey(key: string): Pick<SortstarLocation, "section" | "group"> {
  const normalized = key.toLowerCase();

  if (["customer", "machine", "direction"].includes(normalized)) {
    return { section: "GENERAL ORDER ACKNOWLEDGEMENT", group: null };
  }
  if (["quote", "production_speed"].includes(normalized)) {
    return { section: "Order Identification", group: null };
  }
  if (["voltage", "phases", "hz", "amps", "psi", "cfm", "country"].includes(normalized)) {
    return { section: "Utility Specifications", group: null };
  }
  if (normalized.startsWith("conformity_")) {
    return { section: "Utility Specifications", group: "Conformity" };
  }
  if (normalized.startsWith("ce_")) {
    return { section: "Utility Specifications", group: "Certification" };
  }
  if (normalized.startsWith("bs_")) {
    return { section: "BASIC SYSTEMS", group: "Mechanical Basic Machine configuration" };
  }
  if (normalized.startsWith("op_")) {
    return { section: "OPTIONAL SYSTEMS", group: "Guarding System" };
  }
  if (normalized.startsWith("el_")) {
    return { section: "OPTIONAL SYSTEMS", group: "Electrical" };
  }
  if (
    normalized.startsWith("cps_") ||
    normalized.startsWith("plc_") ||
    normalized.startsWith("hmi_") ||
    normalized.startsWith("cpp_")
  ) {
    return { section: "OPTIONAL SYSTEMS", group: "Control Specifications" };
  }
  if (normalized.startsWith("rts_")) {
    return { section: "OPTIONAL SYSTEMS", group: "Remote Technical Service" };
  }
  if (normalized.startsWith("eg_")) {
    return { section: "OPTIONAL SYSTEMS", group: "Euro guarding" };
  }
  if (
    normalized.startsWith("pt_") ||
    normalized.startsWith("sk_") ||
    normalized.startsWith("stpc_") ||
    normalized.startsWith("wi_") ||
    normalized.startsWith("wrts_")
  ) {
    return {
      section: "OPTIONAL SYSTEMS",
      group: "Packaging & Transport & Warranty & Install & Spares",
    };
  }
  if (normalized.startsWith("vd_")) {
    return { section: "OPTIONAL SYSTEMS", group: "Validation Documents" };
  }
  if (normalized === "option_listing" || normalized === "options_listing" || normalized.startsWith("options_")) {
    return { section: "Option Listing", group: null };
  }

  return { section: "Additional Fields", group: null };
}

function inferFieldType(fieldKey: string, value: string): GoaFormSchemaField["type"] {
  if (fieldKey.endsWith("_check") || normalizeCheckboxLike(value)) {
    return "checkbox";
  }
  if (value.includes("\n") || value.length > 120) {
    return "textarea";
  }
  return "text";
}

export function buildSortstarSchema(
  data: Record<string, string>,
  labels?: Record<string, string>,
  sectionTitle = "Sortstar Fields"
): GoaFormSchemaResponse {
  const rows = Object.entries(data).map(([key, rawValue]) => {
      const value = String(rawValue ?? "");
      const mappedLabel = labels?.[key]?.trim() || "";
      const parsedLabel = mappedLabel ? parseHierarchicalLabel(mappedLabel) : null;
      const inferredLocation = inferLocationFromKey(key);
      const location: SortstarLocation = parsedLabel
        ? parsedLabel
        : {
            section: inferredLocation.section,
            group: inferredLocation.group,
            fieldLabel: mappedLabel || prettyLabel(key),
          };

      return {
        section: location.section || sectionTitle,
        group: location.group,
        field: {
          key,
          label: location.fieldLabel || prettyLabel(key),
          type: inferFieldType(key, value),
        } satisfies GoaFormSchemaField,
      };
    });

  rows.sort((a, b) => {
    const aPriority = SECTION_PRIORITY[a.section] ?? 999;
    const bPriority = SECTION_PRIORITY[b.section] ?? 999;
    if (aPriority !== bPriority) return aPriority - bPriority;

    const sectionCmp = a.section.localeCompare(b.section, undefined, { sensitivity: "base" });
    if (sectionCmp !== 0) return sectionCmp;

    const aGroup = a.group ?? "";
    const bGroup = b.group ?? "";
    const groupCmp = aGroup.localeCompare(bGroup, undefined, { sensitivity: "base" });
    if (groupCmp !== 0) return groupCmp;

    return a.field.label.localeCompare(b.field.label, undefined, { sensitivity: "base" });
  });

  const sectionMap = new Map<
    string,
    {
      id: string;
      title: string;
      fieldCount: number;
      groups: Array<{ title: string | null; fields: GoaFormSchemaField[] }>;
    }
  >();

  const groupIndexBySection = new Map<string, Map<string, number>>();

  for (const row of rows) {
    const sectionKey = row.section;
    const groupKey = row.group ?? "";

    if (!sectionMap.has(sectionKey)) {
      sectionMap.set(sectionKey, {
        id: toSectionId(sectionKey),
        title: sectionKey,
        fieldCount: 0,
        groups: [],
      });
      groupIndexBySection.set(sectionKey, new Map());
    }

    const section = sectionMap.get(sectionKey);
    const sectionGroupIndex = groupIndexBySection.get(sectionKey);
    if (!section || !sectionGroupIndex) continue;

    if (!sectionGroupIndex.has(groupKey)) {
      section.groups.push({ title: row.group, fields: [] });
      sectionGroupIndex.set(groupKey, section.groups.length - 1);
    }

    const groupIndex = sectionGroupIndex.get(groupKey);
    if (typeof groupIndex !== "number") continue;
    section.groups[groupIndex].fields.push(row.field);
    section.fieldCount += 1;
  }

  const sections = Array.from(sectionMap.values());
  for (const section of sections) {
    for (const group of section.groups) {
      group.fields.sort((a, b) => a.label.localeCompare(b.label, undefined, { sensitivity: "base" }));
    }
  }

  return {
    sections:
      sections.length > 0
        ? sections
        : [
            {
              id: toSectionId(sectionTitle),
              title: sectionTitle,
              fieldCount: 0,
              groups: [{ title: null, fields: [] }],
            },
          ],
    fieldCount: rows.length,
  };
}
