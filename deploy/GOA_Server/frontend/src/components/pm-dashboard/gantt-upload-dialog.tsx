"use client";

import { useState } from "react";
import { Loader2, Upload } from "lucide-react";
import { uploadGanttPdf } from "@/lib/api";
import { FileUploadPicker } from "@/components/shared/file-upload-picker";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

interface GanttUploadDialogProps {
  projectId: number;
  onUploaded?: () => void;
}

export function GanttUploadDialog({ projectId, onUploaded }: GanttUploadDialogProps) {
  const [open, setOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function reset() {
    setFile(null);
    setUploading(false);
    setError(null);
  }

  async function handleUpload() {
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      await uploadGanttPdf(projectId, file);
      onUploaded?.();
      setOpen(false);
      reset();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to upload Gantt PDF.");
    } finally {
      setUploading(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(value) => {
        setOpen(value);
        if (!value) reset();
      }}
    >
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          <Upload className="mr-2 size-4" />
          Upload Gantt
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Upload Gantt PDF</DialogTitle>
          <DialogDescription>
            Upload a PDF to parse production timeline details for this project.
          </DialogDescription>
        </DialogHeader>
        <FileUploadPicker
          file={file}
          onSelect={setFile}
          emptyLabel="Click to choose a PDF file"
          variant="compact"
        />
        {error ? (
          <div className="rounded-md border border-red-200 bg-red-50 p-2 text-sm text-red-700">
            {error}
          </div>
        ) : null}
        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => {
              setOpen(false);
              reset();
            }}
            disabled={uploading}
          >
            Cancel
          </Button>
          <Button type="button" onClick={() => void handleUpload()} disabled={!file || uploading}>
            {uploading ? <Loader2 className="mr-2 size-4 animate-spin" /> : null}
            {uploading ? "Uploading..." : "Upload"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
