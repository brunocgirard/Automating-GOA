"""API-native HTML report generation services (no Streamlit dependency)."""

from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any

from src.utils.template_utils import DEFAULT_EXPLICIT_MAPPINGS, SORTSTAR_EXPLICIT_MAPPINGS


def _should_include(field_key: str, value: Any) -> bool:
    if value is None:
        return False
    if field_key.endswith("_check"):
        return str(value).upper() == "YES"
    return str(value).strip() != ""


def _field_label(field_key: str, is_sortstar: bool) -> str:
    mapping = SORTSTAR_EXPLICIT_MAPPINGS if is_sortstar else DEFAULT_EXPLICIT_MAPPINGS
    mapped = mapping.get(field_key, field_key)
    delimiter = " > " if is_sortstar else " - "
    parts = [part.strip() for part in mapped.split(delimiter) if part.strip()]
    return parts[-1] if parts else field_key


def _to_rows(template_data: dict[str, Any], is_sortstar: bool) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for key, value in sorted(template_data.items()):
        if not _should_include(key, value):
            continue
        rows.append(
            {
                "key": key,
                "label": _field_label(key, is_sortstar),
                "value": str(value),
            }
        )
    return rows


def _render_rows(rows: list[dict[str, str]]) -> str:
    if not rows:
        return "<p>No selected fields were available for this machine.</p>"
    html = ['<table class="report-table"><thead><tr><th>Field</th><th>Value</th></tr></thead><tbody>']
    for row in rows:
        html.append(
            "<tr>"
            f"<td>{escape(row['label'])}</td>"
            f"<td>{escape(row['value'])}</td>"
            "</tr>"
        )
    html.append("</tbody></table>")
    return "".join(html)


def generate_machine_report_html(
    template_data: dict[str, Any],
    machine_name: str = "",
    template_type: str = "GOA",
    is_sortstar_machine: bool = False,
) -> str:
    """Generate a detailed machine report HTML from saved template data."""
    rows = _to_rows(template_data, is_sortstar_machine)
    table_html = _render_rows(rows)
    return f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Machine Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 20px; color: #1f2937; }}
    .meta {{ color: #6b7280; margin-bottom: 8px; }}
    .report-table {{ width: 100%; border-collapse: collapse; margin-top: 14px; }}
    .report-table th, .report-table td {{ border: 1px solid #d1d5db; padding: 8px; text-align: left; vertical-align: top; }}
    .report-table th {{ background: #f3f4f6; }}
    .print-btn {{ margin-top: 12px; }}
    @media print {{ .print-btn {{ display: none; }} }}
  </style>
</head>
<body>
  <h1>Machine Build Specification</h1>
  <div class="meta">Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}</div>
  <div class="meta">Machine: {escape(machine_name or "N/A")}</div>
  <div class="meta">Template Type: {escape(template_type)}</div>
  {table_html}
  <button class="print-btn" onclick="window.print()">Print</button>
</body>
</html>
""".strip()


def generate_machine_summary_html(
    template_data: dict[str, Any],
    machine_name: str = "",
    template_type: str = "GOA",
    is_sortstar_machine: bool = False,
) -> str:
    """Generate concise summary HTML from saved template data."""
    rows = _to_rows(template_data, is_sortstar_machine)[:40]
    items = "".join(
        f"<li><strong>{escape(row['label'])}:</strong> {escape(row['value'])}</li>" for row in rows
    )
    if not items:
        items = "<li>No selected summary fields were available.</li>"

    return f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Machine Summary</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 20px; color: #111827; }}
    .meta {{ color: #6b7280; margin-bottom: 8px; }}
    ul {{ line-height: 1.5; }}
    .print-btn {{ margin-top: 12px; }}
    @media print {{ .print-btn {{ display: none; }} }}
  </style>
</head>
<body>
  <h1>Machine Build Summary</h1>
  <div class="meta">Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}</div>
  <div class="meta">Machine: {escape(machine_name or "N/A")}</div>
  <div class="meta">Template Type: {escape(template_type)}</div>
  <ul>{items}</ul>
  <button class="print-btn" onclick="window.print()">Print</button>
</body>
</html>
""".strip()

