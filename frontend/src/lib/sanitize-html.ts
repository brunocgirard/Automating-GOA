const STRIP_TAGS = ["script", "iframe", "object", "embed", "link", "meta", "base"];

const URL_ATTRIBUTES = new Set(["href", "src", "xlink:href", "action", "formaction"]);

function isUnsafeUrl(value: string): boolean {
  const normalized = value.trim().toLowerCase();
  return (
    normalized.startsWith("javascript:") ||
    normalized.startsWith("vbscript:") ||
    normalized.startsWith("data:text/html")
  );
}

function hasUnsafeInlineStyle(value: string): boolean {
  const normalized = value.trim().toLowerCase();
  return (
    normalized.includes("expression(") ||
    normalized.includes("javascript:") ||
    normalized.includes("vbscript:") ||
    normalized.includes("data:text/html")
  );
}

function serializeDocument(parsed: Document, preserveDocument: boolean): string {
  if (!preserveDocument) return parsed.body.innerHTML;
  return `<!doctype html>\n${parsed.documentElement.outerHTML}`;
}

export interface SanitizeHtmlOptions {
  preserveDocument?: boolean;
  allowStyleTags?: boolean;
  stripNoPrint?: boolean;
  forceReadonlyBody?: boolean;
  appendStyleBlock?: string;
}

export const DEFAULT_PREVIEW_APPEND_STYLE = `
  .no-print {
    display: none !important;
  }
`;

export function sanitizeHtml(html: string, options: SanitizeHtmlOptions = {}): string {
  if (!html) return "";
  if (typeof DOMParser === "undefined") {
    return "";
  }

  const {
    preserveDocument = false,
    allowStyleTags = false,
    stripNoPrint = false,
    forceReadonlyBody = false,
    appendStyleBlock,
  } = options;

  const parser = new DOMParser();
  const parsed = parser.parseFromString(html, "text/html");
  const stripTags = allowStyleTags ? STRIP_TAGS : [...STRIP_TAGS, "style"];

  parsed.querySelectorAll(stripTags.join(",")).forEach((node) => node.remove());

  parsed.querySelectorAll("*").forEach((element) => {
    for (const attribute of Array.from(element.attributes)) {
      const name = attribute.name.toLowerCase();
      const value = attribute.value;
      if (name.startsWith("on")) {
        element.removeAttribute(attribute.name);
        continue;
      }
      if (name === "srcdoc") {
        element.removeAttribute(attribute.name);
        continue;
      }
      if (URL_ATTRIBUTES.has(name) && isUnsafeUrl(value)) {
        element.removeAttribute(attribute.name);
        continue;
      }
      if (name === "style" && hasUnsafeInlineStyle(value)) {
        element.removeAttribute(attribute.name);
      }
    }
  });

  if (stripNoPrint) {
    parsed.querySelectorAll(".no-print").forEach((node) => node.remove());
  }

  if (forceReadonlyBody) {
    parsed.body.classList.add("readonly");
  }

  if (appendStyleBlock?.trim()) {
    let head = parsed.head;
    if (!head) {
      head = parsed.createElement("head");
      parsed.documentElement.insertBefore(head, parsed.body);
    }
    const style = parsed.createElement("style");
    style.textContent = appendStyleBlock;
    head.appendChild(style);
  }

  return serializeDocument(parsed, preserveDocument);
}
