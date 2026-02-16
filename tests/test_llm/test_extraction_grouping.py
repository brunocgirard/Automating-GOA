"""Unit tests for extraction grouping safeguards."""

from src.llm.extraction import _rebalance_grouped_contexts


def test_rebalance_splits_oversized_group_without_sections() -> None:
    grouped = {
        "General & Utility": {f"f{i:04d}": {"type": "string"} for i in range(1, 11)},
    }

    result = _rebalance_grouped_contexts(grouped, max_fields_per_group=4)

    assert len(result) == 3
    assert all(len(group) <= 4 for group in result.values())
    assert sum(len(group) for group in result.values()) == 10


def test_rebalance_prefers_section_buckets_when_available() -> None:
    grouped = {
        "General & Utility": {
            "a1": {"type": "string", "section": "Basic Information"},
            "a2": {"type": "string", "section": "Basic Information"},
            "b1": {"type": "string", "section": "Control & Programming Specifications"},
            "b2": {"type": "string", "section": "Control & Programming Specifications"},
            "b3": {"type": "string", "section": "Control & Programming Specifications"},
        }
    }

    result = _rebalance_grouped_contexts(grouped, max_fields_per_group=2)

    assert len(result) >= 3
    assert all(len(group) <= 2 for group in result.values())
    assert sum(len(group) for group in result.values()) == 5
    assert any("Basic Information" in key for key in result.keys())


def test_rebalance_keeps_small_groups_unchanged() -> None:
    grouped = {
        "General & Utility": {"f0001": {"type": "string"}},
        "Controls & Electrical": {"f0002": {"type": "string"}},
    }

    result = _rebalance_grouped_contexts(grouped, max_fields_per_group=5)

    assert result == grouped
