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

    def __init__(self, llm_client: Any, model: str | None = None) -> None:
        self._client = llm_client
        # Inherit model from LLMClient if not explicitly set
        self._model = model or getattr(llm_client, 'model', None) or "claude-opus-4-6"

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

_CACHE_5M = {"type": "ephemeral"}


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
        f"## Champion State\n{D['champion_stats']}\n\n"
        f"## How the VNS Solver Uses Operators\n"
        f"- The solver maintains a pool of 40 candidate solutions, sorted by objective.\n"
        f"- Each iteration: for EACH solution in the pool, ONE operator is randomly selected (weighted) and applied.\n"
        f"- If the result is INFEASIBLE (violates any hard constraint), it is DISCARDED.\n"
        f"- Pool update: new + old solutions merged, top 40 by lexicographic objective kept.\n"
        f"- Runs 200 iterations or until 30 consecutive no-improvement iterations.\n"
        f"- Total: ~8000 operator invocations per solve run.\n\n"
        f"Design implications for new operators:\n"
        f"- Your operator will be called ~1000 times. It MUST produce feasible solutions.\n"
        f"- High variance is good: the pool filters bad outcomes and keeps rare great ones.\n"
        f"- A large improvement on 5% of calls is more valuable than a tiny improvement on 50%.\n"
        f"- Your operator competes with 6 existing operators for invocation share.\n"
        f"- It must provide a capability the existing operators LACK, not duplicate them."
    )

    system_blocks = [
        {
            "type": "text",
            "text": system_text,
            "cache_control": _CACHE_5M,
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
        "## Code Quality Rules\n"
        "- Write ONLY what the hypothesis requires. No extra features, helper functions, or abstractions.\n"
        "- Do not add error handling for impossible cases. Trust the data model.\n"
        "- Do not add comments explaining WHAT the code does \u2014 only WHY for non-obvious choices.\n"
        "- Prefer simple, direct code over clever abstractions.\n"
        "- Match the coding style of the existing champion operators EXACTLY.\n"
        "- Do NOT add logging, print statements, or debug output.\n\n"
        "## Feasibility is Non-Negotiable\n"
        "An operator that produces infeasible solutions is WORSE than no operator. "
        "Before returning, mentally verify:\n"
        "1. Every order is assigned to exactly one vehicle\n"
        "2. assignment dict and vehicle.order_ids are consistent\n"
        "3. No vehicle exceeds capacity\n"
        "4. Hazardous goods constraints satisfied\n"
        "5. Region and category constraints hold\n\n"
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
            "cache_control": _CACHE_5M,
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
            "cache_control": _CACHE_5M,
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
