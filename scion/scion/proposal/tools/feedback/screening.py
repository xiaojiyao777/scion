"""feedback.query_screening proposal tool."""

from __future__ import annotations

from scion.core.models import ExperimentStage
from scion.proposal.context_manager import _filter_hypothesis_prompt_steps
from scion.proposal.tools.base import _BaseReadOnlyTool
from scion.proposal.tools.feedback.compaction import _bound_compact_feedback_payload
from scion.proposal.tools.feedback.rows import _screening_step_payload
from scion.proposal.tools.feedback.scope import (
    _feedback_boundary_scope,
    _feedback_payload_provenance,
    _feedback_step_provenance,
)
from scion.proposal.tools.models import (
    FeedbackQueryInput,
    ProposalExposureLevel,
    ProposalObservation,
    ProposalToolContext,
    ProposalToolFailureCode,
    ProposalToolPermission,
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
        feedback_scope = _feedback_boundary_scope(
            safe_steps,
            context=context,
            requested_surface=args.surface,
        )
        available_screening_steps = [
            step
            for step in feedback_scope.active_steps
            if (
                step.protocol_result is not None
                and step.protocol_result.stage == ExperimentStage.SCREENING
            )
        ]
        inactive_reference_screening_steps = [
            step
            for step in feedback_scope.inactive_reference_steps
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
                rows.append(
                    _screening_step_payload(
                        step,
                        provenance=_feedback_step_provenance(
                            step,
                            boundary_surfaces=feedback_scope.boundary_surfaces,
                            role="active_boundary_evidence"
                            if feedback_scope.enforced
                            else "screening_evidence",
                        ),
                    )
                )
        inactive_reference_rows = []
        inactive_reference_count = 0
        for step in reversed(inactive_reference_screening_steps):
            protocol = step.protocol_result
            if protocol is None or protocol.stage != ExperimentStage.SCREENING:
                continue
            if args.branch_id and step.branch_id != args.branch_id:
                continue
            surface = step.hypothesis.change_locus
            if args.surface and surface != args.surface:
                continue
            inactive_reference_count += 1
            if len(inactive_reference_rows) < args.max_items:
                inactive_reference_rows.append(
                    _screening_step_payload(
                        step,
                        provenance=_feedback_step_provenance(
                            step,
                            boundary_surfaces=feedback_scope.boundary_surfaces,
                            role="inactive_reference",
                        ),
                    )
                )
        payload = {
            "branch_id": args.branch_id,
            "surface": args.surface,
            "provenance": _feedback_payload_provenance(
                source="screening_step_history",
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
            "available_screening_step_count": len(available_screening_steps),
            "matched_screening_step_count": matched_count,
            "excluded_inactive_reference_count": feedback_scope.excluded_count,
            "matched_inactive_reference_count": inactive_reference_count,
            "screening_steps": rows,
            "inactive_reference_steps": inactive_reference_rows,
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

__all__ = [
    "FeedbackQueryScreeningTool",
]
