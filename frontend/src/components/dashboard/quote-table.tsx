"use client";

import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { type QuoteRow } from "@/lib/api";
import { FileText, Play, UserRound } from "lucide-react";

const statusConfig = {
  draft: { label: "Draft", className: "bg-neutral-200 text-neutral-700" },
  processed: { label: "Processed", className: "bg-yellow-100 text-yellow-800" },
  ready: { label: "Ready", className: "bg-green-100 text-green-800" },
} as const;

interface MachineTableProps {
  quotes: QuoteRow[];
}

function compactMachineName(value: string): string {
  const firstLine = (value || "").split(/\r?\n/, 1)[0] ?? "";
  const normalized = firstLine.replace(/\s+/g, " ").trim();
  if (!normalized) return "Unassigned Machine";

  const stopCandidates = [
    normalized.indexOf("\u2022"),
    normalized.indexOf("\u00B7"),
    normalized.toLowerCase().indexOf(" including:"),
    normalized.toLowerCase().indexOf(" includes:"),
  ].filter((index) => index >= 0);

  if (stopCandidates.length === 0) {
    return normalized;
  }

  const stopIndex = Math.min(...stopCandidates);
  const compact = normalized.slice(0, stopIndex).trim();
  return compact || normalized;
}

export function MachineTable({ quotes }: MachineTableProps) {
  return (
    <div className="rounded-md border">
      <Table className="min-w-[1040px]">
        <TableHeader>
          <TableRow>
            <TableHead>Customer</TableHead>
            <TableHead>Machine</TableHead>
            <TableHead>Quote Ref</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Date</TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {quotes.length === 0 && (
            <TableRow>
              <TableCell colSpan={6} className="h-24 text-center text-muted-foreground">
                No machines found.
              </TableCell>
            </TableRow>
          )}

          {quotes.map((row) => {
            const cfg = statusConfig[row.status];
            const processHref =
              row.machineId != null
                ? `/processing?quote=${row.quoteId}&machine=${row.machineId}`
                : `/processing?quote=${row.quoteId}`;
            return (
              <TableRow key={row.id}>
                <TableCell className="font-semibold">{row.clientName}</TableCell>
                <TableCell>
                  <p className="font-semibold" title={row.machineName}>
                    {compactMachineName(row.machineName)}
                  </p>
                </TableCell>
                <TableCell>{row.quoteRef}</TableCell>
                <TableCell>
                  <Badge className={cfg.className} variant="secondary">
                    {cfg.label}
                  </Badge>
                </TableCell>
                <TableCell>{row.date}</TableCell>
                <TableCell className="text-right">
                  <div className="flex items-center justify-end gap-1">
                    <Button variant="ghost" size="sm" asChild>
                      <Link href={`/client-info?quote=${row.quoteId}`}>
                        <UserRound className="size-3.5 sm:mr-1" />
                        <span className="hidden sm:inline">Client Info</span>
                      </Link>
                    </Button>
                    {row.machineTemplateId && row.status !== "draft" ? (
                      <Button variant="ghost" size="sm" asChild>
                        <Link href={`/goa/${row.machineTemplateId}`}>
                          <FileText className="size-3.5 sm:mr-1" />
                          <span className="hidden sm:inline">Edit GOA</span>
                        </Link>
                      </Button>
                    ) : null}
                    <Button variant="ghost" size="sm" asChild>
                      <Link href={processHref}>
                        <Play className="size-3.5 sm:mr-1" />
                        <span className="hidden sm:inline">Process</span>
                      </Link>
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
