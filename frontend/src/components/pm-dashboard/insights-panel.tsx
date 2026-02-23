"use client";

import { useEffect, useState } from "react";
import { AlertCircle, AlertTriangle, Info } from "lucide-react";
import { fetchPmInsights } from "@/lib/api";
import type { ProjectInsight } from "@/lib/types";

interface InsightsPanelProps {
  projectId: number;
}

const severityClasses: Record<ProjectInsight["severity"], string> = {
  critical: "border-red-300 bg-red-50 text-red-900",
  warning: "border-yellow-300 bg-yellow-50 text-yellow-900",
  info: "border-blue-300 bg-blue-50 text-blue-900",
};

const severityIcon: Record<ProjectInsight["severity"], React.ElementType> = {
  critical: AlertCircle,
  warning: AlertTriangle,
  info: Info,
};

export function InsightsPanel({ projectId }: InsightsPanelProps) {
  const [insights, setInsights] = useState<ProjectInsight[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    queueMicrotask(() => {
      if (!active) return;
      setLoading(true);
      setError(null);
    });
    void fetchPmInsights(projectId)
      .then((rows) => {
        if (!active) return;
        setInsights(rows.slice(0, 2));
      })
      .catch((err) => {
        if (!active) return;
        setInsights([]);
        setError(err instanceof Error ? err.message : "Failed to load insights.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [projectId]);

  return (
    <section className="space-y-2">
      <h4 className="text-sm font-semibold">AI Insights</h4>
      {loading ? (
        <div className="rounded-md border bg-neutral-50 p-3 text-sm text-muted-foreground">
          Loading insights...
        </div>
      ) : error ? (
        <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      ) : insights.length === 0 ? (
        <div className="rounded-md border bg-neutral-50 p-3 text-sm text-muted-foreground">
          No active insight alerts for this project.
        </div>
      ) : (
        insights.map((insight) => {
          const Icon = severityIcon[insight.severity];
          return (
            <div
              key={`${insight.type}-${insight.task_id ?? "global"}-${insight.title}`}
              className={`rounded-md border p-3 text-sm ${severityClasses[insight.severity]}`}
            >
              <div className="mb-1 flex items-center gap-2 font-semibold">
                <Icon className="size-4" />
                {insight.title}
              </div>
              <p>{insight.message}</p>
            </div>
          );
        })
      )}
    </section>
  );
}
