"""API tests for /api/processing/extract compatibility and metadata."""

from __future__ import annotations

from api.routers import processing as processing_router


def _payload() -> dict:
    return {
        "machine_data": {
            "machine_name": "Test Machine",
            "main_item": {"description": "Main machine"},
            "add_ons": [],
        },
        "common_items": [],
        "template_contexts": None,
        "full_pdf_text": "Sample PDF content",
    }


def test_extract_endpoint_legacy_contract_compatibility(monkeypatch, auth_client):
    """Endpoint must keep legacy top-level fields unchanged."""
    monkeypatch.setattr(
        processing_router,
        "run_extraction",
        lambda **_kwargs: {
            "filled_data": {"customer_name": "ACME"},
            "confidence_scores": {"customer_name": 0.92},
            "suggestions": [],
        },
    )

    response = auth_client.post("/api/processing/extract", json=_payload())

    assert response.status_code == 200
    body = response.json()
    assert body["filled_data"] == {"customer_name": "ACME"}
    assert body["confidence_scores"] == {"customer_name": 0.92}
    assert body["suggestions"] == []
    assert "metadata" in body
    assert body["metadata"] is None


def test_extract_endpoint_metadata_presence_and_sanity(monkeypatch, auth_client):
    """Endpoint should return non-breaking metadata for V2 diagnostics."""
    monkeypatch.setattr(
        processing_router,
        "run_extraction",
        lambda **_kwargs: {
            "filled_data": {"customer_name": "ACME", "voltage": "480V"},
            "confidence_scores": {"customer_name": 0.9, "voltage": 0.81},
            "suggestions": [],
            "metadata": {
                "pipeline_version": "v2_full_prefill",
                "pass1_model": "gemini-2.5-flash-lite",
                "pass2_model": "gemini-2.5-flash",
                "fields_total": 2,
                "fields_pass1_attempted": 2,
                "fields_pass2_attempted": 1,
                "fields_filled_final": 2,
                "low_confidence_count": 0,
                "timing_ms": {"pass1": 120, "pass2": 55, "total": 190},
                "prompt_chars_estimate": {"pass1": 900, "pass2": 250, "total": 1150},
                "critical_text_forced_pass2_count": 1,
                "critical_text_overrides_applied": 1,
                "critical_text_no_evidence_blanked": 0,
                "critical_text_targets": ["direction", "voltage", "hz", "phases"],
            },
        },
    )

    response = auth_client.post("/api/processing/extract", json=_payload())

    assert response.status_code == 200
    body = response.json()
    metadata = body.get("metadata")
    assert isinstance(metadata, dict)
    assert metadata["pipeline_version"] == "v2_full_prefill"
    assert metadata["fields_total"] >= metadata["fields_filled_final"] >= 0
    assert metadata["fields_pass1_attempted"] >= 0
    assert metadata["fields_pass2_attempted"] >= 0
    assert metadata["timing_ms"]["total"] >= metadata["timing_ms"]["pass1"]
    assert metadata["prompt_chars_estimate"]["total"] >= metadata["prompt_chars_estimate"]["pass2"]
    assert metadata["critical_text_forced_pass2_count"] >= 0
    assert metadata["critical_text_overrides_applied"] >= 0
    assert metadata["critical_text_no_evidence_blanked"] >= 0
    assert isinstance(metadata["critical_text_targets"], list)
