"""memory.query proposal tool."""

from __future__ import annotations

from scion.proposal.tools.base import _BaseReadOnlyTool
from scion.proposal.tools.feedback.compaction import _sanitize_memory_text
from scion.proposal.tools.models import (
    MemoryQueryInput,
    ProposalExposureLevel,
    ProposalObservation,
    ProposalToolContext,
    ProposalToolFailureCode,
    ProposalToolPermission,
)
from scion.proposal.tools.utils import _limit_text


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

__all__ = [
    "MemoryQueryTool",
]
