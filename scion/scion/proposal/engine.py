"""CreativeLayer — LLM-backed proposal generation (Round 1 and Round 2)."""
from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict

from pydantic import ValidationError

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
    HypothesisProposalInput,
    PatchProposalInput,
)


class ProposalValidationError(Exception):
    """Raised when LLM response fails Pydantic schema validation."""


class CreativeLayer:
    """Generates HypothesisProposal (Round 1) and PatchProposal (Round 2) via LLM.

    The client must implement ``call(prompt, response_schema, model) -> dict``.
    Both :class:`~scion.proposal.llm_client.LLMClient` and
    :class:`~scion.proposal.mock_client.MockLLMClient` satisfy this interface.

    Errors from the LLM client (LLMRetryExhaustedError, LLMFormatError, …)
    propagate to the caller (CampaignManager → FailureRouter).
    """

    def __init__(
        self,
        llm_client: Any,
        model: str | None = None,
        *,
        trace_dir: str | None = None,
    ) -> None:
        self._client = llm_client
        # Inherit model from LLMClient if not explicitly set
        self._model = model or getattr(llm_client, 'model', None) or "claude-opus-4-6"
        self._trace_dir = trace_dir

    # ------------------------------------------------------------------
    # Round 1 — hypothesis proposal
    # ------------------------------------------------------------------

    def generate_hypothesis(self, context: Dict[str, Any]) -> HypothesisProposal:
        """Generate a HypothesisProposal using tool_use."""
        system_blocks, user_prompt = _split_hypothesis_context(context)
        raw = self._call_with_trace(
            request_kind="hypothesis",
            prompt=user_prompt,
            tool=HYPOTHESIS_TOOL,
            system_blocks=system_blocks,
            context=context,
        )
        return _parse_hypothesis(raw)

    # ------------------------------------------------------------------
    # Round 2 — code / patch proposal
    # ------------------------------------------------------------------

    def generate_code(self, context: Dict[str, Any]) -> PatchProposal:
        """Generate a PatchProposal using tool_use (API handles JSON escape)."""
        system_blocks, user_prompt = _split_code_context(context)
        raw = self._call_with_trace(
            request_kind="code",
            prompt=user_prompt,
            tool=PATCH_TOOL,
            system_blocks=system_blocks,
            context=context,
        )
        return _parse_patch(raw)

    def fix_code(self, context: Dict[str, Any]) -> PatchProposal:
        """Generate a corrected PatchProposal after a light verification failure.

        Uses tool_use (same as generate_hypothesis/generate_code) to avoid
        JSON escape issues when code_content contains complex Python.
        """
        system_blocks, user_prompt = _split_fix_context(context)
        raw = self._call_with_trace(
            request_kind="fix",
            prompt=user_prompt,
            tool=FIX_TOOL,
            system_blocks=system_blocks,
            context=context,
        )
        return _parse_patch(raw)

    def _call_with_trace(
        self,
        *,
        request_kind: str,
        prompt: str,
        tool: Dict[str, Any],
        system_blocks: "list[dict]",
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        trace = _TraceWriter(self._trace_dir)
        trace_path = trace.write_start(
            request_kind=request_kind,
            model=self._model,
            tool=tool,
            prompt=prompt,
            system_blocks=system_blocks,
            context=context,
        )
        try:
            raw = self._client.call_with_tool(
                prompt, tool, self._model,
                system_blocks=system_blocks,
            )
        except Exception as exc:
            trace.write_finish(trace_path, ok=False, error=str(exc))
            raise
        trace.write_finish(trace_path, ok=True, response=raw)
        return raw


class _TraceWriter:
    """Persist prompt/response artifacts for experiment auditability."""

    def __init__(self, trace_dir: str | None) -> None:
        self._trace_dir = trace_dir

    def write_start(
        self,
        *,
        request_kind: str,
        model: str,
        tool: Dict[str, Any],
        prompt: str,
        system_blocks: "list[dict]",
        context: Dict[str, Any],
    ) -> str | None:
        if not self._trace_dir:
            return None
        os.makedirs(self._trace_dir, exist_ok=True)
        digest = _prompt_hash(system_blocks, prompt)
        trace_id = (
            f"{datetime.now().strftime('%Y%m%dT%H%M%S%f')}_"
            f"{request_kind}_{digest[:10]}_{uuid.uuid4().hex[:8]}"
        )
        path = os.path.join(self._trace_dir, f"{trace_id}.json")
        payload = {
            "trace_id": trace_id,
            "request_kind": request_kind,
            "model": model,
            "tool_name": tool.get("name"),
            "prompt_hash": digest,
            "created_at": datetime.now().isoformat(),
            "branch_id": context.get("branch_id"),
            "champion_version": context.get("champion_version"),
            "system_blocks": system_blocks,
            "user_prompt": prompt,
            "tool_schema": tool.get("input_schema") or tool.get("function", {}).get("parameters"),
            "ok": None,
        }
        _write_json(path, payload)
        return path

    def write_finish(
        self,
        path: str | None,
        *,
        ok: bool,
        response: Dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as fh:
                payload = json.load(fh)
        except (OSError, json.JSONDecodeError):
            payload = {}
        payload.update({
            "finished_at": datetime.now().isoformat(),
            "ok": ok,
        })
        if response is not None:
            payload["response"] = response
        if error is not None:
            payload["error"] = error
        _write_json(path, payload)


def _prompt_hash(system_blocks: "list[dict]", prompt: str) -> str:
    blob = json.dumps(
        {"system_blocks": system_blocks, "user_prompt": prompt},
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _write_json(path: str, payload: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False, default=str)


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def _parse_hypothesis(raw: Dict[str, Any]) -> HypothesisProposal:
    """Convert a validated LLM response dict into a HypothesisProposal."""
    try:
        validated = HypothesisProposalInput(**raw)
    except ValidationError as exc:
        raise ProposalValidationError(str(exc)) from exc
    return HypothesisProposal(
        hypothesis_text=validated.hypothesis_text,
        change_locus=validated.change_locus,
        action=validated.action,  # type: ignore[arg-type]
        target_file=validated.target_file or None,
        predicted_direction=validated.predicted_direction,  # type: ignore[arg-type]
        target_weakness=validated.target_weakness,
        expected_effect=validated.expected_effect,
        suggested_weight=validated.suggested_weight,
        target_objectives=tuple(validated.target_objectives or ()),
        protected_objectives=tuple(validated.protected_objectives or ()),
        objective_tradeoff_policy=validated.objective_tradeoff_policy,
        no_op_condition=validated.no_op_condition,
        risk_to_higher_priority=validated.risk_to_higher_priority,
    )


def _parse_patch(raw: Dict[str, Any]) -> PatchProposal:
    """Convert a validated LLM response dict into a PatchProposal."""
    try:
        validated = PatchProposalInput(**raw)
    except ValidationError as exc:
        raise ProposalValidationError(str(exc)) from exc
    return PatchProposal(
        file_path=validated.file_path,
        action=validated.action,  # type: ignore[arg-type]
        code_content=validated.code_content,
        test_hint=validated.test_hint or None,
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

    System: Block 1 (static, high cache hit) + Block 2 (champion, changes on promote)
    User (dynamic): experiment history + blacklist + siblings + analysis steps + task
    """
    D = _DefaultDict(context)

    # Block 1: Static role + problem spec + solver mechanics (never changes)
    static_text = (
        "You are a research agent optimising a combinatorial optimisation solver's operator pool.\n"
        "Your goal is to propose ONE novel hypothesis that, if implemented, would improve solver quality.\n\n"
        f"## Problem Summary\n{D['problem_summary']}\n\n"
        f"{D['objective_policy_guidance']}\n\n"
        f"## How the VNS Solver Uses Operators\n"
        f"- The solver maintains a pool of 40 candidate solutions, sorted by objective.\n"
        f"- Each iteration: for EACH solution in the pool, ONE operator is randomly selected (weighted) and applied.\n"
        f"- If the result is INFEASIBLE (violates any hard constraint), it is DISCARDED.\n"
        f"- Pool update: new + old solutions merged, top 40 by the problem objective policy kept.\n"
        f"- Runs 200 iterations or until 30 consecutive no-improvement iterations.\n"
        f"- Total: ~8000 operator invocations per solve run.\n\n"
        f"Design implications for new operators:\n"
        f"- Your operator will be called ~1000 times. It MUST produce feasible solutions.\n"
        f"- High variance is good: the pool filters bad outcomes and keeps rare great ones.\n"
        f"- A large improvement on 5% of calls is more valuable than a tiny improvement on 50%.\n"
        f"- Your operator competes with existing operators for invocation share.\n"
        f"- It must provide a capability the existing operators LACK, not duplicate them."
    )

    # Block 2: Champion code + stats (changes only on champion promotion)
    champion_text = (
        f"## Current Champion Operator Code\n"
        f"Study these carefully before proposing anything \u2014 avoid duplicating existing logic.\n\n"
        f"{D['champion_operators_code']}\n\n"
        f"## Champion State\n{D['champion_stats']}"
    )

    # Block 3: Branch-specific context (branch code, coverage, strategy, baselines)
    # Only included when at least one field is non-empty
    branch_context_parts = []

    # J1: Search memory (cross-branch history) — highest priority dynamic block
    if D["search_memory"]:
        branch_context_parts.append(D["search_memory"])

    # J2: Saturation signals
    if D["saturation_signal"]:
        branch_context_parts.append(D["saturation_signal"])

    # J-patch: Research log (cross-branch trajectory)
    if D["research_log"]:
        branch_context_parts.append(D["research_log"])

    if D["branch_code"] and D["branch_code"] != D["champion_operators_code"]:
        branch_context_parts.append(
            f"## Current Branch Code\n"
            f"This branch has diverged from the champion. The current branch code is:\n\n"
            f"{D['branch_code']}"
        )
    if D["branch_direction"]:
        branch_context_parts.append(
            f"## Branch Direction\n{D['branch_direction']}"
        )
    if D["exploration_coverage"]:
        branch_context_parts.append(
            f"## Exploration Coverage\n{D['exploration_coverage']}"
        )
    if D["strategy_guidance"]:
        branch_context_parts.append(
            f"## Strategy Guidance\n{D['strategy_guidance']}"
        )
    if D["search_control_guidance"]:
        branch_context_parts.append(D["search_control_guidance"])
    if D["champion_baselines"]:
        branch_context_parts.append(
            f"## Champion Baseline Hints\n{D['champion_baselines']}"
        )
    # J3: Failure pattern warning (Sprint H2 — was built but not injected)
    if D["failure_pattern_warning"]:
        branch_context_parts.append(
            f"## Failure Pattern Warning\n{D['failure_pattern_warning']}"
        )
    # I3: Forced locus constraint
    if D["locus_constraint"]:
        branch_context_parts.append(D["locus_constraint"])
    # L2: Objective improvement guidance (tendency-based)
    if D.get("objective_guidance"):
        branch_context_parts.append(D["objective_guidance"])
    if D.get("objective_opportunity_profile"):
        branch_context_parts.append(D["objective_opportunity_profile"])
    # J6: Weight optimization feedback
    if D["weight_opt_feedback"]:
        branch_context_parts.append(D["weight_opt_feedback"])

    system_blocks = [
        {
            "type": "text",
            "text": static_text,
            "cache_control": _CACHE_5M,
        },
        {
            "type": "text",
            "text": champion_text,
            "cache_control": _CACHE_5M,
        },
    ]
    if branch_context_parts:
        system_blocks.append({
            "type": "text",
            "text": "\n\n".join(branch_context_parts),
        })

    user_prompt = (
        f"## Experiment History \u2014 This Branch\n{D['experiment_history']}\n\n"
        f"## Globally Failed / Blacklisted Approaches\n{D['blacklist_summary']}\n\n"
        f"## Currently Occupied (C10 will auto-reject duplicates)\n{D['active_hyp_summary']}\n\n"
        f"## Sibling Branches\n{D['sibling_summary']}\n\n"
        f"## Analysis Steps (follow in order)\n"
        f"1. Read EVERY champion operator. For each, note: what move type, what objective(s) it improves or protects, what it cannot improve.\n"
        f"2. Identify specific GAPS \u2014 what improvements are IMPOSSIBLE with the current pool?\n"
        f"3. Check experiment history \u2014 which attempts at filling gaps failed, and WHY?\n"
        f"4. Only then propose a hypothesis targeting an identified gap.\n"
        f"5. In the hypothesis text, state target objective(s), protected objective(s), "
        f"and the no-op condition that avoids harming protected objectives.\n\n"
        f"Runtime constraint: proposed operators are called many times inside the VNS pool loop. "
        f"Do not propose unbounded high-order enumeration over vehicles/orders; describe any top-k, "
        f"sampling, or early-stop cap needed to keep runtime comparable to the champion.\n\n"
        f"If your hypothesis duplicates an existing operator's capability (even partially), it will be REJECTED.\n\n"
        f"## Task\n"
        f"Propose ONE new hypothesis for improving the solver.\n"
        f"Choose a category from {D['operator_categories']} as `change_locus`.\n"
        f"Set `action` to one of: \"modify\", \"create_new\", \"remove\".\n"
        f"If action is \"modify\" or \"remove\", provide `target_file`.\n"
    )

    return system_blocks, user_prompt


def _split_code_context(
    context: Dict[str, Any],
) -> "tuple[list[dict], str]":
    """Split code context into system blocks (cacheable) and user prompt.

    System: Block 1 (static role + rules + interface) + Block 2 (champion code)
    User (dynamic): hypothesis + target file + constraints
    """
    D = _DefaultDict(context)

    # Block 1: Static role + quality rules + problem + interface (never changes)
    static_text = (
        "You are a software engineer implementing an operator for a combinatorial optimisation solver framework.\n"
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
        "Follow the problem-specific feasibility and consistency rules in the interface specification exactly.\n\n"
        f"## Problem Summary\n{D['problem_summary']}\n\n"
        f"## Operator Interface Specification\n"
        f"All operator classes MUST conform to this interface exactly:\n\n"
        f"{D['operator_interface_spec']}\n\n"
        f"## Allowed Imports\n"
        f"Only use modules from this whitelist \u2014 any other import will be rejected:\n"
        f"{D['import_whitelist']}"
    )

    # Block 2: Champion code (changes only on champion promotion)
    champion_text = (
        f"## Current Champion Operator Code\n"
        f"Study these implementations for coding style, data model usage, and patterns:\n\n"
        f"{D['champion_operators_code']}"
    )

    system_blocks = [
        {
            "type": "text",
            "text": static_text,
            "cache_control": _CACHE_5M,
        },
        {
            "type": "text",
            "text": champion_text,
            "cache_control": _CACHE_5M,
        },
    ]

    prior_failure_section = ""
    if D["prior_code_failure"]:
        prior_failure_section = (
            f"## Previous Attempt Failed\n"
            f"The previous code generation failed with:\n"
            f"{D['prior_code_failure']}\n"
            f"Avoid the same mistake.\n\n"
        )

    user_prompt = (
        f"{prior_failure_section}"
        f"## Hypothesis to Implement\n{D['hypothesis_detail']}\n\n"
        f"## Target File (current content)\n{D['target_file_code']}\n\n"
        f"## Reference Operators\n{D['reference_operators']}\n\n"
        f"## Constraints\n"
        f"- Editable files: {D['editable_patterns']}\n"
        f"- Frozen (DO NOT MODIFY): {D['frozen_patterns']}\n"
        f"- Conform to the operator interface specification exactly\n"
        f"- Preserve all feasibility, consistency, and determinism invariants described there\n"
        f"- Use the provided `rng` argument for all randomness; do not use system entropy\n"
        f"- Return the new solution/artifact, or the original if no valid move is found\n\n"
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
        "You are a software engineer fixing an optimisation operator that failed verification.\n"
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
        f"- Preserve the operator interface described above exactly\n"
        f"- Make only the minimal changes needed to fix the reported failure\n"
    )

    return system_blocks, user_prompt
