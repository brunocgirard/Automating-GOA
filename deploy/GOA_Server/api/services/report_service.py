"""API-native HTML report generation services (no Streamlit dependency)."""

from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from html import escape
from typing import Any

from src.utils.form_generator import display_label, load_rows
from src.utils.template_utils import DEFAULT_EXPLICIT_MAPPINGS, SORTSTAR_EXPLICIT_MAPPINGS


def _is_yes_checkbox(field_key: str, value: Any) -> bool:
    del field_key
    if value is None:
        return False
    normalized = str(value).strip().upper()
    return normalized in {"YES", "TRUE", "1", "ON", "Y", "CHECKED"}


def _is_checkbox_field(field_key: str) -> bool:
    return field_key.endswith("_check")


def _mapping_for_machine(is_sortstar: bool) -> dict[str, str]:
    return SORTSTAR_EXPLICIT_MAPPINGS if is_sortstar else DEFAULT_EXPLICIT_MAPPINGS


def _display_delimiter(is_sortstar: bool) -> str:
    return " > " if is_sortstar else " - "


def _humanize_field_key(field_key: str) -> str:
    label = field_key.replace("_check", "").replace("_", " ").strip()
    return label if label else field_key


def _normalize_section_name(section_name: str) -> str:
    cleaned = (section_name or "").strip()
    if cleaned.lower().endswith("(section)"):
        cleaned = cleaned[: -len("(section)")].strip()
    return cleaned or "General"


@lru_cache(maxsize=1)
def _goa_checkbox_field_order() -> list[dict[str, str]]:
    rows = load_rows()
    ordered: list[dict[str, str]] = []
    seen: set[str] = set()

    for row in rows:
        placeholder = str(row.get("placeholder", "")).strip()
        if not placeholder or placeholder in seen:
            continue
        if str(row.get("type", "")).strip().lower() != "checkbox":
            continue

        seen.add(placeholder)
        section = _normalize_section_name(str(row.get("section", "")))
        subsection = display_label(str(row.get("subsection", "")).strip())
        subsub = display_label(str(row.get("subsub", "")).strip())
        label = display_label(str(row.get("field", "")).strip()) or placeholder
        item_parts = [part for part in (subsection, subsub, label) if part]
        item = " - ".join(item_parts) if item_parts else label

        ordered.append({"key": placeholder, "section": section, "item": item})

    return ordered


def _label_parts(field_key: str, is_sortstar: bool) -> list[str]:
    mapping = _mapping_for_machine(is_sortstar)
    mapped = mapping.get(field_key, _humanize_field_key(field_key))
    delimiter = _display_delimiter(is_sortstar)
    parts = [part.strip() for part in mapped.split(delimiter) if part.strip()]
    return parts if parts else [_humanize_field_key(field_key)]


def _to_checklist_rows(template_data: dict[str, Any], is_sortstar: bool) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    mapping = _mapping_for_machine(is_sortstar)

    # First: GOA schema-driven checkbox order (fXXXX placeholders).
    for field in _goa_checkbox_field_order():
        key = field["key"]
        if not _is_yes_checkbox(key, template_data.get(key)):
            continue
        rows.append({"key": key, "section": field["section"], "item": field["item"]})
        seen.add(key)

    # Second: legacy mapped checkbox keys in explicit GOA order.
    for key in mapping.keys():
        if key in seen or not _is_checkbox_field(key):
            continue
        if not _is_yes_checkbox(key, template_data.get(key)):
            continue

        parts = _label_parts(key, is_sortstar)
        if len(parts) >= 2:
            section = parts[0]
            item = _display_delimiter(is_sortstar).join(parts[1:])
        else:
            section = "General"
            item = parts[0]

        rows.append(
            {
                "key": key,
                "section": section,
                "item": item,
            }
        )
        seen.add(key)

    # Last: any additional selected legacy checkbox keys not in explicit mapping.
    for key in sorted(template_data.keys()):
        if key in seen or not _is_checkbox_field(key):
            continue
        if not _is_yes_checkbox(key, template_data.get(key)):
            continue

        parts = _label_parts(key, is_sortstar)
        if len(parts) >= 2:
            section = parts[0]
            item = _display_delimiter(is_sortstar).join(parts[1:])
        else:
            section = "General"
            item = parts[0]
        rows.append({"key": key, "section": section, "item": item})
        seen.add(key)

    return rows


def _render_checklist_table(
    rows: list[dict[str, str]],
    *,
    include_notes: bool,
    empty_message: str,
    max_rows: int | None = None,
) -> str:
    rendered_rows = rows[:max_rows] if isinstance(max_rows, int) else rows
    if not rendered_rows:
        return f"<p class=\"hint\">{escape(empty_message)}</p>"

    notes_header = "<th>Notes</th>" if include_notes else ""
    html = [
        '<table class="checklist-table">',
        "<thead>",
        (
            "<tr>"
            "<th class=\"done-col\">Done</th>"
            "<th>Item</th>"
            f"{notes_header}"
            "</tr>"
        ),
        "</thead>",
        "<tbody>",
    ]

    current_section = ""
    for row in rendered_rows:
        section = row["section"]
        if section != current_section:
            col_span = 2 + (1 if include_notes else 0)
            html.append(
                "<tr class=\"section-row\">"
                f"<td colspan=\"{col_span}\">{escape(section)}</td>"
                "</tr>"
            )
            current_section = section

        item_name = row["item"]
        done_label = escape(f"Mark completed: {item_name}")
        notes_cell = "<td class=\"notes-cell\"></td>" if include_notes else ""
        html.append(
            "<tr>"
            "<td class=\"done-cell\">"
            f"<input type=\"checkbox\" aria-label=\"{done_label}\" />"
            "</td>"
            f"<td>{escape(item_name)}</td>"
            f"{notes_cell}"
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
    """Generate a PM-to-engineering GOA checklist report."""
    checklist_rows = _to_checklist_rows(template_data, is_sortstar_machine)
    checklist_count = len(checklist_rows)
    checklist_html = _render_checklist_table(
        checklist_rows,
        include_notes=True,
        empty_message="No selected GOA checklist items were available for this machine.",
    )

    return f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Machine Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 20px; color: #111827; }}
    h1 {{ margin-bottom: 8px; }}
    .meta {{ color: #6b7280; margin-bottom: 6px; }}
    .summary {{ margin: 14px 0; padding: 10px 12px; border: 1px solid #d1d5db; background: #f9fafb; border-radius: 6px; }}
    .summary strong {{ font-size: 18px; }}
    .hint {{ margin: 0; color: #4b5563; font-size: 13px; }}
    .checklist-table {{ width: 100%; border-collapse: collapse; margin-top: 12px; }}
    .checklist-table th, .checklist-table td {{ border: 1px solid #d1d5db; padding: 8px; text-align: left; vertical-align: top; }}
    .checklist-table th {{ background: #f3f4f6; }}
    .section-row td {{ background: #eef2ff; font-weight: 700; color: #1f2937; }}
    .done-col {{ width: 80px; text-align: center; }}
    .done-cell {{ text-align: center; }}
    .done-cell input[type="checkbox"] {{ width: 16px; height: 16px; }}
    .notes-cell {{ min-width: 220px; }}
    .print-btn {{ margin-top: 12px; }}
    @media print {{ .print-btn {{ display: none; }} }}
  </style>
</head>
<body>
  <h1>Machine Build Checklist</h1>
  <div class="meta">Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}</div>
  <div class="meta">Machine: {escape(machine_name or "N/A")}</div>
  <div class="meta">Template Type: {escape(template_type)}</div>
  <div class="summary">
    <div>Selected GOA checklist items: <strong>{checklist_count}</strong></div>
    <p class="hint">Items are listed in GOA section order. Use Done checkboxes during PM + Engineering handoff.</p>
  </div>
  {checklist_html}
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
    """Generate a compact checklist summary for quick handoff."""
    checklist_rows = _to_checklist_rows(template_data, is_sortstar_machine)
    checklist_count = len(checklist_rows)
    checklist_html = _render_checklist_table(
        checklist_rows,
        include_notes=False,
        empty_message="No selected GOA checklist items were available for this machine.",
        max_rows=40,
    )
    truncation_note = (
        "<p class=\"hint\">Showing first 40 checklist items for quick review.</p>"
        if checklist_count > 40
        else ""
    )

    return f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>Machine Summary</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 20px; color: #111827; }}
    h1 {{ margin-bottom: 8px; }}
    .meta {{ color: #6b7280; margin-bottom: 6px; }}
    .summary {{ margin: 14px 0; padding: 10px 12px; border: 1px solid #d1d5db; background: #f9fafb; border-radius: 6px; }}
    .hint {{ margin-top: 8px; color: #4b5563; font-size: 13px; }}
    .checklist-table {{ width: 100%; border-collapse: collapse; margin-top: 12px; }}
    .checklist-table th, .checklist-table td {{ border: 1px solid #d1d5db; padding: 8px; text-align: left; vertical-align: top; }}
    .checklist-table th {{ background: #f3f4f6; }}
    .section-row td {{ background: #eef2ff; font-weight: 700; color: #1f2937; }}
    .done-col {{ width: 80px; text-align: center; }}
    .done-cell {{ text-align: center; }}
    .done-cell input[type="checkbox"] {{ width: 16px; height: 16px; }}
    .print-btn {{ margin-top: 12px; }}
    @media print {{ .print-btn {{ display: none; }} }}
  </style>
</head>
<body>
  <h1>Machine Checklist Summary</h1>
  <div class="meta">Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}</div>
  <div class="meta">Machine: {escape(machine_name or "N/A")}</div>
  <div class="meta">Template Type: {escape(template_type)}</div>
  <div class="summary">
    <div>Selected GOA checklist items: <strong>{checklist_count}</strong></div>
  </div>
  {truncation_note}
  {checklist_html}
  <button class="print-btn" onclick="window.print()">Print</button>
</body>
</html>
""".strip()
