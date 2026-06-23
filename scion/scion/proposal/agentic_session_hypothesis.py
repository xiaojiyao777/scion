"""AgenticSessionHypothesis mixin."""
from __future__ import annotations

from typing import Any, Mapping

from scion.problem.providers import active_subject_taxonomy_payload
from scion.proposal.agentic_session_common import *
from scion.proposal.agentic_session_hypothesis_schema_retry import (
    _canonical_retry_identity_value,
    _drop_empty_identity_fields,
    _flatten_telemetry_activation_items,
    _hypothesis_retry_anchor,
    _is_structural_activation_ref,
    _launch_focus_required_mechanism_retry_pending,
    _latest_schema_preservation_rejection,
    _mechanism_change_anchor,
    _mechanism_id_schema_retry_pending,
    _mechanism_ref_matches,
    _mechanism_ref_token,
    _mechanism_refs_from_telemetry_path,
    _protected_mechanism_ids,
    _same_mechanism_preview_retry_pending,
    _schema_retry_activation_identity_drift,
    _schema_retry_corrective_retry_already_used,
    _schema_retry_drift_failure_detail,
    _schema_retry_drift_feedback,
    _schema_retry_observed_identity,
    _schema_retry_preservation_drift,
    _schema_retry_protected_identity,
    _telemetry_activation_mechanism_refs,
)
from scion.proposal.agentic_session_hypothesis_target import (
    AgenticSessionHypothesisTargetMixin,
    _active_grounding_rejections_for_prompt,
    _algorithm_file_payload_full_content_visible,
    _coerce_nonnegative_int,
    _distinct_grounding_target_key_count,
    _grounding_rejection_count_for_target_context,
    _mechanism_id_schema_output_retry_feedback,
    _normalize_hypothesis_target_intent,
    _normalize_prompt_grounding_path,
    _normalize_target_intent_action,
    _observations_include_bounded_target_file_context,
    _observations_include_full_target_file,
    _observations_include_full_target_slice_context,
    _observations_include_sufficient_target_context,
    _prompt_observations_include_sufficient_target_context,
    _solver_design_target_prompt_grounding_feedback,
    _target_context_summary_from_observations,
    _target_grounding_context_key,
    _target_intent_as_hypothesis,
    _target_intent_placeholder,
)
from scion.proposal.agentic_session_hypothesis_novelty import (
    AgenticSessionHypothesisNoveltyMixin,
    _mechanism_novelty_gate_prompt_parity_feedback,
)
from scion.proposal.agentic_session_hypothesis_prompt import (
    _build_hypothesis_prompt_context,
    _expected_telemetry_guidance_for_hypothesis,
    _hypothesis_prompt_call_kind,
)
from scion.proposal.agentic_session_hypothesis_preview_retry import (
    _compact_preview_list,
    _failed_schema_check_detail,
    _hypothesis_preview_retry_feedback,
    _latest_tool_observation,
    _novelty_signature_preview_retry_feedback,
    _same_mechanism_preview_retry_feedback,
)
from scion.proposal.session_trace_index import attach_agentic_trace_context
from scion.proposal.schemas import normalize_mechanism_changes_with_repair_attribution
from scion.proposal.target_intent_binding import (
    target_intent_binding_retry_feedback as _target_intent_binding_retry_feedback,
    target_intent_binding_retry_pending as _target_intent_binding_retry_pending,
)


class AgenticSessionHypothesisMixin(
    AgenticSessionHypothesisNoveltyMixin,
    AgenticSessionHypothesisTargetMixin,
):
    def _forced_hypothesis_violation(
            self,
            context: ProposalToolContext | None,
            hypothesis: HypothesisProposal,
            *,
            request: AgenticProposalRequest | None = None,
        ) -> str | None:
            forced_surface = str(
                getattr(context, "forced_surface", None)
                or (
                    (request.hypothesis_context or {}).get("forced_surface")
                    if request is not None and request.hypothesis_context is not None
                    else ""
                )
                or ""
            ).strip()
            if not forced_surface:
                boundary = tuple(
                    str(surface or "").strip()
                    for surface in getattr(
                        context,
                        "active_problem_boundary_surfaces",
                        (),
                    )
                    if str(surface or "").strip()
                )
                if not boundary and request is not None and request.hypothesis_context:
                    constraints = request.hypothesis_context.get(
                        "agentic_hypothesis_constraints"
                    )
                    if isinstance(constraints, Mapping):
                        raw = constraints.get("active_problem_boundary_surfaces")
                        if isinstance(raw, str):
                            boundary = tuple(
                                item.strip() for item in raw.split(",") if item.strip()
                            )
                        elif isinstance(raw, (list, tuple)):
                            boundary = tuple(
                                str(item).strip() for item in raw if str(item).strip()
                            )
                if boundary:
                    actual_surface = str(hypothesis.change_locus or "").strip()
                    if actual_surface not in set(boundary):
                        return (
                            "active_problem_boundary_constraint: change_locus must "
                            f"stay within {list(boundary)!r}; got "
                            f"{actual_surface!r}. Component policies are "
                            "implementation hooks or attribution evidence, not "
                            "replacement research goals."
                        )
                return None
            actual_surface = str(hypothesis.change_locus or "").strip()
            if actual_surface != forced_surface:
                return (
                    "forced_surface_constraint: change_locus must be "
                    f"{forced_surface!r}, got {actual_surface!r}"
                )
            forced_action = str(
                getattr(context, "forced_action", None)
                or (
                    (request.hypothesis_context or {}).get("forced_action")
                    if request is not None and request.hypothesis_context is not None
                    else ""
                )
                or ""
            ).strip()
            if forced_action and str(hypothesis.action or "").strip() != forced_action:
                return (
                    "forced_surface_constraint: action must be "
                    f"{forced_action!r}, got {str(hypothesis.action or '').strip()!r}"
                )
            forced_target = str(
                getattr(context, "forced_target_file", None)
                or (
                    (request.hypothesis_context or {}).get("forced_target_file")
                    if request is not None and request.hypothesis_context is not None
                    else ""
                )
                or ""
            ).strip()
            if forced_target and str(hypothesis.target_file or "").strip() != forced_target:
                return (
                    "forced_surface_constraint: target_file must be "
                    f"{forced_target!r}, got {str(hypothesis.target_file or '').strip()!r}"
                )
            return None

    def _generate_hypothesis_with_semantic_retries(
            self,
            *,
            request: AgenticProposalRequest,
            session_id: str,
            state: AgenticProposalSessionState,
            tool_context: ProposalToolContext | None,
            observations: list[ProposalObservation],
            evidence: list[AgenticEvidenceRef],
        ) -> tuple[HypothesisProposal | None, AgenticProposalOutput | None]:
            semantic_rejections: list[Mapping[str, Any]] = []
            preview_rejections: list[Mapping[str, Any]] = []
            grounding_rejections: list[Mapping[str, Any]] = []
            target_intent = self._hypothesis_target_intent_preflight(
                request=request,
                state=state,
                tool_context=tool_context,
                observations=observations,
                evidence=evidence,
            )
            max_attempts = (
                1
                + _MAX_HYPOTHESIS_SEMANTIC_RETRIES
                + _MAX_HYPOTHESIS_PREVIEW_RETRIES
                + (
                    _MAX_HYPOTHESIS_GROUNDING_RETRIES
                    * _MAX_HYPOTHESIS_GROUNDING_TARGET_KEYS
                )
            )
            for attempt in range(1, max_attempts + 1):
                if self._session_timeout_reached(state):
                    output = self._timeout_output(
                        request,
                        state,
                        evidence_used=tuple(evidence),
                    )
                    state.status = output.status
                    return None, self._persist(output, state)
                state.note(
                    AgenticProposalPhase.CHOOSE_SURFACE,
                    "Delegating hypothesis generation.",
                    metadata={"attempt": attempt},
                )
                state.note(
                    AgenticProposalPhase.DRAFT_HYPOTHESIS,
                    "Generating hypothesis proposal.",
                    metadata={"attempt": attempt},
                )
                try:
                    hypothesis_context, prompt_observations = (
                        self._hypothesis_prompt_context(
                            request=request,
                            tool_context=tool_context,
                            observations=observations,
                            semantic_rejections=semantic_rejections,
                            preview_rejections=preview_rejections,
                            grounding_rejections=grounding_rejections,
                            target_intent=target_intent,
                            attempt=attempt,
                        )
                    )
                    call_kind = _hypothesis_prompt_call_kind(
                        attempt=attempt,
                        semantic_rejections=semantic_rejections,
                        preview_rejections=preview_rejections,
                        grounding_rejections=grounding_rejections,
                    )
                    hypothesis_context = attach_agentic_trace_context(
                        hypothesis_context,
                        session_id=state.session_id,
                        request_id=state.request_id or state.session_id,
                        branch_id=state.branch_id,
                        campaign_id=state.campaign_id,
                        request_kind="hypothesis",
                        call_kind=call_kind,
                        phase=AgenticProposalPhase.DRAFT_HYPOTHESIS.value,
                        attempt_number=attempt,
                        problem_id=request.problem_id,
                        problem_spec_hash=request.problem_spec_hash,
                        split_manifest_hash=request.split_manifest_hash,
                        seed_ledger_hash=request.seed_ledger_hash,
                    )
                    self._record_prompt_manifest(
                        state,
                        call_kind=call_kind,
                        prompt_context=hypothesis_context,
                        observations=prompt_observations,
                    )
                    assert self._creative is not None
                    hypothesis = self._creative.generate_hypothesis(hypothesis_context)
                except self._SESSION_ERROR_TYPES as exc:
                    mechanism_id_feedback = (
                        _mechanism_id_schema_output_retry_feedback(
                            exc,
                            target_intent=target_intent,
                            attempt=attempt,
                        )
                    )
                    if (
                        mechanism_id_feedback is not None
                        and len(preview_rejections) < _MAX_HYPOTHESIS_PREVIEW_RETRIES
                    ):
                        feedback_ref, feedback_digest = (
                            self._record_schema_retry_feedback_audit(
                                state,
                                mechanism_id_feedback,
                                attempt=attempt,
                            )
                        )
                        preview_rejections.append(mechanism_id_feedback)
                        state.note(
                            AgenticProposalPhase.DRAFT_HYPOTHESIS,
                            "Formal hypothesis used an invalid mechanism id; retrying with the canonical schema-safe id.",
                            metadata={
                                "attempt": attempt,
                                "failure_code": mechanism_id_feedback.get(
                                    "failure_code"
                                ),
                                "canonical_formal_mechanism_id": (
                                    mechanism_id_feedback.get(
                                        "canonical_formal_mechanism_id"
                                    )
                                ),
                                "feedback_ref": feedback_ref,
                                "feedback_digest": feedback_digest,
                                "schema_output_retry": True,
                            },
                        )
                        continue
                    failure_category = _structured_output_failure_category(exc)
                    _record_failure_ledger_entry(
                        state,
                        phase=AgenticProposalPhase.DRAFT_HYPOTHESIS,
                        category=failure_category,
                        detail=str(exc),
                        source="hypothesis_generation_exception",
                        attempt=attempt,
                    )
                    output = self._failed_output(
                        request=request,
                        session_id=session_id,
                        status=AgenticProposalStatus.FAILED,
                        termination_reason=AgenticTerminationReason.HYPOTHESIS_GENERATION_FAILED,
                        detail=str(exc),
                        evidence_used=tuple(evidence),
                        failure_category=failure_category,
                    )
                    state.status = output.status
                    state.note(
                        AgenticProposalPhase.FINALIZE,
                        "Hypothesis generation failed.",
                        metadata={"error": type(exc).__name__, "attempt": attempt},
                    )
                    return None, self._persist(output, state)
                hypothesis, schema_repairs = _normalize_hypothesis_schema_shape(
                    hypothesis
                )
                if schema_repairs:
                    repair_codes = [
                        str(
                            repair.get("diagnostic_code")
                            or repair.get("repair_kind")
                            or ""
                        )
                        for repair in schema_repairs
                        if isinstance(repair, Mapping)
                    ]
                    repair_codes = list(dict.fromkeys(code for code in repair_codes if code))
                    state.note(
                        AgenticProposalPhase.DRAFT_HYPOTHESIS,
                        "Normalized repairable hypothesis schema shape.",
                        metadata={
                            "attempt": attempt,
                            "diagnostic_codes": repair_codes,
                            "schema_repairs": list(schema_repairs),
                            "schema_only_repair": True,
                            "quality_block": False,
                        },
                    )

                if self._session_timeout_reached(state):
                    output = self._timeout_output(
                        request,
                        state,
                        evidence_used=tuple(evidence),
                    )
                    state.status = output.status
                    return None, self._persist(output, state)

                forced_violation = self._forced_hypothesis_violation(
                    tool_context,
                    hypothesis,
                    request=request,
                )
                if forced_violation is not None:
                    boundary_failure_code = (
                        "active_problem_boundary_constraint"
                        if forced_violation.startswith(
                            "active_problem_boundary_constraint"
                        )
                        else "forced_surface_constraint"
                    )
                    output = self._failed_output(
                        request=request,
                        session_id=session_id,
                        status=AgenticProposalStatus.FAILED,
                        termination_reason=AgenticTerminationReason.HYPOTHESIS_GENERATION_FAILED,
                        detail=forced_violation,
                        evidence_used=tuple(evidence),
                        failure_category=AgenticFailureCategory.CONTRACT_BOUNDARY_FAILURE,
                        structured_rejection={
                            "source": "hypothesis_boundary_gate",
                            "failure_code": boundary_failure_code,
                            "failure_category": (
                                AgenticFailureCategory.CONTRACT_BOUNDARY_FAILURE.value
                            ),
                            "reason": forced_violation,
                            "selected_surface": hypothesis.change_locus,
                            "target_file": hypothesis.target_file,
                        },
                    )
                    state.status = output.status
                    state.note(
                        AgenticProposalPhase.FINALIZE,
                        "Hypothesis generation violated the forced research-surface constraint.",
                        metadata={"detail": forced_violation, "attempt": attempt},
                    )
                    return None, self._persist(output, state)

                binding_feedback = _target_intent_binding_retry_feedback(
                    target_intent,
                    hypothesis,
                    attempt=attempt,
                    manifest=getattr(state, "_latest_hypothesis_prompt_manifest", None),
                )
                if binding_feedback is not None:
                    binding_ref, binding_digest = (
                        self._record_hypothesis_target_binding_audit(
                            state,
                            target_intent=target_intent,
                            hypothesis=hypothesis,
                            binding_status="mismatch",
                            retry_reason=binding_feedback.get("reason"),
                            attempt=attempt,
                            status="retry"
                            if len(preview_rejections)
                            < _MAX_HYPOTHESIS_PREVIEW_RETRIES
                            else "blocked",
                            manifest=getattr(
                                state,
                                "_latest_hypothesis_prompt_manifest",
                                None,
                            ),
                        )
                    )
                    feedback_ref, feedback_digest = (
                        self._record_schema_retry_feedback_audit(
                            state,
                            binding_feedback,
                            attempt=attempt,
                        )
                    )
                    if len(preview_rejections) < _MAX_HYPOTHESIS_PREVIEW_RETRIES:
                        preview_rejections.append(binding_feedback)
                        state.note(
                            AgenticProposalPhase.DRAFT_HYPOTHESIS,
                            "Formal hypothesis did not bind to the selected target intent; retrying under the same selected intent.",
                            metadata={
                                "attempt": attempt,
                                "failure_code": binding_feedback.get("failure_code"),
                                "binding_status": "mismatch",
                                "selected_target_intent": binding_feedback.get(
                                    "selected_target_intent"
                                ),
                                "formal_hypothesis_target": binding_feedback.get(
                                    "formal_hypothesis_target"
                                ),
                                "binding_audit_ref": binding_ref,
                                "binding_audit_digest": binding_digest,
                                "schema_retry_feedback_ref": feedback_ref,
                                "schema_retry_feedback_digest": feedback_digest,
                            },
                        )
                        continue

                    detail = str(binding_feedback.get("reason") or "").strip()
                    _record_failure_ledger_entry(
                        state,
                        phase=AgenticProposalPhase.DRAFT_HYPOTHESIS,
                        category=AgenticFailureCategory.CONTRACT_BOUNDARY_FAILURE,
                        detail=detail,
                        source="hypothesis_target_intent_binding_gate",
                        attempt=attempt,
                        failure_code="target_intent_binding_mismatch",
                        diagnostic_payload=binding_feedback,
                        diagnostic_ref=feedback_ref,
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
                        "Session failed closed because formal hypothesis target/action did not bind to the selected target intent.",
                        metadata={
                            "detail": detail,
                            "attempt": attempt,
                            "failure_code": "target_intent_binding_mismatch",
                            "binding_status": "mismatch",
                            "binding_audit_ref": binding_ref,
                            "binding_audit_digest": binding_digest,
                            "schema_retry_feedback_ref": feedback_ref,
                            "schema_retry_feedback_digest": feedback_digest,
                        },
                    )
                    return None, self._persist(output, state)

                preview_preservation_count = len(preview_rejections)
                preview_preservation_output = (
                    self._hypothesis_preview_preservation_drift_or_retry(
                        request=request,
                        session_id=session_id,
                        state=state,
                        tool_context=tool_context,
                        hypothesis=hypothesis,
                        evidence=evidence,
                        preview_rejections=preview_rejections,
                        attempt=attempt,
                    )
                )
                if preview_preservation_output is not None:
                    return None, preview_preservation_output
                if len(preview_rejections) > preview_preservation_count:
                    continue

                grounding_feedback_count = len(grounding_rejections)
                grounding_output = self._solver_design_target_prompt_grounding_retry(
                    request=request,
                    session_id=session_id,
                    state=state,
                    tool_context=tool_context,
                    hypothesis=hypothesis,
                    prompt_observations=prompt_observations,
                    observations=observations,
                    evidence=evidence,
                    grounding_rejections=grounding_rejections,
                    attempt=attempt,
                )
                if grounding_output is not None:
                    return None, grounding_output
                if len(grounding_rejections) > grounding_feedback_count:
                    continue

                semantic_feedback_count = len(semantic_rejections)
                novelty_output = self._solver_design_semantic_rejection_or_retry(
                    request=request,
                    session_id=session_id,
                    state=state,
                    tool_context=tool_context,
                    hypothesis=hypothesis,
                    observations=observations,
                    evidence=evidence,
                    semantic_rejections=semantic_rejections,
                    attempt=attempt,
                )
                if novelty_output is not None:
                    return None, novelty_output
                if len(semantic_rejections) > semantic_feedback_count:
                    continue

                preview_feedback_count = len(preview_rejections)
                preview_output = self._hypothesis_preview_rejection_or_retry(
                    request=request,
                    session_id=session_id,
                    state=state,
                    tool_context=tool_context,
                    hypothesis=hypothesis,
                    observations=observations,
                    evidence=evidence,
                    preview_rejections=preview_rejections,
                    attempt=attempt,
                )
                if preview_output is not None:
                    return None, preview_output
                if len(preview_rejections) > preview_feedback_count:
                    continue
                if target_intent is not None:
                    self._record_hypothesis_target_binding_audit(
                        state,
                        target_intent=target_intent,
                        hypothesis=hypothesis,
                        binding_status="bound",
                        retry_reason="",
                        attempt=attempt,
                        status="succeeded",
                        manifest=getattr(
                            state,
                            "_latest_hypothesis_prompt_manifest",
                            None,
                        ),
                    )
                return hypothesis, None
            return None, None

    def _hypothesis_preview_preservation_drift_or_retry(
            self,
            *,
            request: AgenticProposalRequest,
            session_id: str,
            state: AgenticProposalSessionState,
            tool_context: ProposalToolContext | None,
            hypothesis: HypothesisProposal,
            evidence: list[AgenticEvidenceRef],
            preview_rejections: list[Mapping[str, Any]],
            attempt: int,
        ) -> AgenticProposalOutput | None:
            structural_activation_refs = _active_subject_telemetry_activation_refs(
                tool_context,
                surface=getattr(hypothesis, "change_locus", None),
            )
            drift = _schema_retry_preservation_drift(
                hypothesis,
                preview_rejections,
                attempt=attempt,
                structural_activation_refs=structural_activation_refs,
            )
            if drift is None:
                return None
            feedback = _schema_retry_drift_feedback(
                drift,
                hypothesis,
                attempt=attempt,
                structural_activation_refs=structural_activation_refs,
            )
            if not _schema_retry_corrective_retry_already_used(preview_rejections):
                preview_rejections.append(feedback)
                state.note(
                    AgenticProposalPhase.DRAFT_HYPOTHESIS,
                    "Hypothesis schema retry changed protected research identity; issuing one identity-corrective retry.",
                    metadata={
                        "attempt": attempt,
                        "failure_code": "schema_retry_drift",
                        "drift_fields": drift.get("drift_fields", ()),
                        "corrective_retry": True,
                    },
                )
                return None

            detail = _schema_retry_drift_failure_detail(drift)
            _record_failure_ledger_entry(
                state,
                phase=AgenticProposalPhase.DRAFT_HYPOTHESIS,
                category=AgenticFailureCategory.CONTRACT_BOUNDARY_FAILURE,
                detail=detail,
                source="hypothesis_preview_retry_preservation_gate",
                attempt=attempt,
                failure_code="schema_retry_drift",
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
                "Hypothesis schema retry failed closed because protected research identity drifted.",
                metadata={
                    "detail": detail,
                    "attempt": attempt,
                    "failure_code": "schema_retry_drift",
                    "drift_fields": drift.get("drift_fields", ()),
                    "corrective_retry_exhausted": True,
                },
            )
            return self._persist(output, state)

    def _hypothesis_prompt_context(
            self,
            *,
            request: AgenticProposalRequest,
            tool_context: ProposalToolContext | None,
            observations: list[ProposalObservation],
            semantic_rejections: list[Mapping[str, Any]],
            preview_rejections: list[Mapping[str, Any]],
            grounding_rejections: list[Mapping[str, Any]],
            target_intent: Mapping[str, Any] | None = None,
            attempt: int,
        ) -> tuple[dict[str, Any], list[ProposalObservation]]:
            return _build_hypothesis_prompt_context(
                request=request,
                tool_context=tool_context,
                constraints=self._hypothesis_constraints(tool_context),
                observations=observations,
                semantic_rejections=semantic_rejections,
                preview_rejections=preview_rejections,
                grounding_rejections=grounding_rejections,
                target_intent=target_intent,
                attempt=attempt,
            )

    def _hypothesis_preview_rejection_or_retry(
            self,
            *,
            request: AgenticProposalRequest,
            session_id: str,
            state: AgenticProposalSessionState,
            tool_context: ProposalToolContext | None,
            hypothesis: HypothesisProposal,
            observations: list[ProposalObservation],
            evidence: list[AgenticEvidenceRef],
            preview_rejections: list[Mapping[str, Any]],
            attempt: int,
        ) -> AgenticProposalOutput | None:
            if tool_context is None:
                return None

            selected_surface_observations = self._run_selected_surface_observation_tool(
                tool_context,
                hypothesis,
                state,
                observations,
            )
            observations.extend(selected_surface_observations)
            evidence.extend(_evidence_from_observations(selected_surface_observations))

            preview_observations = self._run_hypothesis_preview_tools(
                tool_context,
                hypothesis,
                state,
            )
            observations.extend(preview_observations)
            evidence.extend(_evidence_from_observations(preview_observations))
            self_check = _self_check_from_previews(preview_observations)
            self_check_detail = _self_check_failure_detail(
                self_check,
                require_schema_preview=_self_check_required(tool_context),
                require_contract_preview=False,
            )
            if self_check_detail is None:
                return None

            retry_feedback = _hypothesis_preview_retry_feedback(
                preview_observations,
                detail=self_check_detail,
                attempt=attempt,
                previous_hypothesis=hypothesis,
            )
            if (
                retry_feedback is not None
                and len(preview_rejections) < _MAX_HYPOTHESIS_PREVIEW_RETRIES
            ):
                preview_rejections.append(retry_feedback)
                feedback_ref, feedback_digest = (
                    self._record_schema_retry_feedback_audit(
                        state,
                        retry_feedback,
                        attempt=attempt,
                    )
                )
                state.note(
                    AgenticProposalPhase.DRAFT_HYPOTHESIS,
                    "Hypothesis preview gate rejected hypothesis; retrying with structured schema feedback.",
                    metadata={
                        "attempt": attempt,
                        "failure_code": retry_feedback.get("failure_code"),
                        "source": retry_feedback.get("source"),
                        "schema_retry_feedback_ref": feedback_ref,
                        "schema_retry_feedback_digest": feedback_digest,
                    },
                )
                return None

            feedback_ref, feedback_digest = (
                self._record_schema_retry_feedback_audit(
                    state,
                    retry_feedback,
                    attempt=attempt,
                )
                if retry_feedback is not None
                else (None, None)
            )

            _record_failure_ledger_entry(
                state,
                phase=AgenticProposalPhase.SELF_CHECK,
                category=_preview_failure_category(preview_observations),
                detail=self_check_detail,
                source="hypothesis_preview_failure",
                attempt=attempt,
                failure_code=(
                    str(retry_feedback.get("failure_code"))
                    if retry_feedback is not None
                    else None
                ),
                diagnostic_payload=retry_feedback,
                diagnostic_ref=feedback_ref,
            )
            output = self._self_check_failed_output(
                request=request,
                session_id=session_id,
                hypothesis=hypothesis,
                detail=self_check_detail,
                termination_reason=AgenticTerminationReason.HYPOTHESIS_GENERATION_FAILED,
                evidence_used=tuple(evidence),
                self_check=self_check,
                failure_category=AgenticFailureCategory.CONTRACT_BOUNDARY_FAILURE,
            )
            state.status = output.status
            state.note(
                AgenticProposalPhase.FINALIZE,
                "Hypothesis self-check failed closed before approval.",
                metadata={
                    "detail": self_check_detail,
                    "attempt": attempt,
                    "failure_code": (
                        retry_feedback.get("failure_code")
                        if retry_feedback is not None
                        else None
                    ),
                    "schema_retry_feedback_ref": feedback_ref,
                    "schema_retry_feedback_digest": feedback_digest,
                },
            )
            return self._persist(output, state)

    def _record_schema_retry_feedback_audit(
            self,
            state: AgenticProposalSessionState,
            feedback: Mapping[str, Any] | None,
            *,
            attempt: int,
        ) -> tuple[str | None, str | None]:
            if not isinstance(feedback, Mapping):
                return None, None
            payload = {
                "schema_version": "hypothesis-schema-retry-feedback.v1",
                "artifact_kind": "hypothesis_schema_retry_feedback",
                "session_id": state.session_id,
                "attempt": attempt,
                "failure_code": feedback.get("failure_code"),
                "feedback": _sanitize_agentic_value(dict(feedback)),
                "trace_policy": (
                    "Full C11/schema retry feedback is stored here. Compact "
                    "transcript and resume summaries may cite this artifact "
                    "instead of copying the full template."
                ),
            }
            digest = stable_digest(payload, length=64)
            artifact_ref: str | None = None
            if self._artifact_store is not None:
                artifact_ref = self._artifact_store.write_scratch(
                    state.session_id,
                    f"hypothesis_schema_retry_feedback_{attempt:04d}.json",
                    payload,
                )
                state.scratch_artifact_refs.append(artifact_ref)
            return artifact_ref, digest

def _active_subject_telemetry_activation_refs(
    context: ProposalToolContext | None,
    *,
    surface: str | None,
) -> set[str]:
    if context is None:
        return set()
    taxonomy = active_subject_taxonomy_payload(
        context=context,
        problem_spec=getattr(context, "problem_spec", None),
        adapter=getattr(context, "adapter", None),
        surface=surface,
    )
    return {
        _mechanism_ref_token(item)
        for item in taxonomy.get("telemetry_activation_refs", ()) or ()
        if _mechanism_ref_token(item)
    }


def _normalize_hypothesis_schema_shape(
    hypothesis: HypothesisProposal,
) -> tuple[HypothesisProposal, tuple[dict[str, Any], ...]]:
    raw_changes = [
        {
            "id": getattr(change, "id", ""),
            "change_type": getattr(change, "change_type", ""),
        }
        if not isinstance(change, Mapping)
        else dict(change)
        for change in getattr(hypothesis, "mechanism_changes", ()) or ()
    ]
    normalized, repairs = normalize_mechanism_changes_with_repair_attribution(
        raw_changes
    )
    if not repairs or not isinstance(normalized, list):
        return hypothesis, ()
    hypothesis.mechanism_changes = tuple(
        MechanismChange(
            id=str(change.get("id") or "").strip(),
            change_type=str(change.get("change_type") or "").strip(),  # type: ignore[arg-type]
        )
        for change in normalized
        if isinstance(change, Mapping)
    )
    hypothesis.schema_repair_attribution = tuple(
        [
            *tuple(getattr(hypothesis, "schema_repair_attribution", ()) or ()),
            *repairs,
        ]
    )
    return hypothesis, repairs
