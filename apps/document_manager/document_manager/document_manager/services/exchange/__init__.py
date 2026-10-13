# -*- coding: utf-8 -*-
"""Exchange of archival data as XML (module 5): who may use it (capabilities exchange.export / exchange.import)."""

from document_manager.document_manager.permissions import assert_capability, has_capability

CAPABILITIES = ("exchange.export", "exchange.import")


def can_exchange(user: str | None = None) -> bool:
    return has_capability(*CAPABILITIES, user=user)


def require_exchange(*capabilities: str) -> None:
    """Either exchange capability by default; a single one when the action needs it (export or import)."""
    assert_capability(*(capabilities or CAPABILITIES))
