"use client";

import { useMemo } from "react";
import { cn } from "@/lib/utils";
import { DEFAULT_PREVIEW_APPEND_STYLE, sanitizeHtml } from "@/lib/sanitize-html";

interface HtmlPreviewFrameProps {
  html: string;
  title: string;
  className?: string;
  minHeight?: number;
}

export function HtmlPreviewFrame({
  html,
  title,
  className,
  minHeight = 720,
}: HtmlPreviewFrameProps) {
  const safeHtml = useMemo(
    () =>
      sanitizeHtml(html, {
        preserveDocument: true,
        allowStyleTags: true,
        stripNoPrint: true,
        forceReadonlyBody: true,
        appendStyleBlock: DEFAULT_PREVIEW_APPEND_STYLE,
      }),
    [html]
  );

  return (
    <iframe
      title={title}
      srcDoc={safeHtml}
      sandbox="allow-same-origin"
      className={cn("w-full rounded-md border bg-white", className)}
      style={{ minHeight: `${minHeight}px` }}
    />
  );
}
