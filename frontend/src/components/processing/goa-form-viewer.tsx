"use client";

import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
} from "react";
import { cn } from "@/lib/utils";

const GOA_PARENT_SOURCE = "GOA_APP";
const GOA_FORM_SOURCE = "GOA_FORM";
const EMBEDDED_FORM_STYLE_TAG =
  '<style data-goa-embedded-style="true">.no-print { display: none !important; }</style>';

export interface GoaFormViewerHandle {
  getCurrentData: () => Promise<Record<string, string>>;
}

interface GoaFormViewerProps {
  html: string;
  confidenceScores?: Record<string, number>;
  initialData?: Record<string, string>;
  className?: string;
}

type PendingRequest = {
  resolve: (data: Record<string, string>) => void;
  reject: (error: Error) => void;
  timeoutId: number;
};

export const GoaFormViewer = forwardRef<GoaFormViewerHandle, GoaFormViewerProps>(
  function GoaFormViewer({ html, confidenceScores, initialData, className }, ref) {
    const iframeRef = useRef<HTMLIFrameElement | null>(null);
    const pendingRequestRef = useRef<PendingRequest | null>(null);
    const [iframeHeight, setIframeHeight] = useState(900);
    const [readyTick, setReadyTick] = useState(0);

    const frameKey = useMemo(() => {
      let hash = 0;
      for (let index = 0; index < html.length; index += 1) {
        hash = (hash * 31 + html.charCodeAt(index)) | 0;
      }
      return `${html.length}:${hash}`;
    }, [html]);

    const embeddedHtml = useMemo(() => {
      if (!html) return html;
      if (html.includes('data-goa-embedded-style="true"')) return html;
      if (html.includes("</head>")) {
        return html.replace("</head>", `${EMBEDDED_FORM_STYLE_TAG}</head>`);
      }
      return `${EMBEDDED_FORM_STYLE_TAG}${html}`;
    }, [html]);

    const postToFrame = useCallback(
      (type: string, payload?: Record<string, unknown>) => {
        const frame = iframeRef.current?.contentWindow;
        if (!frame || typeof window === "undefined") return;
        frame.postMessage(
          {
            source: GOA_PARENT_SOURCE,
            type,
            ...(payload ?? {}),
          },
          window.location.origin
        );
      },
      []
    );

    const readDataFromFrameDom = useCallback((): Record<string, string> | null => {
      const documentRef = iframeRef.current?.contentDocument;
      if (!documentRef) return null;

      const data: Record<string, string> = {};

      const fields = documentRef.querySelectorAll<
        HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement
      >("input[name], textarea[name], select[name]");

      fields.forEach((field) => {
        const key = field.getAttribute("name");
        if (!key) return;
        const tagName = field.tagName.toLowerCase();
        const inputType =
          tagName === "input" ? (field.getAttribute("type") ?? "").toLowerCase() : "";
        if (tagName === "input" && inputType === "checkbox") {
          const checked = (field as { checked?: boolean }).checked === true;
          data[key] = checked ? "YES" : "NO";
          return;
        }
        data[key] = field.value ?? "";
      });

      const formattedFields =
        documentRef.querySelectorAll<HTMLElement>(".formatted-list[data-field-key]");
      formattedFields.forEach((field) => {
        const key = field.dataset.fieldKey?.trim();
        if (!key || data[key] !== undefined) return;
        const storedValue = field.dataset.fieldValue;
        data[key] = storedValue ?? field.textContent?.trim() ?? "";
      });

      return data;
    }, []);

    useEffect(() => {
      const onMessage = (event: MessageEvent) => {
        if (
          typeof window !== "undefined" &&
          event.origin !== window.location.origin &&
          event.origin !== "null"
        ) {
          return;
        }
        if (event.source !== iframeRef.current?.contentWindow) return;
        const payload = event.data as
          | {
              source?: string;
              type?: string;
              data?: Record<string, string>;
              height?: number;
            }
          | undefined;

        if (!payload || payload.source !== GOA_FORM_SOURCE || !payload.type) return;

        if (payload.type === "GOA_FORM_READY") {
          setReadyTick((value) => value + 1);
          return;
        }

        if (payload.type === "GOA_FORM_HEIGHT" && typeof payload.height === "number") {
          const nextHeight = Math.max(500, Math.min(payload.height, 5000));
          setIframeHeight(nextHeight);
          return;
        }

        if (payload.type === "GOA_FORM_DATA") {
          const pending = pendingRequestRef.current;
          if (!pending) return;
          window.clearTimeout(pending.timeoutId);
          pendingRequestRef.current = null;
          const domData = readDataFromFrameDom();
          if (domData && Object.keys(domData).length > 0) {
            pending.resolve(domData);
            return;
          }
          pending.resolve(payload.data ?? {});
        }
      };

      window.addEventListener("message", onMessage);
      return () => {
        window.removeEventListener("message", onMessage);
      };
    }, [readDataFromFrameDom]);

    useEffect(() => {
      if (readyTick === 0 || !initialData) return;
      postToFrame("FILL_DATA", { data: initialData });
    }, [initialData, postToFrame, readyTick]);

    useEffect(() => {
      if (readyTick === 0 || !confidenceScores) return;
      postToFrame("APPLY_CONFIDENCE", { scores: confidenceScores });
    }, [confidenceScores, postToFrame, readyTick]);

    useImperativeHandle(
      ref,
      () => ({
        getCurrentData: () =>
          new Promise<Record<string, string>>((resolve, reject) => {
            if (!iframeRef.current?.contentWindow) {
              reject(new Error("GOA form is not loaded."));
              return;
            }

            const directData = readDataFromFrameDom();
            if (readyTick === 0 && directData && Object.keys(directData).length > 0) {
              resolve(directData);
              return;
            }

            if (pendingRequestRef.current) {
              window.clearTimeout(pendingRequestRef.current.timeoutId);
              pendingRequestRef.current.reject(new Error("Previous GOA form read was superseded."));
            }

            const timeoutId = window.setTimeout(() => {
              const pending = pendingRequestRef.current;
              if (!pending) return;
              pendingRequestRef.current = null;
              const fallbackData = readDataFromFrameDom();
              if (fallbackData && Object.keys(fallbackData).length > 0) {
                pending.resolve(fallbackData);
                return;
              }
              pending.reject(new Error("Timed out while reading GOA form data."));
            }, 5000);

            pendingRequestRef.current = { resolve, reject, timeoutId };
            postToFrame("GET_DATA");
          }),
      }),
      [postToFrame, readDataFromFrameDom, readyTick]
    );

    useEffect(() => {
      return () => {
        const pending = pendingRequestRef.current;
        if (!pending) return;
        window.clearTimeout(pending.timeoutId);
        pending.reject(new Error("GOA form viewer unmounted before data was returned."));
        pendingRequestRef.current = null;
      };
    }, []);

    return (
      <div className={cn("rounded-md border bg-white", className)}>
        <iframe
          key={frameKey}
          ref={iframeRef}
          title="GOA Form"
          srcDoc={embeddedHtml}
          className="w-full rounded-md border-0"
          style={{ height: `${iframeHeight}px` }}
          onLoad={() => setIframeHeight(900)}
        />
      </div>
    );
  }
);
