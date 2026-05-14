"""CreativeLayer — LLM-backed proposal generation (Round 1 and Round 2)."""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict, Mapping

from pydantic import ValidationError

from scion.core.models import HypothesisProposal, PatchProposal
from scion.proposal.schemas import (
    HYPOTHESIS_PROPOSAL_SCHEMA,
    PATCH_PROPOSAL_SCHEMA,
    HYPOTHESIS_TOOL,
    PATCH_TOOL,
    FIX_TOOL,
    TOOL_SELECTION_TOOL,
    HYPOTHESIS_PROMPT_TEMPLATE,
    CODE_PROMPT_TEMPLATE,
    FIX_PROMPT_TEMPLATE,
    HypothesisProposalInput,
    PatchProposalInput,
    ToolSelectionInput,
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
        self._model = model or getattr(llm_client, "model", None) or "claude-opus-4-6"
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

    def plan_tool_call(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Ask the model to choose the next APS proposal tool.

        The model only returns a plan. APS validates the selected tool against
        its allowed list and executes through ProposalToolRegistry.
        """
        prompt = _build_tool_selection_prompt(context)
        raw = self._call_with_trace(
            request_kind="tool_selection",
            prompt=prompt,
            tool=TOOL_SELECTION_TOOL,
            system_blocks=[],
            context=context,
        )
        try:
            validated = ToolSelectionInput(**raw)
        except ValidationError as exc:
            raise ProposalValidationError(str(exc)) from exc
        if validated.intent in {"stop", "final"}:
            return {"stop": True, "intent": validated.intent}
        return {
            "tool_name": validated.tool_name,
            "args": dict(validated.args or {}),
            "intent": validated.intent,
        }

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
                prompt,
                tool,
                self._model,
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
            "tool_schema": tool.get("input_schema")
            or tool.get("function", {}).get("parameters"),
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
        payload.update(
            {
                "finished_at": datetime.now().isoformat(),
                "ok": ok,
            }
        )
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


def _build_tool_selection_prompt(context: Dict[str, Any]) -> str:
    safe_context = _sanitize_tool_selection_context(context)
    if bool(context.get("code_phase")):
        return (
            "You are selecting the next exposure-controlled code-phase inspection "
            "tool for Scion after a hypothesis has already been approved.\n"
            "Scion controls boundaries and executes tools; you only return one "
            "plan_proposal_tool_call input naming an allowed tool and JSON args. "
            "Use these tools to inspect memory, branch state, runtime/screening "
            "feedback, and the declared problem research object before writing "
            "the final patch. Do not include code_content, private rationale, "
            "raw metric references, validation/frozen details, or workspace "
            "writes in the tool plan. Stop when no more inspection is needed.\n\n"
            "## Tool Selection Context\n"
            f"{json.dumps(safe_context, indent=2, sort_keys=True, default=str)}"
        )
    return (
        "You are selecting the next read-only proposal-context tool for Scion.\n"
        "Scion is a framework: use only the provided context and tool specs, "
        "without assuming any particular problem domain.\n"
        "Return exactly one plan_proposal_tool_call tool input. The selected "
        "tool_name must be present in allowed_tools. Do not execute tools. "
        "For context.read_surface, choose surface only from the current "
        "context.list_surfaces observation values shown in tool_arg_guidance. "
        "Do not include rationale, memory, private metric references, private "
        "evaluation details, or workspace target file code.\n\n"
        "## Tool Selection Context\n"
        f"{json.dumps(safe_context, indent=2, sort_keys=True, default=str)}"
    )


def _sanitize_tool_selection_context(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if key_text in {
                "raw_metrics_ref",
                "case_ids",
                "seed_set",
                "pair_feedback",
                "code",
                "code_content",
                "current_artifact",
                "target_file_code",
            }:
                continue
            cleaned[key_text] = _sanitize_tool_selection_context(item)
        return cleaned
    if isinstance(value, (list, tuple)):
        return [_sanitize_tool_selection_context(item) for item in value]
    if isinstance(value, str):
        forbidden_terms = (
            "raw_metrics_ref",
            "raw metrics",
            "validation",
            "frozen",
            "holdout",
        )
        lines = [
            line
            for line in value.splitlines()
            if not any(term in line.lower() for term in forbidden_terms)
        ]
        return "\n".join(lines)
    return value


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
        target_runtime_effect=validated.target_runtime_effect,
        complexity_claim=validated.complexity_claim,
        runtime_budget_strategy=validated.runtime_budget_strategy,
        novelty_signature=dict(validated.novelty_signature or {}),
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
_AGENTIC_RESEARCH_DIAGNOSIS_CHARS = 12000
_AGENTIC_TOOL_OBSERVATIONS_CHARS = 24000
_AGENTIC_CODE_RESEARCH_DIAGNOSIS_CHARS = 6000
_AGENTIC_CODE_TOOL_OBSERVATIONS_CHARS = 6000
_SOLVER_DESIGN_CODE_PROBLEM_OBJECT_CHARS = 1800
_SOLVER_DESIGN_CODE_SOLVER_MECHANICS_CHARS = 1800
_SOLVER_DESIGN_CODE_INTERFACE_CHARS = 2400
_SOLVER_DESIGN_CODE_HYPOTHESIS_CHARS = 3000
_SOLVER_DESIGN_COMPACT_RETRY_PROBLEM_OBJECT_CHARS = 1200
_SOLVER_DESIGN_COMPACT_RETRY_SOLVER_MECHANICS_CHARS = 1200
_SOLVER_DESIGN_COMPACT_RETRY_INTERFACE_CHARS = 1600
_SOLVER_DESIGN_COMPACT_RETRY_HYPOTHESIS_CHARS = 1600
_SOLVER_DESIGN_BROAD_SCOPE_TERMS = (
    "hybrid",
    "alns",
    "vns",
    "lns",
    "destroy",
    "repair",
    "recombination",
    "route-pool",
    "route pool",
    "population",
    "portfolio",
    "ensemble",
    "multi-operator",
    "multi operator",
    "restart",
    "perturb",
)


def _split_hypothesis_context(
    context: Dict[str, Any],
) -> "tuple[list[dict], str]":
    """Split hypothesis context into system blocks (cacheable) and user prompt.

    System: Block 1 (static, high cache hit) + Block 2 (champion, changes on promote)
    User (dynamic): experiment history + blacklist + siblings + analysis steps + task
    """
    D = _DefaultDict(context)
    solver_mechanics = str(D["solver_mechanics"]).strip()
    problem_object = str(D["problem_object"]).strip()
    problem_object_text = (
        f"## Problem Object\n{problem_object}\n\n" if problem_object else ""
    )
    if solver_mechanics:
        solver_mechanics_text = (
            f"## Solver Execution Model\n{solver_mechanics}\n\n"
            f"Design implications for new research-surface changes:\n"
            f"- Follow the problem-specific execution model above; do not assume a fixed invocation count.\n"
            f"- Operator surfaces MUST preserve feasibility and the adapter-defined solution contract.\n"
            f"- State the capability gap it fills, the objective it targets, and the no-op condition that protects other objectives.\n"
            f"- Runtime is part of the evidence: describe explicit bounds, filters, sampling, or early exits."
        )
    else:
        solver_mechanics_text = (
            "## Solver Execution Model\n"
            "The exact operator execution model is problem-specific. Use the problem summary, "
            "operator interface, current champion code, and runtime feedback as the source of truth.\n\n"
            "Design implications for new research-surface changes:\n"
            "- Do not assume a fixed invocation count, pool size, neighborhood structure, or acceptance rule.\n"
            "- Operator surfaces MUST preserve feasibility and the problem-specific solution contract.\n"
            "- State the capability gap it fills, the objective it targets, and the no-op condition that protects other objectives.\n"
            "- Runtime is part of the evidence: describe explicit bounds, filters, sampling, or early exits."
        )

    # Block 1: Static role + problem spec + solver mechanics (never changes)
    static_text = (
        "You are a research agent optimising declared research surfaces of a combinatorial optimisation solver.\n"
        "Your goal is to propose ONE novel hypothesis that, if implemented, would improve solver quality.\n\n"
        f"## Problem Summary\n{D['problem_summary']}\n\n"
        f"{problem_object_text}"
        f"{D['research_surfaces']}\n\n"
        f"{D['objective_policy_guidance']}\n\n"
        f"{solver_mechanics_text}"
    )

    # Block 2: Champion code + stats (changes only on champion promotion)
    champion_text = (
        f"## Current Champion Research Code\n"
        f"Study these carefully before proposing anything \u2014 avoid duplicating existing logic or policy choices.\n\n"
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
        branch_context_parts.append(f"## Branch Direction\n{D['branch_direction']}")
    if D["exploration_coverage"]:
        branch_context_parts.append(
            f"## Exploration Coverage\n{D['exploration_coverage']}"
        )
    if D["strategy_guidance"]:
        branch_context_parts.append(f"## Strategy Guidance\n{D['strategy_guidance']}")
    if D["solver_design_boundary_guidance"]:
        branch_context_parts.append(D["solver_design_boundary_guidance"])
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
    if D["runtime_feedback"]:
        branch_context_parts.append(f"## Runtime Feedback\n{D['runtime_feedback']}")
    if D["runtime_failure_guidance"]:
        branch_context_parts.append(
            f"## Runtime Failure Guidance\n{D['runtime_failure_guidance']}"
        )
    agentic_context = _agentic_research_context_block(D)
    if agentic_context:
        branch_context_parts.append(agentic_context)

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
        system_blocks.append(
            {
                "type": "text",
                "text": "\n\n".join(branch_context_parts),
            }
        )

    user_prompt = (
        f"## Experiment History \u2014 This Branch\n{D['experiment_history']}\n\n"
        f"## Globally Failed / Blacklisted Approaches\n{D['blacklist_summary']}\n\n"
        f"## Currently Occupied (C10 will auto-reject duplicates)\n{D['active_hyp_summary']}\n\n"
        f"## Sibling Branches\n{D['sibling_summary']}\n\n"
        f"## Analysis Steps (follow in order)\n"
        f"1. Read every relevant champion research-surface file. For operator files, note: what move type, what objective(s) it improves or protects, what it cannot improve. For policy/config files, note the declared bounded lever being changed.\n"
        f"2. Identify specific GAPS \u2014 what improvements are IMPOSSIBLE with the current pool?\n"
        f"3. Check experiment history \u2014 which attempts at filling gaps failed, and WHY?\n"
        f"4. Only then propose a hypothesis targeting an identified gap.\n"
        f"5. In the hypothesis text, state target objective(s), protected objective(s), "
        f"and the no-op condition that avoids harming protected objectives.\n"
        f"6. Fill the runtime intent fields: `target_runtime_effect`, `complexity_claim`, "
        f"and `runtime_budget_strategy`.\n\n"
        f"Runtime constraint: proposed research-surface changes are evaluated inside the problem solver and "
        f"algorithmic efficiency is part of the evidence. Do not propose unbounded high-order "
        f"enumeration over problem entities; describe any top-k, "
        f"sampling, or early-stop cap needed to keep runtime comparable to the champion.\n\n"
        f"If your hypothesis duplicates an existing surface's capability (even partially), it will be REJECTED.\n\n"
        f"{_hypothesis_task_prompt(D)}"
    )

    return system_blocks, user_prompt


def _hypothesis_task_prompt(context: Mapping[str, Any]) -> str:
    forced_surface = str(context.get("forced_surface") or "").strip()
    forced_action = str(context.get("forced_action") or "").strip()
    forced_target_file = str(context.get("forced_target_file") or "").strip()
    constraints = context.get("agentic_hypothesis_constraints")
    novelty_requirements: Mapping[str, Any] = {}
    active_boundary = str(context.get("active_problem_boundary_surfaces") or "").strip()
    if isinstance(constraints, Mapping):
        forced_surface = (
            forced_surface or str(constraints.get("forced_surface") or "").strip()
        )
        forced_action = (
            forced_action or str(constraints.get("forced_action") or "").strip()
        )
        forced_target_file = (
            forced_target_file
            or str(constraints.get("forced_target_file") or "").strip()
        )
        boundary_value = constraints.get("active_problem_boundary_surfaces")
        if not active_boundary and isinstance(boundary_value, (list, tuple)):
            active_boundary = ", ".join(
                str(item).strip() for item in boundary_value if str(item).strip()
            )
        elif not active_boundary:
            active_boundary = str(boundary_value or "").strip()
        raw_novelty_requirements = constraints.get("novelty_signature_requirements")
        if isinstance(raw_novelty_requirements, Mapping):
            novelty_requirements = raw_novelty_requirements
    if forced_surface:
        lines = [
            "## Task",
            (
                "Propose ONE new hypothesis for improving the solver within "
                "the active forced research-surface constraint."
            ),
            f"Set `change_locus` exactly to `{forced_surface}`.",
            (
                "Do not choose any other research surface, even if prior "
                "attempts on the forced surface failed or were blacklisted; "
                "vary the in-surface mechanism instead."
            ),
        ]
        if forced_action:
            lines.append(f"Set `action` exactly to `{forced_action}`.")
        else:
            lines.append("Set `action` to one legal action for the forced surface.")
        if forced_target_file:
            lines.append(f"Set `target_file` exactly to `{forced_target_file}`.")
        else:
            lines.append(
                'If the forced action is "modify" or "remove", provide a '
                "target_file declared by the forced surface."
            )
        lines.extend(_novelty_signature_task_lines(novelty_requirements))
        return "\n".join(lines) + "\n"
    if active_boundary:
        targetable_files = str(context.get("targetable_files") or "")
        lines = [
            "## Task",
            (
                "Propose ONE new hypothesis for improving the solver within "
                "the active problem-object research boundary."
            ),
            f"Set `change_locus` to one of: {active_boundary}.",
            (
                "Do not choose a component policy as `change_locus`; component "
                "policies may be referenced only as implementation hooks or "
                "attribution evidence inside the problem-level solver design."
            ),
            "Set `action` to one legal action for the active boundary.",
        ]
        if targetable_files:
            lines.append(
                'If action is "modify" or "remove", provide `target_file` '
                f"from the active boundary files: {targetable_files}."
            )
        lines.extend(_novelty_signature_task_lines(novelty_requirements))
        return "\n".join(lines) + "\n"
    operator_categories = str(context.get("operator_categories") or "")
    available_actions = str(
        context.get("available_actions") or "create_new, modify, remove"
    )
    targetable_files = str(context.get("targetable_files") or "")
    return (
        "## Task\n"
        "Propose ONE new hypothesis for improving the solver.\n"
        f"Choose a research surface from {operator_categories} as `change_locus`.\n"
        f"Set `action` to one of: {available_actions}.\n"
        'If action is "modify" or "remove", provide `target_file` from '
        f"the targetable files when available: {targetable_files}.\n"
    )


def _novelty_signature_task_lines(
    requirements: Mapping[str, Any],
) -> list[str]:
    if not isinstance(requirements, Mapping) or not requirements:
        return []
    lines: list[str] = []
    for surface_name, requirement in sorted(requirements.items()):
        if not isinstance(requirement, Mapping):
            continue
        fields = requirement.get("required_fields")
        if not isinstance(fields, (list, tuple)) or not fields:
            continue
        field_text = ", ".join(str(field) for field in fields if str(field).strip())
        if not field_text:
            continue
        lines.append(
            f"For `{surface_name}`, populate `novelty_signature` with every "
            f"declared semantic field: {field_text}. Keep scalar string values "
            "at or below 120 characters."
        )
        sequence_fields = requirement.get("nonempty_sequence_fields")
        if isinstance(sequence_fields, (list, tuple)) and sequence_fields:
            seq_text = ", ".join(
                str(field) for field in sequence_fields if str(field).strip()
            )
            if seq_text:
                lines.append(
                    f"For `{surface_name}`, `{seq_text}` must be non-empty "
                    "JSON arrays of component names; do not use null, false, "
                    "empty strings, or empty arrays."
                )
    return lines


def _split_code_context(
    context: Dict[str, Any],
) -> "tuple[list[dict], str]":
    """Split code context into system blocks (cacheable) and user prompt.

    System: Block 1 (static role + rules + interface) + Block 2 (champion code)
    User (dynamic): hypothesis + target file + constraints
    """
    D = _DefaultDict(context)
    solver_mechanics = str(D["solver_mechanics"]).strip()
    problem_object = str(D["problem_object"]).strip()
    surface_name = str(D["research_surface_name"] or D["change_locus"]).strip()
    surface_kind = str(D["research_surface_kind"] or "operator").strip()
    is_solver_design_surface = surface_kind in {
        "solver_design",
        "solver_algorithm",
    } or surface_name in {"solver_design", "solver_algorithm"}
    compact_timeout_retry = (
        str(D["code_generation_mode"]).strip() == "compact_timeout_retry"
    )
    if is_solver_design_surface:
        problem_object = _limit_code_phase_text(
            problem_object,
            (
                _SOLVER_DESIGN_COMPACT_RETRY_PROBLEM_OBJECT_CHARS
                if compact_timeout_retry
                else _SOLVER_DESIGN_CODE_PROBLEM_OBJECT_CHARS
            ),
            label="problem object",
        )
        solver_mechanics = _limit_code_phase_text(
            solver_mechanics,
            (
                _SOLVER_DESIGN_COMPACT_RETRY_SOLVER_MECHANICS_CHARS
                if compact_timeout_retry
                else _SOLVER_DESIGN_CODE_SOLVER_MECHANICS_CHARS
            ),
            label="solver execution model",
        )
        interface_spec = _limit_code_phase_text(
            str(D["operator_interface_spec"]),
            (
                _SOLVER_DESIGN_COMPACT_RETRY_INTERFACE_CHARS
                if compact_timeout_retry
                else _SOLVER_DESIGN_CODE_INTERFACE_CHARS
            ),
            label="surface interface",
        )
    else:
        interface_spec = str(D["operator_interface_spec"])
    problem_object_section = (
        f"## Problem Object\n{problem_object}\n\n" if problem_object else ""
    )
    solver_mechanics_section = (
        f"## Solver Execution Model\n{solver_mechanics}\n\n" if solver_mechanics else ""
    )

    surface_label = (
        f"{surface_name} [{surface_kind}]" if surface_name else f"[{surface_kind}]"
    )
    solver_design_code_rules = (
        "\n## Full Solver-Algorithm Rules\n"
        "- Implement a complete `solve(instance, rng, time_limit_sec, context)` "
        "algorithm body. Do not return a lifecycle/config dictionary.\n"
        "- Default to a compact replacement file: one coherent construction or "
        "seeding path, one bounded improvement/search loop, no more than two "
        "move families, and only the helper functions needed for that path.\n"
        "- Do not preserve the inactive template merely to edit a few constants, "
        "and do not grow a helper forest for ALNS/VNS, route-pool, destroy/repair, "
        "and perturbation all at once. Select one vertical algorithm slice that "
        "can run and screen now; later rounds can add breadth after it proves "
        "movement.\n"
        "- The preferred target is `policies/baseline_algorithm.py`: change "
        "the controlled algorithm body directly and do not call "
        "`context.baseline` there. The older `policies/solver_algorithm.py` "
        "compatibility hook may use `context.baseline` only when paired with "
        "a bounded algorithmic search loop and telemetry via "
        "`context.record_move` or `context.record_iteration`.\n"
        "- Do not submit a shallow wrapper that changes baseline budget/params "
        "or adds a tiny post-baseline polish.\n"
        "- You may change algorithm strategy and runtime scheduling, but not "
        "problem objective semantics, feasibility constraints, parsing, seeds, "
        "protocol splits, Decision rules, or adapter/runtime files.\n"
        if is_solver_design_surface
        else ""
    )
    solver_design_scope_control = _solver_design_scope_control_section(
        D,
        is_solver_design_surface=is_solver_design_surface,
    )
    solver_design_user_constraints = (
        "- For solver-design surfaces, return a compact complete replacement "
        "file. The file may be much shorter than the current inactive template "
        "if it still implements the approved `solve(...)` interface and "
        "records runtime/search telemetry.\n"
        if is_solver_design_surface
        else ""
    )

    # Block 1: Static role + quality rules + problem + interface (never changes)
    static_text = (
        "You are a software engineer implementing a declared research surface for a combinatorial optimisation solver framework.\n"
        "Your task is to write the complete file contents that implement the approved hypothesis below.\n\n"
        "## Code Quality Rules\n"
        "- Write ONLY what the hypothesis requires. For non-solver surfaces, do not add extra helper functions or abstractions.\n"
        "- Do not add error handling for impossible cases. Trust the data model.\n"
        "- Do not add comments explaining WHAT the code does \u2014 only WHY for non-obvious choices.\n"
        "- Prefer simple, direct code over clever abstractions.\n"
        "- Match the coding style of the existing champion research-surface files.\n"
        "- Do NOT add logging, print statements, or debug output.\n"
        f"{solver_design_code_rules}"
        f"{solver_design_scope_control}\n"
        "## Feasibility is Non-Negotiable\n"
        "An operator surface that produces infeasible solutions is worse than no change. "
        "Follow the problem-specific feasibility and consistency rules in the interface specification exactly.\n\n"
        f"## Problem Summary\n{D['problem_summary']}\n\n"
        f"{problem_object_section}"
        f"{solver_mechanics_section}"
        f"## Research Surface Interface Specification\n"
        f"Active surface: {surface_label}\n"
        f"Follow this interface exactly:\n\n"
        f"{interface_spec}\n\n"
        f"## Allowed Imports\n"
        f"Only use modules from this whitelist \u2014 any other import will be rejected:\n"
        f"{D['import_whitelist']}"
    )

    # Block 2: Champion code (changes only on champion promotion).  Whole-solver
    # candidates already receive the full selected target file below; repeating
    # every component policy here makes final code-generation calls too large
    # without improving the boundary.
    if is_solver_design_surface:
        champion_text = (
            "## Current Champion Research Code\n"
            "The approved solver-design target file is provided in full in the "
            "`Target File` section below. Legacy component policies may be "
            "implementation context, but they are not the research object for "
            "this patch; follow the problem object, interface specification, "
            "and target file instead of copying lifecycle/config tables."
        )
    else:
        champion_text = (
            f"## Current Champion Research Code\n"
            f"Study these files for coding style, data model usage, and patterns:\n\n"
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
        prior_failure = str(D["prior_code_failure"])
        if _is_timeout_failure(prior_failure):
            prior_failure_section = (
                "## Previous Attempt Failed\n"
                "The previous code generation attempt timed out before "
                "returning a patch. Keep the implementation compact and "
                "bounded. Implement one coherent solver body with at most "
                "a small set of helpers, prefer one construction path plus "
                "one bounded improvement loop, and avoid large ALNS helper "
                "forests unless absolutely necessary.\n\n"
            )
        else:
            prior_failure_section = (
                f"## Previous Attempt Failed\n"
                f"The previous code generation failed with:\n"
                f"{prior_failure}\n"
                f"Avoid the same mistake.\n\n"
            )
    agentic_context = _agentic_research_context_block(D, code_phase=True)
    if agentic_context:
        prior_failure_section += f"{agentic_context}\n\n"

    user_prompt = (
        f"{prior_failure_section}"
        f"## Hypothesis to Implement\n{_code_hypothesis_detail(D, is_solver_design_surface)}\n\n"
        f"## Target File (current content)\n{D['target_file_code']}\n\n"
        f"## Reference Surface Files\n{D['reference_operators']}\n\n"
        f"## Constraints\n"
        f"- Editable files: {D['editable_patterns']}\n"
        f"- Frozen (DO NOT MODIFY): {D['frozen_patterns']}\n"
        f"- Conform to the active research-surface interface specification exactly\n"
        f"- Preserve all feasibility, consistency, and determinism invariants described there\n"
        f"- For operator surfaces, use the provided `rng` argument for all randomness and return the new solution/artifact, or the original if no valid move is found\n"
        f"- For policy surfaces, implement the required module-level functions and keep return values inside the documented bounds\n\n"
        f"{solver_design_user_constraints}\n"
        f"Respond with a single JSON object (no markdown fences, no extra text):\n"
        f"{{\n"
        f'  "file_path": "<relative path, e.g. operators/my_operator.py>",\n'
        f'  "action": "modify" | "create" | "delete",\n'
        f'  "code_content": "<complete file contents>",\n'
        f'  "test_hint": "<optional note, or null>"\n'
        f"}}\n"
    )

    return system_blocks, user_prompt


def _agentic_research_context_block(
    context: Dict[str, Any],
    *,
    code_phase: bool = False,
) -> str:
    parts: list[str] = []
    diagnosis = context.get("agentic_research_diagnosis")
    if diagnosis:
        heading = (
            "## Evidence Diagnosis Behind This Hypothesis"
            if code_phase
            else "## Agentic Research Diagnosis"
        )
        parts.append(
            f"{heading}\n"
            "Screening/runtime observations below are tainted proposal context, "
            "not Decision input. Use them to explain which declared surface "
            "evidence should change and why the next mechanism differs from "
            "prior failed attempts.\n\n"
            f"{_bounded_json(diagnosis, _agentic_research_diagnosis_chars(code_phase))}"
        )
    observations = context.get("agentic_tool_observations")
    if observations:
        parts.append(
            "## Agentic Proposal Tool Observations\n"
            "These are exposure-controlled tool observations gathered before "
            "generation. Use screening/runtime feedback and selected-surface "
            "metadata when forming the hypothesis or implementing the approved "
            "change; do not treat raw refs or holdout detail as available.\n\n"
            f"{_bounded_json(observations, _agentic_observation_chars(code_phase))}"
        )
    return "\n\n".join(parts)


def _code_hypothesis_detail(
    context: Mapping[str, Any],
    is_solver_design_surface: bool,
) -> str:
    detail = str(context.get("hypothesis_detail") or "")
    if not is_solver_design_surface:
        return detail
    if (
        str(context.get("code_generation_mode") or "").strip()
        == "compact_timeout_retry"
    ):
        return _limit_code_phase_text(
            detail,
            _SOLVER_DESIGN_COMPACT_RETRY_HYPOTHESIS_CHARS,
            label="hypothesis detail",
        )
    return _limit_code_phase_text(
        detail,
        _SOLVER_DESIGN_CODE_HYPOTHESIS_CHARS,
        label="hypothesis detail",
    )


def _solver_design_scope_control_section(
    context: Mapping[str, Any],
    *,
    is_solver_design_surface: bool,
) -> str:
    if not is_solver_design_surface:
        return ""
    scope = context.get("agentic_code_scope_control")
    if not isinstance(scope, Mapping):
        scope = {}
    mode = str(context.get("code_generation_mode") or scope.get("mode") or "").strip()
    broad_terms = _solver_design_broad_terms(context)
    if not broad_terms and isinstance(scope.get("detected_broad_terms"), list):
        broad_terms = [
            str(term)
            for term in scope.get("detected_broad_terms", ())
            if str(term).strip()
        ]

    lines = [
        "",
        "## Compact Solver-Design Implementation Scope",
        "- Scion controls the research boundary; the code agent should still write a real algorithm, but this patch must be small enough to generate, review, preview, and screen.",
        "- Implement one primary mechanism now. Prefer a direct seed/construction plus one bounded relocate/swap/2-opt-style improvement loop over a broad hybrid portfolio.",
        "- Hard size target: keep the replacement file around 180 lines or less and around six helper functions or fewer unless correctness clearly requires slightly more.",
        "- Do not implement more than two move/neighborhood families in one patch; choose the smallest complete algorithm slice that can change screening evidence.",
        "- Every search loop must have an explicit iteration/customer/route cap and should check `context.remaining_time()` or `time_limit_sec` through the provided context.",
        "- Record movement evidence with `context.record_iteration`, `context.record_move`, phase timing, and `context.set_stop_reason` where the interface supports it.",
    ]
    if mode:
        lines.append(f"- Current code-generation mode: `{mode}`.")
    if broad_terms:
        lines.append(
            "- The approved hypothesis mentions broad mechanisms "
            f"({', '.join(dict.fromkeys(broad_terms))}). Reduce them to one "
            "executable path for this patch; do not implement a full portfolio."
        )
    if scope.get("failure_detail"):
        lines.append(
            "- Previous code generation timed out. Treat that as an instruction "
            "to shrink implementation breadth before adding algorithmic detail."
        )
    return "\n".join(lines) + "\n"


def _solver_design_broad_terms(context: Mapping[str, Any]) -> list[str]:
    text = "\n".join(
        str(context.get(key) or "")
        for key in (
            "hypothesis_detail",
            "prior_code_failure",
            "target_runtime_effect",
            "complexity_claim",
            "runtime_budget_strategy",
        )
    ).lower()
    return [term for term in _SOLVER_DESIGN_BROAD_SCOPE_TERMS if term in text]


def _limit_code_phase_text(text: str, max_chars: int, *, label: str) -> str:
    if not text or len(text) <= max_chars:
        return text
    suffix = f"\n... <truncated {label} for compact code generation>"
    return text[: max(0, max_chars - len(suffix))] + suffix


def _agentic_research_diagnosis_chars(code_phase: bool) -> int:
    return (
        _AGENTIC_CODE_RESEARCH_DIAGNOSIS_CHARS
        if code_phase
        else _AGENTIC_RESEARCH_DIAGNOSIS_CHARS
    )


def _agentic_observation_chars(code_phase: bool) -> int:
    return (
        _AGENTIC_CODE_TOOL_OBSERVATIONS_CHARS
        if code_phase
        else _AGENTIC_TOOL_OBSERVATIONS_CHARS
    )


def _is_timeout_failure(text: str) -> bool:
    lowered = text.lower()
    return "timed out" in lowered or "timeout" in lowered


def _bounded_json(value: Any, max_chars: int) -> str:
    try:
        rendered = json.dumps(value, indent=2, sort_keys=True, default=str)
    except TypeError:
        rendered = str(value)
    if len(rendered) <= max_chars:
        return rendered
    return rendered[: max(0, max_chars - 80)] + "\n... <truncated agentic context>"


def _split_fix_context(
    context: Dict[str, Any],
) -> "tuple[list[dict], str]":
    """Split fix context into system blocks (cacheable) and user prompt.

    System (1h cache): role + problem + operator interface + import whitelist
    User (dynamic): original code + failure details + task
    """
    D = _DefaultDict(context)
    solver_mechanics = str(D["solver_mechanics"]).strip()
    problem_object = str(D["problem_object"]).strip()
    problem_object_section = (
        f"## Problem Object\n{problem_object}\n\n" if problem_object else ""
    )
    solver_mechanics_section = (
        f"## Solver Execution Model\n{solver_mechanics}\n\n" if solver_mechanics else ""
    )

    system_text = (
        "You are a software engineer fixing an optimisation research-surface file that failed verification.\n"
        "Correct the code so it passes, while preserving the intended logic.\n\n"
        f"## Problem Summary\n{D['problem_summary']}\n\n"
        f"{problem_object_section}"
        f"{solver_mechanics_section}"
        f"## Research Surface Interface Specification\n"
        f"Follow this interface exactly:\n\n"
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
        f"- Preserve the research-surface interface described above exactly\n"
        f"- Make only the minimal changes needed to fix the reported failure\n"
    )

    return system_blocks, user_prompt
