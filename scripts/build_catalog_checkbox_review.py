from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from docx import Document
from docx.oxml.ns import qn


EXCLUDED_SECTION_KEYWORDS = (
    "proj. #",
    "order identification",
    "utility specifications",
    "notes",
    "critical urs compliance points",
    "productions notes",
    "fat requirements",
    "manual specifications",
    "validation documents",
    "packaging & transport & warranty & install & spares",
    "revision log",
)

METADATA_PREFIXES = ("bom:", "part:", "ref.", "revision id:")
CONNECTOR_PREFIXES = (
    "with ",
    "without ",
    "for ",
    "including ",
    "includes ",
    "and ",
    "or ",
    "to ",
)

NONE_LABEL_EXACT = {
    "none",
    "no",
    "n/a",
    "na",
    "not applicable",
    "not included",
    "not required",
}


def _normalize_text(text: str) -> str:
    return " ".join(str(text or "").split()).strip()


def _normalize_key(text: str) -> str:
    compact = _normalize_text(text).lower()
    compact = compact.replace("–", "-").replace("—", "-")
    compact = compact.replace("“", '"').replace("”", '"')
    return compact


def _dedupe_cells(cells: list[str]) -> list[str]:
    deduped: list[str] = []
    for cell in cells:
        normalized = _normalize_text(cell)
        if not normalized:
            continue
        if deduped and _normalize_key(deduped[-1]) == _normalize_key(normalized):
            continue
        deduped.append(normalized)
    return deduped


def _row_phrase(cells: list[str]) -> str:
    meaningful: list[str] = []
    for cell in _dedupe_cells(cells):
        lowered = _normalize_key(cell)
        if not lowered:
            continue
        if lowered.startswith(METADATA_PREFIXES):
            continue
        meaningful.append(cell)
    return " | ".join(meaningful).strip()


def _section_is_excluded(section_header: str) -> bool:
    normalized = _normalize_key(section_header)
    return any(keyword in normalized for keyword in EXCLUDED_SECTION_KEYWORDS)


def _looks_like_subsection_label(phrase: str) -> bool:
    normalized = _normalize_key(phrase)
    if not normalized:
        return False
    if "spec." in normalized:
        return True
    if normalized in {"option listing"}:
        return True
    return False


def _checkbox_stats(cell: Any) -> tuple[int, int]:
    boxes = cell._tc.findall(".//" + qn("w:checkBox"))
    if not boxes:
        return 0, 0

    checked_count = 0
    for box in boxes:
        checked = box.find(qn("w:checked"))
        default = box.find(qn("w:default"))
        checked_val = checked.get(qn("w:val")) if checked is not None else None
        default_val = default.get(qn("w:val")) if default is not None else None
        if checked_val == "1" or default_val == "1":
            checked_count += 1
    return len(boxes), checked_count


def _selected_option_labels(cells: list[str], checked_indexes: list[int]) -> list[str]:
    labels: list[str] = []
    for checked_index in checked_indexes:
        for probe in range(checked_index - 1, -1, -1):
            candidate = _normalize_text(cells[probe])
            if not candidate:
                continue
            lowered = _normalize_key(candidate)
            if lowered.startswith(METADATA_PREFIXES):
                continue
            labels.append(candidate)
            break
    deduped: list[str] = []
    for label in labels:
        if label not in deduped:
            deduped.append(label)
    return deduped


def _is_none_like_label(label: str) -> bool:
    normalized = _normalize_key(label)
    normalized = re.sub(r"[^a-z0-9\s/+.-]", " ", normalized)
    normalized = " ".join(normalized.split())
    if not normalized:
        return False
    if normalized in NONE_LABEL_EXACT:
        return True
    if normalized.startswith("none "):
        return True
    return False


def _classify_selection_labels(labels: list[str]) -> dict[str, Any]:
    cleaned = [_normalize_text(label) for label in labels if _normalize_text(label)]
    if not cleaned:
        return {
            "selection_mode": "unspecified",
            "positive_selected_option_labels": [],
            "none_selected_option_labels": [],
            "is_none_selection": False,
            "is_positive_selection": False,
        }

    none_labels = [label for label in cleaned if _is_none_like_label(label)]
    positive_labels = [label for label in cleaned if not _is_none_like_label(label)]

    if positive_labels and none_labels:
        mode = "mixed"
    elif positive_labels:
        mode = "positive"
    elif none_labels:
        mode = "none"
    else:
        mode = "unspecified"

    return {
        "selection_mode": mode,
        "positive_selected_option_labels": positive_labels,
        "none_selected_option_labels": none_labels,
        "is_none_selection": mode == "none",
        "is_positive_selection": mode in {"positive", "mixed"},
    }


def _machine_family(machine_name: str) -> str:
    normalized = _normalize_key(machine_name)
    if "sortstar" in normalized:
        return "sortstar"
    if "labelstar" in normalized:
        return "labelstar"
    if "alpha c" in normalized:
        return "alpha_c"
    if "conquest" in normalized:
        return "conquest"
    if "flowstar" in normalized:
        return "flowstar"
    if "road runner" in normalized:
        return "road_runner"
    if "accurofill" in normalized:
        return "accurofill"
    if "patriot" in normalized:
        return "patriot"
    if "bambino" in normalized:
        return "bambino"
    if "intrepid" in normalized:
        return "intrepid"
    if "bottle unscrambler" in normalized:
        return "bottle_unscrambler"
    return "unknown"


def extract_selected_checkbox_phrases(docx_path: Path) -> list[dict[str, Any]]:
    doc = Document(str(docx_path))
    selected: list[dict[str, Any]] = []

    for table_index, table in enumerate(doc.tables):
        if not table.rows:
            continue

        header_cells = [_normalize_text(cell.text) for cell in table.rows[0].cells]
        section_header = _row_phrase(header_cells)
        if not section_header or _section_is_excluded(section_header):
            continue

        subsection = ""
        pending_prefix: dict[str, Any] | None = None

        for row_index, row in enumerate(table.rows[1:], start=1):
            cells = [_normalize_text(cell.text) for cell in row.cells]
            phrase = _row_phrase(cells)

            total_boxes = 0
            checked_boxes = 0
            checked_indexes: list[int] = []
            for cell_index, cell in enumerate(row.cells):
                box_count, checked_count = _checkbox_stats(cell)
                total_boxes += box_count
                checked_boxes += checked_count
                if checked_count > 0:
                    checked_indexes.append(cell_index)

            has_checkbox = total_boxes > 0
            has_checked = checked_boxes > 0

            if phrase and _normalize_key(phrase) == _normalize_key(section_header):
                pending_prefix = None
                continue

            if phrase and _looks_like_subsection_label(phrase):
                subsection = phrase
                pending_prefix = None
                continue

            if phrase and not has_checkbox:
                pending_prefix = {
                    "phrase": phrase,
                    "row_index": row_index,
                }
                continue

            if not has_checked:
                pending_prefix = None
                continue

            final_phrase = phrase
            source_rows = [row_index]
            if (
                pending_prefix is not None
                and phrase
                and _normalize_key(phrase).startswith(CONNECTOR_PREFIXES)
            ):
                final_phrase = f"{pending_prefix['phrase']} {phrase}".strip()
                source_rows = [int(pending_prefix["row_index"]), row_index]

            selected_option_labels = _selected_option_labels(cells, checked_indexes)
            selection_classification = _classify_selection_labels(selected_option_labels)

            selected.append(
                {
                    "table_index": table_index,
                    "row_index": row_index,
                    "source_rows": source_rows,
                    "section": section_header,
                    "subsection": subsection,
                    "phrase": final_phrase,
                    "selected_option_labels": selected_option_labels,
                    "checkbox_count": total_boxes,
                    "checked_checkbox_count": checked_boxes,
                    **selection_classification,
                }
            )
            pending_prefix = None

    return selected


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a review report of checked GOA legacy-form checkbox rows and link them "
            "to quote line items from the analysis dataset."
        )
    )
    parser.add_argument(
        "--dataset",
        default="output/catalog_goa_analysis_dataset.json",
        help="Path to the analysis dataset JSON.",
    )
    parser.add_argument(
        "--output",
        default="output/catalog_checkbox_review.json",
        help="Path to write the checkbox review JSON report.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dataset_path = Path(args.dataset).resolve()
    if not dataset_path.exists():
        raise FileNotFoundError(f"Analysis dataset not found: {dataset_path}")

    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    source_dir = Path(dataset["source_dir"])
    if not source_dir.exists():
        raise FileNotFoundError(f"Source directory not found: {source_dir}")

    records: list[dict[str, Any]] = []
    total_selected_rows = 0

    for group in dataset.get("quote_groups", []):
        quote_line_items: list[str] = []
        for pdf_document in group.get("pdf_documents", []):
            for phrase in pdf_document.get("line_item_descriptions", []):
                normalized = _normalize_text(phrase)
                if normalized:
                    quote_line_items.append(normalized)
        deduped_quote_line_items = list(dict.fromkeys(quote_line_items))

        for record in group.get("records", []):
            goa_path = source_dir / record["relative_path"]
            selected_phrases = extract_selected_checkbox_phrases(goa_path)
            total_selected_rows += len(selected_phrases)

            machine_name = record.get("machine", "")
            records.append(
                {
                    "quote_key": group.get("quote_key", ""),
                    "goa_file": record.get("file_name", ""),
                    "project_number": record.get("project_number", ""),
                    "quote_number": record.get("quote_number", ""),
                    "machine": machine_name,
                    "machine_family": _machine_family(machine_name),
                    "direction": record.get("direction", ""),
                    "quote_line_item_count": len(deduped_quote_line_items),
                    "selected_checkbox_row_count": len(selected_phrases),
                    "quote_line_items": deduped_quote_line_items,
                    "selected_checkbox_phrases": selected_phrases,
                }
            )

    sortstar_records = [record for record in records if record["machine_family"] == "sortstar"]

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_path": str(dataset_path),
        "totals": {
            "record_count": len(records),
            "sortstar_record_count": len(sortstar_records),
            "total_selected_checkbox_rows": total_selected_rows,
        },
        "records": records,
        "sortstar_records": sortstar_records,
    }

    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Wrote checkbox review report to {output_path}")
    print(
        "Summary: "
        f"records={report['totals']['record_count']} "
        f"sortstar={report['totals']['sortstar_record_count']} "
        f"selected_checkbox_rows={report['totals']['total_selected_checkbox_rows']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
