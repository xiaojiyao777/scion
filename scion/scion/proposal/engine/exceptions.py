"""Proposal engine exceptions."""

from __future__ import annotations


class ProposalValidationError(Exception):
    """Raised when LLM response fails Pydantic schema validation."""
