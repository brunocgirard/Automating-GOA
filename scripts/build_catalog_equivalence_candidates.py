from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


GENERIC_QUOTE_PREFIXES = (
    "manual instruction",
    "hard copy of manual instruction",
    "training documentation",
    "iq, oq validation",
    "dq, design qualification",
    "fs, ds ",
    "hds, sds",
    "two (x 2) years",
    "one (x 1) year",
    "start up and commissioning",
)

LOW_SIGNAL_EXACT_PHRASES = {
    "each",
    "includes",
    "for the selected items only",
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
)

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
    "spec",
}

META_OPTION_LABELS = {
    "yes",
    "no",
    "none",
    "n/a",
    "na",
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


def _normalize_text(text: str) -> str:
    return " ".join(str(text or "").split()).strip()


def _normalize_fractions(text: str) -> str:
    normalized = str(text or "")
    for symbol, suffix in UNICODE_FRACTION_DECIMAL_SUFFIX.items():
        normalized = re.sub(
            rf"(\d+)\s*{re.escape(symbol)}",
            lambda match, s=suffix: f"{match.group(1)}{s}",
            normalized,
        )
    for symbol, ascii_fraction in UNICODE_FRACTION_ASCII.items():
        normalized = normalized.replace(symbol, f" {ascii_fraction} ")
    return normalized


def _normalize_key(text: str) -> str:
    compact = _normalize_fractions(_normalize_text(text)).lower()
    compact = compact.replace("–", "-").replace("—", "-")
    compact = compact.replace("“", '"').replace("”", '"').replace("’", "'").replace("″", '"')
    compact = re.sub(r"[^a-z0-9\s/+'.-]", " ", compact)
    compact = re.sub(r"\s+", " ", compact).strip()
    return compact


def _is_numeric_value_phrase(normalized_phrase: str) -> bool:
    cleaned = str(normalized_phrase or "").strip()
    if not cleaned:
        return False
    return bool(
        re.fullmatch(
            r"(?:\d+(?:\.\d+)?(?:\s*/\s*\d+(?:\.\d+)?)?)(?:\s*(?:mm|cm|m|in|inch|ft|vac|v|hz|psi|l|ltr|liters)?)",
            cleaned,
        )
    )


def _tokenize_for_overlap(text: str) -> set[str]:
    normalized = _normalize_key(text)
    return {
        token
        for token in normalized.replace("/", " ").replace("-", " ").split()
        if (
            token not in TOKEN_STOPWORDS
            and (
                len(token) > 2
                or bool(re.fullmatch(r"\d+(?:\.\d+)?", token))
            )
        )
    }


def _is_meta_option_label(text: str) -> bool:
    normalized = _normalize_key(text)
    return normalized in META_OPTION_LABELS


def _field_label_from_selected_phrase(selected_phrase: str) -> str:
    phrase = _normalize_text(selected_phrase)
    if "|" not in phrase:
        return phrase
    return _normalize_text(phrase.split("|", 1)[0])


def _contains_any_phrase(text: str, phrases: set[str]) -> bool:
    normalized = _normalize_key(text)
    return any(phrase in normalized for phrase in phrases)


def _semantic_alias_hits(query_text: str, candidate_text: str) -> int:
    hits = 0
    for group in SEMANTIC_ALIAS_GROUPS:
        if _contains_any_phrase(query_text, group) and _contains_any_phrase(candidate_text, group):
            hits += 1
    return hits


def _parse_quote_atomic_phrases(description: str) -> list[str]:
    raw = str(description or "").replace("\r\n", "\n").replace("\r", "\n")
    if not raw.strip():
        return []

    # Promote common inline bullet markers to line breaks before splitting.
    raw = re.sub(r"\s+[•►▸·]\s+", "\n", raw)
    raw = re.sub(r"(?<=[:;])\s*-\s+", "\n", raw)

    phrases: list[str] = []
    for line in raw.split("\n"):
        cleaned = line.strip()
        if not cleaned:
            continue
        cleaned = re.sub(r"^[•\-\*►▸·]\s*", "", cleaned).strip()
        cleaned = _normalize_text(cleaned)
        if not cleaned:
            continue
        normalized = _normalize_key(cleaned)
        if not normalized:
            continue
        if any(normalized.startswith(prefix) for prefix in GENERIC_QUOTE_PREFIXES):
            continue
        if normalized in LOW_SIGNAL_EXACT_PHRASES:
            continue
        if any(fragment in normalized for fragment in LOW_SIGNAL_CONTAINS):
            continue
        if len(normalized) <= 4 and not _is_numeric_value_phrase(normalized):
            continue
        phrases.append(cleaned)

    deduped: list[str] = []
    for phrase in phrases:
        if phrase not in deduped:
            deduped.append(phrase)
    return deduped


def _record_id(record: dict[str, Any]) -> str:
    return f"{record.get('quote_key', '')}::{record.get('goa_file', '')}"


def _selected_query_texts(selected: dict[str, Any]) -> list[str]:
    selected_phrase = str(selected.get("phrase", "")).strip()
    field_label = _field_label_from_selected_phrase(selected_phrase)
    preferred_option_labels = selected.get("positive_selected_option_labels") or selected.get("selected_option_labels", [])

    query_texts: list[str] = []

    for value in preferred_option_labels:
        normalized_value = str(value).strip()
        if not normalized_value or _is_meta_option_label(normalized_value):
            continue
        query_texts.append(normalized_value)

    # For matrix-like options (e.g., "Width | 3 | 4 | 7"), prefer the field label
    # and selected value, not the full option list.
    if field_label:
        query_texts.append(field_label)
    elif selected_phrase:
        query_texts.append(selected_phrase)

    if selected_phrase and "|" not in selected_phrase:
        query_texts.append(selected_phrase)

    if str(selected.get("subsection", "")).strip():
        query_texts.append(str(selected.get("subsection", "")).strip())
    # De-duplicate while preserving order.
    deduped: list[str] = []
    for text in query_texts:
        if text and text not in deduped:
            deduped.append(text)
    return deduped


def _candidate_relevance_score(selected: dict[str, Any], quote_phrase: str) -> int:
    quote_text = _normalize_text(quote_phrase)
    if not quote_text:
        return 0
    quote_norm = _normalize_key(quote_text)
    quote_tokens = _tokenize_for_overlap(quote_text)
    if not quote_norm and not quote_tokens:
        return 0

    score = 0
    for query_text in _selected_query_texts(selected):
        query_norm = _normalize_key(query_text)
        if not query_norm:
            continue
        query_tokens = _tokenize_for_overlap(query_text)
        overlap = len(query_tokens & quote_tokens)
        alias_hits = _semantic_alias_hits(query_text, quote_text)
        score = max(score, overlap + (alias_hits * 2))

        if query_norm in quote_norm:
            score = max(score, 5)
        else:
            query_parts = [
                part
                for part in query_tokens
                if len(part) >= 3 and not bool(re.fullmatch(r"\d+(?:\.\d+)?", part))
            ]
            if query_parts:
                partial_hits = sum(1 for part in query_parts if part in quote_norm)
                if partial_hits:
                    score = max(score, min(4, partial_hits))

    return score


def _score_line_item_relevance(selected: dict[str, Any], description: str) -> int:
    description_text = _normalize_text(description)
    if not description_text:
        return 0

    description_norm = _normalize_key(description_text)
    description_tokens = _tokenize_for_overlap(description_text)
    if not description_tokens and not description_norm:
        return 0

    query_texts = _selected_query_texts(selected)

    best_score = 0
    for query_text in query_texts:
        query_norm = _normalize_key(query_text)
        if not query_norm:
            continue

        query_tokens = _tokenize_for_overlap(query_text)
        overlap = len(query_tokens & description_tokens)
        alias_hits = _semantic_alias_hits(query_text, description_text)

        score = overlap + (alias_hits * 2)
        if query_norm in description_norm:
            score += 3
        else:
            query_parts = [
                part
                for part in query_tokens
                if len(part) >= 3 and not bool(re.fullmatch(r"\d+(?:\.\d+)?", part))
            ]
            partial_hits = sum(1 for part in query_parts if part in description_norm)
            if partial_hits:
                score += min(2, partial_hits)

        if score > best_score:
            best_score = score

    return best_score


def _related_quote_line_items(selected: dict[str, Any], pdf_documents: list[dict[str, Any]]) -> list[str]:
    scored_items: list[tuple[int, str]] = []

    for pdf_document in pdf_documents:
        for line_item in pdf_document.get("line_items", []):
            description = _normalize_text(line_item.get("description", ""))
            if not description:
                continue
            score = _score_line_item_relevance(selected, description)
            if score > 0:
                scored_items.append((score, description))

    if not scored_items:
        return []

    scored_items.sort(key=lambda item: (-item[0], item[1]))
    best_score = scored_items[0][0]

    selected_descriptions: list[str] = []
    for score, description in scored_items:
        if len(selected_descriptions) >= 2:
            break
        if score < max(1, best_score - 1):
            continue
        if description not in selected_descriptions:
            selected_descriptions.append(description)

    return selected_descriptions or [scored_items[0][1]]


def _top_candidates(bucket: dict[str, dict[str, Any]], *, limit: int = 25) -> list[dict[str, Any]]:
    items = sorted(
        bucket.values(),
        key=lambda item: (-int(item["count"]), -int(item.get("relevance_sum", 0)), item["phrase"]),
    )
    return items[:limit]


def _build_candidate_index(
    checkbox_records: list[dict[str, Any]],
    quote_group_map: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    selected_phrase_buckets: dict[str, dict[str, Any]] = {}

    for record in checkbox_records:
        quote_key = record.get("quote_key", "")
        group = quote_group_map.get(quote_key)
        if not group:
            continue

        pdf_documents = list(group.get("pdf_documents", []))
        record_key = _record_id(record)

        for selected in record.get("selected_checkbox_phrases", []):
            if bool(selected.get("is_none_selection")):
                # "None" rows represent explicit absence, not positive feature evidence.
                continue

            selected_phrase = _normalize_text(selected.get("phrase", ""))
            if not selected_phrase:
                continue
            selected_key = _normalize_key(selected_phrase)
            if not selected_key:
                continue

            bucket = selected_phrase_buckets.setdefault(
                selected_key,
                {
                    "selected_phrase": selected_phrase,
                    "occurrence_count": 0,
                    "machine_families": set(),
                    "records": set(),
                    "selected_option_labels": set(),
                    "quote_phrase_candidates": {},
                },
            )

            if record_key not in bucket["records"]:
                bucket["occurrence_count"] += 1
                bucket["records"].add(record_key)
            bucket["machine_families"].add(record.get("machine_family", "unknown"))
            preferred_option_labels = selected.get("positive_selected_option_labels") or selected.get("selected_option_labels", [])
            for label in preferred_option_labels:
                normalized_label = _normalize_text(str(label))
                if normalized_label:
                    bucket["selected_option_labels"].add(normalized_label)

            related_line_items = _related_quote_line_items(selected, pdf_documents)
            quote_atomic_phrases: list[str] = []
            for description in related_line_items:
                quote_atomic_phrases.extend(_parse_quote_atomic_phrases(description))
            quote_atomic_phrases = list(dict.fromkeys(quote_atomic_phrases))

            for quote_phrase in quote_atomic_phrases:
                quote_key_norm = _normalize_key(quote_phrase)
                if not quote_key_norm:
                    continue
                relevance = _candidate_relevance_score(selected, quote_phrase)
                if relevance <= 0:
                    continue
                candidate = bucket["quote_phrase_candidates"].setdefault(
                    quote_key_norm,
                    {
                        "phrase": quote_phrase,
                        "count": 0,
                        "relevance_sum": 0,
                        "sample_records": set(),
                        "sample_line_items": {},
                    },
                )
                if record_key not in candidate["sample_records"]:
                    candidate["count"] += 1
                    candidate["relevance_sum"] += relevance
                    candidate["sample_records"].add(record_key)
                    candidate["sample_line_items"][record_key] = related_line_items

    results: list[dict[str, Any]] = []
    for key, bucket in selected_phrase_buckets.items():
        candidate_items = []
        for candidate in _top_candidates(bucket["quote_phrase_candidates"]):
            candidate_items.append(
                {
                    "phrase": candidate["phrase"],
                    "count": candidate["count"],
                    "relevance_sum": candidate.get("relevance_sum", 0),
                    "sample_records": sorted(candidate["sample_records"]),
                    "sample_line_items": candidate["sample_line_items"],
                }
            )

        results.append(
            {
                "selected_phrase": bucket["selected_phrase"],
                "occurrence_count": bucket["occurrence_count"],
                "machine_families": sorted(bucket["machine_families"]),
                "sample_records": sorted(bucket["records"]),
                "selected_option_labels": sorted(bucket["selected_option_labels"]),
                "top_quote_phrase_candidates": candidate_items,
            }
        )

    results.sort(key=lambda item: (-int(item["occurrence_count"]), item["selected_phrase"]))
    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build candidate phrase equivalences by aggregating quote phrase co-occurrence "
            "with selected GOA checkbox phrases."
        )
    )
    parser.add_argument(
        "--dataset",
        default="output/catalog_goa_analysis_dataset.json",
        help="Path to the analysis dataset JSON.",
    )
    parser.add_argument(
        "--checkbox-review",
        default="output/catalog_checkbox_review.json",
        help="Path to the checkbox review JSON.",
    )
    parser.add_argument(
        "--output",
        default="output/catalog_equivalence_candidates.json",
        help="Path to write the equivalence candidate JSON.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dataset_path = Path(args.dataset).resolve()
    checkbox_review_path = Path(args.checkbox_review).resolve()

    if not dataset_path.exists():
        raise FileNotFoundError(f"Analysis dataset not found: {dataset_path}")
    if not checkbox_review_path.exists():
        raise FileNotFoundError(f"Checkbox review not found: {checkbox_review_path}")

    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    checkbox_review = json.loads(checkbox_review_path.read_text(encoding="utf-8"))

    quote_group_map = {
        group.get("quote_key", ""): group
        for group in dataset.get("quote_groups", [])
    }
    all_records = list(checkbox_review.get("records", []))
    sortstar_records = list(checkbox_review.get("sortstar_records", []))

    all_candidates = _build_candidate_index(all_records, quote_group_map)
    sortstar_candidates = _build_candidate_index(sortstar_records, quote_group_map)

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_path": str(dataset_path),
        "checkbox_review_path": str(checkbox_review_path),
        "totals": {
            "all_candidate_groups": len(all_candidates),
            "sortstar_candidate_groups": len(sortstar_candidates),
        },
        "all_candidates": all_candidates,
        "sortstar_candidates": sortstar_candidates,
    }

    output_path = Path(args.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Wrote equivalence candidate report to {output_path}")
    print(
        "Summary: "
        f"all_candidate_groups={report['totals']['all_candidate_groups']} "
        f"sortstar_candidate_groups={report['totals']['sortstar_candidate_groups']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
