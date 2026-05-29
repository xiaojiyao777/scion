"""Hypothesis prompt rendering for the proposal engine."""

from __future__ import annotations

import re
from typing import Any, Dict, Mapping

from .prompt_common import (
    _CACHE_5M,
    _DefaultDict,
    _agentic_research_context_block,
)
from .solver_design_prompts import _solver_design_hypothesis_guidance


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
        f"## Currently Occupied (C10 will auto-reject duplicates)\n{D['active_hyp_summary']}\n\n"
        f"## Sibling Branches\n{D['sibling_summary']}\n\n"
        f"## Analysis Steps (follow in order)\n"
        f"1. Read every relevant champion research-surface file and active solver fact available in context. For operator files, note: what move type, what objective(s) it improves or protects, what it cannot improve. For policy/config files, note the declared bounded lever being changed.\n"
        f"2. Identify the active bottleneck from screening/runtime feedback, objective opportunity profile, and experiment history. Distinguish the primary decision reason from auxiliary telemetry or runtime warnings.\n"
        f"3. Identify specific GAPS — what improvements are IMPOSSIBLE with the current pool or active solver design?\n"
        f"4. Check experiment history — which attempts at filling gaps failed, and WHY? Do not target a stable/protected objective or recent no-effect mechanism unless you have new evidence or a materially different mechanism.\n"
        f"5. Only then propose a hypothesis targeting an identified gap and active bottleneck.\n"
        f"6. In the hypothesis text, state: active bottleneck from feedback; stable/protected objectives to preserve; mechanism novelty evidence from active solver facts and prior feedback; why the target mechanism is likely to affect the bottleneck; and the no-op/failure conditions that avoid wasting runtime or harming protected objectives.\n"
        f"7. Fill the runtime intent fields: `target_runtime_effect`, `complexity_claim`, "
        f"and `runtime_budget_strategy`.\n\n"
        f"Telemetry contract: `expected_telemetry` top-level keys must be only "
        f"`activity`, `activation`, `effect`, or `budget`. Put declared runtime "
        f"field paths under those categories as exact strings or arrays of "
        f"strings; do not write prose descriptions as field values. Do not use "
        f"metric names or suffixes such as `best_delta`, `improvement_counts`, "
        f"`phase_runtime`, or `runtime_ms` as categories. Activation must be "
        f"mechanism-specific activity evidence, not objective/outcome fields. "
        f"Aggregate outcome/activity fields show effect or activity, not "
        f"activation. For mapping telemetry, use a mechanism-specific path "
        f"containing the declared mechanism id; the whole map field alone is "
        f"not activation evidence. If changing an existing phase or component, "
        f"name the changed lever as a mechanism id and use that same id in every "
        f"expected telemetry path.\n\n"
        f"Objective field contract: `target_objectives` and "
        f"`protected_objectives` must contain only declared problem objective ids. "
        f"Hard constraints, feasibility conditions, parser validity, and "
        f"solution consistency belong in `risk_to_higher_priority` or "
        f"`no_op_condition`, not in objective arrays.\n\n"
        f"Runtime constraint: proposed research-surface changes are evaluated inside the problem solver and "
        f"algorithmic efficiency is part of the evidence. Do not propose unbounded high-order "
        f"enumeration over problem entities; describe any top-k, "
        f"sampling, or early-stop cap needed to keep runtime comparable to the champion.\n\n"
        f"If your hypothesis duplicates an existing surface's capability (even partially), it will be REJECTED.\n\n"
        f"{negative_fact_block + chr(10) + chr(10) if negative_fact_block else ''}"
        f"{_hypothesis_task_prompt(D)}"
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
        if "solver_design" in active_boundary:
            lines.extend(_solver_design_hypothesis_guidance(context))
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
