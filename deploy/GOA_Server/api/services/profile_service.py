"""Pure profile extraction services migrated from Streamlit workflow."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from api.services._doc_helpers import write_temp_file
from src.llm.client import configure_gemini_client, get_generative_model, genai
from src.utils.db import save_client_info, save_document_content, save_machines_data, save_priced_items
from src.utils.pdf_utils import extract_full_pdf_text, extract_line_item_details, identify_machines_from_items


def _extract_standard_fields_via_llm(full_text: str, fallback_quote_ref: str) -> dict[str, str]:
    """Best-effort LLM extraction of standard profile fields."""
    standard_fields = {
        "Company": "",
        "Customer": "",
        "Machine": "",
        "Quote No": fallback_quote_ref,
        "Serial Number": "",
        "Sold to/Address 1": "",
        "Sold to/Address 2": "",
        "Sold to/Address 3": "",
        "Ship to/Address 1": "",
        "Ship to/Address 2": "",
        "Ship to/Address 3": "",
        "Telefone": "",
        "Customer PO": "",
        "Order date": "",
        "Via": "",
        "Incoterm": "",
        "Tax ID": "",
        "H.S": "",
        "Customer Number": "",
        "Customer contact": "",
    }

    try:
        if not configure_gemini_client():
            return standard_fields
        model = get_generative_model()
        if model is None:
            return standard_fields

        prompt = (
            "Extract these fields from the quote text and return JSON only with exact keys: "
            + ", ".join(standard_fields.keys())
            + "\n\nQuote text:\n"
            + full_text[:12000]
        )
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(temperature=0.2, top_p=0.95, max_output_tokens=2048),
        )
        match = re.search(r"\{.*\}", response.text, re.DOTALL)
        if not match:
            return standard_fields

        parsed = json.loads(match.group(0))
        for key in standard_fields:
            if parsed.get(key) is not None:
                standard_fields[key] = str(parsed.get(key, "")).strip()
        if not standard_fields["Quote No"]:
            standard_fields["Quote No"] = fallback_quote_ref
        return standard_fields
    except Exception:
        return standard_fields


def extract_client_profile(pdf_bytes: bytes, filename: str) -> dict[str, Any]:
    """Extract a profile payload from an uploaded quote PDF."""
    temp_pdf_path: str | None = None
    quote_ref = Path(filename).stem
    try:
        temp_pdf_path = write_temp_file(".pdf", pdf_bytes)

        full_text = extract_full_pdf_text(temp_pdf_path)
        line_items = extract_line_item_details(temp_pdf_path)
        machines_data = identify_machines_from_items(line_items)
        standard_fields = _extract_standard_fields_via_llm(full_text, quote_ref)

        client_name = standard_fields.get("Customer") or standard_fields.get("Company") or ""
        client_info = {
            "client_name": client_name,
            "quote_ref": standard_fields.get("Quote No") or quote_ref,
            "contact_person": standard_fields.get("Customer contact", ""),
            "phone": standard_fields.get("Telefone", ""),
            "billing_address": "\n".join(
                [
                    standard_fields.get("Sold to/Address 1", ""),
                    standard_fields.get("Sold to/Address 2", ""),
                    standard_fields.get("Sold to/Address 3", ""),
                ]
            ).strip(),
            "shipping_address": "\n".join(
                [
                    standard_fields.get("Ship to/Address 1", ""),
                    standard_fields.get("Ship to/Address 2", ""),
                    standard_fields.get("Ship to/Address 3", ""),
                ]
            ).strip(),
            "customer_po": standard_fields.get("Customer PO", ""),
            "incoterm": standard_fields.get("Incoterm", ""),
            "quote_date": standard_fields.get("Order date", ""),
        }

        return {
            "client_info": client_info,
            "standard_fields": standard_fields,
            "line_items": line_items,
            "machines_data": machines_data,
            "full_text": full_text,
            "pdf_filename": filename,
        }
    finally:
        if temp_pdf_path and os.path.exists(temp_pdf_path):
            os.remove(temp_pdf_path)


def save_profile(profile: dict[str, Any]) -> str:
    """Persist a confirmed profile payload and return quote_ref."""
    client_info = profile.get("client_info", {})
    standard_fields = profile.get("standard_fields", {})
    quote_ref = client_info.get("quote_ref")
    if not quote_ref:
        raise ValueError("Profile is missing quote_ref.")

    client_record = {
        "quote_ref": quote_ref,
        "customer_name": client_info.get("client_name", ""),
        "machine_model": ", ".join(
            [m.get("machine_name", "") for m in profile.get("machines_data", {}).get("machines", [])]
        ),
        "sold_to_address": client_info.get("billing_address", ""),
        "ship_to_address": client_info.get("shipping_address", ""),
        "telephone": client_info.get("phone", ""),
        "customer_contact_person": client_info.get("contact_person", ""),
        "customer_po": client_info.get("customer_po", ""),
        "incoterm": client_info.get("incoterm", ""),
        "order_date": client_info.get("quote_date", ""),
        "tax_id": standard_fields.get("Tax ID", ""),
        "hs_code": standard_fields.get("H.S", ""),
        "via": standard_fields.get("Via", ""),
        "serial_number": standard_fields.get("Serial Number", ""),
        "customer_number": standard_fields.get("Customer Number", ""),
        "company": standard_fields.get("Company", ""),
    }

    if not save_client_info(client_record):
        raise RuntimeError(f"Failed to save client profile for quote_ref '{quote_ref}'.")

    line_items = profile.get("line_items", [])
    if line_items:
        if not save_priced_items(quote_ref, line_items):
            raise RuntimeError(f"Failed to save line items for quote_ref '{quote_ref}'.")

    machines_data = profile.get("machines_data", {})
    if machines_data:
        if not save_machines_data(quote_ref, machines_data):
            raise RuntimeError(f"Failed to save machine data for quote_ref '{quote_ref}'.")

    save_document_content(quote_ref, profile.get("full_text", ""), profile.get("pdf_filename", ""))
    return quote_ref
