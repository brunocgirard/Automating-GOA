"""Unit tests for lightweight PDF retrieval helpers."""

from src.utils.pdf_rag import build_retrieved_pdf_context, chunk_text


def test_build_retrieved_pdf_context_returns_full_text_when_short() -> None:
    text = "Customer: ACME Corp\nQuote: Q-123\nVoltage: 480V"

    context, note = build_retrieved_pdf_context(text, ["customer", "voltage"], max_context_chars=5000)

    assert context == text
    assert "Full PDF text included" in note


def test_build_retrieved_pdf_context_finds_late_document_evidence() -> None:
    filler = ("General quote language without key evidence. " * 40 + "\n") * 40
    tail_evidence = "Delivery date is December 19, 2026. Customer PO is PO-9999."
    text = f"Intro section.\n{filler}\n{tail_evidence}\n"

    context, note = build_retrieved_pdf_context(
        text,
        ["delivery date", "PO-9999"],
        max_context_chars=6000,
        chunk_size=900,
        chunk_overlap=120,
        include_last_chunk=False,
    )

    assert "PO-9999" in context
    assert "Delivery date is December 19, 2026." in context
    assert "RAG context:" in note


def test_build_retrieved_pdf_context_respects_character_budget() -> None:
    text = ("spec line " * 1000).strip()

    context, _ = build_retrieved_pdf_context(
        text,
        ["spec line"],
        max_context_chars=2500,
        chunk_size=700,
        chunk_overlap=100,
    )

    assert len(context) <= 2500


def test_chunk_text_obeys_max_chunks() -> None:
    text = "A" * 10000
    chunks = chunk_text(text, chunk_size=1000, overlap=100, max_chunks=3)
    assert len(chunks) == 3


def test_weighted_hints_recover_direction_chunk_from_primary_signals() -> None:
    noisy_chunk = (
        "Labelling machine model monostar pharma for stable base container "
        "coming from motorized conveyor with indexing system and change parts. "
    ) * 70
    direction_chunk = (
        "Equipment General Specification. Conveyor and Compress Air details. "
        "Line Direction is From left to Right. Power 220 Volts, 3 Phases, 60/50 Hz."
    )
    text = f"{noisy_chunk}\n\n{noisy_chunk}\n\n{direction_chunk}\n\n{noisy_chunk}"

    # Without weighted primary hints, noise-heavy machine context dominates.
    unweighted_context, _ = build_retrieved_pdf_context(
        text,
        query_hints=["monostar pharma", "stable base container", "motorized conveyor"],
        max_context_chars=4200,
        chunk_size=900,
        chunk_overlap=120,
        include_last_chunk=False,
        weighted_hints_enabled=False,
    )

    weighted_context, _ = build_retrieved_pdf_context(
        text,
        query_hints=["monostar pharma", "stable base container", "motorized conveyor"],
        primary_query_hints=["line direction", "from left to right", "60/50 hz", "220 volts"],
        secondary_query_hints=["monostar pharma", "stable base container", "motorized conveyor"],
        max_context_chars=4200,
        chunk_size=900,
        chunk_overlap=120,
        include_last_chunk=False,
        weighted_hints_enabled=True,
    )

    assert "from left to right" not in unweighted_context.lower()
    assert "from left to right" in weighted_context.lower()
