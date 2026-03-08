"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ExternalLink } from "lucide-react";
import { fetchQuotes } from "@/lib/api";
import type { ProjectDetail, TaskStatus } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { InsightsPanel } from "@/components/pm-dashboard/insights-panel";
import { PhaseProgress } from "@/components/pm-dashboard/phase-progress";
import { TaskChecklist } from "@/components/pm-dashboard/task-checklist";

interface ProjectDetailSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  project: ProjectDetail | null;
  updatingTaskId?: number | null;
  onTaskStatusChange: (taskId: number, status: TaskStatus) => Promise<void> | void;
}

function toDate(value: string | null | undefined): Date | null {
  if (!value) return null;
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

function dateDiffDays(start: Date | null, end: Date | null): number | null {
  if (!start || !end) return null;
  const ms = end.getTime() - start.getTime();
  if (!Number.isFinite(ms)) return null;
  return Math.max(0, Math.round(ms / (1000 * 60 * 60 * 24)));
}

function formatDate(value: Date | null): string {
  if (!value) return "-";
  return value.toLocaleDateString();
}

export function ProjectDetailSheet({
  open,
  onOpenChange,
  project,
  updatingTaskId,
  onTaskStatusChange,
}: ProjectDetailSheetProps) {
  const [quoteId, setQuoteId] = useState<number | null>(null);

  useEffect(() => {
    let active = true;
    queueMicrotask(() => {
      if (active) setQuoteId(null);
    });
    if (!project?.quote_ref) return;

    void fetchQuotes()
      .then((rows) => {
        if (!active) return;
        const match = rows.find((row) => row.quoteRef === project.quote_ref);
        setQuoteId(match?.quoteId ?? null);
      })
      .catch(() => {
        if (active) setQuoteId(null);
      });

    return () => {
      active = false;
    };
  }, [project?.quote_ref]);

  const quickLinkQuoteValue = useMemo(() => {
    if (!project?.quote_ref) return null;
    if (quoteId != null) return String(quoteId);
    return project.quote_ref;
  }, [project?.quote_ref, quoteId]);

  const startDate = toDate(project?.start_date);
  const targetDate = toDate(project?.target_end_date);
  const elapsedDays = dateDiffDays(startDate, new Date());
  const totalDays = dateDiffDays(startDate, targetDate);

  const estimatedCompletion = useMemo(() => {
    if (!project || !startDate || project.progress_pct <= 0 || elapsedDays == null) return null;
    const estimatedTotalDays = Math.round((elapsedDays / project.progress_pct) * 100);
    const eta = new Date(startDate);
    eta.setDate(eta.getDate() + estimatedTotalDays);
    return eta;
  }, [elapsedDays, project, startDate]);

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full overflow-y-auto sm:max-w-2xl">
        {!project ? (
          <>
            <SheetHeader className="sr-only">
              <SheetTitle>Project details</SheetTitle>
              <SheetDescription>Select a project to view details.</SheetDescription>
            </SheetHeader>
            <div className="p-6 text-sm text-muted-foreground">Select a project to view details.</div>
          </>
        ) : (
          <div className="space-y-4 p-6">
            <SheetHeader className="p-0">
              <SheetTitle className="text-xl">{project.project_name}</SheetTitle>
              <SheetDescription>{project.customer_name}</SheetDescription>
            </SheetHeader>

            <div className="flex items-center gap-2">
              <Badge variant="secondary">{project.status}</Badge>
              <Badge
                variant="secondary"
                className={
                  project.risk_level === "overdue"
                    ? "bg-red-100 text-red-800"
                    : project.risk_level === "at_risk"
                      ? "bg-yellow-100 text-yellow-800"
                      : "bg-green-100 text-green-800"
                }
              >
                {project.risk_level.replace("_", " ")}
              </Badge>
            </div>

            <InsightsPanel projectId={project.id} />

            <section className="grid gap-2 rounded-md border p-3 sm:grid-cols-2">
              <div>
                <p className="text-xs uppercase tracking-wide text-muted-foreground">Days Elapsed</p>
                <p className="text-sm font-semibold">
                  {elapsedDays == null ? "-" : elapsedDays}
                  {totalDays != null ? ` / ${totalDays}` : ""}
                </p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wide text-muted-foreground">Est. Completion</p>
                <p className="text-sm font-semibold">{formatDate(estimatedCompletion)}</p>
              </div>
            </section>

            <section className="space-y-2">
              <h4 className="text-sm font-semibold">Quick Links</h4>
              {quickLinkQuoteValue ? (
                <div className="grid gap-2 sm:grid-cols-2">
                  <Link
                    className="inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm hover:bg-neutral-50"
                    href={`/client-info?quote=${encodeURIComponent(quickLinkQuoteValue)}`}
                  >
                    Client Info <ExternalLink className="size-3.5" />
                  </Link>
                  <Link
                    className="inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm hover:bg-neutral-50"
                    href={`/processing?quote=${encodeURIComponent(quickLinkQuoteValue)}`}
                  >
                    GOA Processing <ExternalLink className="size-3.5" />
                  </Link>
                  <Link
                    className="inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm hover:bg-neutral-50"
                    href={`/shipping-documents?quote=${encodeURIComponent(quickLinkQuoteValue)}`}
                  >
                    Shipping Docs <ExternalLink className="size-3.5" />
                  </Link>
                  <Link
                    className="inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm hover:bg-neutral-50"
                    href={`/cor-documents?quote=${encodeURIComponent(quickLinkQuoteValue)}`}
                  >
                    COR Docs <ExternalLink className="size-3.5" />
                  </Link>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">No quote reference linked to this project.</p>
              )}
            </section>

            <PhaseProgress tasks={project.tasks} />

            <TaskChecklist
              tasks={project.tasks}
              updatingTaskId={updatingTaskId}
              onStatusChange={onTaskStatusChange}
            />
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}
