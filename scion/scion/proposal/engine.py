"""CreativeLayer — LLM-backed proposal generation (Round 1 and Round 2)."""
from __future__ import annotations

from typing import Any, Dict

from scion.core.models import HypothesisProposal, PatchProposal
from scion.proposal.schemas import (
    HYPOTHESIS_PROPOSAL_SCHEMA,
    PATCH_PROPOSAL_SCHEMA,
    HYPOTHESIS_PROMPT_TEMPLATE,
    CODE_PROMPT_TEMPLATE,
    FIX_PROMPT_TEMPLATE,
)


class CreativeLayer:
    """Generates HypothesisProposal (Round 1) and PatchProposal (Round 2) via LLM.

    The client must implement ``call(prompt, response_schema, model) -> dict``.
    Both :class:`~scion.proposal.llm_client.LLMClient` and
    :class:`~scion.proposal.mock_client.MockLLMClient` satisfy this interface.

    Errors from the LLM client (LLMRetryExhaustedError, LLMFormatError, …)
    propagate to the caller (CampaignManager → FailureRouter).
    """

    def __init__(self, llm_client: Any, model: str = "claude-sonnet-4-6") -> None:
        self._client = llm_client
        self._model = model

    # ------------------------------------------------------------------
    # Round 1 — hypothesis proposal
    # ------------------------------------------------------------------

    def generate_hypothesis(self, context: Dict[str, Any]) -> HypothesisProposal:
        """Generate a HypothesisProposal from the given context dict.

        Expected context keys (from ContextManager.build_hypothesis_context):
            problem_name, operator_categories, pool_summary,
            branch_history, blacklist_summary, sibling_summary.
        """
        prompt = HYPOTHESIS_PROMPT_TEMPLATE.format_map(_DefaultDict(context))
        raw = self._client.call(prompt, HYPOTHESIS_PROPOSAL_SCHEMA, self._model)
        return _parse_hypothesis(raw)

    # ------------------------------------------------------------------
    # Round 2 — code / patch proposal
    # ------------------------------------------------------------------

    def generate_code(self, context: Dict[str, Any]) -> PatchProposal:
        """Generate a PatchProposal implementing the current hypothesis.

        Expected context keys (from ContextManager.build_code_context):
            problem_name, editable_patterns, frozen_patterns,
            import_whitelist, hypothesis_text, change_locus, action,
            target_file, champion_code.
        """
        prompt = CODE_PROMPT_TEMPLATE.format_map(_DefaultDict(context))
        raw = self._client.call(prompt, PATCH_PROPOSAL_SCHEMA, self._model)
        return _parse_patch(raw)

    def fix_code(self, context: Dict[str, Any]) -> PatchProposal:
        """Generate a corrected PatchProposal after a light verification failure.

        Expected context keys (from ContextManager.build_fix_context):
            problem_name, editable_patterns, frozen_patterns,
            import_whitelist, file_path, action, code_content,
            failure_severity, first_failure, failure_details.
        """
        prompt = FIX_PROMPT_TEMPLATE.format_map(_DefaultDict(context))
        raw = self._client.call(prompt, PATCH_PROPOSAL_SCHEMA, self._model)
        return _parse_patch(raw)


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def _parse_hypothesis(raw: Dict[str, Any]) -> HypothesisProposal:
    """Convert a validated LLM response dict into a HypothesisProposal."""
    return HypothesisProposal(
        hypothesis_text=str(raw.get("hypothesis_text", "")),
        change_locus=str(raw.get("change_locus", "")),
        action=raw.get("action", "modify"),  # type: ignore[arg-type]
        target_file=raw.get("target_file") or None,
        predicted_direction=raw.get("predicted_direction", "exploratory"),  # type: ignore[arg-type]
        target_weakness=str(raw.get("target_weakness", "")),
        expected_effect=str(raw.get("expected_effect", "")),
        suggested_weight=_to_float_or_none(raw.get("suggested_weight")),
    )


def _parse_patch(raw: Dict[str, Any]) -> PatchProposal:
    """Convert a validated LLM response dict into a PatchProposal."""
    return PatchProposal(
        file_path=str(raw.get("file_path", "")),
        action=raw.get("action", "modify"),  # type: ignore[arg-type]
        code_content=str(raw.get("code_content", "")),
        test_hint=raw.get("test_hint") or None,
    )


def _to_float_or_none(v: Any) -> "float | None":
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


class _DefaultDict(dict):
    """dict subclass that returns '' for missing keys (safe format_map)."""

    def __missing__(self, key: str) -> str:
        return ""
