from __future__ import annotations

import copy
import csv
import json
import random
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from scripts.build_catalog_checkbox_review import extract_selected_checkbox_phrases
from src.utils import template_utils
from src.utils.form_generator import extract_schema_from_excel
from src.utils.goa_semantic_overrides import (
    build_schema_target_index,
    load_goa_field_semantic_overrides,
    match_catalog_selected_phrase_to_targets,
    normalize_runtime_machine_family,
    normalize_semantic_text,
)
from src.utils.machine_type import determine_machine_type, is_sortstar_machine
from src.utils.pdf_utils import identify_machines_from_items


DEFAULT_REVIEW_SAMPLE_COLUMNS = (
    "selected_sample_records",
    "candidate_sample_records",
)


@dataclass
class EvaluationRecord:
    quote_key: str
    goa_file: str
    goa_relative_path: str
    goa_path: str
    machine_name: str
    machine_family: str
    template_scope: str
    full_pdf_text: str
    machine_data: dict[str, Any]
    common_items: list[dict[str, Any]]
    applicable_field_keys: list[str]


def _normalize_checkbox_value(value: Any) -> str:
    return "YES" if str(value or "").strip().upper() == "YES" else "NO"


def _safe_ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 6)


def _template_scope_for_machine(machine_name: str) -> str:
    return "sortstar" if is_sortstar_machine(machine_name) else "default"


def _sortstar_template_path() -> Path | None:
    candidate_paths = [
        Path("templates") / "GOA_Sortstar_Temp.docx",
        Path("templates") / "goa_sortstar_temp.docx",
    ]
    return next((path for path in candidate_paths if path.exists()), None)


def load_template_contexts_for_machine(
    machine_name: str,
    *,
    semantic_overrides_path: str | Path | None = None,
) -> tuple[dict[str, dict[str, Any]], str, str]:
    machine_family = determine_machine_type(machine_name)
    template_scope = _template_scope_for_machine(machine_name)
    resolved_overrides_path = ""
    if semantic_overrides_path:
        resolved_overrides_path = str(Path(semantic_overrides_path).resolve())
    contexts, template_scope, machine_family = _load_template_contexts_for_machine_cached(
        machine_family,
        template_scope,
        resolved_overrides_path,
    )
    return copy.deepcopy(contexts), template_scope, machine_family


@lru_cache(maxsize=32)
def _load_template_contexts_for_machine_cached(
    machine_family: str,
    template_scope: str,
    semantic_overrides_path_str: str,
) -> tuple[dict[str, dict[str, Any]], str, str]:
    semantic_overrides_path = semantic_overrides_path_str or None

    if template_scope == "default":
        return (
            extract_schema_from_excel(
                machine_family=machine_family,
                semantic_overrides_path=semantic_overrides_path,
            ),
            template_scope,
            machine_family,
        )

    template_path = _sortstar_template_path()
    if template_path is None:
        return {}, template_scope, machine_family

    contexts = template_utils.extract_placeholder_schema(
        template_path=str(template_path),
        explicit_mappings=template_utils.SORTSTAR_EXPLICIT_MAPPINGS,
        is_sortstar=True,
        machine_family=machine_family,
        semantic_overrides_path=str(semantic_overrides_path) if semantic_overrides_path else None,
    )
    return contexts, template_scope, machine_family


def load_review_source_records(
    csv_paths: list[str | Path],
    *,
    sample_columns: tuple[str, ...] = DEFAULT_REVIEW_SAMPLE_COLUMNS,
) -> set[str]:
    reviewed_records: set[str] = set()

    for csv_path in csv_paths:
        path = Path(csv_path)
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                for column in sample_columns:
                    raw_value = str(row.get(column, ""))
                    for part in raw_value.split("|"):
                        sample = part.strip()
                        if not sample:
                            continue
                        if "::" in sample:
                            reviewed_records.add(sample.split("::", 1)[1].strip())
                        else:
                            reviewed_records.add(sample)

    return reviewed_records


def load_dataset_records(dataset_path: str | Path) -> list[dict[str, Any]]:
    payload = json.loads(Path(dataset_path).read_text(encoding="utf-8"))
    flattened: list[dict[str, Any]] = []

    for group in payload.get("quote_groups", []):
        for record in group.get("records", []):
            flattened.append(
                {
                    "quote_key": str(group.get("quote_key", "")),
                    "source_dir": str(payload.get("source_dir", "")),
                    "group": group,
                    "record": record,
                }
            )

    return flattened


def select_dataset_records(
    dataset_records: list[dict[str, Any]],
    *,
    excluded_goa_files: set[str] | None = None,
    selection_mode: str = "auto",
    min_strict_holdout: int = 4,
    max_records: int | None = None,
    seed: int = 7,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    excluded = {str(value).strip() for value in (excluded_goa_files or set()) if str(value).strip()}

    strict_holdout = [
        item
        for item in dataset_records
        if str(item["record"].get("file_name", "")).strip() not in excluded
    ]

    applied_mode = selection_mode
    warnings: list[str] = []

    if selection_mode == "auto":
        if len(strict_holdout) >= min_strict_holdout:
            selected = strict_holdout
            applied_mode = "strict_holdout"
        else:
            selected = list(dataset_records)
            applied_mode = "all_records_fallback"
            warnings.append(
                "Strict holdout has too few records after approval-source exclusion; "
                "falling back to all records for an in-sample audit."
            )
    elif selection_mode == "strict_holdout":
        selected = strict_holdout
        if len(strict_holdout) < min_strict_holdout:
            warnings.append(
                "Strict holdout has fewer records than the configured minimum; "
                "metrics may be noisy."
            )
    elif selection_mode == "all_records":
        selected = list(dataset_records)
    else:
        raise ValueError(f"Unsupported selection_mode: {selection_mode}")

    selected = list(selected)
    random.Random(seed).shuffle(selected)
    if isinstance(max_records, int) and max_records > 0:
        selected = selected[:max_records]

    metadata = {
        "mode_requested": selection_mode,
        "mode_applied": applied_mode,
        "dataset_record_count": len(dataset_records),
        "strict_holdout_record_count": len(strict_holdout),
        "selected_record_count": len(selected),
        "excluded_record_count": len(excluded),
        "warnings": warnings,
    }
    return selected, metadata


def _machine_candidate_score(record_machine_name: str, candidate: dict[str, Any]) -> int:
    candidate_name = str(candidate.get("machine_name", "")).strip()
    candidate_desc = str(candidate.get("main_item", {}).get("description", "")).strip()
    record_norm = normalize_semantic_text(record_machine_name)
    candidate_norm = normalize_semantic_text(candidate_name)
    candidate_desc_norm = normalize_semantic_text(candidate_desc)
    score = 0

    if record_norm and candidate_norm:
        if record_norm == candidate_norm:
            score += 12
        elif record_norm in candidate_norm or candidate_norm in record_norm:
            score += 8

    record_family = determine_machine_type(record_machine_name)
    candidate_family = determine_machine_type(candidate_name)
    if record_family == candidate_family and record_family:
        score += 5

    if record_norm and record_norm in candidate_desc_norm:
        score += 3

    return score


def resolve_machine_payload(
    record_machine_name: str,
    line_items: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    grouped = identify_machines_from_items(copy.deepcopy(line_items))
    candidates = list(grouped.get("machines", []))
    common_items = list(grouped.get("common_items", []))

    if candidates:
        ranked = sorted(
            candidates,
            key=lambda candidate: (
                -_machine_candidate_score(record_machine_name, candidate),
                normalize_semantic_text(candidate.get("machine_name", "")),
            ),
        )
        best = ranked[0]
        score = _machine_candidate_score(record_machine_name, best)
        if score > 0 or len(candidates) == 1:
            return best, common_items, {"match_mode": "identified_machine", "match_score": score}

    fallback_machine = {
        "machine_name": record_machine_name or "Unknown Machine",
        "main_item": line_items[0] if line_items else {"description": record_machine_name or "Unknown Machine"},
        "add_ons": line_items[1:] if len(line_items) > 1 else [],
    }
    return fallback_machine, common_items, {"match_mode": "fallback_combined_quote", "match_score": 0}


def applicable_override_fields_for_machine(
    overrides: dict[str, dict[str, Any]],
    *,
    template_scope: str,
    machine_family: str,
) -> list[str]:
    normalized_scope = normalize_semantic_text(template_scope) or "default"
    normalized_family = normalize_runtime_machine_family(machine_family)
    applicable: list[str] = []

    for field_key, entry in overrides.items():
        entry_scope = normalize_semantic_text(entry.get("template_scope", "")) or "default"
        if entry_scope != normalized_scope:
            continue
        allowed_families = [
            normalize_runtime_machine_family(value)
            for value in entry.get("machine_families", [])
            if str(value).strip()
        ]
        if allowed_families and normalized_family not in allowed_families:
            continue
        applicable.append(field_key)

    return sorted(applicable)


def build_truth_for_record(
    goa_path: str | Path,
    *,
    contexts: dict[str, dict[str, Any]],
    template_scope: str,
    approved_field_keys: list[str],
) -> tuple[dict[str, str], dict[str, list[str]], dict[str, Any]]:
    truth = {field_key: "NO" for field_key in approved_field_keys}
    evidence_by_field: dict[str, list[str]] = defaultdict(list)
    selected_rows = extract_selected_checkbox_phrases(Path(goa_path))
    schema_targets = build_schema_target_index(contexts, template_scope=template_scope)
    unmatched_rows = 0

    for selected in selected_rows:
        selected_phrase = str(selected.get("phrase", "")).strip()
        option_labels = [
            str(value).strip()
            for value in (
                selected.get("positive_selected_option_labels")
                or selected.get("selected_option_labels")
                or []
            )
            if str(value).strip()
        ]
        matched_targets = match_catalog_selected_phrase_to_targets(
            selected_phrase,
            option_labels,
            schema_targets,
        )

        matched_any = False
        for target in matched_targets:
            field_key = str(target.get("field_key", "")).strip()
            if field_key not in truth:
                continue
            truth[field_key] = "YES"
            if selected_phrase and selected_phrase not in evidence_by_field[field_key]:
                evidence_by_field[field_key].append(selected_phrase)
            matched_any = True

        if not matched_any:
            unmatched_rows += 1

    details = {
        "selected_checkbox_rows": len(selected_rows),
        "matched_truth_fields": sum(1 for value in truth.values() if value == "YES"),
        "unmatched_selected_rows": unmatched_rows,
    }
    return truth, dict(evidence_by_field), details


def build_evaluation_records(
    dataset_records: list[dict[str, Any]],
    *,
    overrides_path: str | Path,
) -> tuple[list[EvaluationRecord], dict[str, Any]]:
    overrides = load_goa_field_semantic_overrides(overrides_path)
    evaluation_records: list[EvaluationRecord] = []
    skipped_records: list[dict[str, str]] = []

    for item in dataset_records:
        group = item["group"]
        record = item["record"]
        source_dir = Path(str(item.get("source_dir", ".")) or ".")
        record_machine_name = str(record.get("machine", "")).strip()
        line_items: list[dict[str, Any]] = []
        full_pdf_parts: list[str] = []
        for pdf_document in group.get("pdf_documents", []):
            line_items.extend(list(pdf_document.get("line_items", [])))
            page_text = str(pdf_document.get("page_text", "")).strip()
            if page_text:
                full_pdf_parts.append(page_text)

        machine_data, common_items, _match_details = resolve_machine_payload(record_machine_name, line_items)
        contexts, template_scope, machine_family = load_template_contexts_for_machine(
            record_machine_name,
            semantic_overrides_path=overrides_path,
        )
        approved_field_keys = applicable_override_fields_for_machine(
            overrides,
            template_scope=template_scope,
            machine_family=machine_family,
        )

        if not contexts or not approved_field_keys:
            skipped_records.append(
                {
                    "goa_file": str(record.get("file_name", "")),
                    "reason": "missing_contexts_or_applicable_fields",
                }
            )
            continue

        goa_relative_path = str(record.get("relative_path", "")).strip()
        goa_file = str(record.get("file_name", "")).strip()
        goa_path = source_dir / goa_relative_path if goa_relative_path else source_dir / goa_file
        evaluation_records.append(
            EvaluationRecord(
                quote_key=str(group.get("quote_key", "")),
                goa_file=goa_file,
                goa_relative_path=str(goa_relative_path),
                goa_path=str(goa_path),
                machine_name=record_machine_name or str(machine_data.get("machine_name", "")),
                machine_family=machine_family,
                template_scope=template_scope,
                full_pdf_text="\n".join(full_pdf_parts).strip(),
                machine_data=machine_data,
                common_items=common_items,
                applicable_field_keys=approved_field_keys,
            )
        )

    metadata = {
        "prepared_record_count": len(evaluation_records),
        "skipped_records": skipped_records,
    }
    return evaluation_records, metadata


def build_field_metadata(
    field_keys: list[str],
    *,
    contexts: dict[str, dict[str, Any]],
    overrides: dict[str, dict[str, Any]],
    template_scope: str,
) -> dict[str, dict[str, str]]:
    metadata: dict[str, dict[str, str]] = {}

    for field_key in field_keys:
        context = contexts.get(field_key, {})
        override = overrides.get(field_key, {})
        description = str(context.get("description", field_key)).strip() if isinstance(context, dict) else field_key
        option_group = str(override.get("option_group", "")).strip()
        if not option_group and isinstance(context, dict):
            option_group = str(context.get("option_group", "")).strip()
        metadata[field_key] = {
            "field_label": description,
            "option_group": option_group,
            "template_scope": template_scope,
        }

    return metadata


def evaluate_field_predictions(
    truth: dict[str, str],
    predicted: dict[str, Any],
    *,
    field_metadata: dict[str, dict[str, str]],
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    metrics = {
        "fields_evaluated": len(truth),
        "actual_yes": 0,
        "predicted_yes": 0,
        "tp": 0,
        "fp": 0,
        "fn": 0,
        "tn": 0,
        "option_groups_with_truth_yes": 0,
        "wrong_option_groups": 0,
    }
    per_field: dict[str, dict[str, Any]] = {}

    option_groups: dict[str, dict[str, set[str]]] = defaultdict(lambda: {"truth_yes": set(), "predicted_yes": set()})

    for field_key, truth_value in truth.items():
        normalized_truth = _normalize_checkbox_value(truth_value)
        normalized_predicted = _normalize_checkbox_value(predicted.get(field_key, "NO"))
        metadata = field_metadata.get(field_key, {})
        option_group = str(metadata.get("option_group", "")).strip()

        if normalized_truth == "YES":
            metrics["actual_yes"] += 1
            if option_group:
                option_groups[option_group]["truth_yes"].add(field_key)

        if normalized_predicted == "YES":
            metrics["predicted_yes"] += 1
            if option_group:
                option_groups[option_group]["predicted_yes"].add(field_key)

        if normalized_truth == "YES" and normalized_predicted == "YES":
            outcome = "tp"
            metrics["tp"] += 1
        elif normalized_truth == "NO" and normalized_predicted == "YES":
            outcome = "fp"
            metrics["fp"] += 1
        elif normalized_truth == "YES" and normalized_predicted == "NO":
            outcome = "fn"
            metrics["fn"] += 1
        else:
            outcome = "tn"
            metrics["tn"] += 1

        per_field[field_key] = {
            "truth": normalized_truth,
            "predicted": normalized_predicted,
            "outcome": outcome,
        }

    for group_data in option_groups.values():
        truth_yes = group_data["truth_yes"]
        predicted_yes = group_data["predicted_yes"]
        if not truth_yes:
            continue
        metrics["option_groups_with_truth_yes"] += 1
        if predicted_yes and truth_yes.isdisjoint(predicted_yes):
            metrics["wrong_option_groups"] += 1

    metrics["precision"] = _safe_ratio(metrics["tp"], metrics["predicted_yes"])
    metrics["recall"] = _safe_ratio(metrics["tp"], metrics["actual_yes"])
    metrics["false_no_rate"] = _safe_ratio(metrics["fn"], metrics["actual_yes"])
    metrics["wrong_option_rate"] = _safe_ratio(
        metrics["wrong_option_groups"],
        metrics["option_groups_with_truth_yes"],
    )
    return metrics, per_field


def aggregate_field_metrics(
    record_results: list[dict[str, Any]],
    *,
    run_keys: tuple[str, ...] = ("baseline", "overrides"),
) -> list[dict[str, Any]]:
    aggregates: dict[str, dict[str, Any]] = {}

    for record_result in record_results:
        record_field_metadata = record_result.get("field_metadata", {})
        truth = record_result.get("truth", {})
        per_run_field_results = record_result.get("per_run_field_results", {})

        for field_key, truth_value in truth.items():
            aggregate = aggregates.setdefault(
                field_key,
                {
                    "field_key": field_key,
                    "field_label": str(record_field_metadata.get(field_key, {}).get("field_label", "")),
                    "option_group": str(record_field_metadata.get(field_key, {}).get("option_group", "")),
                    "template_scope": str(record_field_metadata.get(field_key, {}).get("template_scope", "")),
                    "machine_families": set(),
                    "truth_yes_count": 0,
                    "record_count": 0,
                },
            )
            aggregate["record_count"] += 1
            aggregate["machine_families"].add(str(record_result.get("machine_family", "")))
            if _normalize_checkbox_value(truth_value) == "YES":
                aggregate["truth_yes_count"] += 1

            for run_key in run_keys:
                prefix = f"{run_key}_"
                aggregate.setdefault(f"{prefix}predicted_yes_count", 0)
                aggregate.setdefault(f"{prefix}tp", 0)
                aggregate.setdefault(f"{prefix}fp", 0)
                aggregate.setdefault(f"{prefix}fn", 0)

                field_outcome = (
                    per_run_field_results.get(run_key, {})
                    .get(field_key, {})
                )
                predicted_value = _normalize_checkbox_value(field_outcome.get("predicted", "NO"))
                outcome = str(field_outcome.get("outcome", "tn")).strip().lower()
                if predicted_value == "YES":
                    aggregate[f"{prefix}predicted_yes_count"] += 1
                if outcome in {"tp", "fp", "fn"}:
                    aggregate[f"{prefix}{outcome}"] += 1

    rows: list[dict[str, Any]] = []
    for field_key, aggregate in sorted(aggregates.items()):
        row = {
            "field_key": field_key,
            "field_label": aggregate["field_label"],
            "option_group": aggregate["option_group"],
            "template_scope": aggregate["template_scope"],
            "machine_families": ", ".join(sorted(value for value in aggregate["machine_families"] if value)),
            "record_count": aggregate["record_count"],
            "truth_yes_count": aggregate["truth_yes_count"],
        }
        for run_key in run_keys:
            prefix = f"{run_key}_"
            tp = int(aggregate.get(f"{prefix}tp", 0))
            fp = int(aggregate.get(f"{prefix}fp", 0))
            fn = int(aggregate.get(f"{prefix}fn", 0))
            predicted_yes = int(aggregate.get(f"{prefix}predicted_yes_count", 0))
            row[f"{prefix}predicted_yes_count"] = predicted_yes
            row[f"{prefix}tp"] = tp
            row[f"{prefix}fp"] = fp
            row[f"{prefix}fn"] = fn
            row[f"{prefix}precision"] = _safe_ratio(tp, predicted_yes)
            row[f"{prefix}recall"] = _safe_ratio(tp, int(aggregate["truth_yes_count"]))
        baseline_recall = row.get("baseline_recall")
        overrides_recall = row.get("overrides_recall")
        baseline_precision = row.get("baseline_precision")
        overrides_precision = row.get("overrides_precision")
        row["delta_recall"] = (
            round(float(overrides_recall) - float(baseline_recall), 6)
            if baseline_recall is not None and overrides_recall is not None
            else None
        )
        row["delta_precision"] = (
            round(float(overrides_precision) - float(baseline_precision), 6)
            if baseline_precision is not None and overrides_precision is not None
            else None
        )
        rows.append(row)
    return rows


def aggregate_run_metrics(record_results: list[dict[str, Any]], run_key: str) -> dict[str, Any]:
    total = {
        "records_evaluated": len(record_results),
        "fields_evaluated": 0,
        "actual_yes": 0,
        "predicted_yes": 0,
        "tp": 0,
        "fp": 0,
        "fn": 0,
        "tn": 0,
        "option_groups_with_truth_yes": 0,
        "wrong_option_groups": 0,
    }

    for record_result in record_results:
        metrics = record_result.get("metrics_by_run", {}).get(run_key, {})
        for key in total:
            if key == "records_evaluated":
                continue
            total[key] += int(metrics.get(key, 0) or 0)

    total["precision"] = _safe_ratio(total["tp"], total["predicted_yes"])
    total["recall"] = _safe_ratio(total["tp"], total["actual_yes"])
    total["false_no_rate"] = _safe_ratio(total["fn"], total["actual_yes"])
    total["wrong_option_rate"] = _safe_ratio(
        total["wrong_option_groups"],
        total["option_groups_with_truth_yes"],
    )
    return total


def build_example_rows(record_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for record_result in record_results:
        field_metadata = record_result.get("field_metadata", {})
        truth = record_result.get("truth", {})
        evidence = record_result.get("truth_evidence", {})
        baseline_field_results = record_result.get("per_run_field_results", {}).get("baseline", {})
        override_field_results = record_result.get("per_run_field_results", {}).get("overrides", {})

        for field_key in sorted(truth):
            truth_value = _normalize_checkbox_value(truth.get(field_key, "NO"))
            baseline_predicted = _normalize_checkbox_value(
                baseline_field_results.get(field_key, {}).get("predicted", "NO")
            )
            override_predicted = _normalize_checkbox_value(
                override_field_results.get(field_key, {}).get("predicted", "NO")
            )
            baseline_outcome = str(baseline_field_results.get(field_key, {}).get("outcome", "tn")).strip()
            override_outcome = str(override_field_results.get(field_key, {}).get("outcome", "tn")).strip()
            changed = baseline_predicted != override_predicted
            any_error = baseline_outcome in {"fp", "fn"} or override_outcome in {"fp", "fn"}

            if not changed and not any_error:
                continue

            metadata = field_metadata.get(field_key, {})
            rows.append(
                {
                    "quote_key": record_result.get("quote_key", ""),
                    "goa_file": record_result.get("goa_file", ""),
                    "machine_name": record_result.get("machine_name", ""),
                    "machine_family": record_result.get("machine_family", ""),
                    "template_scope": metadata.get("template_scope", ""),
                    "field_key": field_key,
                    "field_label": metadata.get("field_label", ""),
                    "option_group": metadata.get("option_group", ""),
                    "truth_value": truth_value,
                    "baseline_value": baseline_predicted,
                    "baseline_outcome": baseline_outcome,
                    "override_value": override_predicted,
                    "override_outcome": override_outcome,
                    "truth_evidence": " || ".join(evidence.get(field_key, [])),
                    "changed_with_overrides": "yes" if changed else "no",
                }
            )

    return rows
