"use client";

import { Input } from "@/components/ui/input";
import { AlertTriangle } from "lucide-react";

interface FieldEditorProps {
  fields: Record<string, { value: string; confidence: number }>;
  onChange: (key: string, value: string) => void;
}

function confidenceColor(score: number) {
  if (score >= 0.85) return "bg-green-500";
  if (score >= 0.6) return "bg-yellow-500";
  return "bg-red-500";
}

export function FieldEditor({ fields, onChange }: FieldEditorProps) {
  const suspicious = Object.entries(fields).filter(
    ([, f]) => f.confidence < 0.6
  );

  return (
    <div className="space-y-4">
      {suspicious.length > 0 && (
        <div className="flex items-start gap-2 rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-800">
          <AlertTriangle className="mt-0.5 size-4 shrink-0" />
          <div>
            <p className="font-medium">Suspicious fields detected</p>
            <p>
              The following fields have low confidence and may need review:{" "}
              {suspicious.map(([k]) => k).join(", ")}
            </p>
          </div>
        </div>
      )}
      <div className="grid gap-4 sm:grid-cols-2">
        {Object.entries(fields).map(([key, field]) => (
          <div key={key} className="space-y-1">
            <label className="flex items-center gap-2 text-sm font-medium">
              <span
                className={`inline-block size-2.5 rounded-full ${confidenceColor(field.confidence)}`}
                title={`Confidence: ${Math.round(field.confidence * 100)}%`}
              />
              {key}
            </label>
            <Input
              value={field.value}
              onChange={(e) => onChange(key, e.target.value)}
            />
          </div>
        ))}
      </div>
    </div>
  );
}
