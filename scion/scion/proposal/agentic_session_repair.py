"""AgenticSessionRepair mixin."""
from __future__ import annotations

from scion.proposal.agentic_session_common import *


class AgenticSessionRepairMixin:
    def _repair_patch_after_preview(
            self,
            *,
            request: AgenticProposalRequest,
            state: AgenticProposalSessionState,
            hypothesis: HypothesisProposal,
            patch: PatchProposal,
            code_context: Mapping[str, Any],
            observations: list[ProposalObservation],
            failed_preview: ProposalObservation,
            repair_attempt: int = 1,
        ) -> PatchProposal:
            repair_context = dict(code_context)
            if failed_preview.tool_name == "proposal.algorithm_smoke":
                detail = _algorithm_smoke_failure_detail([failed_preview])
                repair_context["prior_code_failure"] = (
                    detail
                    or "Algorithm smoke failed before official screening: "
                    f"{failed_preview.summary}"
                )
                feedback_kind = "algorithm-smoke"
            else:
                repair_context["prior_code_failure"] = (
                    "Contract preview failed before workspace materialization: "
                    f"{failed_preview.summary}"
                )
                feedback_kind = "Contract-preview"
            repair_context["previous_patch"] = _proposal_payload(patch)
            repair_context["agentic_preview_feedback"] = _observation_prompt_payload(
                failed_preview
            )
            research_diagnosis = _research_diagnosis_from_observations(observations)
            if research_diagnosis:
                repair_context["agentic_research_diagnosis"] = research_diagnosis
            prompt_observations = _code_prompt_observations(observations)
            if failed_preview not in prompt_observations:
                prompt_observations.append(failed_preview)
            repair_context["agentic_tool_observations"] = [
                _code_observation_prompt_payload(observation)
                for observation in prompt_observations
            ]
            state.note(
                AgenticProposalPhase.DRAFT_PATCH,
                f"Regenerating patch proposal with {feedback_kind} feedback.",
                metadata={
                    "selected_surface": hypothesis.change_locus,
                    "target_file": hypothesis.target_file,
                    "repair_attempt": repair_attempt,
                    "feedback_tool": failed_preview.tool_name,
                },
            )
            repair_context = _with_code_scope_control(
                repair_context,
                hypothesis,
                timeout_retry=False,
            )
            return self._generate_code_with_timeout_retry(
                state=state,
                hypothesis=hypothesis,
                code_context=repair_context,
                observations=observations,
            )

    def _repair_patch_after_code_self_check(
            self,
            *,
            request: AgenticProposalRequest,
            state: AgenticProposalSessionState,
            hypothesis: HypothesisProposal,
            code_context: Mapping[str, Any],
            observations: list[ProposalObservation],
            patch: PatchProposal,
            issue_detail: str,
            repair_attempt: int,
        ) -> PatchProposal:
            del request
            repair_context = dict(code_context)
            repair_context["prior_code_failure"] = issue_detail
            repair_context["previous_patch"] = _proposal_payload(patch)
            repair_context["agentic_code_self_check_feedback"] = {
                "passed": False,
                "issue": issue_detail,
                "file_path": patch.file_path,
                "action": patch.action,
                "test_hint": patch.test_hint,
            }
            research_diagnosis = _research_diagnosis_from_observations(observations)
            if research_diagnosis:
                repair_context["agentic_research_diagnosis"] = research_diagnosis
            repair_context["agentic_tool_observations"] = [
                _code_observation_prompt_payload(observation)
                for observation in _code_prompt_observations(observations)
            ]
            state.note(
                AgenticProposalPhase.DRAFT_PATCH,
                "Regenerating patch proposal after code self-check feedback.",
                metadata={
                    "selected_surface": hypothesis.change_locus,
                    "target_file": hypothesis.target_file,
                    "repair_attempt": repair_attempt,
                    "issue": issue_detail,
                },
            )
            repair_context = _with_code_scope_control(
                repair_context,
                hypothesis,
                timeout_retry=False,
            )
            return self._generate_code_with_timeout_retry(
                state=state,
                hypothesis=hypothesis,
                code_context=repair_context,
                observations=observations,
            )

    def _generate_code_with_timeout_retry(
            self,
            *,
            state: AgenticProposalSessionState,
            hypothesis: HypothesisProposal,
            code_context: Mapping[str, Any],
            observations: list[ProposalObservation],
        ) -> PatchProposal:
            assert self._creative is not None
            max_retries = max(
                0,
                int(self._tool_loop_config.max_code_generation_timeout_retries),
            )
            attempt_context: Mapping[str, Any] = code_context
            for attempt in range(max_retries + 1):
                try:
                    self._record_prompt_manifest(
                        state,
                        call_kind="code",
                        prompt_context=attempt_context,
                        observations=observations,
                    )
                    return self._creative.generate_code(attempt_context)
                except self._SESSION_ERROR_TYPES as exc:
                    category = _structured_output_failure_category(exc)
                    _record_failure_ledger_entry(
                        state,
                        phase=AgenticProposalPhase.DRAFT_PATCH,
                        category=category,
                        detail=str(exc),
                        source="code_generation_exception",
                        attempt=attempt + 1,
                    )
                    if (
                        attempt >= max_retries
                        or self._session_timeout_reached(state)
                        or not _is_code_generation_timeout(exc)
                    ):
                        raise
                    attempt_context = _code_timeout_retry_context(
                        attempt_context,
                        hypothesis,
                        exc,
                        observations,
                    )
                    state.note(
                        AgenticProposalPhase.DRAFT_PATCH,
                        "Retrying patch generation with compact timeout scope.",
                        metadata={
                            "selected_surface": hypothesis.change_locus,
                            "target_file": hypothesis.target_file,
                            "retry_attempt": attempt + 1,
                            "max_timeout_retries": max_retries,
                            "error": type(exc).__name__,
                        },
                    )
            raise RuntimeError("unreachable code-generation timeout retry state")
