"use client";

import { useRef } from "react";
import { Upload } from "lucide-react";
import { cn } from "@/lib/utils";

type FileUploadPickerVariant = "dropzone" | "compact";

interface FileUploadPickerProps {
  file: File | null;
  onSelect: (file: File | null) => void;
  emptyLabel: string;
  accept?: string;
  variant?: FileUploadPickerVariant;
  className?: string;
}

export function FileUploadPicker({
  file,
  onSelect,
  emptyLabel,
  accept = ".pdf,application/pdf",
  variant = "dropzone",
  className,
}: FileUploadPickerProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);

  return (
    <>
      <button
        type="button"
        className={cn(
          variant === "dropzone"
            ? "flex w-full cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-8 text-center transition-colors hover:border-primary/50"
            : "w-full rounded-md border border-dashed p-4 text-left text-sm hover:border-neutral-400",
          className
        )}
        onClick={() => inputRef.current?.click()}
      >
        {variant === "dropzone" ? (
          <Upload className="mb-2 size-8 text-muted-foreground" />
        ) : null}
        <span className="text-sm text-muted-foreground">
          {file ? file.name : emptyLabel}
        </span>
      </button>
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        className="hidden"
        onChange={(event) => onSelect(event.target.files?.[0] ?? null)}
      />
    </>
  );
}
