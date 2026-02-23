"use client";

import { AlertTriangle, CheckCircle2 } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import type { AtRiskSummary } from "@/lib/types";

interface AlertStripProps {
  atRisk: AtRiskSummary | null;
  loading?: boolean;
}

export function AlertStrip({ atRisk, loading = false }: AlertStripProps) {
  if (loading) {
    return (
      <Card className="border-neutral-300 bg-white py-3">
        <CardContent className="px-4 text-sm text-muted-foreground">
          Loading project alerts...
        </CardContent>
      </Card>
    );
  }

  const count = atRisk?.count ?? 0;
  const worst = atRisk?.projects?.[0];

  if (count > 0 && worst) {
    return (
      <Card className="border-red-300 bg-red-50 py-3">
        <CardContent className="flex items-start gap-3 px-4 py-0 text-sm text-red-900">
          <AlertTriangle className="mt-0.5 size-4 shrink-0" />
          <div className="space-y-1">
            <p className="font-semibold">
              {count} project{count === 1 ? "" : "s"} at risk
            </p>
            <p className="text-red-800">
              {worst.name} is stalled on <span className="font-medium">{worst.task}</span> ({worst.phase}) for{" "}
              {worst.days_stalled} days.
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border-green-300 bg-green-50 py-3">
      <CardContent className="flex items-center gap-2 px-4 py-0 text-sm text-green-900">
        <CheckCircle2 className="size-4 shrink-0" />
        <span className="font-semibold">All projects on track</span>
      </CardContent>
    </Card>
  );
}
