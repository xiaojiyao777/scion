"""AgenticSessionPreviewTool mixin."""
from __future__ import annotations

from scion.proposal.agentic_session_common import *


class AgenticSessionPreviewToolMixin:
    def _run_hypothesis_preview_tools(
            self,
            context: ProposalToolContext,
            hypothesis: HypothesisProposal,
            state: AgenticProposalSessionState,
        ) -> list[ProposalObservation]:
            hypothesis_payload = _proposal_payload(hypothesis)
            calls: tuple[tuple[str, Mapping[str, Any]], ...] = (
                ("proposal.schema_preview", {"hypothesis": hypothesis_payload}),
                (
                    "proposal.target_permission_preview",
                    {
                        "change_locus": hypothesis.change_locus,
                        "action": hypothesis.action,
                        "target_file": hypothesis.target_file,
                    },
                ),
            )
            observations: list[ProposalObservation] = []
            for name, args in calls:
                if self._session_timeout_reached(state):
                    self._record_loop_stop(state, "session_timeout")
                    break
                observations.append(
                    self._call_tool(
                        context,
                        state,
                        AgenticProposalPhase.SELF_CHECK,
                        name,
                        args,
                        selection_source="fallback_selected",
                    )
                )
            return observations

    def _run_solver_design_grounding_tools(
            self,
            context: ProposalToolContext,
            state: AgenticProposalSessionState,
            prior_observations: list[ProposalObservation],
            *,
            selection_source: str,
            hypothesis: HypothesisProposal | None = None,
        ) -> list[ProposalObservation]:
            return _run_solver_design_grounding_context_tools(
                self,
                context,
                state,
                prior_observations,
                selection_source=selection_source,
                hypothesis=hypothesis,
            )

    def _run_selected_surface_observation_tool(
            self,
            context: ProposalToolContext,
            hypothesis: HypothesisProposal,
            state: AgenticProposalSessionState,
            observations: list[ProposalObservation],
        ) -> list[ProposalObservation]:
            return _run_selected_surface_context_tool(
                self,
                context,
                hypothesis,
                state,
                observations,
            )

    def _run_contract_preview_tool(
            self,
            context: ProposalToolContext,
            hypothesis: HypothesisProposal,
            patch: PatchProposal,
            state: AgenticProposalSessionState,
        ) -> ProposalObservation:
            return self._call_tool(
                context,
                state,
                AgenticProposalPhase.SELF_CHECK,
                "proposal.contract_preview",
                {
                    "hypothesis": _proposal_payload(hypothesis),
                    "patch": _patch_payload_for_preview(patch),
                },
                selection_source="fallback_selected",
            )

    def _run_algorithm_smoke_tool(
            self,
            context: ProposalToolContext,
            hypothesis: HypothesisProposal,
            patch: PatchProposal,
            state: AgenticProposalSessionState,
        ) -> ProposalObservation:
            return self._call_tool(
                context,
                state,
                AgenticProposalPhase.SELF_CHECK,
                "proposal.algorithm_smoke",
                {
                    "hypothesis": _proposal_payload(hypothesis),
                    "patch": _patch_payload_for_preview(patch),
                },
                selection_source="fallback_selected",
            )
