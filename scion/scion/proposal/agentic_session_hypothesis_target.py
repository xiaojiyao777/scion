"""Target-intent and target-file grounding support for hypothesis sessions."""
from __future__ import annotations

from typing import Any, Mapping

from scion.core.models import MechanismChange
from scion.proposal.agentic_session_common import *
from scion.proposal.agentic_session_hypothesis_schema_retry import _hypothesis_retry_anchor
from scion.proposal.schemas import HypothesisTargetIntentInput
from scion.proposal.session_trace_index import attach_agentic_trace_context
from scion.proposal.target_intent_binding import (
    canonical_formal_mechanism_id as _canonical_formal_mechanism_id,
    formal_hypothesis_target_payload as _formal_hypothesis_target_payload,
    formal_target_source_visibility_from_manifest as _formal_target_source_visibility_from_manifest,
    selected_target_intent_payload as _selected_target_intent_payload,
    target_intent_mechanism_identity as _target_intent_mechanism_identity,
)


class AgenticSessionHypothesisTargetMixin:
    def _hypothesis_target_intent_preflight(
            self,
            *,
            request: AgenticProposalRequest,
            state: AgenticProposalSessionState,
            tool_context: ProposalToolContext | None,
            observations: list[ProposalObservation],
            evidence: list[AgenticEvidenceRef],
        ) -> Mapping[str, Any] | None:
            if tool_context is None or not _context_requires_solver_design_grounding(
                tool_context
            ):
                return None
            generator = getattr(
                self._creative,
                "generate_hypothesis_target_intent",
                None,
            )
            if not callable(generator):
                state.note(
                    AgenticProposalPhase.DRAFT_HYPOTHESIS,
                    "Hypothesis target-intent preflight unavailable; falling back to existing hypothesis flow.",
                    metadata={
                        "call_kind": "hypothesis_target_intent",
                        "status": "skipped",
                        "reason": "creative_layer_method_unavailable",
                        "fallback_to_current_flow": True,
                    },
                )
                return None

            state.note(
                AgenticProposalPhase.DRAFT_HYPOTHESIS,
                "Selecting hypothesis target intent before final hypothesis generation.",
                metadata={"call_kind": "hypothesis_target_intent"},
            )
            try:
                intent_context, prompt_observations = self._hypothesis_prompt_context(
                    request=request,
                    tool_context=tool_context,
                    observations=observations,
                    semantic_rejections=[],
                    preview_rejections=[],
                    grounding_rejections=[],
                    target_intent=None,
                    attempt=0,
                )
                intent_context = attach_agentic_trace_context(
                    intent_context,
                    session_id=state.session_id,
                    request_id=state.request_id or state.session_id,
                    branch_id=state.branch_id,
                    campaign_id=state.campaign_id,
                    request_kind="hypothesis",
                    call_kind="hypothesis_target_intent",
                    phase=AgenticProposalPhase.DRAFT_HYPOTHESIS.value,
                    attempt_number=0,
                    problem_id=request.problem_id,
                    problem_spec_hash=request.problem_spec_hash,
                    split_manifest_hash=request.split_manifest_hash,
                    seed_ledger_hash=request.seed_ledger_hash,
                )
                self._record_prompt_manifest(
                    state,
                    call_kind="hypothesis_target_intent",
                    prompt_context=intent_context,
                    observations=prompt_observations,
                )
                raw_intent = generator(intent_context)
                intent = _normalize_hypothesis_target_intent(raw_intent)
            except Exception as exc:
                self._record_hypothesis_target_intent_audit(
                    state,
                    status="fallback",
                    intent=None,
                    diagnostics={
                        "reason": "target_intent_preflight_failed",
                        "error_type": type(exc).__name__,
                        "detail": str(exc)[:500],
                        "fallback_to_current_flow": True,
                    },
                )
                state.note(
                    AgenticProposalPhase.DRAFT_HYPOTHESIS,
                    "Hypothesis target-intent preflight failed; falling back to existing hypothesis flow.",
                    metadata={
                        "call_kind": "hypothesis_target_intent",
                        "status": "fallback",
                        "error_type": type(exc).__name__,
                        "fallback_to_current_flow": True,
                    },
                )
                return None

            result: dict[str, Any] = {
                "schema_version": "hypothesis-target-intent-context.v1",
                "call_kind": "hypothesis_target_intent",
                "tainted": True,
                "formal_proposal": False,
                "decision_input": False,
                "intent": intent,
            }
            action = _normalize_target_intent_action(intent.get("action"))
            if action in {"modify", "remove"}:
                grounding = self._ground_hypothesis_target_intent(
                    state=state,
                    tool_context=tool_context,
                    observations=observations,
                    evidence=evidence,
                    intent=intent,
                )
                if grounding:
                    result["grounding"] = grounding
            elif action == "create_new":
                result["placeholder"] = _target_intent_placeholder(intent)

            artifact_ref, digest = self._record_hypothesis_target_intent_audit(
                state,
                status="succeeded",
                intent=result,
                diagnostics={},
            )
            state.note(
                AgenticProposalPhase.DRAFT_HYPOTHESIS,
                "Recorded hypothesis target-intent preflight.",
                metadata={
                    "call_kind": "hypothesis_target_intent",
                    "status": "succeeded",
                    "action": action,
                    "target_file": intent.get("target_file"),
                    "mechanism_id": intent.get("mechanism_id"),
                    "artifact_ref": artifact_ref,
                    "digest": digest,
                },
            )
            return result

    def _ground_hypothesis_target_intent(
            self,
            *,
            state: AgenticProposalSessionState,
            tool_context: ProposalToolContext,
            observations: list[ProposalObservation],
            evidence: list[AgenticEvidenceRef],
            intent: Mapping[str, Any],
        ) -> dict[str, Any]:
            target_hypothesis = _target_intent_as_hypothesis(intent)
            target_read_args = _solver_design_target_file_read_args(
                target_hypothesis,
                context=tool_context,
                observations=observations,
            )
            if target_read_args is None:
                return {
                    "status": "not_grounded",
                    "reason": "target_file_not_resolved_as_existing_algorithm_file",
                    "target_file": intent.get("target_file"),
                    "fallback_to_current_flow": True,
                }
            grounding_observations = self._run_solver_design_grounding_tools(
                tool_context,
                state,
                observations,
                selection_source="hypothesis_target_intent_grounding",
                hypothesis=target_hypothesis,
            )
            observations.extend(grounding_observations)
            evidence.extend(_evidence_from_observations(grounding_observations))
            target_context = _target_context_summary_from_observations(
                observations,
                target_read_args,
            )
            sufficient = _observations_include_sufficient_target_context(
                observations,
                target_read_args,
            )
            return _drop_empty_dict(
                {
                    "status": "grounded" if sufficient else "grounding_incomplete",
                    "target_file": target_read_args.get("file_path"),
                    "target_context_key": _target_grounding_context_key(
                        target_read_args,
                        target_context,
                    ),
                    "target_context_digest": target_context.get("content_digest"),
                    "source": target_context.get("source"),
                    "coverage_status": target_context.get("coverage_status"),
                    "api_visible_before_final_hypothesis": bool(sufficient),
                    "observation_ids": [
                        observation.observation_id
                        for observation in grounding_observations
                        if observation.observation_id
                    ],
                    "selection_source": "hypothesis_target_intent_grounding",
                    "fallback_to_current_flow": False if sufficient else True,
                }
            )

    def _record_hypothesis_target_intent_audit(
            self,
            state: AgenticProposalSessionState,
            *,
            status: str,
            intent: Mapping[str, Any] | None,
            diagnostics: Mapping[str, Any],
        ) -> tuple[str | None, str]:
            payload = {
                "schema_version": "hypothesis-target-intent-artifact.v1",
                "artifact_kind": "hypothesis_target_intent",
                "call_kind": "hypothesis_target_intent",
                "session_id": state.session_id,
                "status": status,
                "tainted": True,
                "formal_proposal": False,
                "decision_input": False,
                "intent": _sanitize_agentic_value(intent or {}),
                "diagnostics": _sanitize_agentic_value(dict(diagnostics or {})),
                "trace_policy": (
                    "This preflight artifact is proposal-layer target intent. "
                    "It may guide deterministic context exposure, but it is not "
                    "a formal hypothesis and is not read by Decision."
                ),
            }
            digest = stable_digest(payload, length=64)
            artifact_ref: str | None = None
            if self._artifact_store is not None:
                artifact_ref = self._artifact_store.write_scratch(
                    state.session_id,
                    "hypothesis_target_intent_0001.json",
                    payload,
                )
                state.scratch_artifact_refs.append(artifact_ref)
            return artifact_ref, digest

    def _record_hypothesis_target_binding_audit(
            self,
            state: AgenticProposalSessionState,
            *,
            target_intent: Mapping[str, Any] | None,
            hypothesis: HypothesisProposal,
            binding_status: str,
            retry_reason: Any,
            attempt: int,
            status: str,
            manifest: Mapping[str, Any] | None,
        ) -> tuple[str | None, str]:
            selected_intent = _selected_target_intent_payload(target_intent)
            payload = {
                "schema_version": "hypothesis-target-intent-binding.v1",
                "artifact_kind": "hypothesis_target_intent_binding",
                "call_kind": "hypothesis",
                "session_id": state.session_id,
                "attempt": attempt,
                "status": status,
                "binding_status": binding_status,
                "retry_reason": str(retry_reason or ""),
                "tainted": True,
                "decision_input": False,
                "selected_target_intent": _sanitize_agentic_value(selected_intent),
                "formal_hypothesis_target": _sanitize_agentic_value(
                    _formal_hypothesis_target_payload(hypothesis)
                ),
                "formal_target_source_visibility_ledger": _sanitize_agentic_value(
                    _formal_target_source_visibility_from_manifest(
                        manifest,
                        hypothesis,
                    )
                ),
                "trace_policy": (
                    "Proposal-layer audit of whether the final formal "
                    "hypothesis stayed bound to the selected target-intent "
                    "preflight. The source-visibility ledger is keyed by the "
                    "formal hypothesis target_file, not by the preflight owner."
                ),
            }
            digest = stable_digest(payload, length=64)
            artifact_ref: str | None = None
            if self._artifact_store is not None:
                artifact_ref = self._artifact_store.write_scratch(
                    state.session_id,
                    f"hypothesis_target_intent_binding_{attempt:04d}.json",
                    payload,
                )
                state.scratch_artifact_refs.append(artifact_ref)
            return artifact_ref, digest

    def _solver_design_target_prompt_grounding_retry(
            self,
            *,
            request: AgenticProposalRequest,
            session_id: str,
            state: AgenticProposalSessionState,
            tool_context: ProposalToolContext | None,
            hypothesis: HypothesisProposal,
            prompt_observations: list[ProposalObservation],
            observations: list[ProposalObservation],
            evidence: list[AgenticEvidenceRef],
            grounding_rejections: list[Mapping[str, Any]],
            attempt: int,
        ) -> AgenticProposalOutput | None:
            if tool_context is None or not _is_solver_design_hypothesis(hypothesis):
                return None
            target_read_args = _solver_design_target_file_read_args(
                hypothesis,
                context=tool_context,
                observations=observations,
            )
            if target_read_args is None:
                return None
            if _prompt_observations_include_sufficient_target_context(
                prompt_observations,
                target_read_args,
            ):
                return None

            grounding_observations = self._run_solver_design_grounding_tools(
                tool_context,
                state,
                observations,
                selection_source="solver_design_target_prompt_grounding_required",
                hypothesis=hypothesis,
            )
            observations.extend(grounding_observations)
            evidence.extend(_evidence_from_observations(grounding_observations))
            grounding_error = _missing_solver_design_grounding_error(
                observations,
                hypothesis=hypothesis,
                context=tool_context,
            )
            target_context = _target_context_summary_from_observations(
                observations,
                target_read_args,
            )
            target_context_key = _target_grounding_context_key(
                target_read_args,
                target_context,
            )
            target_retry_count = _grounding_rejection_count_for_target_context(
                grounding_rejections,
                target_context_key,
            )
            if (
                _observations_include_sufficient_target_context(
                    observations,
                    target_read_args,
                )
                and target_retry_count < _MAX_HYPOTHESIS_GROUNDING_RETRIES
                and _distinct_grounding_target_key_count(
                    grounding_rejections,
                    additional_key=target_context_key,
                )
                <= _MAX_HYPOTHESIS_GROUNDING_TARGET_KEYS
            ):
                grounding_rejections.append(
                    _solver_design_target_prompt_grounding_feedback(
                        hypothesis,
                        target_read_args,
                        attempt=attempt,
                        target_context=target_context,
                        target_context_key=target_context_key,
                        retry_count_for_target=target_retry_count + 1,
                    )
                )
                state.note(
                    AgenticProposalPhase.DRAFT_HYPOTHESIS,
                    "Solver-design target file was read after hypothesis generation; retrying with target source visible in the hypothesis prompt.",
                    metadata={
                        "attempt": attempt,
                        "target_file": target_read_args.get("file_path"),
                        "target_context_key": target_context_key,
                        "target_context_digest": target_context.get(
                            "content_digest"
                        ),
                        "target_retry_count": target_retry_count + 1,
                        "api_visible_in_latest_prompt": False,
                        "failure_code": "solver_design_target_not_in_hypothesis_prompt",
                    },
                )
                return None

            if grounding_error is not None:
                detail = grounding_error
            else:
                detail = (
                    "solver_design target-file grounding invariant failed: "
                    "hypothesis selected existing target_file "
                    f"{target_read_args.get('file_path')!r}, but the API-visible "
                    "hypothesis prompt did not include a sufficiently complete "
                    "provider-declared target-file context observation for that "
                    "file. "
                    f"target_context_key={target_context_key!r}; "
                    f"target_context_digest={target_context.get('content_digest')!r}; "
                    "api_visible_in_latest_prompt=False; "
                    f"retry_count_for_target={target_retry_count}; "
                    f"distinct_grounding_target_count={_distinct_grounding_target_key_count(grounding_rejections)}."
                )
            output = self._failed_output(
                request=request,
                session_id=session_id,
                status=AgenticProposalStatus.FAILED,
                termination_reason=AgenticTerminationReason.HYPOTHESIS_GENERATION_FAILED,
                detail=detail,
                evidence_used=tuple(evidence),
                failure_category=AgenticFailureCategory.CONTRACT_BOUNDARY_FAILURE,
            )
            state.status = output.status
            state.note(
                AgenticProposalPhase.FINALIZE,
                "Session failed closed before solver_design hypothesis approval because target-file source was not API-visible to hypothesis generation.",
                metadata={
                    "detail": detail,
                    "attempt": attempt,
                    "target_file": target_read_args.get("file_path"),
                    "target_context_key": target_context_key,
                    "target_context_digest": target_context.get("content_digest"),
                    "api_visible_in_latest_prompt": False,
                    "retry_count_for_target": target_retry_count,
                },
            )
            return self._persist(output, state)


def _solver_design_target_prompt_grounding_feedback(
    hypothesis: HypothesisProposal,
    target_read_args: Mapping[str, Any],
    *,
    attempt: int,
    target_context: Mapping[str, Any] | None = None,
    target_context_key: str = "",
    retry_count_for_target: int = 0,
) -> dict[str, Any]:
    target_file = str(target_read_args.get("file_path") or "").strip()
    target_context = dict(target_context or {})
    coverage_status = str(target_context.get("coverage_status") or "").strip()
    retry_constraint = (
        "Use the newly visible full context.read_algorithm_file content "
        f"for {target_file}. Redraft the same target/mechanism only after "
        "checking that file; do not proceed from a read receipt or "
        "post-hoc grounding observation."
    )
    if coverage_status == "truncated":
        retry_constraint = (
            "Use the newly visible truncated context.read_algorithm_file "
            f"context for {target_file}, including its digest and line coverage. "
            "Acknowledge the visible line range and avoid claims that require "
            "unseen source; request a narrower symbol/slice later only if the "
            "visible target context is insufficient."
        )
    return _drop_empty_dict(
        {
            "attempt": attempt,
            "source": "solver_design_target_prompt_grounding",
            "failure_code": "solver_design_target_not_in_hypothesis_prompt",
            "failure_category": AgenticFailureCategory.CONTRACT_BOUNDARY_FAILURE.value,
            "target_file": target_file,
            "target_context_key": target_context_key,
            "target_context_digest": target_context.get("content_digest"),
            "api_visible_in_latest_prompt": False,
            "retry_count_for_target": retry_count_for_target,
            "reason": (
                "The previous solver_design hypothesis selected an existing "
                "target_file, but sufficiently complete target-file context was "
                "not included in the API-visible prompt that generated it."
            ),
            "target_context": target_context,
            "preserve_hypothesis": _hypothesis_retry_anchor(hypothesis),
            "retry_constraint": retry_constraint,
        }
    )


def _target_grounding_context_key(
    target_read_args: Mapping[str, Any],
    target_context: Mapping[str, Any] | None = None,
) -> str:
    target_file = _normalize_prompt_grounding_path(target_read_args.get("file_path"))
    context = target_context or {}
    digest = str(
        context.get("content_digest")
        or context.get("digest")
        or target_read_args.get("source_digest")
        or ""
    ).strip()
    if digest:
        return f"{target_file}@{digest}"
    coverage = str(context.get("coverage_status") or "").strip()
    size_chars = str(context.get("size_chars") or "").strip()
    max_chars = str(target_read_args.get("max_chars") or "").strip()
    return f"{target_file}@{coverage}:{size_chars}:{max_chars}"


def _grounding_rejection_count_for_target_context(
    grounding_rejections: list[Mapping[str, Any]],
    target_context_key: str,
) -> int:
    return sum(
        1
        for rejection in grounding_rejections
        if str(rejection.get("target_context_key") or "") == target_context_key
    )


def _distinct_grounding_target_key_count(
    grounding_rejections: list[Mapping[str, Any]],
    *,
    additional_key: str | None = None,
) -> int:
    keys = {
        str(rejection.get("target_context_key") or "").strip()
        for rejection in grounding_rejections
        if str(rejection.get("target_context_key") or "").strip()
    }
    if additional_key:
        keys.add(str(additional_key).strip())
    return len(keys)


def _active_grounding_rejections_for_prompt(
    grounding_rejections: list[Mapping[str, Any]],
    *,
    semantic_rejections: list[Mapping[str, Any]],
    preview_rejections: list[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    if not grounding_rejections:
        return []
    latest_semantic_or_preview_attempt = max(
        [
            int(rejection.get("attempt") or 0)
            for rejection in [*semantic_rejections, *preview_rejections]
        ]
        or [0]
    )
    active = [
        rejection
        for rejection in grounding_rejections
        if int(rejection.get("attempt") or 0) >= latest_semantic_or_preview_attempt
    ]
    return active[-1:] if active else []


def _prompt_observations_include_sufficient_target_context(
    prompt_observations: list[ProposalObservation],
    target_read_args: Mapping[str, Any],
) -> bool:
    return _observations_include_sufficient_target_context(
        prompt_observations,
        target_read_args,
    )


def _observations_include_sufficient_target_context(
    observations: list[ProposalObservation],
    target_read_args: Mapping[str, Any],
) -> bool:
    return (
        _observations_include_full_target_file(observations, target_read_args)
        or _observations_include_bounded_target_file_context(
            observations,
            target_read_args,
        )
        or _observations_include_full_target_slice_context(
            observations,
            target_file=target_read_args.get("file_path"),
        )
    )


def _observations_include_full_target_file(
    observations: list[ProposalObservation],
    target_read_args: Mapping[str, Any],
) -> bool:
    target_path = _normalize_prompt_grounding_path(target_read_args.get("file_path"))
    if not target_path:
        return False
    requested_max_chars = _coerce_nonnegative_int(
        target_read_args.get("max_chars"),
        default=_APS_TARGET_ALGORITHM_FILE_READ_CHARS,
    )
    for observation in observations:
        if observation.is_error or observation.tool_name != "context.read_algorithm_file":
            continue
        payload = observation.structured_payload
        if not isinstance(payload, Mapping):
            continue
        if _normalize_prompt_grounding_path(payload.get("file_path")) != target_path:
            continue
        if _algorithm_file_payload_full_content_visible(
            payload,
            requested_max_chars=requested_max_chars,
        ):
            return True
    return False


def _algorithm_file_payload_full_content_visible(
    payload: Mapping[str, Any],
    *,
    requested_max_chars: int,
) -> bool:
    if payload.get("readable") is not True:
        return False
    if payload.get("already_observed"):
        return False
    content_preview = payload.get("content_preview")
    if content_preview is None:
        return False
    if bool(payload.get("truncated")):
        return False
    preview_chars = len(str(content_preview))
    size_chars = _coerce_nonnegative_int(payload.get("size_chars"))
    max_chars = _coerce_nonnegative_int(payload.get("max_chars"))
    if (
        size_chars is not None
        and max_chars is not None
        and max_chars >= size_chars
    ):
        return True
    if size_chars is not None:
        return preview_chars >= min(size_chars, requested_max_chars)
    if max_chars is not None:
        return preview_chars >= min(max_chars, requested_max_chars)
    return not bool(payload.get("compacted_for_agentic_budget"))


def _observations_include_bounded_target_file_context(
    observations: list[ProposalObservation],
    target_read_args: Mapping[str, Any],
) -> bool:
    target_context = _target_context_summary_from_observations(
        observations,
        target_read_args,
    )
    if not target_context:
        return False
    if target_context.get("coverage_status") == "full":
        return True
    if target_context.get("coverage_status") != "truncated":
        return False
    return bool(
        target_context.get("content_digest")
        and target_context.get("line_start") == 1
        and target_context.get("line_end")
        and target_context.get("covered_line_count")
        and target_context.get("total_line_count")
    )


def _observations_include_full_target_slice_context(
    observations: list[ProposalObservation],
    *,
    target_file: Any,
) -> bool:
    target_path = _normalize_prompt_grounding_path(target_file)
    if not target_path:
        return False
    for observation in observations:
        if observation.is_error or observation.tool_name != "context.read_algorithm_slice":
            continue
        payload = observation.structured_payload
        if not isinstance(payload, Mapping):
            continue
        if not payload.get("available", True):
            continue
        if _normalize_prompt_grounding_path(payload.get("file_path")) != target_path:
            continue
        coverage_status = str(
            payload.get("coverage_status") or payload.get("coverage") or ""
        ).strip()
        if coverage_status == "full" and str(payload.get("content") or "").strip():
            return True
    return False


def _target_context_summary_from_observations(
    observations: list[ProposalObservation],
    target_read_args: Mapping[str, Any],
) -> dict[str, Any]:
    target_path = _normalize_prompt_grounding_path(target_read_args.get("file_path"))
    if not target_path:
        return {}
    for observation in reversed(observations):
        if observation.is_error or observation.tool_name != "context.read_algorithm_file":
            continue
        payload = observation.structured_payload
        if not isinstance(payload, Mapping):
            continue
        if _normalize_prompt_grounding_path(payload.get("file_path")) != target_path:
            continue
        content_preview = str(payload.get("content_preview") or "")
        if not bool(payload.get("readable")) or not content_preview:
            return {}
        truncated = bool(payload.get("truncated"))
        total_line_count = _coerce_nonnegative_int(payload.get("total_line_count"))
        covered_line_count = _coerce_nonnegative_int(payload.get("covered_line_count"))
        if total_line_count is None:
            total_line_count = len(content_preview.splitlines())
        if covered_line_count is None:
            covered_line_count = len(content_preview.splitlines())
        line_end = _coerce_nonnegative_int(payload.get("line_end"))
        if line_end is None and covered_line_count:
            line_end = covered_line_count
        content_digest = str(
            payload.get("content_digest")
            or payload.get("sha256")
            or payload.get("digest")
            or ""
        ).strip()
        return _drop_empty_dict(
            {
                "tool_name": observation.tool_name,
                "observation_id": observation.observation_id,
                "file_path": target_path,
                "coverage_status": "truncated" if truncated else "full",
                "truncated": truncated,
                "size_chars": payload.get("size_chars"),
                "max_chars": payload.get("max_chars"),
                "line_start": payload.get("line_start") or 1,
                "line_end": line_end,
                "covered_line_count": covered_line_count,
                "total_line_count": total_line_count,
                "content_digest": content_digest,
                "digest": payload.get("digest"),
                "source": payload.get("source"),
            }
        )
    return {}


def _normalize_prompt_grounding_path(value: Any) -> str:
    return str(value or "").replace("\\", "/").lstrip("/").strip()


def _coerce_nonnegative_int(value: Any, *, default: int | None = None) -> int | None:
    try:
        parsed = int(value)
    except Exception:
        return default
    if parsed < 0:
        return default
    return parsed


def _mechanism_id_schema_output_retry_feedback(
    exc: BaseException,
    *,
    target_intent: Mapping[str, Any] | None,
    attempt: int,
) -> dict[str, Any] | None:
    detail = str(exc)
    if "mechanism id must match ^[a-z][a-z0-9_]{0,63}$" not in detail:
        return None
    selected = _selected_target_intent_payload(target_intent)
    canonical_id = _canonical_formal_mechanism_id(selected.get("mechanism_id"))
    raw_id = str(selected.get("raw_mechanism_id") or "").strip()
    if not canonical_id and raw_id:
        canonical_id = _canonical_formal_mechanism_id(raw_id)
    return _drop_empty_dict(
        {
            "attempt": attempt,
            "attempt_kind": "schema_output_repair",
            "repair_classification": "mechanism_id_schema_output_repair",
            "source": "hypothesis_schema_output_parser",
            "gate_name": "hypothesis_structured_output_schema",
            "failure_code": "invalid_mechanism_id",
            "check": "mechanism_changes_id_pattern",
            "failure_category": AgenticFailureCategory.SCHEMA_OUTPUT_FAILURE.value,
            "reason": _limit_string(detail, 1000),
            "canonical_formal_mechanism_id": canonical_id,
            "raw_mechanism_id": raw_id,
            "selected_target_intent": selected,
            "protected_identity": {
                "change_locus": selected.get("change_locus"),
                "action": selected.get("action"),
                "target_file": selected.get("target_file"),
                "mechanism_id": canonical_id,
                "raw_mechanism_id": raw_id,
            },
            "final_task": (
                "Rewrite the same formal hypothesis using the canonical "
                "schema-safe mechanism id."
            ),
            "retry_constraint": (
                "Formal mechanism_changes[].id must match "
                "^[a-z][a-z0-9_]{0,63}$. Use canonical_formal_mechanism_id "
                "exactly when present. raw_mechanism_id is audit provenance "
                "only and must not be copied into mechanism_changes or "
                "expected telemetry refs."
            ),
            "proposal_failure_accounting": (
                "pre_code_schema_retry; do_not_count_as_code_or_screening_failure"
            ),
        }
    )


def _normalize_hypothesis_target_intent(raw: Any) -> dict[str, Any]:
    if isinstance(raw, HypothesisTargetIntentInput):
        payload = raw.model_dump()
        raw_mapping: Mapping[str, Any] = {}
    elif isinstance(raw, Mapping):
        raw_mapping = raw
        allowed_fields = set(HypothesisTargetIntentInput.model_fields)
        payload = {
            key: value
            for key, value in dict(raw).items()
            if key in allowed_fields
        }
    else:
        raise ProposalValidationError(
            "hypothesis target-intent preflight must return a JSON object"
        )
    validated = HypothesisTargetIntentInput(**payload)
    change_locus = str(validated.change_locus or validated.surface or "").strip()
    action = _normalize_target_intent_action(validated.action)
    mechanism_identity = _target_intent_mechanism_identity(
        mechanism_id=raw_mapping.get("raw_mechanism_id") or validated.mechanism_id,
        mechanism_family=validated.mechanism_family,
        mechanism_sketch=validated.mechanism_sketch,
    )
    return _drop_empty_dict(
        {
            "change_locus": change_locus,
            "surface": change_locus,
            "action": action,
            "target_file": _normalize_prompt_grounding_path(validated.target_file),
            **mechanism_identity,
            "mechanism_sketch": validated.mechanism_sketch,
            "confidence": validated.confidence,
            "notes": validated.notes,
        }
    )


def _normalize_target_intent_action(value: Any) -> str:
    action = str(value or "").strip()
    return "create_new" if action == "create" else action


def _target_intent_as_hypothesis(intent: Mapping[str, Any]) -> HypothesisProposal:
    action = _normalize_target_intent_action(intent.get("action"))
    mechanism_id = str(intent.get("mechanism_id") or "").strip()
    change_type = {
        "create_new": "add",
        "modify": "modify",
        "remove": "remove",
    }.get(action, "modify")
    return HypothesisProposal(
        hypothesis_text="Target-intent preflight grounding surrogate.",
        change_locus=str(intent.get("change_locus") or intent.get("surface") or ""),
        action=action,  # type: ignore[arg-type]
        target_file=str(intent.get("target_file") or "") or None,
        mechanism_changes=(
            (MechanismChange(id=mechanism_id, change_type=change_type),)
            if mechanism_id
            else ()
        ),
    )


def _target_intent_placeholder(intent: Mapping[str, Any]) -> dict[str, Any]:
    target_file = _normalize_prompt_grounding_path(intent.get("target_file"))
    return _drop_empty_dict(
        {
            "schema_version": "hypothesis-target-placeholder.v1",
            "target_file": target_file,
            "action": "create_new",
            "owner_required": False,
            "source_status": "new_file_placeholder",
            "source_provenance": "target_intent_create_new",
            "placeholder_visible": True,
            "integration_context": (
                "Use active solver facts, map receipts, declared surface "
                "bounds, and branch context to describe how this new target "
                "would integrate. No existing owner source is required for "
                "this preflight target."
            ),
        }
    )
