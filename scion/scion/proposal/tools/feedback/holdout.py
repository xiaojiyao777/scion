"""feedback.query_holdout_summary proposal tool."""

from __future__ import annotations

from scion.core.models import ExperimentStage
from scion.proposal.tools.base import _BaseReadOnlyTool
from scion.proposal.tools.feedback.rows import _holdout_step_payload
from scion.proposal.tools.models import (
    FeedbackQueryInput,
    HoldoutExposure,
    ProposalExposureLevel,
    ProposalObservation,
    ProposalToolContext,
    ProposalToolPermission,
)
from scion.proposal.tools.utils import _stage_value


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

__all__ = [
    "FeedbackQueryHoldoutSummaryTool",
]
