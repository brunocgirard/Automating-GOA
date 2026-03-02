"""Tests for V2 extraction orchestration in processing_service."""

from __future__ import annotations

from api.services import processing_service as service


def test_run_extraction_routes_to_v2_when_flag_enabled(monkeypatch):
    monkeypatch.setenv("EXTRACTION_FULL_PREFILL_V2_ENABLED", "true")

    sentinel = {
        "filled_data": {"customer": "ACME"},
        "confidence_scores": {"customer": 0.9},
        "suggestions": [],
        "metadata": {"pipeline_version": "v2_full_prefill"},
    }

    monkeypatch.setattr(service, "run_extraction_v2_full_prefill", lambda **_kwargs: sentinel)

    result = service.run_extraction(
        machine_data={"machine_name": "Test"},
        common_items=[],
        template_contexts={"customer": {"type": "string"}},
        full_pdf_text="",
    )
    assert result is sentinel


def test_run_extraction_v2_full_prefill_returns_metadata(monkeypatch):
    monkeypatch.setenv("GOA_LLM_MODEL_DRAFT", "gemini-2.5-flash-lite")
    monkeypatch.setenv("GOA_LLM_MODEL_DEEP", "gemini-2.5-flash")
    monkeypatch.setenv("LLM_FORCE_PASS2_CRITICAL_TEXT", "true")
    monkeypatch.setenv("LLM_CRITICAL_TEXT_RESOLVER_ENABLED", "true")

    monkeypatch.setattr(service, "configure_gemini_client", lambda **_kwargs: True)
    monkeypatch.setattr(service, "_build_selected_pdf_descriptions", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(service, "apply_post_processing_rules", lambda data, *_args, **_kwargs: data)
    monkeypatch.setattr(service, "sanitize_extracted_fields", lambda extracted_data, expected_schema: (extracted_data, {}))
    monkeypatch.setattr(
        service,
        "resolve_critical_text_fields",
        lambda extracted_data, **_kwargs: (
            extracted_data,
            {
                "critical_text_overrides_applied": 1,
                "critical_text_no_evidence_blanked": 0,
            },
        ),
    )

    def _fake_estimate(extracted_data, **_kwargs):
        return {key: 0.8 for key in extracted_data.keys()}

    monkeypatch.setattr(service, "estimate_extraction_confidence", _fake_estimate)
    monkeypatch.setattr(
        service,
        "validate_field_dependencies",
        lambda extracted_data, confidence_scores: (extracted_data, confidence_scores, []),
    )
    monkeypatch.setattr(
        service,
        "select_repair_field_contexts",
        lambda **_kwargs: {"voltage": {"type": "string", "section": "Utility Specifications"}},
    )

    def _fake_extract(**kwargs):
        pass_name = kwargs["pass_options"].pass_name
        if pass_name == "pass1_fast_prefill":
            return (
                {"customer": "ACME", "voltage": ""},
                {
                    "pass_name": pass_name,
                    "fields_attempted": 2,
                    "groups_processed": 1,
                    "prompt_chars_estimate": 1000,
                    "duration_ms": 120,
                    "model_name": "gemini-2.5-flash-lite",
                },
            )
        return (
            {"voltage": "480V"},
            {
                "pass_name": pass_name,
                "fields_attempted": 1,
                "groups_processed": 1,
                "prompt_chars_estimate": 300,
                "duration_ms": 60,
                "model_name": "gemini-2.5-flash",
            },
        )

    monkeypatch.setattr(service, "extract_machine_fields_with_options", _fake_extract)

    result = service.run_extraction_v2_full_prefill(
        machine_data={"machine_name": "Test Machine", "main_item": {"description": "desc"}, "add_ons": []},
        common_items=[],
        template_contexts={
            "customer": {"type": "string", "section": "Basic Information"},
            "voltage": {"type": "string", "section": "Utility Specifications"},
        },
        full_pdf_text="sample text",
    )

    assert result["filled_data"]["customer"] == "ACME"
    assert result["filled_data"]["voltage"] == "480V"
    metadata = result["metadata"]
    assert metadata["pipeline_version"] == "v2_full_prefill"
    assert metadata["pass1_model"] == "gemini-2.5-flash-lite"
    assert metadata["pass2_model"] == "gemini-2.5-flash"
    assert metadata["fields_total"] == 2
    assert metadata["fields_pass1_attempted"] == 2
    assert metadata["fields_pass2_attempted"] == 1
    assert metadata["prompt_chars_estimate"]["total"] == 1300
    assert metadata["critical_text_forced_pass2_count"] >= 0
    assert metadata["critical_text_overrides_applied"] == 1
    assert metadata["critical_text_no_evidence_blanked"] == 0
    assert isinstance(metadata["critical_text_targets"], list)
