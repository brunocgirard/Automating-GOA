import html
import re
import os
import copy
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Any

from openpyxl import load_workbook

# Define constants
TEMPLATE_DIR = Path("templates")
EXCEL_FILENAME = "GOA_template.xlsx"
EXCEL_PATH = TEMPLATE_DIR / EXCEL_FILENAME
OUTPUT_HTML_FILENAME = "goa_form.html"
OUTPUT_HTML_PATH = TEMPLATE_DIR / OUTPUT_HTML_FILENAME

def load_rows(excel_path: Path = EXCEL_PATH) -> List[Dict[str, str]]:
    """
    Reads rows from the Excel template.
    Returns a list of dictionaries representing each field.
    """
    if not excel_path.exists():
        raise FileNotFoundError(f"Excel template not found at {excel_path}")

    wb = load_workbook(excel_path, data_only=True)
    if "Form" not in wb.sheetnames:
        raise ValueError(f"Sheet 'Form' not found in {excel_path}")
        
    ws = wb["Form"]
    rows = []
    
    # Iterate rows, skipping header
    for raw in ws.iter_rows(min_row=2, values_only=True):
        # Ensure we have enough columns (at least 6)
        if len(raw) < 6:
            continue
            
        section, subsection, subsub, field_name, ftype, placeholder = raw[:6]
        
        # Skip empty rows or rows without critical info
        if not placeholder or not field_name:
            continue
            
        rows.append(
            {
                "section": str(section or "").strip(),
                "subsection": str(subsection or "").strip(),
                "subsub": str(subsub or "").strip(),
                "field": str(field_name or "").strip(),
                "type": str(ftype or "").strip().lower(),
                "placeholder": str(placeholder).strip(),
            }
        )

    # Ensure we always have an options_listing placeholder for downstream rendering.
    # If it's missing, first try to reuse the existing "Option Listing" row (e.g., f0091)
    # by renaming its placeholder to options_listing; if not found, insert a new row
    # immediately after the Option Listing section to preserve the Excel order.
    has_options_listing = any(r["placeholder"] == "options_listing" for r in rows)
    if not has_options_listing:
        renamed = False
        for r in rows:
            sec = r["section"].strip().lower()
            fld = r["field"].strip().lower()
            if sec == "option listing" or fld.startswith("option listing"):
                r["placeholder"] = "options_listing"
                r["type"] = "textarea"
                renamed = True
                break

        if not renamed:
            insert_at = len(rows)
            for idx, r in enumerate(rows):
                if r["section"].strip().lower() == "option listing":
                    insert_at = idx + 1
                    break

            rows.insert(
                insert_at,
                {
                    "section": "Option Listing",
                    "subsection": "",
                    "subsub": "",
                    "field": "Options Listing (auto-generated)",
                    "type": "textarea",
                    "placeholder": "options_listing",
                },
            )
    return rows

def display_label(raw: str) -> str:
    """Strip helper suffixes like (text)/(checkbox)/(qty) and example hints."""
    label = re.sub(r"\s*-\s*example:.*", "", raw, flags=re.IGNORECASE)
    label = re.sub(r"\s*\((text|checkbox|qty|text heading|heading)[^)]*\)", "", label, flags=re.IGNORECASE)
    return label.strip(" -:")

def group_by_section(rows):
    sections = defaultdict(list)
    for row in rows:
        sections[row["section"]].append(row)
    return sections

def render_input(row: dict) -> str:
    ph = html.escape(f"{{{{{row['placeholder']}}}}}")
    label = html.escape(display_label(row["field"]))
    
    if row["type"] == "checkbox":
        return f"""
        <label class="field checkbox" data-placeholder="{ph}">
          <input type="checkbox" name="{row['placeholder']}" data-placeholder="{ph}" />
          <span class="label">{label}</span>
          <span class="token">{ph}</span>
        </label>
        """
    
    # Special handling for options_listing or explicit textarea type
    if row['placeholder'] == 'options_listing' or row["type"] == "textarea":
        return f"""
        <label class="field textarea" data-placeholder="{ph}">
          <span class="label">{label}</span>
          <textarea name="{row['placeholder']}" data-placeholder="{ph}" rows="5"></textarea>
          <span class="token">{ph}</span>
        </label>
        """

    input_type = "number" if row["type"] == "qty" else "text"
    return f"""
    <label class="field" data-placeholder="{ph}">
      <span class="label">{label}</span>
      <input type="{input_type}" name="{row['placeholder']}" data-placeholder="{ph}" />
      <span class="token">{ph}</span>
    </label>
    """

def render_group(title: str, items: list[dict]) -> str:
    all_check = all(it["type"] == "checkbox" for it in items)
    grid_class = "checkbox-grid" if all_check else "field-grid"
    heading = f'<div class="group-title">{html.escape(title)}</div>' if title else ""
    fields_html = "\n".join(render_input(it) for it in items)
    return f"""
    <div class="group">
      {heading}
      <div class="{grid_class}">
        {fields_html}
      </div>
    </div>
    """

def render_section(name: str, items: list[dict]) -> str:
    clean_name = re.sub(r"\s*\(section\)", "", name, flags=re.IGNORECASE).strip()
    # bucket by subsection/subsub
    grouped = []
    current = (None, None)
    bucket = []
    for entry in items:
        key = (entry["subsection"], entry["subsub"])
        if key != current and bucket:
            grouped.append((current, bucket))
            bucket = []
        current = key
        bucket.append(entry)
    if bucket:
        grouped.append((current, bucket))

    groups_html = ""
    for (sub, subsub), bucket in grouped:
        title_parts = [p for p in (sub, subsub) if p]
        title = " / ".join(title_parts)
        groups_html += render_group(title, bucket)

    return f"""
    <section class="section">
      <div class="section-header">
        <h2>{html.escape(clean_name)}</h2>
      </div>
      {groups_html}
    </section>
    """

def build_html(rows):
    sections = group_by_section(rows)
    # Sort sections to ensure consistent order if needed, or rely on Excel order
    # Here we rely on Excel order preserved in 'rows' list, but group_by_section uses defaultdict which might lose order if python < 3.7 (unlikely)
    # Better to iterate sections in order of appearance
    section_order = []
    seen = set()
    for row in rows:
        if row["section"] not in seen:
            section_order.append(row["section"])
            seen.add(row["section"])

    body = "\n".join(render_section(name, sections[name]) for name in section_order)

    template = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>General Order Acknowledgement</title>
  <style>
    :root {
      --bg: #f3f5f8;
      --card: #ffffff;
      --ink: #1f2430;
      --muted: #4b5563;
      --accent: #c00000;      /* template docx red accent */
      --header-fill: #e5e5e5; /* template docx gray strip */
      --border: #cdd4e0;
    }
    * { box-sizing: border-box; font-family: "Calibri", "Segoe UI", Arial, sans-serif; }
    body {
      margin: 0;
      padding: 24px;
      background: var(--bg);
      color: var(--ink);
    }
    .page { max-width: 1200px; margin: 0 auto; }
    header { margin-bottom: 18px; display: flex; justify-content: space-between; align-items: center; }
    h1 {
      margin: 0 0 6px;
      font-size: 26px;
      color: var(--accent);
      font-weight: 700;
      letter-spacing: -0.015em;
    }
    .subtitle { color: var(--muted); margin: 0 0 8px; font-size: 14px; }
    .note { font-size: 13px; color: var(--muted); margin: 3px 0; }
    .divider {
      height: 6px;
      background: var(--header-fill);
      border: 1px solid var(--border);
      border-radius: 6px;
      margin-bottom: 12px;
    }
    .section {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 10px;
      margin-bottom: 14px;
      box-shadow: 0 4px 12px rgba(0,0,0,0.04);
      overflow: hidden;
    }
    .section-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      padding: 10px 14px;
      background: var(--header-fill);
      border-bottom: 1px solid var(--border);
      border-top-left-radius: 10px;
      border-top-right-radius: 10px;
      cursor: pointer;
      user-select: none;
    }
    .section-header.active + .section-content {
        /* styles when open */
    }
    .section.collapsed > .section-header {
        border-bottom-color: transparent;
    }
    .toggle-icon {
        transition: transform 0.3s ease;
        font-weight: bold;
        font-size: 20px;
        color: var(--muted);
    }
    .section-header.active .toggle-icon {
        transform: rotate(45deg);
    }
    .section-content {
        padding: 16px 14px;
        overflow: hidden;
        max-height: 10000px; /* A large enough value to not clip content */
        transition: max-height 0.4s ease-in-out, padding 0.3s ease-in-out;
    }
    .section.collapsed > .section-content {
        max-height: 0;
        padding-top: 0;
        padding-bottom: 0;
    }
    .section h2 {
      margin: 0;
      font-size: 18px;
      color: var(--accent);
      font-weight: 700;
    }
    .pill {
      background: var(--header-fill);
      color: var(--accent);
      padding: 4px 10px;
      border-radius: 999px;
      font-size: 11px;
      font-weight: 700;
      border: 1px solid var(--border);
    }
    .group { margin: 10px 14px 0 14px; }
    .group-title {
      font-size: 13px;
      font-weight: 700;
      color: var(--muted);
      margin: 6px 0 4px;
    }
    .field-grid {
      display: flex;
      flex-wrap: wrap;
      gap: 10px 12px;
    }
    .checkbox-grid {
      display: flex;
      flex-wrap: wrap;
      gap: 8px 10px;
    }
    .field-grid > .field {
      flex: 1 1 calc((100% - 36px) / 4);
      max-width: calc((100% - 36px) / 4);
      min-width: 260px;
    }
    .checkbox-grid > .field {
      flex: 1 1 calc((100% - 30px) / 4);
      max-width: calc((100% - 30px) / 4);
      min-width: 220px;
    }
    @supports (display: grid) {
      .field-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      }
      .checkbox-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      }
      .field-grid > .field,
      .checkbox-grid > .field {
        max-width: none;
        min-width: 0;
      }
    }
    .field {
      border-left: 3px solid #f3f3f3;
      display: grid;
      grid-template-rows: auto auto auto;
      gap: 4px;
      padding: 10px;
      border: 1px solid #cdd4e0;
      border: 1px solid var(--border);
      border-radius: 6px;
      background: #fff;
    }
    .field.checkbox {
      grid-template-columns: auto 1fr auto;
      grid-template-rows: auto;
      align-items: center;
      gap: 8px;
      background: #f8f9fc;
      border-color: #d5dbe7;
    }
    .field.checkbox .label { font-weight: 600; color: var(--ink); }
    .label { font-size: 13px; color: var(--ink); font-weight: 600; }
    input[type="text"], input[type="number"], textarea {
      width: 100%;
      padding: 7px 9px;
      border-radius: 4px;
      border: 1px solid var(--border);
      background: #fdfdff;
      font-size: 14px;
      color: var(--ink);
      font-family: inherit;
    }
    textarea { resize: vertical; }
    input:focus { outline: 2px solid #b5c7e3; }
    .token {
      font-size: 12px;
      color: var(--muted);
      font-family: "Consolas", "SFMono-Regular", monospace;
      display: none; /* hide placeholders */
    }
    .header-fill {
      background: var(--header-fill);
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 6px 10px;
      font-weight: 700;
      color: var(--accent);
      display: inline-block;
      margin-top: 6px;
    }
    input[type="checkbox"] {
      width: 18px;
      height: 18px;
    }
    
    /* Styles for Read-Only / Filled View */
    body.readonly input {
        border: none;
        background: transparent;
        pointer-events: none;
    }
    body.readonly input[type="checkbox"] {
        /* Custom styling for checked box in print mode? Or just keep browser default */
    }
    body.readonly .field {
        border: 1px solid transparent; /* Hide border or make lighter */
        box-shadow: none;
        background: transparent;
    }
    body.readonly .section {
        box-shadow: none;
        border: 1px solid #eee;
    }

    /* Edit Mode Styles */
    .delete-btn {
        display: none;
        padding: 4px 8px;
        background: #dc2626;
        color: white;
        border: none;
        border-radius: 4px;
        cursor: pointer;
        font-size: 12px;
        font-weight: bold;
        opacity: 0;
        transition: opacity 0.2s;
    }
    body.edit-mode .delete-btn {
        display: inline-block;
    }
    body.edit-mode .section:hover .delete-section-btn,
    body.edit-mode .field:hover .delete-field-btn {
        opacity: 1;
    }
    body.edit-mode .section-header h2[contenteditable="true"],
    body.edit-mode .field .label[contenteditable="true"],
    body.edit-mode .group-title[contenteditable="true"] {
        cursor: text;
        padding: 4px 6px;
        border-radius: 4px;
        transition: background 0.2s, outline 0.2s;
        display: inline-block;
        min-width: 50px;
    }
    body.edit-mode .section-header h2[contenteditable="true"]:hover,
    body.edit-mode .field .label[contenteditable="true"]:hover,
    body.edit-mode .group-title[contenteditable="true"]:hover {
        background: rgba(37, 99, 235, 0.15);
        outline: 2px dashed #2563eb;
    }
    body.edit-mode .section-header h2[contenteditable="true"]:focus,
    body.edit-mode .field .label[contenteditable="true"]:focus,
    body.edit-mode .group-title[contenteditable="true"]:focus {
        background: rgba(37, 99, 235, 0.25);
        outline: 2px solid #2563eb;
    }
    /* Add visual indicator for editable group titles */
    body.edit-mode .group-title[contenteditable="true"]::before {
        content: '✎ ';
        color: #2563eb;
        font-weight: bold;
        margin-right: 4px;
        opacity: 0.6;
    }
    .delete-section-btn {
        margin-left: auto;
    }
    .delete-field-btn {
        position: absolute;
        top: 4px;
        right: 4px;
    }
    body.edit-mode .field {
        position: relative;
    }
    body.edit-mode .section {
        border: 2px dashed transparent;
        transition: border-color 0.2s;
    }
    body.edit-mode .section:hover {
        border-color: #cbd5e1;
    }

    /* Section Controls Styling */
    .section-controls button {
        transition: all 0.2s ease;
    }
    .section-controls button:hover {
        opacity: 0.9;
        transform: translateY(-1px);
        box-shadow: 0 2px 8px rgba(0,0,0,0.15);
    }
    .section-controls button:active {
        transform: translateY(0);
        box-shadow: 0 1px 4px rgba(0,0,0,0.1);
    }

    /* User-friendliness upgrades */
    .page {
      max-width: 1520px;
    }
    .sticky-toolbar {
      position: sticky;
      top: 8px;
      z-index: 120;
      margin-bottom: 14px;
      padding: 12px 14px;
      border: 1px solid var(--border);
      border-radius: 10px;
      background: rgba(255, 255, 255, 0.94);
      box-shadow: 0 8px 20px rgba(31, 36, 48, 0.08);
      backdrop-filter: blur(4px);
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 12px;
    }
    .toolbar-title-wrap {
      min-width: 220px;
      flex: 1 1 320px;
    }
    .toolbar-title-wrap .subtitle {
      margin: 2px 0 0;
      font-size: 12px;
    }
    .toolbar-actions {
      display: flex;
      flex-wrap: wrap;
      justify-content: flex-end;
      gap: 8px;
      flex: 2 1 540px;
    }
    .toolbar-btn {
      border: none;
      border-radius: 6px;
      cursor: pointer;
      padding: 8px 14px;
      color: #fff;
      font-weight: 700;
      font-size: 13px;
      letter-spacing: 0.01em;
      transition: all 0.18s ease;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
    }
    .toolbar-btn:hover {
      transform: translateY(-1px);
      box-shadow: 0 3px 10px rgba(0, 0, 0, 0.16);
    }
    .toolbar-btn:active {
      transform: translateY(0);
      box-shadow: 0 1px 4px rgba(0, 0, 0, 0.12);
    }
    .toolbar-btn.compact-btn {
      padding: 6px 12px;
      font-size: 12px;
    }
    .btn-edit {
      background: #2563eb;
    }
    .btn-edit.is-active {
      background: #dc2626;
    }
    .btn-download {
      background: #059669;
    }
    .btn-save {
      background: #0891b2;
    }
    .btn-print {
      background: #c00000;
    }
    .btn-expand {
      background: #10b981;
    }
    .btn-collapse {
      background: #6b7280;
    }
    .btn-neutral {
      background: #475569;
    }
    .layout-shell {
      display: grid;
      grid-template-columns: 280px minmax(0, 1fr);
      gap: 14px;
      align-items: start;
    }
    .toc-sidebar {
      position: sticky;
      top: 112px;
      align-self: start;
      max-height: calc(100vh - 130px);
      overflow: auto;
    }
    .toc-card {
      border: 1px solid var(--border);
      border-radius: 10px;
      background: #fff;
      padding: 12px;
      box-shadow: 0 4px 14px rgba(0, 0, 0, 0.05);
    }
    .toc-title {
      margin: 0 0 6px;
      font-size: 13px;
      font-weight: 700;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }
    .toc-overall-progress {
      margin: 0 0 10px;
      padding: 6px 8px;
      border: 1px solid var(--border);
      border-radius: 6px;
      font-size: 12px;
      background: #f8fafc;
      color: #1f2937;
      font-weight: 700;
    }
    .toc-nav {
      display: flex;
      flex-direction: column;
      gap: 6px;
    }
    .toc-link {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      border: 1px solid #e2e8f0;
      border-radius: 6px;
      text-decoration: none;
      color: #1f2937;
      background: #fff;
      padding: 6px 8px;
      font-size: 12px;
      transition: all 0.16s ease;
    }
    .toc-link:hover {
      border-color: #94a3b8;
      background: #f8fafc;
    }
    .toc-link.active {
      border-color: #ef4444;
      background: #fef2f2;
      color: #991b1b;
      font-weight: 700;
    }
    .toc-link.hidden {
      display: none;
    }
    .toc-link-title {
      min-width: 0;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    .toc-link-count {
      color: #475569;
      font-weight: 700;
      font-size: 11px;
      flex: 0 0 auto;
    }
    .form-main {
      min-width: 0;
    }
    .section-controls {
      position: sticky;
      top: 108px;
      z-index: 110;
      margin-bottom: 14px;
      display: flex;
      flex-direction: column;
      gap: 10px;
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 10px;
      background: rgba(255, 255, 255, 0.95);
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
      backdrop-filter: blur(2px);
    }
    .search-controls,
    .quick-controls {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }
    #fieldSearchInput {
      width: min(420px, 100%);
      border: 1px solid var(--border);
      border-radius: 6px;
      font-size: 14px;
      padding: 8px 10px;
      background: #fff;
    }
    .status-pill {
      border: 1px solid var(--border);
      border-radius: 999px;
      background: #f8fafc;
      color: #334155;
      font-size: 12px;
      font-weight: 700;
      padding: 5px 10px;
      white-space: nowrap;
    }
    .legend-chip {
      border-radius: 999px;
      font-size: 11px;
      font-weight: 700;
      padding: 4px 9px;
      border: 1px solid transparent;
      white-space: nowrap;
    }
    .legend-filled {
      background: #dcfce7;
      border-color: #86efac;
      color: #166534;
    }
    .legend-optional {
      background: #fef9c3;
      border-color: #fde047;
      color: #854d0e;
    }
    .legend-required {
      background: #fee2e2;
      border-color: #fca5a5;
      color: #991b1b;
    }
    .autosave-status {
      color: #0f172a;
    }
    .required-badge {
      color: #b91c1c;
      margin-left: 4px;
      font-weight: 700;
    }
    .section-progress {
      margin-left: auto;
      margin-right: 6px;
      padding: 3px 8px;
      border-radius: 999px;
      border: 1px solid var(--border);
      background: #f8fafc;
      color: #334155;
      font-size: 11px;
      font-weight: 700;
      white-space: nowrap;
    }
    .section-progress.progress-alert {
      border-color: #fca5a5;
      background: #fef2f2;
      color: #b91c1c;
    }
    .section-progress.progress-complete {
      border-color: #86efac;
      background: #dcfce7;
      color: #166534;
    }
    .field {
      transition: border-color 0.2s ease, background 0.2s ease, box-shadow 0.2s ease;
    }
    .field.state-filled {
      border-color: #86efac;
      border-left-color: #22c55e;
      background: #f0fdf4;
    }
    .field.state-empty-optional {
      border-color: #fde047;
      border-left-color: #eab308;
      background: #fffbeb;
    }
    .field.state-empty-required {
      border-color: #fca5a5;
      border-left-color: #ef4444;
      background: #fef2f2;
    }
    .field.field-match {
      box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.26);
    }
    .field.field-hidden-by-search,
    .group.group-hidden-by-search,
    .section.section-hidden-by-search {
      display: none !important;
    }
    @media (max-width: 768px) {
      .layout-shell {
        grid-template-columns: 1fr;
      }
      .toc-sidebar {
        display: none;
      }
      .section-controls {
        top: 98px;
      }
    }

    /* Print Styles */
    @page {
        size: letter portrait;
        margin: 10mm;
    }

    @media print {
        .no-print { display: none !important; }
        body {
            background: #fff;
            -webkit-print-color-adjust: exact;
            print-color-adjust: exact;
        }
        .section.collapsed > .section-content {
            max-height: none !important;
            padding: 16px 14px !important;
        }
        .section-header .toggle-icon {
            display: none !important;
        }
    }

    @media (max-width: 480px) {
      body { padding: 12px; }
      .section { padding: 12px; }
      .field-grid,
      .checkbox-grid {
        grid-template-columns: 1fr;
      }
      input[type="text"], input[type="number"] {
        padding: 10px 12px;
        font-size: 15px;
      }
      .field {
        gap: 6px;
      }
      .field.checkbox {
        grid-template-columns: auto 1fr;
        grid-template-rows: auto auto;
        row-gap: 4px;
      }
    }
  </style>
</head>
  <body>
    <div class="page">
      <header class="sticky-toolbar no-print">
        <div class="toolbar-title-wrap">
          <h1>General Order Acknowledgement</h1>
          <p class="subtitle">Validation highlights, progress tracking, and autosave are enabled.</p>
        </div>
        <div class="toolbar-actions">
          <button id="editModeBtn" onclick="toggleEditMode()" class="toolbar-btn btn-edit">Enable Edit Mode</button>
          <button id="downloadBtn" onclick="downloadModifiedHTML()" class="toolbar-btn btn-download" style="display: none;">Download Modified Form</button>
          <button onclick="saveFilledFormHTML()" class="toolbar-btn btn-save">Save Filled Form (HTML)</button>
          <button onclick="generatePDF()" class="toolbar-btn btn-print">Print to PDF</button>
        </div>
      </header>
      <div class="divider"></div>

      <div class="layout-shell">
        <aside class="toc-sidebar no-print">
          <div class="toc-card">
            <p class="toc-title">Table of Contents</p>
            <p id="tocOverallProgress" class="toc-overall-progress">0 of 0 fields filled</p>
            <nav id="tocNav" class="toc-nav"></nav>
          </div>
        </aside>

        <div class="form-main">
          <div class="section-controls no-print">
            <div class="search-controls">
              <input id="fieldSearchInput" type="text" placeholder="Search fields, values, or field keys..." />
              <button type="button" onclick="clearFieldSearch()" class="toolbar-btn btn-neutral compact-btn">Clear</button>
              <span id="searchSummary" class="status-pill">Showing all fields</span>
            </div>
            <div class="quick-controls">
              <span id="overallProgress" class="status-pill status-progress">0 of 0 fields filled</span>
              <span class="legend-chip legend-filled">Filled</span>
              <span class="legend-chip legend-optional">Optional Empty</span>
              <span class="legend-chip legend-required">Required Empty</span>
              <span id="autosaveStatus" class="status-pill autosave-status">Autosave ready</span>
              <button onclick="expandAllSections()" class="toolbar-btn btn-expand compact-btn">Expand All Sections</button>
              <button onclick="collapseAllSections()" class="toolbar-btn btn-collapse compact-btn">Collapse All Sections</button>
              <button onclick="clearAutoSavedDraft()" class="toolbar-btn btn-neutral compact-btn">Clear Local Draft</button>
            </div>
          </div>

      
    

    
__FORM_BODY__

    

    
    </div>
    </div>
    </div>
    <script>
      const REQUIRED_FIELD_KEYS = new Set([
        "f0001",
        "f0002",
        "f0003",
        "f0004",
        "f0005",
        "f0006",
        "f0007",
        "f0008",
        "f0014",
      ]);
      const CHECKBOX_TRUE_VALUES = new Set(["YES", "TRUE", "ON", "1", "Y", "CHECKED"]);
      const AUTO_SAVE_KEY = "goa_form_autosave_v1";
      const AUTO_SAVE_DEBOUNCE_MS = 1200;
      let autoSaveTimerId = null;
      let searchDebounceId = null;
      let scrollTicking = false;

      document.addEventListener("DOMContentLoaded", function () {
          setupSections();
          tagRequiredFields();
          initializeEditMode();
          initializeSearch();
          initializeFieldListeners();
          assignSectionIds();
          buildToc();
          refreshFormState();
          restoreAutoSavedDraft();
          updateActiveSectionFromScroll();

          window.addEventListener("scroll", handleScroll, { passive: true });
          document.addEventListener("visibilitychange", () => {
              if (document.visibilityState === "hidden") {
                  saveDraftToLocalStorage();
              }
          });
      });

      function setupSections() {
          const sections = document.querySelectorAll(".section");
          sections.forEach((section, index) => {
              const header = section.querySelector(".section-header");
              if (!header) return;

              if (!section.querySelector(":scope > .section-content")) {
                  const content = document.createElement("div");
                  content.className = "section-content";
                  const groups = Array.from(section.children).filter((child) =>
                      child.classList.contains("group")
                  );
                  groups.forEach((group) => {
                      content.appendChild(group);
                  });
                  section.appendChild(content);
              }

              if (!header.querySelector(".section-progress")) {
                  const progress = document.createElement("span");
                  progress.className = "section-progress";
                  progress.textContent = "0 of 0 fields filled";
                  header.appendChild(progress);
              }

              if (!header.querySelector(".toggle-icon")) {
                  const icon = document.createElement("span");
                  icon.className = "toggle-icon";
                  icon.textContent = "+";
                  header.appendChild(icon);
              }

              if (!header.dataset.toggleBound) {
                  header.addEventListener("click", (event) => {
                      if (event.target.closest(".delete-btn")) return;
                      section.classList.toggle("collapsed");
                      header.classList.toggle("active");
                  });
                  header.dataset.toggleBound = "1";
              }

              if (index > 0) {
                  section.classList.add("collapsed");
              } else {
                  header.classList.add("active");
              }
          });
      }

      function slugify(text) {
          return (text || "")
              .toLowerCase()
              .replace(/[^a-z0-9]+/g, "-")
              .replace(/^-+|-+$/g, "") || "section";
      }

      function assignSectionIds() {
          const used = new Map();
          document.querySelectorAll(".section").forEach((section, index) => {
              const title = section.querySelector(".section-header h2")?.textContent?.trim() || `Section ${index + 1}`;
              const base = slugify(title);
              const count = (used.get(base) || 0) + 1;
              used.set(base, count);
              section.id = count === 1 ? base : `${base}-${count}`;
          });
      }

      function buildToc() {
          const nav = document.getElementById("tocNav");
          if (!nav) return;
          nav.innerHTML = "";

          document.querySelectorAll(".section").forEach((section) => {
              const title = section.querySelector(".section-header h2")?.textContent?.trim() || section.id;
              const link = document.createElement("a");
              link.className = "toc-link";
              link.href = `#${section.id}`;
              link.dataset.sectionId = section.id;

              const titleEl = document.createElement("span");
              titleEl.className = "toc-link-title";
              titleEl.textContent = title;

              const countEl = document.createElement("span");
              countEl.className = "toc-link-count";
              countEl.textContent = "0/0";

              link.appendChild(titleEl);
              link.appendChild(countEl);
              link.addEventListener("click", (event) => {
                  event.preventDefault();
                  expandSection(section);
                  section.scrollIntoView({ behavior: "smooth", block: "start" });
                  setActiveTocLink(section.id);
              });

              nav.appendChild(link);
          });
      }

      function setActiveTocLink(sectionId) {
          document.querySelectorAll(".toc-link").forEach((link) => {
              link.classList.toggle("active", link.dataset.sectionId === sectionId);
          });
      }

      function handleScroll() {
          if (scrollTicking) return;
          scrollTicking = true;
          window.requestAnimationFrame(() => {
              updateActiveSectionFromScroll();
              scrollTicking = false;
          });
      }

      function updateActiveSectionFromScroll() {
          const visibleSections = Array.from(document.querySelectorAll(".section"))
              .filter((section) => !section.classList.contains("section-hidden-by-search"));
          if (visibleSections.length === 0) return;

          let active = visibleSections[0];
          const threshold = 170;
          visibleSections.forEach((section) => {
              const top = section.getBoundingClientRect().top;
              if (top - threshold <= 0) {
                  active = section;
              }
          });
          setActiveTocLink(active.id);
      }

      function expandSection(section) {
          section.classList.remove("collapsed");
          const header = section.querySelector(".section-header");
          if (header) header.classList.add("active");
      }

      function getFieldInput(field) {
          return field.querySelector("input[name], textarea[name], select[name]");
      }

      function getFieldKey(field) {
          const input = getFieldInput(field);
          if (input?.name) return input.name;
          const placeholder = field.getAttribute("data-placeholder") || "";
          return placeholder.replace("{{", "").replace("}}", "").trim();
      }

      function tagRequiredFields() {
          document.querySelectorAll("label.field").forEach((field) => {
              const key = getFieldKey(field);
              const required = REQUIRED_FIELD_KEYS.has(key);
              field.dataset.required = required ? "true" : "false";

              const label = field.querySelector(".label");
              if (!label) return;
              const existing = label.querySelector(".required-badge");
              if (required && !existing) {
                  const badge = document.createElement("span");
                  badge.className = "required-badge";
                  badge.textContent = "*";
                  badge.title = "Required field";
                  label.appendChild(badge);
              }
              if (!required && existing) {
                  existing.remove();
              }
          });
      }

      function isFieldRequired(field) {
          return field.dataset.required === "true";
      }

      function isFieldFilled(field) {
          const checkbox = field.querySelector('input[type="checkbox"]');
          if (checkbox) return checkbox.checked;

          const formatted = field.querySelector(".formatted-list");
          if (formatted) {
              const value = formatted.dataset.fieldValue || formatted.textContent || "";
              return value.trim().length > 0;
          }

          const input = getFieldInput(field);
          if (!input) return false;
          return (input.value || "").trim().length > 0;
      }

      function getFieldValueText(field) {
          const checkbox = field.querySelector('input[type="checkbox"]');
          if (checkbox) return checkbox.checked ? "YES" : "NO";

          const formatted = field.querySelector(".formatted-list");
          if (formatted) return (formatted.dataset.fieldValue || formatted.textContent || "").trim();

          const input = getFieldInput(field);
          return (input?.value || "").trim();
      }

      function updateFieldValidation(field) {
          const filled = isFieldFilled(field);
          const required = isFieldRequired(field);
          field.classList.remove("state-filled", "state-empty-optional", "state-empty-required");
          if (filled) {
              field.classList.add("state-filled");
          } else if (required) {
              field.classList.add("state-empty-required");
          } else {
              field.classList.add("state-empty-optional");
          }
      }

      function updateProgressIndicators() {
          let overallTotal = 0;
          let overallFilled = 0;

          document.querySelectorAll(".section").forEach((section) => {
              const fields = Array.from(section.querySelectorAll("label.field"));
              const filled = fields.filter((field) => isFieldFilled(field)).length;
              const missingRequired = fields.filter((field) => isFieldRequired(field) && !isFieldFilled(field)).length;
              const total = fields.length;

              overallTotal += total;
              overallFilled += filled;

              const progress = section.querySelector(".section-progress");
              if (progress) {
                  progress.textContent = `${filled} of ${total} fields filled`;
                  progress.classList.toggle("progress-alert", missingRequired > 0);
                  progress.classList.toggle("progress-complete", total > 0 && filled === total);
              }

              const tocCount = document.querySelector(`.toc-link[data-section-id="${section.id}"] .toc-link-count`);
              if (tocCount) {
                  tocCount.textContent = `${filled}/${total}`;
              }
          });

          const overallText = `${overallFilled} of ${overallTotal} fields filled`;
          const overallEl = document.getElementById("overallProgress");
          if (overallEl) overallEl.textContent = overallText;
          const tocOverallEl = document.getElementById("tocOverallProgress");
          if (tocOverallEl) tocOverallEl.textContent = overallText;
      }

      function fieldMatchesSearch(field, query) {
          if (!query) return true;
          const key = getFieldKey(field).toLowerCase();
          const label = (field.querySelector(".label")?.textContent || "").toLowerCase();
          const value = getFieldValueText(field).toLowerCase();
          return key.includes(query) || label.includes(query) || value.includes(query);
      }

      function applySearchFilter(rawQuery) {
          const query = (rawQuery || "").trim().toLowerCase();
          let matches = 0;
          let visibleSections = 0;

          document.querySelectorAll(".section").forEach((section) => {
              let sectionHasVisibleFields = false;

              section.querySelectorAll(".group").forEach((group) => {
                  let groupHasVisibleFields = false;

                  group.querySelectorAll("label.field").forEach((field) => {
                      const match = fieldMatchesSearch(field, query);
                      field.classList.toggle("field-hidden-by-search", !match);
                      field.classList.toggle("field-match", !!query && match);
                      if (match) {
                          groupHasVisibleFields = true;
                          if (query) matches += 1;
                      }
                  });

                  group.classList.toggle("group-hidden-by-search", !groupHasVisibleFields);
                  if (groupHasVisibleFields) sectionHasVisibleFields = true;
              });

              section.classList.toggle("section-hidden-by-search", !sectionHasVisibleFields);
              const tocLink = document.querySelector(`.toc-link[data-section-id="${section.id}"]`);
              if (tocLink) {
                  tocLink.classList.toggle("hidden", !sectionHasVisibleFields);
              }
              if (query && sectionHasVisibleFields) {
                  expandSection(section);
              }
              if (sectionHasVisibleFields) visibleSections += 1;
          });

          const summary = document.getElementById("searchSummary");
          if (summary) {
              summary.textContent = query
                  ? `${matches} matches in ${visibleSections} sections`
                  : "Showing all fields";
          }

          updateActiveSectionFromScroll();
      }

      function initializeSearch() {
          const searchInput = document.getElementById("fieldSearchInput");
          if (!searchInput) return;

          searchInput.addEventListener("input", () => {
              window.clearTimeout(searchDebounceId);
              searchDebounceId = window.setTimeout(() => {
                  applySearchFilter(searchInput.value);
              }, 80);
          });
          searchInput.addEventListener("keydown", (event) => {
              if (event.key === "Escape") {
                  event.preventDefault();
                  clearFieldSearch();
              }
          });
      }

      function clearFieldSearch() {
          const searchInput = document.getElementById("fieldSearchInput");
          if (!searchInput) return;
          searchInput.value = "";
          applySearchFilter("");
      }

      function refreshFormState() {
          document.querySelectorAll("label.field").forEach((field) => {
              updateFieldValidation(field);
          });
          updateProgressIndicators();
          const query = document.getElementById("fieldSearchInput")?.value || "";
          applySearchFilter(query);
      }

      function initializeFieldListeners() {
          document
              .querySelectorAll("input[name], textarea[name], select[name]")
              .forEach((field) => {
                  field.addEventListener("input", () => {
                      refreshFormState();
                      queueAutoSave();
                  });
                  field.addEventListener("change", () => {
                      refreshFormState();
                      queueAutoSave();
                  });
              });
      }

      function queueAutoSave() {
          updateAutosaveStatus("Autosave pending...");
          window.clearTimeout(autoSaveTimerId);
          autoSaveTimerId = window.setTimeout(saveDraftToLocalStorage, AUTO_SAVE_DEBOUNCE_MS);
      }

      function collectCurrentData() {
          const data = {};
          document
              .querySelectorAll("input[name], textarea[name], select[name]")
              .forEach((field) => {
                  const key = field.name;
                  if (!key) return;

                  if (field.matches('input[type="checkbox"]')) {
                      data[key] = field.checked ? "YES" : "NO";
                      return;
                  }

                  data[key] = field.value || "";
              });

          document.querySelectorAll(".formatted-list[data-field-key]").forEach((field) => {
              const key = field.dataset.fieldKey?.trim();
              if (!key || data[key] !== undefined) return;
              data[key] = field.dataset.fieldValue || field.textContent?.trim() || "";
          });
          return data;
      }

      function isMeaningfulValue(value) {
          const normalized = String(value ?? "").trim();
          if (!normalized) return false;
          return normalized.toUpperCase() !== "NO";
      }

      function saveDraftToLocalStorage() {
          try {
              const payload = {
                  savedAt: new Date().toISOString(),
                  data: collectCurrentData(),
              };
              localStorage.setItem(AUTO_SAVE_KEY, JSON.stringify(payload));
              const stamp = new Date(payload.savedAt).toLocaleTimeString();
              updateAutosaveStatus(`Autosaved at ${stamp}`);
          } catch {
              updateAutosaveStatus("Autosave unavailable");
          }
      }

      function applyDataToForm(data) {
          document.querySelectorAll("input[name], textarea[name], select[name]").forEach((field) => {
              const key = field.name;
              if (!key || !(key in data)) return;
              const next = String(data[key] ?? "");
              if (field.matches('input[type="checkbox"]')) {
                  field.checked = CHECKBOX_TRUE_VALUES.has(next.trim().toUpperCase());
              } else {
                  field.value = next;
              }
          });
      }

      function restoreAutoSavedDraft() {
          try {
              const raw = localStorage.getItem(AUTO_SAVE_KEY);
              if (!raw) {
                  updateAutosaveStatus("Autosave ready");
                  return;
              }

              const parsed = JSON.parse(raw);
              if (!parsed || typeof parsed !== "object" || !parsed.data || typeof parsed.data !== "object") {
                  updateAutosaveStatus("Autosave ready");
                  return;
              }

              const hasMeaningfulData = Object.values(parsed.data).some((value) => isMeaningfulValue(value));
              if (!hasMeaningfulData) {
                  updateAutosaveStatus("Autosave ready");
                  return;
              }

              const savedAt = parsed.savedAt ? new Date(parsed.savedAt) : null;
              const promptText = savedAt
                  ? `Restore autosaved draft from ${savedAt.toLocaleString()}?`
                  : "Restore autosaved draft?";
              if (!window.confirm(promptText)) {
                  updateAutosaveStatus(savedAt ? `Draft available (${savedAt.toLocaleTimeString()})` : "Draft available");
                  return;
              }

              applyDataToForm(parsed.data);
              refreshFormState();
              updateAutosaveStatus(savedAt ? `Restored draft (${savedAt.toLocaleTimeString()})` : "Restored draft");
          } catch {
              updateAutosaveStatus("Autosave ready");
          }
      }

      function clearAutoSavedDraft() {
          try {
              localStorage.removeItem(AUTO_SAVE_KEY);
              updateAutosaveStatus("Local draft cleared");
          } catch {
              updateAutosaveStatus("Unable to clear local draft");
          }
      }

      function updateAutosaveStatus(text) {
          const statusEl = document.getElementById("autosaveStatus");
          if (!statusEl) return;
          statusEl.textContent = text;
      }

      function bindEditableChangeHandlers() {
          const refreshFromEdit = () => {
              assignSectionIds();
              buildToc();
              refreshFormState();
              queueAutoSave();
          };

          document.querySelectorAll(".section-header h2, .group-title, .field .label").forEach((el) => {
              if (el.dataset.editBound) return;
              el.addEventListener("input", refreshFromEdit);
              el.dataset.editBound = "1";
          });
      }

      function initializeEditMode() {
          document.querySelectorAll(".section").forEach((section) => {
              const header = section.querySelector(".section-header");
              if (!header) return;

              if (!header.querySelector(".delete-section-btn")) {
                  const deleteSectionButton = document.createElement("button");
                  deleteSectionButton.className = "delete-btn delete-section-btn";
                  deleteSectionButton.type = "button";
                  deleteSectionButton.textContent = "x Delete Section";
                  deleteSectionButton.onclick = (event) => {
                      event.stopPropagation();
                      deleteSection(section);
                  };
                  header.appendChild(deleteSectionButton);
              }

              section.querySelectorAll(".field").forEach((field) => {
                  if (field.querySelector(".delete-field-btn")) return;
                  const deleteFieldButton = document.createElement("button");
                  deleteFieldButton.className = "delete-btn delete-field-btn";
                  deleteFieldButton.type = "button";
                  deleteFieldButton.textContent = "x";
                  deleteFieldButton.onclick = (event) => {
                      event.stopPropagation();
                      deleteField(field);
                  };
                  field.appendChild(deleteFieldButton);
              });
          });

          bindEditableChangeHandlers();
      }

      function toggleEditMode() {
          const body = document.body;
          const editBtn = document.getElementById("editModeBtn");
          const downloadBtn = document.getElementById("downloadBtn");

          body.classList.toggle("edit-mode");
          const isEditMode = body.classList.contains("edit-mode");

          if (isEditMode) {
              editBtn.textContent = "Disable Edit Mode";
              editBtn.classList.add("is-active");
              downloadBtn.style.display = "inline-block";
              enableEditing();
          } else {
              editBtn.textContent = "Enable Edit Mode";
              editBtn.classList.remove("is-active");
              downloadBtn.style.display = "none";
              disableEditing();
          }
      }

      function enableEditing() {
          document.querySelectorAll(".section-header h2").forEach((h2) => {
              h2.setAttribute("contenteditable", "true");
              h2.setAttribute("title", "Click to edit section name");
          });
          document.querySelectorAll(".group-title").forEach((groupTitle) => {
              groupTitle.setAttribute("contenteditable", "true");
              groupTitle.setAttribute("title", "Click to edit subsection name");
          });
          document.querySelectorAll(".field .label").forEach((label) => {
              label.setAttribute("contenteditable", "true");
              label.setAttribute("title", "Click to edit field label");
          });
      }

      function disableEditing() {
          document.querySelectorAll('[contenteditable="true"]').forEach((el) => {
              el.removeAttribute("contenteditable");
              el.removeAttribute("title");
          });
          assignSectionIds();
          buildToc();
          refreshFormState();
      }

      function deleteField(field) {
          if (!window.confirm("Are you sure you want to delete this field?")) return;
          field.remove();
          refreshFormState();
          queueAutoSave();
      }

      function deleteSection(section) {
          const sectionName = section.querySelector("h2")?.textContent || "this";
          if (!window.confirm(`Are you sure you want to delete the entire "${sectionName}" section?`)) return;
          section.remove();
          assignSectionIds();
          buildToc();
          refreshFormState();
          queueAutoSave();
      }

      function stripTransientClasses(root) {
          root.querySelectorAll(".field-hidden-by-search, .group-hidden-by-search, .section-hidden-by-search, .field-match")
              .forEach((el) => {
                  el.classList.remove("field-hidden-by-search", "group-hidden-by-search", "section-hidden-by-search", "field-match");
              });
          root.querySelectorAll(".toc-link.active").forEach((el) => el.classList.remove("active"));
      }

      function downloadModifiedHTML() {
          const clone = document.documentElement.cloneNode(true);
          const cloneBody = clone.querySelector("body");
          cloneBody.classList.remove("edit-mode");
          clone.querySelectorAll('[contenteditable="true"]').forEach((el) => {
              el.removeAttribute("contenteditable");
              el.removeAttribute("title");
          });
          clone.querySelectorAll(".delete-btn").forEach((button) => button.remove());
          stripTransientClasses(clone);

          const htmlString = "<!DOCTYPE html>\n" + clone.outerHTML;
          const blob = new Blob([htmlString], { type: "text/html" });
          const url = URL.createObjectURL(blob);
          const anchor = document.createElement("a");
          anchor.href = url;
          anchor.download = "goa_form_modified.html";
          document.body.appendChild(anchor);
          anchor.click();
          document.body.removeChild(anchor);
          URL.revokeObjectURL(url);
          alert("Modified form downloaded.");
      }

      function saveFilledFormHTML() {
          saveDraftToLocalStorage();
          const clone = document.documentElement.cloneNode(true);
          const cloneBody = clone.querySelector("body");
          cloneBody.classList.remove("edit-mode");
          clone.querySelectorAll('[contenteditable="true"]').forEach((el) => {
              el.removeAttribute("contenteditable");
              el.removeAttribute("title");
          });
          clone.querySelectorAll(".delete-btn").forEach((button) => button.remove());
          stripTransientClasses(clone);

          document.querySelectorAll('input[type="text"], input[type="number"]').forEach((input, index) => {
              const cloneInputs = clone.querySelectorAll('input[type="text"], input[type="number"]');
              if (cloneInputs[index]) {
                  cloneInputs[index].setAttribute("value", input.value || "");
              }
          });

          document.querySelectorAll('input[type="checkbox"]').forEach((checkbox, index) => {
              const cloneCheckboxes = clone.querySelectorAll('input[type="checkbox"]');
              if (!cloneCheckboxes[index]) return;
              if (checkbox.checked) {
                  cloneCheckboxes[index].setAttribute("checked", "checked");
              } else {
                  cloneCheckboxes[index].removeAttribute("checked");
              }
          });

          document.querySelectorAll("textarea").forEach((textarea, index) => {
              const cloneTextareas = clone.querySelectorAll("textarea");
              if (cloneTextareas[index]) {
                  cloneTextareas[index].textContent = textarea.value || "";
              }
          });

          const htmlString = "<!DOCTYPE html>\n" + clone.outerHTML;
          const blob = new Blob([htmlString], { type: "text/html" });
          const url = URL.createObjectURL(blob);
          const anchor = document.createElement("a");
          anchor.href = url;
          anchor.download = "goa_form_filled.html";
          document.body.appendChild(anchor);
          anchor.click();
          document.body.removeChild(anchor);
          URL.revokeObjectURL(url);
          alert("Filled form saved as HTML.");
      }

      function generatePDF() {
          const wasInEditMode = document.body.classList.contains("edit-mode");
          if (wasInEditMode) {
              document.body.classList.remove("edit-mode");
          }

          const searchInput = document.getElementById("fieldSearchInput");
          const previousQuery = searchInput ? searchInput.value : "";
          if (searchInput && previousQuery.trim()) {
              searchInput.value = "";
              applySearchFilter("");
          }

          const sections = document.querySelectorAll(".section");
          const collapsedSections = [];
          sections.forEach((section, index) => {
              if (section.classList.contains("collapsed")) {
                  collapsedSections.push(index);
                  section.classList.remove("collapsed");
                  const header = section.querySelector(".section-header");
                  if (header) header.classList.add("active");
              }
          });

          setTimeout(() => {
              window.print();
              setTimeout(() => {
                  collapsedSections.forEach((index) => {
                      sections[index].classList.add("collapsed");
                      const header = sections[index].querySelector(".section-header");
                      if (header) header.classList.remove("active");
                  });

                  if (searchInput && previousQuery.trim()) {
                      searchInput.value = previousQuery;
                      applySearchFilter(previousQuery);
                  }

                  if (wasInEditMode) {
                      document.body.classList.add("edit-mode");
                  }
                 updateActiveSectionFromScroll();
              }, 100);
          }, 300);
      }

      function expandAllSections() {
          document.querySelectorAll(".section:not(.section-hidden-by-search)").forEach((section) => {
              section.classList.remove("collapsed");
              const header = section.querySelector(".section-header");
              if (header) header.classList.add("active");
          });
      }

      function collapseAllSections() {
          document.querySelectorAll(".section:not(.section-hidden-by-search)").forEach((section) => {
              section.classList.add("collapsed");
              const header = section.querySelector(".section-header");
              if (header) header.classList.remove("active");
          });
      }
</script>
  </body>
</html>

"""
    return template.replace("__FORM_BODY__", body)

def generate_goa_form(excel_path: Path = EXCEL_PATH, output_path: Path = OUTPUT_HTML_PATH) -> bool:
    """
    Generates the HTML form from the Excel template.
    """
    try:
        print(f"Generating form from {excel_path}...")
        rows = load_rows(excel_path)
        html_doc = build_html(rows)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_doc)
        print(f"Successfully generated {output_path} with {len(rows)} fields.")
        return True
    except Exception as e:
        print(f"Error generating form: {e}")
        import traceback
        traceback.print_exc()
        return False

def extract_schema_from_excel(excel_path: Path = EXCEL_PATH) -> Dict[str, Dict]:
    """
    Extracts a schema dictionary from the Excel template for use by the LLM.
    
    Returns:
    {
        "placeholder_key": {
            "type": "string" | "boolean",
            "section": "Section Name",
            "subsection": "Subsection Name",
            "description": "Full description for LLM",
            "synonyms": [...],
            "positive_indicators": [...]
        }
    }
    """
    try:
        resolved_path = Path(excel_path)
        if not resolved_path.exists():
            raise FileNotFoundError(f"Excel template not found at {resolved_path}")
        stat = resolved_path.stat()
        cached_schema = _extract_schema_from_excel_cached(str(resolved_path.resolve()), stat.st_mtime_ns)
        # Return a copy so callers can safely mutate without polluting cache.
        return copy.deepcopy(cached_schema)
    except Exception as e:
        print(f"Error extracting schema from Excel: {e}")
        return {}


@lru_cache(maxsize=4)
def _extract_schema_from_excel_cached(excel_path_str: str, excel_mtime_ns: int) -> Dict[str, Dict]:
    """
    Cached schema extraction keyed by absolute path + file mtime.

    mtime is part of the key so template edits invalidate the cache naturally.
    """
    del excel_mtime_ns
    rows = load_rows(Path(excel_path_str))
    schema: Dict[str, Dict] = {}

    from src.utils.template_utils import generate_synonyms_for_checkbox, generate_positive_indicators

    def _build_text_semantics(section: str, description: str) -> Dict[str, Any]:
        section_norm = str(section or "").strip().lower()
        desc_norm = str(description or "").strip().lower()

        semantic_tag = None
        text_indicators: list[str] = []
        value_patterns: list[str] = []

        if section_norm == "basic information" and "direction" in desc_norm:
            semantic_tag = "direction"
            text_indicators = [
                "line direction",
                "from left to right",
                "from right to left",
                "left to right",
                "right to left",
            ]
            value_patterns = [
                r"\bfrom\s+left\s+to\s+right\b",
                r"\bfrom\s+right\s+to\s+left\b",
                r"\bleft\s+to\s+right\b",
                r"\bright\s+to\s+left\b",
            ]
        elif "utility specifications" in section_norm and "voltage" in desc_norm:
            semantic_tag = "voltage"
            text_indicators = [
                "line voltage",
                "voltage",
                "volts",
                "vac",
            ]
            value_patterns = [
                r"\b\d{2,4}(?:\s*/\s*\d{2,4})?\s*(?:v|volt|volts|vac)\b",
            ]
        elif "utility specifications" in section_norm and "hz" in desc_norm:
            semantic_tag = "hz"
            text_indicators = [
                "frequency",
                "hz",
                "hertz",
                "line frequency",
            ]
            value_patterns = [
                r"\b\d{2,3}(?:\s*/\s*\d{2,3})?\s*(?:hz|hertz)\b",
            ]
        elif "utility specifications" in section_norm and "phase" in desc_norm:
            semantic_tag = "phases"
            text_indicators = [
                "phase",
                "phases",
                "single phase",
                "three phase",
            ]
            value_patterns = [
                r"\b[123]\s*(?:phase|phases)\b",
            ]

        if not semantic_tag:
            return {}

        return {
            "semantic_tag": semantic_tag,
            "text_indicators": text_indicators,
            "value_patterns": value_patterns,
        }

    for row in rows:
        ph_key = row["placeholder"]
        ftype = "boolean" if row["type"] == "checkbox" else "string"

        # Keep section hierarchy in description for better LLM guidance.
        parts = [row["section"], row["subsection"], row["subsub"], row["field"]]
        description = " - ".join(filter(None, parts))

        schema[ph_key] = {
            "type": ftype,
            "section": row["section"],
            "subsection": row["subsection"],
            "description": description,
            "location": "form",
        }

        if ftype == "boolean":
            synonyms = generate_synonyms_for_checkbox(ph_key, description)
            schema[ph_key]["synonyms"] = synonyms
            schema[ph_key]["positive_indicators"] = generate_positive_indicators(ph_key, description, synonyms)
        else:
            text_semantics = _build_text_semantics(row["section"], description)
            if text_semantics:
                schema[ph_key].update(text_semantics)

    return schema

def get_all_fields_from_excel(excel_path: Path = EXCEL_PATH) -> Dict[str, str]:
    """
    Returns a simple dictionary of {placeholder: description} for all fields.
    Used for the CRM editor "Add Field" dropdown.
    """
    try:
        rows = load_rows(excel_path)
        fields = {}
        for row in rows:
            ph_key = row["placeholder"]
            parts = [row["section"], row["subsection"], row["subsub"], row["field"]]
            description = " - ".join(filter(None, parts))
            fields[ph_key] = description
        return fields
    except Exception as e:
        print(f"Error getting fields from Excel: {e}")
        return {}

if __name__ == "__main__":
    generate_goa_form()
