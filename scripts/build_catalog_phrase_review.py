from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXCLUDED_SECTION_HEADERS = {
    "proj. # | customer | machine | direction",
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
}

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


def _normalize_text(text: str) -> str:
    return " ".join(str(text or "").split()).strip()


def _normalize_key(text: str) -> str:
    compact = _normalize_text(text).lower()
    compact = compact.replace("–", "-").replace("—", "-")
    return compact


def _normalize_phrase_for_count(text: str) -> str:
    compact = _normalize_key(text)
    compact = re.sub(r"[^a-z0-9\s|/+\"'-]", " ", compact)
    compact = re.sub(r"\s+", " ", compact).strip()
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


def _row_cells_to_phrase(cells: list[str]) -> str:
    meaningful: list[str] = []
    for cell in _dedupe_cells(cells):
        lowered = _normalize_key(cell)
        if not lowered:
            continue
        if lowered.startswith(METADATA_PREFIXES):
            continue
        meaningful.append(cell)
    return " | ".join(meaningful).strip()


def _looks_like_subsection_label(phrase: str) -> bool:
    normalized = _normalize_key(phrase)
    if not normalized:
        return False
    if "spec." in normalized:
        return True
    if normalized in {"option listing", "cleaning", "electrical", "control specifications", "reject"}:
        return True
    return False


def _extract_goa_feature_phrases(goa_content: dict[str, Any]) -> list[dict[str, Any]]:
    rows = list(goa_content.get("table_rows", []))
    tables: dict[int, list[dict[str, Any]]] = {}
    for row in rows:
        table_index = int(row.get("table_index", -1))
        tables.setdefault(table_index, []).append(row)

    features: list[dict[str, Any]] = []

    for table_index in sorted(tables):
        table_rows = sorted(tables[table_index], key=lambda item: int(item.get("row_index", 0)))
        if not table_rows:
            continue

        section_header = _row_cells_to_phrase(list(table_rows[0].get("cells", [])))
        section_key = _normalize_key(section_header)
        if section_key in EXCLUDED_SECTION_HEADERS:
            continue

        subsection = ""
        last_feature: dict[str, Any] | None = None

        for row in table_rows[1:]:
            row_index = int(row.get("row_index", 0))
            phrase = _row_cells_to_phrase(list(row.get("cells", [])))
            if not phrase:
                continue

            normalized_phrase = _normalize_key(phrase)
            if not normalized_phrase:
                continue

            if normalized_phrase == section_key:
                continue

            if _looks_like_subsection_label(phrase):
                subsection = phrase
                last_feature = None
                continue

            if any(char.isdigit() for char in normalized_phrase) and len(normalized_phrase) <= 4:
                continue

            if normalized_phrase.startswith(CONNECTOR_PREFIXES) and last_feature is not None:
                last_feature["phrase"] = f"{last_feature['phrase']} {phrase}".strip()
                continue

            feature = {
                "table_index": table_index,
                "row_index": row_index,
                "section": section_header,
                "subsection": subsection,
                "phrase": phrase,
            }
            features.append(feature)
            last_feature = feature

    return features


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


def _top_counts(counter: Counter[str], *, min_count: int = 2, limit: int = 50) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for phrase, count in counter.most_common():
        if count < min_count:
            continue
        results.append({"phrase": phrase, "count": count})
        if len(results) >= limit:
            break
    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a review report that links extracted quote line items with likely selected "
            "feature phrases from completed GOA DOCX files."
        )
    )
    parser.add_argument(
        "--dataset",
        default="output/catalog_goa_analysis_dataset.json",
        help="Path to the analysis dataset JSON produced by build_catalog_goa_analysis_dataset.py",
    )
    parser.add_argument(
        "--output",
        default="output/catalog_phrase_review.json",
        help="Path to write the review JSON report.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dataset_path = Path(args.dataset).resolve()
    if not dataset_path.exists():
        raise FileNotFoundError(f"Analysis dataset not found: {dataset_path}")

    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))

    review_records: list[dict[str, Any]] = []
    quote_phrase_counter: Counter[str] = Counter()
    goa_phrase_counter: Counter[str] = Counter()
    machine_family_counter: Counter[str] = Counter()

    for group in dataset.get("quote_groups", []):
        pdf_documents = list(group.get("pdf_documents", []))
        quote_line_items: list[str] = []
        for pdf_doc in pdf_documents:
            for phrase in pdf_doc.get("line_item_descriptions", []):
                normalized = _normalize_text(phrase)
                if normalized:
                    quote_line_items.append(normalized)

        deduped_quote_line_items = list(dict.fromkeys(quote_line_items))
        for phrase in deduped_quote_line_items:
            quote_phrase_counter[_normalize_phrase_for_count(phrase)] += 1

        for record in group.get("records", []):
            machine_name = record.get("machine", "")
            family = _machine_family(machine_name)
            machine_family_counter[family] += 1

            goa_features = _extract_goa_feature_phrases(record.get("goa_content", {}))
            for feature in goa_features:
                goa_phrase_counter[_normalize_phrase_for_count(feature["phrase"])] += 1

            review_records.append(
                {
                    "quote_key": group.get("quote_key", ""),
                    "goa_file": record.get("file_name", ""),
                    "project_number": record.get("project_number", ""),
                    "quote_number": record.get("quote_number", ""),
                    "machine": machine_name,
                    "machine_family": family,
                    "direction": record.get("direction", ""),
                    "quote_line_item_count": len(deduped_quote_line_items),
                    "goa_feature_count": len(goa_features),
                    "quote_line_items": deduped_quote_line_items,
                    "goa_feature_phrases": goa_features,
                }
            )

    sortstar_records = [record for record in review_records if record["machine_family"] == "sortstar"]

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_path": str(dataset_path),
        "totals": {
            "review_record_count": len(review_records),
            "sortstar_record_count": len(sortstar_records),
            "unique_quote_phrase_count": len(quote_phrase_counter),
            "unique_goa_feature_phrase_count": len(goa_phrase_counter),
        },
        "machine_family_counts": dict(machine_family_counter),
        "repeated_quote_phrases": _top_counts(quote_phrase_counter),
        "repeated_goa_feature_phrases": _top_counts(goa_phrase_counter),
        "records": review_records,
        "sortstar_records": sortstar_records,
    }

    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Wrote phrase review report to {output_path}")
    print(
        "Summary: "
        f"records={report['totals']['review_record_count']} "
        f"sortstar={report['totals']['sortstar_record_count']} "
        f"unique_quote_phrases={report['totals']['unique_quote_phrase_count']} "
        f"unique_goa_feature_phrases={report['totals']['unique_goa_feature_phrase_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
