"use client";

import { useEffect, useMemo, useState } from "react";
import { ChevronDown, ChevronRight, Pencil, Plus, Trash2 } from "lucide-react";
import {
  createUserTask,
  deleteUserTask,
  fetchQuotes,
  fetchUserTaskTags,
  fetchUserTasks,
  toggleUserTask,
  updateUserTask,
} from "@/lib/api";
import type {
  UserTask,
  UserTaskPriority,
  UserTaskStatus,
} from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface TaskDraft {
  title: string;
  description: string;
  client_tag: string;
  priority: UserTaskPriority;
  due_date: string;
}

const EMPTY_DRAFT: TaskDraft = {
  title: "",
  description: "",
  client_tag: "",
  priority: "normal",
  due_date: "",
};

const priorityRank: Record<UserTaskPriority, number> = {
  urgent: 0,
  high: 1,
  normal: 2,
  low: 3,
};

const priorityBadgeClass: Record<UserTaskPriority, string> = {
  low: "bg-neutral-100 text-neutral-700",
  normal: "bg-slate-100 text-slate-700",
  high: "bg-amber-100 text-amber-700",
  urgent: "bg-red-100 text-red-700",
};

const tagColors = [
  "bg-blue-100 text-blue-700 border-blue-200",
  "bg-emerald-100 text-emerald-700 border-emerald-200",
  "bg-amber-100 text-amber-700 border-amber-200",
  "bg-cyan-100 text-cyan-700 border-cyan-200",
  "bg-rose-100 text-rose-700 border-rose-200",
  "bg-indigo-100 text-indigo-700 border-indigo-200",
];

function toNullable(value: string): string | null {
  const normalized = value.trim();
  return normalized.length > 0 ? normalized : null;
}

function normalizeDateForInput(value: string | null): string {
  if (!value) return "";
  return value.length >= 10 ? value.slice(0, 10) : value;
}

function formatDate(value: string | null): string | null {
  if (!value) return null;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleDateString();
}

function tagBadgeClass(tag: string): string {
  const normalized = tag.trim();
  if (!normalized) return "bg-neutral-100 text-neutral-700 border-neutral-200";
  const hash = normalized
    .split("")
    .reduce((sum, char) => sum + char.charCodeAt(0), 0);
  return tagColors[hash % tagColors.length] ?? "bg-neutral-100 text-neutral-700 border-neutral-200";
}

function buildTagOptions(tasks: UserTask[], taskTags: string[], quoteTags: string[]): string[] {
  const values = new Set<string>();
  for (const task of tasks) {
    if (task.client_tag && task.client_tag.trim()) values.add(task.client_tag.trim());
  }
  for (const tag of taskTags) {
    if (tag.trim()) values.add(tag.trim());
  }
  for (const tag of quoteTags) {
    if (tag.trim()) values.add(tag.trim());
  }
  return [...values].sort((a, b) => a.localeCompare(b));
}

function matchesTag(task: UserTask, tagFilter: string): boolean {
  if (tagFilter === "all") return true;
  return (task.client_tag ?? "").trim().toLowerCase() === tagFilter.trim().toLowerCase();
}

function isOverdue(task: UserTask): boolean {
  if (task.status !== "pending" || !task.due_date) return false;
  const due = new Date(task.due_date);
  if (Number.isNaN(due.getTime())) return false;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return due.getTime() < today.getTime();
}

function sortPendingTasks(a: UserTask, b: UserTask): number {
  const dueA = a.due_date ? Date.parse(a.due_date) : Number.POSITIVE_INFINITY;
  const dueB = b.due_date ? Date.parse(b.due_date) : Number.POSITIVE_INFINITY;
  if (dueA !== dueB) return dueA - dueB;

  const priorityA = priorityRank[a.priority] ?? 99;
  const priorityB = priorityRank[b.priority] ?? 99;
  if (priorityA !== priorityB) return priorityA - priorityB;

  return a.title.localeCompare(b.title);
}

function sortCompletedTasks(a: UserTask, b: UserTask): number {
  const doneA = a.completed_at ? Date.parse(a.completed_at) : 0;
  const doneB = b.completed_at ? Date.parse(b.completed_at) : 0;
  if (doneA !== doneB) return doneB - doneA;
  return b.id - a.id;
}

function groupTasksByTag(rows: UserTask[]): Array<{ key: string; label: string; tasks: UserTask[] }> {
  const groups = new Map<string, UserTask[]>();
  for (const row of rows) {
    const tag = (row.client_tag ?? "").trim();
    const key = tag || "__no_client__";
    const existing = groups.get(key);
    if (existing) {
      existing.push(row);
    } else {
      groups.set(key, [row]);
    }
  }

  return [...groups.entries()]
    .map(([key, tasks]) => ({
      key,
      label: key === "__no_client__" ? "No Client Tag" : key,
      tasks,
    }))
    .sort((a, b) => a.label.localeCompare(b.label));
}

export function PersonalTaskBoard() {
  const [tasks, setTasks] = useState<UserTask[]>([]);
  const [tagOptions, setTagOptions] = useState<string[]>([]);
  const [quoteTags, setQuoteTags] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [addDraft, setAddDraft] = useState<TaskDraft>(EMPTY_DRAFT);
  const [editingTaskId, setEditingTaskId] = useState<number | null>(null);
  const [editDraft, setEditDraft] = useState<TaskDraft>(EMPTY_DRAFT);
  const [pendingActionTaskId, setPendingActionTaskId] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const [tagFilter, setTagFilter] = useState("all");
  const [showCompleted, setShowCompleted] = useState(true);
  const [completedCollapsed, setCompletedCollapsed] = useState(false);

  async function refreshTasks(nextQuoteTags?: string[]) {
    const [taskRows, taskTags] = await Promise.all([fetchUserTasks(), fetchUserTaskTags()]);
    const mergedQuoteTags = nextQuoteTags ?? quoteTags;
    setTasks(taskRows);
    setTagOptions(buildTagOptions(taskRows, taskTags, mergedQuoteTags));
  }

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);

    void (async () => {
      try {
        const quoteRows = await fetchQuotes().catch(() => []);
        if (!active) return;
        const extractedQuoteTags = [
          ...new Set(
            quoteRows
              .map((row) => row.clientName.trim())
              .filter((value) => value.length > 0)
          ),
        ].sort((a, b) => a.localeCompare(b));
        setQuoteTags(extractedQuoteTags);
        const [taskRows, taskTags] = await Promise.all([fetchUserTasks(), fetchUserTaskTags()]);
        if (!active) return;
        setTasks(taskRows);
        setTagOptions(buildTagOptions(taskRows, taskTags, extractedQuoteTags));
      } catch (err) {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Failed to load personal tasks.");
      } finally {
        if (active) setLoading(false);
      }
    })();

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (tagFilter === "all") return;
    if (!tagOptions.includes(tagFilter)) {
      setTagFilter("all");
    }
  }, [tagFilter, tagOptions]);

  const pendingGroups = useMemo(() => {
    const rows = tasks
      .filter((task) => task.status === "pending" && matchesTag(task, tagFilter))
      .sort(sortPendingTasks);
    return groupTasksByTag(rows);
  }, [tagFilter, tasks]);

  const completedGroups = useMemo(() => {
    const rows = tasks
      .filter((task) => task.status === "done" && matchesTag(task, tagFilter))
      .sort(sortCompletedTasks);
    return groupTasksByTag(rows);
  }, [tagFilter, tasks]);

  const completedCount = useMemo(
    () => completedGroups.reduce((sum, group) => sum + group.tasks.length, 0),
    [completedGroups]
  );

  async function handleCreateTask() {
    const title = addDraft.title.trim();
    if (!title) {
      setError("Task title is required.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const payload = {
        title,
        description: toNullable(addDraft.description),
        client_tag: toNullable(addDraft.client_tag),
        priority: addDraft.priority,
        due_date: toNullable(addDraft.due_date),
      };
      await createUserTask(payload);
      setAddDraft(EMPTY_DRAFT);
      setShowAddForm(false);
      await refreshTasks();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create task.");
    } finally {
      setSaving(false);
    }
  }

  async function handleToggle(task: UserTask) {
    setPendingActionTaskId(task.id);
    setError(null);
    try {
      await toggleUserTask(task.id);
      await refreshTasks();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update task status.");
    } finally {
      setPendingActionTaskId(null);
    }
  }

  function startEditing(task: UserTask) {
    setEditingTaskId(task.id);
    setEditDraft({
      title: task.title,
      description: task.description ?? "",
      client_tag: task.client_tag ?? "",
      priority: task.priority,
      due_date: normalizeDateForInput(task.due_date),
    });
  }

  async function handleSaveEdit(taskId: number) {
    const title = editDraft.title.trim();
    if (!title) {
      setError("Task title is required.");
      return;
    }
    setPendingActionTaskId(taskId);
    setError(null);
    try {
      await updateUserTask(taskId, {
        title,
        description: toNullable(editDraft.description),
        client_tag: toNullable(editDraft.client_tag),
        priority: editDraft.priority,
        due_date: toNullable(editDraft.due_date),
      });
      setEditingTaskId(null);
      setEditDraft(EMPTY_DRAFT);
      await refreshTasks();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save task.");
    } finally {
      setPendingActionTaskId(null);
    }
  }

  async function handleDelete(taskId: number) {
    if (!window.confirm("Delete this task?")) return;
    setPendingActionTaskId(taskId);
    setError(null);
    try {
      await deleteUserTask(taskId);
      if (editingTaskId === taskId) {
        setEditingTaskId(null);
        setEditDraft(EMPTY_DRAFT);
      }
      await refreshTasks();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete task.");
    } finally {
      setPendingActionTaskId(null);
    }
  }

  function renderTaskRow(task: UserTask, status: UserTaskStatus) {
    const isBusy = pendingActionTaskId === task.id;
    const doneDate = formatDate(task.completed_at);
    const dueDate = formatDate(task.due_date);
    const rowIsEditing = editingTaskId === task.id;

    return (
      <div key={task.id} className="space-y-2 rounded-md border bg-white px-3 py-2">
        <div className="flex items-center gap-2">
          <Checkbox
            checked={status === "done"}
            disabled={isBusy}
            onCheckedChange={() => {
              void handleToggle(task);
            }}
          />
          <button
            type="button"
            className="min-w-0 flex-1 text-left text-sm"
            disabled={isBusy}
            onClick={() => {
              void handleToggle(task);
            }}
          >
            <span className={status === "done" ? "line-through text-muted-foreground" : ""}>
              {task.title}
            </span>
          </button>
          {task.client_tag ? (
            <Badge variant="outline" className={`border ${tagBadgeClass(task.client_tag)}`}>
              {task.client_tag}
            </Badge>
          ) : null}
          <Badge variant="secondary" className={priorityBadgeClass[task.priority]}>
            {task.priority}
          </Badge>
          {status === "done" && doneDate ? (
            <Badge variant="outline" className="text-green-700">
              Done {doneDate}
            </Badge>
          ) : null}
          {status === "pending" && dueDate ? (
            <Badge variant="outline" className={isOverdue(task) ? "text-red-700" : "text-muted-foreground"}>
              Due {dueDate}
            </Badge>
          ) : null}
          <Button
            type="button"
            variant="ghost"
            size="icon-xs"
            disabled={isBusy}
            onClick={() => startEditing(task)}
          >
            <Pencil className="size-3.5" />
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon-xs"
            disabled={isBusy}
            onClick={() => {
              void handleDelete(task.id);
            }}
          >
            <Trash2 className="size-3.5" />
          </Button>
        </div>

        {task.description ? <p className="text-xs text-muted-foreground">{task.description}</p> : null}

        {rowIsEditing ? (
          <div className="grid gap-2 rounded-md border bg-neutral-50 p-2 sm:grid-cols-2">
            <Input
              value={editDraft.title}
              onChange={(event) =>
                setEditDraft((value) => ({ ...value, title: event.target.value }))
              }
              placeholder="Task title"
            />
            <Input
              value={editDraft.client_tag}
              onChange={(event) =>
                setEditDraft((value) => ({ ...value, client_tag: event.target.value }))
              }
              list="pm-task-client-tags"
              placeholder="Client tag"
            />
            <Select
              value={editDraft.priority}
              onValueChange={(value) =>
                setEditDraft((current) => ({
                  ...current,
                  priority: value as UserTaskPriority,
                }))
              }
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="low">Low</SelectItem>
                <SelectItem value="normal">Normal</SelectItem>
                <SelectItem value="high">High</SelectItem>
                <SelectItem value="urgent">Urgent</SelectItem>
              </SelectContent>
            </Select>
            <Input
              type="date"
              value={editDraft.due_date}
              onChange={(event) =>
                setEditDraft((value) => ({ ...value, due_date: event.target.value }))
              }
            />
            <Input
              className="sm:col-span-2"
              value={editDraft.description}
              onChange={(event) =>
                setEditDraft((value) => ({ ...value, description: event.target.value }))
              }
              placeholder="Description (optional)"
            />
            <div className="flex gap-2 sm:col-span-2">
              <Button
                type="button"
                size="sm"
                disabled={isBusy}
                onClick={() => {
                  void handleSaveEdit(task.id);
                }}
              >
                Save
              </Button>
              <Button
                type="button"
                size="sm"
                variant="outline"
                disabled={isBusy}
                onClick={() => {
                  setEditingTaskId(null);
                  setEditDraft(EMPTY_DRAFT);
                }}
              >
                Cancel
              </Button>
            </div>
          </div>
        ) : null}
      </div>
    );
  }

  return (
    <Card className="py-4">
      <CardHeader className="px-4 pb-2 sm:px-6">
        <div className="flex items-center justify-between gap-3">
          <CardTitle className="text-base">My Tasks</CardTitle>
          <Button
            type="button"
            size="sm"
            onClick={() => setShowAddForm((value) => !value)}
          >
            <Plus className="size-3.5" />
            {showAddForm ? "Cancel" : "Add Task"}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-3 px-4 sm:px-6">
        {error ? (
          <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {error}
          </div>
        ) : null}

        <datalist id="pm-task-client-tags">
          {tagOptions.map((tag) => (
            <option key={tag} value={tag} />
          ))}
        </datalist>

        <div className="grid gap-2 sm:grid-cols-[220px_auto_auto] sm:items-center">
          <Select value={tagFilter} onValueChange={setTagFilter}>
            <SelectTrigger>
              <SelectValue placeholder="Filter by client" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All clients</SelectItem>
              {tagOptions.map((tag) => (
                <SelectItem key={tag} value={tag}>
                  {tag}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => setShowCompleted((value) => !value)}
          >
            {showCompleted ? "Hide Completed" : "Show Completed"}
          </Button>
          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={() => {
              void refreshTasks();
            }}
          >
            Refresh
          </Button>
        </div>

        {showAddForm ? (
          <div className="grid gap-2 rounded-md border bg-neutral-50 p-3 sm:grid-cols-2">
            <Input
              value={addDraft.title}
              onChange={(event) =>
                setAddDraft((value) => ({ ...value, title: event.target.value }))
              }
              placeholder="Task title"
            />
            <Input
              value={addDraft.client_tag}
              onChange={(event) =>
                setAddDraft((value) => ({ ...value, client_tag: event.target.value }))
              }
              list="pm-task-client-tags"
              placeholder="Client tag"
            />
            <Select
              value={addDraft.priority}
              onValueChange={(value) =>
                setAddDraft((current) => ({
                  ...current,
                  priority: value as UserTaskPriority,
                }))
              }
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="low">Low</SelectItem>
                <SelectItem value="normal">Normal</SelectItem>
                <SelectItem value="high">High</SelectItem>
                <SelectItem value="urgent">Urgent</SelectItem>
              </SelectContent>
            </Select>
            <Input
              type="date"
              value={addDraft.due_date}
              onChange={(event) =>
                setAddDraft((value) => ({ ...value, due_date: event.target.value }))
              }
            />
            <Input
              className="sm:col-span-2"
              value={addDraft.description}
              onChange={(event) =>
                setAddDraft((value) => ({ ...value, description: event.target.value }))
              }
              placeholder="Description (optional)"
            />
            <div className="sm:col-span-2">
              <Button
                type="button"
                size="sm"
                disabled={saving}
                onClick={() => {
                  void handleCreateTask();
                }}
              >
                Add Task
              </Button>
            </div>
          </div>
        ) : null}

        {loading ? (
          <div className="rounded-md border bg-neutral-50 p-3 text-sm text-muted-foreground">
            Loading tasks...
          </div>
        ) : (
          <>
            <div className="space-y-2">
              {pendingGroups.length === 0 ? (
                <div className="rounded-md border border-dashed p-3 text-sm text-muted-foreground">
                  No pending tasks.
                </div>
              ) : (
                pendingGroups.map((group) => (
                  <div key={group.key} className="space-y-1.5">
                    <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                      {group.label}
                    </p>
                    <div className="space-y-2">
                      {group.tasks.map((task) => renderTaskRow(task, "pending"))}
                    </div>
                  </div>
                ))
              )}
            </div>

            {showCompleted ? (
              <section className="space-y-2">
                <button
                  type="button"
                  className="flex w-full items-center justify-between rounded-md border bg-neutral-50 px-3 py-2 text-left"
                  onClick={() => setCompletedCollapsed((value) => !value)}
                >
                  <span className="text-sm font-semibold">
                    Completed ({completedCount})
                  </span>
                  {completedCollapsed ? (
                    <ChevronRight className="size-4" />
                  ) : (
                    <ChevronDown className="size-4" />
                  )}
                </button>
                {!completedCollapsed ? (
                  completedGroups.length === 0 ? (
                    <div className="rounded-md border border-dashed p-3 text-sm text-muted-foreground">
                      No completed tasks.
                    </div>
                  ) : (
                    completedGroups.map((group) => (
                      <div key={group.key} className="space-y-1.5">
                        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                          {group.label}
                        </p>
                        <div className="space-y-2">
                          {group.tasks.map((task) => renderTaskRow(task, "done"))}
                        </div>
                      </div>
                    ))
                  )
                ) : null}
              </section>
            ) : null}
          </>
        )}
      </CardContent>
    </Card>
  );
}
