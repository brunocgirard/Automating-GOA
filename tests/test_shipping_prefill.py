"""Shipping prefill behavior tests."""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.main import app
from api.routers import shipping as shipping_router
from api.services.shipping_doc_service import build_shipping_prefill_data


def test_build_shipping_prefill_data_includes_line_item_options():
    quote = {
        "id": 11,
        "quote_ref": "Q-11",
        "customer_name": "ACME",
        "company": "ACME",
        "hs_code": "8438.80",
    }
    line_items = [
        {
            "id": 1,
            "item_description": "Markem-Image Thermal Transfer Overprinter Model SmartDate X65- 128",
            "item_quantity": "1",
            "item_price_numeric": 18500.0,
        },
        {
            "id": 2,
            "item_description": "Induction Sealer",
            "item_quantity": "1",
            "item_price_numeric": 9200.0,
        },
        {
            "id": 3,
            "item_description": "Inline Checkweigher",
            "item_quantity": "1",
            "item_price_numeric": 18500.0,
        },
    ]

    prefill = build_shipping_prefill_data(quote, machine_rows=[], line_item_rows=line_items)
    options = prefill.get("lineItemOptions")

    assert isinstance(options, list)
    assert len(options) == 3
    assert options[0]["description"] == "Markem-Image Thermal Transfer Overprinter Model SmartDate X65- 128"
    assert options[0]["name"] == "SmartDate X65-128"
    assert options[0]["unitPrice"] == 18500.0
    assert options[1]["description"] == "Induction Sealer"
    assert options[1]["name"] == "Induction Sealer"
    assert options[1]["unitPrice"] == 9200.0


def test_load_shipping_state_merges_line_item_options(monkeypatch):
    quote = {"id": 5, "quote_ref": "Q-5"}

    monkeypatch.setattr(shipping_router, "get_client_by_id", lambda quote_id: quote if quote_id == 5 else None)
    monkeypatch.setattr(shipping_router, "load_machines_for_quote", lambda _quote_ref: [])
    monkeypatch.setattr(
        shipping_router,
        "load_priced_items_for_quote",
        lambda _quote_ref: [
            {
                "id": 10,
                "item_description": "Checkweigher",
                "item_quantity": "1",
                "item_price_numeric": 12000.0,
            }
        ],
    )
    monkeypatch.setattr(
        shipping_router,
        "load_shipping_document",
        lambda _quote_ref: {
            "created_date": "2026-01-10 09:00:00",
            "modified_date": "2026-01-10 09:05:00",
            "shipping_data": {"quoteId": 5, "quoteRef": "Q-5", "machines": []},
        },
    )

    client = TestClient(app)
    response = client.get("/api/shipping/5/load")

    assert response.status_code == 200
    payload = response.json()
    options = payload["shipping_data"]["lineItemOptions"]
    assert len(options) == 1
    assert options[0]["description"] == "Checkweigher"
    assert options[0]["name"] == "Checkweigher"
    assert options[0]["unitPrice"] == 12000.0


def test_save_shipping_state_persists_line_item_options(monkeypatch):
    quote = {"id": 6, "quote_ref": "Q-6"}
    captured: dict[str, object] = {}

    monkeypatch.setattr(shipping_router, "get_client_by_id", lambda quote_id: quote if quote_id == 6 else None)
    monkeypatch.setattr(shipping_router, "load_machines_for_quote", lambda _quote_ref: [])
    monkeypatch.setattr(
        shipping_router,
        "load_priced_items_for_quote",
        lambda _quote_ref: [
            {
                "id": 14,
                "item_description": "Induction Sealer",
                "item_quantity": "1",
                "item_price_numeric": 9800.0,
            }
        ],
    )

    def fake_save(_quote_ref: str, shipping_data: dict[str, object]) -> dict[str, object]:
        captured["shipping_data"] = shipping_data
        return {
            "modified_date": "2026-01-11 10:15:00",
            "shipping_data": shipping_data,
        }

    monkeypatch.setattr(shipping_router, "save_shipping_document", fake_save)

    client = TestClient(app)
    response = client.post("/api/shipping/6/save", json={"shipping_data": {"machines": []}})

    assert response.status_code == 200
    saved_payload = captured["shipping_data"]
    assert isinstance(saved_payload, dict)
    options = saved_payload.get("lineItemOptions")
    assert isinstance(options, list)
    assert len(options) == 1
    assert options[0]["description"] == "Induction Sealer"
    assert options[0]["name"] == "Induction Sealer"
