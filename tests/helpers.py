"""Shared test helpers used across the suite."""

from __future__ import annotations

import os
import uuid
from collections.abc import Callable
from typing import Any

import pytest


def login(
    client: Any,
    username: str = "admin",
    password: str = "test-admin-password",
) -> dict[str, Any]:
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    return payload if isinstance(payload, dict) else {}


def unique_name(prefix: str = "value") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def unique_username(prefix: str = "user") -> str:
    return unique_name(prefix)


def stub_get_client_by_id(
    return_value: dict[str, Any] | None = None,
    *,
    expected_id: int | None = None,
) -> Callable[..., dict[str, Any] | None]:
    default = {"id": 1, "client_name": "Test Client"}
    payload = return_value or default

    def _stub(quote_id: int, **_kwargs: Any) -> dict[str, Any] | None:
        if expected_id is not None and quote_id != expected_id:
            return None
        return payload

    return _stub


class DocCapture:
    """Capture call arguments while returning a fixed value or computed payload."""

    def __init__(
        self,
        *,
        return_value: Any = None,
        return_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
        self._return_value = return_value
        self._return_factory = return_factory

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        self.calls.append((args, kwargs))
        if self._return_factory is not None:
            return self._return_factory(*args, **kwargs)
        return self._return_value


def skip_unless_pdf(path: str | os.PathLike[str]) -> None:
    if not os.path.exists(path):
        pytest.skip(f"PDF not found: {path}")
