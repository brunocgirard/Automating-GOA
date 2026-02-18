"""Tests for quote artifact loading behavior in processing_service."""

from __future__ import annotations

import sys
import types
import importlib

# Keep this test independent from optional google-genai installation.
try:
    google_module = importlib.import_module("google")
except Exception:
    google_module = types.ModuleType("google")
    google_module.__path__ = []  # Mark as package for namespace-style imports.
    sys.modules["google"] = google_module

if not hasattr(google_module, "genai"):
    google_module.genai = types.SimpleNamespace(
        types=types.SimpleNamespace(),
        Client=lambda *args, **kwargs: None,
    )

from api.services import processing_service as service


def test_load_quote_artifacts_prefers_priced_items_for_order(monkeypatch) -> None:
    """Use priced_items order when available so index-based regrouping stays correct."""

    machine_rows = [
        {
            "machine_data": {
                "main_item": {"description": "Machine A", "quantity_text": "1", "selection_text": "$10000"},
                "add_ons": [
                    {"description": "Addon A1", "quantity_text": "1", "selection_text": "$1000"},
                ],
                "common_items": [
                    {"description": "Common Service", "quantity_text": "1", "selection_text": "$500"},
                ],
            }
        },
        {
            "machine_data": {
                "main_item": {"description": "Machine B", "quantity_text": "1", "selection_text": "$9000"},
                "add_ons": [
                    {"description": "Addon B1", "quantity_text": "1", "selection_text": "$700"},
                ],
                "common_items": [
                    {"description": "Common Service", "quantity_text": "1", "selection_text": "$500"},
                ],
            }
        },
    ]

    priced_rows = [
        {"item_description": "Machine A", "item_quantity": "1", "item_price_str": "$10000", "item_price_numeric": 10000.0},
        {"item_description": "Addon A1", "item_quantity": "1", "item_price_str": "$1000", "item_price_numeric": 1000.0},
        {"item_description": "Machine B", "item_quantity": "1", "item_price_str": "$9000", "item_price_numeric": 9000.0},
        {"item_description": "Addon B1", "item_quantity": "1", "item_price_str": "$700", "item_price_numeric": 700.0},
        {"item_description": "Common Service", "item_quantity": "1", "item_price_str": "$500", "item_price_numeric": 500.0},
    ]

    monkeypatch.setattr(service, "load_document_content", lambda _quote_ref: {"full_pdf_text": "text", "pdf_filename": "q.pdf"})
    monkeypatch.setattr(service, "load_machines_for_quote", lambda _quote_ref: machine_rows)
    monkeypatch.setattr(service, "load_priced_items_for_quote", lambda _quote_ref: priced_rows)

    result = service.load_quote_artifacts("Q-123")

    descriptions = [item["description"] for item in result["items"]]
    assert descriptions == ["Machine A", "Addon A1", "Machine B", "Addon B1", "Common Service"]


def test_load_quote_artifacts_falls_back_to_machine_payloads_when_priced_missing(monkeypatch) -> None:
    """Fallback keeps compatibility with historical records without priced_items rows."""

    machine_rows = [
        {
            "machine_data": {
                "main_item": {"description": "Machine X", "quantity_text": "1", "selection_text": "$5000"},
                "add_ons": [
                    {"description": "Addon X1", "quantity_text": "1", "selection_text": "$250"},
                ],
                "common_items": [
                    {"description": "Common Warranty", "quantity_text": "1", "selection_text": "$100"},
                ],
            }
        }
    ]

    monkeypatch.setattr(service, "load_document_content", lambda _quote_ref: {})
    monkeypatch.setattr(service, "load_machines_for_quote", lambda _quote_ref: machine_rows)
    monkeypatch.setattr(service, "load_priced_items_for_quote", lambda _quote_ref: [])

    result = service.load_quote_artifacts("Q-456")

    descriptions = [item["description"] for item in result["items"]]
    assert descriptions == ["Machine X", "Addon X1", "Common Warranty"]
