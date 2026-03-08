"use client";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { ProjectListItem } from "@/lib/types";

const riskDotClass: Record<ProjectListItem["risk_level"], string> = {
  on_track: "bg-green-500",
  at_risk: "bg-yellow-500",
  overdue: "bg-red-500",
};

function daysClass(days: number | null): string {
  if (days == null) return "text-muted-foreground";
  if (days >= 14) return "text-red-700";
  if (days >= 7) return "text-yellow-700";
  return "text-muted-foreground";
}

interface ProjectCardProps {
  project: ProjectListItem;
  onClick: () => void;
}

export function ProjectCard({ project, onClick }: ProjectCardProps) {
  return (
    <button type="button" className="w-full text-left" onClick={onClick}>
      <Card className="py-3 transition-colors hover:border-[#c00000]/40 hover:bg-[#c00000]/[0.02]">
        <CardContent className="space-y-2 px-4 py-0">
          <div className="flex items-start justify-between gap-2">
            <p className="line-clamp-2 text-sm font-semibold">{project.project_name}</p>
            <span className={cn("mt-1 size-2.5 shrink-0 rounded-full", riskDotClass[project.risk_level])} />
          </div>
          <p className="truncate text-xs text-muted-foreground">{project.customer_name}</p>
          <Badge variant="secondary" className="max-w-full truncate">
            {project.current_task || "All tasks complete"}
          </Badge>
          <p className={cn("font-mono text-xs", daysClass(project.days_in_phase))}>
            {project.days_in_phase == null ? "Days in phase: -" : `Days in phase: ${project.days_in_phase}`}
          </p>
        </CardContent>
      </Card>
    </button>
  );
}
