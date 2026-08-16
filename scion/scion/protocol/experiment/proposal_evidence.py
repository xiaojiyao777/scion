"""Generic dispatch for problem-owned proposal-visible mechanism evidence."""
from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Any

from scion.problem.providers import resolve_proposal_mechanism_evidence_provider

logger = logging.getLogger(__name__)

_ENVELOPE_SCHEMA = "scion.problem_proposal_mechanism_evidence.v1"


def problem_proposal_mechanism_evidence(
    *,
    stage: str,
    selected_surface: str | None,
    runtime_pairs: Sequence[Mapping[str, Any]],
    problem_spec: Any = None,
    adapter: Any = None,
) -> dict[str, Any]:
    """Return a safe proposal-only envelope, or ``{}`` on provider absence/error."""

    if stage != "screening" or not runtime_pairs:
        return {}
    try:
        provider = resolve_proposal_mechanism_evidence_provider(
            problem_spec=problem_spec,
            adapter=adapter,
        )
        summarize = getattr(provider, "summarize_proposal_mechanism_evidence", None)
        if not callable(summarize):
            return {}
        raw = summarize(
            stage=stage,
            selected_surface=selected_surface,
            runtime_pairs=runtime_pairs,
        )
    except Exception:
        logger.warning(
            "Problem proposal mechanism evidence provider failed; preserving formal result",
            exc_info=True,
        )
        return {}
    if not isinstance(raw, Mapping) or not raw:
        return {}
    family = _problem_family(problem_spec, adapter)
    return {
        "schema_version": _ENVELOPE_SCHEMA,
        "problem_family": family or "unknown",
        "producer": "problem_provider",
        "evidence": dict(raw),
    }


def is_proposal_mechanism_evidence_envelope(value: Any) -> bool:
    return bool(
        isinstance(value, Mapping)
        and value.get("schema_version") == _ENVELOPE_SCHEMA
        and value.get("producer") == "problem_provider"
        and isinstance(value.get("evidence"), Mapping)
    )


def _problem_family(problem_spec: Any, adapter: Any) -> str:
    adapter_spec = getattr(adapter, "spec", None) or getattr(adapter, "_spec", None)
    spec_v1 = getattr(problem_spec, "spec_v1", None)
    for owner in (adapter_spec, spec_v1, problem_spec):
        value = str(
            getattr(owner, "id", None)
            or getattr(owner, "problem_id", None)
            or getattr(owner, "name", "")
            or ""
        ).strip()
        if value:
            return value
    return ""


__all__ = [
    "is_proposal_mechanism_evidence_envelope",
    "problem_proposal_mechanism_evidence",
]
