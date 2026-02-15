"use client";

import { Button } from "@/components/ui/button";
import { HtmlPreviewFrame } from "@/components/ui/html-preview-frame";
import { sanitizeHtml } from "@/lib/sanitize-html";
import { Printer } from "lucide-react";
import { useMemo } from "react";

interface ReportViewerProps {
  html: string | null;
}

export function ReportViewer({ html }: ReportViewerProps) {
  const safeHtml = useMemo(() => sanitizeHtml(html ?? ""), [html]);

  function handlePrint() {
    if (!safeHtml) return;
    const printWindow = window.open("", "_blank");
    if (!printWindow) return;
    printWindow.document.write(
      `<html><head><title>Report</title></head><body style="font-family:system-ui,sans-serif;padding:24px">${safeHtml}</body></html>`
    );
    printWindow.document.close();
    printWindow.print();
  }

  if (!html) {
    return (
      <p className="py-12 text-center text-sm text-muted-foreground">
        Select a machine with a generated template to view the build report.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-end print:hidden">
        <Button onClick={handlePrint} disabled={!safeHtml} className="w-full sm:w-auto">
          <Printer className="mr-1 size-4" />
          Print / Download
        </Button>
      </div>
      <HtmlPreviewFrame html={html} title="Report Viewer" className="prose prose-sm max-w-none border-0" />
    </div>
  );
}
