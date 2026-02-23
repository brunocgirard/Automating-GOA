"use client";

import { useMemo, useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { GanttUploadDialog } from "@/components/pm-dashboard/gantt-upload-dialog";

interface GanttDetailProps {
  projectId: number;
  ganttData: Record<string, unknown> | null;
  onRefresh?: () => void;
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function asString(value: unknown): string {
  if (value == null) return "";
  return String(value);
}

function asNumber(value: unknown): number {
  if (typeof value === "number") return Number.isFinite(value) ? value : 0;
  const parsed = Number(asString(value).replace(/[^0-9.-]/g, ""));
  return Number.isFinite(parsed) ? parsed : 0;
}

export function GanttDetail({ projectId, ganttData, onRefresh }: GanttDetailProps) {
  const [collapsed, setCollapsed] = useState(true);

  const machines = useMemo(() => {
    const payload = asRecord(ganttData);
    const rows = Array.isArray(payload.machines) ? payload.machines : [];
    return rows.map((entry) => asRecord(entry));
  }, [ganttData]);

  return (
    <section className="space-y-2">
      <button
        type="button"
        onClick={() => setCollapsed((value) => !value)}
        className="flex w-full items-center justify-between rounded-md border bg-neutral-50 px-3 py-2 text-left"
      >
        <span className="text-sm font-semibold">Production Gantt</span>
        {collapsed ? <ChevronRight className="size-4" /> : <ChevronDown className="size-4" />}
      </button>

      {!collapsed ? (
        <div className="space-y-3 rounded-md border p-3">
          <div className="flex items-center justify-end">
            <GanttUploadDialog projectId={projectId} onUploaded={onRefresh} />
          </div>

          {machines.length === 0 ? (
            <div className="rounded-md border bg-neutral-50 p-3 text-sm text-muted-foreground">
              No Gantt uploaded.
            </div>
          ) : (
            <div className="space-y-3">
              {machines.map((machine, index) => {
                const phasesRaw = Array.isArray(machine.phases) ? machine.phases : [];
                const progress = Math.max(0, Math.min(100, asNumber(machine.overall_pct)));
                return (
                  <div key={`${asString(machine.name)}-${index}`} className="rounded-md border p-3">
                    <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                      <p className="text-sm font-semibold">{asString(machine.name) || `Machine ${index + 1}`}</p>
                      <span className="text-xs text-muted-foreground">{progress.toFixed(0)}%</span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-neutral-200">
                      <div className="h-full bg-blue-600" style={{ width: `${progress}%` }} />
                    </div>
                    {phasesRaw.length > 0 ? (
                      <div className="mt-3 grid gap-2 sm:grid-cols-2">
                        {phasesRaw.map((phase, phaseIndex) => {
                          const phaseRecord = asRecord(phase);
                          const phaseProgress = Math.max(
                            0,
                            Math.min(100, asNumber(phaseRecord.progress_pct))
                          );
                          return (
                            <div key={`${asString(phaseRecord.name)}-${phaseIndex}`} className="rounded border p-2">
                              <div className="mb-1 flex items-center justify-between text-xs">
                                <span>{asString(phaseRecord.name) || `Phase ${phaseIndex + 1}`}</span>
                                <span>{phaseProgress.toFixed(0)}%</span>
                              </div>
                              <div className="h-1.5 overflow-hidden rounded-full bg-neutral-200">
                                <div className="h-full bg-emerald-600" style={{ width: `${phaseProgress}%` }} />
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    ) : null}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      ) : null}
    </section>
  );
}
