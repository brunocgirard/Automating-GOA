"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { fetchMachineReport, getQuoteDetail, type QuoteDetail } from "@/lib/api";
import { useFetch } from "@/hooks/use-fetch";
import { HtmlPreviewFrame } from "@/components/ui/html-preview-frame";
import { Button } from "@/components/ui/button";
import { sanitizeHtml } from "@/lib/sanitize-html";
import { ArrowLeft, Printer } from "lucide-react";

function isMissingGoaTemplateError(error: unknown): boolean {
  if (!(error instanceof Error)) return false;
  return error.message.includes("Template 'GOA' not found for machine");
}

interface QuotePreviewPageClientProps {
  id: string;
}

export default function QuotePreviewPageClient({ id }: QuotePreviewPageClientProps) {
  const [reportHtml, setReportHtml] = useState<string | null>(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const { data: detail, loading: detailLoading, error: detailError } = useFetch<QuoteDetail>(
    async () => {
      try {
        return await getQuoteDetail(id);
      } catch (err) {
        throw err instanceof Error ? err : new Error("Failed to load quote.");
      }
    },
    [id]
  );
  const loading = detailLoading || reportLoading;
  const error = previewError ?? detailError;
  const safeReportHtml = useMemo(() => sanitizeHtml(reportHtml ?? ""), [reportHtml]);

  useEffect(() => {
    setReportHtml(null);
    setPreviewError(null);
    setReportLoading(false);
  }, [id]);

  useEffect(() => {
    if (!detail) {
      setReportHtml(null);
      setPreviewError(null);
      setReportLoading(false);
      return;
    }

    if (!detail.machineId) {
      setReportHtml(null);
      setPreviewError(null);
      setReportLoading(false);
      return;
    }

    let active = true;
    setReportLoading(true);
    setPreviewError(null);
    setReportHtml(null);

    void fetchMachineReport(detail.machineId)
      .then((report) => {
        if (active) setReportHtml(report.html);
      })
      .catch((err) => {
        if (!active) return;
        if (isMissingGoaTemplateError(err)) {
          setReportHtml(null);
          setPreviewError(null);
          return;
        }
        setPreviewError(err instanceof Error ? err.message : "Failed to load report preview.");
      })
      .finally(() => {
        if (active) setReportLoading(false);
      });

    return () => {
      active = false;
    };
  }, [detail?.quoteRef, detail?.machineId]);

  function handlePrint() {
    if (!safeReportHtml) return;
    const printWindow = window.open("", "_blank");
    if (!printWindow) return;
    printWindow.document.write(
      `<html><head><title>Report Preview</title></head><body style="font-family:system-ui,sans-serif;padding:24px">${safeReportHtml}</body></html>`
    );
    printWindow.document.close();
    printWindow.print();
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between print:hidden">
        <Button variant="ghost" size="sm" asChild className="w-full sm:w-auto">
          <Link href={`/client-info?quote=${id}`}>
            <ArrowLeft className="mr-1 size-4" />
            Back to Client Info
          </Link>
        </Button>
        <Button onClick={handlePrint} disabled={!safeReportHtml} className="w-full sm:w-auto">
          <Printer className="mr-1 size-4" />
          Print / Download
        </Button>
      </div>

      {loading ? (
        <div className="rounded-md border bg-white p-8 text-sm text-muted-foreground">
          Loading preview...
        </div>
      ) : error ? (
        <div className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          Failed to load preview: {error}
        </div>
      ) : reportHtml ? (
        <HtmlPreviewFrame
          html={reportHtml}
          title="Quote Report Preview"
          className="rounded-lg border bg-white p-4 shadow-sm print:border-none print:shadow-none"
          minHeight={760}
        />
      ) : detail ? (
        <div className="rounded-md border bg-white p-8 text-sm text-muted-foreground">
          No report template found for {detail.quoteRef}. Save template fields first, then preview again.
        </div>
      ) : (
        <div className="rounded-md border bg-white p-8 text-sm text-muted-foreground">
          Quote not found.
        </div>
      )}
    </div>
  );
}
