from __future__ import annotations

import copy
import csv
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any


DEFAULT_OVERRIDES_PATH = Path("config") / "goa_field_semantic_overrides.json"

LOADABLE_REVIEW_STATUSES = {
    "",
    "approved",
    "approved_seed",
    "seed",
}

_GENERIC_TOKENS = {
    "and",
    "checkbox",
    "control",
    "field",
    "for",
    "general",
    "goa",
    "machine",
    "none",
    "option",
    "options",
    "or",
    "qty",
    "section",
    "spec",
    "specifications",
    "system",
    "the",
    "type",
    "with",
}

_CATALOG_FAMILY_TO_RUNTIME = {
    "accurofill": "filling",
    "alpha_c": "capping",
    "bambino": "filling",
    "bottle_unscrambler": "sortstar",
    "capping": "capping",
    "conquest": "filling",
    "filling": "filling",
    "flowstar": "filling",
    "general": "general",
    "intrepid": "filling",
    "labeling": "labeling",
    "labelstar": "labeling",
    "patriot": "filling",
    "road_runner": "filling",
    "sortstar": "sortstar",
}

_UNICODE_FRACTIONS = {
    "¼": "1/4",
    "½": "1/2",
    "¾": "3/4",
}


def _normalize_space(text: str) -> str:
    return " ".join(str(text or "").split()).strip()


def normalize_semantic_text(text: str) -> str:
    normalized = _normalize_space(text).lower()
    for source, target in _UNICODE_FRACTIONS.items():
        normalized = normalized.replace(source, f" {target} ")
    normalized = normalized.replace("–", "-").replace("—", "-")
    normalized = normalized.replace("“", '"').replace("”", '"').replace("’", "'")
    normalized = normalized.replace("w/", "with ")
    normalized = normalized.replace("&", " and ")
    normalized = re.sub(r"\bqty[:.]?\b", "quantity", normalized)
    normalized = re.sub(r"\byrs?\b", "year", normalized)
    normalized = re.sub(r"\boper\.\b", "operator", normalized)
    normalized = re.sub(r"(\d+)\s*\"", r"\1 inch", normalized)
    normalized = re.sub(r"(\d+)\s*''", r"\1 inch", normalized)
    normalized = re.sub(r"(\d+)\s*”", r"\1 inch", normalized)
    normalized = re.sub(r"[^a-z0-9\s/+.-]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _split_list_like(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        raw_items = value
    else:
        raw_text = str(value).strip()
        if not raw_text:
            return []
        raw_items = re.split(r"\s*\|\|\s*|\s*;\s*", raw_text)

    cleaned: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        text = _normalize_space(str(item))
        if not text:
            continue
        key = normalize_semantic_text(text)
        if not key or key in seen:
            continue
        seen.add(key)
        cleaned.append(text)
    return cleaned


def _merge_prefer_first(preferred: list[str], existing: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()

    for value in [*preferred, *existing]:
        text = _normalize_space(str(value))
        if not text:
            continue
        key = normalize_semantic_text(text)
        if not key or key in seen:
            continue
        seen.add(key)
        merged.append(text)
    return merged


def normalize_runtime_machine_family(machine_family: str) -> str:
    normalized = normalize_semantic_text(machine_family).replace(" ", "_")
    return _CATALOG_FAMILY_TO_RUNTIME.get(normalized, normalized)


def _split_machine_family_values(values: Any) -> list[str]:
    if values is None:
        return []
    if isinstance(values, list):
        raw_items = values
    else:
        raw_text = str(values).strip()
        if not raw_text:
            return []
        raw_items = re.split(r"\s*\|\|\s*|\s*;\s*|\s*,\s*", raw_text)
    return [_normalize_space(str(item)) for item in raw_items if _normalize_space(str(item))]


def _expand_compound_machine_family(value: str) -> list[str]:
    normalized = normalize_semantic_text(value).replace(" ", "_")
    if not normalized:
        return []

    known_keys = sorted(set(_CATALOG_FAMILY_TO_RUNTIME) | set(_CATALOG_FAMILY_TO_RUNTIME.values()), key=len, reverse=True)
    if normalized in known_keys:
        return [normalize_runtime_machine_family(normalized)]

    parts = normalized.split("_")
    expanded: list[str] = []
    index = 0
    while index < len(parts):
        match = None
        for probe in range(len(parts), index, -1):
            candidate = "_".join(parts[index:probe])
            if candidate in known_keys:
                match = candidate
                index = probe
                break
        if match is None:
            match = parts[index]
            index += 1
        expanded.append(normalize_runtime_machine_family(match))
    return expanded


def normalize_machine_family_scope(values: Any) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in _split_machine_family_values(values):
        for family in _expand_compound_machine_family(value):
            if not family or family in seen:
                continue
            seen.add(family)
            normalized.append(family)
    return normalized


def _entry_is_loadable(entry: dict[str, Any]) -> bool:
    review_status = normalize_semantic_text(str(entry.get("review_status", "")))
    return review_status in LOADABLE_REVIEW_STATUSES


def _normalize_override_entry(entry: dict[str, Any]) -> dict[str, Any]:
    template_scope = normalize_semantic_text(entry.get("template_scope", "")) or "default"
    return {
        "template_scope": template_scope,
        "machine_families": normalize_machine_family_scope(entry.get("machine_families", [])),
        "option_group": _normalize_space(entry.get("option_group", "")),
        "aliases": _split_list_like(entry.get("aliases", [])),
        "positive_evidence": _split_list_like(entry.get("positive_evidence", [])),
        "negative_evidence": _split_list_like(entry.get("negative_evidence", [])),
        "related_terms": _split_list_like(entry.get("related_terms", [])),
        "notes": _normalize_space(entry.get("notes", "")),
        "review_status": _normalize_space(entry.get("review_status", "")),
    }


@lru_cache(maxsize=4)
def _load_goa_field_semantic_overrides_cached(path_str: str, mtime_ns: int) -> dict[str, dict[str, Any]]:
    del mtime_ns
    path = Path(path_str)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and isinstance(payload.get("fields"), dict):
        raw_fields = payload["fields"]
    elif isinstance(payload, dict):
        raw_fields = payload
    else:
        raw_fields = {}

    normalized: dict[str, dict[str, Any]] = {}
    for field_key, raw_entry in raw_fields.items():
        if not isinstance(raw_entry, dict) or str(field_key).startswith("_"):
            continue
        if not _entry_is_loadable(raw_entry):
            continue
        normalized[str(field_key)] = _normalize_override_entry(raw_entry)

    return normalized


def load_goa_field_semantic_overrides(
    overrides_path: str | Path | None = None,
) -> dict[str, dict[str, Any]]:
    path = Path(overrides_path) if overrides_path else DEFAULT_OVERRIDES_PATH
    if not path.exists():
        return {}
    stat = path.stat()
    loaded = _load_goa_field_semantic_overrides_cached(str(path.resolve()), stat.st_mtime_ns)
    return copy.deepcopy(loaded)


def _scope_matches(
    override: dict[str, Any],
    *,
    template_scope: str,
    machine_family: str | None,
) -> bool:
    override_scope = normalize_semantic_text(override.get("template_scope", "")) or "default"
    requested_scope = normalize_semantic_text(template_scope) or "default"
    if override_scope != requested_scope:
        return False

    allowed_families = [
        normalize_runtime_machine_family(value)
        for value in override.get("machine_families", [])
        if _normalize_space(str(value))
    ]
    if not allowed_families:
        return True
    if not machine_family:
        return False

    return normalize_runtime_machine_family(machine_family) in allowed_families


def merge_semantic_overrides_into_schema(
    schema: dict[str, dict[str, Any]],
    *,
    template_scope: str,
    machine_family: str | None = None,
    overrides_path: str | Path | None = None,
) -> dict[str, dict[str, Any]]:
    overrides = load_goa_field_semantic_overrides(overrides_path)
    if not overrides:
        return schema

    for field_key, field_context in schema.items():
        if not isinstance(field_context, dict):
            continue
        override = overrides.get(field_key)
        if not override or not _scope_matches(override, template_scope=template_scope, machine_family=machine_family):
            continue

        approved_aliases = _merge_prefer_first(override["aliases"], override["related_terms"])
        approved_positive = list(override["positive_evidence"])
        approved_negative = list(override["negative_evidence"])

        field_context["synonyms"] = _merge_prefer_first(approved_aliases, list(field_context.get("synonyms", [])))
        field_context["positive_indicators"] = _merge_prefer_first(
            approved_positive,
            list(field_context.get("positive_indicators", [])),
        )
        field_context["negative_indicators"] = _merge_prefer_first(
            approved_negative,
            list(field_context.get("negative_indicators", [])),
        )
        field_context["approved_aliases"] = approved_aliases
        field_context["approved_positive_evidence"] = approved_positive
        field_context["approved_negative_evidence"] = approved_negative
        if override.get("option_group"):
            field_context["option_group"] = override["option_group"]
        if override.get("notes"):
            field_context["semantic_notes"] = override["notes"]
        field_context["semantic_override_applied"] = True

    return schema


def _clean_field_label(label: str) -> str:
    cleaned = _normalize_space(label)
    cleaned = re.sub(r"\s*\((?:checkbox|text|qty|textarea)[^)]*\)\s*$", "", cleaned, flags=re.IGNORECASE)
    return _normalize_space(cleaned)


def build_schema_target_index(
    schema: dict[str, dict[str, Any]],
    *,
    template_scope: str,
) -> list[dict[str, Any]]:
    targets: list[dict[str, Any]] = []
    for field_key, field_info in schema.items():
        if not isinstance(field_info, dict) or field_info.get("type") != "boolean":
            continue

        field_label = _clean_field_label(str(field_info.get("description", field_key)))
        parts = [_clean_field_label(part) for part in field_label.split(" - ") if _clean_field_label(part)]
        option_label = parts[-1] if parts else field_label
        context_parts = parts[:-1] if len(parts) > 1 else []
        context_tokens = {
            token
            for token in normalize_semantic_text(" ".join(context_parts)).replace("/", " ").replace("-", " ").split()
            if token and token not in _GENERIC_TOKENS and len(token) > 1
        }

        targets.append(
            {
                "field_key": field_key,
                "field_label": field_label,
                "template_scope": template_scope,
                "option_group": " | ".join(context_parts) if context_parts else field_label,
                "option_label": option_label,
                "option_label_normalized": normalize_semantic_text(option_label),
                "context_parts": context_parts,
                "context_tokens": context_tokens,
            }
        )
    return targets


def _parse_catalog_selected_phrase(
    selected_phrase: str,
    selected_option_labels: list[str] | None = None,
) -> tuple[list[str], list[str]]:
    parts = [_normalize_space(part) for part in str(selected_phrase or "").split("|") if _normalize_space(part)]
    selected_labels = [_normalize_space(label) for label in (selected_option_labels or []) if _normalize_space(label)]
    if selected_labels:
        selected_keys = {normalize_semantic_text(label) for label in selected_labels}
        context_parts = [part for part in parts if normalize_semantic_text(part) not in selected_keys]
        return context_parts, selected_labels

    if len(parts) <= 1:
        return parts, []

    return parts[:-1], parts[-1:]


def _score_target_match(
    *,
    context_parts: list[str],
    option_label: str,
    target: dict[str, Any],
) -> int:
    option_norm = normalize_semantic_text(option_label)
    target_option_norm = str(target.get("option_label_normalized", ""))
    if not option_norm or not target_option_norm:
        return 0

    score = 0
    if option_norm == target_option_norm:
        score += 8
    else:
        option_tokens = {
            token
            for token in option_norm.replace("/", " ").replace("-", " ").split()
            if token and token not in _GENERIC_TOKENS
        }
        target_tokens = {
            token
            for token in target_option_norm.replace("/", " ").replace("-", " ").split()
            if token and token not in _GENERIC_TOKENS
        }
        overlap = len(option_tokens & target_tokens)
        if overlap == 0:
            return 0
        score += overlap * 3

    context_tokens = {
        token
        for token in normalize_semantic_text(" ".join(context_parts)).replace("/", " ").replace("-", " ").split()
        if token and token not in _GENERIC_TOKENS and len(token) > 1
    }
    target_context_tokens = set(target.get("context_tokens", set()))
    overlap = len(context_tokens & target_context_tokens)
    if context_tokens:
        score += overlap * 2
        if overlap == 0:
            score -= 2

    if context_parts:
        context_text = normalize_semantic_text(" ".join(context_parts))
        option_text = normalize_semantic_text(option_label)
        target_label = normalize_semantic_text(str(target.get("field_label", "")))
        if context_text and context_text in target_label:
            score += 2
        if option_text and option_text in target_label:
            score += 1

    return score


def match_catalog_selected_phrase_to_targets(
    selected_phrase: str,
    selected_option_labels: list[str],
    schema_targets: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    context_parts, option_labels = _parse_catalog_selected_phrase(selected_phrase, selected_option_labels)
    matched_targets: list[dict[str, Any]] = []
    seen_keys: set[str] = set()

    for option_label in option_labels:
        scored: list[tuple[int, dict[str, Any]]] = []
        for target in schema_targets:
            score = _score_target_match(context_parts=context_parts, option_label=option_label, target=target)
            if score > 0:
                scored.append((score, target))

        if not scored:
            continue

        scored.sort(key=lambda item: (-item[0], str(item[1].get("field_key", ""))))
        best_score = scored[0][0]
        second_score = scored[1][0] if len(scored) > 1 else -999
        if best_score < 8:
            continue
        if second_score >= best_score:
            continue

        best_target = dict(scored[0][1])
        best_target["matched_option_label"] = option_label
        best_target["match_score"] = best_score
        field_key = str(best_target.get("field_key", ""))
        if not field_key or field_key in seen_keys:
            continue
        seen_keys.add(field_key)
        matched_targets.append(best_target)

    return matched_targets


def build_semantic_overrides_from_review_rows(rows: list[dict[str, str]]) -> dict[str, Any]:
    fields: dict[str, dict[str, Any]] = {}

    for row in rows:
        review_status = normalize_semantic_text(row.get("review_status", ""))
        if review_status not in {"approved", "yes", "true"}:
            continue

        field_key = _normalize_space(row.get("target_field_key", ""))
        if not field_key:
            continue

        field = fields.setdefault(
            field_key,
            {
                "template_scope": normalize_semantic_text(row.get("template_scope", "")) or "default",
                "machine_families": normalize_machine_family_scope(row.get("machine_families", "")),
                "option_group": _normalize_space(row.get("option_group", "")),
                "aliases": [],
                "positive_evidence": [],
                "negative_evidence": [],
                "related_terms": [],
                "notes": "",
                "review_status": "approved",
            },
        )

        field["aliases"] = _merge_prefer_first(
            _split_list_like(row.get("normalized_concept", "")),
            list(field.get("aliases", [])),
        )
        field["positive_evidence"] = _merge_prefer_first(
            _split_list_like(row.get("candidate_quote_phrase", "")) + _split_list_like(row.get("approved_mapping", "")),
            list(field.get("positive_evidence", [])),
        )
        field["related_terms"] = _merge_prefer_first(
            _split_list_like(row.get("selected_phrase", "")) + _split_list_like(row.get("goa_selected_labels", "")),
            list(field.get("related_terms", [])),
        )
        reviewer_notes = _normalize_space(row.get("reviewer_notes", ""))
        if reviewer_notes:
            existing_notes = _normalize_space(field.get("notes", ""))
            field["notes"] = f"{existing_notes} | {reviewer_notes}".strip(" |") if existing_notes else reviewer_notes

    ordered_fields = {
        key: {
            "template_scope": value.get("template_scope", "default"),
            "machine_families": list(value.get("machine_families", [])),
            "option_group": value.get("option_group", ""),
            "aliases": list(value.get("aliases", [])),
            "positive_evidence": list(value.get("positive_evidence", [])),
            "negative_evidence": list(value.get("negative_evidence", [])),
            "related_terms": list(value.get("related_terms", [])),
            "notes": value.get("notes", ""),
            "review_status": "approved",
        }
        for key, value in sorted(fields.items())
    }
    return {"fields": ordered_fields}


def build_semantic_overrides_from_review_csv(csv_path: str | Path) -> dict[str, Any]:
    path = Path(csv_path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    return build_semantic_overrides_from_review_rows(rows)


def build_semantic_overrides_from_review_csvs(csv_paths: list[str | Path]) -> dict[str, Any]:
    rows: list[dict[str, str]] = []
    for csv_path in csv_paths:
        path = Path(csv_path)
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            rows.extend(reader)
    return build_semantic_overrides_from_review_rows(rows)
