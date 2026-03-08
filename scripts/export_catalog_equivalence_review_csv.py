from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


CSV_COLUMNS = [
    "scope",
    "target_field_label",
    "target_field_key",
    "selected_phrase",
    "selected_occurrence_count",
    "machine_families",
    "candidate_rank",
    "candidate_quote_phrase",
    "candidate_count",
    "selected_sample_records",
    "candidate_sample_records",
    "suggested_priority",
    "review_status",
    "approved_mapping",
    "normalized_concept",
    "reviewer_notes",
]

SIMPLE_CSV_COLUMNS = [
    "scope",
    "machine_families",
    "goa_option",
    "goa_selected_labels",
    "quote_phrase",
    "related_quote_items",
    "evidence",
    "evidence_level",
    "sample_jobs",
    "matching_sample_jobs",
    "missing_sample_jobs",
    "keep_for_future",
    "notes",
]

LOW_SIGNAL_EXACT_PHRASES = {
    "",
    "each",
    "english or french",
    "for the selected items only",
    "includes",
}

LOW_SIGNAL_CONTAINS = (
    "manual",
    "documentation",
    "qualification",
    "service manual",
    "operator manual",
    "maintenance schedule",
    "capmatic ordering",
    "complete electronic file",
    "set up sheet",
    "occurs first",
    "capmatic premises",
)

SEMANTIC_ALIAS_GROUPS = [
    {"stack light", "status beacon", "beacon light", "tower light", "status light"},
    {"buzzer", "audible alarm", "alarm"},
    {"lexan", "euroguard", "top cover", "guard", "guarding", "cover"},
    {"ionized", "ionized air", "blowing"},
    {"hopper", "hopper sensor", "low level hopper sensor", "low level"},
    {"hmi", "touch screen", "screen", "control interface"},
    {"english", "french", "language"},
    {"infeed", "outfeed"},
    {"operator side", "machine side", "rear"},
    {"control panel", "panel control", "swivel panel", "axis"},
    {"explosion proof", "ex proof"},
    {"electrical", "mechanical"},
    {"fallen bottle", "inverted bottle", "bottle detection"},
    {"vacuum", "ionized sys"},
    {"wireway", "wirecovers", "trough"},
    {"tunnel guard", "infeed", "outfeed"},
]

TOKEN_STOPWORDS = {
    "with",
    "without",
    "and",
    "or",
    "the",
    "for",
    "from",
    "into",
    "option",
    "system",
    "only",
    "per",
    "line",
    "side",
    "none",
}

UNICODE_FRACTION_DECIMAL_SUFFIX = {
    "¼": ".25",
    "½": ".5",
    "¾": ".75",
}

UNICODE_FRACTION_ASCII = {
    "¼": "1/4",
    "½": "1/2",
    "¾": "3/4",
}


def _normalize_for_compare(text: str) -> str:
    compact = str(text or "").strip()
    for symbol, suffix in UNICODE_FRACTION_DECIMAL_SUFFIX.items():
        compact = compact.replace(symbol, suffix)
    for symbol, ascii_fraction in UNICODE_FRACTION_ASCII.items():
        compact = compact.replace(symbol, f" {ascii_fraction} ")
    compact = compact.lower()
    compact = compact.replace("–", "-").replace("—", "-")
    compact = compact.replace("“", "").replace("”", "")
    compact = compact.replace("(", " ").replace(")", " ")
    compact = compact.replace('"', " ")
    compact = " ".join(compact.split())
    return compact


def _is_low_signal_phrase(text: str) -> bool:
    normalized = _normalize_for_compare(text)
    if normalized in LOW_SIGNAL_EXACT_PHRASES:
        return True
    if any(fragment in normalized for fragment in LOW_SIGNAL_CONTAINS):
        return True
    return False


def _tokenize_for_overlap(text: str) -> set[str]:
    normalized = _normalize_for_compare(text)
    tokens = {
        token
        for token in normalized.replace("/", " ").replace("-", " ").split()
        if (
            token not in TOKEN_STOPWORDS
            and (
                len(token) > 2
                or token.replace(".", "", 1).isdigit()
            )
        )
    }
    return tokens


def _contains_any_phrase(text: str, phrases: set[str]) -> bool:
    normalized = _normalize_for_compare(text)
    return any(phrase in normalized for phrase in phrases)


def _semantic_alias_hits(selected_phrase: str, candidate_phrase: str) -> int:
    hits = 0
    for group in SEMANTIC_ALIAS_GROUPS:
        if _contains_any_phrase(selected_phrase, group) and _contains_any_phrase(candidate_phrase, group):
            hits += 1
    return hits


def _candidate_sort_key(
    goa_option: str,
    goa_selected_labels: str,
    candidate_phrase: str,
    candidate_count: int,
    relevance_sum: int,
) -> tuple[int, int, int, str]:
    field_label = str(goa_option or "").split("|", 1)[0].strip()
    selected_context = " ".join(part for part in [field_label, str(goa_selected_labels or "").strip()] if part)
    selected_tokens = _tokenize_for_overlap(selected_context)
    candidate_tokens = _tokenize_for_overlap(candidate_phrase)
    overlap = len(selected_tokens & candidate_tokens)
    # Sort descending by count, relevance, overlap, then phrase.
    return (-candidate_count, -relevance_sum, -overlap, _normalize_for_compare(candidate_phrase))


def _suggested_priority(selected_count: int, candidate_count: int) -> str:
    if selected_count >= 4 and candidate_count >= 3:
        return "high"
    if selected_count >= 2 and candidate_count >= 2:
        return "medium"
    return "low"


def _flatten_candidate_rows(scope: str, candidate_groups: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    for group in candidate_groups:
        selected_phrase = str(group.get("selected_phrase", "")).strip()
        selected_count = int(group.get("occurrence_count", 0) or 0)
        machine_families = ", ".join(str(v).strip() for v in group.get("machine_families", []) if str(v).strip())
        selected_samples = " | ".join(
            str(v).strip() for v in group.get("sample_records", []) if str(v).strip()
        )

        top_candidates = list(group.get("top_quote_phrase_candidates", []))
        if not top_candidates:
            rows.append(
                {
                    "scope": scope,
                    "target_field_label": selected_phrase,
                    "target_field_key": "",
                    "selected_phrase": selected_phrase,
                    "selected_occurrence_count": str(selected_count),
                    "machine_families": machine_families,
                    "candidate_rank": "",
                    "candidate_quote_phrase": "",
                    "candidate_count": "0",
                    "selected_sample_records": selected_samples,
                    "candidate_sample_records": "",
                    "suggested_priority": "low",
                    "review_status": "",
                    "approved_mapping": "",
                    "normalized_concept": "",
                    "reviewer_notes": "",
                }
            )
            continue

        for rank, candidate in enumerate(top_candidates, start=1):
            candidate_count = int(candidate.get("count", 0) or 0)
            candidate_samples = " | ".join(
                str(v).strip() for v in candidate.get("sample_records", []) if str(v).strip()
            )
            rows.append(
                {
                    "scope": scope,
                    "target_field_label": selected_phrase,
                    "target_field_key": "",
                    "selected_phrase": selected_phrase,
                    "selected_occurrence_count": str(selected_count),
                    "machine_families": machine_families,
                    "candidate_rank": str(rank),
                    "candidate_quote_phrase": str(candidate.get("phrase", "")).strip(),
                    "candidate_count": str(candidate_count),
                    "selected_sample_records": selected_samples,
                    "candidate_sample_records": candidate_samples,
                    "suggested_priority": _suggested_priority(selected_count, candidate_count),
                    "review_status": "",
                    "approved_mapping": "",
                    "normalized_concept": "",
                    "reviewer_notes": "",
                }
            )

    return rows


def _write_csv(output_path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _evidence_level(selected_count: int, candidate_count: int) -> str:
    if candidate_count == 0:
        return "missing"
    if selected_count == 1:
        return "single-example"
    if candidate_count >= 2:
        return "repeated"
    return "weak"


def _prefill_simple_decision(
    goa_option: str,
    quote_phrase: str,
    selected_count: int,
    candidate_count: int,
) -> tuple[str, str]:
    if _is_low_signal_phrase(quote_phrase):
        return "no", "auto-prefill: low-signal phrase"

    overlap = len(_tokenize_for_overlap(goa_option) & _tokenize_for_overlap(quote_phrase))
    alias_hits = _semantic_alias_hits(goa_option, quote_phrase)

    # Strongest signal: explicit lexical overlap or alias group match.
    score = overlap + (alias_hits * 2)

    if selected_count == 1:
        if score >= 2:
            reason = "auto-prefill: single example but strong semantic match"
            if alias_hits:
                reason = "auto-prefill: single example alias match"
            return "yes", reason
        if score == 1:
            return "maybe", "auto-prefill: single example weak lexical match"
        return "no", "auto-prefill: single example and no meaningful match"

    if score >= 2:
        reason = "auto-prefill: repeated evidence with semantic match"
        if alias_hits:
            reason = "auto-prefill: repeated alias match"
        return "yes", reason
    if score == 1 and candidate_count >= 2:
        return "maybe", "auto-prefill: repeated but only partial lexical match"
    if candidate_count >= max(2, selected_count - 1) and score >= 1:
        return "maybe", "auto-prefill: frequent co-occurrence, verify manually"
    return "no", "auto-prefill: no clear semantic link"


def _flatten_simple_rows(
    scope: str,
    candidate_groups: list[dict[str, Any]],
    *,
    max_candidates_per_option: int = 8,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    for group in candidate_groups:
        selected_phrase = str(group.get("selected_phrase", "")).strip()
        selected_count = int(group.get("occurrence_count", 0) or 0)
        machine_families = ", ".join(str(v).strip() for v in group.get("machine_families", []) if str(v).strip())
        selected_option_labels = " | ".join(
            str(v).strip() for v in group.get("selected_option_labels", []) if str(v).strip()
        )
        selected_samples = [str(v).strip() for v in group.get("sample_records", []) if str(v).strip()]
        sample_jobs = " | ".join(selected_samples)

        filtered_candidates = []
        for candidate in list(group.get("top_quote_phrase_candidates", [])):
            candidate_phrase = str(candidate.get("phrase", "")).strip()
            candidate_count = int(candidate.get("count", 0) or 0)
            relevance_sum = int(candidate.get("relevance_sum", 0) or 0)
            if _is_low_signal_phrase(candidate_phrase):
                continue
            candidate_samples = [
                str(v).strip()
                for v in candidate.get("sample_records", [])
                if str(v).strip()
            ]
            sample_line_items = candidate.get("sample_line_items", {})
            filtered_candidates.append(
                (candidate_phrase, candidate_count, relevance_sum, candidate_samples, sample_line_items)
            )

        filtered_candidates.sort(
            key=lambda item: _candidate_sort_key(selected_phrase, selected_option_labels, item[0], item[1], item[2])
        )

        if not filtered_candidates:
            rows.append(
                {
                    "scope": scope,
                    "machine_families": machine_families,
                    "goa_option": selected_phrase,
                    "goa_selected_labels": selected_option_labels,
                    "quote_phrase": "",
                    "related_quote_items": "",
                    "evidence": f"0/{selected_count}",
                    "evidence_level": _evidence_level(selected_count, 0),
                    "sample_jobs": sample_jobs,
                    "matching_sample_jobs": "",
                    "missing_sample_jobs": sample_jobs,
                    "keep_for_future": "no",
                    "notes": "auto-prefill: no semantically relevant quote phrase found",
                }
            )
            continue

        for candidate_phrase, candidate_count, _relevance_sum, candidate_samples, sample_line_items in filtered_candidates[:max_candidates_per_option]:
            keep_for_future, notes = _prefill_simple_decision(
                selected_phrase,
                candidate_phrase,
                selected_count,
                candidate_count,
            )
            matching_sample_jobs = " | ".join(candidate_samples)
            missing_sample_jobs = " | ".join(
                sample for sample in selected_samples if sample not in set(candidate_samples)
            )
            related_quote_items_list: list[str] = []
            for sample in candidate_samples:
                for line_item in sample_line_items.get(sample, []):
                    normalized_line_item = str(line_item).strip()
                    if normalized_line_item and normalized_line_item not in related_quote_items_list:
                        related_quote_items_list.append(normalized_line_item)
            related_quote_items = " || ".join(related_quote_items_list)
            rows.append(
                {
                    "scope": scope,
                    "machine_families": machine_families,
                    "goa_option": selected_phrase,
                    "goa_selected_labels": selected_option_labels,
                    "quote_phrase": candidate_phrase,
                    "related_quote_items": related_quote_items,
                    "evidence": f"{candidate_count}/{selected_count}",
                    "evidence_level": _evidence_level(selected_count, candidate_count),
                    "sample_jobs": sample_jobs,
                    "matching_sample_jobs": matching_sample_jobs,
                    "missing_sample_jobs": missing_sample_jobs,
                    "keep_for_future": keep_for_future,
                    "notes": notes,
                }
            )

    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Flatten equivalence-candidate JSON into human-review CSV files with blank approval columns."
        )
    )
    parser.add_argument(
        "--input",
        default="output/catalog_equivalence_candidates.json",
        help="Path to the equivalence candidate JSON report.",
    )
    parser.add_argument(
        "--all-output",
        default="output/catalog_equivalence_review_all.csv",
        help="Path to write the all-machine review CSV.",
    )
    parser.add_argument(
        "--sortstar-output",
        default="output/catalog_equivalence_review_sortstar.csv",
        help="Path to write the SortStar-only review CSV.",
    )
    parser.add_argument(
        "--all-simple-output",
        default="output/catalog_equivalence_review_all_simple.csv",
        help="Path to write the simplified all-machine review CSV.",
    )
    parser.add_argument(
        "--sortstar-simple-output",
        default="output/catalog_equivalence_review_sortstar_simple.csv",
        help="Path to write the simplified SortStar-only review CSV.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = Path(args.input).resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"Equivalence candidate report not found: {input_path}")

    report = json.loads(input_path.read_text(encoding="utf-8"))
    all_rows = _flatten_candidate_rows("all", list(report.get("all_candidates", [])))
    sortstar_rows = _flatten_candidate_rows("sortstar", list(report.get("sortstar_candidates", [])))
    all_simple_rows = _flatten_simple_rows("all", list(report.get("all_candidates", [])))
    sortstar_simple_rows = _flatten_simple_rows("sortstar", list(report.get("sortstar_candidates", [])))

    all_output = Path(args.all_output).resolve()
    sortstar_output = Path(args.sortstar_output).resolve()
    all_simple_output = Path(args.all_simple_output).resolve()
    sortstar_simple_output = Path(args.sortstar_simple_output).resolve()
    _write_csv(all_output, all_rows, CSV_COLUMNS)
    _write_csv(sortstar_output, sortstar_rows, CSV_COLUMNS)
    _write_csv(all_simple_output, all_simple_rows, SIMPLE_CSV_COLUMNS)
    _write_csv(sortstar_simple_output, sortstar_simple_rows, SIMPLE_CSV_COLUMNS)

    print(f"Wrote all-machine review CSV to {all_output}")
    print(f"Wrote SortStar review CSV to {sortstar_output}")
    print(f"Wrote simplified all-machine review CSV to {all_simple_output}")
    print(f"Wrote simplified SortStar review CSV to {sortstar_simple_output}")
    print(
        "Summary: "
        f"all_rows={len(all_rows)} "
        f"sortstar_rows={len(sortstar_rows)} "
        f"all_simple_rows={len(all_simple_rows)} "
        f"sortstar_simple_rows={len(sortstar_simple_rows)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
