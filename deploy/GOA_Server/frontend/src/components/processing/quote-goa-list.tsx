"use client";

import Link from "next/link";
import { Fragment, useMemo, useState } from "react";
import { ChevronDown, ChevronRight, FileText, Play, UserRound } from "lucide-react";
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
import type { QuoteRow } from "@/lib/api";

type Status = QuoteRow["status"];

interface QuoteGoaListProps {
  quotes: QuoteRow[];
  loading: boolean;
  error: string | null;
  onProcessQuote: (quoteId: number) => void;
}

interface QuoteGroup {
  quoteId: number;
  quoteRef: string;
  customerName: string;
  machines: QuoteRow[];
  status: Status;
}

const statusConfig: Record<Status, { label: string; className: string }> = {
  draft: { label: "Draft", className: "bg-neutral-200 text-neutral-700" },
  processed: { label: "Processed", className: "bg-yellow-100 text-yellow-800" },
  ready: { label: "Ready", className: "bg-green-100 text-green-800" },
};

function compactMachineName(value: string): string {
  const line = (value || "").split(/\r?\n/, 1)[0] ?? "";
  const normalized = line.replace(/\s+/g, " ").trim();
  if (!normalized) return "Unassigned Machine";
  const splitters = [
    normalized.indexOf("\u2022"),
    normalized.indexOf("\u00B7"),
    normalized.toLowerCase().indexOf(" including:"),
    normalized.toLowerCase().indexOf(" includes:"),
  ].filter((index) => index >= 0);
  if (splitters.length === 0) return normalized;
  const compact = normalized.slice(0, Math.min(...splitters)).trim();
  return compact || normalized;
}

function aggregateStatus(machines: QuoteRow[]): Status {
  if (machines.length === 0) return "draft";
  if (machines.every((machine) => machine.status === "ready")) return "ready";
  if (machines.some((machine) => machine.status === "processed" || machine.status === "ready")) {
    return "processed";
  }
  return "draft";
}

function buildQuoteGroups(rows: QuoteRow[]): QuoteGroup[] {
  const map = new Map<number, QuoteGroup>();
  for (const row of rows) {
    const existing = map.get(row.quoteId);
    if (existing) {
      existing.machines.push(row);
      existing.status = aggregateStatus(existing.machines);
      continue;
    }
    map.set(row.quoteId, {
      quoteId: row.quoteId,
      quoteRef: row.quoteRef,
      customerName: row.clientName,
      machines: [row],
      status: aggregateStatus([row]),
    });
  }
  return Array.from(map.values()).sort((a, b) => b.quoteId - a.quoteId);
}

function rowActionCell(row: QuoteRow, onProcessQuote: (quoteId: number) => void) {
  return (
    <div className="flex items-center justify-end gap-1">
      {row.machineTemplateId && row.status !== "draft" ? (
        <Button variant="ghost" size="sm" asChild>
          <Link href={`/goa/${row.machineTemplateId}`}>
            <FileText className="size-3.5 sm:mr-1" />
            <span className="hidden sm:inline">Edit GOA</span>
          </Link>
        </Button>
      ) : null}
      <Button variant="ghost" size="sm" onClick={() => onProcessQuote(row.quoteId)}>
        <Play className="size-3.5 sm:mr-1" />
        <span className="hidden sm:inline">Process</span>
      </Button>
      <Button variant="ghost" size="sm" asChild>
        <Link href={`/client-info?quote=${row.quoteId}`}>
          <UserRound className="size-3.5 sm:mr-1" />
          <span className="hidden sm:inline">View Client</span>
        </Link>
      </Button>
    </div>
  );
}

export function QuoteGoaList({ quotes, loading, error, onProcessQuote }: QuoteGoaListProps) {
  const [expandedQuotes, setExpandedQuotes] = useState<Record<number, boolean>>({});

  const groups = useMemo(() => buildQuoteGroups(quotes), [quotes]);

  function toggleQuote(quoteId: number) {
    setExpandedQuotes((previous) => ({
      ...previous,
      [quoteId]: !previous[quoteId],
    }));
  }

  return (
    <div className="rounded-md border bg-white">
      <Table className="min-w-[980px]">
        <TableHeader>
          <TableRow>
            <TableHead>Quote Ref</TableHead>
            <TableHead>Customer</TableHead>
            <TableHead>Machine</TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="text-right">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {loading ? (
            <TableRow>
              <TableCell colSpan={5} className="h-24 text-center text-muted-foreground">
                Loading quotes...
              </TableCell>
            </TableRow>
          ) : error ? (
            <TableRow>
              <TableCell colSpan={5} className="h-24 text-center text-red-700">
                Failed to load quotes: {error}
              </TableCell>
            </TableRow>
          ) : groups.length === 0 ? (
            <TableRow>
              <TableCell colSpan={5} className="h-24 text-center text-muted-foreground">
                No quotes found.
              </TableCell>
            </TableRow>
          ) : (
            groups.map((group) => {
              const status = statusConfig[group.status];
              const expanded = Boolean(expandedQuotes[group.quoteId]);
              const multiMachine = group.machines.length > 1;
              const primaryMachine = group.machines[0];
              return (
                <Fragment key={`quote-${group.quoteId}`}>
                  <TableRow key={`quote-${group.quoteId}`}>
                    <TableCell className="font-semibold">{group.quoteRef}</TableCell>
                    <TableCell>{group.customerName}</TableCell>
                    <TableCell>
                      {multiMachine ? (
                        <button
                          type="button"
                          onClick={() => toggleQuote(group.quoteId)}
                          className="inline-flex items-center gap-1 rounded px-1 py-0.5 hover:bg-neutral-100"
                        >
                          {expanded ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" />}
                          {group.machines.length} machines
                        </button>
                      ) : (
                        compactMachineName(primaryMachine?.machineName ?? "")
                      )}
                    </TableCell>
                    <TableCell>
                      <Badge className={status.className} variant="secondary">
                        {status.label}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      {primaryMachine ? rowActionCell(primaryMachine, onProcessQuote) : null}
                    </TableCell>
                  </TableRow>
                  {multiMachine && expanded
                    ? group.machines.map((machine) => (
                        <TableRow key={`machine-${machine.id}`} className="bg-neutral-50/40">
                          <TableCell className="pl-8 text-muted-foreground">└</TableCell>
                          <TableCell className="text-sm text-muted-foreground">
                            {group.customerName}
                          </TableCell>
                          <TableCell>{compactMachineName(machine.machineName)}</TableCell>
                          <TableCell>
                            <Badge className={statusConfig[machine.status].className} variant="secondary">
                              {statusConfig[machine.status].label}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-right">
                            {rowActionCell(machine, onProcessQuote)}
                          </TableCell>
                        </TableRow>
                      ))
                    : null}
                </Fragment>
              );
            })
          )}
        </TableBody>
      </Table>
    </div>
  );
}
