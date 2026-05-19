"""Agentic proposal request and tool-context assembly."""
from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping

from scion.core.models import Branch, ChampionState, HypothesisProposal
from scion.proposal.agentic_session import (
    AgenticProposalRequest,
    AgenticProposalSession,
    AgenticToolLoopConfig,
    FileAgenticSessionArtifactStore,
)
from scion.proposal.tools import (
    ContextExposurePolicy,
    ProposalToolContext,
    ProposalToolRegistry,
)

from .boundaries import _declared_solver_design_surface_names
from .protocols import AgenticProposalSessionLike
from .utils import _runtime_attr


class AgenticRequestMixin:
    @property
    def _agentic_enabled(self) -> bool:
        return self.use_agentic_proposal or self.agentic_session is not None

    def _get_agentic_session(self) -> AgenticProposalSessionLike:
        if self.agentic_session is not None:
            return self.agentic_session
        artifact_store = (
            FileAgenticSessionArtifactStore(self.agentic_artifact_dir)
            if self.agentic_artifact_dir
            else None
        )
        self.agentic_session = AgenticProposalSession(
            self.creative,
            artifact_store=artifact_store,
            tool_loop_config=self._agentic_tool_loop_config(),
            tool_registry=ProposalToolRegistry.default_read_only(),
        )
        return self.agentic_session

    def _agentic_tool_loop_config(self) -> AgenticToolLoopConfig:
        if self.agentic_session_timeout_sec is None:
            return AgenticToolLoopConfig()
        return AgenticToolLoopConfig(
            max_wall_time_sec=float(self.agentic_session_timeout_sec)
        )

    def _build_agentic_request(
        self,
        *,
        branch: Branch,
        champion: ChampionState,
        hypothesis_context: dict[str, Any] | None,
        prior_failure: str | None = None,
        approved_hypothesis: HypothesisProposal | None = None,
        resume_context: Mapping[str, Any] | None = None,
    ) -> AgenticProposalRequest:
        def build_code_context(
            hypothesis: HypothesisProposal,
        ) -> Mapping[str, Any]:
            if approved_hypothesis is None:
                raise PermissionError(
                    "agentic code context requires a ContractGate-approved "
                    "hypothesis"
                )
            if hypothesis != approved_hypothesis:
                raise PermissionError(
                    "agentic code context hypothesis does not match the "
                    "approved hypothesis"
                )
            return self.problem_runtime.build_code_context(
                branch=branch,
                hypothesis=hypothesis,
                champion=champion,
                prior_failure=prior_failure,
                branch_workspace=self.branch_workspaces.get(branch.branch_id),
            )

        return AgenticProposalRequest(
            campaign_id=self.campaign_id,
            branch=branch,
            champion=champion,
            hypothesis_context=hypothesis_context,
            build_code_context=build_code_context,
            problem_id=self.problem_id,
            problem_spec_hash=self.problem_spec_hash,
            prior_failure=prior_failure,
            approved_hypothesis=approved_hypothesis,
            resume_context=resume_context,
            tool_context=self._build_agentic_tool_context(
                branch=branch,
                champion=champion,
                hypothesis_context=hypothesis_context,
            ),
        )

    def _build_agentic_tool_context(
        self,
        *,
        branch: Branch,
        champion: ChampionState,
        hypothesis_context: Mapping[str, Any] | None,
    ) -> ProposalToolContext:
        problem_spec = _runtime_attr(self.problem_runtime, "spec")
        if problem_spec is None:
            problem_spec = _runtime_attr(self.problem_runtime, "_spec")
        if problem_spec is None and hypothesis_context is not None:
            problem_spec = hypothesis_context.get("problem_spec")

        adapter = _runtime_attr(self.problem_runtime, "adapter")
        if adapter is None:
            adapter = _runtime_attr(self.problem_runtime, "_adapter")

        forced_surface = (
            str((hypothesis_context or {}).get("forced_surface") or "").strip()
            or self.persistent_forced_locus
        )
        forced_action = (
            str((hypothesis_context or {}).get("forced_action") or "").strip()
            or (self.forced_surface_action if forced_surface else None)
        )
        forced_target_file = (
            str((hypothesis_context or {}).get("forced_target_file") or "").strip()
            or (self.forced_surface_target_file if forced_surface else None)
        )

        active_boundary = _declared_solver_design_surface_names(problem_spec)
        if not active_boundary and adapter is not None:
            adapter_spec = _runtime_attr(adapter, "spec")
            if adapter_spec is None:
                adapter_spec = _runtime_attr(adapter, "_spec")
            active_boundary = _declared_solver_design_surface_names(adapter_spec)

        return ProposalToolContext(
            session_id="pending",
            campaign_id=self.campaign_id,
            branch=branch,
            champion=champion,
            problem_spec=problem_spec,
            split_manifest=self.split_manifest,
            seed_ledger=self.seed_ledger,
            adapter=adapter,
            step_history=tuple(self.step_history),
            search_memory=self.search_memory,
            research_log=self.research_log,
            policy=ContextExposurePolicy(allow_contract_preview=True),
            problem_id=self.problem_id,
            problem_spec_hash=self.problem_spec_hash,
            forced_surface=forced_surface or None,
            forced_action=forced_action or None,
            forced_target_file=forced_target_file or None,
            active_problem_boundary_surfaces=(
                ()
                if forced_surface
                else tuple(active_boundary)
            ),
            branch_workspace=self.branch_workspaces.get(branch.branch_id),
        )
