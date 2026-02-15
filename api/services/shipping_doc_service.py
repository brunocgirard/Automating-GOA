"""Shipping workflow helpers for prefill, HS lookup, and DOCX generation."""

from __future__ import annotations

import json
import re
import zipfile
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from docx import Document

HS_CODE_FILE = Path("src/data/hs_codes.json")
OUTPUT_ROOT = Path("data/generated/shipping")

TEMPLATE_PATHS = {
    "packing_slip": Path("Mail_merge/Paking Slip.docx"),
    "commercial_invoice": Path("Mail_merge/Commercial Invoice.docx"),
    "certificate_origin": Path("Mail_merge/CERTIFICATION OF ORIGIN_NAFTA.docx"),
}

TOKEN_PATTERN = re.compile(r"\u00ab[^\u00bb]+\u00bb")

DEFAULT_META: dict[str, str] = {
    "brokerInfo": "",
    "blanketFrom": "",
    "blanketTo": "",
    "originCriterion": "B",
    "certifierName": "",
    "certifierTitle": "Project Manager",
    "certifierDate": "",
    "certifierContact": "",
    "totalInvoiceAmount": "",
    "countryOfOrigin": "Canada",
}


@dataclass
class GeneratedShippingArtifact:
    path: Path
    filename: str
    media_type: str


@lru_cache(maxsize=1)
def load_hs_code_patterns() -> list[dict[str, str]]:
    """Load HS code pattern data from seed JSON."""
    if not HS_CODE_FILE.exists():
        return []

    try:
        raw = json.loads(HS_CODE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []

    rows: list[dict[str, str]] = []
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        pattern = str(item.get("machine_pattern") or "").strip()
        hs_code = str(item.get("hs_code") or "").strip()
        if not pattern or not hs_code:
            continue
        rows.append({"machine_pattern": pattern, "hs_code": hs_code})

    rows.sort(key=lambda entry: len(_normalize_machine_text(entry["machine_pattern"])), reverse=True)
    return rows


def match_machine_hs_code(machine_name: str, fallback: str = "") -> str:
    """Best-effort machine name to HS code lookup."""
    normalized_name = _normalize_machine_text(machine_name)
    if not normalized_name:
        return fallback

    for entry in load_hs_code_patterns():
        normalized_pattern = _normalize_machine_text(entry["machine_pattern"])
        if normalized_pattern and normalized_pattern in normalized_name:
            return entry["hs_code"]

    return fallback


def build_shipping_prefill_data(quote: dict[str, Any], machine_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a prefilled shipping state from quote + machine DB rows."""
    sold_to = _split_address_lines(quote.get("sold_to_address"))
    ship_to = _split_address_lines(quote.get("ship_to_address"))

    machines: list[dict[str, Any]] = []
    for index, machine_row in enumerate(machine_rows, start=1):
        machine_payload = machine_row.get("machine_data") if isinstance(machine_row, dict) else {}
        if not isinstance(machine_payload, dict):
            machine_payload = {}

        machine_name = _to_text(machine_row.get("machine_name"))
        model = _resolve_machine_model(machine_name, machine_payload)
        hs_code = match_machine_hs_code(
            f"{machine_name} {model}".strip(),
            fallback=_to_text(quote.get("hs_code")),
        )

        machines.append(
            {
                "id": f"machine-{machine_row.get('id', index)}",
                "machineId": machine_row.get("id"),
                "machineName": machine_name or f"Machine {index}",
                "model": model or machine_name or f"Machine {index}",
                "hsCode": hs_code,
                "serialNumber": _to_text(quote.get("serial_number")),
                "unitPrice": _resolve_machine_price(machine_payload),
                "truckId": "truck-1",
                "crates": [
                    {
                        "id": f"crate-{index}-1",
                        "lengthIn": "",
                        "widthIn": "",
                        "heightIn": "",
                        "weightLbs": "",
                    }
                ],
            }
        )

    if not machines:
        fallback_machine = _to_text(quote.get("machine_model")) or "Machine"
        machines.append(
            {
                "id": "machine-1",
                "machineId": None,
                "machineName": fallback_machine,
                "model": fallback_machine,
                "hsCode": match_machine_hs_code(fallback_machine, fallback=_to_text(quote.get("hs_code"))),
                "serialNumber": _to_text(quote.get("serial_number")),
                "unitPrice": 0,
                "truckId": "truck-1",
                "crates": [
                    {
                        "id": "crate-1-1",
                        "lengthIn": "",
                        "widthIn": "",
                        "heightIn": "",
                        "weightLbs": "",
                    }
                ],
            }
        )

    total_invoice_amount = sum(_to_float(machine.get("unitPrice")) for machine in machines)
    meta = dict(DEFAULT_META)
    if total_invoice_amount > 0:
        meta["totalInvoiceAmount"] = f"{total_invoice_amount:.2f}"

    return {
        "quoteId": int(quote.get("id") or 0),
        "quoteRef": _to_text(quote.get("quote_ref")),
        "client": {
            "quoteRef": _to_text(quote.get("quote_ref")),
            "company": _to_text(quote.get("company")) or _to_text(quote.get("customer_name")),
            "customerName": _to_text(quote.get("customer_name")),
            "soldToAddress1": sold_to[0],
            "soldToAddress2": sold_to[1],
            "soldToAddress3": sold_to[2],
            "shipToAddress1": ship_to[0],
            "shipToAddress2": ship_to[1],
            "shipToAddress3": ship_to[2],
            "telephone": _to_text(quote.get("telephone")),
            "customerPO": _to_text(quote.get("customer_po")),
            "orderDate": _to_text(quote.get("order_date")),
            "ax": _to_text(quote.get("ax")),
            "ox": _to_text(quote.get("ox")),
            "via": _to_text(quote.get("via")),
            "incoterm": _to_text(quote.get("incoterm")),
            "taxId": _to_text(quote.get("tax_id")),
            "customerNumber": _to_text(quote.get("customer_number")),
            "clientContact": _to_text(quote.get("customer_contact_person")),
        },
        "machines": machines,
        "trucks": [{"id": "truck-1", "name": "Truck 1"}],
        "meta": meta,
    }


def generate_shipping_documents(
    shipping_data: dict[str, Any],
    quote_ref: str,
    document_type: str = "all",
) -> GeneratedShippingArtifact:
    """Generate one shipping DOCX or a ZIP containing all shipping documents."""
    requested = document_type or "all"
    if requested not in TEMPLATE_PATHS and requested != "all":
        raise ValueError(f"Unsupported document_type '{requested}'.")

    safe_quote_ref = _slugify(quote_ref) or "quote"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = OUTPUT_ROOT / safe_quote_ref / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)

    docs_to_generate = list(TEMPLATE_PATHS.keys()) if requested == "all" else [requested]
    generated: dict[str, Path] = {}

    for key in docs_to_generate:
        output_name = {
            "packing_slip": "packing-slip.docx",
            "commercial_invoice": "commercial-invoice.docx",
            "certificate_origin": "certificate-of-origin.docx",
        }[key]
        output_path = output_dir / output_name
        _generate_single_docx(key, shipping_data, output_path)
        generated[key] = output_path

    if requested == "all":
        zip_path = output_dir / f"{safe_quote_ref}_shipping_documents.zip"
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in generated.values():
                archive.write(path, path.name)
        return GeneratedShippingArtifact(
            path=zip_path,
            filename=zip_path.name,
            media_type="application/zip",
        )

    single_path = generated[requested]
    return GeneratedShippingArtifact(
        path=single_path,
        filename=single_path.name,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


def _generate_single_docx(document_type: str, shipping_data: dict[str, Any], output_path: Path) -> None:
    template_path = TEMPLATE_PATHS[document_type]
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")

    document = Document(str(template_path))
    machine_rows = _machine_rows(shipping_data)
    _fill_repeating_machine_rows(document, machine_rows)

    token_replacements = _build_global_token_replacements(shipping_data, machine_rows)
    literal_replacements = _build_literal_replacements(shipping_data)
    _replace_tokens_in_document(document, token_replacements, literal_replacements)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    document.save(str(output_path))


def _machine_rows(shipping_data: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for machine in shipping_data.get("machines", []):
        if not isinstance(machine, dict):
            continue
        machine_name = _to_text(machine.get("model")) or _to_text(machine.get("machineName"))
        rows.append(
            {
                "Machine": machine_name,
                "Serial_Number": _to_text(machine.get("serialNumber")),
                "HS": _to_text(machine.get("hsCode")),
                "Next Record": "",
            }
        )

    if rows:
        return rows

    return [{"Machine": "", "Serial_Number": "", "HS": "", "Next Record": ""}]


def _fill_repeating_machine_rows(document: Document, machine_rows: list[dict[str, str]]) -> None:
    required_count = max(1, len(machine_rows))
    for table in document.tables:
        row_indices = [
            index
            for index, row in enumerate(table.rows)
            if "\u00abNext Record\u00bb" in _table_row_text(row)
        ]
        if not row_indices:
            continue

        if required_count > len(row_indices):
            template_row = table.rows[row_indices[-1]]._tr
            insert_before = table.rows[row_indices[-1] + 1]._tr if row_indices[-1] + 1 < len(table.rows) else None
            for _ in range(required_count - len(row_indices)):
                cloned = deepcopy(template_row)
                if insert_before is None:
                    table._tbl.append(cloned)
                else:
                    insert_before.addprevious(cloned)

            row_indices = [
                index
                for index, row in enumerate(table.rows)
                if "\u00abNext Record\u00bb" in _table_row_text(row)
            ]

        for slot, row_index in enumerate(row_indices):
            row = table.rows[row_index]
            replacement = machine_rows[slot] if slot < len(machine_rows) else machine_rows[-1]
            if slot >= len(machine_rows):
                replacement = {"Machine": "", "Serial_Number": "", "HS": "", "Next Record": ""}
            for cell in row.cells:
                _replace_tokens_in_cell(cell, replacement, {})


def _replace_tokens_in_document(
    document: Document,
    token_replacements: dict[str, str],
    literal_replacements: dict[str, str],
) -> None:
    for paragraph in document.paragraphs:
        _replace_tokens_in_paragraph(paragraph, token_replacements, literal_replacements)

    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                _replace_tokens_in_cell(cell, token_replacements, literal_replacements)


def _replace_tokens_in_cell(
    cell: Any,
    token_replacements: dict[str, str],
    literal_replacements: dict[str, str],
) -> None:
    for paragraph in cell.paragraphs:
        _replace_tokens_in_paragraph(paragraph, token_replacements, literal_replacements)
    for nested in cell.tables:
        for row in nested.rows:
            for nested_cell in row.cells:
                _replace_tokens_in_cell(nested_cell, token_replacements, literal_replacements)


def _replace_tokens_in_paragraph(
    paragraph: Any,
    token_replacements: dict[str, str],
    literal_replacements: dict[str, str],
) -> None:
    raw_text = "".join(run.text for run in paragraph.runs)
    if not raw_text:
        raw_text = paragraph.text or ""
    if not raw_text:
        return

    updated_text = raw_text
    for token, value in token_replacements.items():
        updated_text = updated_text.replace(f"\u00ab{token}\u00bb", value)

    for source, target in literal_replacements.items():
        if source:
            updated_text = updated_text.replace(source, target)

    updated_text = TOKEN_PATTERN.sub("", updated_text)
    updated_text = re.sub(r"\s+\n", "\n", updated_text)

    if updated_text == raw_text:
        return

    if paragraph.runs:
        paragraph.runs[0].text = updated_text
        for run in paragraph.runs[1:]:
            run.text = ""
    else:
        paragraph.text = updated_text


def _build_global_token_replacements(
    shipping_data: dict[str, Any],
    machine_rows: list[dict[str, str]],
) -> dict[str, str]:
    client = shipping_data.get("client") if isinstance(shipping_data.get("client"), dict) else {}
    meta = shipping_data.get("meta") if isinstance(shipping_data.get("meta"), dict) else {}
    first_machine = machine_rows[0] if machine_rows else {"Machine": "", "Serial_Number": "", "HS": ""}

    replacements = {
        "Company": _to_text(client.get("company")) or _to_text(client.get("customerName")),
        "Sold_toAddress_1": _to_text(client.get("soldToAddress1")),
        "Sold_toAddress_2": _to_text(client.get("soldToAddress2")),
        "Sold_toAddress_3": _to_text(client.get("soldToAddress3")),
        "Ship_toAddress_1": _to_text(client.get("shipToAddress1")),
        "Ship_toAddress_2": _to_text(client.get("shipToAddress2")),
        "Ship_toAddress_3": _to_text(client.get("shipToAddress3")),
        "Customer_PO": _to_text(client.get("customerPO")),
        "Order_date": _to_text(client.get("orderDate")),
        "Ox": _to_text(client.get("ox")),
        "Incoterm": _to_text(client.get("incoterm")),
        "Customer_Number": _to_text(client.get("customerNumber")),
        "Tax_ID": _to_text(client.get("taxId")),
        "Telefone": _to_text(client.get("telephone")),
        "Customer_contact": _to_text(client.get("clientContact")),
        "Machine": _to_text(first_machine.get("Machine")),
        "Serial_Number": _to_text(first_machine.get("Serial_Number")),
        "HS": _to_text(first_machine.get("HS")),
        "Origin_Criterion": _to_text(meta.get("originCriterion") or "B"),
        "Country_of_origin": _to_text(meta.get("countryOfOrigin") or "Canada"),
        "Certifier_Name": _to_text(meta.get("certifierName")),
        "Certifier_Title": _to_text(meta.get("certifierTitle")),
        "Certifier_Date": _to_text(meta.get("certifierDate")),
    }
    return {key: value for key, value in replacements.items()}


def _build_literal_replacements(shipping_data: dict[str, Any]) -> dict[str, str]:
    machines = [machine for machine in shipping_data.get("machines", []) if isinstance(machine, dict)]
    trucks = [truck for truck in shipping_data.get("trucks", []) if isinstance(truck, dict)]
    meta = shipping_data.get("meta") if isinstance(shipping_data.get("meta"), dict) else {}

    total_crates = 0
    total_weight = 0.0
    for machine in machines:
        crates = machine.get("crates")
        if not isinstance(crates, list):
            continue
        total_crates += len(crates)
        for crate in crates:
            if not isinstance(crate, dict):
                continue
            total_weight += _to_float(crate.get("weightLbs"))

    truck_names = ", ".join(
        _to_text(truck.get("name")) for truck in trucks if _to_text(truck.get("name"))
    )

    replacements = {
        "X Crates (Total)": f"{total_crates} Crates (Total)",
        "x lbs (Total)": f"{total_weight:.1f} lbs (Total)",
        "Truck x": truck_names or "Truck 1",
    }

    broker_name = _to_text(meta.get("brokerInfo"))
    if broker_name:
        replacements["Reciever Broker"] = broker_name

    return replacements


def _resolve_machine_model(machine_name: str, machine_payload: dict[str, Any]) -> str:
    description = _to_text(machine_payload.get("description"))
    if description:
        return description.splitlines()[0].strip()

    main_item = machine_payload.get("main_item")
    if isinstance(main_item, dict):
        main_description = _to_text(main_item.get("description"))
        if main_description:
            return main_description.splitlines()[0].strip()

    return machine_name


def _resolve_machine_price(machine_payload: dict[str, Any]) -> float:
    total = 0.0

    main_item = machine_payload.get("main_item")
    if isinstance(main_item, dict):
        total += _to_float(main_item.get("item_price_numeric"))

    add_ons = machine_payload.get("add_ons")
    if isinstance(add_ons, list):
        for row in add_ons:
            if isinstance(row, dict):
                total += _to_float(row.get("item_price_numeric"))

    return round(total, 2)


def _split_address_lines(raw_value: Any) -> tuple[str, str, str]:
    text = _to_text(raw_value)
    if not text:
        return "", "", ""
    lines = [line.strip() for line in re.split(r"\r?\n", text) if line.strip()]
    return (
        lines[0] if len(lines) > 0 else "",
        lines[1] if len(lines) > 1 else "",
        "\n".join(lines[2:]) if len(lines) > 2 else "",
    )


def _table_row_text(row: Any) -> str:
    return " | ".join(cell.text for cell in row.cells)


def _to_text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _to_float(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = re.sub(r"[^0-9.\-]", "", str(value))
    if not cleaned:
        return 0.0
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def _slugify(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip()).strip("-")
    return normalized.lower()


def _normalize_machine_text(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", value.lower())
    return re.sub(r"\s+", " ", normalized).strip()
