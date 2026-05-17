"""Memory and experiment-feedback proposal tools."""

from __future__ import annotations

from typing import Any, Mapping

from scion.core.models import ExperimentStage, StepRecord
from scion.proposal.context_manager import (
    _build_runtime_feedback,
    _build_runtime_failure_guidance,
    _filter_hypothesis_prompt_steps,
    _get_adapter_problem_spec,
    _get_research_surfaces,
)
from scion.proposal.tools.base import _BaseReadOnlyTool
from scion.proposal.tools.models import (
    FeedbackQueryInput,
    HoldoutExposure,
    MemoryQueryInput,
    ProposalExposureLevel,
    ProposalObservation,
    ProposalToolContext,
    ProposalToolFailureCode,
    ProposalToolPermission,
)
from scion.proposal.tools.surface import _drop_empty_items
from scion.proposal.tools.utils import (
    _attr,
    _json_size,
    _limit_text,
    _model_payload,
    _stage_value,
    _strip_forbidden_value,
)

_COMPACT_FEEDBACK_PAYLOAD_CHARS = 24000
_COMPACT_FEEDBACK_TEXT_CHARS = 8000
_COMPACT_FEEDBACK_STRING_CHARS = 1200
_COMPACT_FEEDBACK_LIST_ITEMS = 8
_COMPACT_FEEDBACK_MAP_ITEMS = 32
_RUNTIME_ATTRIBUTION_SUFFIXES = (
    "_initial_distance",
    "_returned_distance",
    "_objective_delta",
    "_active",
    "_loaded",
    "_errors",
    "_attempts",
    "_accepted",
    "_skip_reasons",
    "_best_delta",
    "_improvement_counts",
    "_accepted_delta_sum",
    "_accepted_best_delta",
    "_accepted_positive_counts",
    "_recovery_delta_sum",
    "_recovery_best_delta",
    "_recovery_counts",
    "_phase_delta_sum",
    "_phase_best_delta",
    "_phase_improvement_counts",
    "_runtime_ms",
    "_objective_trace",
    "_delta_by_phase",
    "_stop_reason",
    "_coverage_status",
    "_quality_guard_applied",
    "_param_clamps",
)
_RUNTIME_ATTRIBUTION_PRIORITY_SUFFIXES = (
    "_objective_trace",
    "_objective_delta",
    "_delta_by_phase",
    "_phase_delta_sum",
    "_initial_distance",
    "_returned_distance",
    "_phase_best_delta",
    "_phase_improvement_counts",
    "_recovery_delta_sum",
    "_recovery_best_delta",
    "_recovery_counts",
    "_accepted_delta_sum",
    "_accepted_best_delta",
    "_accepted_positive_counts",
    "_accepted",
    "_attempts",
    "_skip_reasons",
    "_best_delta",
    "_improvement_counts",
    "_coverage_status",
    "_stop_reason",
    "_errors",
    "_active",
    "_loaded",
)

class MemoryQueryTool(_BaseReadOnlyTool):
    name = "memory.query"
    input_schema = MemoryQueryInput
    permission = ProposalToolPermission.READ_TAINTED_MEMORY
    max_result_chars = 20000

    def call(
        self,
        args: MemoryQueryInput,
        context: ProposalToolContext,
    ) -> ProposalObservation:
        sections: list[str] = []
        if context.search_memory is not None:
            render = getattr(context.search_memory, "render", None)
            if not callable(render):
                return self._error(
                    context,
                    failure_code=ProposalToolFailureCode.UNSUPPORTED,
                    summary="Search memory does not provide a callable render method.",
                    repair_hint=(
                        "Provide a callable render(view='hypothesis') implementation "
                        "for proposal memory reads."
                    ),
                )
            try:
                text = render(view="hypothesis")
            except TypeError:
                return self._error(
                    context,
                    failure_code=ProposalToolFailureCode.UNSUPPORTED,
                    summary="Search memory does not support the safe hypothesis view.",
                    repair_hint=(
                        "Provide a render(view='hypothesis') implementation for "
                        "proposal memory reads."
                    ),
                )
            if text:
                sections.append(str(text))
        if context.research_log is not None:
            render = getattr(context.research_log, "render", None)
            if not callable(render):
                return self._error(
                    context,
                    failure_code=ProposalToolFailureCode.UNSUPPORTED,
                    summary="Research log does not provide a callable render method.",
                    repair_hint=(
                        "Provide a callable render(view='hypothesis') implementation "
                        "for proposal memory reads."
                    ),
                )
            try:
                text = render(view="hypothesis")
            except TypeError:
                return self._error(
                    context,
                    failure_code=ProposalToolFailureCode.UNSUPPORTED,
                    summary="Research log does not support the safe hypothesis view.",
                    repair_hint=(
                        "Provide a render(view='hypothesis') implementation for "
                        "proposal memory reads."
                    ),
                )
            if text:
                sections.append(str(text))

        combined = "\n\n".join(sections)
        combined = _sanitize_memory_text(combined)
        if args.surface:
            combined = "\n".join(
                line for line in combined.splitlines() if args.surface in line
            )
        if args.query:
            q = args.query.lower()
            combined = "\n".join(
                line for line in combined.splitlines() if q in line.lower()
            )
        limited = _limit_text(combined, args.max_chars)
        payload = {
            "query": args.query,
            "surface": args.surface,
            "text": limited,
            "truncated": len(combined) > args.max_chars,
            "policy_id": context.policy.context_policy_id,
            "excluded_signals": [
                "champion_evolution",
                "promotion_path",
                "validation",
                "frozen",
                "holdout",
            ],
        }
        return self._observation(
            context,
            observation_type="proposal_memory",
            summary="Returned tainted proposal/search memory safe view.",
            structured_payload=payload,
            exposure_level=ProposalExposureLevel.TAINTED_MEMORY,
        )

class FeedbackQueryScreeningTool(_BaseReadOnlyTool):
    name = "feedback.query_screening"
    input_schema = FeedbackQueryInput
    permission = ProposalToolPermission.READ_TAINTED_MEMORY

    def call(
        self,
        args: FeedbackQueryInput,
        context: ProposalToolContext,
    ) -> ProposalObservation:
        if not context.policy.allow_screening_case_detail:
            return self._error(
                context,
                failure_code=ProposalToolFailureCode.EXPOSURE_DENIED,
                summary="Screening detail is disabled by ContextExposurePolicy.",
            )
        safe_steps = _filter_hypothesis_prompt_steps(list(context.step_history))
        available_screening_steps = [
            step
            for step in safe_steps
            if (
                step.protocol_result is not None
                and step.protocol_result.stage == ExperimentStage.SCREENING
            )
        ]
        rows = []
        matched_count = 0
        for step in reversed(available_screening_steps):
            protocol = step.protocol_result
            if protocol is None or protocol.stage != ExperimentStage.SCREENING:
                continue
            if args.branch_id and step.branch_id != args.branch_id:
                continue
            surface = step.hypothesis.change_locus
            if args.surface and surface != args.surface:
                continue
            matched_count += 1
            if len(rows) < args.max_items:
                rows.append(_screening_step_payload(step))
        payload = {
            "branch_id": args.branch_id,
            "surface": args.surface,
            "query_scope": {
                "campaign_id": context.campaign_id,
                "branch_filter_applied": bool(args.branch_id),
                "surface_filter_applied": bool(args.surface),
                "recent_first": True,
            },
            "available_screening_step_count": len(available_screening_steps),
            "matched_screening_step_count": matched_count,
            "screening_steps": rows,
        }
        payload = _bound_compact_feedback_payload(payload)
        return self._observation(
            context,
            observation_type="screening_feedback",
            summary=(
                f"Returned {len(rows)} of {matched_count} screening feedback row(s)."
            ),
            structured_payload=payload,
            exposure_level=ProposalExposureLevel.SCREENING_DETAIL,
        )

class FeedbackQueryHoldoutSummaryTool(_BaseReadOnlyTool):
    name = "feedback.query_holdout_summary"
    input_schema = FeedbackQueryInput
    permission = ProposalToolPermission.READ_TAINTED_MEMORY

    def call(
        self,
        args: FeedbackQueryInput,
        context: ProposalToolContext,
    ) -> ProposalObservation:
        rows = []
        for step in context.step_history:
            protocol = step.protocol_result
            if protocol is None or protocol.stage == ExperimentStage.SCREENING:
                continue
            if args.branch_id and step.branch_id != args.branch_id:
                continue
            surface = step.hypothesis.change_locus
            if args.surface and surface != args.surface:
                continue
            stage = _stage_value(protocol.stage)
            if stage == "validation":
                exposure = context.policy.validation_exposure
                level = ProposalExposureLevel.VALIDATION_AGGREGATE
            elif stage == "frozen":
                exposure = context.policy.frozen_exposure
                level = ProposalExposureLevel.FROZEN_AGGREGATE
            else:
                continue
            if exposure == HoldoutExposure.NONE:
                continue
            rows.append(_holdout_step_payload(step, exposure, level))
            if len(rows) >= args.max_items:
                break

        payload = {
            "branch_id": args.branch_id,
            "surface": args.surface,
            "holdout_steps": rows,
            "validation_exposure": context.policy.validation_exposure.value,
            "frozen_exposure": context.policy.frozen_exposure.value,
            "metrics_file_refs_exposed": False,
        }
        exposure_level = (
            ProposalExposureLevel.VALIDATION_AGGREGATE
            if any(row.get("stage") == "validation" for row in rows)
            else (
                ProposalExposureLevel.FROZEN_AGGREGATE
                if rows
                else ProposalExposureLevel.NONE
            )
        )
        return self._observation(
            context,
            observation_type="holdout_summary",
            summary=f"Returned {len(rows)} exposure-controlled holdout row(s).",
            structured_payload=payload,
            exposure_level=exposure_level,
        )

class FeedbackQueryRuntimeTool(_BaseReadOnlyTool):
    name = "feedback.query_runtime"
    input_schema = FeedbackQueryInput
    permission = ProposalToolPermission.READ_TAINTED_MEMORY

    def call(
        self,
        args: FeedbackQueryInput,
        context: ProposalToolContext,
    ) -> ProposalObservation:
        if not context.policy.allow_screening_runtime_raw_read:
            return self._error(
                context,
                failure_code=ProposalToolFailureCode.UNSUPPORTED,
                summary="Screening runtime raw read helper is disabled by policy.",
                repair_hint="Enable allow_screening_runtime_raw_read or use screening aggregates.",
            )
        safe_steps = [
            step
            for step in _filter_hypothesis_prompt_steps(list(context.step_history))
            if (not args.branch_id or step.branch_id == args.branch_id)
            and (not args.surface or step.hypothesis.change_locus == args.surface)
        ]
        rendered = _limit_text(
            _build_runtime_feedback(safe_steps, max_items=args.max_items),
            _COMPACT_FEEDBACK_TEXT_CHARS,
        )
        adapter_spec = _get_adapter_problem_spec(context.adapter)
        guidance = _limit_text(
            _build_runtime_failure_guidance(
                safe_steps,
                problem_spec=context.problem_spec,
                adapter_spec=adapter_spec,
                max_items=args.max_items,
                forced_surface=str(context.forced_surface or "").strip() or None,
            ),
            _COMPACT_FEEDBACK_TEXT_CHARS,
        )
        payload = {
            "branch_id": args.branch_id,
            "surface": args.surface,
            "query_scope": {
                "campaign_id": context.campaign_id,
                "branch_filter_applied": bool(args.branch_id),
                "surface_filter_applied": bool(args.surface),
                "recent_first": True,
            },
            "runtime_feedback": rendered,
            "runtime_failure_guidance": guidance,
            "screening_runtime_attribution": [
                attribution
                for attribution in (
                    _surface_runtime_attribution_payload(step)
                    for step in reversed(safe_steps)
                    if (
                        step.protocol_result is not None
                        and step.protocol_result.stage == ExperimentStage.SCREENING
                    )
                )
                if attribution
            ][: args.max_items],
            "research_diagnosis": _research_diagnosis_payload(
                safe_steps,
                max_items=args.max_items,
                problem_spec=context.problem_spec,
            ),
            "screening_only": True,
            "metrics_file_refs_exposed": False,
        }
        payload = _bound_compact_feedback_payload(payload)
        return self._observation(
            context,
            observation_type="runtime_feedback",
            summary=(
                "Returned screening-derived runtime feedback."
                if rendered
                else "No safe screening-derived runtime feedback is available."
            ),
            structured_payload=payload,
            exposure_level=ProposalExposureLevel.SCREENING_DETAIL,
        )

def _surface_runtime_attribution_payload(step: StepRecord) -> dict[str, Any]:
    protocol = step.protocol_result
    if protocol is None:
        return {}
    summary = protocol.candidate_surface_runtime_summary or {}
    if not isinstance(summary, Mapping):
        return {}
    fields = summary.get("fields")
    if not isinstance(fields, Mapping):
        return {}
    candidates: list[tuple[tuple[int, int, str], dict[str, Any]]] = []
    for field_name, field_summary in fields.items():
        if not isinstance(field_name, str) or not isinstance(field_summary, Mapping):
            continue
        if not _runtime_attribution_field_is_interesting(field_name, field_summary):
            continue
        candidates.append(
            (
                _runtime_attribution_sort_key(field_name, field_summary),
                {
                    "field": field_name,
                    "present": field_summary.get("present"),
                    "missing": field_summary.get("missing"),
                    "empty": field_summary.get("empty"),
                    "failed": field_summary.get("failed"),
                    "numeric_summary": _strip_forbidden_value(
                        field_summary.get("numeric_summary") or {}
                    ),
                    "values": _compact_runtime_attribution_values(
                        field_summary.get("values")
                    ),
                },
            )
        )
    candidates.sort(key=lambda item: item[0])
    highlights = [payload for _sort_key, payload in candidates[:12]]
    if not highlights:
        return {}
    return {
        "round_num": step.round_num,
        "branch_id": step.branch_id,
        "surface": step.hypothesis.change_locus,
        "target_file": step.hypothesis.target_file,
        "gate_outcome": protocol.gate_outcome,
        "reason_codes": list(protocol.reason_codes),
        "stats": _eval_stats_payload(protocol.stats),
        "runtime_field_highlights": highlights,
    }

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

def _runtime_highlight_is_all_zero_numeric(highlight: Mapping[str, Any]) -> bool:
    numeric = highlight.get("numeric_summary")
    if not isinstance(numeric, Mapping):
        return False
    summaries = _runtime_numeric_leaf_summaries(numeric)
    if not summaries:
        return False
    observed = False
    for summary in summaries:
        try:
            count = int(summary.get("observed_count") or 0)
        except (TypeError, ValueError):
            count = 0
        if count <= 0:
            continue
        observed = True
        if _safe_positive_int(summary.get("nonzero_count")):
            return False
        try:
            if abs(float(summary.get("weighted_sum") or 0.0)) > 1e-12:
                return False
        except (TypeError, ValueError):
            return False
    return observed

def _runtime_numeric_leaf_summaries(
    numeric: Mapping[str, Any],
) -> list[Mapping[str, Any]]:
    summaries: list[Mapping[str, Any]] = []
    stack: list[Any] = [numeric]
    while stack:
        value = stack.pop()
        if not isinstance(value, Mapping):
            continue
        if "observed_count" in value and (
            "nonzero_count" in value or "weighted_sum" in value
        ):
            summaries.append(value)
            continue
        stack.extend(value.values())
    return summaries

def _runtime_highlight_has_nonzero_numeric(highlight: Mapping[str, Any]) -> bool:
    numeric = highlight.get("numeric_summary")
    if not isinstance(numeric, Mapping):
        return False
    stack: list[Any] = [numeric]
    while stack:
        value = stack.pop()
        if isinstance(value, Mapping):
            for key, nested in value.items():
                if key in {"nonzero_count", "positive_count"} and _safe_positive_int(
                    nested
                ):
                    return True
                if key == "weighted_sum":
                    try:
                        if abs(float(nested or 0.0)) > 1e-12:
                            return True
                    except (TypeError, ValueError):
                        pass
                stack.append(nested)
        elif isinstance(value, list):
            stack.extend(value)
    return False

def _runtime_attribution_sort_key(
    field_name: str,
    field_summary: Mapping[str, Any],
) -> tuple[int, int, str]:
    has_issue = any(
        _safe_positive_int(field_summary.get(key))
        for key in ("missing", "empty", "failed")
    )
    priority = len(_RUNTIME_ATTRIBUTION_PRIORITY_SUFFIXES)
    for index, suffix in enumerate(_RUNTIME_ATTRIBUTION_PRIORITY_SUFFIXES):
        if field_name.endswith(suffix):
            priority = index
            break
    return (0 if has_issue else 1, priority, field_name)

def _runtime_attribution_field_is_interesting(
    field_name: str,
    field_summary: Mapping[str, Any],
) -> bool:
    for key in ("missing", "empty", "failed"):
        if _safe_positive_int(field_summary.get(key)):
            return True
    return any(field_name.endswith(suffix) for suffix in _RUNTIME_ATTRIBUTION_SUFFIXES)

def _safe_positive_int(value: Any) -> bool:
    try:
        return int(value or 0) > 0
    except (TypeError, ValueError):
        return False

def _compact_runtime_attribution_values(values: Any) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        return []
    compact: list[dict[str, Any]] = []
    for item in values[:3]:
        if not isinstance(item, Mapping):
            continue
        compact.append(
            _drop_empty_items(
                {
                    "value": _limit_text(str(item.get("value", "")), 240),
                    "count": item.get("count"),
                }
            )
        )
    return compact

def _screening_step_payload(step: StepRecord) -> dict[str, Any]:
    protocol = step.protocol_result
    assert protocol is not None
    stats = protocol.stats
    return {
        "round_num": step.round_num,
        "branch_id": step.branch_id,
        "surface": step.hypothesis.change_locus,
        "action": step.hypothesis.action,
        "target_file": step.hypothesis.target_file,
        "gate_outcome": protocol.gate_outcome,
        "reason_codes": list(protocol.reason_codes),
        "stats": _eval_stats_payload(stats),
        "candidate_runtime_failure_categories": dict(
            protocol.candidate_runtime_failure_categories or {}
        ),
        "candidate_first_runtime_failure": _strip_forbidden_value(
            protocol.candidate_first_runtime_failure or {}
        ),
        "candidate_operator_attempts": protocol.candidate_operator_attempts,
        "candidate_operator_accepted": protocol.candidate_operator_accepted,
        "candidate_operator_errors": protocol.candidate_operator_errors,
        "candidate_operator_invalid_outputs": (
            protocol.candidate_operator_invalid_outputs
        ),
        "candidate_policy_errors": protocol.candidate_policy_errors,
        "candidate_construction_errors": protocol.candidate_construction_errors,
        "candidate_portfolio_errors": protocol.candidate_portfolio_errors,
        "candidate_runtime_stop_reasons": dict(
            protocol.candidate_runtime_stop_reasons or {}
        ),
        "candidate_surface_runtime_summary": _strip_forbidden_value(
            protocol.candidate_surface_runtime_summary or {}
        ),
        "candidate_surface_runtime_attribution": _surface_runtime_attribution_payload(
            step
        ),
        "pattern_summary": _model_payload(protocol.pattern_summary),
        "case_feedback": [
            _model_payload(feedback) for feedback in (protocol.case_feedback or ())[:6]
        ],
        "metrics_file_ref_exposed": False,
    }

def _holdout_step_payload(
    step: StepRecord,
    exposure: HoldoutExposure,
    level: ProposalExposureLevel,
) -> dict[str, Any]:
    protocol = step.protocol_result
    assert protocol is not None
    payload: dict[str, Any] = {
        "round_num": step.round_num,
        "branch_id": step.branch_id,
        "surface": step.hypothesis.change_locus,
        "stage": _stage_value(protocol.stage),
        "exposure_level": level.value,
        "gate_outcome": protocol.gate_outcome,
        "reason_codes": list(protocol.reason_codes),
        "candidate_runtime_failure_categories": dict(
            protocol.candidate_runtime_failure_categories or {}
        ),
        "candidate_first_runtime_failure": _strip_forbidden_value(
            protocol.candidate_first_runtime_failure or {}
        ),
        "candidate_operator_attempts": protocol.candidate_operator_attempts,
        "candidate_operator_accepted": protocol.candidate_operator_accepted,
        "candidate_operator_errors": protocol.candidate_operator_errors,
        "candidate_operator_invalid_outputs": (
            protocol.candidate_operator_invalid_outputs
        ),
        "candidate_policy_errors": protocol.candidate_policy_errors,
        "candidate_construction_errors": protocol.candidate_construction_errors,
        "candidate_portfolio_errors": protocol.candidate_portfolio_errors,
        "candidate_runtime_stop_reasons": dict(
            protocol.candidate_runtime_stop_reasons or {}
        ),
        "candidate_surface_runtime_summary": _strip_forbidden_value(
            protocol.candidate_surface_runtime_summary or {}
        ),
        "metrics_file_ref_exposed": False,
        "case_ids_exposed": False,
        "pair_feedback_exposed": False,
    }
    if exposure == HoldoutExposure.AGGREGATE:
        payload["stats"] = _eval_stats_payload(protocol.stats)
    return payload

def _eval_stats_payload(stats: Any) -> dict[str, Any]:
    allowed = {
        "n_cases",
        "wins",
        "losses",
        "ties",
        "win_rate",
        "median_delta",
        "ci_low",
        "ci_high",
        "statistical_status",
        "statistical_metric",
        "runtime_ratio_median",
        "runtime_delta_median_ms",
        "runtime_regression_rate",
        "runtime_pairs",
        "total_pairs",
        "attempted_pairs",
        "valid_pairs",
        "failed_pairs",
        "candidate_failed_pairs",
        "champion_failed_pairs",
    }
    return {name: _attr(stats, name) for name in allowed if hasattr(stats, name)}

def _bound_compact_feedback_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    estimated = _json_size(payload)
    if estimated <= _COMPACT_FEEDBACK_PAYLOAD_CHARS:
        bounded = dict(payload)
        bounded.setdefault("payload_truncated", False)
        return bounded
    compact = _compact_feedback_value(payload)
    compact_estimated = _json_size(compact)
    if (
        isinstance(compact, Mapping)
        and compact_estimated <= _COMPACT_FEEDBACK_PAYLOAD_CHARS
    ):
        bounded = dict(compact)
        bounded["payload_truncated"] = True
        bounded["original_estimated_chars"] = estimated
        return bounded
    return {
        "payload_truncated": True,
        "original_estimated_chars": estimated,
        "compacted_estimated_chars": compact_estimated,
        "available_keys": sorted(str(key) for key in payload.keys()),
        "summary": "Compact feedback payload exceeded budget and was summarized.",
    }

def _compact_feedback_value(value: Any, *, depth: int = 0) -> Any:
    if isinstance(value, Mapping):
        compact: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= _COMPACT_FEEDBACK_MAP_ITEMS:
                compact["omitted_mapping_items"] = len(value) - index
                break
            compact[str(key)] = _compact_feedback_value(item, depth=depth + 1)
        return compact
    if isinstance(value, tuple):
        return _compact_feedback_value(list(value), depth=depth)
    if isinstance(value, list):
        compact_list = [
            _compact_feedback_value(item, depth=depth + 1)
            for item in value[:_COMPACT_FEEDBACK_LIST_ITEMS]
        ]
        if len(value) > _COMPACT_FEEDBACK_LIST_ITEMS:
            compact_list.append(
                {"omitted_items": len(value) - _COMPACT_FEEDBACK_LIST_ITEMS}
            )
        return compact_list
    if isinstance(value, str):
        limit = max(
            200,
            _COMPACT_FEEDBACK_STRING_CHARS // max(1, min(depth, 4)),
        )
        return _limit_text(value, limit)
    return _strip_forbidden_value(value)

def _sanitize_memory_text(text: str) -> str:
    if not text:
        return ""
    forbidden_terms = (
        "champion_evolution",
        "champion evolution",
        "promotion",
        "promoted",
        "promote",
        "validation",
        "frozen",
        "holdout",
        "raw_metrics",
        "raw metrics",
    )
    safe_lines = []
    for line in text.splitlines():
        lowered = line.lower()
        if any(term in lowered for term in forbidden_terms):
            continue
        safe_lines.append(line)
    return "\n".join(safe_lines)

__all__ = [
    "FeedbackQueryHoldoutSummaryTool",
    "FeedbackQueryRuntimeTool",
    "FeedbackQueryScreeningTool",
    "MemoryQueryTool",
    "_COMPACT_FEEDBACK_LIST_ITEMS",
    "_COMPACT_FEEDBACK_MAP_ITEMS",
    "_COMPACT_FEEDBACK_PAYLOAD_CHARS",
    "_COMPACT_FEEDBACK_STRING_CHARS",
    "_COMPACT_FEEDBACK_TEXT_CHARS",
    "_RUNTIME_ATTRIBUTION_PRIORITY_SUFFIXES",
    "_RUNTIME_ATTRIBUTION_SUFFIXES",
    "_bound_compact_feedback_payload",
    "_compact_feedback_value",
    "_compact_runtime_attribution_values",
    "_declared_mechanism_surface_names",
    "_declared_solver_design_surface_names",
    "_diagnostic_surface_priorities",
    "_eval_stats_payload",
    "_holdout_step_payload",
    "_mechanism_surface_names_from_surfaces",
    "_pre_protocol_failed_solver_design_surface_names",
    "_research_diagnosis_payload",
    "_runtime_attribution_field_is_interesting",
    "_runtime_attribution_sort_key",
    "_runtime_highlight_has_nonzero_numeric",
    "_runtime_highlight_is_all_zero_numeric",
    "_runtime_numeric_leaf_summaries",
    "_safe_positive_int",
    "_sanitize_memory_text",
    "_screening_failed_solver_design_surface_names",
    "_screening_step_payload",
    "_surface_runtime_attribution_payload",
]
