"""Report generation endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.dependencies.auth import require_authenticated_user
from api.models.schemas import ReportResponse
from api.routers._helpers import require, scope_kwargs
from api.services.processing_service import load_machine_by_id
from api.services.report_service import (
    generate_machine_report_html,
    generate_machine_summary_html,
)
from src.utils.machine_type import is_sortstar_machine
from src.utils.db import load_machine_template_data

router = APIRouter(prefix="/api/reports", tags=["Reports"])


@router.get("/{machine_id}", response_model=ReportResponse)
def get_machine_report(
    machine_id: int,
    template_type: str = Query(default="GOA"),
    current_user: dict[str, Any] = Depends(require_authenticated_user),
) -> dict:
    machine = require(load_machine_by_id(machine_id, **scope_kwargs(current_user)), "Machine not found.")

    template = require(
        load_machine_template_data(machine_id, template_type),
        f"Template '{template_type}' not found for machine.",
    )

    machine_name = machine.get("machine_name", "")
    html = generate_machine_report_html(
        template_data=template.get("template_data", {}),
        machine_name=machine_name,
        template_type=template_type,
        is_sortstar_machine=is_sortstar_machine(machine_name),
    )
    return {"machine_id": machine_id, "machine_name": machine_name, "html": html}


@router.get("/{machine_id}/summary", response_model=ReportResponse)
def get_machine_summary_report(
    machine_id: int,
    template_type: str = Query(default="GOA"),
    current_user: dict[str, Any] = Depends(require_authenticated_user),
) -> dict:
    machine = require(load_machine_by_id(machine_id, **scope_kwargs(current_user)), "Machine not found.")

    template = require(
        load_machine_template_data(machine_id, template_type),
        f"Template '{template_type}' not found for machine.",
    )

    machine_name = machine.get("machine_name", "")
    html = generate_machine_summary_html(
        template_data=template.get("template_data", {}),
        machine_name=machine_name,
        template_type=template_type,
        is_sortstar_machine=is_sortstar_machine(machine_name),
    )
    return {"machine_id": machine_id, "machine_name": machine_name, "html": html}
