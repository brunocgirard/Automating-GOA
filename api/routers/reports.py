"""Report generation endpoints."""

from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException, Query, status

from api.models.schemas import ReportResponse
from api.services.processing_service import load_machine_by_id
from api.services.report_service import (
    generate_machine_report_html,
    generate_machine_summary_html,
)
from src.utils.db import load_machine_template_data

router = APIRouter(prefix="/api/reports", tags=["Reports"])


def _is_sortstar_machine(machine_name: str) -> bool:
    return bool(re.search(r"\b(sortstar|unscrambler|bottle unscrambler)\b", (machine_name or "").lower()))


@router.get("/{machine_id}", response_model=ReportResponse)
def get_machine_report(machine_id: int, template_type: str = Query(default="GOA")) -> dict:
    machine = load_machine_by_id(machine_id)
    if not machine:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Machine not found.")

    template = load_machine_template_data(machine_id, template_type)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template '{template_type}' not found for machine.",
        )

    machine_name = machine.get("machine_name", "")
    html = generate_machine_report_html(
        template_data=template.get("template_data", {}),
        machine_name=machine_name,
        template_type=template_type,
        is_sortstar_machine=_is_sortstar_machine(machine_name),
    )
    return {"machine_id": machine_id, "machine_name": machine_name, "html": html}


@router.get("/{machine_id}/summary", response_model=ReportResponse)
def get_machine_summary_report(machine_id: int, template_type: str = Query(default="GOA")) -> dict:
    machine = load_machine_by_id(machine_id)
    if not machine:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Machine not found.")

    template = load_machine_template_data(machine_id, template_type)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template '{template_type}' not found for machine.",
        )

    machine_name = machine.get("machine_name", "")
    html = generate_machine_summary_html(
        template_data=template.get("template_data", {}),
        machine_name=machine_name,
        template_type=template_type,
        is_sortstar_machine=_is_sortstar_machine(machine_name),
    )
    return {"machine_id": machine_id, "machine_name": machine_name, "html": html}
