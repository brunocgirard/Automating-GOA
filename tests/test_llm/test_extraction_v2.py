"""Unit tests for V2 pass-based extraction helpers."""

from __future__ import annotations

from typing import Any

from src.llm.extraction import (
    ExtractionPassOptions,
    _parse_main_item_subitems,
    extract_machine_fields_with_options,
    select_repair_field_contexts,
)


class _FakeResponse:
    def __init__(self, text: str):
        self.text = text


class _FakeModel:
    def __init__(self, response_text: str = "{}"):
        self._response_text = response_text

    def generate_content(self, *_args: Any, **_kwargs: Any) -> _FakeResponse:
        return _FakeResponse(self._response_text)


class _CapturingModel(_FakeModel):
    def __init__(self, response_text: str = "{}"):
        super().__init__(response_text)
        self.prompts: list[str] = []

    def generate_content(self, prompt: str, *_args: Any, **_kwargs: Any) -> _FakeResponse:
        self.prompts.append(prompt)
        return super().generate_content(prompt, *_args, **_kwargs)


def test_parse_main_item_subitems_with_symbol_bullets() -> None:
    description = "Main conveyor system\n• Integrated container hopper\n• Low level hopper sensor"

    assert _parse_main_item_subitems(description) == [
        "Integrated container hopper",
        "Low level hopper sensor",
    ]


def test_parse_main_item_subitems_with_dash_bullets() -> None:
    description = "Main conveyor system\n- Integrated container hopper\n- Low level hopper sensor"

    assert _parse_main_item_subitems(description) == [
        "Integrated container hopper",
        "Low level hopper sensor",
    ]


def test_parse_main_item_subitems_without_bullets_returns_empty_list() -> None:
    assert _parse_main_item_subitems("Main conveyor system with integrated hopper") == []


def test_parse_main_item_subitems_empty_values_return_empty_list() -> None:
    assert _parse_main_item_subitems("") == []
    assert _parse_main_item_subitems(None) == []  # type: ignore[arg-type]


def test_select_repair_field_contexts_uses_thresholds_and_suggestions() -> None:
    contexts = {
        "customer": {"type": "string"},
        "voltage": {"type": "string"},
        "ce_csa_check": {"type": "boolean"},
        "plc_allenb_check": {"type": "boolean"},
    }
    extracted = {
        "customer": "",
        "voltage": "480V",
        "ce_csa_check": "YES",
        "plc_allenb_check": "NO",
    }
    confidence = {
        "customer": 0.50,
        "voltage": 0.95,
        "ce_csa_check": 0.40,
        "plc_allenb_check": 0.90,
    }
    suggestions = [{"field": "voltage", "reason": "dependency mismatch", "type": "warning"}]

    selected = select_repair_field_contexts(
        extracted_data=extracted,
        confidence_scores=confidence,
        template_placeholder_contexts=contexts,
        text_confidence_threshold=0.72,
        checkbox_yes_confidence_threshold=0.80,
        dependency_suggestions=suggestions,
    )

    assert "customer" in selected  # empty text
    assert "ce_csa_check" in selected  # YES but low confidence
    assert "voltage" in selected  # added by dependency suggestion
    assert "plc_allenb_check" not in selected  # NO checkbox is not repaired by threshold rule


def test_extract_machine_fields_with_options_respects_pass_toggles(monkeypatch) -> None:
    from src.llm import extraction as extraction_module

    monkeypatch.setattr(extraction_module, "get_generative_model", lambda *_args, **_kwargs: _FakeModel("{}"))
    monkeypatch.setattr(extraction_module, "configure_gemini_client", lambda: True)

    def _quote_library_should_not_run(**_kwargs: Any):
        raise AssertionError("QUOTE_LIBRARY should be disabled for this pass")

    monkeypatch.setattr(extraction_module, "get_quote_library_context", _quote_library_should_not_run)
    monkeypatch.setattr(
        extraction_module,
        "enhance_prompt_with_few_shot_examples",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("few-shot should be disabled")),
    )
    if hasattr(extraction_module, "enhance_prompt_with_semantic_examples"):
        monkeypatch.setattr(
            extraction_module,
            "enhance_prompt_with_semantic_examples",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("semantic few-shot should be disabled")),
        )

    contexts = {
        "customer": {"type": "string", "description": "Customer name", "section": "Basic Information"},
        "ce_csa_check": {"type": "boolean", "description": "CSA", "section": "Utility Specifications"},
        "voltage": {"type": "string", "description": "Voltage", "section": "Utility Specifications"},
    }

    data, metrics = extract_machine_fields_with_options(
        machine_data={"machine_name": "Test Machine", "main_item": {"description": "Main"}},
        common_items=[],
        template_placeholder_contexts=contexts,
        full_pdf_text="Voltage 480V",
        pass_options=ExtractionPassOptions(
            pass_name="test_pass",
            model_name="gemini-2.5-flash-lite",
            rag_max_chars=8000,
            max_fields_per_group=2,
            enable_few_shot=False,
            enable_quote_library=False,
            compact_prompt=True,
            concurrency=2,
        ),
    )

    assert set(data.keys()) == set(contexts.keys())
    assert data["customer"] == ""
    assert data["ce_csa_check"] in {"NO", "YES"}
    assert metrics["fields_attempted"] == len(contexts)
    assert metrics["model_name"] == "gemini-2.5-flash-lite"
    assert metrics["groups_processed"] >= 1


def test_select_repair_field_contexts_forces_critical_semantic_text_fields() -> None:
    contexts = {
        "f0004": {
            "type": "string",
            "section": "Basic Information",
            "description": "Basic Information - Direction (text)",
            "semantic_tag": "direction",
        },
        "f0015": {
            "type": "string",
            "section": "Utility Specifications",
            "description": "Utility Specifications - Voltage (text)",
            "semantic_tag": "voltage",
        },
        "other": {"type": "string", "description": "Some other text"},
    }
    extracted = {
        "f0004": "For stable base container coming from a motorized conveyor",
        "f0015": "220 Volts",
        "other": "plain value",
    }
    confidence = {
        "f0004": 0.95,
        "f0015": 0.91,
        "other": 0.93,
    }

    selected = select_repair_field_contexts(
        extracted_data=extracted,
        confidence_scores=confidence,
        template_placeholder_contexts=contexts,
        force_critical_text_fields=True,
        forced_semantic_tags=("direction", "voltage"),
    )

    assert "f0004" in selected
    assert "f0015" in selected
    assert "other" not in selected


def test_extract_machine_fields_with_options_keeps_comment_fields_empty(monkeypatch) -> None:
    from src.llm import extraction as extraction_module

    model = _FakeModel(
        '{"customer":"ACME","rj_comm":"LLM generated comment that should be removed","ce_csa_check":"YES"}'
    )
    monkeypatch.setattr(extraction_module, "get_generative_model", lambda *_args, **_kwargs: model)
    monkeypatch.setattr(extraction_module, "configure_gemini_client", lambda: True)
    monkeypatch.setattr(extraction_module, "get_quote_library_context", lambda **_kwargs: ("", []))

    contexts = {
        "customer": {"type": "string", "description": "Customer name", "section": "Basic Information"},
        "rj_comm": {"type": "string", "description": "Reject / Inspection System - comments", "section": "Reject"},
        "ce_csa_check": {"type": "boolean", "description": "CSA", "section": "Utility Specifications"},
    }

    data, _metrics = extract_machine_fields_with_options(
        machine_data={"machine_name": "Test Machine", "main_item": {"description": "Main"}},
        common_items=[],
        template_placeholder_contexts=contexts,
        full_pdf_text="CSA required",
        pass_options=ExtractionPassOptions(
            pass_name="test_comment_policy",
            enable_few_shot=False,
            enable_quote_library=False,
            compact_prompt=True,
        ),
    )

    assert data["customer"] == "ACME"
    assert data["ce_csa_check"] == "YES"
    assert data["rj_comm"] == ""


def test_extract_machine_fields_with_options_structures_main_item_subitems(monkeypatch) -> None:
    from src.llm import extraction as extraction_module

    model = _CapturingModel('{"hopper_check":"YES"}')
    monkeypatch.setattr(extraction_module, "get_generative_model", lambda *_args, **_kwargs: model)
    monkeypatch.setattr(extraction_module, "configure_gemini_client", lambda: True)
    monkeypatch.setattr(extraction_module, "get_quote_library_context", lambda **_kwargs: ("", []))

    contexts = {
        "hopper_check": {
            "type": "boolean",
            "description": "Integrated hopper included",
            "section": "Machine Options",
        }
    }

    extract_machine_fields_with_options(
        machine_data={
            "machine_name": "SortStar",
            "main_item": {
                "description": (
                    "Main conveyor system\n"
                    "• Integrated container hopper\n"
                    "• Low level hopper sensor"
                )
            },
        },
        common_items=[],
        template_placeholder_contexts=contexts,
        full_pdf_text="",
        pass_options=ExtractionPassOptions(
            pass_name="test_subitems",
            enable_few_shot=False,
            enable_quote_library=False,
            compact_prompt=False,
        ),
    )

    assert len(model.prompts) == 1
    prompt = model.prompts[0]
    assert "- Main item: Main conveyor system" in prompt
    assert "- Main item includes:" in prompt
    assert "  • Integrated container hopper" in prompt
    assert "  • Low level hopper sensor" in prompt
