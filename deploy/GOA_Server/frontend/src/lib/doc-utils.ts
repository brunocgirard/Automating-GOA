export function line(value: string | null | undefined): string {
  return (value ?? "").trim() || "-";
}

export function toNumber(
  value: string | number | null | undefined,
  fallback = 0
): number {
  if (typeof value === "number") {
    return Number.isFinite(value) ? value : fallback;
  }

  const parsed = Number(String(value ?? "").replace(/[^0-9.-]/g, ""));
  return Number.isFinite(parsed) ? parsed : fallback;
}

export function uid(prefix: string): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return `${prefix}-${crypto.randomUUID()}`;
  }

  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`;
}

export function formatStatusTimestamp(value: string | null): string {
  if (!value) return "";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString();
}

export function workflowQuoteBadgeConfig(
  status: string | null | undefined
): { label: string; className: string } {
  if (status === "ready") {
    return { label: "Ready", className: "bg-green-100 text-green-800" };
  }
  if (status === "processed") {
    return { label: "Processed", className: "bg-yellow-100 text-yellow-800" };
  }
  return { label: "Draft", className: "bg-neutral-200 text-neutral-700" };
}
