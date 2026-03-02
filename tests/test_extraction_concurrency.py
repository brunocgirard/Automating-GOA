"""Unit tests for extraction concurrency controls."""

from __future__ import annotations

import threading
import time

from api.services.extraction_concurrency import (
    ExtractionSlotLease,
    acquire_extraction_slot,
    reset_extraction_concurrency_state,
)


def test_acquire_slot_without_queue(monkeypatch) -> None:
    monkeypatch.setenv("LLM_EXTRACTION_MAX_CONCURRENCY", "2")
    monkeypatch.setenv("LLM_EXTRACTION_MAX_CONCURRENCY_PER_USER", "1")
    reset_extraction_concurrency_state()

    lease = acquire_extraction_slot(1)
    try:
        assert lease.queued is False
        assert lease.queue_message is None
        assert lease.wait_ms >= 0
    finally:
        lease.release()


def test_per_user_limit_queues_second_request(monkeypatch) -> None:
    monkeypatch.setenv("LLM_EXTRACTION_MAX_CONCURRENCY", "2")
    monkeypatch.setenv("LLM_EXTRACTION_MAX_CONCURRENCY_PER_USER", "1")
    reset_extraction_concurrency_state()

    first = acquire_extraction_slot(7)
    acquired: dict[str, ExtractionSlotLease] = {}

    def _worker() -> None:
        lease = acquire_extraction_slot(7)
        acquired["lease"] = lease

    worker = threading.Thread(target=_worker, daemon=True)
    worker.start()
    time.sleep(0.15)
    assert worker.is_alive()

    first.release()
    worker.join(timeout=2.0)
    assert not worker.is_alive()

    second = acquired.get("lease")
    assert second is not None
    assert second.queued is True
    assert second.wait_ms >= 100
    second.release()


def test_global_limit_queues_other_user(monkeypatch) -> None:
    monkeypatch.setenv("LLM_EXTRACTION_MAX_CONCURRENCY", "1")
    monkeypatch.setenv("LLM_EXTRACTION_MAX_CONCURRENCY_PER_USER", "1")
    reset_extraction_concurrency_state()

    first = acquire_extraction_slot(101)
    acquired: dict[str, ExtractionSlotLease] = {}

    def _worker() -> None:
        lease = acquire_extraction_slot(202)
        acquired["lease"] = lease

    worker = threading.Thread(target=_worker, daemon=True)
    worker.start()
    time.sleep(0.15)
    assert worker.is_alive()

    first.release()
    worker.join(timeout=2.0)
    assert not worker.is_alive()

    second = acquired.get("lease")
    assert second is not None
    assert second.queued is True
    assert second.wait_ms >= 100
    second.release()
