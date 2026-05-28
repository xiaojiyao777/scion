"""AgenticSessionRepair mixin."""
from __future__ import annotations

import ast
import json
import re

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
            self_check_feedback = {
                "passed": False,
                "issue": issue_detail,
                "file_path": patch.file_path,
                "action": patch.action,
                "test_hint": patch.test_hint,
            }
            self_check_feedback.update(
                _code_self_check_structured_feedback(
                    issue_detail,
                    hypothesis,
                    code_context=code_context,
                )
            )
            repair_context["agentic_code_self_check_feedback"] = (
                self_check_feedback
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
    return feedback.get("reason") in {
        "exact_replace_empty_old_string",
        "exact_replace_empty_source_digest",
        "exact_replace_missing_new_string",
        "exact_replace_missing_old_string",
        "exact_replace_missing_source_digest",
        "exact_replace_not_serializable",
        "exact_replace_non_string_new_string",
        "exact_replace_non_string_old_string",
        "exact_replace_null_new_string",
        "exact_replace_null_old_string",
        "old_string_not_unique",
        "existing_file_create_rejected",
        "existing_file_full_file_modify_rejected",
        "existing_file_full_file_modify_source_required",
        "existing_file_near_whole_file_exact_replace_rejected",
        "existing_file_whole_file_exact_replace_rejected",
    }


def _code_self_check_structured_feedback(
    issue_detail: str,
    hypothesis: HypothesisProposal,
    *,
    code_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if "code_stage_telemetry_identity_mismatch" not in str(issue_detail or ""):
        return {}
    protected_ids = [
        str(change.id)
        for change in mechanism_changes(hypothesis)
        if str(change.id).strip()
    ]
    offending_ids = _parse_telemetry_identity_ids(issue_detail)
    offending_usages = _parse_telemetry_identity_usages(issue_detail)
    return _drop_empty_dict(
        {
            "failure_code": "code_stage_telemetry_identity_mismatch",
            "current_blocker": "telemetry_identity",
            "offending_telemetry_ids": offending_ids,
            "offending_generated_telemetry_ids": offending_ids,
            "offending_telemetry_usages": offending_usages,
            "protected_mechanism_ids": protected_ids,
            "allowed_structural_telemetry_ids": (
                _code_context_telemetry_identity_allowlist(code_context)
            ),
            "telemetry_preservation_policy": "protected_mechanism_ids_only",
            "repair_instruction": (
                "Repair each offending_telemetry_usage in the named file_path "
                "and json_pointer: replace that telemetry mechanism id with "
                "one of protected_mechanism_ids, or remove the newly added "
                "mechanism-evidence call. Do not preserve any telemetry id "
                "outside protected_mechanism_ids from the previous patch; "
                "baseline phase ids are diagnostic context only unless "
                "unchanged."
            ),
        }
    )


def _parse_telemetry_identity_ids(issue_detail: str) -> list[str]:
    match = re.search(
        r"not declared by the approved hypothesis:\s*(\[[^\]]*\])",
        str(issue_detail or ""),
    )
    if match:
        try:
            parsed = ast.literal_eval(match.group(1))
        except (SyntaxError, ValueError):
            parsed = []
        if isinstance(parsed, (list, tuple, set)):
            return sorted(
                str(item).strip()
                for item in parsed
                if str(item).strip()
            )
    fallback = re.findall(r"['\"]([A-Za-z][A-Za-z0-9_]{1,63})['\"]", str(issue_detail))
    return sorted(dict.fromkeys(fallback))


def _parse_telemetry_identity_usages(issue_detail: str) -> list[dict[str, Any]]:
    text = str(issue_detail or "")
    marker = "Offending generated telemetry usages:"
    marker_index = text.find(marker)
    if marker_index < 0:
        return []
    payload_start = text.find("[", marker_index)
    if payload_start < 0:
        return []
    try:
        parsed, _end = json.JSONDecoder().raw_decode(text[payload_start:])
    except (json.JSONDecodeError, TypeError, ValueError):
        return []
    if not isinstance(parsed, list):
        return []
    usages: list[dict[str, Any]] = []
    for item in parsed[:12]:
        if not isinstance(item, Mapping):
            continue
        usage = _drop_empty_dict(
            {
                "mechanism_id": item.get("mechanism_id"),
                "file_path": item.get("file_path"),
                "json_pointer": item.get("json_pointer"),
                "line": item.get("line"),
                "column": item.get("column"),
                "helper": item.get("helper"),
                "receiver": item.get("receiver"),
                "line_text": item.get("line_text"),
                "usage_kind": item.get("usage_kind"),
                "repair_guidance": item.get("repair_guidance"),
            }
        )
        if usage:
            usages.append(usage)
    return usages


def _code_context_telemetry_identity_allowlist(
    code_context: Mapping[str, Any] | None,
) -> list[str]:
    if not isinstance(code_context, Mapping):
        return []
    taxonomy = code_context.get("active_subject_taxonomy")
    if not isinstance(taxonomy, Mapping):
        return []
    return sorted(
        str(item).strip()
        for item in taxonomy.get("telemetry_identity_allowlist", ()) or ()
        if str(item).strip()
    )


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
    reason = str(feedback.get("reason") or "")
    if reason == "old_string_not_unique":
        retry_context["prior_code_failure"] = (
            "Typed exact_replace edit failed: old_string_not_unique"
            + (f" ({match_count} matches)" if match_count else "")
            + f" in {target_file!r}. Regenerate a unique old_string by copying "
            "stable surrounding context from one candidate snippet. Keep "
            "replace_all=false unless this is intentionally a global replacement. "
            f"Preserve target_file={hypothesis.target_file!r}, "
            f"action={hypothesis.action!r}, and mechanism_changes ids={protected_ids!r}."
        )
        final_task = (
            "Return the same patch intent using exact_replace with an "
            "old_string that matches exactly one intended location. Include "
            "nearby unchanged context from one candidate's "
            "unique_old_string_hint."
        )
    elif reason == "exact_replace_not_serializable":
        prior_pointers = feedback.get("prior_json_pointers")
        retry_context["prior_code_failure"] = (
            "Typed same-file exact_replace edits were not serializable: "
            f"{reason} in {target_file!r} at "
            f"{feedback.get('json_pointer')!r}. Prior same-file edit pointers: "
            f"{prior_pointers!r}. "
            f"{feedback.get('guidance') or ''} Preserve "
            f"target_file={hypothesis.target_file!r}, action={hypothesis.action!r}, "
            f"and mechanism_changes ids={protected_ids!r}; repair only the "
            "current same-file serialization blocker. For the failing file, "
            "the retry must use one change per file: merge intended edits into "
            "a single exact_replace or emit a helper file plus one small "
            "integration edit. Do not include multiple additional_changes for "
            "that file. Remove no-op EOF/trailing newline edits and any "
            "old_string == new_string entries."
        )
        final_task = (
            "Return the same patch intent with one file change for the failing "
            "file. Do not generate no-op EOF/trailing newline edits, "
            "old_string == new_string entries, or multiple same-file "
            "additional_changes."
        )
    elif reason.startswith("exact_replace_"):
        field = str(feedback.get("field") or "typed edit field")
        pointer = str(feedback.get("json_pointer") or "")
        retry_context["prior_code_failure"] = (
            "Typed exact_replace schema/preflight failed: "
            f"{reason} at {pointer or target_file!r}. "
            f"Rejected field={field!r} for {target_file!r}. Preserve "
            f"target_file={hypothesis.target_file!r}, action={hypothesis.action!r}, "
            f"and mechanism_changes ids={protected_ids!r}; repair only the "
            "typed edit selector. Return action='modify', "
            "edit_intent='exact_replace', source_digest, non-empty old_string, "
            "new_string, and replace_all. For deletion use new_string: \"\"; "
            "do not omit new_string or set it to null."
        )
        final_task = (
            "Return the same patch intent with a complete exact_replace edit: "
            "action='modify', edit_intent='exact_replace', source_digest, "
            "non-empty old_string, new_string, and replace_all. For deletion "
            "use new_string: \"\"; never omit new_string or use null."
        )
    elif reason in {
        "existing_file_near_whole_file_exact_replace_rejected",
        "existing_file_whole_file_exact_replace_rejected",
    }:
        coverage_ratio = feedback.get("coverage_ratio")
        old_string_chars = feedback.get("old_string_chars")
        file_chars = feedback.get("file_chars")
        source_digest = feedback.get("source_digest")
        guidance = str(feedback.get("guidance") or "").strip()
        retry_context["prior_code_failure"] = (
            "Typed exact_replace edit was too broad: "
            f"{reason} in {target_file!r}. "
            f"coverage_ratio={coverage_ratio!r}, "
            f"old_string_chars={old_string_chars!r}, "
            f"file_chars={file_chars!r}, source_digest={source_digest!r}. "
            f"{guidance} Preserve target_file={hypothesis.target_file!r}, "
            f"action={hypothesis.action!r}, and mechanism_changes "
            f"ids={protected_ids!r}; repair only the edit granularity. "
            "Do not replace a registry/function plus unrelated later functions "
            "as one contiguous old_string."
        )
        final_task = (
            "Return the same patch intent split into function/block-level "
            "exact_replace edits, or create a helper file and add one small "
            "integration edit. Each existing-file old_string must identify only "
            "the local block that changes; keep old_string coverage below the "
            "recommended coverage ratio and never use one near-whole-file "
            "selector to repair runtime feedback."
        )
    else:
        retry_context["prior_code_failure"] = (
            "Typed edit target/action failed: existing file requires modify "
            "exact_replace with source_digest; create is only for new files. "
            f"Rejected action={feedback.get('action')!r} for {target_file!r}. "
            f"Preserve target_file={hypothesis.target_file!r} and "
            f"mechanism_changes ids={protected_ids!r}; repair the patch by "
            "using action='modify', edit_intent='exact_replace', source_digest, "
            "old_string, and new_string for any existing file. If adding a "
            "new helper module, keep only that new file as action='create' "
            "full_file and put existing integration files in typed "
            "additional_changes."
        )
        final_task = (
            "Existing file requires modify exact_replace with source_digest; "
            "create is only for new files. Return action='modify' with "
            "edit_intent='exact_replace' for existing files. Use full_file "
            "only for genuinely new file creates or deletes."
        )
    retry_context["agentic_code_edit_retry_feedback"] = _drop_empty_dict(
        {
            "failure_code": "code_edit_protocol_retry",
            "reason": reason,
            "file_path": target_file,
            "json_pointer": feedback.get("json_pointer"),
            "prior_json_pointers": feedback.get("prior_json_pointers"),
            "action": feedback.get("action"),
            "match_count": feedback.get("match_count"),
            "candidate_matches": feedback.get("candidate_matches"),
            "source_digest": feedback.get("source_digest"),
            "old_string_chars": feedback.get("old_string_chars"),
            "file_chars": feedback.get("file_chars"),
            "coverage_ratio": feedback.get("coverage_ratio"),
            "max_coverage_ratio": feedback.get("max_coverage_ratio"),
            "recommended_max_coverage_ratio": feedback.get(
                "recommended_max_coverage_ratio"
            ),
            "stage": feedback.get("stage"),
            "field": feedback.get("field"),
            "change_pointer": feedback.get("change_pointer"),
            "detail": feedback.get("detail"),
            "guidance": feedback.get("guidance"),
            "minimal_json_shape": feedback.get("minimal_json_shape"),
            "final_task": final_task,
            "current_blocker_only": (
                "Repair the single blocker named in reason; do not mix older "
                "runtime, preview, or import-whitelist blockers into this "
                "typed-edit retry."
            ),
            "same_file_retry_policy": (
                "After exact_replace_not_serializable, use one change per file "
                "for the failing file."
            )
            if reason == "exact_replace_not_serializable"
            else "",
            "edit_size_policy": (
                "Existing-file exact_replace old_string must be a local "
                "function/block/import/registration selector, not most of the "
                "file. Split large repairs into serializable small edits or a "
                "new helper file plus a minimal integration edit."
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
