"""Pure backend services extracted from Streamlit processing workflows."""

from __future__ import annotations

import json
import os
import re
import sqlite3
import tempfile
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
from src.llm import configure_gemini_client, get_machine_specific_fields_with_confidence
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

        client_info: dict[str, Any] = {
            "quote_ref": quote_ref,
            "customer_name": "",
            "machine_model": machine_model_guess,
            "country_destination": "",
            "sold_to_address": "",
            "ship_to_address": "",
            "telephone": "",
            "customer_contact_person": "",
            "customer_po": "",
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
    """Run LLM extraction and return structured data without session state."""
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
    items = _items_from_machine_payloads(machines)
    if not items:
        items = _items_from_priced_rows(load_priced_items_for_quote(quote_ref))
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
