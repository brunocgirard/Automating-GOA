"use client";

import { ProjectCard } from "@/components/pm-dashboard/project-card";
import type { ProjectListItem } from "@/lib/types";

interface KanbanBoardProps {
  projects: ProjectListItem[];
  onSelectProject: (projectId: number) => void;
}

type ColumnKey =
  | "sales_onboarding"
  | "engineering_prep"
  | "design_approval"
  | "production"
  | "delivery";

const columns: Array<{ key: ColumnKey; label: string }> = [
  { key: "sales_onboarding", label: "Sales & Onboarding" },
  { key: "engineering_prep", label: "Engineering Prep" },
  { key: "design_approval", label: "Design & Approval" },
  { key: "production", label: "Production" },
  { key: "delivery", label: "Delivery" },
];

function resolveColumn(project: ProjectListItem): ColumnKey {
  if (project.progress_pct >= 100) return "delivery";
  return (project.current_phase as ColumnKey | null) ?? "delivery";
}

export function KanbanBoard({ projects, onSelectProject }: KanbanBoardProps) {
  const grouped = new Map<ColumnKey, ProjectListItem[]>(
    columns.map((column) => [column.key, [] as ProjectListItem[]])
  );
  for (const project of projects) {
    grouped.get(resolveColumn(project))?.push(project);
  }

  return (
    <div className="grid gap-4 lg:grid-cols-5">
      {columns.map((column) => {
        const items = grouped.get(column.key) ?? [];
        return (
          <section key={column.key} className="rounded-lg border bg-white p-3">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-sm font-semibold">{column.label}</h3>
              <span className="rounded-full bg-neutral-100 px-2 py-0.5 text-xs text-muted-foreground">
                {items.length}
              </span>
            </div>
            <div className="space-y-2">
              {items.length === 0 ? (
                <div className="rounded-md border border-dashed p-3 text-xs text-muted-foreground">
                  No projects
                </div>
              ) : (
                items.map((project) => (
                  <ProjectCard
                    key={project.id}
                    project={project}
                    onClick={() => onSelectProject(project.id)}
                  />
                ))
              )}
            </div>
          </section>
        );
      })}
    </div>
  );
}
