"use client";

import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import type { ProjectTask } from "@/lib/types";

const phases: Array<{ key: ProjectTask["phase"]; label: string }> = [
  { key: "sales_onboarding", label: "Sales" },
  { key: "engineering_prep", label: "Engineering" },
  { key: "design_approval", label: "Design" },
  { key: "production", label: "Production" },
  { key: "delivery", label: "Delivery" },
];

interface PhaseProgressProps {
  tasks: ProjectTask[];
}

function phaseStats(tasks: ProjectTask[], phase: ProjectTask["phase"]) {
  const phaseTasks = tasks.filter((task) => task.phase === phase);
  const total = phaseTasks.length;
  const done = phaseTasks.filter((task) => task.status === "done" || task.status === "skipped").length;
  const inProgress = phaseTasks.some((task) => task.status === "in_progress");
  const hasStarted = phaseTasks.some((task) => task.status !== "pending");
  return { total, done, inProgress, hasStarted };
}

function phaseClassName(total: number, done: number, inProgress: boolean, hasStarted: boolean): string {
  if (total > 0 && done >= total) return "bg-green-600 text-white";
  if (inProgress || (hasStarted && done > 0)) return "bg-blue-600 text-white animate-pulse";
  return "bg-neutral-200 text-neutral-700";
}

export function PhaseProgress({ tasks }: PhaseProgressProps) {
  return (
    <div className="space-y-2">
      <h4 className="text-sm font-semibold">Phase Progress</h4>
      <div className="grid grid-cols-5 gap-2">
        {phases.map((phase) => {
          const stats = phaseStats(tasks, phase.key);
          return (
            <Tooltip key={phase.key}>
              <TooltipTrigger asChild>
                <div
                  className={cn(
                    "flex h-16 cursor-default flex-col items-center justify-center rounded-md text-xs font-medium",
                    phaseClassName(stats.total, stats.done, stats.inProgress, stats.hasStarted)
                  )}
                >
                  <span>{phase.label}</span>
                  <span className="font-mono">
                    {stats.done}/{stats.total}
                  </span>
                </div>
              </TooltipTrigger>
              <TooltipContent sideOffset={4}>
                <p>{phase.label}</p>
                <p>
                  {stats.done} complete of {stats.total}
                </p>
              </TooltipContent>
            </Tooltip>
          );
        })}
      </div>
    </div>
  );
}
