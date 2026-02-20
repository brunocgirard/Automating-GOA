"""Tests for quote upload client field prefill extraction."""

from __future__ import annotations

import importlib
import sys
import types

# Keep this test independent from optional google-genai installation.
try:
    google_module = importlib.import_module("google")
except Exception:
    google_module = types.ModuleType("google")
    google_module.__path__ = []
    sys.modules["google"] = google_module

if not hasattr(google_module, "genai"):
    google_module.genai = types.SimpleNamespace(
        types=types.SimpleNamespace(),
        Client=lambda *args, **kwargs: None,
    )

from api.services import processing_service as service


def test_extract_quote_profile_fields_parses_presented_to_section() -> None:
    full_text = """
Quote Reference: UME-23-0001CN-R5-V2
Date: Friday, December 15, 2023
Presented to:
IDEXX Laboratories, Inc.
:1 Idexx Drive
Westbrook Maine
04092
United States
Brennan Parker
Sr. Project Engineer
: + 207-210-7233
: Brennan-Parker@idexx.com
Quotation# UME-23-0001CN-R5-V2.doc
"""

    extracted = service._extract_quote_profile_fields(full_text, "fallback-quote")

    assert extracted["quote_ref"] == "UME-23-0001CN-R5-V2"
    assert extracted["customer_name"] == "Idexx"
    assert extracted["company"] == "Brennan Parker"
    assert extracted["customer_contact_person"] == "Brennan-Parker@idexx.com"
    assert "1 Idexx Drive" in extracted["sold_to_address"]
    assert "United States" in extracted["sold_to_address"]
    assert "207-210-7233" in extracted["telephone"]
    assert extracted["order_date"] == "Friday, December 15, 2023"


def test_extract_quote_profile_fields_returns_safe_defaults_when_missing() -> None:
    extracted = service._extract_quote_profile_fields("No structured data", "Q-DEFAULT")

    assert extracted["quote_ref"] == "Q-DEFAULT"
    assert extracted["company"] == ""
    assert extracted["customer_name"] == ""
    assert extracted["sold_to_address"] == ""
    assert extracted["telephone"] == ""
    assert extracted["order_date"] == ""
    assert extracted["customer_contact_person"] == ""


def test_extract_and_catalog_prefills_selected_client_fields(monkeypatch) -> None:
    captured_client: dict[str, str] = {}

    full_text = """
Quote Reference: Q-77
Date: Wednesday, February 18, 2026
Presented to:
IDEXX Laboratories, Inc.
:1 Idexx Drive
Westbrook Maine
04092
United States
Brennan Parker
Sr. Project Engineer
: + 207-210-7233
: Brennan-Parker@idexx.com
"""

    monkeypatch.setattr(
        service,
        "extract_line_item_details",
        lambda _pdf_path: [{"description": "Machine A", "quantity_text": "1", "selection_text": "1000"}],
    )
    monkeypatch.setattr(service, "extract_full_pdf_text", lambda _pdf_path: full_text)
    monkeypatch.setattr(
        service,
        "identify_machines_from_items",
        lambda _items: {"machines": [{"machine_name": "Machine A"}], "common_items": []},
    )

    def _fake_save_client(payload: dict[str, str]) -> bool:
        captured_client.update(payload)
        return True

    monkeypatch.setattr(service, "save_client_info", _fake_save_client)
    monkeypatch.setattr(service, "save_priced_items", lambda _quote_ref, _items: True)
    monkeypatch.setattr(service, "save_document_content", lambda _quote_ref, _text, _name: True)
    monkeypatch.setattr(service, "save_machines_data", lambda _quote_ref, _machines: True)

    result = service.extract_and_catalog(b"fake-pdf-bytes", "fallback-name.pdf")

    assert result["quote_ref"] == "Q-77"
    assert captured_client["quote_ref"] == "Q-77"
    assert captured_client["customer_name"] == "Idexx"
    assert captured_client["company"] == "Brennan Parker"
    assert captured_client["customer_contact_person"] == "Brennan-Parker@idexx.com"
    assert "1 Idexx Drive" in captured_client["sold_to_address"]
    assert "207-210-7233" in captured_client["telephone"]
    assert captured_client["order_date"] == "Wednesday, February 18, 2026"
    assert captured_client["machine_model"] == "Machine A"
