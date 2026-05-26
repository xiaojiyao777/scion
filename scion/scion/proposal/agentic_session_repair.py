"""AgenticSessionRepair mixin."""
from __future__ import annotations

from scion.core.models import mechanism_changes
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
            if failed_preview.tool_name == "proposal.algorithm_smoke":
                repair_context["agentic_preview_feedback"] = (
                    _preview_repair_feedback_prompt_payload(failed_preview)
                )
            research_diagnosis = _research_diagnosis_from_observations(observations)
            if research_diagnosis:
                repair_context["agentic_research_diagnosis"] = research_diagnosis
            active_algorithm_facts = _active_algorithm_facts_for_prompt_context(
                observations
            )
            if active_algorithm_facts:
                repair_context["agentic_active_algorithm_facts"] = (
                    active_algorithm_facts
                )
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
            active_algorithm_facts = _active_algorithm_facts_for_prompt_context(
                observations
            )
            if active_algorithm_facts:
                repair_context["agentic_active_algorithm_facts"] = (
                    active_algorithm_facts
                )
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
        timeout_attempt = 0
        generation_attempt = 0
        shape_retry_used = False
        edit_protocol_retry_used = False
        while True:
            generation_attempt += 1
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
                    attempt=generation_attempt,
                )
                if (
                    not edit_protocol_retry_used
                    and _is_code_edit_protocol_retryable(exc)
                    and not self._session_timeout_reached(state)
                ):
                    edit_protocol_retry_used = True
                    attempt_context = _code_edit_protocol_retry_context(
                        attempt_context,
                        hypothesis,
                        exc,
                    )
                    state.note(
                        AgenticProposalPhase.DRAFT_PATCH,
                        "Retrying patch generation with typed-edit protocol feedback.",
                        metadata={
                            "selected_surface": hypothesis.change_locus,
                            "target_file": hypothesis.target_file,
                            "retry_attempt": generation_attempt,
                            "error": type(exc).__name__,
                            "failure_code": "code_edit_protocol_retry",
                        },
                    )
                    continue
                if (
                    not shape_retry_used
                    and _is_code_schema_shape_retryable(exc)
                    and not self._session_timeout_reached(state)
                ):
                    shape_retry_used = True
                    attempt_context = _code_schema_shape_retry_context(
                        attempt_context,
                        hypothesis,
                        exc,
                    )
                    state.note(
                        AgenticProposalPhase.DRAFT_PATCH,
                        "Retrying patch generation with shape-only schema feedback.",
                        metadata={
                            "selected_surface": hypothesis.change_locus,
                            "target_file": hypothesis.target_file,
                            "retry_attempt": generation_attempt,
                            "error": type(exc).__name__,
                            "failure_code": "code_output_shape_retry",
                        },
                    )
                    continue
                if (
                    timeout_attempt >= max_retries
                    or self._session_timeout_reached(state)
                    or not _is_code_generation_timeout(exc)
                ):
                    raise
                timeout_attempt += 1
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
                        "retry_attempt": timeout_attempt,
                        "max_timeout_retries": max_retries,
                        "error": type(exc).__name__,
                    },
                )
                continue


def _is_code_edit_protocol_retryable(exc: BaseException) -> bool:
    if not isinstance(exc, ProposalValidationError):
        return False
    feedback = _code_edit_protocol_feedback(exc)
    return feedback.get("reason") == "old_string_not_unique"


def _code_edit_protocol_retry_context(
    context: Mapping[str, Any],
    hypothesis: HypothesisProposal,
    exc: BaseException,
) -> dict[str, Any]:
    retry_context = dict(context)
    feedback = _code_edit_protocol_feedback(exc)
    protected_ids = [
        str(change.id)
        for change in mechanism_changes(hypothesis)
        if str(change.id).strip()
    ]
    match_count = feedback.get("match_count")
    target_file = feedback.get("file_path") or hypothesis.target_file
    retry_context["prior_code_failure"] = (
        "Typed exact_replace edit failed: old_string_not_unique"
        + (f" ({match_count} matches)" if match_count else "")
        + f" in {target_file!r}. Regenerate a unique old_string by copying "
        "stable surrounding context from one candidate snippet. Keep "
        "replace_all=false unless this is intentionally a global replacement. "
        f"Preserve target_file={hypothesis.target_file!r}, "
        f"action={hypothesis.action!r}, and mechanism_changes ids={protected_ids!r}."
    )
    retry_context["agentic_code_edit_retry_feedback"] = _drop_empty_dict(
        {
            "failure_code": "code_edit_protocol_retry",
            "reason": feedback.get("reason"),
            "file_path": target_file,
            "json_pointer": feedback.get("json_pointer"),
            "match_count": feedback.get("match_count"),
            "candidate_matches": feedback.get("candidate_matches"),
            "source_digest": feedback.get("source_digest"),
            "final_task": (
                "Return the same patch intent using exact_replace with an "
                "old_string that matches exactly one intended location. Include "
                "nearby unchanged context from one candidate's "
                "unique_old_string_hint."
            ),
            "replace_all_rule": (
                "Use replace_all=true only when the intended edit is global "
                "across every candidate match."
            ),
            "protected_identity": _drop_empty_dict(
                {
                    "action": hypothesis.action,
                    "target_file": hypothesis.target_file,
                    "mechanism_change_ids": protected_ids,
                }
            ),
        }
    )
    return retry_context


def _code_edit_protocol_feedback(exc: BaseException) -> dict[str, Any]:
    text = str(exc).strip()
    if not text:
        return {}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, Mapping):
        return {}
    if payload.get("error") != "patch_edit_protocol":
        return {}
    return dict(payload)


def _is_code_schema_shape_retryable(exc: BaseException) -> bool:
    if not isinstance(exc, ProposalValidationError):
        return False
    text = str(exc).lower()
    return (
        "additional_changes" in text
        and "json-encoded string" in text
        and "shape-only retry" in text
    )


def _code_schema_shape_retry_context(
    context: Mapping[str, Any],
    hypothesis: HypothesisProposal,
    exc: BaseException,
) -> dict[str, Any]:
    retry_context = dict(context)
    message = str(exc)
    protected_ids = [
        str(change.id)
        for change in mechanism_changes(hypothesis)
        if str(change.id).strip()
    ]
    retry_context["prior_code_failure"] = (
        "Patch structured output shape failure: "
        f"{message} Repair only the JSON shape. Preserve the same hypothesis, "
        f"target_file={hypothesis.target_file!r}, action={hypothesis.action!r}, "
        f"and mechanism_changes ids={protected_ids!r}; do not change the "
        "research mechanism or patch intent."
    )
    retry_context["agentic_code_schema_shape_retry_feedback"] = _drop_empty_dict(
        {
            "failure_code": "code_output_shape_retry",
            "field": "additional_changes",
            "reason": message,
            "final_task": (
                "Return the same patch as valid JSON shape: additional_changes "
                "must be an array of edit objects, not a string."
            ),
            "protected_identity": _drop_empty_dict(
                {
                    "action": hypothesis.action,
                    "target_file": hypothesis.target_file,
                    "mechanism_change_ids": protected_ids,
                }
            ),
            "retry_constraint": (
                "Shape-only retry. Do not rename, retarget, add, or drop "
                "mechanism ids."
            ),
        }
    )
    return retry_context
