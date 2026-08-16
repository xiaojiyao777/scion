"""Shared edit-protocol error type."""

from __future__ import annotations


class PatchEditProtocolError(ValueError):
    """Raised when a typed edit cannot be safely normalized."""
