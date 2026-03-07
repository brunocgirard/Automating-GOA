"""COR workflow behavior tests."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from docx import Document

from api.routers import cor as cor_router
from api.services import cor_doc_service as cor_service
from api.services.cor_doc_service import build_cor_prefill_data
from tests.helpers import DocCapture, stub_get_client_by_id


def test_build_cor_prefill_data_maps_quote_and_starts_with_blank_line():
    quote = {
        "id": 77,
        "quote_ref": "Q-77",
        "customer_name": "ACME Foods",
        "company": "Brennan Parker",
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
    assert payload["revisionDescription"] == ""
    assert payload["corStatus"] == ""
    assert payload["capmaticPM"] == ""
    assert payload["initiatorOfChange"] == "contact_person"
    assert payload["salesRep"] == ""
    assert payload["contactPerson"] == "Brennan Parker"
    assert payload["impactDeliverables"] == ""
    assert payload["impactDeliveryDate"] == ""
    assert payload["paymentTerms"] == ""
    assert payload["currency"] == ""
    assert re.match(r"\d{4}-\d{2}-\d{2}$", payload["approvalDate"]) is not None
    assert payload["comments"] == ""

    assert len(payload["lineItems"]) == 1
    assert payload["lineItems"][0]["qty"] == ""
    assert payload["lineItems"][0]["reqDescription"] == ""
    assert payload["lineItems"][0]["unitCost"] == ""
    assert payload["lineItems"][0]["selectedItems"] == ""


def test_cor_prefill_endpoint_uses_client_info_and_blank_rows(monkeypatch, auth_client):
    quote = {
        "id": 5,
        "quote_ref": "Q-5",
        "customer_name": "Client A",
        "company": "Jordan Name",
    }
    monkeypatch.setattr("api.routers._helpers.get_client_by_id", stub_get_client_by_id(quote, expected_id=5))

    response = auth_client.get("/api/cor/5/prefill")

    assert response.status_code == 200
    payload = response.json()
    assert payload["quote_id"] == 5
    assert payload["quote_ref"] == "Q-5"
    assert payload["cor_data"]["client"]["company"] == "Client A"
    assert payload["cor_data"]["corStatus"] == ""
    assert payload["cor_data"]["capmaticPM"] == ""
    assert payload["cor_data"]["initiatorOfChange"] == "contact_person"
    assert payload["cor_data"]["salesRep"] == ""
    assert payload["cor_data"]["contactPerson"] == "Jordan Name"
    assert payload["cor_data"]["impactDeliverables"] == ""
    assert payload["cor_data"]["impactDeliveryDate"] == ""
    assert payload["cor_data"]["paymentTerms"] == ""
    assert payload["cor_data"]["currency"] == ""
    assert re.match(r"\d{4}-\d{2}-\d{2}$", payload["cor_data"]["approvalDate"]) is not None
    assert payload["cor_data"]["comments"] == ""
    assert payload["cor_data"]["lineItems"][0]["qty"] == ""
    assert payload["cor_data"]["lineItems"][0]["reqDescription"] == ""
    assert payload["cor_data"]["lineItems"][0]["unitCost"] == ""
    assert payload["cor_data"]["lineItems"][0]["selectedItems"] == ""


def test_cor_save_endpoint_persists_quote_context(monkeypatch, auth_client):
    quote = {
        "id": 9,
        "quote_ref": "Q-9",
        "customer_name": "Idexx",
        "company": "Idexx LLC",
        "customer_po": "PO-900",
        "order_date": "2026-02-18",
        "ax": "AX-1",
        "ox": "OX-2",
        "machine_model": "Fallback Machine",
        "customer_contact_person": "Client Contact",
    }
    captured: dict[str, Any] = {}

    monkeypatch.setattr("api.routers._helpers.get_client_by_id", stub_get_client_by_id(quote, expected_id=9))
    monkeypatch.setattr(
        cor_router,
        "load_machines_for_quote",
        lambda quote_ref, **_kwargs: [
            {"machine_name": "Automatic Bottle Unscrambler Model: SortStar", "machine_data": {"machine_type": "main"}},
            {"machine_name": "Bottle Filler Model: X", "machine_data": {"machine_type": "main"}},
        ] if quote_ref == "Q-9" else [],
    )

    save_capture = DocCapture(
        return_factory=lambda _quote_ref, cor_data, cor_document_id=None, create_new=False, cor_no=None, description=None: {
            "id": 17,
            "cor_no": cor_data.get("corNo", ""),
            "description": cor_data.get("revisionDescription", ""),
            "modified_date": "2026-02-18 11:30:00",
            "cor_data": cor_data,
        }
    )
    monkeypatch.setattr(cor_router, "save_cor_document", save_capture)

    response = auth_client.post(
        "/api/cor/9/save",
        json={
            "cor_data": {
                "corNo": "3",
                "revisionDescription": "Rev A",
                "contactPerson": "Should Be Overridden",
                "client": {
                    "company": "Should Be Overridden",
                    "customerPO": "Should Be Overridden",
                    "orderDate": "1999-01-01",
                    "ax": "Should Be Overridden",
                    "ox": "Should Be Overridden",
                    "machine": "Automatic Bottle Unscrambler Model: SortStar",
                },
                "justificationForChange": "Customer requested update.",
                "lineItems": [{"id": "line-1", "qty": "1", "reqDescription": "Sealer"}],
            },
            "create_new": True,
        },
    )

    args, kwargs = save_capture.calls[0]
    captured["cor_data"] = args[1]
    captured["cor_document_id"] = kwargs["cor_document_id"]
    captured["create_new"] = kwargs["create_new"]
    captured["cor_no"] = kwargs["cor_no"]
    captured["description"] = kwargs["description"]

    assert response.status_code == 200
    saved_payload = captured["cor_data"]
    assert isinstance(saved_payload, dict)
    assert saved_payload["quoteId"] == 9
    assert saved_payload["quoteRef"] == "Q-9"
    assert saved_payload["corNo"] == "3"
    assert saved_payload["revisionDescription"] == "Rev A"
    assert saved_payload["contactPerson"] == "Idexx LLC"
    assert saved_payload["client"]["company"] == "Idexx"
    assert saved_payload["client"]["customerPO"] == "PO-900"
    assert saved_payload["client"]["orderDate"] == "2026-02-18"
    assert saved_payload["client"]["ax"] == "AX-1"
    assert saved_payload["client"]["ox"] == "OX-2"
    assert saved_payload["client"]["machine"] == "Automatic Bottle Unscrambler Model: SortStar"
    assert captured["create_new"] is True
    assert response.json()["cor_document_id"] == 17


def test_cor_revisions_endpoint_returns_numbered_entries(monkeypatch, auth_client):
    quote = {"id": 11, "quote_ref": "Q-11"}
    monkeypatch.setattr("api.routers._helpers.get_client_by_id", stub_get_client_by_id(quote, expected_id=11))
    monkeypatch.setattr(
        cor_router,
        "list_cor_documents",
        lambda quote_ref: [
            {
                "id": 2,
                "cor_no": "2",
                "description": "Rev B",
                "created_date": "2026-02-18 08:00:00",
                "modified_date": "2026-02-18 09:00:00",
            },
            {
                "id": 1,
                "cor_no": "1",
                "description": "Initial",
                "created_date": "2026-02-17 08:00:00",
                "modified_date": "2026-02-17 08:00:00",
            },
        ],
    )

    response = auth_client.get("/api/cor/11/revisions")
    payload = response.json()

    assert response.status_code == 200
    assert payload["quote_id"] == 11
    assert payload["quote_ref"] == "Q-11"
    assert len(payload["revisions"]) == 2
    assert payload["revisions"][0]["cor_document_id"] == 2
    assert payload["revisions"][0]["cor_no"] == "2"
    assert payload["revisions"][0]["description"] == "Rev B"


def test_cor_dashboard_returns_rows_across_quotes(monkeypatch, auth_client):
    monkeypatch.setattr(
        cor_router,
        "load_all_clients",
        lambda **_kwargs: [
            {"id": 11, "quote_ref": "Q-11", "customer_name": "Client A", "company": "Client A"},
            {"id": 12, "quote_ref": "Q-12", "customer_name": "Client B", "company": "Client B"},
        ],
    )
    monkeypatch.setattr(
        cor_router,
        "list_cor_documents",
        lambda quote_ref: [
            {
                "id": 3,
                "cor_no": "3",
                "cor_status": "Approved",
                "description": "Rev C",
                "created_date": "2026-02-20 08:00:00",
                "modified_date": "2026-02-20 09:00:00",
            }
        ]
        if quote_ref == "Q-12"
        else [
            {
                "id": 2,
                "cor_no": "2",
                "cor_status": "Waiting for approval",
                "description": "Rev B",
                "created_date": "2026-02-18 08:00:00",
                "modified_date": "2026-02-18 09:00:00",
            },
            {
                "id": 1,
                "cor_no": "1",
                "cor_status": "Not Submitted",
                "description": "Initial",
                "created_date": "2026-02-17 08:00:00",
                "modified_date": "2026-02-17 08:00:00",
            },
        ],
    )

    response = auth_client.get("/api/cor/dashboard")
    payload = response.json()

    assert response.status_code == 200
    assert len(payload["entries"]) == 3
    assert payload["entries"][0]["quote_id"] == 12
    assert payload["entries"][0]["quote_ref"] == "Q-12"
    assert payload["entries"][0]["client_name"] == "Client B"
    assert payload["entries"][0]["cor_no"] == "3"
    assert payload["entries"][0]["cor_status"] == "Approved"
    assert payload["entries"][1]["quote_id"] == 11
    assert payload["entries"][2]["cor_document_id"] == 1


def _build_test_cor_template(path: Path) -> None:
    doc = Document()
    doc.add_paragraph("COR Number: {{COR NO. #}}")
    doc.add_paragraph("Customer: {{Customer}}")
    doc.add_paragraph("PO: \u00abCustomer_PO\u00bb AX: \u00abAx\u00bb OX: \u00abOx\u00bb Machine: \u00abMachine\u00bb")
    doc.add_paragraph("Initiator: {{Contact_Person}} or {{Capmatic_PM}}")
    doc.add_paragraph(
        "Status: {{COR_Satus}} PM: {{Capmatic_PM}} Rep: {{Sales_Rep}} Terms: {{Payment_Terms}} Cur: {{Currency}} Date: {{Date}}"
    )

    table0 = doc.add_table(rows=5, cols=2)
    table0.rows[3].cells[0].text = "{{COR_Satus}}"
    table0.rows[4].cells[1].text = ""

    table1 = doc.add_table(rows=4, cols=4)
    table1.rows[1].cells[1].text = ""
    table1.rows[1].cells[3].text = "{{Capmatic_PM}}"
    table1.rows[2].cells[1].text = "{{Sales_Rep}}"
    table1.rows[3].cells[1].text = "{{Contact_Person}} or {{Capmatic_PM}}"

    table2 = doc.add_table(rows=13, cols=7)
    table2.rows[3].cells[0].text = "PAYMENT TERMS:"
    table2.rows[4].cells[0].text = "IMPACT OF CHANGE TO DELIVERABLES:"
    table2.rows[5].cells[0].text = "IMPACT ON DELIVERY DATE:"
    table2.rows[8].cells[1].text = "Qty. Req"
    table2.rows[12].cells[2].text = "Total (Excluding Taxes)"

    table3 = doc.add_table(rows=2, cols=1)
    table3.rows[0].cells[0].text = "COMMENTS:"
    table3.rows[1].cells[0].text = "\u00abComments\u00bb"

    doc.save(str(path))


def test_generate_cor_document_fills_justification_and_line_items(tmp_path, monkeypatch):
    template_path = tmp_path / "cor-template.docx"
    output_root = tmp_path / "generated"
    _build_test_cor_template(template_path)

    monkeypatch.setattr(cor_service, "TEMPLATE_PATH", template_path)
    monkeypatch.setattr(cor_service, "TEMPLATE_PATH_CANDIDATES", (template_path,))
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
        "corStatus": "Approved",
        "capmaticPM": "Christian Normandin",
        "initiatorOfChange": "capmatic_pm",
        "salesRep": "Jairo Martinez",
        "contactPerson": "Client Contact",
        "impactDeliverables": "Yes",
        "impactDeliveryDate": "No",
        "paymentTerms": "100% w/PO",
        "currency": "USD",
        "approvalDate": "1999-12-31",
        "justificationForChange": "Line one\nLine two",
        "comments": "Approved with no impact.",
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
    assert "COR Number: COR 7" in paragraph_text
    assert "ACME Foods" in paragraph_text
    assert "PO-900" in paragraph_text
    assert "Main Filler" in paragraph_text
    assert "Approved" in paragraph_text
    assert "Christian Normandin" in paragraph_text
    assert "Jairo Martinez" in paragraph_text
    assert "100% w/PO" in paragraph_text
    assert "USD" in paragraph_text
    assert f"Date: {datetime.now().strftime('%Y-%m-%d')}" in paragraph_text
    assert "1999-12-31" not in paragraph_text
    assert "Initiator: Christian Normandin" in paragraph_text
    assert "Client Contact" not in paragraph_text
    assert " or " not in paragraph_text
    assert "\u00abCompany\u00bb" not in paragraph_text

    table0 = generated.tables[0]
    table1 = generated.tables[1]
    table2 = generated.tables[2]

    assert table0.rows[3].cells[0].text == "Approved"
    assert table0.rows[4].cells[1].text == "7"
    assert table1.rows[1].cells[1].text == "2026-02-18"
    assert table1.rows[1].cells[3].text == "Christian Normandin"
    assert table1.rows[2].cells[1].text == "Jairo Martinez"
    assert table1.rows[3].cells[1].text == "Christian Normandin"
    assert table2.rows[1].cells[0].text == "Line one"
    assert table2.rows[2].cells[0].text == "Line two"
    assert table2.rows[3].cells[2].text == "100% w/PO"
    assert table2.rows[4].cells[3].text == "Yes"
    assert table2.rows[5].cells[2].text == "No"

    assert table2.rows[9].cells[1].text == "2"
    assert table2.rows[9].cells[2].text == "Induction Sealer"
    assert table2.rows[10].cells[2].text == "Inline Checkweigher"
    assert table2.rows[12].cells[5].text == "4,000.00"
    assert table2.rows[12].cells[6].text == "USD"

    full_text = "\n".join(
        paragraph.text
        for table in generated.tables
        for row in table.rows
        for cell in row.cells
        for paragraph in cell.paragraphs
    )
    assert "Approved with no impact." in full_text
