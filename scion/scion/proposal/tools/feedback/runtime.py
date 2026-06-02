"""feedback.query_runtime proposal tool."""

from __future__ import annotations

from scion.core.models import ExperimentStage
from scion.proposal.context_manager import (
    _build_runtime_feedback,
    _build_runtime_failure_guidance,
    _filter_hypothesis_prompt_steps,
    _get_adapter_problem_spec,
)
from scion.proposal.tools.base import _BaseReadOnlyTool
from scion.proposal.tools.feedback.attribution import _surface_runtime_attribution_payload
from scion.proposal.tools.feedback.compaction import _bound_compact_feedback_payload
from scion.proposal.tools.feedback.constants import _COMPACT_FEEDBACK_TEXT_CHARS
from scion.proposal.tools.feedback.diagnosis import _research_diagnosis_payload
from scion.proposal.tools.feedback.scope import (
    _feedback_boundary_scope,
    _feedback_payload_provenance,
    _feedback_step_provenance,
    _with_feedback_provenance,
)
from scion.proposal.tools.models import (
    FeedbackQueryInput,
    ProposalExposureLevel,
    ProposalObservation,
    ProposalToolContext,
    ProposalToolFailureCode,
    ProposalToolPermission,
)
from scion.proposal.tools.utils import _limit_text


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
            if not args.branch_id or step.branch_id == args.branch_id
        ]
        feedback_scope = _feedback_boundary_scope(
            safe_steps,
            context=context,
            requested_surface=args.surface,
        )
        active_steps = [
            step
            for step in feedback_scope.active_steps
            if not args.surface or step.hypothesis.change_locus == args.surface
        ]
        inactive_reference_steps = [
            step
            for step in feedback_scope.inactive_reference_steps
            if not args.surface or step.hypothesis.change_locus == args.surface
        ]
        rendered = _limit_text(
            _build_runtime_feedback(active_steps, max_items=args.max_items),
            _COMPACT_FEEDBACK_TEXT_CHARS,
        )
        inactive_rendered = _limit_text(
            _build_runtime_feedback(
                inactive_reference_steps,
                max_items=args.max_items,
            ),
            _COMPACT_FEEDBACK_TEXT_CHARS,
        )
        adapter_spec = _get_adapter_problem_spec(context.adapter)
        guidance = _limit_text(
            _build_runtime_failure_guidance(
                active_steps,
                problem_spec=context.problem_spec,
                adapter_spec=adapter_spec,
                max_items=args.max_items,
                forced_surface=str(context.forced_surface or "").strip() or None,
            ),
            _COMPACT_FEEDBACK_TEXT_CHARS,
        )
        active_attribution = [
            _with_feedback_provenance(
                attribution,
                _feedback_step_provenance(
                    step,
                    boundary_surfaces=feedback_scope.boundary_surfaces,
                    role="active_boundary_evidence"
                    if feedback_scope.enforced
                    else "screening_evidence",
                ),
            )
            for step in reversed(active_steps)
            for attribution in (_surface_runtime_attribution_payload(step),)
            if (
                attribution
                and step.protocol_result is not None
                and step.protocol_result.stage == ExperimentStage.SCREENING
            )
        ][: args.max_items]
        inactive_attribution = [
            _with_feedback_provenance(
                attribution,
                _feedback_step_provenance(
                    step,
                    boundary_surfaces=feedback_scope.boundary_surfaces,
                    role="inactive_reference",
                ),
            )
            for step in reversed(inactive_reference_steps)
            for attribution in (_surface_runtime_attribution_payload(step),)
            if (
                attribution
                and step.protocol_result is not None
                and step.protocol_result.stage == ExperimentStage.SCREENING
            )
        ][: args.max_items]
        runtime_status = _runtime_observation_status(
            context=context,
            args=args,
            active_steps=active_steps,
            inactive_reference_steps=inactive_reference_steps,
            runtime_feedback=rendered,
            runtime_failure_guidance=guidance,
            active_attribution=active_attribution,
            inactive_attribution=inactive_attribution,
        )
        payload = {
            "branch_id": args.branch_id,
            "surface": args.surface,
            "runtime_observation_status": runtime_status,
            "provenance": _feedback_payload_provenance(
                source="screening_runtime_history",
                feedback_scope=feedback_scope,
            ),
            "query_scope": {
                "campaign_id": context.campaign_id,
                "branch_filter_applied": bool(args.branch_id),
                "surface_filter_applied": bool(args.surface),
                "recent_first": True,
                "active_boundary_filter_applied": feedback_scope.enforced,
            },
            "active_boundary_filter": feedback_scope.payload(),
            "runtime_feedback": rendered,
            "runtime_failure_guidance": guidance,
            "screening_runtime_attribution": active_attribution,
            "inactive_reference_runtime_feedback": inactive_rendered,
            "inactive_reference_runtime_attribution": inactive_attribution,
            "research_diagnosis": _research_diagnosis_payload(
                active_steps,
                max_items=args.max_items,
                problem_spec=context.problem_spec,
            ),
            "excluded_inactive_reference_count": feedback_scope.excluded_count,
            "matched_inactive_reference_count": len(inactive_reference_steps),
            "screening_only": True,
            "metrics_file_refs_exposed": False,
        }
        payload = _bound_compact_feedback_payload(payload)
        payload.setdefault("runtime_observation_status", runtime_status)
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


def _runtime_observation_status(
    *,
    context: ProposalToolContext,
    args: FeedbackQueryInput,
    active_steps: list,
    inactive_reference_steps: list,
    runtime_feedback: str,
    runtime_failure_guidance: str,
    active_attribution: list,
    inactive_attribution: list,
) -> dict:
    low_confidence_exclusions = []
    for step in active_steps:
        protocol = getattr(step, "protocol_result", None)
        if protocol is None:
            continue
        stats = getattr(protocol, "stats", None)
        runtime_pairs = int(getattr(stats, "runtime_pairs", 0) or 0)
        confidence = str(getattr(protocol, "runtime_confidence", "") or "").strip()
        cached_pairs = int(getattr(protocol, "champion_cached_runtime_pairs", 0) or 0)
        if runtime_pairs <= 0 and confidence and confidence != "high":
            low_confidence_exclusions.append(
                {
                    "round_num": getattr(step, "round_num", None),
                    "runtime_confidence": confidence,
                    "champion_cached_runtime_pairs": cached_pairs,
                    "reason": confidence,
                }
            )
    usable = bool(
        runtime_feedback.strip()
        or runtime_failure_guidance.strip()
        or active_attribution
        or inactive_attribution
    )
    return {
        "schema_version": "runtime_feedback_observation_status.v1",
        "canonical_scope": {
            "campaign_id": context.campaign_id,
            "branch_id": str(args.branch_id or "").strip(),
            "surface": str(args.surface or context.forced_surface or "").strip(),
        },
        "usable": usable,
        "active_step_count": len(active_steps),
        "inactive_reference_step_count": len(inactive_reference_steps),
        "active_runtime_attribution_count": len(active_attribution),
        "inactive_runtime_attribution_count": len(inactive_attribution),
        "runtime_feedback_available": bool(runtime_feedback.strip()),
        "runtime_failure_guidance_available": bool(runtime_failure_guidance.strip()),
        "aggregate_runtime_exclusion_reasons": low_confidence_exclusions[:4],
    }

__all__ = [
    "FeedbackQueryRuntimeTool",
]
