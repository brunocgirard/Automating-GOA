"use client";

import { useCallback, useEffect, useState } from "react";
import {
  fetchAtRiskSummary,
  fetchProject,
  fetchProjects,
  updateTaskStatus,
} from "@/lib/api";
import type { AtRiskSummary, ProjectDetail, ProjectListItem, TaskStatus } from "@/lib/types";
import { AlertStrip } from "@/components/pm-dashboard/alert-strip";
import { KanbanBoard } from "@/components/pm-dashboard/kanban-board";
import { ProjectDetailSheet } from "@/components/pm-dashboard/project-detail-sheet";
import { PersonalTaskBoard } from "@/components/pm-dashboard/personal-task-board";
import { UploadDialog } from "@/components/dashboard/upload-dialog";

export default function PmDashboardPageClient() {
  const [projects, setProjects] = useState<ProjectListItem[]>([]);
  const [atRisk, setAtRisk] = useState<AtRiskSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(null);
  const [selectedProject, setSelectedProject] = useState<ProjectDetail | null>(null);
  const [updatingTaskId, setUpdatingTaskId] = useState<number | null>(null);

  const loadSurface = useCallback(async () => {
    setError(null);
    const [projectRows, atRiskSummary] = await Promise.all([
      fetchProjects(),
      fetchAtRiskSummary(),
    ]);
    setProjects(projectRows);
    setAtRisk(atRiskSummary);
  }, []);

  useEffect(() => {
    let active = true;
    setLoading(true);
    void loadSurface()
      .catch((err) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Failed to load PM dashboard.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [loadSurface]);

  const refreshSelectedProject = useCallback(async () => {
    if (selectedProjectId == null) return;
    const detail = await fetchProject(selectedProjectId);
    setSelectedProject(detail);
  }, [selectedProjectId]);

  useEffect(() => {
    let active = true;
    if (selectedProjectId == null) {
      setSelectedProject(null);
      return () => {
        active = false;
      };
    }
    void fetchProject(selectedProjectId)
      .then((project) => {
        if (!active) return;
        setSelectedProject(project);
      })
      .catch(() => {
        if (active) setSelectedProject(null);
      });
    return () => {
      active = false;
    };
  }, [selectedProjectId]);

  async function handleTaskStatusChange(taskId: number, status: TaskStatus) {
    setUpdatingTaskId(taskId);
    try {
      await updateTaskStatus(taskId, status);
      await Promise.all([refreshSelectedProject(), loadSurface()]);
    } finally {
      setUpdatingTaskId(null);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight">PM Dashboard</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Minimalist project status board with task-level intervention controls.
          </p>
        </div>
        <div className="flex flex-col gap-2 sm:flex-row">
          <UploadDialog
            onUploaded={() => {
              void loadSurface();
            }}
            triggerLabel="New Project"
            triggerIcon="plus"
          />
        </div>
      </div>

      <AlertStrip atRisk={atRisk} loading={loading} />

      <PersonalTaskBoard />

      {loading ? (
        <div className="rounded-md border bg-white p-8 text-sm text-muted-foreground">
          Loading projects...
        </div>
      ) : error ? (
        <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          Failed to load PM dashboard: {error}
        </div>
      ) : projects.length === 0 ? (
        <div className="rounded-md border bg-white p-8 text-sm text-muted-foreground">
          No projects available yet. Use New Project to upload a quote and create the PM project.
        </div>
      ) : (
        <KanbanBoard projects={projects} onSelectProject={setSelectedProjectId} />
      )}

      <ProjectDetailSheet
        open={selectedProjectId != null}
        project={selectedProject}
        updatingTaskId={updatingTaskId}
        onOpenChange={(open) => {
          if (!open) {
            setSelectedProjectId(null);
            setSelectedProject(null);
          }
        }}
        onTaskStatusChange={handleTaskStatusChange}
      />
    </div>
  );
}
