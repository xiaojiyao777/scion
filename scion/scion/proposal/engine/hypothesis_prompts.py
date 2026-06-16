"""Hypothesis prompt rendering for the proposal engine."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Mapping

from .prompt_common import (
    _CACHE_5M,
    _DefaultDict,
    _agentic_research_context_block,
)
from .solver_design_prompts import _solver_design_hypothesis_guidance

_PROMPT_SAME_MECHANISM_ALLOWED_ACTIONS = (
    "tune",
    "integrate",
    "repair",
    "parameterize",
    "telemetry_wiring",
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
        f"## Problem Object (Adapter-Rendered Problem Semantics)\n"
        f"{problem_object}\n\n"
        if problem_object
        else ""
    )
    if solver_mechanics:
        solver_mechanics_text = (
            f"## Solver Execution Model (Adapter-Rendered Problem Semantics)\n"
            f"{solver_mechanics}\n\n"
            f"Design implications for new research-surface changes:\n"
            f"- Follow the problem-specific execution model above; do not assume a fixed invocation count.\n"
            f"- Operator surfaces MUST preserve feasibility and the adapter-defined solution contract.\n"
            f"- State the capability gap it fills, the objective it targets, and the no-op condition that protects other objectives.\n"
            f"- Runtime is part of the evidence: describe explicit bounds, filters, sampling, or early exits."
        )
    else:
        solver_mechanics_text = (
            "## Solver Execution Model (Adapter-Rendered Problem Semantics)\n"
            "The exact operator execution model is problem-specific. Use the problem summary, "
            "operator interface, current champion code, and runtime feedback as the source of truth.\n\n"
            "Design implications for new research-surface changes:\n"
            "- Do not assume a fixed invocation count, pool size, neighborhood structure, or selection rule.\n"
            "- Operator surfaces MUST preserve feasibility and the problem-specific solution contract.\n"
            "- State the capability gap it fills, the objective it targets, and the no-op condition that protects other objectives.\n"
            "- Runtime is part of the evidence: describe explicit bounds, filters, sampling, or early exits."
        )

    static_text = (
        "You are a research agent optimising declared research surfaces of a combinatorial optimisation solver.\n"
        "Your goal is to propose ONE novel hypothesis that, if implemented, would improve solver quality.\n\n"
        f"## Problem Summary\n{D['problem_summary']}\n\n"
        f"{problem_object_text}"
        f"{D['research_surfaces']}\n\n"
        f"{D['objective_policy_guidance']}\n\n"
        f"{solver_mechanics_text}"
    )

    champion_text = (
        f"## Current Champion Research Code\n"
        f"Study these carefully before proposing anything — avoid duplicating existing logic or policy choices.\n\n"
        f"{D['champion_operators_code']}\n\n"
        f"## Champion State\n{D['champion_stats']}"
    )

    branch_context_parts = []
    compact_research_signals = _compact_research_signals(context, D)
    if compact_research_signals:
        branch_context_parts.append(compact_research_signals)

    same_mechanism_constraints = _same_mechanism_followup_constraints(D)
    if same_mechanism_constraints:
        branch_context_parts.append(same_mechanism_constraints)

    if D["search_memory"]:
        branch_context_parts.append(D["search_memory"])

    if D["saturation_signal"]:
        branch_context_parts.append(D["saturation_signal"])

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
    if D["branch_dossier"]:
        branch_context_parts.append(f"## Branch Dossier\n{D['branch_dossier']}")
    branch_lesson_context = _branch_lesson_usage_context_block(context)
    if branch_lesson_context:
        branch_context_parts.append(branch_lesson_context)
    if D["cross_branch_research"]:
        branch_context_parts.append(
            f"## Cross-Branch Research Map\n{D['cross_branch_research']}"
        )
    if D["branch_followup_policy"]:
        branch_context_parts.append(
            f"## Branch Follow-up Policy\n{D['branch_followup_policy']}"
        )
    if D["branch_hygiene_guidance"]:
        branch_context_parts.append(
            f"## Branch Code Status\n{D['branch_hygiene_guidance']}"
        )
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
    if D["failure_pattern_warning"]:
        branch_context_parts.append(
            f"## Failure Pattern Warning\n{D['failure_pattern_warning']}"
        )
    if D["locus_constraint"]:
        branch_context_parts.append(D["locus_constraint"])
    if D.get("objective_guidance"):
        branch_context_parts.append(D["objective_guidance"])
    if D.get("problem_measurement_diagnostics"):
        branch_context_parts.append(
            "## Problem Measurement Diagnostics\n"
            f"{D['problem_measurement_diagnostics']}"
        )
    if D.get("objective_opportunity_profile"):
        branch_context_parts.append(D["objective_opportunity_profile"])
    if D["weight_opt_feedback"]:
        branch_context_parts.append(D["weight_opt_feedback"])
    if D["runtime_feedback"]:
        branch_context_parts.append(f"## Runtime Feedback\n{D['runtime_feedback']}")
    if D["runtime_failure_guidance"]:
        branch_context_parts.append(
            f"## Runtime Failure Guidance\n{D['runtime_failure_guidance']}"
        )
    if D["agent_quality_feedback"]:
        branch_context_parts.append(
            f"## Agent Quality Feedback\n{D['agent_quality_feedback']}"
        )
    agentic_context = _agentic_research_context_block(D)
    cacheable_agentic_context = ""
    dynamic_agentic_context = ""
    if agentic_context:
        cacheable_agentic_context, dynamic_agentic_context = (
            _split_agentic_context_for_hypothesis_cache(agentic_context)
        )
    negative_fact_block = str(D["agentic_negative_fact_block"]).strip()

    stable_prefix_parts = [static_text, champion_text]
    if cacheable_agentic_context:
        stable_prefix_parts.append(cacheable_agentic_context)
    system_blocks = [
        {
            "type": "text",
            "text": "\n\n".join(
                part for part in stable_prefix_parts if str(part).strip()
            ),
            "cache_control": _CACHE_5M,
        }
    ]
    if branch_context_parts:
        system_blocks.append(
            {
                "type": "text",
                "text": "\n\n".join(branch_context_parts),
            }
        )

    dynamic_agentic_prefix = (
        f"{dynamic_agentic_context}\n\n" if dynamic_agentic_context else ""
    )
    experiment_history = str(D["experiment_history"]).strip()
    experiment_history_section = (
        f"## Experiment History — This Branch\n{experiment_history}\n\n"
        if experiment_history
        else ""
    )
    user_prompt = (
        f"{dynamic_agentic_prefix}"
        f"{experiment_history_section}"
        f"## Globally Failed / Blacklisted Approaches\n{D['blacklist_summary']}\n\n"
        f"## Currently Occupied (C10 reports duplicate-risk diagnostics)\n{D['active_hyp_summary']}\n\n"
        f"## Sibling Branches\n{D['sibling_summary']}\n\n"
        f"## Analysis Steps (follow in order)\n"
        f"1. Read every relevant champion research-surface file and active solver fact available in context. For operator files, note: what move type, what objective(s) it improves or protects, what it cannot improve. For policy/config files, note the declared bounded lever being changed.\n"
        f"2. Identify the active bottleneck from screening/runtime feedback, objective opportunity profile, and experiment history. Distinguish the primary decision reason from auxiliary telemetry or runtime warnings.\n"
        f"3. Identify specific GAPS — what improvements are IMPOSSIBLE with the current pool or active solver design?\n"
        f"4. Check experiment history — which attempts at filling gaps failed, and WHY? Do not target a stable/protected objective or recent no-effect mechanism unless you have new evidence or a materially different mechanism.\n"
        f"5. Only then propose a hypothesis targeting an identified gap and active bottleneck.\n"
        f"6. In the hypothesis text, state: active bottleneck; objectives to preserve; novelty evidence; why the mechanism can affect the bottleneck; no-op/failure conditions.\n"
        f"7. Fill `target_runtime_effect`, `complexity_claim`, and `runtime_budget_strategy`.\n\n"
        f"## Compact Safety and Output Invariants\n"
        f"Telemetry contract: `expected_telemetry` keys must be only `activity`, "
        f"`activation`, `effect`, or `budget`; values must be exact field paths "
        f"or arrays of paths, not prose. Activation is mechanism-specific "
        f"activity evidence, not objective outcome, aggregate phase, family, or "
        f"runtime bucket labels. Reuse the declared mechanism id in every "
        f"expected telemetry path.\n"
        f"Objective field contract: `target_objectives` and "
        f"`protected_objectives` must contain only declared problem objective ids; "
        f"put constraints, feasibility, parser validity, and solution consistency "
        f"in `risk_to_higher_priority` or `no_op_condition`.\n"
        f"Runtime constraint: keep proposed solver changes bounded and comparable "
        f"to the champion with explicit top-k, sampling, filter, or early-stop "
        f"caps when needed.\n"
        f"If your hypothesis duplicates an existing surface's capability (even partially), it will be REJECTED.\n\n"
        f"{negative_fact_block + chr(10) + chr(10) if negative_fact_block else ''}"
        f"{_hypothesis_task_prompt(D)}"
    )

    return system_blocks, user_prompt


def _split_hypothesis_target_intent_context(
    context: Dict[str, Any],
) -> "tuple[list[dict], str]":
    """Render the tainted preflight prompt used to select a target intent."""
    D = _DefaultDict(context)
    solver_mechanics = str(D["solver_mechanics"]).strip()
    problem_object = str(D["problem_object"]).strip()
    problem_object_text = (
        f"## Problem Object (Adapter-Rendered Problem Semantics)\n"
        f"{problem_object}\n\n"
        if problem_object
        else ""
    )
    static_text = (
        "You are a target-intent preflight worker for a governed research "
        "proposal protocol.\n"
        "Select only the likely target intent for the next hypothesis. Do not "
        "write the formal hypothesis, telemetry contract, patch plan, or code.\n"
        "Your output is tainted proposal context used only so the host can "
        "deterministically expose the selected target source or a new-file "
        "placeholder before the final hypothesis call.\n\n"
        f"## Problem Summary\n{D['problem_summary']}\n\n"
        f"{problem_object_text}"
        f"{D['research_surfaces']}\n\n"
        f"{D['objective_policy_guidance']}\n\n"
        f"## Solver Execution Model (Adapter-Rendered Problem Semantics)\n"
        f"{solver_mechanics if solver_mechanics else 'Use the declared problem and surface context as the source of truth.'}"
    )
    champion_text = (
        "## Current Champion Research Code\n"
        "Use this only to identify the likely owner target; do not draft the "
        "final proposal here.\n\n"
        f"{D['champion_operators_code']}\n\n"
        f"## Champion State\n{D['champion_stats']}"
    )
    branch_context_parts = []
    same_mechanism_constraints = _same_mechanism_followup_constraints(D)
    if same_mechanism_constraints:
        branch_context_parts.append(same_mechanism_constraints)
    for key, title in (
        ("branch_hygiene_guidance", "Branch Same-Mechanism / Clean-Fork Guidance"),
        ("branch_followup_policy", "Branch Follow-up Policy"),
        ("branch_dossier", "Branch Dossier"),
        ("cross_branch_research", "Cross-Branch Research Map"),
        ("experiment_history", "Experiment History"),
        ("blacklist_summary", "Globally Failed / Blacklisted Approaches"),
        ("active_hyp_summary", "Currently Occupied"),
        ("sibling_summary", "Sibling Branches"),
    ):
        value = str(D[key]).strip()
        if value:
            branch_context_parts.append(f"## {title}\n{value}")
    agentic_context = _agentic_research_context_block(D)
    cacheable_agentic_context = ""
    dynamic_agentic_context = ""
    if agentic_context:
        cacheable_agentic_context, dynamic_agentic_context = (
            _split_agentic_context_for_hypothesis_cache(agentic_context)
        )
    stable_prefix_parts = [static_text, champion_text]
    if cacheable_agentic_context:
        stable_prefix_parts.append(cacheable_agentic_context)
    system_blocks = [
        {
            "type": "text",
            "text": "\n\n".join(
                part for part in stable_prefix_parts if str(part).strip()
            ),
            "cache_control": _CACHE_5M,
        }
    ]
    if branch_context_parts:
        system_blocks.append(
            {"type": "text", "text": "\n\n".join(branch_context_parts)}
        )

    forced_surface = str(D["forced_surface"]).strip()
    forced_action = str(D["forced_action"]).strip()
    forced_target_file = str(D["forced_target_file"]).strip()
    constraints = context.get("agentic_hypothesis_constraints")
    active_boundary = str(D["active_problem_boundary_surfaces"]).strip()
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
        if not active_boundary:
            boundary_value = constraints.get("active_problem_boundary_surfaces")
            if isinstance(boundary_value, (list, tuple)):
                active_boundary = ", ".join(
                    str(item).strip() for item in boundary_value if str(item).strip()
                )
            else:
                active_boundary = str(boundary_value or "").strip()
    targetable_files = str(D["targetable_files"]).strip()
    task_lines = [
        "## Target-Intent Preflight Task",
        "Choose the likely target intent for the next formal hypothesis.",
        "Return only structured fields. Do not include final hypothesis prose.",
        "Use action `modify` or `remove` for an existing target; use `create_new` for a new target.",
        (
            "The selected intent will bind the following formal hypothesis: "
            "target_file, action, change_locus, and mechanism family or "
            "mechanism continuation must stay consistent after preflight."
        ),
    ]
    if forced_surface:
        task_lines.append(f"Set `change_locus` exactly to `{forced_surface}`.")
    elif active_boundary:
        task_lines.append(f"Set `change_locus` to one of: {active_boundary}.")
    if forced_action:
        task_lines.append(f"Set `action` exactly to `{forced_action}`.")
    if forced_target_file:
        task_lines.append(f"Set `target_file` exactly to `{forced_target_file}`.")
    elif targetable_files:
        task_lines.append(
            "For existing targets, choose `target_file` from declared active "
            f"boundary files when applicable: {targetable_files}."
        )
    if same_mechanism_constraints:
        task_lines.append(
            "Same-branch refinement is same-mechanism only. Select a target "
            "intent for the protected mechanism. If the best idea is a new or "
            "unrelated mechanism, do not force it into this same-branch formal "
            "hypothesis; it requires a clean branch/fork signal before formal "
            "hypothesis generation."
        )
    task_lines.extend(
        _material_difference_requirement_task_lines(context, preflight=True)
    )
    user_prompt = (
        f"{dynamic_agentic_context + chr(10) + chr(10) if dynamic_agentic_context else ''}"
        + "\n".join(task_lines)
        + "\n\nRequired output fields:\n"
        "- `change_locus` or `surface`\n"
        "- `action`\n"
        "- `target_file`\n"
        "- `mechanism_id` or `mechanism_family` or `mechanism_sketch`\n"
        "- `confidence` and `notes` when useful\n"
    )
    return system_blocks, user_prompt


_AGENTIC_CONTEXT_HEADING_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_CACHEABLE_AGENTIC_CONTEXT_HEADINGS = frozenset(
    {
        "active algorithm facts",
        "active solver mechanism digest",
        "active solver map receipts",
        "solver-design full algorithm file reads",
    }
)


def _split_agentic_context_for_hypothesis_cache(
    text: str,
) -> tuple[str, str]:
    """Split stable active-solver context from dynamic session feedback.

    Generic Scion owns the cache boundary only: stable active fact/source
    projections may be cached, while tool observations, retry feedback, runtime
    feedback, and session ids stay uncached. The section names are generic APS
    prompt sections, not problem-domain semantics.
    """
    text = str(text or "")
    if not text.strip():
        return "", ""
    matches = list(_AGENTIC_CONTEXT_HEADING_RE.finditer(text))
    if not matches:
        return "", text
    cacheable: list[str] = []
    dynamic: list[str] = []
    if matches[0].start() > 0 and text[: matches[0].start()].strip():
        dynamic.append(text[: matches[0].start()].strip())
    for offset, match in enumerate(matches):
        start = match.start()
        end = matches[offset + 1].start() if offset + 1 < len(matches) else len(text)
        section = text[start:end].strip()
        heading = re.sub(r"\s+", " ", match.group(1).strip().lower())
        if heading in _CACHEABLE_AGENTIC_CONTEXT_HEADINGS:
            cacheable.append(section)
        else:
            dynamic.append(section)
    return "\n\n".join(cacheable), "\n\n".join(dynamic)


def _same_mechanism_followup_constraints(context: Mapping[str, Any]) -> str:
    """Project branch-local mechanism constraints before broader research context."""
    guidance = str(context.get("branch_hygiene_guidance") or "").strip()
    if "protected_mechanism_ids=" not in guidance:
        return ""
    protected = _extract_guidance_value(guidance, "protected_mechanism_ids")
    allowed = _prompt_same_mechanism_allowed_actions(guidance)
    clean_fork_policy = (
        _extract_guidance_value(guidance, "clean_fork_policy")
        or "clean_fork_required_for_new_mechanism"
    )
    forbidden_policy = (
        _extract_guidance_value(guidance, "forbidden_mechanism_policy")
        or "no_unrelated_mechanism_ids"
    )
    marginal_guidance = _marginal_same_branch_followup_guidance(context)
    return (
        "## Same-Mechanism Follow-up Constraints\n"
        f"protected_mechanism_ids={protected}\n"
        f"allowed_actions={allowed}\n"
        f"forbidden_mechanism_policy={forbidden_policy}\n"
        f"clean_fork_policy={clean_fork_policy}\n"
        "For this branch, hypothesis mechanism_changes must use only the "
        "protected ids above. Allowed work is limited to tuning, integration, "
        "repair, parameterization, or telemetry wiring for the same mechanism. "
        "These allowed_actions are research action labels, not "
        "mechanism_changes[].change_type values; map tune/parameterize to "
        "modify and telemetry_wiring to modify or integrate when emitting "
        "mechanism_changes. "
        "Telemetry/accounting-only repair is not a new algorithmic hypothesis: "
        "keep the target and protected mechanism ids fixed while repairing "
        "expected_telemetry or precise instrumentation. "
        "A new or unrelated mechanism requires a clean branch or clean fork "
        "before generation."
        f"{marginal_guidance}"
    )


def _prompt_same_mechanism_allowed_actions(guidance: str) -> str:
    raw_allowed = _extract_guidance_value(guidance, "same_mechanism_allowed_actions")
    if not raw_allowed:
        return ",".join(_PROMPT_SAME_MECHANISM_ALLOWED_ACTIONS)
    raw_actions = {item.strip() for item in raw_allowed.split(",") if item.strip()}
    prompt_actions = [
        action
        for action in _PROMPT_SAME_MECHANISM_ALLOWED_ACTIONS
        if action in raw_actions
    ]
    if prompt_actions:
        return ",".join(prompt_actions)
    return raw_allowed


def _extract_guidance_value(text: str, key: str) -> str:
    match = re.search(rf"\b{re.escape(key)}=([^;.\n]+)", text)
    return match.group(1).strip() if match else ""


def _marginal_same_branch_followup_guidance(context: Mapping[str, Any]) -> str:
    hygiene = context.get("branch_hygiene")
    if not isinstance(hygiene, Mapping):
        return ""
    status = str(hygiene.get("branch_code_status") or "").strip()
    tier = str(hygiene.get("last_screening_feedback_tier") or "").strip()
    if status != "active_marginal" and tier != "marginal":
        return ""
    positive_cases = _case_ids_from_hygiene(hygiene.get("case_level_winners"))
    if not positive_cases:
        positive_cases = _case_ids_from_hygiene(
            hygiene.get("case_level_positive_cases")
        )
    case_text = ",".join(positive_cases) if positive_cases else "available positive cases"
    phase = hygiene.get("phase_activation_summary")
    effect_status = ""
    activation_status = ""
    if isinstance(phase, Mapping):
        effect_status = str(
            phase.get("objective_effect_status") or phase.get("effect_status") or ""
        ).strip()
        activation_status = str(
            phase.get("activation_evidence_status")
            or phase.get("activation_status")
            or ""
        ).strip()
    evidence_bits = []
    if activation_status:
        evidence_bits.append(f"activation_status={activation_status}")
    if effect_status:
        evidence_bits.append(f"effect_status={effect_status}")
    evidence_text = "; " + "; ".join(evidence_bits) if evidence_bits else ""
    return (
        "\nMarginal same-branch refinement: positive_cases="
        f"{case_text}{evidence_text}. The next same-branch hypothesis must "
        "explain the causal effect_path from the protected mechanism to those "
        "positive cases, preserve or narrow the successful trigger, and state "
        "a no_op_condition guard for non-matching, tie-heavy, or loss-prone "
        "cases. Do not use this branch for broad unrelated exploration; if the "
        "effect_path or no-op guard cannot be named, require a clean branch or "
        "clean fork."
    )


def _case_ids_from_hygiene(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    case_ids: list[str] = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        case_id = str(
            item.get("case_id")
            or item.get("case")
            or item.get("instance")
            or item.get("name")
            or ""
        ).strip()
        if case_id:
            case_ids.append(case_id)
    return case_ids[:8]


def _compact_research_signals(
    context: Mapping[str, Any],
    D: Mapping[str, Any],
) -> str:
    """Render a default-visible research signal index before rules."""
    payload = _drop_empty_mapping(
        {
            "schema_version": "compact_research_signals.v1",
            "taint": "proposal_research_feedback",
            "decision_input_policy": "excluded_from_decision_features",
            "branch_history": _compact_text_signal(D["experiment_history"]),
            "sibling_branches": _compact_text_signal(D["sibling_summary"]),
            "blacklist": _compact_text_signal(D["blacklist_summary"]),
            "objective_opportunity_profile": _compact_text_signal(
                D.get("objective_opportunity_profile")
            ),
            "problem_measurement_diagnostics": _compact_text_signal(
                D.get("compact_problem_measurement_diagnostics")
                or D.get("problem_measurement_diagnostics"),
            ),
            "runtime_feedback": _compact_text_signal(D["runtime_feedback"]),
            "cross_branch_index": _compact_cross_branch_signal_index(context, D),
            "branch_lesson_ids": _lesson_ids_from_context(context),
            "research_shape": _compact_text_signal(D.get("research_shape_diagnostics")),
        }
    )
    if len(payload) <= 3:
        return ""
    return (
        "## Compact Research Signals\n"
        "Default-visible proposal context only; excluded from DecisionFeatures. "
        "Use this before broader rules or raw feedback when choosing the next "
        "mechanism.\n\n"
        f"{_compact_json(payload)}"
    )


def _drop_empty_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    return {
        str(key): item
        for key, item in value.items()
        if item not in (None, "", [], {}, ())
    }


def _compact_text_signal(
    value: Any,
    *,
    max_chars: int | None = None,
    enforce_max_chars: bool = False,
) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if not text or text in {"(none)", "none", "null"}:
        return ""
    return text


def _compact_cross_branch_signal_index(
    context: Mapping[str, Any],
    D: Mapping[str, Any],
) -> dict[str, Any]:
    ids = _lesson_ids_from_context(context)
    text = str(D.get("cross_branch_research") or "")
    if not ids and not text.strip():
        return {}
    return _drop_empty_mapping(
        {
            "lesson_ids": ids,
            "section_available": bool(text.strip()),
            "compact_learning_schema": (
                "compact_cross_branch_learning.v1"
                if "compact_cross_branch_learning.v1" in text
                else ""
            ),
            "signal_hint": _compact_text_signal(_first_nonempty_line(text)),
        }
    )


def _first_nonempty_line(value: str) -> str:
    for line in str(value or "").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("{"):
            return stripped
    return ""


def _compact_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, default=str)


def _lesson_ids_from_context(context: Mapping[str, Any]) -> list[str]:
    ids: list[str] = []
    for key in (
        "branch_lesson_records",
        "branch_lessons",
        "cross_branch_lesson_records",
    ):
        records = context.get(key)
        if not isinstance(records, (list, tuple)):
            continue
        for record in records:
            if not isinstance(record, Mapping):
                continue
            lesson_id = str(
                record.get("lesson_id")
                or record.get("id")
                or record.get("record_id")
                or ""
            ).strip()
            if lesson_id and lesson_id not in ids:
                ids.append(lesson_id)
    return ids


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
    target_intent_lines = _target_intent_binding_task_lines(context)
    material_difference_lines = _material_difference_requirement_task_lines(context)
    branch_lesson_usage_lines = _branch_lesson_usage_requirement_task_lines(context)
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
        lines.extend(target_intent_lines)
        lines.extend(material_difference_lines)
        lines.extend(branch_lesson_usage_lines)
        lines.extend(_novelty_signature_task_lines(novelty_requirements))
        return "\n".join(lines) + "\n"
    if active_boundary:
        targetable_files = str(context.get("targetable_files") or "")
        available_actions = str(
            context.get("available_actions") or "create_new, modify, remove"
        )
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
            f"Set `action` to one of the legal active-boundary actions: {available_actions}.",
        ]
        if targetable_files:
            lines.append(
                'If action is "modify" or "remove", provide `target_file` '
                f"from the active boundary files: {targetable_files}."
            )
        lines.extend(target_intent_lines)
        if "solver_design" in active_boundary:
            lines.extend(_solver_design_hypothesis_guidance(context))
        lines.extend(_novelty_signature_task_lines(novelty_requirements))
        lines.extend(material_difference_lines)
        lines.extend(branch_lesson_usage_lines)
        return "\n".join(lines) + "\n"
    operator_categories = str(context.get("operator_categories") or "")
    available_actions = str(
        context.get("available_actions") or "create_new, modify, remove"
    )
    targetable_files = str(context.get("targetable_files") or "")
    lines = [
        "## Task",
        "Propose ONE new hypothesis for improving the solver.",
        f"Choose a research surface from {operator_categories} as `change_locus`.",
        f"Set `action` to one of: {available_actions}.",
        (
            'If action is "modify" or "remove", provide `target_file` from '
            f"the targetable files when available: {targetable_files}."
        ),
    ]
    lines.extend(target_intent_lines)
    lines.extend(material_difference_lines)
    lines.extend(branch_lesson_usage_lines)
    return "\n".join(lines) + "\n"


def _target_intent_binding_task_lines(context: Mapping[str, Any]) -> list[str]:
    raw_intent = context.get("agentic_hypothesis_target_intent")
    if not isinstance(raw_intent, Mapping):
        return []
    intent_value = raw_intent.get("intent")
    intent = intent_value if isinstance(intent_value, Mapping) else raw_intent
    change_locus = str(
        intent.get("change_locus") or intent.get("surface") or ""
    ).strip()
    action = str(intent.get("action") or "").strip()
    target_file = str(intent.get("target_file") or "").strip()
    mechanism_family = str(intent.get("mechanism_family") or "").strip()
    mechanism_id = str(intent.get("mechanism_id") or "").strip()
    raw_mechanism_id = str(intent.get("raw_mechanism_id") or "").strip()
    lines = [
        "Selected target-intent binding: this formal hypothesis must keep "
        "`change_locus`, `action`, `target_file`, and mechanism family or "
        "mechanism continuation consistent with the host-selected intent."
    ]
    if change_locus:
        lines.append(f"Set `change_locus` to selected intent value `{change_locus}`.")
    if action:
        lines.append(f"Set `action` to selected intent value `{action}`.")
    if target_file:
        lines.append(f"Set `target_file` to selected intent value `{target_file}`.")
    if mechanism_id or mechanism_family:
        lines.append(
            "Use mechanism_changes / novelty_signature that continue selected "
            f"formal schema mechanism_id `{mechanism_id or '<none>'}` or "
            f"mechanism_family `{mechanism_family or '<none>'}`; do not switch "
            "to a different mechanism in the formal hypothesis."
        )
    if mechanism_id:
        lines.append(
            f"Write formal `mechanism_changes[].id` as `{mechanism_id}` "
            "when this hypothesis declares mechanism_changes; it already "
            "matches ^[a-z][a-z0-9_]{0,63}$."
        )
    if raw_mechanism_id and raw_mechanism_id != mechanism_id:
        lines.append(
            f"Raw mechanism id `{raw_mechanism_id}` is audit provenance only; "
            "do not copy raw/provenance ids into formal mechanism_changes or "
            "expected telemetry refs."
        )
    lines.append(
        "If the intended formal hypothesis needs a different target or "
        "mechanism, stop and require a host-controlled target-intent reselect "
        "before formal hypothesis generation."
    )
    return lines


def _material_difference_requirement_task_lines(
    context: Mapping[str, Any],
    *,
    preflight: bool = False,
) -> list[str]:
    requirement = context.get("material_difference_requirement")
    if not isinstance(requirement, Mapping) or requirement.get("required") is False:
        return []
    if not (
        requirement.get("required") is True
        or str(requirement.get("record_id") or "").strip()
        or str(requirement.get("required_for") or "").strip()
    ):
        return []
    required_for = str(requirement.get("required_for") or "unspecified").strip()
    source = str(requirement.get("requirement_source") or "scheduler_audit").strip()
    if preflight:
        return [
            (
                "Material-difference requirement is active for "
                f"{required_for} from {source}. Select a target intent only "
                "if the later formal hypothesis can state a concrete "
                "material_difference against the listed nearby candidates "
                "using structural anchors such as `changed_dimensions`, "
                "`signature_digest`, or `evidence_status_delta`."
            )
        ]
    return [
        (
            "Material-difference requirement is active for "
            f"{required_for} from {source}: the formal hypothesis must include "
            "a non-empty `material_difference` object."
        ),
        (
            "`material_difference` must contain compact generic structural "
            "anchors such as `changed_dimensions`, `signature_digest`, or "
            "`evidence_status_delta`. "
            "Do not satisfy it with generic phrases such as 'different "
            "approach', 'new mechanism', 'materially different', repeated "
            "hypothesis prose, or descriptive-only fields such as "
            "`differs_from` or `effect_path`."
        ),
    ]


def _branch_lesson_usage_context_block(context: Mapping[str, Any]) -> str:
    payload: dict[str, Any] = {}
    requirement = context.get("branch_lesson_usage_requirement")
    if isinstance(requirement, Mapping) and requirement:
        payload["branch_lesson_usage_requirement"] = (
            _compact_branch_lesson_usage_requirement(requirement)
        )
    for key in (
        "branch_lesson_records",
        "branch_lessons",
        "cross_branch_lesson_records",
    ):
        records = context.get(key)
        if records:
            payload[key] = _compact_branch_lesson_records(records)
    if not payload:
        return ""
    return (
        "## Branch Lesson Usage Context\n"
        "This is tainted proposal-only research feedback and is excluded from "
        "DecisionFeatures. Use compact lesson ids and generic dimensions; do "
        "not copy raw lesson text into the formal hypothesis.\n\n"
        f"{_compact_json(payload)}"
    )


def _branch_lesson_usage_requirement_task_lines(
    context: Mapping[str, Any],
) -> list[str]:
    if not _branch_lesson_usage_context_present(context):
        return []
    return [
        (
            "Branch lesson usage context is active: the formal hypothesis must "
            "include a compact proposal-only `branch_lesson_usage` object that "
            "states which visible lessons it borrows, avoids, contrasts, "
            "preserves, or rejects with machine-readable reason codes."
        ),
        (
            "For a clean fork or sibling-aware proposal, `branch_lesson_usage` "
            "must include at least one of `borrowed_lessons`, "
            "`avoided_lessons`, or `contrasted_lessons`, plus changed generic "
            "contrast dimensions and target_file/action/mechanism linkage. For "
            "weak-positive transfer, borrow or preserve with activation_path "
            "and effect_path, or emit `rejected_weak_positive_lessons` with a "
            "reject_reason_code and the same linkage. For same-branch "
            "weak-positive refinement, use `preserved_same_branch_lesson` when "
            "preserving local evidence. Keep values to compact ids, enum-like "
            "tokens, short arrays, and small "
            "objects; do not include raw lesson text, rationale, reasoning, "
            "trace, prompt, transcript, observation, or problem-specific "
            "semantics."
        ),
        (
            "When leaving a no-effect or weak-positive branch via a clean fork, "
            "make the semantic contrast auditable: include the source lesson id, "
            "the old target/action/mechanism family being avoided or contrasted, "
            "the new target/action/mechanism linkage, and at least one changed "
            "generic contrast dimension such as target_file, mechanism_family, "
            "runtime_budget_strategy, activation_path, effect_path, or "
            "no_op_condition."
        ),
    ]


def _branch_lesson_usage_context_present(context: Mapping[str, Any]) -> bool:
    requirement = context.get("branch_lesson_usage_requirement")
    if isinstance(requirement, Mapping) and requirement.get("required") is False:
        requirement = {}
    if isinstance(requirement, Mapping) and requirement:
        return True
    for key in (
        "branch_lesson_records",
        "branch_lessons",
        "cross_branch_lesson_records",
    ):
        records = context.get(key)
        if records not in (None, "", [], {}, ()):
            return True
    return False


def _compact_branch_lesson_usage_requirement(
    requirement: Mapping[str, Any],
) -> dict[str, Any]:
    keep_fields = (
        "schema_version",
        "record_id",
        "record_digest",
        "requirement_source",
        "required",
        "required_for",
        "required_fors",
        "required_output_field",
        "candidate_lesson_ids",
        "candidate_target_files",
        "candidate_actions",
        "candidate_change_loci",
        "candidate_mechanism_families",
        "required_contrast_dimensions",
        "same_branch_refinement_allowed",
        "sibling_duplication_allowed",
        "pre_code_block_required",
        "proposal_visibility_only",
        "decision_features_excluded",
    )
    return {
        key: _compact_branch_lesson_value(requirement.get(key))
        for key in keep_fields
        if requirement.get(key) not in (None, "", [], {}, ())
    }


def _compact_branch_lesson_records(records: Any) -> list[dict[str, Any]]:
    if not isinstance(records, (list, tuple)):
        return []
    compact: list[dict[str, Any]] = []
    for raw in records:
        if not isinstance(raw, Mapping):
            continue
        item = {
            key: _compact_branch_lesson_value(raw.get(key))
            for key in (
                "schema_version",
                "lesson_id",
                "source",
                "decision_input_policy",
                "scope",
                "lesson_role",
                "lesson_type",
                "maturity",
                "source_branch_ids",
                "shared_signature",
                "evidence_basis",
                "summary",
                "outcome_summary",
            )
            if raw.get(key) not in (None, "", [], {}, ())
        }
        if item:
            compact.append(item)
    return compact


def _compact_branch_lesson_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        allowed = {
            "action",
            "activation_path",
            "activation_statuses",
            "change_locus",
            "decision_input_policy",
            "effect_path",
            "effect_statuses",
            "mechanism_family",
            "mechanism_id",
            "outcome_patterns",
            "outcome_summary",
            "required_contrast_dimensions",
            "required_for",
            "required_output_field",
            "same_branch_refinement_allowed",
            "sibling_duplication_allowed",
            "source_branch_ids",
            "summary",
            "target_file",
        }
        result = {
            str(key): _compact_branch_lesson_value(item)
            for key, item in value.items()
            if str(key) in allowed and item not in (None, "", [], {}, ())
        }
        return result
    if isinstance(value, (list, tuple)):
        return [_compact_branch_lesson_value(item) for item in value]
    if isinstance(value, str):
        text = re.sub(r"\s+", " ", value).strip()
        return text
    return value


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
        if str(surface_name) == "solver_design":
            lines.append(
                "For `solver_design`, make `novelty_signature` compact identity "
                "tokens, not prose. Put rationale and expected mechanism detail "
                "in `hypothesis_text`."
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
