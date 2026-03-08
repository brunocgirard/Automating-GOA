from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from docx import Document


SUMMARY_FIELDS = {
    "proj. #": "project_number",
    "proj #": "project_number",
    "customer": "customer",
    "machine": "machine",
    "direction": "direction",
    "order date": "order_date",
    "purchase order #": "purchase_order_number",
    "quote #": "quote_number",
    "internal order #": "internal_order_number",
    "customer #": "customer_number",
    "production speed": "production_speed",
}


@dataclass
class GoaRecord:
    file_name: str
    relative_path: str
    customer_key: str
    project_number: str = ""
    customer: str = ""
    machine: str = ""
    direction: str = ""
    order_date: str = ""
    purchase_order_number: str = ""
    quote_number: str = ""
    internal_order_number: str = ""
    customer_number: str = ""
    production_speed: str = ""
    table_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_name": self.file_name,
            "relative_path": self.relative_path,
            "customer_key": self.customer_key,
            "project_number": self.project_number,
            "customer": self.customer,
            "machine": self.machine,
            "direction": self.direction,
            "order_date": self.order_date,
            "purchase_order_number": self.purchase_order_number,
            "quote_number": self.quote_number,
            "internal_order_number": self.internal_order_number,
            "customer_number": self.customer_number,
            "production_speed": self.production_speed,
            "table_count": self.table_count,
        }


def _normalize_cell(text: str) -> str:
    return " ".join(str(text or "").split()).strip()


def _normalize_label(text: str) -> str:
    return _normalize_cell(text).lower().rstrip(":")


def _extract_goa_summary(docx_path: Path, root_dir: Path) -> GoaRecord:
    doc = Document(str(docx_path))
    record = GoaRecord(
        file_name=docx_path.name,
        relative_path=str(docx_path.relative_to(root_dir)),
        customer_key=docx_path.stem.split("_GOA")[0],
        table_count=len(doc.tables),
    )

    captured: dict[str, str] = {}

    # Table 0 usually contains the primary identifiers in a header/value row format.
    if doc.tables:
        first_table = doc.tables[0]
        if len(first_table.rows) >= 2:
            headers = [_normalize_cell(cell.text) for cell in first_table.rows[0].cells]
            values = [_normalize_cell(cell.text) for cell in first_table.rows[1].cells]
            for header, value in zip(headers, values):
                normalized = _normalize_label(header)
                field_name = SUMMARY_FIELDS.get(normalized)
                if field_name and value:
                    captured[field_name] = value

    # Scan the rest of the tables for common key/value pairs in the first two columns.
    for table in doc.tables:
        for row in table.rows:
            cells = [_normalize_cell(cell.text) for cell in row.cells]
            if len(cells) < 2:
                continue
            label = _normalize_label(cells[0])
            value = cells[1]
            if not label or not value:
                continue
            if label == _normalize_label(value):
                continue
            field_name = SUMMARY_FIELDS.get(label)
            if field_name and field_name not in captured:
                captured[field_name] = value

    for field_name, value in captured.items():
        setattr(record, field_name, value)

    return record


def _group_key_for_goa(docx_path: Path) -> str:
    return docx_path.stem.split("_GOA")[0]


def build_manifest(source_dir: Path) -> dict[str, Any]:
    files = sorted(path for path in source_dir.rglob("*") if path.is_file())
    pdfs = [path for path in files if path.suffix.lower() == ".pdf"]
    goas = [path for path in files if path.suffix.lower() == ".docx"]

    quote_groups: dict[str, dict[str, Any]] = {}

    for pdf_path in pdfs:
        key = pdf_path.stem
        entry = quote_groups.setdefault(
            key,
            {
                "quote_key": key,
                "pdf_files": [],
                "goa_files": [],
                "records": [],
            },
        )
        entry["pdf_files"].append(str(pdf_path.relative_to(source_dir)))

    for goa_path in goas:
        key = _group_key_for_goa(goa_path)
        entry = quote_groups.setdefault(
            key,
            {
                "quote_key": key,
                "pdf_files": [],
                "goa_files": [],
                "records": [],
            },
        )
        entry["goa_files"].append(str(goa_path.relative_to(source_dir)))
        entry["records"].append(_extract_goa_summary(goa_path, source_dir).to_dict())

    sorted_groups = []
    dataset_records = 0
    multi_goa_quote_groups = 0

    for key in sorted(quote_groups):
        entry = quote_groups[key]
        record_count = len(entry["records"])
        if len(entry["goa_files"]) > 1:
            multi_goa_quote_groups += 1
        dataset_records += record_count
        sorted_groups.append(
            {
                "quote_key": entry["quote_key"],
                "pdf_files": entry["pdf_files"],
                "goa_files": entry["goa_files"],
                "record_count": record_count,
                "has_multiple_goas": len(entry["goa_files"]) > 1,
                "records": entry["records"],
            }
        )

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_dir": str(source_dir),
        "totals": {
            "pdf_count": len(pdfs),
            "goa_docx_count": len(goas),
            "quote_group_count": len(sorted_groups),
            "dataset_record_count": dataset_records,
            "multi_goa_quote_group_count": multi_goa_quote_groups,
        },
        "quote_groups": sorted_groups,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a structured manifest for a folder of quote PDFs and completed GOA DOCX files."
    )
    parser.add_argument(
        "source_dir",
        nargs="?",
        default="Catalog_GOA",
        help="Folder containing quote PDFs and GOA DOCX files.",
    )
    parser.add_argument(
        "--output",
        default="output/catalog_goa_manifest.json",
        help="Path to write the generated JSON manifest.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_dir = Path(args.source_dir).resolve()
    if not source_dir.exists():
        raise FileNotFoundError(f"Source directory not found: {source_dir}")
    if not source_dir.is_dir():
        raise NotADirectoryError(f"Source path is not a directory: {source_dir}")

    manifest = build_manifest(source_dir)
    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    totals = manifest["totals"]
    print(f"Wrote manifest to {output_path}")
    print(
        "Summary: "
        f"pdfs={totals['pdf_count']} "
        f"goas={totals['goa_docx_count']} "
        f"quote_groups={totals['quote_group_count']} "
        f"records={totals['dataset_record_count']} "
        f"multi_goa_quotes={totals['multi_goa_quote_group_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
