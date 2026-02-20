"""Pure backend services extracted from Streamlit processing workflows."""

from __future__ import annotations

import json
import os
import re
import sqlite3
import tempfile
import time
from pathlib import Path
from typing import Any

from src.utils import template_utils
from src.utils.db import (
    DB_PATH,
    find_machines_by_name,
    get_client_by_id,
    load_document_content,
    load_machines_for_quote,
    load_priced_items_for_quote,
    save_client_info,
    save_document_content,
    save_machine_template_data,
    save_machines_data,
    save_priced_items,
)
from src.utils.doc_filler import fill_word_document_from_llm_data
from src.utils.form_generator import OUTPUT_HTML_PATH, extract_schema_from_excel, generate_goa_form
from src.utils.html_doc_filler import fill_and_generate_html
from src.llm import (
    ExtractionPassOptions,
    apply_post_processing_rules,
    configure_gemini_client,
    estimate_extraction_confidence,
    extract_machine_fields_with_options,
    get_machine_specific_fields_with_confidence,
    resolve_critical_text_fields,
    sanitize_extracted_fields,
    select_repair_field_contexts,
    validate_field_dependencies,
)
from src.utils.machine_type import is_sortstar_machine
from src.utils.pdf_utils import extract_full_pdf_text, extract_line_item_details, identify_machines_from_items

DEFAULT_TEMPLATE_FILE = os.path.join("templates", "template.docx")
SORTSTAR_TEMPLATE_CANDIDATES = (
    os.path.join("templates", "GOA_Sortstar_Temp.docx"),
    os.path.join("templates", "goa_sortstar_temp.docx"),
)


def _resolve_existing_template_path(candidates: tuple[str, ...]) -> str:
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return candidates[0]


SORTSTAR_TEMPLATE_FILE = _resolve_existing_template_path(SORTSTAR_TEMPLATE_CANDIDATES)


def _env_flag(name: str, default: bool = False) -> bool:
    raw = str(os.getenv(name, "")).strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _env_positive_int(name: str, default: int, *, min_value: int = 1) -> int:
    raw = str(os.getenv(name, "")).strip()
    if not raw:
        return default
    try:
        parsed = int(raw)
    except ValueError:
        return default
    return max(min_value, parsed)


def _env_csv(name: str, default: list[str]) -> list[str]:
    raw = str(os.getenv(name, "")).strip()
    if not raw:
        return list(default)
    values = [value.strip() for value in raw.split(",")]
    cleaned = [value for value in values if value]
    return cleaned or list(default)


def _template_config(machine_name: str) -> dict[str, Any]:
    is_sortstar = is_sortstar_machine(machine_name)
    if is_sortstar:
        return {
            "template_file": SORTSTAR_TEMPLATE_FILE,
            "explicit_mappings": template_utils.SORTSTAR_EXPLICIT_MAPPINGS,
            "outline_file": "sortstar_fields_outline.md",
            "is_sortstar": True,
        }
    return {
        "template_file": DEFAULT_TEMPLATE_FILE,
        "explicit_mappings": template_utils.DEFAULT_EXPLICIT_MAPPINGS,
        "outline_file": "full_fields_outline.md",
        "is_sortstar": False,
    }


_CONTACT_TITLE_KEYWORDS = (
    "engineer",
    "manager",
    "coordinator",
    "president",
    "specialist",
    "director",
    "buyer",
    "purchasing",
    "project",
    "operations",
)


def _clean_profile_line(value: str) -> str:
    cleaned = re.sub(r"^[\s:•\-\uf02d]+", "", value or "").strip()
    return re.sub(r"\s+", " ", cleaned)


def _is_title_line(value: str) -> bool:
    lowered = value.lower()
    return any(keyword in lowered for keyword in _CONTACT_TITLE_KEYWORDS)


def _is_phone_line(value: str) -> bool:
    return bool(re.search(r"\+?\s*\d[\d()\s.\-]{6,}\d", value))


def _extract_phone(value: str) -> str:
    match = re.search(r"(\+?\s*\d[\d()\s.\-]{6,}\d)", value)
    if not match:
        return ""
    return re.sub(r"\s+", " ", match.group(1)).strip()


def _extract_email(value: str) -> str:
    match = re.search(r"([A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,})", value, flags=re.IGNORECASE)
    if not match:
        return ""
    return match.group(1).strip()


def _is_contact_candidate(section_lines: list[str], index: int) -> bool:
    line = section_lines[index]
    if not line or _is_phone_line(line) or "@" in line or any(char.isdigit() for char in line):
        return False

    words = re.findall(r"[A-Za-z][A-Za-z'`.\-]*", line)
    if len(words) < 2 or len(words) > 4:
        return False

    next_line = section_lines[index + 1].lower() if index + 1 < len(section_lines) else ""
    if not next_line:
        return False
    if _is_title_line(next_line):
        return True
    if _is_phone_line(next_line) or "@" in next_line:
        return True
    return False


def _normalize_company_name(raw: str) -> str:
    text = _clean_profile_line(raw)
    if not text:
        return ""

    text = text.split("|", 1)[0].split("/", 1)[0].strip()
    base = text.split(",", 1)[0].strip()
    tokens = base.split()
    if not tokens:
        return text

    suffixes = {
        "inc",
        "inc.",
        "ltd",
        "ltd.",
        "llc",
        "corp",
        "corp.",
        "corporation",
        "co",
        "co.",
        "company",
        "laboratories",
        "laboratory",
        "labs",
    }
    kept: list[str] = []
    for token in tokens:
        normalized = token.lower().strip(".")
        if kept and normalized in suffixes:
            break
        kept.append(token)

    normalized_name = " ".join(kept) if kept else tokens[0]
    return normalized_name.title() if normalized_name.isupper() else normalized_name


def _extract_quote_profile_fields(full_text: str, fallback_quote_ref: str) -> dict[str, str]:
    if not full_text:
        return {
            "quote_ref": fallback_quote_ref,
            "company": "",
            "customer_name": "",
            "sold_to_address": "",
            "telephone": "",
            "order_date": "",
            "customer_contact_person": "",
        }

    quote_ref = fallback_quote_ref
    quote_patterns = (
        r"\bQuotation#\s*([^\n\r]+)",
        r"\bQuote Reference:\s*([^\n\r]+)",
    )
    for pattern in quote_patterns:
        match = re.search(pattern, full_text, flags=re.IGNORECASE)
        if not match:
            continue
        candidate = _clean_profile_line(match.group(1))
        candidate = re.sub(r"\.(docx?|pdf)$", "", candidate, flags=re.IGNORECASE).strip()
        if candidate:
            quote_ref = candidate
            break

    order_date = ""
    order_date_match = re.search(r"\bDate:\s*([^\n\r]+)", full_text, flags=re.IGNORECASE)
    if order_date_match:
        order_date = _clean_profile_line(order_date_match.group(1))

    lines_raw = full_text.splitlines()[:260]
    lines = [_clean_profile_line(line) for line in lines_raw if _clean_profile_line(line)]
    presented_index = next(
        (idx for idx, line in enumerate(lines) if line.lower().startswith("presented to")),
        None,
    )
    section_lines = lines[presented_index + 1 : presented_index + 26] if presented_index is not None else []

    customer_name = ""
    company = ""
    sold_to_address = ""
    telephone = ""
    contact_person = ""
    client_contact_email = ""

    if section_lines:
        company_idx = None
        for idx, line in enumerate(section_lines):
            lowered = line.lower()
            if _is_phone_line(line) or "@" in line or lowered.startswith("www."):
                continue
            customer_name = _normalize_company_name(line)
            company_idx = idx
            break

        start_idx = (company_idx + 1) if company_idx is not None else 0
        address_lines: list[str] = []
        for idx in range(start_idx, len(section_lines)):
            line = section_lines[idx]
            lowered = line.lower()
            if _is_phone_line(line):
                if not telephone:
                    telephone = _extract_phone(line)
                continue
            if "@" in line:
                if not client_contact_email:
                    client_contact_email = _extract_email(line)
                continue
            if lowered.startswith("www.") or lowered.endswith(".com"):
                continue
            if not contact_person and _is_contact_candidate(section_lines, idx):
                contact_person = line
                continue
            if contact_person:
                continue
            if _is_title_line(line):
                continue
            address_lines.append(line)

        sold_to_address = "\n".join(address_lines).strip()

        if not contact_person:
            for idx in range(start_idx, len(section_lines)):
                if _is_contact_candidate(section_lines, idx):
                    contact_person = section_lines[idx]
                    break
        if not telephone:
            for line in section_lines:
                phone = _extract_phone(line)
                if phone:
                    telephone = phone
                    break
        if not client_contact_email:
            for line in section_lines:
                email = _extract_email(line)
                if email:
                    client_contact_email = email
                    break

    contact_person = _clean_profile_line(contact_person)
    company = contact_person

    return {
        "quote_ref": quote_ref,
        "company": company,
        "customer_name": customer_name,
        "sold_to_address": sold_to_address,
        "telephone": telephone,
        "order_date": order_date,
        "customer_contact_person": client_contact_email,
    }


def extract_and_catalog(
    pdf_bytes: bytes, filename: str, existing_client_id: int | None = None
) -> dict[str, Any]:
    """Extract quote data from PDF and persist it to CRM tables."""
    temp_pdf_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            tmp_file.write(pdf_bytes)
            temp_pdf_path = tmp_file.name

        items = extract_line_item_details(temp_pdf_path)
        full_text = extract_full_pdf_text(temp_pdf_path)
        if not items:
            raise ValueError("No line items were extracted from the uploaded PDF.")

        quote_ref = Path(filename).stem
        machine_model_guess = ""
        identified = identify_machines_from_items(items)
        if identified.get("machines"):
            machine_model_guess = identified["machines"][0].get("machine_name", "")
        extracted_profile = _extract_quote_profile_fields(full_text, quote_ref)

        client_info: dict[str, Any] = {
            "quote_ref": extracted_profile.get("quote_ref") or quote_ref,
            "customer_name": extracted_profile.get("customer_name", ""),
            "machine_model": machine_model_guess,
            "country_destination": "",
            "sold_to_address": extracted_profile.get("sold_to_address", ""),
            "ship_to_address": "",
            "telephone": extracted_profile.get("telephone", ""),
            "customer_contact_person": extracted_profile.get("customer_contact_person", ""),
            "customer_po": "",
            "order_date": extracted_profile.get("order_date", ""),
            "company": extracted_profile.get("company", ""),
        }

        linked_existing_client_id: int | None = None
        if existing_client_id:
            existing_client = get_client_by_id(existing_client_id)
            if existing_client:
                linked_existing_client_id = existing_client_id
                client_info = dict(existing_client)
                client_info["quote_ref"] = f"{existing_client['quote_ref']}_{quote_ref}"

        if not save_client_info(client_info):
            raise RuntimeError(f"Failed to save client record for quote_ref '{client_info['quote_ref']}'.")
        if not save_priced_items(client_info["quote_ref"], items):
            raise RuntimeError(f"Failed to save priced items for quote_ref '{client_info['quote_ref']}'.")
        if full_text and not save_document_content(client_info["quote_ref"], full_text, filename):
            raise RuntimeError(f"Failed to save document content for quote_ref '{client_info['quote_ref']}'.")
        if not save_machines_data(client_info["quote_ref"], identified):
            raise RuntimeError(f"Failed to save machine data for quote_ref '{client_info['quote_ref']}'.")

        return {
            "quote_ref": client_info["quote_ref"],
            "items": items,
            "items_count": len(items),
            "linked_existing_client_id": linked_existing_client_id,
        }
    finally:
        if temp_pdf_path and os.path.exists(temp_pdf_path):
            os.remove(temp_pdf_path)


def get_contexts_for_machine(machine_record: dict[str, Any]) -> tuple[dict[str, Any], str, bool]:
    """Resolve template schema/contexts for machine extraction and generation."""
    config = _template_config(machine_record.get("machine_name", ""))
    template_file = config["template_file"]

    if not config["is_sortstar"]:
        contexts = extract_schema_from_excel()
        return contexts or {}, template_file, False

    if not os.path.exists(template_file):
        return {}, template_file, True

    try:
        contexts = template_utils.extract_placeholder_schema(
            template_path=template_file,
            explicit_mappings=config["explicit_mappings"],
            is_sortstar=True,
        )
        if contexts:
            return contexts, template_file, True
    except Exception:
        pass

    try:
        contexts = template_utils.extract_placeholder_context_hierarchical(
            template_path=template_file,
            explicit_placeholder_mappings=config["explicit_mappings"],
            enhance_with_outline=os.path.exists(config["outline_file"]),
            outline_path=config["outline_file"],
            is_sortstar=True,
        )
        if contexts:
            return contexts, template_file, True
    except Exception:
        pass

    placeholders = template_utils.extract_placeholders(template_file)
    return {key: key for key in placeholders}, template_file, True


def run_extraction(
    machine_data: dict[str, Any],
    common_items: list[dict[str, Any]],
    template_contexts: dict[str, Any] | None,
    full_pdf_text: str,
) -> dict[str, Any]:
    """Run extraction via V2 two-pass pipeline or legacy fallback."""
    if _env_flag("EXTRACTION_FULL_PREFILL_V2_ENABLED", default=False):
        return run_extraction_v2_full_prefill(
            machine_data=machine_data,
            common_items=common_items,
            template_contexts=template_contexts,
            full_pdf_text=full_pdf_text,
        )
    return _run_extraction_legacy(
        machine_data=machine_data,
        common_items=common_items,
        template_contexts=template_contexts,
        full_pdf_text=full_pdf_text,
    )


def _run_extraction_legacy(
    machine_data: dict[str, Any],
    common_items: list[dict[str, Any]],
    template_contexts: dict[str, Any] | None,
    full_pdf_text: str,
) -> dict[str, Any]:
    if not configure_gemini_client():
        raise RuntimeError("Gemini client configuration failed.")

    contexts = template_contexts or {}
    if not contexts:
        contexts, _, _ = get_contexts_for_machine(machine_data)
    if not contexts:
        raise RuntimeError("No template contexts could be loaded for machine extraction.")

    effective_common_items = common_items or machine_data.get("common_items", []) or []
    filled_data, confidence_scores, suggestions = get_machine_specific_fields_with_confidence(
        machine_data,
        effective_common_items,
        contexts,
        full_pdf_text,
    )
    return {
        "filled_data": filled_data,
        "confidence_scores": confidence_scores,
        "suggestions": suggestions,
        "metadata": {
            "pipeline_version": "legacy_v1",
            "fields_total": len(contexts),
            "fields_pass1_attempted": len(contexts),
            "fields_pass2_attempted": 0,
            "fields_filled_final": sum(1 for value in filled_data.values() if str(value).strip().upper() not in {"", "NO"}),
            "low_confidence_count": sum(1 for value in confidence_scores.values() if float(value) < 0.6),
            "timing_ms": {"pass1": None, "pass2": 0, "total": None},
            "prompt_chars_estimate": {"pass1": None, "pass2": 0, "total": None},
            "critical_text_forced_pass2_count": 0,
            "critical_text_overrides_applied": 0,
            "critical_text_no_evidence_blanked": 0,
            "critical_text_targets": [],
        },
    }


def _build_selected_pdf_descriptions(
    machine_data: dict[str, Any],
    common_items: list[dict[str, Any]],
) -> list[str]:
    selected_descriptions: list[str] = []
    main_item_desc = machine_data.get("main_item", {}).get("description", "")
    if main_item_desc:
        selected_descriptions.append(main_item_desc)
    selected_descriptions.extend(
        item.get("description", "")
        for item in machine_data.get("add_ons", []) or []
        if item.get("description")
    )
    selected_descriptions.extend(
        item.get("description", "")
        for item in common_items
        if item.get("description")
    )
    return selected_descriptions


def run_extraction_v2_full_prefill(
    machine_data: dict[str, Any],
    common_items: list[dict[str, Any]],
    template_contexts: dict[str, Any] | None,
    full_pdf_text: str,
) -> dict[str, Any]:
    """Two-pass full-template prefill (fast pass + auto-repair pass)."""
    if not configure_gemini_client():
        raise RuntimeError("Gemini client configuration failed.")

    contexts = template_contexts or {}
    if not contexts:
        contexts, _, _ = get_contexts_for_machine(machine_data)
    if not contexts:
        raise RuntimeError("No template contexts could be loaded for machine extraction.")

    effective_common_items = common_items or machine_data.get("common_items", []) or []
    total_start = time.time()
    weighted_hints_enabled = _env_flag("LLM_RAG_WEIGHTED_HINTS_ENABLED", default=True)
    force_critical_pass2 = _env_flag("LLM_FORCE_PASS2_CRITICAL_TEXT", default=True)
    critical_text_targets = _env_csv(
        "LLM_CRITICAL_TEXT_TAGS",
        ["direction", "voltage", "hz", "phases"],
    )
    resolver_enabled = _env_flag("LLM_CRITICAL_TEXT_RESOLVER_ENABLED", default=True)

    pass1_model = os.getenv("GOA_LLM_MODEL_DRAFT", "gemini-2.5-flash-lite")
    pass2_model = os.getenv("GOA_LLM_MODEL_DEEP", "gemini-2.5-flash")
    pass1_options = ExtractionPassOptions(
        pass_name="pass1_fast_prefill",
        model_name=pass1_model,
        rag_max_chars=_env_positive_int("LLM_PASS1_RAG_MAX_CHARS", 12000, min_value=4000),
        max_fields_per_group=_env_positive_int("LLM_PASS1_GROUP_MAX_FIELDS", 60, min_value=20),
        enable_few_shot=False,
        enable_quote_library=False,
        compact_prompt=True,
        concurrency=_env_positive_int("LLM_EXTRACTION_MAX_CONCURRENCY", 3, min_value=1),
        max_examples_per_field=0,
        max_checkbox_synonyms=2,
        max_checkbox_indicators=1,
        use_weighted_rag=weighted_hints_enabled,
    )
    pass2_options = ExtractionPassOptions(
        pass_name="pass2_auto_repair",
        model_name=pass2_model,
        rag_max_chars=_env_positive_int("LLM_PASS2_RAG_MAX_CHARS", 22000, min_value=6000),
        max_fields_per_group=_env_positive_int("LLM_PASS2_GROUP_MAX_FIELDS", 35, min_value=10),
        enable_few_shot=True,
        enable_quote_library=True,
        compact_prompt=True,
        concurrency=_env_positive_int("LLM_EXTRACTION_MAX_CONCURRENCY", 3, min_value=1),
        max_examples_per_field=1,
        max_checkbox_synonyms=3,
        max_checkbox_indicators=2,
        use_weighted_rag=weighted_hints_enabled,
    )

    pass1_data, pass1_metrics = extract_machine_fields_with_options(
        machine_data=machine_data,
        common_items=effective_common_items,
        template_placeholder_contexts=contexts,
        full_pdf_text=full_pdf_text,
        pass_options=pass1_options,
    )

    pass1_confidence = estimate_extraction_confidence(
        extracted_data=pass1_data,
        template_contexts=contexts,
        full_pdf_text=full_pdf_text,
        machine_data=machine_data,
        common_items=effective_common_items,
    )
    _, pass1_conf_validated, dependency_suggestions = validate_field_dependencies(
        extracted_data=pass1_data,
        confidence_scores=pass1_confidence,
    )
    baseline_repair_contexts = select_repair_field_contexts(
        extracted_data=pass1_data,
        confidence_scores=pass1_conf_validated,
        template_placeholder_contexts=contexts,
        text_confidence_threshold=0.72,
        checkbox_yes_confidence_threshold=0.80,
        dependency_suggestions=dependency_suggestions,
    )
    repair_contexts = baseline_repair_contexts
    if force_critical_pass2:
        repair_contexts = select_repair_field_contexts(
            extracted_data=pass1_data,
            confidence_scores=pass1_conf_validated,
            template_placeholder_contexts=contexts,
            text_confidence_threshold=0.72,
            checkbox_yes_confidence_threshold=0.80,
            dependency_suggestions=dependency_suggestions,
            force_critical_text_fields=True,
            forced_semantic_tags=critical_text_targets,
        )
    forced_pass2_fields = set(repair_contexts.keys()) - set(baseline_repair_contexts.keys())

    pass2_data: dict[str, str] = {}
    pass2_metrics: dict[str, Any] = {
        "duration_ms": 0,
        "prompt_chars_estimate": 0,
        "fields_attempted": 0,
        "groups_processed": 0,
        "model_name": pass2_model,
    }
    if repair_contexts:
        pass2_data, pass2_metrics = extract_machine_fields_with_options(
            machine_data=machine_data,
            common_items=effective_common_items,
            template_placeholder_contexts=repair_contexts,
            full_pdf_text=full_pdf_text,
            pass_options=pass2_options,
        )

    merged_data = dict(pass1_data)
    merged_data.update(pass2_data)

    selected_pdf_descriptions = _build_selected_pdf_descriptions(machine_data, effective_common_items)
    post_processed_data = apply_post_processing_rules(
        merged_data,
        contexts,
        full_pdf_text,
        selected_pdf_descriptions,
    )
    resolver_metrics: dict[str, Any] = {
        "critical_text_overrides_applied": 0,
        "critical_text_no_evidence_blanked": 0,
    }
    resolved_data = post_processed_data
    if resolver_enabled:
        resolved_data, resolver_metrics = resolve_critical_text_fields(
            extracted_data=post_processed_data,
            template_contexts=contexts,
            full_pdf_text=full_pdf_text,
            target_tags=critical_text_targets,
            blank_direction_without_evidence=True,
        )
    sanitized_data, schema_notes = sanitize_extracted_fields(
        extracted_data=resolved_data,
        expected_schema=contexts,
    )
    final_confidence = estimate_extraction_confidence(
        extracted_data=sanitized_data,
        template_contexts=contexts,
        full_pdf_text=full_pdf_text,
        machine_data=machine_data,
        common_items=effective_common_items,
    )
    final_data, final_confidence, final_suggestions = validate_field_dependencies(
        extracted_data=sanitized_data,
        confidence_scores=final_confidence,
    )

    if schema_notes:
        for field_name, notes in schema_notes.items():
            final_suggestions.append(
                {
                    "field": field_name,
                    "reason": "; ".join(notes),
                    "type": "info",
                }
            )

    total_ms = int((time.time() - total_start) * 1000)
    fields_filled_final = sum(
        1 for value in final_data.values() if str(value).strip().upper() not in {"", "NO"}
    )
    low_confidence_count = sum(1 for value in final_confidence.values() if float(value) < 0.6)
    metadata = {
        "pipeline_version": "v2_full_prefill",
        "pass1_model": pass1_metrics.get("model_name", pass1_model),
        "pass2_model": pass2_metrics.get("model_name", pass2_model),
        "fields_total": len(contexts),
        "fields_pass1_attempted": pass1_metrics.get("fields_attempted", len(contexts)),
        "fields_pass2_attempted": pass2_metrics.get("fields_attempted", len(repair_contexts)),
        "fields_filled_final": fields_filled_final,
        "low_confidence_count": low_confidence_count,
        "timing_ms": {
            "pass1": pass1_metrics.get("duration_ms", 0),
            "pass2": pass2_metrics.get("duration_ms", 0),
            "total": total_ms,
        },
        "prompt_chars_estimate": {
            "pass1": pass1_metrics.get("prompt_chars_estimate", 0),
            "pass2": pass2_metrics.get("prompt_chars_estimate", 0),
            "total": int(pass1_metrics.get("prompt_chars_estimate", 0))
            + int(pass2_metrics.get("prompt_chars_estimate", 0)),
        },
        "critical_text_forced_pass2_count": len(forced_pass2_fields),
        "critical_text_overrides_applied": int(resolver_metrics.get("critical_text_overrides_applied", 0)),
        "critical_text_no_evidence_blanked": int(resolver_metrics.get("critical_text_no_evidence_blanked", 0)),
        "critical_text_targets": critical_text_targets,
    }
    return {
        "filled_data": final_data,
        "confidence_scores": final_confidence,
        "suggestions": final_suggestions,
        "metadata": metadata,
    }


def _clean_description(description: str) -> str:
    if not description:
        return ""
    for prefix in ("Each ", "Each\n", "Each: "):
        if description.startswith(prefix):
            description = description[len(prefix) :].strip()

    lines = description.split("\n")
    cleaned: list[str] = []
    for index, line in enumerate(lines):
        text = line.strip()
        if not text:
            continue
        is_bullet = text.startswith(("•", "-", "*", "►", "▸", "·"))
        if index == 0 or not is_bullet:
            if index == 0:
                cleaned.append(text)
            elif cleaned:
                cleaned[-1] += f" {text}"
            else:
                cleaned.append(text)
        else:
            if not text.startswith("  "):
                text = f"  {text}"
            cleaned.append(text)
    return "\n".join(cleaned)


def build_options_listing(
    machine_data: dict[str, Any],
    common_items: list[dict[str, Any]],
    filled_data: dict[str, str],
) -> str:
    """Construct options listing from selected machine items."""
    if filled_data.get("options_listing"):
        return str(filled_data["options_listing"])

    options_lines: list[str] = []
    main_item = machine_data.get("main_item", {})
    if main_item and main_item.get("description"):
        machine_desc = _clean_description(main_item.get("description", ""))
        if machine_desc:
            options_lines.append(f"MACHINE: {machine_desc}\n")

    for addon in machine_data.get("add_ons", []) or []:
        desc = _clean_description(addon.get("description", ""))
        if desc:
            options_lines.append(f"• {desc}")

    for common in common_items or []:
        desc = _clean_description(common.get("description", ""))
        if desc:
            options_lines.append(f"• {desc}")

    return "\n".join(options_lines) if options_lines else "No options or specifications selected for this machine."


def generate_document(
    machine_data: dict[str, Any],
    filled_data: dict[str, str],
    common_items: list[dict[str, Any]],
) -> tuple[str, bool]:
    """Generate GOA output file and return output path + sortstar flag."""
    _, template_file_path, is_sortstar_template = get_contexts_for_machine(machine_data)
    machine_name = machine_data.get("machine_name") or "machine"
    clean_name = re.sub(r'[\\/*?:"<>|]', "_", machine_name.replace(" ", "_"))

    filled_payload = dict(filled_data)
    filled_payload["options_listing"] = build_options_listing(machine_data, common_items, filled_payload)

    if is_sortstar_template:
        output_path = f"output_SORTSTAR_{clean_name}_GOA.docx"
        fill_word_document_from_llm_data(template_file_path, filled_payload, output_path)
    else:
        output_path = f"output_{clean_name}_GOA.html"
        if not generate_goa_form():
            raise RuntimeError("Failed to generate HTML GOA form from Excel template.")
        fill_and_generate_html(str(OUTPUT_HTML_PATH), filled_payload, output_path)

    if not os.path.exists(output_path):
        raise RuntimeError(f"Output document was not created: {output_path}")
    return output_path, is_sortstar_template


def save_generated_template(
    machine_id: int,
    filled_data: dict[str, Any],
    output_path: str,
    template_type: str = "GOA",
) -> None:
    """Persist generated template data for a machine."""
    if not save_machine_template_data(machine_id, template_type, filled_data, output_path):
        raise RuntimeError(f"Failed to save template data for machine_id={machine_id}.")


def load_machine_by_id(machine_id: int) -> dict[str, Any] | None:
    """Load machine row and parsed JSON data."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, machine_name, client_quote_ref, machine_data_json, processing_date
            FROM machines
            WHERE id = ?
            """,
            (machine_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        payload = dict(row)
        payload["machine_data"] = json.loads(payload["machine_data_json"])
        return payload
    finally:
        conn.close()


def load_machine_name(machine_id: int) -> str:
    machine_row = load_machine_by_id(machine_id)
    if machine_row:
        return machine_row.get("machine_name", "")
    return ""


def get_machine_id_from_data(machine_data: dict[str, Any]) -> int | None:
    """Resolve a machine id from machine payload or machine name lookup."""
    machine_id = machine_data.get("id")
    if isinstance(machine_id, int):
        return machine_id

    machine_name = machine_data.get("machine_name", "")
    if not machine_name:
        return None

    matches = find_machines_by_name(machine_name)
    if matches:
        return int(matches[0]["id"])

    quote_ref = machine_data.get("client_quote_ref")
    if quote_ref:
        for machine in load_machines_for_quote(quote_ref):
            if machine.get("machine_name") == machine_name:
                return int(machine["id"])
    return None


def load_quote_artifacts(quote_ref: str) -> dict[str, Any]:
    """Load full text, items, and machine data for a quote."""
    document = load_document_content(quote_ref) or {}
    machines = load_machines_for_quote(quote_ref)
    # Preserve original quote line-item order for regrouping screens.
    # Reconstructing from machine payloads can reorder items (main/add-ons/common),
    # which breaks index-based assignment of add-ons between selected machines.
    items = _items_from_priced_rows(load_priced_items_for_quote(quote_ref))
    if not items:
        items = _items_from_machine_payloads(machines)
    return {
        "quote_ref": quote_ref,
        "full_pdf_text": document.get("full_pdf_text", ""),
        "pdf_filename": document.get("pdf_filename", ""),
        "items": items,
        "machines": machines,
    }


def _items_from_priced_rows(priced_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized_items: list[dict[str, Any]] = []
    for row in priced_rows:
        normalized = _normalize_artifact_item(row)
        if normalized:
            normalized_items.append(normalized)
    return normalized_items


def _items_from_machine_payloads(machine_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, float | None]] = set()

    for machine_row in machine_rows:
        machine_payload = machine_row.get("machine_data")
        if not isinstance(machine_payload, dict):
            continue

        item_candidates: list[dict[str, Any]] = []
        main_item = machine_payload.get("main_item")
        if isinstance(main_item, dict):
            item_candidates.append(main_item)

        add_ons = machine_payload.get("add_ons", [])
        if isinstance(add_ons, list):
            item_candidates.extend(item for item in add_ons if isinstance(item, dict))

        common_items = machine_payload.get("common_items", [])
        if isinstance(common_items, list):
            item_candidates.extend(item for item in common_items if isinstance(item, dict))

        for candidate in item_candidates:
            normalized = _normalize_artifact_item(candidate)
            if not normalized:
                continue

            item_key = (
                normalized["description"],
                normalized.get("quantity_text") or "",
                normalized.get("selection_text") or "",
                normalized.get("item_price_numeric"),
            )
            if item_key in seen:
                continue

            seen.add(item_key)
            items.append(normalized)

    return items


def _normalize_artifact_item(item: dict[str, Any]) -> dict[str, Any] | None:
    description_raw = item.get("description")
    if not isinstance(description_raw, str):
        description_raw = item.get("item_description")
    if description_raw is None:
        return None

    description = str(description_raw).strip()
    if not description:
        return None

    quantity_raw = item.get("quantity_text")
    if quantity_raw is None:
        quantity_raw = item.get("item_quantity")

    selection_raw = item.get("selection_text")
    if selection_raw is None:
        selection_raw = item.get("item_price_str")

    price_raw = item.get("item_price_numeric")
    price_numeric: float | None
    if isinstance(price_raw, bool):
        price_numeric = None
    elif isinstance(price_raw, (int, float)):
        price_numeric = float(price_raw)
    else:
        price_numeric = None

    return {
        "description": description,
        "quantity_text": str(quantity_raw).strip() if quantity_raw is not None else None,
        "selection_text": str(selection_raw).strip() if selection_raw is not None else None,
        "item_price_numeric": price_numeric,
    }
