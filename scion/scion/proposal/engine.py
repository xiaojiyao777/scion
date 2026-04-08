"""CreativeLayer — LLM-backed proposal generation (Round 1 and Round 2)."""
from __future__ import annotations

from typing import Any, Dict

from scion.core.models import HypothesisProposal, PatchProposal
from scion.proposal.schemas import (
    HYPOTHESIS_PROPOSAL_SCHEMA,
    PATCH_PROPOSAL_SCHEMA,
    HYPOTHESIS_TOOL,
    PATCH_TOOL,
    FIX_TOOL,
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
        """Generate a HypothesisProposal using tool_use."""
        system_blocks, user_prompt = _split_hypothesis_context(context)
        raw = self._client.call_with_tool(
            user_prompt, HYPOTHESIS_TOOL, self._model,
            system_blocks=system_blocks,
        )
        return _parse_hypothesis(raw)

    # ------------------------------------------------------------------
    # Round 2 — code / patch proposal
    # ------------------------------------------------------------------

    def generate_code(self, context: Dict[str, Any]) -> PatchProposal:
        """Generate a PatchProposal using tool_use (API handles JSON escape)."""
        system_blocks, user_prompt = _split_code_context(context)
        raw = self._client.call_with_tool(
            user_prompt, PATCH_TOOL, self._model,
            system_blocks=system_blocks,
        )
        return _parse_patch(raw)

    def fix_code(self, context: Dict[str, Any]) -> PatchProposal:
        """Generate a corrected PatchProposal after a light verification failure.

        Uses tool_use (same as generate_hypothesis/generate_code) to avoid
        JSON escape issues when code_content contains complex Python.
        """
        system_blocks, user_prompt = _split_fix_context(context)
        raw = self._client.call_with_tool(
            user_prompt, FIX_TOOL, self._model,
            system_blocks=system_blocks,
        )
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


# ---------------------------------------------------------------------------
# Cache-aware prompt splitting
# ---------------------------------------------------------------------------

_CACHE_1H = {"type": "ephemeral", "ttl": "1h"}


def _split_hypothesis_context(
    context: Dict[str, Any],
) -> "tuple[list[dict], str]":
    """Split hypothesis context into system blocks (cacheable) and user prompt.

    System (1h cache): role + problem + champion code + champion stats
    User (dynamic): experiment history + blacklist + siblings + task + schema
    """
    D = _DefaultDict(context)

    system_text = (
        "You are a research agent optimising a combinatorial optimisation solver's operator pool.\n"
        "Your goal is to propose ONE novel hypothesis that, if implemented, would improve solver quality.\n\n"
        f"## Problem Summary\n{D['problem_summary']}\n\n"
        f"## Current Champion Operator Code\n"
        f"The following operators make up the current champion solution.\n"
        f"Study them carefully before proposing anything \u2014 avoid duplicating existing logic.\n\n"
        f"{D['champion_operators_code']}\n\n"
        f"## Champion State\n{D['champion_stats']}"
    )

    system_blocks = [
        {
            "type": "text",
            "text": system_text,
            "cache_control": _CACHE_1H,
        }
    ]

    user_prompt = (
        f"## Experiment History \u2014 This Branch\n{D['experiment_history']}\n\n"
        f"## Globally Failed / Blacklisted Approaches\n{D['blacklist_summary']}\n\n"
        f"## Sibling Branches\n{D['sibling_summary']}\n\n"
        f"## Task\n"
        f"Propose ONE new hypothesis for improving the solver.\n"
        f"Choose a category from {D['operator_categories']} as `change_locus`.\n"
        f"Set `action` to one of: \"modify\", \"create_new\", \"remove\".\n"
        f"If action is \"modify\" or \"remove\", provide `target_file`.\n"
        f"Explain your reasoning in `hypothesis_text`.\n\n"
        f"Respond with a single JSON object (no markdown fences, no extra text):\n"
        f"{{\n"
        f'  "hypothesis_text": "<string>",\n'
        f'  "change_locus": "<string>",\n'
        f'  "action": "modify" | "create_new" | "remove",\n'
        f'  "target_file": "<string or null>",\n'
        f'  "predicted_direction": "improve" | "tradeoff" | "exploratory",\n'
        f'  "target_weakness": "<string>",\n'
        f'  "expected_effect": "<string>",\n'
        f'  "suggested_weight": <number or null>\n'
        f"}}\n"
    )

    return system_blocks, user_prompt


def _split_code_context(
    context: Dict[str, Any],
) -> "tuple[list[dict], str]":
    """Split code context into system blocks (cacheable) and user prompt.

    System (1h cache): role + problem + champion code + interface spec
    User (dynamic): hypothesis + target file + task + schema
    """
    D = _DefaultDict(context)

    system_text = (
        "You are a software engineer implementing a VRP operator for a solver optimisation framework.\n"
        "Your task is to write the complete file contents that implement the approved hypothesis below.\n\n"
        f"## Problem Summary\n{D['problem_summary']}\n\n"
        f"## Current Champion Operator Code\n"
        f"Study these implementations for coding style, data model usage, and patterns:\n\n"
        f"{D['champion_operators_code']}\n\n"
        f"## Operator Interface Specification\n"
        f"All operator classes MUST conform to this interface exactly:\n\n"
        f"{D['operator_interface_spec']}\n\n"
        f"## Allowed Imports\n"
        f"Only use modules from this whitelist \u2014 any other import will be rejected:\n"
        f"{D['import_whitelist']}"
    )

    system_blocks = [
        {
            "type": "text",
            "text": system_text,
            "cache_control": _CACHE_1H,
        }
    ]

    user_prompt = (
        f"## Hypothesis to Implement\n{D['hypothesis_detail']}\n\n"
        f"## Target File (current content)\n{D['target_file_code']}\n\n"
        f"## Reference Operators\n{D['reference_operators']}\n\n"
        f"## Constraints\n"
        f"- Editable files: {D['editable_patterns']}\n"
        f"- Frozen (DO NOT MODIFY): {D['frozen_patterns']}\n"
        f"- Subclass `Operator` and implement `execute(self, solution, rng) -> Solution`\n"
        f"- Deep-copy the solution: `new_sol = solution.deep_copy()`\n"
        f"- Skip locked orders (`order.locked_vehicle_id is not None`)\n"
        f"- Use `rng` for all randomness, return new solution or original\n\n"
        f"Respond with a single JSON object (no markdown fences, no extra text):\n"
        f"{{\n"
        f'  "file_path": "<relative path, e.g. operators/my_operator.py>",\n'
        f'  "action": "modify" | "create" | "delete",\n'
        f'  "code_content": "<complete file contents>",\n'
        f'  "test_hint": "<optional note, or null>"\n'
        f"}}\n"
    )

    return system_blocks, user_prompt


def _split_fix_context(
    context: Dict[str, Any],
) -> "tuple[list[dict], str]":
    """Split fix context into system blocks (cacheable) and user prompt.

    System (1h cache): role + problem + operator interface + import whitelist
    User (dynamic): original code + failure details + task
    """
    D = _DefaultDict(context)

    system_text = (
        "You are a software engineer fixing a VRP operator that failed verification.\n"
        "Correct the code so it passes, while preserving the intended logic.\n\n"
        f"## Problem Summary\n{D['problem_summary']}\n\n"
        f"## Operator Interface Specification\n"
        f"All operator classes MUST conform to this interface exactly:\n\n"
        f"{D['operator_interface_spec']}\n\n"
        f"## Allowed Imports\n"
        f"Only use modules from this whitelist \u2014 any other import will be rejected:\n"
        f"{D['import_whitelist']}"
    )

    system_blocks = [
        {
            "type": "text",
            "text": system_text,
            "cache_control": _CACHE_1H,
        }
    ]

    user_prompt = (
        f"## Original Code That Failed\n{D['original_code']}\n\n"
        f"## Verification Failure Details\n{D['failure_detail']}\n\n"
        f"## Constraints\n"
        f"- Editable files: {D['editable_patterns']}\n"
        f"- Frozen (DO NOT MODIFY): {D['frozen_patterns']}\n"
        f"- Preserve the operator interface: `def execute(self, solution, rng) -> Solution`\n"
        f"- Make only the minimal changes needed to fix the reported failure\n"
    )

    return system_blocks, user_prompt
