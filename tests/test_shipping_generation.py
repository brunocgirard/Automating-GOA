"""Shipping generation behavior tests."""

from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any

from api.services import shipping_doc_service as shipping_service


def _sample_shipping_state() -> dict[str, Any]:
    return {
        "quoteId": 42,
        "quoteRef": "Q-42",
        "client": {},
        "machines": [
            {
                "id": "machine-1",
                "machineId": 1,
                "lineItemOptionId": None,
                "machineName": "Machine One",
                "model": "Machine One",
                "hsCode": "",
                "serialNumber": "",
                "unitPrice": 1000,
                "truckId": "truck-1",
                "crates": [],
            },
            {
                "id": "machine-2",
                "machineId": 2,
                "lineItemOptionId": None,
                "machineName": "Machine Two",
                "model": "Machine Two",
                "hsCode": "",
                "serialNumber": "",
                "unitPrice": 2000,
                "truckId": "truck-2",
                "crates": [],
            },
        ],
        "trucks": [
            {"id": "truck-1", "name": "Truck 1"},
            {"id": "truck-2", "name": "Truck 2"},
        ],
        "meta": {},
    }


def _single_truck_shipping_state() -> dict[str, Any]:
    payload = _sample_shipping_state()
    payload["machines"] = [
        machine
        for machine in payload["machines"]
        if machine.get("truckId") == "truck-1"
    ]
    payload["trucks"] = [{"id": "truck-1", "name": "Truck 1"}]
    return payload


def _fake_generate_single_docx(_doc_type: str, truck_state: dict[str, Any], output_path: Path) -> None:
    machine_count = len([m for m in truck_state.get("machines", []) if isinstance(m, dict)])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(f"machines={machine_count}", encoding="utf-8")


def test_generate_all_documents_creates_set_per_truck(tmp_path, monkeypatch):
    monkeypatch.setattr(shipping_service, "OUTPUT_ROOT", tmp_path)
    monkeypatch.setattr(shipping_service, "_generate_single_docx", _fake_generate_single_docx)

    artifact = shipping_service.generate_shipping_documents(
        shipping_data=_sample_shipping_state(),
        quote_ref="Q-42",
        document_type="all",
    )

    assert artifact.media_type == "application/zip"
    assert artifact.filename.endswith("_shipping_documents.zip")

    with zipfile.ZipFile(artifact.path, "r") as archive:
        names = sorted(archive.namelist())
        assert names == sorted(
            [
                "packing-slip-truck-1.docx",
                "commercial-invoice-truck-1.docx",
                "certificate-of-origin-truck-1.docx",
                "packing-slip-truck-2.docx",
                "commercial-invoice-truck-2.docx",
                "certificate-of-origin-truck-2.docx",
            ]
        )


def test_generate_single_document_creates_zip_for_multiple_trucks(tmp_path, monkeypatch):
    monkeypatch.setattr(shipping_service, "OUTPUT_ROOT", tmp_path)
    monkeypatch.setattr(shipping_service, "_generate_single_docx", _fake_generate_single_docx)

    artifact = shipping_service.generate_shipping_documents(
        shipping_data=_sample_shipping_state(),
        quote_ref="Q-42",
        document_type="packing_slip",
    )

    assert artifact.media_type == "application/zip"
    assert artifact.filename.endswith("_packing_slip_by_truck.zip")

    with zipfile.ZipFile(artifact.path, "r") as archive:
        names = sorted(archive.namelist())
        assert names == ["packing-slip-truck-1.docx", "packing-slip-truck-2.docx"]


def test_generate_single_html_document_for_one_truck(tmp_path, monkeypatch):
    monkeypatch.setattr(shipping_service, "OUTPUT_ROOT", tmp_path)

    artifact = shipping_service.generate_shipping_documents(
        shipping_data=_single_truck_shipping_state(),
        quote_ref="Q-42",
        document_type="packing_slip",
        output_format="html",
    )

    assert artifact.media_type.startswith("text/html")
    assert artifact.filename.endswith(".html")
    content = artifact.path.read_text(encoding="utf-8")
    assert "<!doctype html>" in content.lower()
    assert "Packing Slip" in content


def test_generate_all_html_documents_creates_set_per_truck(tmp_path, monkeypatch):
    monkeypatch.setattr(shipping_service, "OUTPUT_ROOT", tmp_path)

    artifact = shipping_service.generate_shipping_documents(
        shipping_data=_sample_shipping_state(),
        quote_ref="Q-42",
        document_type="all",
        output_format="html",
    )

    assert artifact.media_type == "application/zip"
    assert artifact.filename.endswith("_shipping_documents.zip")

    with zipfile.ZipFile(artifact.path, "r") as archive:
        names = sorted(archive.namelist())
        assert names == sorted(
            [
                "packing-slip-truck-1.html",
                "commercial-invoice-truck-1.html",
                "certificate-of-origin-truck-1.html",
                "packing-slip-truck-2.html",
                "commercial-invoice-truck-2.html",
                "certificate-of-origin-truck-2.html",
            ]
        )
