"""COR workflow behavior tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from docx import Document
from fastapi.testclient import TestClient

from api.main import app
from api.routers import cor as cor_router
from api.services import cor_doc_service as cor_service
from api.services.cor_doc_service import build_cor_prefill_data


def test_build_cor_prefill_data_maps_quote_and_starts_with_blank_line():
    quote = {
        "id": 77,
        "quote_ref": "Q-77",
        "company": "ACME Foods",
        "customer_po": "PO-900",
        "order_date": "2026-02-18",
        "ax": "AX-1",
        "ox": "OX-2",
        "machine_model": "Main Filler",
    }
    payload = build_cor_prefill_data(quote)

    assert payload["quoteId"] == 77
    assert payload["quoteRef"] == "Q-77"
    assert payload["client"]["company"] == "ACME Foods"
    assert payload["client"]["customerPO"] == "PO-900"
    assert payload["client"]["orderDate"] == "2026-02-18"
    assert payload["client"]["ax"] == "AX-1"
    assert payload["client"]["ox"] == "OX-2"
    assert payload["client"]["machine"] == "Main Filler"

    assert len(payload["lineItems"]) == 1
    assert payload["lineItems"][0]["qty"] == ""
    assert payload["lineItems"][0]["reqDescription"] == ""
    assert payload["lineItems"][0]["unitCost"] == ""
    assert payload["lineItems"][0]["selectedItems"] == ""


def test_cor_prefill_endpoint_uses_client_info_and_blank_rows(monkeypatch):
    quote = {"id": 5, "quote_ref": "Q-5", "company": "Client A"}
    monkeypatch.setattr(cor_router, "get_client_by_id", lambda quote_id: quote if quote_id == 5 else None)

    client = TestClient(app)
    response = client.get("/api/cor/5/prefill")

    assert response.status_code == 200
    payload = response.json()
    assert payload["quote_id"] == 5
    assert payload["quote_ref"] == "Q-5"
    assert payload["cor_data"]["client"]["company"] == "Client A"
    assert payload["cor_data"]["lineItems"][0]["qty"] == ""
    assert payload["cor_data"]["lineItems"][0]["reqDescription"] == ""
    assert payload["cor_data"]["lineItems"][0]["unitCost"] == ""
    assert payload["cor_data"]["lineItems"][0]["selectedItems"] == ""


def test_cor_save_endpoint_persists_quote_context(monkeypatch):
    quote = {"id": 9, "quote_ref": "Q-9"}
    captured: dict[str, Any] = {}

    monkeypatch.setattr(cor_router, "get_client_by_id", lambda quote_id: quote if quote_id == 9 else None)

    def fake_save(_quote_ref: str, cor_data: dict[str, Any]) -> dict[str, Any]:
        captured["cor_data"] = cor_data
        return {
            "modified_date": "2026-02-18 11:30:00",
            "cor_data": cor_data,
        }

    monkeypatch.setattr(cor_router, "save_cor_document", fake_save)

    client = TestClient(app)
    response = client.post(
        "/api/cor/9/save",
        json={
            "cor_data": {
                "corNo": "3",
                "justificationForChange": "Customer requested update.",
                "lineItems": [{"id": "line-1", "qty": "1", "reqDescription": "Sealer"}],
            }
        },
    )

    assert response.status_code == 200
    saved_payload = captured["cor_data"]
    assert isinstance(saved_payload, dict)
    assert saved_payload["quoteId"] == 9
    assert saved_payload["quoteRef"] == "Q-9"
    assert saved_payload["corNo"] == "3"


def _build_test_cor_template(path: Path) -> None:
    doc = Document()
    doc.add_paragraph("Company: \u00abCompany\u00bb")
    doc.add_paragraph("PO: \u00abCustomer_PO\u00bb AX: \u00abAx\u00bb OX: \u00abOx\u00bb Machine: \u00abMachine\u00bb")

    table0 = doc.add_table(rows=5, cols=2)
    table0.rows[4].cells[1].text = ""

    table1 = doc.add_table(rows=2, cols=2)
    table1.rows[1].cells[1].text = ""

    table2 = doc.add_table(rows=13, cols=6)
    table2.rows[8].cells[0].text = "Qty. Req"
    table2.rows[12].cells[0].text = "Total (Excluding Taxes)"

    doc.save(str(path))


def test_generate_cor_document_fills_justification_and_line_items(tmp_path, monkeypatch):
    template_path = tmp_path / "cor-template.docx"
    output_root = tmp_path / "generated"
    _build_test_cor_template(template_path)

    monkeypatch.setattr(cor_service, "TEMPLATE_PATH", template_path)
    monkeypatch.setattr(cor_service, "OUTPUT_ROOT", output_root)

    cor_data = {
        "quoteId": 77,
        "quoteRef": "Q-77",
        "client": {
            "company": "ACME Foods",
            "customerPO": "PO-900",
            "orderDate": "2026-02-18",
            "ax": "AX-1",
            "ox": "OX-2",
            "machine": "Main Filler",
        },
        "corNo": "7",
        "justificationForChange": "Line one\nLine two",
        "lineItems": [
            {
                "id": "line-1",
                "qty": "2",
                "reqDescription": "Induction Sealer",
                "unitCost": "1,500.00",
                "selectedItems": "1,500.00",
            },
            {
                "id": "line-2",
                "qty": "1",
                "reqDescription": "Inline Checkweigher",
                "unitCost": "2,500.00",
                "selectedItems": "2,500.00",
            },
        ],
    }

    artifact = cor_service.generate_cor_document(cor_data, quote_ref="Q-77")
    assert artifact.path.exists()
    assert artifact.filename.endswith(".docx")

    generated = Document(str(artifact.path))
    paragraph_text = "\n".join(paragraph.text for paragraph in generated.paragraphs)
    assert "ACME Foods" in paragraph_text
    assert "PO-900" in paragraph_text
    assert "Main Filler" in paragraph_text
    assert "\u00abCompany\u00bb" not in paragraph_text

    table0 = generated.tables[0]
    table1 = generated.tables[1]
    table2 = generated.tables[2]

    assert table0.rows[4].cells[1].text == "7"
    assert table1.rows[1].cells[1].text == "2026-02-18"
    assert table2.rows[1].cells[0].text == "Line one"
    assert table2.rows[2].cells[0].text == "Line two"

    assert table2.rows[9].cells[1].text == "2"
    assert table2.rows[9].cells[2].text == "Induction Sealer"
    assert table2.rows[10].cells[2].text == "Inline Checkweigher"
    assert table2.rows[12].cells[5].text == "4,000.00"
