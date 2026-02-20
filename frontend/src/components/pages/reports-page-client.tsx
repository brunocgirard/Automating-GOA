"use client";

import { useEffect, useMemo, useState } from "react";
import {
  fetchClients,
  fetchMachineReport,
  fetchQuotes,
  type Client,
  type QuoteRow,
} from "@/lib/api";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { HtmlPreviewFrame } from "@/components/ui/html-preview-frame";
import { sanitizeHtml } from "@/lib/sanitize-html";
import { Printer, Download } from "lucide-react";

export default function ReportsPage() {
  const [clients, setClients] = useState<Client[]>([]);
  const [quotes, setQuotes] = useState<QuoteRow[]>([]);
  const [selectedClient, setSelectedClient] = useState("__all__");
  const [selectedQuote, setSelectedQuote] = useState("");
  const [reportHtml, setReportHtml] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    void Promise.all([fetchClients(), fetchQuotes()])
      .then(([clientRows, quoteRows]) => {
        if (!active) return;
        setClients(clientRows);
        setQuotes(quoteRows);
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Failed to load reports data.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  const filteredQuotes = useMemo(() => {
    if (selectedClient === "__all__") return quotes;
    return quotes.filter((quote) => quote.clientId === selectedClient);
  }, [quotes, selectedClient]);

  const selectedQuoteData = filteredQuotes.find((quote) => quote.id === selectedQuote);
  const safeReportHtml = useMemo(() => sanitizeHtml(reportHtml ?? ""), [reportHtml]);

  useEffect(() => {
    if (!selectedQuoteData?.machineId) {
      return;
    }

    let active = true;

    void fetchMachineReport(selectedQuoteData.machineId)
      .then((report) => {
        if (active) setReportHtml(report.html);
      })
      .catch((err) => {
        if (active) {
          setReportHtml(null);
          setError(err instanceof Error ? err.message : "Failed to load report.");
        }
      });

    return () => {
      active = false;
    };
  }, [selectedQuoteData?.machineId]);

  function handlePrint() {
    if (!safeReportHtml) return;
    const printWindow = window.open("", "_blank");
    if (!printWindow) return;
    printWindow.document.write(
      `<html><head><title>Report</title></head><body style="font-family:system-ui,sans-serif;padding:24px">${safeReportHtml}</body></html>`
    );
    printWindow.document.close();
    printWindow.print();
  }

  function handleSaveHtml() {
    if (!reportHtml) return;

    const parts = [selectedQuoteData?.quoteRef, selectedQuoteData?.machineName]
      .filter(Boolean)
      .map((part) =>
        String(part)
          .trim()
          .replace(/[^a-zA-Z0-9._-]+/g, "_")
          .replace(/^_+|_+$/g, "")
      )
      .filter((part) => part.length > 0);

    const filename = `${parts.join("_") || "machine_report"}.html`;
    const blob = new Blob([reportHtml], { type: "text/html;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">Reports</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          View, save as HTML, or print machine build reports.
        </p>
      </div>

      {loading ? (
        <div className="rounded-md border bg-white p-8 text-sm text-muted-foreground">
          Loading reports data...
        </div>
      ) : (
        <>
          <div className="flex flex-col gap-4 lg:flex-row lg:flex-wrap lg:items-end">
            <div className="w-full space-y-1.5 sm:w-auto">
              <label className="text-sm font-medium">Client</label>
              <Select
                value={selectedClient}
                onValueChange={(value) => {
                  setSelectedClient(value);
                  setSelectedQuote("");
                  setReportHtml(null);
                  setError(null);
                }}
              >
                <SelectTrigger className="w-full sm:w-[260px]">
                  <SelectValue placeholder="All clients" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__all__">All clients</SelectItem>
                  {clients.map((client) => (
                    <SelectItem key={client.id} value={client.id}>
                      {client.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="w-full space-y-1.5 sm:w-auto">
              <label className="text-sm font-medium">Machine / Quote</label>
              <Select
                value={selectedQuote}
                onValueChange={(value) => {
                  setSelectedQuote(value);
                  setReportHtml(null);
                  setError(null);
                }}
              >
                <SelectTrigger className="w-full sm:w-[360px]">
                  <SelectValue placeholder="Select a machine..." />
                </SelectTrigger>
                <SelectContent>
                  {filteredQuotes.map((quote) => (
                    <SelectItem key={quote.id} value={quote.id}>
                      {quote.quoteRef} - {quote.machineName}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {reportHtml && (
              <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row">
                <Button variant="outline" size="sm" onClick={handlePrint}>
                  <Printer className="mr-2 h-4 w-4" />
                  Print / Save PDF
                </Button>
                <Button variant="outline" size="sm" onClick={handleSaveHtml}>
                  <Download className="mr-2 h-4 w-4" />
                  Save HTML
                </Button>
              </div>
            )}
          </div>

          <Separator />

          {selectedQuoteData && (
            <div className="flex items-center gap-3 text-sm">
              <span className="font-medium">{selectedQuoteData.quoteRef}</span>
              <Badge
                variant={
                  selectedQuoteData.status === "ready"
                    ? "default"
                    : selectedQuoteData.status === "processed"
                      ? "secondary"
                      : "outline"
                }
              >
                {selectedQuoteData.status}
              </Badge>
              <span className="text-muted-foreground">{selectedQuoteData.clientName}</span>
            </div>
          )}

          {error && (
            <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
              {error}
            </div>
          )}

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Report Preview</CardTitle>
            </CardHeader>
            <CardContent>
              {reportHtml ? (
                <HtmlPreviewFrame
                  html={reportHtml}
                  title="Machine Report Preview"
                  className="prose prose-sm max-w-none border-0"
                />
              ) : (
                <p className="py-12 text-center text-sm text-muted-foreground">
                  Select a machine with a generated template to view the build report.
                </p>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
