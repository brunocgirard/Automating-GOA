"""
Diagnostic benchmark helper for legacy vs V2 extraction prompt/latency metrics.

Run manually:
    python tests/diagnostic/test_fast_prefill_benchmark.py
"""

from __future__ import annotations

import os
import re
import time
from pathlib import Path

from api.services.processing_service import (
    get_contexts_for_machine,
    run_extraction,
)
from src.utils.pdf_utils import extract_full_pdf_text, extract_line_item_details, identify_machines_from_items


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().lower()


def _extract_expected_direction(full_pdf_text: str) -> str:
    patterns = (
        r"\bfrom\s+left\s+to\s+right\b",
        r"\bfrom\s+right\s+to\s+left\b",
        r"\bleft\s+to\s+right\b",
        r"\bright\s+to\s+left\b",
    )
    text = str(full_pdf_text or "")
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return re.sub(r"\s+", " ", match.group(0)).strip()
    return ""


def _find_semantic_field(contexts: dict, semantic_tag: str) -> str | None:
    for key, info in contexts.items():
        if not isinstance(info, dict):
            continue
        if str(info.get("semantic_tag", "")).strip().lower() == semantic_tag:
            return key
    return None


def run_benchmark(pdf_path: str = "templates/UME-23-0001CN-R5-V2.pdf") -> None:
    candidate = Path(pdf_path)
    if not candidate.exists():
        raise FileNotFoundError(f"Benchmark PDF not found: {candidate}")

    items = extract_line_item_details(str(candidate))
    grouped = identify_machines_from_items(items)
    machines = grouped.get("machines", [])
    if not machines:
        raise RuntimeError("No machines were identified from benchmark PDF.")

    machine = machines[0]
    common_items = grouped.get("common_items", [])
    full_pdf_text = extract_full_pdf_text(str(candidate))
    contexts, _, _ = get_contexts_for_machine(machine)

    direction_key = _find_semantic_field(contexts, "direction")
    voltage_key = _find_semantic_field(contexts, "voltage")
    hz_key = _find_semantic_field(contexts, "hz")
    phases_key = _find_semantic_field(contexts, "phases")
    expected_direction = _extract_expected_direction(full_pdf_text)
    baseline_prompt_total: int | None = None
    baseline_elapsed_ms: int | None = None

    for flag in ("false", "true"):
        os.environ["EXTRACTION_FULL_PREFILL_V2_ENABLED"] = flag
        label = "V2_FULL_PREFILL" if flag == "true" else "LEGACY_V1"
        start = time.time()
        result = run_extraction(
            machine_data=machine,
            common_items=common_items,
            template_contexts=contexts,
            full_pdf_text=full_pdf_text,
        )
        elapsed_ms = int((time.time() - start) * 1000)
        metadata = result.get("metadata") or {}
        prompt_total = int((metadata.get("prompt_chars_estimate") or {}).get("total") or 0)
        filled = result.get("filled_data", {})
        direction_value = str(filled.get(direction_key, "")) if direction_key else ""
        direction_hit = (
            bool(expected_direction)
            and bool(direction_value)
            and _normalize(expected_direction) in _normalize(direction_value)
        )
        utility_snapshot = {
            "voltage": str(filled.get(voltage_key, "")) if voltage_key else "",
            "hz": str(filled.get(hz_key, "")) if hz_key else "",
            "phases": str(filled.get(phases_key, "")) if phases_key else "",
        }

        if baseline_prompt_total is None:
            baseline_prompt_total = prompt_total
            baseline_elapsed_ms = elapsed_ms

        print("=" * 80)
        print(label)
        print(f"Elapsed: {elapsed_ms} ms")
        print(f"Fields total: {len(result.get('filled_data', {}))}")
        print(f"Low confidence: {sum(1 for v in result.get('confidence_scores', {}).values() if v < 0.6)}")
        print(f"Direction key/value: {direction_key} => {direction_value!r}")
        print(f"Direction expected: {expected_direction!r} | hit={direction_hit}")
        print(f"Utility snapshot: {utility_snapshot}")
        print(f"Prompt chars total: {prompt_total}")
        if baseline_prompt_total:
            print(f"Prompt delta vs baseline: {prompt_total - baseline_prompt_total}")
        if baseline_elapsed_ms:
            print(f"Latency delta vs baseline: {elapsed_ms - baseline_elapsed_ms} ms")
        print(f"Metadata: {metadata}")


if __name__ == "__main__":
    run_benchmark()
