"use client";

import { Check, Upload, Cpu, FileOutput } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ProcessingStep } from "@/lib/types";

type StepVariant = "full" | "machine-direct";

const fullSteps: { key: ProcessingStep; label: string; icon: React.ElementType }[] = [
  { key: "load-quote", label: "Select Quote", icon: Upload },
  { key: "select-machine", label: "Select Machine", icon: Cpu },
  { key: "process-machine", label: "Process", icon: FileOutput },
];

const directSteps: { key: ProcessingStep; label: string; icon: React.ElementType }[] = [
  { key: "load-quote", label: "Load Machine", icon: Upload },
  { key: "process-machine", label: "Process", icon: FileOutput },
];

const stepIndex = (
  current: ProcessingStep,
  steps: { key: ProcessingStep; label: string; icon: React.ElementType }[]
) => steps.findIndex((entry) => entry.key === current);

export function StepIndicator({
  current,
  variant = "full",
}: {
  current: ProcessingStep;
  variant?: StepVariant;
}) {
  const steps = variant === "machine-direct" ? directSteps : fullSteps;
  const ci = stepIndex(current, steps);
  const minWidthClass = variant === "machine-direct" ? "min-w-[20rem]" : "min-w-[28rem]";
  const maxWidthClass = variant === "machine-direct" ? "max-w-lg" : "max-w-xl";

  return (
    <div className="mb-8 w-full overflow-x-auto">
      <div className={cn("mx-auto flex items-center justify-between", minWidthClass, maxWidthClass)}>
        {steps.map((step, i) => {
          const completed = i < ci;
          const active = i === ci;
          const Icon = step.icon;
          return (
            <div key={step.key} className="flex flex-1 items-center last:flex-none">
              <div className="flex flex-col items-center gap-1">
                <div
                  className={cn(
                    "flex h-10 w-10 items-center justify-center rounded-full border-2 transition-colors",
                    completed && "border-green-600 bg-green-600 text-white",
                    active && "border-[#c00000] bg-[#c00000] text-white",
                    !completed && !active && "border-neutral-300 text-neutral-400"
                  )}
                >
                  {completed ? <Check className="h-5 w-5" /> : <Icon className="h-5 w-5" />}
                </div>
                <span
                  className={cn(
                    "whitespace-nowrap text-xs font-medium",
                    active && "text-[#c00000]",
                    completed && "text-green-600",
                    !active && !completed && "text-neutral-400"
                  )}
                >
                  {step.label}
                </span>
              </div>
              {i < steps.length - 1 && (
                <div
                  className={cn(
                    "mx-2 mt-[-1.25rem] h-0.5 flex-1",
                    i < ci ? "bg-green-600" : "bg-neutral-200"
                  )}
                />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
