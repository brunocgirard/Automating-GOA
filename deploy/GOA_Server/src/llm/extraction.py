"""
LLM Field Extraction Module

This module handles core LLM field extraction operations using structured prompts and chains.
It provides the main extraction functions for document field population, using both
comprehensive and machine-specific extraction strategies.

Key Features:
- Comprehensive field extraction for all document fields (get_all_fields_via_llm)
- Machine-specific field extraction with divide-and-conquer strategy (get_machine_specific_fields_via_llm)
- Interactive chat-based field updates (get_llm_chat_update)
- CRM-to-document mapping for secondary documents (map_crm_to_document_via_llm)
- Confidence-scored extraction with validation (get_machine_specific_fields_with_confidence)
- Few-shot learning integration for improved accuracy

Extraction Strategies:
1. Comprehensive Extraction: Processes all fields in a single LLM call with structured prompts
2. Divide and Conquer: Splits fields into logical groups for focused extraction
3. Chat Update: Allows interactive corrections based on user instructions
4. CRM Mapping: Maps existing CRM data to new document templates

The module integrates with:
- Few-shot learning (basic and enhanced semantic similarity)
- Post-processing rules for field correction
- Confidence estimation and dependency validation
- Template-specific extraction strategies (Standard vs SortStar)
"""

import re
import os
import json
import time
import traceback
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Any, Optional, Tuple, Sequence

# LangChain imports
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel, Field, create_model, model_validator

# Internal LLM module imports
from .client import get_generative_model, configure_gemini_client, get_configured_model_name, genai
from .constants import FIELD_GROUPS, FieldWithConfidence
from .confidence import estimate_extraction_confidence
from .validation import (
    sanitize_extracted_fields,
    validate_field_dependencies,
    validate_llm_response,
)
from .post_processing import apply_post_processing_rules

# Few-shot learning imports (basic)
from src.utils.few_shot_learning import (
    determine_machine_type,
    save_successful_extraction_as_example,
    record_user_feedback_on_extraction,
    enhance_prompt_with_few_shot_examples,
)
from src.utils.pdf_rag import build_retrieved_pdf_context, prepare_pdf_rag_chunks

# Try to import enhanced few-shot learning, fall back to basic if not available
try:
    from src.utils.few_shot_enhanced import (
        enhance_prompt_with_semantic_examples,
        FewShotManager,
        create_enhanced_few_shot_prompt,
        get_few_shot_manager,
    )
    ENHANCED_FEW_SHOT_AVAILABLE = True
except ImportError as e:
    print(f"[WARN] Enhanced few-shot learning not available: {e}")
    print("  Falling back to basic few-shot learning")
    ENHANCED_FEW_SHOT_AVAILABLE = False
    FewShotManager = None  # type: ignore
    get_few_shot_manager = None  # type: ignore

# Runtime safety switch: keep default enabled, allow emergency disable via env.
DISABLE_ALL_FEW_SHOT = os.getenv("DISABLE_ALL_FEW_SHOT", "").strip().lower() in {
    "1", "true", "yes", "on"
}
if DISABLE_ALL_FEW_SHOT:
    print("[WARN] Few-shot learning disabled via DISABLE_ALL_FEW_SHOT environment variable.")
else:
    print("[OK] Few-shot learning enabled with quality guards.")

# Template utilities imports (must NOT be moved - imported from template_utils)
from src.utils.template_utils import add_section_aware_instructions, select_sortstar_basic_system
from src.utils.quote_library import get_quote_library_context


def _safe_positive_int_env(var_name: str, default: int) -> int:
    raw_value = str(os.getenv(var_name, "")).strip()
    if not raw_value:
        return default
    try:
        parsed = int(raw_value)
        return parsed if parsed > 0 else default
    except ValueError:
        return default


_MAIN_ITEM_INLINE_BULLET_PATTERN = re.compile(r"\s+([•*►▸·])\s+")
_MAIN_ITEM_INLINE_DASH_BULLET_PATTERN = re.compile(r"([:;])\s*-\s+")
_MAIN_ITEM_BULLET_SPLIT_PATTERN = re.compile(r"(?:^|\n)\s*[•\-\*►▸·]\s+")


def _normalize_main_item_bullet_text(description: str | None) -> str:
    text = str(description or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return ""
    text = _MAIN_ITEM_INLINE_BULLET_PATTERN.sub(r"\n\1 ", text)
    text = _MAIN_ITEM_INLINE_DASH_BULLET_PATTERN.sub(r"\1\n- ", text)
    return text


def _parse_main_item_subitems(description: str) -> List[str]:
    normalized = _normalize_main_item_bullet_text(description)
    if not normalized or not _MAIN_ITEM_BULLET_SPLIT_PATTERN.search(normalized):
        return []

    subitems: List[str] = []
    for raw_item in _MAIN_ITEM_BULLET_SPLIT_PATTERN.split(normalized)[1:]:
        cleaned = re.sub(r"\s+", " ", raw_item).strip(" \t\r\n-•*►▸·;:,")
        if cleaned:
            subitems.append(cleaned)
    return subitems


def _extract_main_item_headline(description: str) -> str:
    normalized = _normalize_main_item_bullet_text(description)
    if not normalized:
        return ""

    first_bullet = _MAIN_ITEM_BULLET_SPLIT_PATTERN.search(normalized)
    headline = normalized[: first_bullet.start()] if first_bullet else normalized
    return re.sub(r"\s+", " ", headline).strip(" \t\r\n-•*►▸·")


MAX_FIELDS_PER_EXTRACTION_GROUP = _safe_positive_int_env("LLM_MAX_FIELDS_PER_GROUP", 180)


@dataclass
class ExtractionPassOptions:
    """Runtime options for one extraction pass."""

    pass_name: str = "pass"
    model_name: str | None = None
    rag_max_chars: int = 40000
    max_fields_per_group: int = MAX_FIELDS_PER_EXTRACTION_GROUP
    enable_few_shot: bool = True
    enable_quote_library: bool = True
    max_examples_per_field: int = 1
    max_checkbox_synonyms: int = 3
    max_checkbox_indicators: int = 2
    compact_prompt: bool = False
    concurrency: int = 1
    use_weighted_rag: bool = True
    secondary_hint_char_limit: int = 320


def _is_checkbox_field(field_key: str, context: Any, using_schema_format: bool) -> bool:
    return field_key.endswith("_check") or (
        using_schema_format and isinstance(context, dict) and context.get("type") == "boolean"
    )


def _is_comment_field(field_key: str, context: Any, using_schema_format: bool) -> bool:
    if field_key.endswith("_check"):
        return False
    if using_schema_format and isinstance(context, dict):
        return "comment" in str(context.get("description", "")).lower()
    if isinstance(context, str):
        return "comment" in context.lower()
    lowered = field_key.lower()
    return lowered in {"rj_comm", "ci_vcom"} or lowered.endswith("_comm") or lowered.endswith("_comment")


def _find_group_for_field(key: str, context: Any = None) -> str:
    if isinstance(context, dict):
        section = str(context.get("section", "")).strip().lower()
        if section and any(
            x in section for x in ["control", "electrical", "program", "guard", "code", "coding", "inspect"]
        ):
            return "Controls & Electrical"
        if section and any(
            x in section for x in ["liquid", "fill", "bottle", "handling", "tablet", "cotton", "desiccant", "gas"]
        ):
            return "Liquid Filling & Handling"
        if section and any(
            x in section for x in ["cap", "label", "induction", "sleeve", "conveyor", "plug", "belt", "shrink", "retorquer"]
        ):
            return "Capping, Labeling & Other"

    for group_name, rules in FIELD_GROUPS.items():
        if key in rules["exact"]:
            return group_name
        for prefix in rules["prefixes"]:
            if key.startswith(prefix):
                return group_name
    return "General & Utility"


def _group_contexts_for_extraction(
    template_placeholder_contexts: Dict[str, Any],
    *,
    max_fields_per_group: int,
) -> Dict[str, Dict[str, Any]]:
    grouped_contexts = {group: {} for group in FIELD_GROUPS.keys()}
    for key, context in template_placeholder_contexts.items():
        group = _find_group_for_field(key, context)
        grouped_contexts[group][key] = context

    active_groups = {k: v for k, v in grouped_contexts.items() if v}
    largest_group_size = max((len(group) for group in active_groups.values()), default=0)
    if largest_group_size > max_fields_per_group:
        active_groups = _rebalance_grouped_contexts(
            active_groups,
            max_fields_per_group=max_fields_per_group,
        )
    return active_groups


def _clean_json_response(raw_text: str) -> str:
    cleaned = (raw_text or "").strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return cleaned.strip()


def _normalize_group_output(
    parsed: Dict[str, Any],
    group_contexts: Dict[str, Any],
    *,
    using_schema_format: bool,
) -> Dict[str, str]:
    output: Dict[str, str] = {}
    for key in group_contexts:
        context = group_contexts[key]
        is_checkbox = _is_checkbox_field(key, context, using_schema_format)
        is_comment = _is_comment_field(key, context, using_schema_format)
        value = parsed.get(key)
        if is_checkbox:
            if isinstance(value, bool):
                output[key] = "YES" if value else "NO"
            elif isinstance(value, str) and value.strip().upper() in {"YES", "TRUE", "1"}:
                output[key] = "YES"
            else:
                output[key] = "NO"
        else:
            output[key] = "" if is_comment else (str(value).strip() if value is not None else "")
    return output


def _build_group_field_lines(
    group_contexts: Dict[str, Any],
    *,
    compact_prompt: bool,
    max_checkbox_synonyms: int,
    max_checkbox_indicators: int,
) -> tuple[list[str], bool]:
    using_schema_format = isinstance(next(iter(group_contexts.values()), {}), dict)
    field_lines: list[str] = []

    for key, ctx in group_contexts.items():
        is_checkbox = _is_checkbox_field(key, ctx, using_schema_format)
        is_comment = _is_comment_field(key, ctx, using_schema_format)
        field_type = "C" if is_checkbox else "T"

        if isinstance(ctx, dict):
            description = str(ctx.get("description") or key).strip()
            section = str(ctx.get("section") or "").strip()
            subsection = str(ctx.get("subsection") or "").strip()

            if compact_prompt:
                label = description
                if subsection:
                    label = f"{subsection}: {label}"
                if section:
                    label = f"{section} > {label}"
                suffix = ""
                if is_checkbox:
                    synonyms = [str(v).strip() for v in ctx.get("synonyms", []) if str(v).strip()]
                    indicators = [str(v).strip() for v in ctx.get("positive_indicators", []) if str(v).strip()]
                    syn_text = ", ".join(synonyms[:max_checkbox_synonyms])
                    ind_text = ", ".join(indicators[:max_checkbox_indicators])
                    if syn_text:
                        suffix += f" | alt={syn_text}"
                    if ind_text:
                        suffix += f" | +={ind_text}"
                elif is_comment:
                    suffix += " | user_entry=true | return_empty=true"
                field_lines.append(f"- {key} | {field_type} | {label}{suffix}")
            else:
                extras = ""
                if is_checkbox:
                    synonyms = ctx.get("synonyms", [])
                    if synonyms:
                        extras += f" [Alt: {', '.join(str(v) for v in synonyms[:5])}]"
                    positive = ctx.get("positive_indicators", [])
                    if positive and len(group_contexts) <= 80:
                        extras += f" [+: {', '.join(str(v) for v in positive[:3])}]"
                    negative = ctx.get("negative_indicators", [])
                    if negative and len(group_contexts) <= 80:
                        extras += f" [-: {', '.join(str(v) for v in negative[:3])}]"
                elif is_comment:
                    extras += " [User entry field: return empty string]"
                if subsection:
                    field_lines.append(f"- {key}: [{subsection}] {description}{extras}")
                else:
                    field_lines.append(f"- {key}: {description}{extras}")
            continue

        context_text = str(ctx).strip() if ctx is not None else key
        if is_comment:
            context_text = f"{context_text} [User entry field: return empty string]"
        field_lines.append(f"- {key} | {field_type} | {context_text}" if compact_prompt else f"- {key}: {context_text}")

    return field_lines, using_schema_format


def _build_group_query_hints(
    group_name: str,
    group_contexts: Dict[str, Any],
    *,
    machine_name: str,
    main_item_desc: str,
    main_item_subitems: List[str],
    add_on_descs: str,
    common_item_descs: str,
    quote_library_context: str,
    compact_prompt: bool,
    secondary_hint_char_limit: int = 320,
) -> tuple[List[str], List[str]]:
    def _trim_hint(text: str, limit: int = 320) -> str:
        compact = re.sub(r"\s+", " ", str(text or "")).strip()
        if not compact:
            return ""
        if len(compact) <= limit:
            return compact
        return compact[: limit - 1].rstrip() + "..."

    main_item_headline = _extract_main_item_headline(main_item_desc)

    primary_hints: List[str] = [group_name]
    secondary_hints: List[str] = [_trim_hint(machine_name, secondary_hint_char_limit)]
    if main_item_subitems:
        main_item_hint = main_item_headline or main_item_desc
        if main_item_hint:
            secondary_hints.append(_trim_hint(main_item_hint, secondary_hint_char_limit))
        secondary_hints.extend(
            _trim_hint(subitem, secondary_hint_char_limit) for subitem in main_item_subitems
        )
    else:
        secondary_hints.append(_trim_hint(main_item_desc, secondary_hint_char_limit))
    secondary_hints.extend(
        [
            _trim_hint(add_on_descs, secondary_hint_char_limit),
            _trim_hint(common_item_descs, secondary_hint_char_limit),
            group_name,
        ]
    )
    if quote_library_context and not compact_prompt:
        secondary_hints.append(_trim_hint(quote_library_context, max(secondary_hint_char_limit, 640)))

    for key, context in group_contexts.items():
        primary_hints.append(key.replace("_", " "))
        if isinstance(context, dict):
            for hint_key in ("description", "section", "subsection"):
                hint_val = context.get(hint_key)
                if isinstance(hint_val, str) and hint_val.strip():
                    primary_hints.append(hint_val)
            text_indicators = context.get("text_indicators", [])
            if isinstance(text_indicators, list):
                limit = 10 if compact_prompt else 15
                primary_hints.extend(str(v).strip() for v in text_indicators[:limit] if str(v).strip())
            value_patterns = context.get("value_patterns", [])
            if isinstance(value_patterns, list):
                limit = 4 if compact_prompt else 8
                for pattern in value_patterns[:limit]:
                    cleaned_pattern = re.sub(r"[^a-z0-9\s/]+", " ", str(pattern).lower()).strip()
                    if cleaned_pattern:
                        primary_hints.append(cleaned_pattern)

            for hint_list_key in ("synonyms", "positive_indicators"):
                hint_values = context.get(hint_list_key, [])
                if isinstance(hint_values, list):
                    limit = 2 if compact_prompt else 5
                    secondary_hints.extend(str(v) for v in hint_values[:limit] if v)
        elif isinstance(context, str) and context.strip():
            primary_hints.append(context)

    # Drop empties while preserving order.
    primary_hints = [hint for hint in primary_hints if str(hint).strip()]
    secondary_hints = [hint for hint in secondary_hints if str(hint).strip()]
    return primary_hints, secondary_hints

def _chunk_contexts(
    contexts: Dict[str, Any],
    chunk_size: int,
) -> List[Dict[str, Any]]:
    if chunk_size <= 0 or len(contexts) <= chunk_size:
        return [contexts]
    items = list(contexts.items())
    return [dict(items[i : i + chunk_size]) for i in range(0, len(items), chunk_size)]


def _rebalance_grouped_contexts(
    grouped_contexts: Dict[str, Dict[str, Any]],
    *,
    max_fields_per_group: int,
) -> Dict[str, Dict[str, Any]]:
    """
    Prevent oversized extraction groups that can stall requests.

    Primary strategy:
    - Split large groups by section when section metadata is available.
    - Fall back to deterministic chunking by field count.
    - Merge tiny groups (< min_fields) back together to avoid wasteful
      API calls that send 40K of context for 1 field.
    """
    min_fields = max(10, max_fields_per_group // 4)
    rebalanced: Dict[str, Dict[str, Any]] = {}

    for group_name, group_contexts in grouped_contexts.items():
        if len(group_contexts) <= max_fields_per_group:
            rebalanced[group_name] = group_contexts
            continue

        section_buckets: Dict[str, Dict[str, Any]] = {}
        unsectioned: Dict[str, Any] = {}
        for field_key, field_context in group_contexts.items():
            section_name = ""
            if isinstance(field_context, dict):
                section_name = str(field_context.get("section", "")).strip()
            if section_name:
                section_buckets.setdefault(section_name, {})[field_key] = field_context
            else:
                unsectioned[field_key] = field_context

        if section_buckets:
            # Merge small sections together before emitting groups
            merged_sections: List[tuple] = []  # (label, contexts_dict)
            pending_label = ""
            pending_fields: Dict[str, Any] = {}

            section_index = 1
            for section_name, section_contexts in section_buckets.items():
                section_label = re.sub(r"\s+", " ", section_name).strip()[:48] or f"Section {section_index}"
                section_index += 1

                # If adding this section still fits in one group, merge it
                if len(pending_fields) + len(section_contexts) <= max_fields_per_group:
                    pending_fields.update(section_contexts)
                    pending_label = pending_label or section_label
                    if len(pending_fields) < min_fields:
                        continue  # keep accumulating
                    # Flush
                    merged_sections.append((pending_label, dict(pending_fields)))
                    pending_label = ""
                    pending_fields = {}
                else:
                    # Flush pending first
                    if pending_fields:
                        merged_sections.append((pending_label, dict(pending_fields)))
                        pending_label = ""
                        pending_fields = {}
                    # This section alone may need chunking
                    if len(section_contexts) <= max_fields_per_group:
                        merged_sections.append((section_label, section_contexts))
                    else:
                        chunks = _chunk_contexts(section_contexts, max_fields_per_group)
                        for ci, chunk in enumerate(chunks, 1):
                            suffix = f" #{ci}" if len(chunks) > 1 else ""
                            merged_sections.append((f"{section_label}{suffix}", chunk))

            # Flush remaining pending
            if pending_fields:
                merged_sections.append((pending_label, dict(pending_fields)))

            # Add unsectioned fields by merging into last group if it fits
            if unsectioned:
                if merged_sections and len(merged_sections[-1][1]) + len(unsectioned) <= max_fields_per_group:
                    last_label, last_fields = merged_sections[-1]
                    last_fields.update(unsectioned)
                    merged_sections[-1] = (last_label, last_fields)
                else:
                    chunks = _chunk_contexts(unsectioned, max_fields_per_group)
                    for ci, chunk in enumerate(chunks, 1):
                        suffix = f" #{ci}" if len(chunks) > 1 else ""
                        merged_sections.append((f"Unsectioned{suffix}", chunk))

            for label, fields_dict in merged_sections:
                rebalanced[f"{group_name} | {label}"] = fields_dict
            continue

        chunks = _chunk_contexts(group_contexts, max_fields_per_group)
        for chunk_index, chunk in enumerate(chunks, start=1):
            chunk_suffix = f" #{chunk_index}" if len(chunks) > 1 else ""
            rebalanced[f"{group_name}{chunk_suffix}"] = chunk

    return rebalanced


def _extract_single_group(
    *,
    model: Any,
    group_name: str,
    group_contexts: Dict[str, Any],
    machine_name: str,
    main_item_desc: str,
    main_item_subitems: List[str],
    add_on_descs: str,
    common_item_descs: str,
    full_pdf_text: str,
    quote_library_context: str,
    pass_options: ExtractionPassOptions,
    precomputed_chunks: Sequence[str] | None = None,
    machine_data: Optional[Dict[str, Any]] = None,
    common_items: Optional[List[Dict[str, Any]]] = None,
) -> tuple[Dict[str, str], int]:
    field_lines, using_schema_format = _build_group_field_lines(
        group_contexts,
        compact_prompt=pass_options.compact_prompt,
        max_checkbox_synonyms=pass_options.max_checkbox_synonyms,
        max_checkbox_indicators=pass_options.max_checkbox_indicators,
    )
    fields_block = "\n".join(field_lines)

    primary_hints, secondary_hints = _build_group_query_hints(
        group_name,
        group_contexts,
        machine_name=machine_name,
        main_item_desc=main_item_desc,
        main_item_subitems=main_item_subitems,
        add_on_descs=add_on_descs,
        common_item_descs=common_item_descs,
        quote_library_context=quote_library_context if pass_options.enable_quote_library else "",
        compact_prompt=pass_options.compact_prompt,
        secondary_hint_char_limit=max(120, int(pass_options.secondary_hint_char_limit or 320)),
    )

    if full_pdf_text:
        pdf_context, rag_note = build_retrieved_pdf_context(
            full_pdf_text,
            [*primary_hints, *secondary_hints],
            max_context_chars=max(2000, pass_options.rag_max_chars),
            precomputed_chunks=precomputed_chunks,
            primary_query_hints=primary_hints,
            secondary_query_hints=secondary_hints,
            weighted_hints_enabled=pass_options.use_weighted_rag,
        )
    else:
        pdf_context, rag_note = "", "[No PDF text provided.]"

    main_item_headline = _extract_main_item_headline(main_item_desc)
    if not main_item_headline:
        main_item_headline = re.sub(r"\s+", " ", str(main_item_desc or "")).strip()

    prompt_parts = [
        f"You are extracting GOA template values for section '{group_name}' ({pass_options.pass_name}).",
        "Fill every listed key.",
        "",
        "MACHINE CONTEXT:",
        f"- Machine: {machine_name}",
    ]
    if main_item_subitems:
        prompt_parts.append(f"- Main item: {main_item_headline}")
        prompt_parts.append("- Main item includes:")
        prompt_parts.extend(f"  • {subitem}" for subitem in main_item_subitems)
    else:
        prompt_parts.append(f"- Main item: {main_item_desc}")
    prompt_parts.extend(
        [
            f"- Add-ons: {add_on_descs}",
            f"- Common items: {common_item_descs}",
        ]
    )
    if pass_options.enable_quote_library and quote_library_context:
        prompt_parts.append(f"- QUOTE_LIBRARY reference: {quote_library_context}")

    prompt_parts.extend(
        [
            "",
            f"PDF CONTEXT {rag_note}:",
            pdf_context,
            "",
            "FIELDS:",
            fields_block,
            "",
            "RULES:",
            '- Checkbox fields (type "C"): value must be "YES" or "NO". Default to "NO" if unsupported.',
            '- Text fields (type "T"): value must be extracted text or empty string "".',
            '- Comment/comment(s) text fields are user-entered; always return empty string "" for those fields.',
            "- Never return null.",
            "- Return JSON object with all listed keys only.",
            "",
            "JSON:",
        ]
    )

    if pass_options.enable_few_shot and not DISABLE_ALL_FEW_SHOT:
        try:
            if ENHANCED_FEW_SHOT_AVAILABLE:
                prompt_parts = enhance_prompt_with_semantic_examples(
                    prompt_parts=prompt_parts,
                    machine_data=machine_data or {},
                    template_placeholder_contexts=group_contexts,
                    common_items=common_items or [],
                    full_pdf_text=full_pdf_text,
                    max_examples_per_field=max(1, pass_options.max_examples_per_field),
                )
            else:
                prompt_parts = enhance_prompt_with_few_shot_examples(
                    prompt_parts=prompt_parts,
                    machine_data=machine_data or {},
                    template_placeholder_contexts=group_contexts,
                    common_items=common_items or [],
                    full_pdf_text=full_pdf_text,
                    max_examples_per_field=max(1, pass_options.max_examples_per_field),
                )
        except Exception as few_shot_error:
            print(f"[WARN] Few-shot enhancement skipped for {group_name}: {few_shot_error}")

    prompt = "\n".join(prompt_parts)
    prompt_chars = len(prompt)

    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
    ]

    parsed: Dict[str, Any] = {}
    for attempt in range(2):
        try:
            response = model.generate_content(prompt, safety_settings=safety_settings)
            cleaned = _clean_json_response(getattr(response, "text", ""))
            loaded = json.loads(cleaned)
            if isinstance(loaded, dict):
                parsed = loaded
                break
            print(f"[WARN] Non-dict response for group {group_name}; attempt {attempt + 1}")
        except Exception as extract_error:
            print(f"[WARN] Group extraction attempt {attempt + 1} failed for {group_name}: {extract_error}")
            if attempt == 1:
                parsed = {}
            else:
                # Basic backoff for transient provider throttling.
                time.sleep(0.7 * (attempt + 1))

    return _normalize_group_output(parsed, group_contexts, using_schema_format=using_schema_format), prompt_chars


def extract_machine_fields_with_options(
    machine_data: Dict[str, Any],
    common_items: List[Dict[str, Any]],
    template_placeholder_contexts: Dict[str, Any],
    full_pdf_text: str,
    *,
    pass_options: Optional[ExtractionPassOptions] = None,
    template_metadata: Optional[Dict[str, Any]] = None,
    user_id: int | None = None,
) -> tuple[Dict[str, str], Dict[str, Any]]:
    """
    Extract fields using configurable per-pass settings.

    Returns:
        tuple[dict, dict]:
            - extracted field values
            - extraction metrics metadata
    """
    options = pass_options or ExtractionPassOptions()
    model = get_generative_model(options.model_name, user_id=user_id)
    if model is None and not configure_gemini_client(user_id=user_id):
        defaults = {
            key: ("NO" if key.endswith("_check") else "")
            for key in template_placeholder_contexts.keys()
        }
        return defaults, {
            "pass_name": options.pass_name,
            "groups_processed": 0,
            "fields_attempted": len(template_placeholder_contexts),
            "prompt_chars_estimate": 0,
            "duration_ms": 0,
            "model_name": options.model_name or get_configured_model_name(),
        }
    if model is None:
        model = get_generative_model(options.model_name, user_id=user_id)

    start = time.time()
    machine_name = machine_data.get("machine_name", "")
    main_item_desc = machine_data.get("main_item", {}).get("description", "")
    main_item_subitems = _parse_main_item_subitems(main_item_desc)
    add_on_descs = "; ".join(item.get("description", "") for item in machine_data.get("add_ons", []) if item.get("description"))
    common_item_descs = "; ".join(item.get("description", "") for item in common_items if item.get("description"))

    active_groups = _group_contexts_for_extraction(
        template_placeholder_contexts,
        max_fields_per_group=max(1, options.max_fields_per_group),
    )

    quote_library_context = ""
    if options.enable_quote_library:
        quote_library_path = template_metadata.get("quote_library_path") if isinstance(template_metadata, dict) else None
        try:
            quote_library_context, quote_library_matches = get_quote_library_context(
                machine_name=machine_name,
                main_item_desc=main_item_desc,
                add_on_descs=add_on_descs,
                quote_library_path=quote_library_path,
            )
            if quote_library_matches:
                print(f"[{options.pass_name}] Matched QUOTE_LIBRARY specs: {', '.join(quote_library_matches)}")
        except Exception as quote_library_error:
            print(f"[{options.pass_name}] QUOTE_LIBRARY lookup failed: {quote_library_error}")

    precomputed_chunks: Sequence[str] | None = None
    if full_pdf_text and len(full_pdf_text) > max(2000, options.rag_max_chars):
        precomputed_chunks = prepare_pdf_rag_chunks(full_pdf_text)

    all_extracted_data: Dict[str, str] = {}
    prompt_chars_estimate = 0
    groups_processed = 0

    def run_group(group_name: str, group_contexts: Dict[str, Any]) -> tuple[str, Dict[str, str], int]:
        values, prompt_chars = _extract_single_group(
            model=model,
            group_name=group_name,
            group_contexts=group_contexts,
            machine_name=machine_name,
            main_item_desc=main_item_desc,
            main_item_subitems=main_item_subitems,
            add_on_descs=add_on_descs,
            common_item_descs=common_item_descs,
            full_pdf_text=full_pdf_text,
            quote_library_context=quote_library_context,
            pass_options=options,
            precomputed_chunks=precomputed_chunks,
            machine_data=machine_data,
            common_items=common_items,
        )
        return group_name, values, prompt_chars

    concurrency = max(1, int(options.concurrency or 1))
    if concurrency > 1 and len(active_groups) > 1:
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [
                executor.submit(run_group, group_name, group_contexts)
                for group_name, group_contexts in active_groups.items()
            ]
            for future in as_completed(futures):
                group_name, group_values, prompt_chars = future.result()
                all_extracted_data.update(group_values)
                prompt_chars_estimate += prompt_chars
                groups_processed += 1
                print(f"[{options.pass_name}] Group completed: {group_name}")
    else:
        for group_name, group_contexts in active_groups.items():
            _, group_values, prompt_chars = run_group(group_name, group_contexts)
            all_extracted_data.update(group_values)
            prompt_chars_estimate += prompt_chars
            groups_processed += 1

    # Ensure full key coverage for this pass scope.
    for key, context in template_placeholder_contexts.items():
        if key in all_extracted_data:
            continue
        is_checkbox = key.endswith("_check") or (isinstance(context, dict) and context.get("type") == "boolean")
        all_extracted_data[key] = "NO" if is_checkbox else ""

    duration_ms = int((time.time() - start) * 1000)
    metrics = {
        "pass_name": options.pass_name,
        "groups_processed": groups_processed,
        "fields_attempted": len(template_placeholder_contexts),
        "prompt_chars_estimate": prompt_chars_estimate,
        "duration_ms": duration_ms,
        "model_name": options.model_name or get_configured_model_name(),
    }
    return all_extracted_data, metrics


def select_repair_field_contexts(
    extracted_data: Dict[str, str],
    confidence_scores: Dict[str, float],
    template_placeholder_contexts: Dict[str, Any],
    *,
    text_confidence_threshold: float = 0.72,
    checkbox_yes_confidence_threshold: float = 0.80,
    dependency_suggestions: Optional[List[Dict[str, Any]]] = None,
    force_critical_text_fields: bool = False,
    forced_semantic_tags: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """
    Build a focused field subset for repair pass extraction.
    """
    selected: Dict[str, Any] = {}
    suggestions = dependency_suggestions or []
    semantic_tags = {
        str(tag).strip().lower()
        for tag in (forced_semantic_tags or ("direction", "voltage", "hz", "phases"))
        if str(tag).strip()
    }

    def _resolve_semantic_tag(field_key: str, field_context: Any) -> str:
        if isinstance(field_context, dict):
            explicit = str(field_context.get("semantic_tag", "")).strip().lower()
            if explicit:
                return explicit
            description = str(field_context.get("description", "")).strip().lower()
            section = str(field_context.get("section", "")).strip().lower()
            if "direction" in description and "basic information" in section:
                return "direction"
            if "utility specifications" in section:
                if "voltage" in description:
                    return "voltage"
                if "hz" in description or "hertz" in description:
                    return "hz"
                if "phase" in description:
                    return "phases"
        return ""

    for field_key, context in template_placeholder_contexts.items():
        value = extracted_data.get(field_key, "")
        confidence = float(confidence_scores.get(field_key, 0.0) or 0.0)
        is_checkbox = field_key.endswith("_check") or (isinstance(context, dict) and context.get("type") == "boolean")

        if is_checkbox:
            normalized = str(value or "").strip().upper()
            if normalized == "YES" and confidence < checkbox_yes_confidence_threshold:
                selected[field_key] = context
            elif normalized not in {"YES", "NO"}:
                selected[field_key] = context
            continue

        if not str(value or "").strip() or confidence < text_confidence_threshold:
            selected[field_key] = context
            continue

        if force_critical_text_fields:
            semantic_tag = _resolve_semantic_tag(field_key, context)
            if semantic_tag and semantic_tag in semantic_tags:
                selected[field_key] = context

    # Include dependency warning fields for auto-repair attempts.
    for suggestion in suggestions:
        field_key = suggestion.get("field")
        if isinstance(field_key, str) and field_key in template_placeholder_contexts:
            selected[field_key] = template_placeholder_contexts[field_key]

    return selected


def get_all_fields_via_llm(selected_pdf_descriptions: List[str],
                             template_placeholder_contexts: Dict[str, str],
                             full_pdf_text: str,
                             user_id: int | None = None) -> Dict[str, str]:
    """
    Constructs a comprehensive prompt for the LLM to fill all template fields
    (checkboxes and text fields) based on selected PDF items and full PDF text.

    The function now better handles enhanced context from the outline file.

    Args:
        selected_pdf_descriptions: List of item descriptions selected from the PDF
        template_placeholder_contexts: Dictionary of field keys to descriptions/schema
        full_pdf_text: Full text content of the PDF document

    Returns:
        Dictionary mapping field keys to extracted values (YES/NO for checkboxes, text for fields)
    """
    GENERATIVE_MODEL = get_generative_model(user_id=user_id)
    if GENERATIVE_MODEL is None:
        if not configure_gemini_client(user_id=user_id):
            print("LLM client not configured. Returning empty data for all fields.")
            return {key: ("NO" if key.endswith("_check") else "") for key in template_placeholder_contexts.keys()}

    # Determine if we're using the old format (string context) or new format (schema)
    using_schema_format = isinstance(next(iter(template_placeholder_contexts.values()), ""), dict)

    pdf_query_hints: List[str] = list(selected_pdf_descriptions)
    for field_key, context in template_placeholder_contexts.items():
        pdf_query_hints.append(field_key.replace("_", " "))
        if isinstance(context, dict):
            for hint_key in ("description", "section", "subsection"):
                hint_val = context.get(hint_key)
                if isinstance(hint_val, str) and hint_val.strip():
                    pdf_query_hints.append(hint_val)
            for hint_list_key in ("synonyms", "positive_indicators"):
                hint_values = context.get(hint_list_key, [])
                if isinstance(hint_values, list):
                    pdf_query_hints.extend(str(v) for v in hint_values[:8] if v)
        elif isinstance(context, str) and context.strip():
            pdf_query_hints.append(context)

    rag_pdf_text, rag_context_note = build_retrieved_pdf_context(
        full_pdf_text,
        pdf_query_hints,
        max_context_chars=50000,
    )

    prompt_parts = [
        "You are an AI assistant tasked with accurately extracting information from a PDF quote to fill a structured Word template.",
        "You will be given:",
        "  1. A list of 'SELECTED PDF ITEMS' which are explicitly priced or marked as included in the quote.",
        "  2. The 'FULL PDF TEXT' of the entire quote document.",
        "  3. A list of 'TEMPLATE FIELDS' with their descriptions (contexts) from the Word template.",

        "\nFULL PDF TEXT (retrieved relevant chunks from the quote; evidence is not limited to the first page/text block):",
        rag_context_note,
        rag_pdf_text,

        "\nSELECTED PDF ITEMS (These are primary evidence for options being selected):"
    ]
    if not selected_pdf_descriptions:
        prompt_parts.append("  (No specific items were identified as selected from tables in the PDF quote.)")
    else:
        for i, desc in enumerate(selected_pdf_descriptions):
            prompt_parts.append(f"  - PDF Item {i+1}: {desc}")

    if using_schema_format:
        # Group fields by section when using schema format
        sections = {}
        for key, field_info in template_placeholder_contexts.items():
            section = field_info.get("section", "General")
            if section not in sections:
                sections[section] = []
            sections[section].append((key, field_info))

        prompt_parts.append("\nTEMPLATE FIELDS TO FILL (organized by section):")

        for section, fields in sorted(sections.items()):
            prompt_parts.append(f"\n## {section} SECTION:")

            # Group by field type within section
            text_fields = [f for f in fields if f[1].get("type") == "string"]
            checkbox_fields = [f for f in fields if f[1].get("type") == "boolean"]

            if text_fields:
                prompt_parts.append("TEXT FIELDS:")
                for key, field_info in text_fields:
                    desc = field_info.get("description", key)
                    subsection = field_info.get("subsection", "")
                    if subsection:
                        prompt_parts.append(f"  - '{key}': [{subsection}] {desc}")
                    else:
                        prompt_parts.append(f"  - '{key}': {desc}")

            if checkbox_fields:
                prompt_parts.append("CHECKBOX FIELDS (must be YES or NO):")
                for key, field_info in checkbox_fields:
                    desc = field_info.get("description", key)
                    subsection = field_info.get("subsection", "")

                    # Include synonyms and positive indicators for checkbox fields
                    synonyms = field_info.get("synonyms", [])
                    positive_indicators = field_info.get("positive_indicators", [])

                    # Format the synonyms and indicators for the prompt
                    synonym_text = ""
                    if synonyms:
                        synonym_text = f" [Alternative terms: {', '.join(synonyms[:5])}]" if synonyms else ""

                    # Add positive indicators only for the first few checkboxes to avoid making the prompt too long
                    indicator_text = ""
                    if positive_indicators and len(checkbox_fields) < 20:  # Only if not too many checkboxes
                        indicator_text = f" [Indicators: {', '.join(positive_indicators[:3])}]" if positive_indicators else ""

                    # Include negative indicators for checkbox fields
                    negative_indicators = field_info.get("negative_indicators", [])
                    negative_indicator_text = ""
                    if negative_indicators and len(checkbox_fields) < 20: # Only if not too many checkboxes
                        negative_indicator_text = f" [Negative Indicators: {', '.join(negative_indicators[:3])}]" if negative_indicators else ""

                    if subsection:
                        prompt_parts.append(f"  - '{key}': [{subsection}] {desc}{synonym_text}{indicator_text}{negative_indicator_text}")
                    else:
                        prompt_parts.append(f"  - '{key}': {desc}{synonym_text}{indicator_text}{negative_indicator_text}")

        # Add section-aware instructions
        prompt_parts = add_section_aware_instructions(template_placeholder_contexts, prompt_parts)
    else:
        # For hierarchical context format, organize by section/subsection structure
        # This better handles the enhanced context from the outline file

        # Extract sections from context values
        sections = {}
        for key, context in template_placeholder_contexts.items():
            # Split context into parts (assuming section - subsection - description format)
            parts = context.split(" - ")
            section = parts[0] if parts else "General"

            if section not in sections:
                sections[section] = {}

            # Get subsection if available
            subsection = parts[1] if len(parts) > 1 else "General"
            if subsection not in sections[section]:
                sections[section][subsection] = []

            # Add field to the appropriate subsection
            sections[section][subsection].append((key, context))

        prompt_parts.append("\nTEMPLATE FIELDS TO FILL (organized by section and subsection):")

        for section, subsections in sorted(sections.items()):
            prompt_parts.append(f"\n## {section} SECTION:")

            for subsection, fields in sorted(subsections.items()):
                if subsection != "General":
                    prompt_parts.append(f"\n### {subsection} Subsection:")

                # Split fields into checkboxes and text fields
                checkbox_fields = [(k, c) for k, c in fields if k.endswith('_check')]
                text_fields = [(k, c) for k, c in fields if not k.endswith('_check')]

                if text_fields:
                    prompt_parts.append("TEXT FIELDS:")
                    for key, context in text_fields:
                        # Extract just the field description part
                        description = context.split(" - ")[-1] if " - " in context else context
                        prompt_parts.append(f"  - '{key}': {description}")

                if checkbox_fields:
                    prompt_parts.append("CHECKBOX FIELDS (must be YES or NO):")
                    for key, context in checkbox_fields:
                        # Extract just the field description part
                        description = context.split(" - ")[-1] if " - " in context else context
                        prompt_parts.append(f"  - '{key}': {description}")

    prompt_parts.append("\nYOUR TASK & RESPONSE FORMAT:")
    prompt_parts.append("Carefully analyze all provided information.")
    prompt_parts.append("For each TEMPLATE FIELD:")
    prompt_parts.append("  - If the field key ends with '_check' (a checkbox): Determine if it is confirmed as selected. Value must be \"YES\" or \"NO\". Prioritize SELECTED PDF ITEMS for these.")
    prompt_parts.append("  - If the field key does NOT end with '_check' (a text field): Extract the specific information from the FULL PDF TEXT using the field description as a guide. If the information cannot be found, the value should be an empty string (\"\").")
    prompt_parts.append("  - SPECIFIC INSTRUCTION for 'production_speed': Prioritize speed specifications mentioned *within the description of the primary selected machine* (e.g., a Monoblock) over general 'Projected Speed' sections if they differ. Look for phrases like 'up to X bottles/units per minute'.")
    prompt_parts.append("  - NOTE: 'Projected Speed' and 'Production Speed' refer to the same information - the rate at which the machine processes bottles/units, typically expressed in units per minute.")
    prompt_parts.append("Pay attention to bundled features within SELECTED PDF ITEMS. For example, if 'Monoblock Model ABC' description says 'Including: Feature X, Feature Y', then template fields for Feature X and Feature Y (if they are _check fields) should be YES.")
    prompt_parts.append("If a PDF item is general (e.g., 'Three (X 3) colours status beacon light') and the template has specific sub-features (e.g., 'Status Beacon Light: Red', 'Status Beacon Light: Yellow', 'Status Beacon Light: Green'), mark ALL corresponding specific sub-feature placeholders as YES.")
    prompt_parts.append("Be accurate and conservative. For checkboxes, if unsure, default to \"NO\". If an entire category of options (e.g., 'Street Fighter Tablet Counter') is NOT MENTIONED AT ALL in the PDF text or selected items, all its related checkboxes should be \"NO\".")
    prompt_parts.append("For text fields, if not found, use an empty string.")
    prompt_parts.append("  - For COMMENT fields (description contains 'Comment' or 'Comments'): these are user-entry fields. Always return empty string (\"\").")
    prompt_parts.append("Respond with a single, valid JSON object. The keys in the JSON MUST be ALL the TEMPLATE PLACEHOLDER KEYS listed above, and the values must be their extracted text or \"YES\"/\"NO\".")

    # Add context about General Order Acknowledgement structure to help with understanding
    prompt_parts.append("\nADDITIONAL CONTEXT ABOUT THE GENERAL ORDER ACKNOWLEDGEMENT (GOA) FORM:")
    prompt_parts.append("The GOA form is used in the packaging manufacturing industry to capture all specifications for a machine build.")
    prompt_parts.append("1. It starts with basic customer and project information (Proj #, Customer name, Machine type).")
    prompt_parts.append("2. It includes utility specifications (voltage, conformity certifications, country of destination).")
    prompt_parts.append("3. Material specifications define what components contact the product (metal parts usually SS304/316).")
    prompt_parts.append("4. Control & Programming sections define the automation system (PLC type, HMI size, etc.).")
    prompt_parts.append("5. Different sections cover specific functional modules (Filling System, Capping, Labeling, etc.).")
    prompt_parts.append("Pay close attention to the hierarchical structure of fields when determining YES/NO values for checkboxes.")

    # Add example JSON response format
    prompt_parts.append("\nEXAMPLE JSON RESPONSE FORMAT:")
    prompt_parts.append("""```json
{
  "machine_model": "LabelStar Model System 1",
  "production_speed": "60 units per minute",
  "barcode_scanner_check": "YES",
  "extended_conveyor_check": "NO",
  "customer_name": "ACME Corp",
  ... (other fields)
}
```""")

    prompt_parts.append("\nYour JSON Response:")

    prompt = "\n".join(prompt_parts)

    # print("\n----- LLM PROMPT (get_all_fields_via_llm) -----")
    # print(prompt)
    # print("--------------------------------------------\n")

    # Initialize with default values based on all template placeholders provided
    llm_response_data = {key: ("NO" if key.endswith("_check") else "") for key in template_placeholder_contexts.keys()}

    try:
        print("Sending comprehensive prompt to Gemini API...")
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
        response = GENERATIVE_MODEL.generate_content(prompt, safety_settings=safety_settings)

        cleaned_response_text = response.text.strip()
        if cleaned_response_text.startswith("```json"):
            cleaned_response_text = cleaned_response_text[7:]
            if cleaned_response_text.endswith("```"):
                cleaned_response_text = cleaned_response_text[:-3]
        cleaned_response_text = cleaned_response_text.strip()

        try:
            parsed_llm_output = json.loads(cleaned_response_text)
            if isinstance(parsed_llm_output, dict):
                # Validate the response if using schema format
                if using_schema_format:
                    validation_errors = validate_llm_response(parsed_llm_output, template_placeholder_contexts)
                    if validation_errors:
                        print("Validation errors found in LLM response:")
                        for field, errors in validation_errors.items():
                            print(f"  - '{field}': {', '.join(errors)}")
                        # Continue anyway - we'll use what we got

                # Update the response data with values
                for key, value in parsed_llm_output.items():
                    if key in llm_response_data: # Only update keys that were expected
                        is_checkbox = (using_schema_format and
                                      isinstance(template_placeholder_contexts.get(key), dict) and
                                      template_placeholder_contexts.get(key, {}).get("type") == "boolean") or \
                                      (not using_schema_format and key.endswith("_check"))

                        if is_checkbox:
                            if isinstance(value, str) and value.upper() in ["YES", "NO"]:
                                llm_response_data[key] = value.upper()
                            # else: keep default "NO"
                        else: # It's a text field
                            llm_response_data[key] = str(value) # Assign extracted text
            else:
                print(f"Warning: LLM response was not a JSON dictionary: {parsed_llm_output}")
        except json.JSONDecodeError as e:
            print(f"Error decoding LLM JSON response: {e}")
            print(f"LLM Response Text was: {repr(cleaned_response_text)}")
    except Exception as e:
        print(f"Error communicating with Gemini API or processing response: {e}")
        traceback.print_exc()

    # Apply post-processing rules to improve the data
    corrected_data = apply_post_processing_rules(
        llm_response_data,
        template_placeholder_contexts,
        full_pdf_text,
        selected_pdf_descriptions,
    )
    return corrected_data


def get_llm_chat_update(current_data: Dict[str, str],
                        user_instruction: str,
                        selected_pdf_descriptions: List[str],
                        template_placeholder_contexts: Dict[str, str],
                        full_pdf_text: str,
                        user_id: int | None = None) -> Dict[str, str]:
    """
    Takes current data, user instruction, and original contexts, then asks LLM for an updated data dictionary
    covering ALL fields (text and checkboxes).

    Args:
        current_data: Current field values before update
        user_instruction: User's instruction for what to change
        selected_pdf_descriptions: List of item descriptions from PDF
        template_placeholder_contexts: Template field contexts/descriptions
        full_pdf_text: Full PDF text for reference

    Returns:
        Updated dictionary with corrected field values
    """
    GENERATIVE_MODEL = get_generative_model(user_id=user_id)
    if GENERATIVE_MODEL is None:
        if not configure_gemini_client(user_id=user_id):
            print("LLM client not configured for chat update. Returning current data.")
            return current_data

    pdf_query_hints: List[str] = [user_instruction]
    pdf_query_hints.extend(selected_pdf_descriptions)
    for field_key, context in template_placeholder_contexts.items():
        pdf_query_hints.append(field_key.replace("_", " "))
        if isinstance(context, dict):
            for hint_key in ("description", "section", "subsection"):
                hint_val = context.get(hint_key)
                if isinstance(hint_val, str) and hint_val.strip():
                    pdf_query_hints.append(hint_val)
        elif isinstance(context, str) and context.strip():
            pdf_query_hints.append(context)

    rag_pdf_text, rag_context_note = build_retrieved_pdf_context(
        full_pdf_text,
        pdf_query_hints,
        max_context_chars=45000,
    )

    prompt_parts = [
        "You are an AI assistant helping to correct a technical equipment order template that was previously filled (partially or fully).",
        "The user will provide an instruction to change one or more field values.",
        "\nPREVIOUSLY FILLED DATA (this is the data you need to update):",
        json.dumps(current_data, indent=2),
        "\nUSER'S CORRECTION INSTRUCTION:",
        f">>> {user_instruction}",
        "\nORIGINAL CONTEXT FOR YOUR REFERENCE (use this if the user's instruction is ambiguous or refers to original details):",
        "1. SELECTED PDF ITEMS (primary evidence for checkbox options):"
    ]
    if not selected_pdf_descriptions:
        prompt_parts.append("  (No specific items were identified as selected from tables.)")
    else:
        for i, desc in enumerate(selected_pdf_descriptions):
            prompt_parts.append(f"  - PDF Item {i+1}: {desc}")

    prompt_parts.append("\n2. FULL PDF TEXT (retrieved relevant chunks from the quote):")
    prompt_parts.append(rag_context_note)
    prompt_parts.append(rag_pdf_text)

    prompt_parts.append("\n3. TEMPLATE FIELDS (Placeholder Key: Description from template that the user might refer to):")
    placeholder_list_for_prompt = []
    for key, context in template_placeholder_contexts.items():
        field_type = "Checkbox (YES/NO)" if key.endswith("_check") else "Text Field"
        placeholder_list_for_prompt.append(f"  - '{key}' (Type: {field_type}): '{context}'")
    if not placeholder_list_for_prompt:
        prompt_parts.append("  (No template fields provided for context.)")
    else:
        for item_for_prompt in placeholder_list_for_prompt:
            prompt_parts.append(item_for_prompt)

    prompt_parts.append("\nYOUR TASK:")
    prompt_parts.append("1. Understand the USER'S CORRECTION INSTRUCTION.")
    prompt_parts.append("2. If the instruction refers to a template field by its description, identify the corresponding Placeholder Key.")
    prompt_parts.append("3. Modify the PREVIOUSLY FILLED DATA according to the user's instruction. For text fields, extract the new value from the FULL PDF TEXT if the user implies it (e.g., 'Correct the customer name').")
    prompt_parts.append("4. IMPORTANT: Your response MUST be a single, valid JSON object.")
    prompt_parts.append("5. This JSON object MUST contain ALL the original placeholder keys listed in the TEMPLATE FIELDS section above.")
    prompt_parts.append("   - For keys ending with '_check', the value MUST be \"YES\" or \"NO\".")
    prompt_parts.append("   - For other keys (text fields), the value should be the extracted string, or an empty string if not found/applicable.")
    prompt_parts.append("   Do NOT omit any original keys. Do NOT add new keys.")
    prompt_parts.append("\nUpdated JSON Response:")

    prompt = "\n".join(prompt_parts)

    print("\n----- LLM CHAT PROMPT -----")
    print(prompt)
    print("-------------------------")

    updated_data = current_data.copy()

    try:
        print("Sending correction prompt to Gemini API...")
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
        response = GENERATIVE_MODEL.generate_content(prompt, safety_settings=safety_settings)

        print("\n----- LLM CHAT RAW RESPONSE -----")
        print(response.text)
        print("----------------------------")

        cleaned_response_text = response.text.strip()
        if cleaned_response_text.startswith("```json"):
            cleaned_response_text = cleaned_response_text[7:]
            if cleaned_response_text.endswith("```"):
                cleaned_response_text = cleaned_response_text[:-3]
        cleaned_response_text = cleaned_response_text.strip()

        try:
            parsed_llm_update = json.loads(cleaned_response_text)
            if isinstance(parsed_llm_update, dict):
                for key, value in parsed_llm_update.items():
                    if key in updated_data and key.endswith("_check"):
                        if isinstance(value, str) and value.upper() in ["YES", "NO"]:
                            updated_data[key] = value.upper()
                        else:
                            print(f"Warning: LLM provided invalid value '{value}' for key '{key}'. Keeping previous: '{updated_data[key]}'.")
                    elif key in updated_data: # For text fields (not ending in _check)
                        updated_data[key] = str(value)
            else:
                print(f"Warning: LLM chat update response was not a JSON dictionary: {parsed_llm_update}")
        except json.JSONDecodeError as e:
            print(f"Error decoding LLM chat update JSON response: {e}")
            print(f"LLM Chat Update Response Text was: {repr(cleaned_response_text)}")

    except Exception as e:
        print(f"Error in get_llm_chat_update: {e}")
        traceback.print_exc()

    # Apply post-processing rules to improve the data
    corrected_data = apply_post_processing_rules(
        updated_data,
        template_placeholder_contexts,
        full_pdf_text,
        selected_pdf_descriptions,
    )

    return corrected_data


def map_crm_to_document_via_llm(crm_client_data: Dict[str, Any],
                                crm_priced_items: List[Dict[str, Any]],
                                document_template_contexts: Dict[str, str],
                                document_type_hint: str,
                                user_id: int | None = None,
                                # full_original_pdf_text: Optional[str] = None # For future LLM calls if CRM data is not enough
                               ) -> Dict[str, str]:
    """
    Uses an LLM to map CRM data (client details and priced items) to the placeholders
    of a specified document template (e.g., Packing Slip, Commercial Invoice).

    Args:
        crm_client_data: Dictionary of the client's main details from the CRM.
        crm_priced_items: List of dictionaries for their priced items from the CRM.
        document_template_contexts: Dict of {{placeholder}} -> "context string" for the target document.
        document_type_hint: String like "Packing Slip" or "Commercial Invoice" to guide the LLM.
        # full_original_pdf_text: Optional full text of the original quote if LLM needs to refer back.

    Returns:
        A dictionary ready to be used by doc_filler.py for the target document.
    """
    GENERATIVE_MODEL = get_generative_model(user_id=user_id)
    if GENERATIVE_MODEL is None:
        if not configure_gemini_client(user_id=user_id):
            print(f"LLM client not configured for {document_type_hint} generation. Returning empty data.")
            return {key: "" for key in document_template_contexts.keys()} # Default all to empty

    prompt_parts = [
        f"You are an AI assistant preparing data to fill a '{document_type_hint}' document.",
        "You will be given data from a CRM (Customer Relationship Management) system and a list of fields from the target document template.",

        "\nCRM DATA:",
        "1. Client Details:",
        json.dumps(crm_client_data, indent=2),
        "\n2. Priced Line Items from Original Quote:"
    ]
    if not crm_priced_items:
        prompt_parts.append("  (No priced line items found in CRM for this client/quote.)")
    else:
        for i, item in enumerate(crm_priced_items):
            prompt_parts.append(f"  - Item {i+1}: Description='{item.get('item_description')}', Quantity='{item.get('item_quantity')}', Price String='{item.get('item_price_str')}', Numeric Price='{item.get('item_price_numeric')}'") # Add H.S. Code later if available

    prompt_parts.append(f"\nTARGET DOCUMENT TEMPLATE FIELDS ('{document_type_hint}' - Placeholder Key: Description from template):")
    placeholder_list_for_prompt = []
    for key, context in document_template_contexts.items():
        placeholder_list_for_prompt.append(f"  - '{key}': '{context}'")
    if not placeholder_list_for_prompt:
        prompt_parts.append("  (No template fields provided for the target document.)")
        return {}
    for item_for_prompt in placeholder_list_for_prompt:
        prompt_parts.append(item_for_prompt)

    prompt_parts.append("\nYOUR TASK:")
    prompt_parts.append(f"Based on the provided CRM DATA, determine the correct value for each TARGET DOCUMENT TEMPLATE FIELD.")
    prompt_parts.append("  - Directly map CRM fields (like customer_name, quote_ref, addresses, customer_po) to corresponding template fields.")
    prompt_parts.append("  - For line items in the template (e.g., item_1_desc, item_1_qty), populate them sequentially from the CRM Priced Line Items. If the template has more line item placeholders than available items, leave the extra ones as empty strings.")
    prompt_parts.append("  - For fields specific to the new document that are not directly in the CRM (e.g., '{document_type_hint} Number', 'Ship Date', 'AX Number', 'OX Number', 'Incoterm', 'Via', 'Serial Number'):")
    prompt_parts.append("    - If a sensible default is obvious (like today's date for 'Ship Date', or deriving '{document_type_hint} Number' from quote_ref like 'PS-[quote_ref]'), generate it.")
    prompt_parts.append("    - Otherwise, use \"TBD\" or an empty string for such fields if the information isn't in the CRM.")
    prompt_parts.append("  - Ensure dates are formatted as YYYY-MM-DD if applicable.")
    prompt_parts.append("  - For any checkbox fields (ending in '_check'), determine their YES/NO value based on CRM data or common sense for the document type.")

    prompt_parts.append("RESPONSE FORMAT:")
    prompt_parts.append("Respond with a single, valid JSON object. The keys in the JSON MUST be ALL the TARGET DOCUMENT TEMPLATE PLACEHOLDER KEYS, and the values should be the data to fill them with.")
    prompt_parts.append("\nYour JSON Response:")

    prompt = "\n".join(prompt_parts)

    # print(f"\n----- LLM PROMPT ({document_type_hint} Data Mapping) -----")
    # print(prompt)
    # print("----------------------------------------------------\n")

    # Initialize with default values based on all target template placeholders
    output_data_for_document = {key: ("NO" if key.endswith("_check") else "") for key in document_template_contexts.keys()}

    try:
        print(f"Sending '{document_type_hint}' data mapping prompt to Gemini API...")
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]
        response = GENERATIVE_MODEL.generate_content(prompt, safety_settings=safety_settings)

        cleaned_response_text = response.text.strip()
        if cleaned_response_text.startswith("```json"):
            cleaned_response_text = cleaned_response_text[7:]
            if cleaned_response_text.endswith("```"):
                cleaned_response_text = cleaned_response_text[:-3]
        cleaned_response_text = cleaned_response_text.strip()

        try:
            parsed_llm_output = json.loads(cleaned_response_text)
            if isinstance(parsed_llm_output, dict):
                for key, value in parsed_llm_output.items():
                    if key in output_data_for_document: # Only update keys that were expected from the target template
                        if key.endswith("_check"):
                            if isinstance(value, str) and value.upper() in ["YES", "NO"]:
                                output_data_for_document[key] = value.upper()
                        else: # It's a text field
                            output_data_for_document[key] = str(value) # Assign extracted/generated text
            else:
                print(f"Warning: LLM response for {document_type_hint} was not a JSON dictionary.")
        except json.JSONDecodeError as e:
            print(f"Error decoding LLM JSON response for {document_type_hint}: {e}")
            print(f"LLM Response Text was: {repr(cleaned_response_text)}")
    except Exception as e:
        print(f"Error generating data for {document_type_hint}: {e}")
        traceback.print_exc()

    print(f"Prepared data for {document_type_hint}:", json.dumps(output_data_for_document, indent=2))
    return output_data_for_document


def get_machine_specific_fields_via_llm(machine_data: Dict,
                                       common_items: List[Dict],
                                       template_placeholder_contexts: Dict[str, Any], # Can be Dict[str, str] or Dict[str, Dict]
                                       full_pdf_text: str,
                                       template_metadata: Optional[Dict] = None,
                                       user_id: int | None = None) -> Dict[str, str]:
    """
    Uses LangChain to create robust, schema-driven extraction chains to fill
    fields based on machine data, common items, and full PDF text.

    Implements a 'Divide and Conquer' strategy by splitting fields into logical groups
    and running multiple smaller LLM calls to improve accuracy and focus.

    Args:
        machine_data: Dictionary containing machine information (name, main_item, add_ons)
        common_items: List of common/shared items for this quote
        template_placeholder_contexts: Template field contexts (string or dict schema)
        full_pdf_text: Full text of the PDF document
        template_metadata: Optional metadata about the template

    Returns:
        Dictionary mapping field keys to extracted values
    """
    GENERATIVE_MODEL = get_generative_model(user_id=user_id)
    if GENERATIVE_MODEL is None:
        if not configure_gemini_client(user_id=user_id):
            print("LLM client not configured. Returning empty data.")
            return {key: ("NO" if key.endswith("_check") else "") for key in template_placeholder_contexts.keys()}

    configured_model_name = get_configured_model_name()

    # 1. Categorize fields into groups
    grouped_contexts = {group: {} for group in FIELD_GROUPS.keys()}

    # Helper to find group
    def find_group(key, context=None):
        # Strategy 1: Use section name from schema context if available
        if isinstance(context, dict):
            section = str(context.get("section", "")).strip().lower()
            # Map sections to groups
            if section and any(
                x in section for x in ["control", "electrical", "program", "guard", "code", "coding", "inspect"]
            ):
                return "Controls & Electrical"

            if section and any(
                x in section for x in ["liquid", "fill", "bottle", "handling", "tablet", "cotton", "desiccant", "gas"]
            ):
                return "Liquid Filling & Handling"

            if section and any(
                x in section for x in ["cap", "label", "induction", "sleeve", "conveyor", "plug", "belt", "shrink", "retorquer"]
            ):
                return "Capping, Labeling & Other"

        # Strategy 2: Fallback to key prefixes (backward compatibility)
        for group_name, rules in FIELD_GROUPS.items():
            if key in rules["exact"]:
                return group_name
            for prefix in rules["prefixes"]:
                if key.startswith(prefix):
                    return group_name

        # Default for sections/keys that are not covered by existing heuristics.
        return "General & Utility"

    for key, context in template_placeholder_contexts.items():
        group = find_group(key, context)
        grouped_contexts[group][key] = context

    # Remove empty groups to avoid unnecessary calls
    active_groups = {k: v for k, v in grouped_contexts.items() if v}
    largest_group_size = max((len(group) for group in active_groups.values()), default=0)
    if largest_group_size > MAX_FIELDS_PER_EXTRACTION_GROUP:
        print(
            f"[WARN] Large extraction group detected ({largest_group_size} fields). "
            f"Rebalancing to max {MAX_FIELDS_PER_EXTRACTION_GROUP} fields per group."
        )
        active_groups = _rebalance_grouped_contexts(
            active_groups,
            max_fields_per_group=MAX_FIELDS_PER_EXTRACTION_GROUP,
        )
        group_sizes = [len(group) for group in active_groups.values()]
        print(
            f"[OK] Rebalanced extraction into {len(active_groups)} groups "
            f"(min={min(group_sizes)}, max={max(group_sizes)} fields)."
        )

    all_extracted_data = {}

    # Determine machine type once for few-shot learning
    machine_name = machine_data.get("machine_name", "")
    machine_type = determine_machine_type(machine_name)

    # Prepare input data common to all groups
    main_item_desc = machine_data.get("main_item", {}).get("description", "")
    add_on_descs = "; ".join([item.get("description", "") for item in machine_data.get("add_ons", [])])
    common_item_descs = "; ".join([item.get("description", "") for item in common_items])

    quote_library_path = None
    if isinstance(template_metadata, dict):
        quote_library_path = template_metadata.get("quote_library_path")

    quote_library_context = ""
    quote_library_matches: List[str] = []
    try:
        quote_library_context, quote_library_matches = get_quote_library_context(
            machine_name=machine_name,
            main_item_desc=main_item_desc,
            add_on_descs=add_on_descs,
            quote_library_path=quote_library_path,
        )
        if quote_library_matches:
            print(f"Matched QUOTE_LIBRARY specs: {', '.join(quote_library_matches)}")
    except Exception as library_error:
        print(f"QUOTE_LIBRARY lookup failed: {library_error}")

    # 2. Iterate through each group and run extraction via direct generate_content()
    #    (monolithic prompt style — no LangChain/Pydantic, which causes null defaults)
    import time

    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
    ]

    for group_name, group_contexts in active_groups.items():
        print(f"\n--- Processing Group: {group_name} ({len(group_contexts)} fields) ---")
        group_start_time = time.time()

        using_schema_format = isinstance(next(iter(group_contexts.values()), {}), dict)

        # --- Build RAG hints for this group ---
        group_query_hints: List[str] = [
            machine_name, main_item_desc, add_on_descs,
            common_item_descs, quote_library_context, group_name,
        ]
        for key, context in group_contexts.items():
            group_query_hints.append(key.replace("_", " "))
            if isinstance(context, dict):
                for hint_key in ("description", "section", "subsection"):
                    hint_val = context.get(hint_key)
                    if isinstance(hint_val, str) and hint_val.strip():
                        group_query_hints.append(hint_val)
                for hint_list_key in ("synonyms", "positive_indicators"):
                    hint_values = context.get(hint_list_key, [])
                    if isinstance(hint_values, list):
                        group_query_hints.extend(str(v) for v in hint_values[:6] if v)
            elif isinstance(context, str) and context.strip():
                group_query_hints.append(context)

        # --- RAG: trim PDF per group ---
        _rag_max = _safe_positive_int_env("LLM_RAG_MAX_CHARS_PER_GROUP", 40000)
        if full_pdf_text and len(full_pdf_text) > _rag_max:
            pdf_context, _rag_note = build_retrieved_pdf_context(
                full_pdf_text, group_query_hints, max_context_chars=_rag_max,
            )
            print(f"  [RAG] Trimmed PDF from {len(full_pdf_text)} to {len(pdf_context)} chars")
        else:
            pdf_context = full_pdf_text or ""

        # --- Build field listing (monolithic prompt style) ---
        field_lines: List[str] = []
        text_fields: List[tuple] = []
        checkbox_fields: List[tuple] = []
        for key, ctx in group_contexts.items():
            is_checkbox = key.endswith("_check") or (
                using_schema_format and isinstance(ctx, dict) and ctx.get("type") == "boolean"
            )
            if is_checkbox:
                checkbox_fields.append((key, ctx))
            else:
                text_fields.append((key, ctx))

        if text_fields:
            field_lines.append("TEXT FIELDS (value should be the extracted text, or empty string \"\" if not found):")
            for key, ctx in text_fields:
                if isinstance(ctx, dict):
                    desc = ctx.get("description", key)
                    subsection = ctx.get("subsection", "")
                    if subsection:
                        field_lines.append(f"  - '{key}': [{subsection}] {desc}")
                    else:
                        field_lines.append(f"  - '{key}': {desc}")
                else:
                    field_lines.append(f"  - '{key}': {ctx}")

        if checkbox_fields:
            field_lines.append("\nCHECKBOX FIELDS (value MUST be \"YES\" or \"NO\"):")
            for key, ctx in checkbox_fields:
                if isinstance(ctx, dict):
                    desc = ctx.get("description", key)
                    subsection = ctx.get("subsection", "")
                    synonyms = ctx.get("synonyms", [])
                    pos_ind = ctx.get("positive_indicators", [])
                    neg_ind = ctx.get("negative_indicators", [])
                    extras = ""
                    if synonyms:
                        extras += f" [Alt: {', '.join(synonyms[:5])}]"
                    if pos_ind and len(checkbox_fields) < 80:
                        extras += f" [+: {', '.join(pos_ind[:3])}]"
                    if neg_ind and len(checkbox_fields) < 80:
                        extras += f" [-: {', '.join(neg_ind[:3])}]"
                    if subsection:
                        field_lines.append(f"  - '{key}': [{subsection}] {desc}{extras}")
                    else:
                        field_lines.append(f"  - '{key}': {desc}{extras}")
                else:
                    field_lines.append(f"  - '{key}': {ctx}")

        fields_block = "\n".join(field_lines)

        # --- Build the prompt (monolithic style — no Pydantic format instructions) ---
        prompt_parts = [
            f"You are an AI assistant extracting information from a packaging machinery quote PDF to fill the '{group_name}' section of a General Order Acknowledgement (GOA) form.",
            "",
            "MACHINE CONTEXT:",
            f"  Machine Name: {machine_name}",
            f"  Main Item: {main_item_desc}",
            f"  Add-ons: {add_on_descs}",
            f"  Common/Shared Items: {common_item_descs}",
        ]
        if quote_library_context:
            prompt_parts.append(f"  QUOTE_LIBRARY Reference: {quote_library_context}")

        prompt_parts.extend([
            "",
            "FULL PDF TEXT (search thoroughly — information may appear in any section):",
            pdf_context,
            "",
            f"TEMPLATE FIELDS TO FILL FOR '{group_name}':",
            fields_block,
            "",
            "EXTRACTION RULES:",
            "- For CHECKBOX fields: Output \"YES\" if evidence exists in the PDF text, selected items, or add-on descriptions. Default to \"NO\" if not mentioned.",
            "- For TEXT fields: Extract the value from the PDF. Use empty string \"\" if not found. Do NOT use null, \"N/A\", \"TBD\", or \"Not specified\".",
            "- For COMMENT fields (field description contains 'Comment' or 'Comments'): these are user-entry fields. Always return empty string \"\".",
            "- Pay attention to bundled features: if a machine description says 'Including: Feature X, Feature Y', mark those features as YES.",
            "- If a PDF item is general (e.g., 'Three colours status beacon light') and the template has specific sub-features, mark ALL corresponding sub-features as YES.",
            "- Search the ENTIRE PDF text — specifications may appear in different sections than expected.",
            "- QUOTE_LIBRARY specs are reference only; if the PDF conflicts, prioritize the PDF.",
            "",
            "RESPONSE FORMAT:",
            "Respond with a single valid JSON object. The keys MUST be ALL the template field keys listed above.",
            "- Checkbox values: \"YES\" or \"NO\" (strings, never null)",
            "- Text values: extracted string or \"\" (never null)",
            "Do NOT omit any keys. Do NOT add extra keys.",
            "",
            "Your JSON Response:",
        ])

        # --- Enhance with few-shot examples ---
        prompt_build_start = time.time()
        if DISABLE_ALL_FEW_SHOT:
            enhanced_prompt_parts = prompt_parts
        elif ENHANCED_FEW_SHOT_AVAILABLE:
            try:
                enhanced_prompt_parts = enhance_prompt_with_semantic_examples(
                    prompt_parts=prompt_parts,
                    machine_data=machine_data,
                    template_placeholder_contexts=group_contexts,
                    common_items=common_items,
                    full_pdf_text=full_pdf_text,
                    max_examples_per_field=1,
                )
            except Exception:
                enhanced_prompt_parts = prompt_parts
        else:
            try:
                enhanced_prompt_parts = enhance_prompt_with_few_shot_examples(
                    prompt_parts=prompt_parts,
                    machine_data=machine_data,
                    template_placeholder_contexts=group_contexts,
                    common_items=common_items,
                    full_pdf_text=full_pdf_text,
                    max_examples_per_field=1,
                )
            except Exception:
                enhanced_prompt_parts = prompt_parts

        prompt = "\n".join(enhanced_prompt_parts)
        prompt_build_time = time.time() - prompt_build_start
        if not DISABLE_ALL_FEW_SHOT:
            print(f"  Prompt built in {prompt_build_time:.1f}s")

        print(f"  [DEBUG] pdf_context: {len(pdf_context)} chars, fields: {len(group_contexts)}")

        # --- Call Gemini API directly (like the monolithic approach) ---
        try:
            print(f"  Sending request to Gemini API...")
            api_start_time = time.time()
            response = GENERATIVE_MODEL.generate_content(prompt, safety_settings=safety_settings)
            api_elapsed = time.time() - api_start_time

            if api_elapsed > 60:
                print(f"  ⚠️  Response received in {api_elapsed:.1f}s (slower than usual)")
            else:
                print(f"  ✓ Response received in {api_elapsed:.1f}s")

            # --- Parse JSON response (monolithic style) ---
            cleaned = response.text.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            parsed = json.loads(cleaned)
            if not isinstance(parsed, dict):
                print(f"  ⚠️  Response was not a JSON dict, got: {type(parsed)}")
                parsed = {}

            # Process results
            for key, value in parsed.items():
                if key not in group_contexts:
                    continue
                ctx = group_contexts[key]
                is_checkbox = key.endswith("_check") or (
                    using_schema_format and isinstance(ctx, dict) and ctx.get("type") == "boolean"
                )
                if is_checkbox:
                    if isinstance(value, str) and value.upper() in ("YES", "TRUE", "1"):
                        all_extracted_data[key] = "YES"
                    elif isinstance(value, bool) and value:
                        all_extracted_data[key] = "YES"
                    else:
                        all_extracted_data[key] = "NO"
                else:
                    all_extracted_data[key] = str(value) if value is not None else ""

            # Fill any missing keys with defaults
            for key in group_contexts:
                if key not in all_extracted_data:
                    is_checkbox = key.endswith("_check") or (
                        using_schema_format and isinstance(group_contexts[key], dict)
                        and group_contexts[key].get("type") == "boolean"
                    )
                    all_extracted_data[key] = "NO" if is_checkbox else ""

            non_empty = sum(1 for k in group_contexts if all_extracted_data.get(k) not in (None, "", "NO"))
            group_total_time = time.time() - group_start_time
            print(f"  ✓ Group completed in {group_total_time:.1f}s ({non_empty}/{len(group_contexts)} fields filled)")

        except json.JSONDecodeError as e:
            print(f"  ⚠️  JSON parse error: {e}")
            print(f"  Response text (first 300 chars): {repr(response.text[:300])}")
            # Retry once
            try:
                print(f"  Retrying group {group_name}...")
                response = GENERATIVE_MODEL.generate_content(prompt, safety_settings=safety_settings)
                cleaned = response.text.strip()
                if cleaned.startswith("```json"):
                    cleaned = cleaned[7:]
                if cleaned.startswith("```"):
                    cleaned = cleaned[3:]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
                parsed = json.loads(cleaned.strip())
                if isinstance(parsed, dict):
                    for key, value in parsed.items():
                        if key not in group_contexts:
                            continue
                        ctx = group_contexts[key]
                        is_checkbox = key.endswith("_check") or (
                            using_schema_format and isinstance(ctx, dict) and ctx.get("type") == "boolean"
                        )
                        if is_checkbox:
                            all_extracted_data[key] = "YES" if (isinstance(value, str) and value.upper() in ("YES", "TRUE", "1")) else "NO"
                        else:
                            all_extracted_data[key] = str(value) if value is not None else ""
                    print(f"  ✓ Retry succeeded")
            except Exception as retry_err:
                print(f"  ✗ Retry also failed: {retry_err}")

            # Fill missing with defaults
            for key in group_contexts:
                if key not in all_extracted_data:
                    all_extracted_data[key] = "NO" if key.endswith("_check") else ""

        except Exception as e:
            print(f"  Error during extraction for group {group_name}: {e}")
            for key in group_contexts:
                if key not in all_extracted_data:
                    all_extracted_data[key] = "NO" if key.endswith("_check") else ""

    # Warn if extraction looks empty
    total_fields = len(all_extracted_data)
    filled_fields = sum(1 for v in all_extracted_data.values() if v not in (None, "", "NO"))
    fill_pct = (filled_fields / total_fields * 100) if total_fields else 0
    print(f"\n--- Extraction summary: {filled_fields}/{total_fields} fields filled ({fill_pct:.0f}%) ---")
    if fill_pct < 5:
        print("  ⚠️  WARNING: Almost no fields were extracted! The LLM may not be processing the PDF content.")

    # 3. Apply post-processing rules to the combined data
    print("\nApplying post-processing rules to combined data...")

    # Construct selected_pdf_descriptions for post-processing
    selected_pdf_descriptions = []
    if main_item_desc: # Add main item description
        selected_pdf_descriptions.append(main_item_desc)
    selected_pdf_descriptions.extend([item.get("description", "") for item in machine_data.get("add_ons", []) if item.get("description")])
    selected_pdf_descriptions.extend([item.get("description", "") for item in common_items if item.get("description")])

    final_data = apply_post_processing_rules(
        all_extracted_data,
        template_placeholder_contexts,
        full_pdf_text,
        selected_pdf_descriptions,
    )

    # If this is a SortStar machine, enforce the basic system selection
    if machine_type == "sortstar":
        print("Enforcing SortStar basic system selection...")
        basic_system_selection = select_sortstar_basic_system(machine_data, full_pdf_text)
        final_data.update(basic_system_selection)
        print("SortStar basic system selection applied.")

    final_data, schema_notes = sanitize_extracted_fields(
        extracted_data=final_data,
        expected_schema=template_placeholder_contexts,
    )
    if schema_notes:
        print("Schema validation adjusted extracted fields:")
        for field_name, notes in schema_notes.items():
            print(f"  - {field_name}: {', '.join(notes)}")

    # Store confident outputs so future runs benefit from richer few-shot data
    _persist_machine_few_shot_examples(
        machine_data=machine_data,
        common_items=common_items,
        full_pdf_text=full_pdf_text,
        extracted_fields=final_data,
        machine_type=machine_type,
    )

    return final_data


def get_machine_specific_fields_with_confidence(
    machine_data: Dict,
    common_items: List[Dict],
    template_placeholder_contexts: Dict[str, Any],
    full_pdf_text: str,
    template_metadata: Optional[Dict] = None,
    user_id: int | None = None,
) -> Tuple[Dict[str, str], Dict[str, float], List[Dict[str, Any]]]:
    """
    Enhanced version of get_machine_specific_fields_via_llm that also returns
    confidence scores and field dependency suggestions.

    Args:
        machine_data: Dictionary containing machine information
        common_items: List of common items
        template_placeholder_contexts: Template field contexts
        full_pdf_text: Full PDF text
        template_metadata: Optional template metadata

    Returns:
        Tuple containing:
        - Dict[str, str]: Extracted field values
        - Dict[str, float]: Confidence scores for each field (0.0-1.0)
        - List[Dict]: Field dependency suggestions/warnings
    """
    # First, run the standard extraction
    extracted_data = get_machine_specific_fields_via_llm(
        machine_data=machine_data,
        common_items=common_items,
        template_placeholder_contexts=template_placeholder_contexts,
        full_pdf_text=full_pdf_text,
        template_metadata=template_metadata,
        user_id=user_id,
    )

    # Estimate confidence for each field
    print("\n--- Estimating field confidence scores ---")
    confidence_scores = estimate_extraction_confidence(
        extracted_data=extracted_data,
        template_contexts=template_placeholder_contexts,
        full_pdf_text=full_pdf_text,
        machine_data=machine_data,
        common_items=common_items
    )

    # Validate field dependencies and get suggestions
    print("\n--- Validating field dependencies ---")
    updated_data, updated_confidence, suggestions = validate_field_dependencies(
        extracted_data=extracted_data,
        confidence_scores=confidence_scores
    )

    if suggestions:
        print(f"Field dependency validation found {len(suggestions)} suggestion(s)/warning(s):")
        for s in suggestions:
            print(f"  [{s['type'].upper()}] {s['field']}: {s['reason']}")

    return updated_data, updated_confidence, suggestions


def _persist_machine_few_shot_examples(
    machine_data: Dict[str, Any],
    common_items: List[Dict[str, Any]],
    full_pdf_text: str,
    extracted_fields: Dict[str, str],
    machine_type: str,
) -> None:
    """
    Save high-confidence model outputs so they can serve as future few-shot examples.

    Args:
        machine_data: Dictionary containing machine information
        common_items: List of common/shared items
        full_pdf_text: Full PDF text content
        extracted_fields: Dictionary of extracted field values
        machine_type: Type of machine (e.g., "sortstar", "default")
    """
    if not extracted_fields or not full_pdf_text:
        return

    template_type = "sortstar" if "sortstar" in machine_type else "default"
    machine_name = machine_data.get("machine_name", "machine")
    saved_count = 0

    manager = None
    if ENHANCED_FEW_SHOT_AVAILABLE and get_few_shot_manager is not None:
        try:
            manager = get_few_shot_manager()  # type: ignore[misc]
        except Exception as manager_error:
            print(f"Unable to initialize FewShotManager cache: {manager_error}")
            manager = None

    # Quick rejection set for common LLM non-answers (checked before DB round-trip)
    _QUICK_REJECT = {
        "n/a", "na", "none", "null", "unknown", "not found", "not specified",
        "not provided", "not available", "not mentioned", "see quote",
        "pending", "tbd", "-", "--", "---", "...", "???", "placeholder",
    }

    for field_name, raw_value in extracted_fields.items():
        value = raw_value.strip() if isinstance(raw_value, str) else ""
        if not value:
            continue

        # Fast pre-filter: reject obvious placeholder/non-answer values
        if value.lower() in _QUICK_REJECT:
            continue

        # Only persist checkbox fields when we detected a positive assertion.
        if field_name.endswith("_check"):
            normalized_checkbox = value.upper()
            if normalized_checkbox != "YES":
                continue
            value_to_store = normalized_checkbox
        else:
            # Avoid polluting the example base with extremely short strings
            if len(value) < 3:
                continue
            value_to_store = value

        success = save_successful_extraction_as_example(
            field_name=field_name,
            field_value=value_to_store,
            machine_data=machine_data,
            common_items=common_items,
            full_pdf_text=full_pdf_text,
            machine_type=machine_type,
            template_type=template_type,
            confidence_score=0.75,
        )

        if success:
            saved_count += 1
            if manager:
                try:
                    manager.invalidate_cache(machine_type, template_type, field_name)
                except Exception as cache_error:
                    print(f"Unable to refresh semantic cache for {field_name}: {cache_error}")

    if saved_count:
        print(f"Saved {saved_count} automatic few-shot example(s) for {machine_name}.")
