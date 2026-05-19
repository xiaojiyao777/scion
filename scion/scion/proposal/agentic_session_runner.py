
"""Public APS session class assembled from focused phase mixins."""
from __future__ import annotations

from scion.proposal.agentic_session_common import *
from scion.proposal.agentic_session_budget_runtime import AgenticSessionBudgetRuntimeMixin
from scion.proposal.agentic_session_code_guidance import AgenticSessionCodeGuidanceMixin
from scion.proposal.agentic_session_code_tools import AgenticSessionCodeToolsMixin
from scion.proposal.agentic_session_diagnosis import AgenticSessionDiagnosisMixin
from scion.proposal.agentic_session_hypothesis import AgenticSessionHypothesisMixin
from scion.proposal.agentic_session_orchestration import AgenticSessionOrchestrationMixin
from scion.proposal.agentic_session_outputs import AgenticSessionOutputMixin
from scion.proposal.agentic_session_patch_flow import AgenticSessionPatchFlowMixin
from scion.proposal.agentic_session_planner_loop import AgenticSessionPlannerLoopMixin
from scion.proposal.agentic_session_preview_tools import AgenticSessionPreviewToolMixin
from scion.proposal.agentic_session_repair import AgenticSessionRepairMixin
from scion.proposal.agentic_session_tool_call import AgenticSessionToolCallMixin


class AgenticProposalSession(
    AgenticSessionOrchestrationMixin,
    AgenticSessionPatchFlowMixin,
    AgenticSessionHypothesisMixin,
    AgenticSessionDiagnosisMixin,
    AgenticSessionPlannerLoopMixin,
    AgenticSessionCodeToolsMixin,
    AgenticSessionCodeGuidanceMixin,
    AgenticSessionPreviewToolMixin,
    AgenticSessionRepairMixin,
    AgenticSessionToolCallMixin,
    AgenticSessionBudgetRuntimeMixin,
    AgenticSessionOutputMixin,
):
    """Bounded proposal session inside Scion's tainted Creative Layer.

    The class keeps the historic ``scion.proposal.agentic_session`` API while
    delegating phase responsibilities to small mixins. It still returns only the
    proposal shapes understood by Contract, Verification, Protocol, and Decision.
    """

    _SESSION_ERROR_TYPES = (
        LLMRetryExhaustedError,
        LLMFormatError,
        LLMTimeoutError,
        ProposalValidationError,
    )

    def __init__(
        self,
        creative: CreativeProposalLike | None = None,
        *,
        artifact_store: AgenticSessionArtifactStore | None = None,
        tool_registry: ProposalToolRegistry | None = None,
        tool_loop_config: AgenticToolLoopConfig | None = None,
        injected_output: (
            AgenticProposalOutput
            | Callable[[AgenticProposalRequest], AgenticProposalOutput]
            | None
        ) = None,
    ) -> None:
        self._creative = creative
        self._artifact_store = artifact_store
        self.tool_registry = tool_registry
        self._tool_loop_config = tool_loop_config or AgenticToolLoopConfig()
        self._injected_output = injected_output

    def idempotency_key_for_request(self, request: AgenticProposalRequest) -> str:
        return compute_agentic_idempotency_key(request, self._tool_loop_config)

    def _self_check_from_authoritative_previews(
        self,
        observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
        state: AgenticProposalSessionState,
    ) -> AgenticSelfCheck:
        return _self_check_from_previews(
            _authoritative_preview_observations(observations, state)
        )

    def _latest_authoritative_preview_failure_detail(
        self,
        observations: tuple[ProposalObservation, ...] | list[ProposalObservation],
        state: AgenticProposalSessionState,
    ) -> str | None:
        return _latest_preview_failure_detail(
            _authoritative_preview_observations(observations, state)
        )

    def run(self, request: AgenticProposalRequest) -> AgenticProposalOutput:
        session_id, state, evidence, observations = self._start_run_state(request)
        tool_context, output = self._prepare_tool_context_or_output(
            request=request,
            session_id=session_id,
            state=state,
            evidence=evidence,
            observations=observations,
        )
        if output is not None:
            return output

        output = self._preflight_output_or_none(
            request=request,
            session_id=session_id,
            state=state,
        )
        if output is not None:
            return output

        hypothesis, output = self._prepare_hypothesis_or_output(
            request=request,
            session_id=session_id,
            state=state,
            tool_context=tool_context,
            observations=observations,
            evidence=evidence,
        )
        if output is not None:
            return output
        assert hypothesis is not None

        patch, code_context, repair_attempts, output = self._build_initial_patch_or_output(
            request=request,
            session_id=session_id,
            state=state,
            tool_context=tool_context,
            hypothesis=hypothesis,
            observations=observations,
            evidence=evidence,
        )
        if output is not None:
            return output
        assert patch is not None and code_context is not None

        patch, repair_attempts, output = self._validate_patch_or_output(
            request=request,
            session_id=session_id,
            state=state,
            hypothesis=hypothesis,
            patch=patch,
            code_context=code_context,
            observations=observations,
            evidence=evidence,
            code_repair_attempts_used=repair_attempts,
        )
        if output is not None:
            return output
        assert patch is not None

        if tool_context is not None:
            patch, repair_attempts, output = self._run_patch_preview_repair_loop(
                request=request,
                session_id=session_id,
                state=state,
                tool_context=tool_context,
                hypothesis=hypothesis,
                patch=patch,
                code_context=code_context,
                observations=observations,
                evidence=evidence,
                code_repair_attempts_used=repair_attempts,
            )
            if output is not None:
                return output
            assert patch is not None

        return self._finalize_patch_output(
            request=request,
            session_id=session_id,
            state=state,
            tool_context=tool_context,
            hypothesis=hypothesis,
            patch=patch,
            observations=observations,
            evidence=evidence,
        )
