"""Machine endpoints router."""

from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status

from api.models.schemas import (
    MachineDetailResponse,
    MachineResponse,
    TemplateResponse,
    TemplateUpdateRequest,
)
from api.services.processing_service import load_machine_by_id
from src.utils.db import (
    get_client_by_id,
    load_all_clients,
    load_all_processed_machines,
    load_machine_template_data,
    load_machines_for_quote,
    save_machine_template_data,
)

router = APIRouter(prefix="/api", tags=["Machines"])

MAIN_MACHINE_PATTERNS = (
    r"\bmodel\b",
    r"\bmonoblock\b",
    r"\bunscrambler\b",
    r"\bfiller\b",
    r"\bcapper\b",
    r"\blabeler\b",
    r"\bcartoner\b",
    r"\bcase\s*packer\b",
    r"\bmachine\b",
    r"\baf-\d+\b",
    r"\bfcp-\d+\b",
)

OPTION_PATTERNS = (
    r"\bextra\b",
    r"\boption\b",
    r"\bspare\s*parts?\b",
    r"\bcommissioning\b",
    r"\bwarranty\b",
    r"\binstallation\b",
    r"\btraining\b",
    r"\bservice\b",
    r"\bmaintenance\b",
    r"\bvalidation\b",
    r"\bshipping\b",
    r"\bdelivery\b",
)


def _parse_machine_data(machine: dict[str, Any]) -> dict[str, Any]:
    payload = machine.get("machine_data")
    if isinstance(payload, dict):
        return payload
    return {}


def _extract_description(machine: dict[str, Any], machine_data: dict[str, Any]) -> str | None:
    description = machine_data.get("description")
    if isinstance(description, str) and description.strip():
        return description.strip()

    main_item = machine_data.get("main_item")
    if isinstance(main_item, dict):
        main_description = main_item.get("description")
        if isinstance(main_description, str) and main_description.strip():
            return main_description.strip()
    return None


def _infer_machine_type(machine_data: dict[str, Any]) -> str:
    explicit = machine_data.get("machine_type")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip().lower()

    main_item = machine_data.get("main_item")
    if not isinstance(main_item, dict):
        return "option"

    price = main_item.get("item_price_numeric")
    if isinstance(price, (int, float)) and float(price) >= 50000:
        return "main"

    description = main_item.get("description")
    text = description.lower() if isinstance(description, str) else ""
    if text and any(re.search(pattern, text) for pattern in OPTION_PATTERNS):
        return "option"
    if text and any(re.search(pattern, text) for pattern in MAIN_MACHINE_PATTERNS):
        return "main"
    return "option"


def _serialize_machine_response(
    *,
    machine: dict[str, Any],
    quote_ref: str,
    client_id: int | None,
    client_name: str | None,
    machine_data: dict[str, Any],
    machine_type: str,
) -> dict[str, Any]:
    template = load_machine_template_data(machine["id"], "GOA")
    status_value = "draft"
    if template:
        status_value = "ready" if template.get("generated_file_path") else "processed"

    return {
        "id": machine["id"],
        "machine_name": machine.get("machine_name", ""),
        "description": _extract_description(machine, machine_data),
        "machine_type": machine_type,
        "quote_ref": quote_ref,
        "client_name": client_name,
        "client_id": client_id,
        "machine_template_id": template.get("id") if template else None,
        "status": status_value,
        "processing_date": machine.get("processing_date"),
        "template_data": template.get("template_data") if template else None,
    }


@router.get("/machines", response_model=list[MachineResponse])
def list_machines() -> list[dict]:
    machines = load_all_processed_machines()
    response: list[dict] = []
    for machine in machines:
        response.append(
            {
                "id": machine["id"],
                "machine_name": machine.get("machine_name", ""),
                "description": None,
                "machine_type": "main",
                "quote_ref": machine.get("quote_ref") or machine.get("client_quote_ref", ""),
                "client_name": machine.get("client_name"),
                "client_id": machine.get("client_id"),
                "machine_template_id": None,
                "status": "processed",
                "processing_date": machine.get("processing_date"),
                "template_data": None,
            }
        )
    return response


@router.get("/machines/all", response_model=list[MachineResponse])
def list_all_quote_machines(
    main_only: bool = Query(default=False),
) -> list[dict[str, Any]]:
    response: list[dict[str, Any]] = []
    for quote in load_all_clients():
        quote_ref = quote.get("quote_ref")
        if not isinstance(quote_ref, str) or not quote_ref:
            continue

        quote_id = quote.get("id")
        client_id = quote_id if isinstance(quote_id, int) else None
        client_name = quote.get("customer_name")
        for machine in load_machines_for_quote(quote_ref):
            machine_data = _parse_machine_data(machine)
            machine_type = _infer_machine_type(machine_data)
            if main_only and machine_type != "main":
                continue
            response.append(
                _serialize_machine_response(
                    machine=machine,
                    quote_ref=quote_ref,
                    client_id=client_id,
                    client_name=client_name if isinstance(client_name, str) else None,
                    machine_data=machine_data,
                    machine_type=machine_type,
                )
            )
    return response


@router.get("/machines/{machine_id}", response_model=MachineDetailResponse)
def get_machine(machine_id: int) -> dict:
    machine = load_machine_by_id(machine_id)
    if not machine:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Machine not found.")
    return {
        "id": machine["id"],
        "machine_name": machine.get("machine_name", ""),
        "client_quote_ref": machine.get("client_quote_ref", ""),
        "processing_date": machine.get("processing_date"),
        "machine_data": machine.get("machine_data", {}),
    }


@router.get("/quotes/{quote_id}/machines", response_model=list[MachineResponse])
def list_machines_for_quote(
    quote_id: int,
    main_only: bool = Query(default=False),
) -> list[dict]:
    quote = get_client_by_id(quote_id)
    if not quote:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quote not found.")

    quote_ref = quote["quote_ref"]
    machines = load_machines_for_quote(quote_ref)
    response: list[dict] = []
    for machine in machines:
        machine_data = _parse_machine_data(machine)
        machine_type = _infer_machine_type(machine_data)
        if main_only and machine_type != "main":
            continue

        response.append(
            _serialize_machine_response(
                machine=machine,
                quote_ref=quote_ref,
                client_id=quote_id,
                client_name=quote.get("customer_name"),
                machine_data=machine_data,
                machine_type=machine_type,
            )
        )
    return response


@router.get("/machines/{machine_id}/template", response_model=TemplateResponse)
def get_machine_template(
    machine_id: int,
    template_type: str = Query(default="GOA"),
) -> dict:
    machine = load_machine_by_id(machine_id)
    if not machine:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Machine not found.")

    template = load_machine_template_data(machine_id, template_type)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template '{template_type}' not found for machine.",
        )
    return {
        "id": template["id"],
        "template_data": template.get("template_data", {}),
        "generated_file_path": template.get("generated_file_path"),
        "processing_date": template.get("processing_date"),
    }


@router.put("/machines/{machine_id}/template", response_model=TemplateResponse)
def update_machine_template(machine_id: int, payload: TemplateUpdateRequest) -> dict:
    machine = load_machine_by_id(machine_id)
    if not machine:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Machine not found.")

    saved = save_machine_template_data(
        machine_id=machine_id,
        template_type=payload.template_type,
        template_data=payload.template_data,
        generated_file_path=payload.generated_file_path,
    )
    if not saved:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save template data.",
        )

    template = load_machine_template_data(machine_id, payload.template_type)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Template saved but could not be reloaded.",
        )
    return {
        "id": template["id"],
        "template_data": template.get("template_data", {}),
        "generated_file_path": template.get("generated_file_path"),
        "processing_date": template.get("processing_date"),
    }
