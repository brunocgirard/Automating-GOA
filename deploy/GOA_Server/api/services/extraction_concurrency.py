"""Concurrency controls for extraction requests."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Final

from api.services._env_helpers import env_positive_int as _env_positive_int


QUEUE_STATUS_MESSAGE: Final[str] = "Processing queued, other extractions in progress."

_STATE_LOCK = threading.Lock()
_GLOBAL_SEMAPHORE: threading.BoundedSemaphore | None = None
_PER_USER_SEMAPHORES: dict[int, threading.BoundedSemaphore] = {}
_LIMITS_CACHE: tuple[int, int] | None = None
def _read_limits() -> tuple[int, int]:
    global_limit = _env_positive_int("LLM_EXTRACTION_MAX_CONCURRENCY", 3, min_value=1)
    per_user_limit = _env_positive_int("LLM_EXTRACTION_MAX_CONCURRENCY_PER_USER", 1, min_value=1)
    # Per-user limit must never exceed the global extraction limit.
    return global_limit, min(global_limit, per_user_limit)


def _ensure_state() -> tuple[threading.BoundedSemaphore, int]:
    global _GLOBAL_SEMAPHORE, _PER_USER_SEMAPHORES, _LIMITS_CACHE

    limits = _read_limits()
    with _STATE_LOCK:
        if _GLOBAL_SEMAPHORE is None or _LIMITS_CACHE != limits:
            _GLOBAL_SEMAPHORE = threading.BoundedSemaphore(limits[0])
            _PER_USER_SEMAPHORES = {}
            _LIMITS_CACHE = limits
        return _GLOBAL_SEMAPHORE, limits[1]


def _get_user_semaphore(user_id: int, per_user_limit: int) -> threading.BoundedSemaphore:
    with _STATE_LOCK:
        user_semaphore = _PER_USER_SEMAPHORES.get(user_id)
        if user_semaphore is None:
            user_semaphore = threading.BoundedSemaphore(per_user_limit)
            _PER_USER_SEMAPHORES[user_id] = user_semaphore
        return user_semaphore


@dataclass(slots=True)
class ExtractionSlotLease:
    """Lease for one extraction slot with queue timing metadata."""

    user_id: int
    queued: bool
    wait_ms: int
    _user_semaphore: threading.BoundedSemaphore = field(repr=False)
    _global_semaphore: threading.BoundedSemaphore = field(repr=False)
    _released: bool = field(default=False, init=False, repr=False)

    @property
    def queue_message(self) -> str | None:
        return QUEUE_STATUS_MESSAGE if self.queued else None

    def release(self) -> None:
        if self._released:
            return
        # Release in reverse order of acquisition.
        self._global_semaphore.release()
        self._user_semaphore.release()
        self._released = True

    def __enter__(self) -> "ExtractionSlotLease":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()


def acquire_extraction_slot(user_id: int) -> ExtractionSlotLease:
    """
    Acquire extraction capacity for one request.

    Uses two semaphores:
    - global extraction concurrency
    - per-user extraction concurrency
    """
    if not isinstance(user_id, int) or user_id <= 0:
        raise ValueError("A valid authenticated user id is required for extraction concurrency control.")

    global_semaphore, per_user_limit = _ensure_state()
    user_semaphore = _get_user_semaphore(user_id, per_user_limit)

    queued = False
    start = time.monotonic()

    if not user_semaphore.acquire(blocking=False):
        queued = True
        user_semaphore.acquire()

    if not global_semaphore.acquire(blocking=False):
        queued = True
        global_semaphore.acquire()

    wait_ms = max(0, int((time.monotonic() - start) * 1000))
    return ExtractionSlotLease(
        user_id=user_id,
        queued=queued,
        wait_ms=wait_ms,
        _user_semaphore=user_semaphore,
        _global_semaphore=global_semaphore,
    )


def reset_extraction_concurrency_state() -> None:
    """Testing helper to reset semaphore state and apply current env config."""
    global _GLOBAL_SEMAPHORE, _PER_USER_SEMAPHORES, _LIMITS_CACHE
    with _STATE_LOCK:
        _GLOBAL_SEMAPHORE = None
        _PER_USER_SEMAPHORES = {}
        _LIMITS_CACHE = None
