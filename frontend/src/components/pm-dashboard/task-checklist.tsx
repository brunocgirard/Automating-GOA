"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronDown, ChevronRight, MoreHorizontal } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Button } from "@/components/ui/button";
import type { ProjectTask, TaskStatus } from "@/lib/types";

interface TaskChecklistProps {
  tasks: ProjectTask[];
  onStatusChange: (taskId: number, status: TaskStatus) => Promise<void> | void;
  updatingTaskId?: number | null;
}

interface ContextMenuState {
  taskId: number;
  x: number;
  y: number;
}

const phaseOrder: ProjectTask["phase"][] = [
  "sales_onboarding",
  "engineering_prep",
  "design_approval",
  "production",
  "delivery",
];

const phaseLabel: Record<ProjectTask["phase"], string> = {
  sales_onboarding: "Sales & Onboarding",
  engineering_prep: "Engineering Prep",
  design_approval: "Design & Approval",
  production: "Production",
  delivery: "Delivery",
};

const statusBadgeClass: Record<TaskStatus, string> = {
  pending: "bg-neutral-200 text-neutral-700",
  in_progress: "bg-blue-100 text-blue-700",
  done: "bg-green-100 text-green-700",
  skipped: "bg-neutral-300 text-neutral-800",
};

function isTaskComplete(status: TaskStatus): boolean {
  return status === "done" || status === "skipped";
}

export function TaskChecklist({ tasks, onStatusChange, updatingTaskId }: TaskChecklistProps) {
  const [collapsed, setCollapsed] = useState(true);
  const [contextMenu, setContextMenu] = useState<ContextMenuState | null>(null);
  const touchTimeoutRef = useRef<number | null>(null);

  const grouped = useMemo(() => {
    const byPhase = new Map<ProjectTask["phase"], ProjectTask[]>();
    for (const phase of phaseOrder) byPhase.set(phase, []);
    for (const task of tasks) {
      const list = byPhase.get(task.phase);
      if (list) {
        list.push(task);
      }
    }
    for (const phase of phaseOrder) {
      byPhase.get(phase)?.sort((a, b) => a.task_order - b.task_order);
    }
    return byPhase;
  }, [tasks]);

  useEffect(() => {
    if (!contextMenu) return;
    const close = () => setContextMenu(null);
    window.addEventListener("click", close);
    window.addEventListener("scroll", close, true);
    return () => {
      window.removeEventListener("click", close);
      window.removeEventListener("scroll", close, true);
    };
  }, [contextMenu]);

  function clearTouchTimer() {
    if (touchTimeoutRef.current != null) {
      window.clearTimeout(touchTimeoutRef.current);
      touchTimeoutRef.current = null;
    }
  }

  function openContextMenu(taskId: number, x: number, y: number) {
    setContextMenu({ taskId, x, y });
  }

  async function handlePrimaryToggle(task: ProjectTask) {
    const nextStatus: TaskStatus = task.status === "done" ? "pending" : "done";
    await onStatusChange(task.id, nextStatus);
  }

  async function handleSetStatus(taskId: number, status: TaskStatus) {
    await onStatusChange(taskId, status);
    setContextMenu(null);
  }

  function outOfOrder(task: ProjectTask, phaseTasks: ProjectTask[]) {
    if (!isTaskComplete(task.status)) return false;
    const earlier = phaseTasks.filter((candidate) => candidate.task_order < task.task_order);
    return earlier.some((candidate) => !isTaskComplete(candidate.status));
  }

  return (
    <section className="space-y-2">
      <button
        type="button"
        onClick={() => setCollapsed((value) => !value)}
        className="flex w-full items-center justify-between rounded-md border bg-neutral-50 px-3 py-2 text-left"
      >
        <span className="text-sm font-semibold">Task Checklist</span>
        {collapsed ? <ChevronRight className="size-4" /> : <ChevronDown className="size-4" />}
      </button>

      {!collapsed ? (
        <div className="max-h-[40vh] space-y-4 overflow-y-auto rounded-md border p-3">
          {phaseOrder.map((phase) => {
            const phaseTasks = grouped.get(phase) ?? [];
            if (phaseTasks.length === 0) return null;

            return (
              <div key={phase} className="space-y-2">
                <h5 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  {phaseLabel[phase]}
                </h5>
                <div className="space-y-1">
                  {phaseTasks.map((task) => {
                    const isUpdating = updatingTaskId === task.id;
                    const showOutOfOrder = outOfOrder(task, phaseTasks);
                    const menuOpen = contextMenu?.taskId === task.id;

                    return (
                      <div
                        key={task.id}
                        onContextMenu={(event) => {
                          event.preventDefault();
                          openContextMenu(task.id, event.clientX, event.clientY);
                        }}
                        onTouchStart={(event) => {
                          clearTouchTimer();
                          const touch = event.touches[0];
                          if (!touch) return;
                          touchTimeoutRef.current = window.setTimeout(() => {
                            openContextMenu(task.id, touch.clientX, touch.clientY);
                          }, 450);
                        }}
                        onTouchEnd={clearTouchTimer}
                        onTouchCancel={clearTouchTimer}
                        onTouchMove={clearTouchTimer}
                        className="rounded-md border bg-white px-2 py-2"
                      >
                        <div className="flex items-center gap-2">
                          <Checkbox
                            checked={task.status === "done"}
                            disabled={isUpdating}
                            onCheckedChange={() => {
                              void handlePrimaryToggle(task);
                            }}
                          />
                          <button
                            type="button"
                            className="min-w-0 flex-1 text-left text-sm"
                            disabled={isUpdating}
                            onClick={() => {
                              void handlePrimaryToggle(task);
                            }}
                          >
                            <span className={task.status === "done" ? "line-through text-muted-foreground" : ""}>
                              {task.task_name}
                            </span>
                          </button>
                          <Badge variant="secondary" className={statusBadgeClass[task.status]}>
                            {task.status.replace("_", " ")}
                          </Badge>
                          {showOutOfOrder ? (
                            <Badge variant="outline" className="text-amber-700">
                              Out of order
                            </Badge>
                          ) : null}
                          <Button
                            type="button"
                            size="icon"
                            variant="ghost"
                            className="size-7"
                            disabled={isUpdating}
                            onClick={(event) => {
                              const rect = event.currentTarget.getBoundingClientRect();
                              openContextMenu(task.id, rect.left, rect.bottom + 4);
                            }}
                          >
                            <MoreHorizontal className="size-4" />
                          </Button>
                        </div>
                        {menuOpen ? (
                          <div
                            className="fixed z-[70] min-w-36 rounded-md border bg-white p-1 shadow-md"
                            style={{
                              left: `${Math.max(8, contextMenu.x)}px`,
                              top: `${Math.max(8, contextMenu.y)}px`,
                            }}
                          >
                            <button
                              type="button"
                              className="w-full rounded px-2 py-1 text-left text-sm hover:bg-neutral-100"
                              onClick={() => {
                                void handleSetStatus(task.id, "in_progress");
                              }}
                            >
                              Mark in progress
                            </button>
                            <button
                              type="button"
                              className="w-full rounded px-2 py-1 text-left text-sm hover:bg-neutral-100"
                              onClick={() => {
                                void handleSetStatus(task.id, "skipped");
                              }}
                            >
                              Mark skipped
                            </button>
                            <button
                              type="button"
                              className="w-full rounded px-2 py-1 text-left text-sm hover:bg-neutral-100"
                              onClick={() => {
                                void handleSetStatus(task.id, "pending");
                              }}
                            >
                              Mark pending
                            </button>
                          </div>
                        ) : null}
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      ) : null}
    </section>
  );
}
