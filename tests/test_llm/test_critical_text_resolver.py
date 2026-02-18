"""Unit tests for deterministic critical text resolver."""

from __future__ import annotations

from src.llm.critical_text_resolver import resolve_critical_text_fields


def test_direction_override_and_blank_when_no_evidence() -> None:
    contexts = {
        "f0004": {
            "type": "string",
            "section": "Basic Information",
            "description": "Basic Information - Direction (text)",
            "semantic_tag": "direction",
        }
    }

    extracted = {"f0004": "For stable base container coming from a motorized conveyor"}
    with_evidence = "Conveyor table. Line Direction is From left to Right. Utility details."

    resolved, metrics = resolve_critical_text_fields(
        extracted_data=extracted,
        template_contexts=contexts,
        full_pdf_text=with_evidence,
        target_tags=["direction"],
        blank_direction_without_evidence=True,
    )
    assert resolved["f0004"].lower() == "from left to right"
    assert metrics["critical_text_overrides_applied"] == 1

    no_evidence = "No line direction is documented in this quote snippet."
    resolved_blank, metrics_blank = resolve_critical_text_fields(
        extracted_data=extracted,
        template_contexts=contexts,
        full_pdf_text=no_evidence,
        target_tags=["direction"],
        blank_direction_without_evidence=True,
    )
    assert resolved_blank["f0004"] == ""
    assert metrics_blank["critical_text_no_evidence_blanked"] == 1


def test_utility_override_when_evidence_exists_and_keep_when_missing() -> None:
    contexts = {
        "f0015": {
            "type": "string",
            "section": "Utility Specifications",
            "description": "Utility Specifications - Voltage (text)",
            "semantic_tag": "voltage",
        },
        "f0016": {
            "type": "string",
            "section": "Utility Specifications",
            "description": "Utility Specifications - Hz (text)",
            "semantic_tag": "hz",
        },
        "f0017": {
            "type": "string",
            "section": "Utility Specifications",
            "description": "Utility Specifications - Phases (text)",
            "semantic_tag": "phases",
        },
    }
    extracted = {
        "f0015": "480V",
        "f0016": "50 Hz",
        "f0017": "3 Phases",
    }

    full_pdf_text = "Line Direction table: 220 Volts, 3 Phases, 60/50 Hz."
    resolved, metrics = resolve_critical_text_fields(
        extracted_data=extracted,
        template_contexts=contexts,
        full_pdf_text=full_pdf_text,
        target_tags=["voltage", "hz", "phases"],
    )
    assert resolved["f0015"].lower().startswith("220")
    assert resolved["f0016"].lower().endswith("hz")
    assert resolved["f0017"].lower().endswith("phases")
    assert metrics["critical_text_overrides_applied"] >= 2

    unresolved, _ = resolve_critical_text_fields(
        extracted_data=extracted,
        template_contexts=contexts,
        full_pdf_text="No utility specs here.",
        target_tags=["voltage", "hz", "phases"],
    )
    assert unresolved["f0015"] == "480V"
    assert unresolved["f0016"] == "50 Hz"
    assert unresolved["f0017"] == "3 Phases"
