"""FastAPI dependencies."""

from .auth import (
    get_current_user,
    is_admin_user,
    require_admin_user,
    require_authenticated_user,
)

__all__ = [
    "get_current_user",
    "is_admin_user",
    "require_authenticated_user",
    "require_admin_user",
]
