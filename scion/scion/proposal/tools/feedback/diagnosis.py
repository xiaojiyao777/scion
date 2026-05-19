"""Research-diagnosis and surface-priority summaries from safe feedback."""

from __future__ import annotations

from typing import Any, Mapping

from scion.core.models import ExperimentStage, StepRecord
from scion.proposal.context_manager import _filter_hypothesis_prompt_steps, _get_research_surfaces
from scion.proposal.tools.feedback.attribution import (
    _runtime_highlight_has_nonzero_numeric,
    _runtime_highlight_is_all_zero_numeric,
    _surface_runtime_attribution_payload,
    _safe_positive_int,
)
from scion.proposal.tools.feedback.stats import _eval_stats_payload
from scion.proposal.tools.models import ProposalToolContext
from scion.proposal.tools.surface.compaction import _drop_empty_items
from scion.proposal.tools.utils import _attr


def _research_diagnosis_payload(
    safe_steps: list[StepRecord],
    *,
    max_items: int,
    problem_spec: Any = None,
) -> dict[str, Any]:
    screening_steps = [
        step
        for step in safe_steps
        if (
            step.protocol_result is not None
            and step.protocol_result.stage == ExperimentStage.SCREENING
        )
    ]
    recent_steps = list(reversed(screening_steps))[:max_items]
    reason_counts: dict[str, int] = {}
    surface_counts: dict[str, int] = {}
    all_screening_surface_counts: dict[str, int] = {}
    gate_counts: dict[str, int] = {}
    failure_tags: set[str] = set()
    recent_rows: list[dict[str, Any]] = []
    runtime_signal_rows: list[dict[str, Any]] = []
    declared_solver_design_surfaces = _declared_solver_design_surface_names(
        problem_spec
    )
    failed_solver_design_surfaces = _pre_protocol_failed_solver_design_surface_names(
        safe_steps,
        declared_solver_design_surfaces,
    )
    screening_failed_solver_design_surfaces = (
        _screening_failed_solver_design_surface_names(
            safe_steps,
            declared_solver_design_surfaces,
        )
    )
    declared_mechanism_surfaces = (
        []
        if declared_solver_design_surfaces
        else _declared_mechanism_surface_names(problem_spec)
    )

    for step in screening_steps:
        surface = step.hypothesis.change_locus
        all_screening_surface_counts[surface] = (
            all_screening_surface_counts.get(surface, 0) + 1
        )

    for step in recent_steps:
        protocol = step.protocol_result
        if protocol is None:
            continue
        surface = step.hypothesis.change_locus
        surface_counts[surface] = surface_counts.get(surface, 0) + 1
        gate = str(protocol.gate_outcome or "")
        gate_counts[gate] = gate_counts.get(gate, 0) + 1
        for reason in protocol.reason_codes or ():
            reason_text = str(reason)
            reason_counts[reason_text] = reason_counts.get(reason_text, 0) + 1
            if "WIN_RATE" in reason_text.upper():
                failure_tags.add("screening_win_rate_failure")
            if "RUNTIME" in reason_text.upper():
                failure_tags.add("runtime_related_failure")
        stats = protocol.stats
        if stats.win_rate is not None and float(stats.win_rate) <= 0.0:
            failure_tags.add("zero_case_win_rate")
        if stats.median_delta is not None and abs(float(stats.median_delta)) <= 1e-12:
            failure_tags.add("zero_median_delta")

        attribution = _surface_runtime_attribution_payload(step)
        runtime_fields = []
        runtime_issue_fields = []
        runtime_nonzero_fields = []
        zero_phase_delta_fields = []
        accepted_signal_fields = []
        recovery_signal_fields = []
        for highlight in attribution.get("runtime_field_highlights", []) or []:
            if not isinstance(highlight, Mapping):
                continue
            field = str(highlight.get("field") or "")
            if not field:
                continue
            runtime_fields.append(field)
            if any(
                _safe_positive_int(highlight.get(key))
                for key in ("missing", "empty", "failed")
            ):
                runtime_issue_fields.append(field)
            if _runtime_highlight_has_nonzero_numeric(highlight):
                runtime_nonzero_fields.append(field)
                if "accepted" in field:
                    accepted_signal_fields.append(field)
                if "recovery" in field:
                    recovery_signal_fields.append(field)
            if (
                "phase_delta" in field or field.endswith("_delta_by_phase")
            ) and _runtime_highlight_is_all_zero_numeric(highlight):
                zero_phase_delta_fields.append(field)
        if runtime_issue_fields:
            failure_tags.add("runtime_evidence_contract_issue")
        if runtime_nonzero_fields and gate != "pass":
            failure_tags.add("runtime_signal_without_protocol_pass")
        if zero_phase_delta_fields:
            failure_tags.add("zero_phase_delta")
        if zero_phase_delta_fields and accepted_signal_fields:
            failure_tags.add("accepted_signal_without_phase_delta")
        if zero_phase_delta_fields and recovery_signal_fields:
            failure_tags.add("recovery_only_accepted_moves")
        if runtime_fields:
            runtime_signal_rows.append(
                _drop_empty_items(
                    {
                        "round_num": step.round_num,
                        "surface": surface,
                        "gate_outcome": gate,
                        "highlight_fields": runtime_fields[:8],
                        "nonzero_numeric_fields": runtime_nonzero_fields[:8],
                        "zero_phase_delta_fields": zero_phase_delta_fields[:8],
                        "accepted_signal_fields": accepted_signal_fields[:8],
                        "recovery_signal_fields": recovery_signal_fields[:8],
                        "issue_fields": runtime_issue_fields[:8],
                    }
                )
            )
        recent_rows.append(
            {
                "round_num": step.round_num,
                "surface": surface,
                "target_file": step.hypothesis.target_file,
                "gate_outcome": gate,
                "reason_codes": list(protocol.reason_codes),
                "stats": _eval_stats_payload(stats),
            }
        )

    unselected_solver_design_surfaces = [
        surface
        for surface in declared_solver_design_surfaces
        if surface not in all_screening_surface_counts
    ]
    unselected_mechanism_surfaces = [
        surface
        for surface in declared_mechanism_surfaces
        if surface not in all_screening_surface_counts
    ]
    if declared_solver_design_surfaces and unselected_solver_design_surfaces:
        failure_tags.add("solver_design_not_selected")
    if failed_solver_design_surfaces:
        failure_tags.add("solver_design_pre_protocol_failure")
    if screening_failed_solver_design_surfaces:
        failure_tags.add("solver_design_screening_failure")
    if declared_mechanism_surfaces and unselected_mechanism_surfaces:
        failure_tags.add("deep_surface_not_selected")

    next_requirements = [
        "Name the screening/runtime evidence pattern being addressed.",
        "State which declared surface evidence fields are expected to change.",
        "Change the mechanism or bounded lever, not only wording or novelty text.",
        "State how the implementation remains within declared interface and bounds.",
    ]
    if failed_solver_design_surfaces:
        next_requirements.append(
            "Retry the solver-design boundary with a different lifecycle "
            "implementation; a pre-screening candidate failure does not retire "
            "the problem-object surface: "
            + ", ".join(failed_solver_design_surfaces[:8])
        )
    elif screening_failed_solver_design_surfaces:
        next_requirements.append(
            "Keep change_locus on the solver-design boundary and change the "
            "whole-lifecycle implementation; screening failure means the "
            "candidate design failed, not that component policies should become "
            "replacement research goals: "
            + ", ".join(screening_failed_solver_design_surfaces[:8])
        )
    elif unselected_solver_design_surfaces:
        next_requirements.append(
            "Use a solver-design surface that reasons from the problem object "
            "before repeating component policies: "
            + ", ".join(unselected_solver_design_surfaces[:8])
        )
    elif unselected_mechanism_surfaces:
        next_requirements.append(
            "Exercise an unselected mechanism surface before repeating older "
            "orchestration surfaces: " + ", ".join(unselected_mechanism_surfaces[:8])
        )
    if "zero_phase_delta" in failure_tags:
        next_requirements.append(
            "Explain how the candidate should move phase-best/objective-delta "
            "runtime fields, not only attempts or accepted counts."
        )

    return {
        "schema_version": "research-diagnosis.v1",
        "screening_only": True,
        "screening_step_count": len(screening_steps),
        "recent_screening_steps": recent_rows,
        "reason_code_counts": reason_counts,
        "surface_counts": surface_counts,
        "declared_solver_design_surfaces": declared_solver_design_surfaces,
        "failed_solver_design_surfaces": failed_solver_design_surfaces,
        "screening_failed_solver_design_surfaces": (
            screening_failed_solver_design_surfaces
        ),
        "unselected_solver_design_surfaces": unselected_solver_design_surfaces,
        "declared_mechanism_surfaces": declared_mechanism_surfaces,
        "unselected_mechanism_surfaces": unselected_mechanism_surfaces,
        "gate_outcome_counts": gate_counts,
        "failure_mode_tags": sorted(failure_tags),
        "runtime_signal_rows": runtime_signal_rows,
        "next_hypothesis_requirements": next_requirements,
    }
def _diagnostic_surface_priorities(
    context: ProposalToolContext,
    declared_surfaces: tuple[Any, ...],
) -> dict[str, Any]:
    solver_design_surfaces = _declared_solver_design_surface_names(
        context.problem_spec
    )
    failed_solver_design = _pre_protocol_failed_solver_design_surface_names(
        list(context.step_history),
        solver_design_surfaces,
    )
    screening_failed_solver_design = _screening_failed_solver_design_surface_names(
        list(context.step_history),
        solver_design_surfaces,
    )
    mechanism_surfaces = _declared_mechanism_surface_names(context.problem_spec)
    if not mechanism_surfaces:
        mechanism_surfaces = _mechanism_surface_names_from_surfaces(declared_surfaces)
    screened_surfaces = {
        step.hypothesis.change_locus
        for step in _filter_hypothesis_prompt_steps(list(context.step_history))
        if (
            step.protocol_result is not None
            and step.protocol_result.stage == ExperimentStage.SCREENING
        )
    }
    has_screening_history = bool(screened_surfaces)
    if solver_design_surfaces:
        unselected_solver_design = [
            surface
            for surface in solver_design_surfaces
            if surface not in screened_surfaces
        ]
        failure_mode_tags = []
        if has_screening_history and unselected_solver_design:
            failure_mode_tags.append("solver_design_not_selected")
        if failed_solver_design:
            failure_mode_tags.append("solver_design_pre_protocol_failure")
        if screening_failed_solver_design:
            failure_mode_tags.append("solver_design_screening_failure")
        next_requirements = []
        if failed_solver_design:
            next_requirements.append(
                "Retry the problem-object solver-design surface with a "
                "different lifecycle implementation; the prior failure was a "
                "candidate failure, not a surface retirement: "
                + ", ".join(failed_solver_design[:8])
            )
        elif screening_failed_solver_design:
            next_requirements.append(
                "Keep the next change_locus on the problem-object "
                "solver-design surface; prior screening failures are candidate "
                "design failures, not a reason to switch research goals to "
                "component policies: "
                + ", ".join(screening_failed_solver_design[:8])
            )
        elif has_screening_history and unselected_solver_design:
            next_requirements.append(
                "Prioritize a solver-design surface that reasons from the "
                "problem object before repeating component policies: "
                + ", ".join(unselected_solver_design[:8])
            )
        recommendation = None
        if failed_solver_design:
            recommendation = (
                "Retry the problem-object solver-design boundary; the prior "
                "pre-protocol result is a candidate failure, and component "
                "policies remain attribution hooks, not fallback research goals."
            )
        elif screening_failed_solver_design:
            recommendation = (
                "Keep change_locus on the problem-object solver-design "
                "boundary; use component policies only as implementation hooks "
                "or attribution evidence inside the solver design."
            )
        elif has_screening_history and unselected_solver_design:
            recommendation = (
                "Prioritize the problem-object solver-design surface; "
                "component policies are attribution hooks, not isolated "
                "research targets."
            )
        return _drop_empty_items(
            {
                "solver_design_surfaces": solver_design_surfaces,
                "failed_solver_design_surfaces": failed_solver_design,
                "screening_failed_solver_design_surfaces": (
                    screening_failed_solver_design
                ),
                "unselected_solver_design_surfaces": unselected_solver_design,
                "failure_mode_tags": failure_mode_tags,
                "next_requirements": next_requirements,
                "recommendation": recommendation,
            }
        )
    unselected = [
        surface for surface in mechanism_surfaces if surface not in screened_surfaces
    ]
    failure_mode_tags = (
        ["deep_surface_not_selected"] if has_screening_history and unselected else []
    )
    next_requirements = (
        [
            "Exercise one unselected mechanism surface before repeating "
            "orchestration or legacy policy surfaces: " + ", ".join(unselected[:8])
        ]
        if has_screening_history and unselected
        else []
    )
    return _drop_empty_items(
        {
            "mechanism_surfaces": mechanism_surfaces,
            "unselected_mechanism_surfaces": unselected,
            "failure_mode_tags": failure_mode_tags,
            "next_requirements": next_requirements,
            "recommendation": (
                "Prioritize one unselected mechanism surface for the next short "
                "diagnostic before repeating orchestration or legacy policy surfaces."
                if has_screening_history and unselected
                else None
            ),
        }
    )
def _declared_solver_design_surface_names(problem_spec: Any) -> list[str]:
    if problem_spec is None:
        return []
    names: list[str] = []
    for surface in _get_research_surfaces(problem_spec):
        name = str(_attr(surface, "name") or "").strip()
        if not name:
            continue
        role = _attr(_attr(surface, "algorithm"), "role", "")
        kind = str(_attr(surface, "kind", "") or "")
        haystack = f"{kind} {role}".lower()
        if (
            kind in {"solver_design", "solver_algorithm"}
            or "solver_design" in haystack
            or "solver_algorithm" in haystack
        ):
            names.append(name)
    return names
def _pre_protocol_failed_solver_design_surface_names(
    steps: list[StepRecord],
    solver_design_surfaces: list[str],
) -> list[str]:
    if not solver_design_surfaces:
        return []
    allowed = set(solver_design_surfaces)
    failed: list[str] = []
    for step in _filter_hypothesis_prompt_steps(steps):
        surface = str(step.hypothesis.change_locus or "").strip()
        if surface not in allowed:
            continue
        if step.protocol_result is not None:
            continue
        if step.failure_stage in {"verification", "patch_contract", "workspace"}:
            if surface not in failed:
                failed.append(surface)
    return failed
def _screening_failed_solver_design_surface_names(
    steps: list[StepRecord],
    solver_design_surfaces: list[str],
) -> list[str]:
    if not solver_design_surfaces:
        return []
    allowed = set(solver_design_surfaces)
    failed: list[str] = []
    for step in _filter_hypothesis_prompt_steps(steps):
        surface = str(step.hypothesis.change_locus or "").strip()
        if surface not in allowed:
            continue
        result = step.protocol_result
        if result is None:
            continue
        if step.decision is not None and getattr(step.decision, "value", "") == "promote":
            continue
        if getattr(result, "gate_outcome", None) == "pass":
            continue
        if surface not in failed:
            failed.append(surface)
    return failed
def _declared_mechanism_surface_names(problem_spec: Any) -> list[str]:
    if problem_spec is None:
        return []
    return _mechanism_surface_names_from_surfaces(_get_research_surfaces(problem_spec))
def _mechanism_surface_names_from_surfaces(surfaces: Any) -> list[str]:
    names: list[str] = []
    for surface in surfaces or ():
        name = str(_attr(surface, "name") or "").strip()
        if not name:
            continue
        role = _attr(_attr(surface, "algorithm"), "role", "")
        description = _attr(_attr(surface, "algorithm"), "description", "")
        kind = str(_attr(surface, "kind", "") or "")
        haystack = f"{role} {description} {kind} {name}".lower()
        if (
            "mechanism" in haystack
            or "candidate_generation" in haystack
            or kind == "acceptance_restart"
        ):
            names.append(name)
    return names

__all__ = [
    "_research_diagnosis_payload",
    "_diagnostic_surface_priorities",
    "_declared_solver_design_surface_names",
    "_pre_protocol_failed_solver_design_surface_names",
    "_screening_failed_solver_design_surface_names",
    "_declared_mechanism_surface_names",
    "_mechanism_surface_names_from_surfaces",
]
