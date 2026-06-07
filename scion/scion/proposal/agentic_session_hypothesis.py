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
from scion.proposal.hypothesis_telemetry_retry import (
    expected_telemetry_retry_feedback as _expected_telemetry_retry_feedback,
)
from scion.proposal.session_trace_index import attach_agentic_trace_context
from scion.proposal.negative_facts import render_negative_fact_block
from scion.proposal.schemas import normalize_mechanism_changes_with_repair_attribution
from scion.proposal.target_intent_binding import (
    target_intent_binding_retry_feedback as _target_intent_binding_retry_feedback,
    target_intent_binding_retry_pending as _target_intent_binding_retry_pending,
)
from scion.runtime.telemetry_guard import expected_telemetry_template


class AgenticSessionHypothesisMixin(AgenticSessionHypothesisTargetMixin):
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
                    output = self._failed_output(
                        request=request,
                        session_id=session_id,
                        status=AgenticProposalStatus.FAILED,
                        termination_reason=AgenticTerminationReason.HYPOTHESIS_GENERATION_FAILED,
                        detail=forced_violation,
                        evidence_used=tuple(evidence),
                        failure_category=AgenticFailureCategory.CONTRACT_BOUNDARY_FAILURE,
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
            hypothesis_context = dict(
                _sanitize_agentic_value(request.hypothesis_context or {})
            )
            if request.resume_context is not None:
                hypothesis_context["agentic_resume_context"] = (
                    _sanitize_agentic_value(request.resume_context)
                )
            constraints = self._hypothesis_constraints(tool_context)
            if constraints:
                hypothesis_context["agentic_hypothesis_constraints"] = (
                    _sanitize_agentic_value(constraints)
                )
            if target_intent:
                hypothesis_context["agentic_hypothesis_target_intent"] = (
                    _sanitize_agentic_value(target_intent)
                )
                placeholder = target_intent.get("placeholder")
                if isinstance(placeholder, Mapping):
                    hypothesis_context["agentic_hypothesis_target_placeholder"] = (
                        _sanitize_agentic_value(placeholder)
                    )
            telemetry_guidance = _expected_telemetry_guidance_for_hypothesis(
                tool_context,
            )
            if telemetry_guidance:
                hypothesis_context["agentic_expected_telemetry_guidance"] = (
                    telemetry_guidance
                )
            if semantic_rejections:
                hypothesis_context["agentic_hypothesis_semantic_rejections"] = [
                    _sanitize_agentic_value(rejection)
                    for rejection in semantic_rejections
                ]
                hypothesis_context["agentic_hypothesis_retry_rule"] = (
                    "An audited gate found a hard boundary/objective-policy "
                    "contradiction in the previous hypothesis. Preserve the "
                    "research goal when possible; if the idea remains near an "
                    "existing mechanism, explicitly acknowledge that mechanism "
                    "and state the material trigger, scoring, schedule, or "
                    "behavior difference."
                )
                hypothesis_context["agentic_hypothesis_retry_attempt"] = attempt
            if preview_rejections:
                hypothesis_context["agentic_hypothesis_preview_rejections"] = [
                    _sanitize_agentic_value(rejection)
                    for rejection in preview_rejections
                ]
                if _schema_retry_corrective_retry_already_used(preview_rejections):
                    hypothesis_context["agentic_hypothesis_preview_retry_rule"] = (
                        "IDENTITY CORRECTIVE RETRY for a schema/telemetry "
                        "repair. Restore the exact protected identity from the "
                        "feedback: action, target_file, mechanism_changes ids/"
                        "change_types, and telemetry activation refs. The final "
                        "task is only to repair expected_telemetry/schema fields "
                        "for that same hypothesis; do not explore, rename, or "
                        "choose a different mechanism."
                    )
                elif _mechanism_id_schema_retry_pending(preview_rejections):
                    hypothesis_context["agentic_hypothesis_preview_retry_rule"] = (
                        "MECHANISM-ID SCHEMA RETRY. The previous formal "
                        "hypothesis used a mechanism_changes id that is not "
                        "legal for the formal schema. Use the canonical formal "
                        "mechanism id from the feedback exactly in "
                        "mechanism_changes and expected telemetry refs. "
                        "raw_mechanism_id/provenance fields are audit-only and "
                        "must not be copied into formal mechanism_changes."
                    )
                elif _target_intent_binding_retry_pending(preview_rejections):
                    hypothesis_context["agentic_hypothesis_preview_retry_rule"] = (
                        "TARGET-INTENT BINDING RETRY. The selected "
                        "hypothesis_target_intent is binding for this final "
                        "formal hypothesis call. Rewrite under the same "
                        "selected intent: preserve change_locus, action, "
                        "target_file, and mechanism family/continuation from "
                        "selected_target_intent. Do not switch owners or "
                        "mechanisms. A different target requires a host-owned "
                        "target-intent reselect flow before formal hypothesis "
                        "generation."
                    )
                elif _same_mechanism_preview_retry_pending(preview_rejections):
                    hypothesis_context["agentic_hypothesis_preview_retry_rule"] = (
                        "SAME-MECHANISM BRANCH RETRY. The selected branch is "
                        "same_mechanism_only, so replace any unrelated "
                        "mechanism_changes ids with one of the protected ids "
                        "from the feedback. The only valid task is tune, "
                        "integrate, repair, parameterize, or telemetry wiring "
                        "inside the protected mechanism. A genuinely different "
                        "mechanism requires a clean branch/fork before "
                        "hypothesis generation; when active clean-fork slots "
                        "are available, treat the new-mechanism idea as a "
                        "branch-routing signal rather than burning this "
                        "same-branch formal proposal."
                    )
                else:
                    hypothesis_context["agentic_hypothesis_preview_retry_rule"] = (
                        "A schema/target preview rejected the previous hypothesis. "
                        "This is a structured-field repair, not a semantic novelty "
                        "rejection. Preserve the previous action, target_file, "
                        "mechanism_changes ids/change_types, and telemetry "
                        "activation mechanism; repair only the exact field named "
                        "by the failed check unless the preview explicitly says "
                        "that surface/action/target is invalid. Natural-language "
                        "hypothesis and novelty_signature wording may be clarified "
                        "without changing the mechanism."
                    )
                hypothesis_context["agentic_hypothesis_retry_attempt"] = attempt
            active_grounding_rejections = _active_grounding_rejections_for_prompt(
                grounding_rejections,
                semantic_rejections=semantic_rejections,
                preview_rejections=preview_rejections,
            )
            if active_grounding_rejections:
                hypothesis_context["agentic_hypothesis_grounding_rejections"] = [
                    _sanitize_agentic_value(rejection)
                    for rejection in active_grounding_rejections
                ]
                latest_grounding = active_grounding_rejections[-1]
                target_file = str(latest_grounding.get("target_file") or "").strip()
                hypothesis_context["agentic_hypothesis_grounding_retry_rule"] = (
                    "The previous solver_design hypothesis selected an existing "
                    "target_file whose full source was not visible in the API "
                    "prompt that generated it. This grounding feedback is scoped "
                    f"to target_file={target_file!r}; do not use source from a "
                    "different target_file as grounding. The target file has now "
                    "been read and is projected into this API-visible prompt. "
                    "Redraft only after using that target-file observation. If "
                    "separate semantic feedback requires changing to a different "
                    "existing target_file, Scion must ground that new target in "
                    "a later prompt before approval."
                )
                hypothesis_context["agentic_hypothesis_retry_attempt"] = attempt
            if observations:
                prompt_observations = _hypothesis_prompt_observations(
                    observations,
                    tool_context,
                )
                research_diagnosis = _research_diagnosis_from_observations(observations)
                if research_diagnosis:
                    hypothesis_context["agentic_research_diagnosis"] = (
                        research_diagnosis
                    )
                active_algorithm_facts = _active_algorithm_facts_for_prompt_context(
                    observations
                )
                if active_algorithm_facts:
                    hypothesis_context["agentic_active_algorithm_facts"] = (
                        active_algorithm_facts
                    )
                hypothesis_context["agentic_tool_observations"] = [
                    _observation_prompt_payload(observation)
                    for observation in prompt_observations
                ]
                negative_fact_block = render_negative_fact_block(
                    active_algorithm_facts=active_algorithm_facts,
                    structured_rejections=semantic_rejections,
                    prior_quality_blocks=tuple(
                        block
                        for block in hypothesis_context.get(
                            "agentic_prior_quality_blocks",
                            (),
                        )
                        if isinstance(block, Mapping)
                    ),
                )
                if negative_fact_block:
                    existing = str(
                        hypothesis_context.get("agentic_negative_fact_block") or ""
                    ).strip()
                    hypothesis_context["agentic_negative_fact_block"] = (
                        existing + "\n" + negative_fact_block
                        if existing
                        else negative_fact_block
                    )
            else:
                prompt_observations = []
            return hypothesis_context, prompt_observations

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

    def _solver_design_semantic_rejection_or_retry(
            self,
            *,
            request: AgenticProposalRequest,
            session_id: str,
            state: AgenticProposalSessionState,
            tool_context: ProposalToolContext | None,
            hypothesis: HypothesisProposal,
            observations: list[ProposalObservation],
            evidence: list[AgenticEvidenceRef],
            semantic_rejections: list[Mapping[str, Any]],
            attempt: int,
        ) -> AgenticProposalOutput | None:
            if tool_context is None or not _is_solver_design_hypothesis(hypothesis):
                return None
            grounding_observations = self._run_solver_design_grounding_tools(
                tool_context,
                state,
                observations,
                selection_source="solver_design_grounding_required",
                hypothesis=hypothesis,
            )
            observations.extend(grounding_observations)
            evidence.extend(_evidence_from_observations(grounding_observations))
            grounding_error = _missing_solver_design_grounding_error(
                observations,
                hypothesis=hypothesis,
                context=tool_context,
            )
            if grounding_error is not None:
                output = self._failed_output(
                    request=request,
                    session_id=session_id,
                    status=AgenticProposalStatus.FAILED,
                    termination_reason=AgenticTerminationReason.HYPOTHESIS_GENERATION_FAILED,
                    detail=grounding_error,
                    evidence_used=tuple(evidence),
                    failure_category=AgenticFailureCategory.CONTRACT_BOUNDARY_FAILURE,
                )
                state.status = output.status
                state.note(
                    AgenticProposalPhase.FINALIZE,
                    "Session failed closed before solver_design hypothesis approval because active solver grounding was missing.",
                    metadata={"detail": grounding_error, "attempt": attempt},
                )
                return self._persist(output, state)

            result = _MECHANISM_NOVELTY_GATE.evaluate(
                hypothesis,
                context=tool_context,
                observations=observations,
            )
            if result is None:
                return None
            if not result.is_hard_block:
                _record_mechanism_novelty_diagnostic(
                    state,
                    hypothesis=hypothesis,
                    result=result,
                    attempt=attempt,
                    observations=observations,
                )
                return None
            parity_feedback = _mechanism_novelty_gate_prompt_parity_feedback(
                result,
                getattr(state, "_latest_hypothesis_prompt_manifest", None),
                attempt=attempt,
            )
            if parity_feedback is not None:
                if len(semantic_rejections) < _MAX_HYPOTHESIS_SEMANTIC_RETRIES:
                    semantic_rejections.append(parity_feedback)
                    state.note(
                        AgenticProposalPhase.DRAFT_HYPOTHESIS,
                        "Mechanism novelty gate facts were not visible in the hypothesis prompt; retrying with gate/prompt parity feedback.",
                        metadata={
                            "attempt": attempt,
                            "failure_code": parity_feedback.get("failure_code"),
                            "fact_packet_digest": parity_feedback.get(
                                "fact_packet_digest"
                            ),
                            "prompt_fact_packet_digest": parity_feedback.get(
                                "prompt_fact_packet_digest"
                            ),
                        },
                    )
                    return None
                detail = str(parity_feedback.get("reason") or "")
                _record_failure_ledger_entry(
                    state,
                    phase=AgenticProposalPhase.DRAFT_HYPOTHESIS,
                    category=AgenticFailureCategory.CONTRACT_BOUNDARY_FAILURE,
                    detail=detail,
                    source="mechanism_novelty_gate_prompt_parity",
                    attempt=attempt,
                    failure_code=str(parity_feedback.get("failure_code") or ""),
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
                    "Session failed closed because mechanism novelty gate facts were not API-visible to hypothesis generation.",
                    metadata=parity_feedback,
                )
                return self._persist(output, state)
            if len(semantic_rejections) < _MAX_HYPOTHESIS_SEMANTIC_RETRIES:
                rejection = result.to_rejection(hypothesis)
                semantic_rejections.append(
                    _hypothesis_semantic_retry_rejection_payload(rejection, attempt)
                )
                state.note(
                    AgenticProposalPhase.DRAFT_HYPOTHESIS,
                    "Mechanism novelty gate rejected hypothesis; retrying with structured semantic feedback.",
                    metadata={
                        "attempt": attempt,
                        "premise_check": result.premise_check,
                        "failure_category": result.failure_category,
                        "mechanism": result.mechanism,
                        "source": "mechanism_novelty_gate",
                    },
                )
                return None
            return self._mechanism_novelty_failed_output(
                request=request,
                session_id=session_id,
                state=state,
                hypothesis=hypothesis,
                tool_context=tool_context,
                observations=observations,
                evidence_used=tuple(evidence),
            )

    def _mechanism_novelty_failed_output(
            self,
            *,
            request: AgenticProposalRequest,
            session_id: str,
            state: AgenticProposalSessionState,
            hypothesis: HypothesisProposal,
            observations: list[ProposalObservation],
            tool_context: ProposalToolContext | None = None,
            evidence_used: tuple[AgenticEvidenceRef, ...] = (),
        ) -> AgenticProposalOutput | None:
            result = _MECHANISM_NOVELTY_GATE.evaluate(
                hypothesis,
                context=tool_context,
                observations=observations,
            )
            if result is None:
                return None
            if not result.is_hard_block:
                _record_mechanism_novelty_diagnostic(
                    state,
                    hypothesis=hypothesis,
                    result=result,
                    attempt=None,
                    observations=observations,
                )
                return None
            parity_feedback = _mechanism_novelty_gate_prompt_parity_feedback(
                result,
                getattr(state, "_latest_hypothesis_prompt_manifest", None),
                attempt=None,
            )
            if parity_feedback is not None:
                detail = str(parity_feedback.get("reason") or "")
                _record_failure_ledger_entry(
                    state,
                    phase=AgenticProposalPhase.DRAFT_HYPOTHESIS,
                    category=AgenticFailureCategory.CONTRACT_BOUNDARY_FAILURE,
                    detail=detail,
                    source="mechanism_novelty_gate_prompt_parity",
                    failure_code=str(parity_feedback.get("failure_code") or ""),
                )
                output = self._failed_output(
                    request=request,
                    session_id=session_id,
                    status=AgenticProposalStatus.FAILED,
                    termination_reason=AgenticTerminationReason.HYPOTHESIS_GENERATION_FAILED,
                    detail=detail,
                    evidence_used=evidence_used,
                    failure_category=AgenticFailureCategory.CONTRACT_BOUNDARY_FAILURE,
                )
                state.status = output.status
                state.note(
                    AgenticProposalPhase.FINALIZE,
                    "Mechanism novelty rejection withheld because gate facts were not API-visible in the hypothesis prompt.",
                    metadata=parity_feedback,
                )
                return self._persist(output, state)
            rejection = result.to_rejection(hypothesis)
            _record_failure_ledger_entry(
                state,
                phase=AgenticProposalPhase.DRAFT_HYPOTHESIS,
                category=result.failure_category,
                detail=result.reason,
                source="mechanism_novelty_gate",
            )
            output = self._structured_rejection_output(
                request=request,
                session_id=session_id,
                hypothesis=hypothesis,
                rejection=rejection,
                evidence_used=evidence_used,
                self_check=AgenticSelfCheck(schema_valid=True),
            )
            state.status = output.status
            state.note(
                AgenticProposalPhase.FINALIZE,
                "Mechanism novelty gate rejected the solver_design hypothesis before code context.",
                metadata={
                    "premise_check": result.premise_check,
                    "failure_category": result.failure_category,
                    "mechanism": result.mechanism,
                },
            )
            return self._persist(output, state)


def _record_mechanism_novelty_diagnostic(
    state: AgenticProposalSessionState,
    *,
    hypothesis: HypothesisProposal,
    result: Any,
    attempt: int | None,
    observations: list[ProposalObservation] | None = None,
) -> None:
    diagnostic = result.to_diagnostic(hypothesis)
    warning = _mechanism_novelty_warning_payload(diagnostic, attempt=attempt)
    state.note(
        AgenticProposalPhase.DRAFT_HYPOTHESIS,
        "Mechanism novelty diagnostic recorded; continuing without hard novelty block.",
        metadata=_drop_empty_dict(
            {
                "attempt": attempt,
                "result_kind": diagnostic.get("result_kind"),
                "gate_action": diagnostic.get("gate_action"),
                "diagnostic_kind": diagnostic.get("diagnostic_kind"),
                "premise_check": diagnostic.get("premise_check"),
                "failure_category": diagnostic.get("failure_category"),
                "mechanism": diagnostic.get("mechanism"),
                "fact_ids": diagnostic.get("fact_ids"),
                "fact_packet_digest": diagnostic.get("fact_packet_digest"),
                "reason": diagnostic.get("reason"),
                "diagnostic": diagnostic,
                "warning": warning,
            }
        ),
    )
    if observations is not None:
        observations.append(
            ProposalObservation(
                observation_id=(
                    f"mechanism-novelty-diagnostic-{len(observations) + 1:04d}"
                ),
                session_id=state.session_id,
                tool_name="proposal.mechanism_novelty_diagnostic",
                tool_call_id=(
                    f"mechanism-novelty-diagnostic-{len(observations) + 1:04d}"
                ),
                observation_type="diagnostic",
                summary=str(warning.get("summary") or "Mechanism novelty warning."),
                structured_payload=warning,
                exposure_level=ProposalExposureLevel.PUBLIC_SPEC,
                is_error=False,
            )
        )


def _mechanism_novelty_warning_payload(
    diagnostic: Mapping[str, Any],
    *,
    attempt: int | None,
) -> dict[str, Any]:
    diagnostic_kind = str(diagnostic.get("diagnostic_kind") or "").strip()
    mechanism = str(diagnostic.get("mechanism") or "").strip()
    reason = str(diagnostic.get("reason") or "").strip()
    guidance = (
        str(diagnostic.get("allowed_variant_guidance") or "").strip()
        or (
            "Existing near-field mechanism evidence may overlap with this "
            "proposal. Continue only by acknowledging the existing mechanism "
            "and stating the material trigger, scoring, schedule, or behavior "
            "difference; do not change direction merely to satisfy novelty "
            "wording."
        )
    )
    if "material" not in guidance.lower():
        guidance = (
            f"{guidance} Acknowledge the existing mechanism and state the "
            "material trigger, scoring, schedule, or behavior difference."
        )
    return _drop_empty_dict(
        {
            "artifact_kind": "agentic_mechanism_novelty_warning",
            "source": diagnostic.get("source") or "mechanism_novelty_gate",
            "gate_name": diagnostic.get("gate_name"),
            "attempt": attempt,
            "warning_kind": diagnostic_kind or "novelty_warning",
            "diagnostic_kind": diagnostic_kind or "novelty_warning",
            "premise_check": diagnostic.get("premise_check"),
            "failure_category": diagnostic.get("failure_category"),
            "mechanism": mechanism,
            "selected_surface": diagnostic.get("selected_surface"),
            "target_file": diagnostic.get("target_file"),
            "reason": reason,
            "fact_ids": diagnostic.get("fact_ids"),
            "fact_packet_digest": diagnostic.get("fact_packet_digest"),
            "snapshot_digest": diagnostic.get("snapshot_digest"),
            "matched_span": diagnostic.get("matched_span"),
            "summary": (
                f"Novelty warning for {mechanism or 'candidate mechanism'}: "
                "an existing or near-field mechanism may overlap; material "
                "difference should be stated before implementation."
            ),
            "agent_guidance": guidance,
            "blocking": False,
            "quality_block": False,
        }
    )


def _expected_telemetry_guidance_for_hypothesis(
    context: ProposalToolContext | None,
) -> dict[str, Any]:
    if context is None:
        return {}
    surfaces: list[str] = []
    forced = str(getattr(context, "forced_surface", "") or "").strip()
    if forced:
        surfaces.append(forced)
    for surface in getattr(context, "active_problem_boundary_surfaces", ()) or ():
        text = str(surface or "").strip()
        if text and text not in surfaces:
            surfaces.append(text)
    if not surfaces:
        return {}
    templates: dict[str, Any] = {}
    for surface in surfaces[:4]:
        template = expected_telemetry_template(
            problem_spec=getattr(context, "problem_spec", None),
            selected_surface=surface,
            declared_mechanisms=("<mechanism_id>",),
            max_fields_per_category=4,
        )
        if template:
            templates[surface] = template
    if not templates:
        return {}
    return _drop_empty_dict(
        {
            "schema_version": "agentic-expected-telemetry-guidance.v1",
            "source": "adapter_declared_runtime_fields",
            "templates_by_surface": templates,
            "rule": (
                "Use only these top-level categories: activity, activation, "
                "effect, budget. Replace <mechanism_id> or {mechanism} with the "
                "exact mechanism_changes id before finalizing the hypothesis."
            ),
            "preview_helper": (
                "Use proposal.schema_preview if unsure; it returns the exact "
                "C11_expected_telemetry repair template without lowering schema "
                "strictness."
            ),
        }
    )


def _mechanism_novelty_gate_prompt_parity_feedback(
    result: Any,
    manifest: Mapping[str, Any] | None,
    *,
    attempt: int | None,
) -> dict[str, Any] | None:
    """Return retry feedback when a gate rejection used non-visible facts."""
    fact_packet_digest = str(getattr(result, "fact_packet_digest", "") or "").strip()
    if not fact_packet_digest:
        return None
    manifest_map = manifest if isinstance(manifest, Mapping) else {}
    statuses = manifest_map.get("section_statuses")
    facts_status = (
        statuses.get("active_algorithm_facts")
        if isinstance(statuses, Mapping)
        else None
    )
    if not isinstance(facts_status, Mapping):
        return _gate_prompt_parity_payload(
            fact_packet_digest=fact_packet_digest,
            prompt_fact_packet_digest="",
            prompt_status="missing",
            attempt=attempt,
        )
    prompt_fact_packet_digest = str(
        facts_status.get("fact_packet_digest") or ""
    ).strip()
    prompt_status = str(facts_status.get("status") or "").strip() or "missing"
    if (
        prompt_status == "included"
        and prompt_fact_packet_digest
        and prompt_fact_packet_digest == fact_packet_digest
    ):
        return None
    return _gate_prompt_parity_payload(
        fact_packet_digest=fact_packet_digest,
        prompt_fact_packet_digest=prompt_fact_packet_digest,
        prompt_status=prompt_status,
        attempt=attempt,
    )


def _gate_prompt_parity_payload(
    *,
    fact_packet_digest: str,
    prompt_fact_packet_digest: str,
    prompt_status: str,
    attempt: int | None,
) -> dict[str, Any]:
    return {
        "source": "mechanism_novelty_gate_prompt_parity",
        "failure_code": "gate_prompt_parity_retry_required",
        "failure_category": "contract_boundary_failure",
        "agent_block_reason": "framework_control",
        "fact_packet_digest": fact_packet_digest,
        "prompt_fact_packet_digest": prompt_fact_packet_digest,
        "prompt_fact_status": prompt_status,
        "attempt": attempt,
        "reason": (
            "Mechanism novelty gate prepared a rejection using active algorithm "
            f"fact_packet_digest={fact_packet_digest}, but that exact fact packet "
            f"was not included in the API-visible hypothesis prompt "
            f"(prompt_status={prompt_status!r}, "
            f"prompt_fact_packet_digest={prompt_fact_packet_digest!r}). Retry "
            "only after the same adapter-owned active_algorithm_facts packet is "
            "rendered to the agent before hypothesis generation; a gate must not "
            "be better informed than the proposal agent."
        ),
        "retry_constraint": (
            "Use the now-visible active_algorithm_facts packet to verify the "
            "premise before restating the same novelty claim."
        ),
    }


def _hypothesis_preview_retry_feedback(
    preview_observations: list[ProposalObservation],
    *,
    detail: str,
    attempt: int,
    previous_hypothesis: HypothesisProposal,
) -> dict[str, Any] | None:
    schema_observation = _latest_tool_observation(
        preview_observations,
        "proposal.schema_preview",
    )
    if schema_observation is None or schema_observation.is_error:
        return None
    payload = schema_observation.structured_payload
    if not isinstance(payload, Mapping):
        return None
    hypothesis = payload.get("hypothesis")
    if not isinstance(hypothesis, Mapping):
        return None
    same_mechanism_feedback = _same_mechanism_preview_retry_feedback(
        hypothesis,
        detail=detail,
        attempt=attempt,
    )
    if same_mechanism_feedback is not None:
        return same_mechanism_feedback
    novelty_feedback = _novelty_signature_preview_retry_feedback(
        hypothesis,
        detail=detail,
        attempt=attempt,
        previous_hypothesis=previous_hypothesis,
    )
    if novelty_feedback is not None:
        return novelty_feedback
    telemetry = hypothesis.get("expected_telemetry_contract")
    if not isinstance(telemetry, Mapping):
        return None
    problem_telemetry = hypothesis.get("problem_expected_telemetry_preview")
    if not isinstance(problem_telemetry, Mapping):
        problem_telemetry = {}
    c11_detail = _failed_schema_check_detail(
        hypothesis,
        "C11_expected_telemetry",
    )
    telemetry_detail = str(
        telemetry.get("detail_full") or telemetry.get("detail") or ""
    ).strip()
    problem_telemetry_failed = problem_telemetry.get("passed") is False
    if (
        bool(telemetry.get("passed")) is not False
        and not c11_detail
        and not problem_telemetry_failed
    ):
        return None
    if (
        "C11_expected_telemetry" not in (c11_detail or detail)
        and str(problem_telemetry.get("failure_code") or "")
        != "C11_expected_telemetry"
    ):
        return None

    preserve_hypothesis = _hypothesis_retry_anchor(previous_hypothesis)
    protected_identity = _schema_retry_protected_identity(preserve_hypothesis)
    return _expected_telemetry_retry_feedback(
        hypothesis,
        telemetry,
        problem_telemetry,
        detail=detail,
        attempt=attempt,
        c11_detail=c11_detail,
        telemetry_detail=telemetry_detail,
        preserve_hypothesis=preserve_hypothesis,
        protected_identity=protected_identity,
    )


def _same_mechanism_preview_retry_feedback(
    hypothesis: Mapping[str, Any],
    *,
    detail: str,
    attempt: int,
) -> dict[str, Any] | None:
    guard = hypothesis.get("branch_continuation_guard")
    if not isinstance(guard, Mapping):
        return None
    if guard.get("passed") is not False:
        return None
    if str(guard.get("failure_code") or "") != "same_mechanism_only_violation":
        return None
    protected_ids = [
        str(item).strip()
        for item in (guard.get("protected_mechanism_ids") or ())
        if str(item).strip()
    ]
    proposed_ids = [
        str(item).strip()
        for item in (guard.get("proposed_mechanism_ids") or ())
        if str(item).strip()
    ]
    allowed_ids = [
        str(item).strip()
        for item in (guard.get("allowed_mechanism_ids") or protected_ids)
        if str(item).strip()
    ]
    allowed_actions = [
        str(item).strip()
        for item in (guard.get("allowed_actions") or ())
        if str(item).strip()
    ]
    return _drop_empty_dict(
        {
            "attempt": attempt,
            "attempt_kind": "schema_accounting_repair",
            "repair_classification": "branch_followup_schema_repair",
            "source": "hypothesis_preview_gate",
            "gate_name": "proposal.schema_preview",
            "failure_code": "same_mechanism_only_violation",
            "check": "same_mechanism_only_branch_guard",
            "failure_category": AgenticFailureCategory.CONTRACT_BOUNDARY_FAILURE.value,
            "reason": _limit_string(
                str(guard.get("reason") or "") or detail,
                1000,
            ),
            "branch_followup_policy": guard.get("branch_followup_policy"),
            "hypothesis_generation_mode": guard.get("hypothesis_generation_mode"),
            "protected_mechanism_ids": protected_ids,
            "allowed_mechanism_ids": allowed_ids,
            "proposed_mechanism_ids": proposed_ids,
            "forbidden_mechanism_policy": guard.get(
                "forbidden_mechanism_policy"
            ),
            "allowed_actions": allowed_actions,
            "allowed_repair_shape": guard.get("allowed_repair_shape"),
            "candidate_routing": guard.get("candidate_routing"),
            "proposal_failure_accounting": guard.get(
                "proposal_failure_accounting"
            ),
            "clean_fork_signal": guard.get("clean_fork_signal"),
            "protected_identity": {
                "protected_mechanism_ids": protected_ids,
                "allowed_mechanism_ids": allowed_ids,
                "allowed_actions": allowed_actions,
            },
            "final_task": (
                "Rewrite the hypothesis as a same-mechanism follow-up on a "
                "protected id. Do not introduce unrelated mechanism ids."
            ),
            "retry_constraint": (
                "Use only protected_mechanism_ids in mechanism_changes and "
                "keep the work to tune, integrate, repair, parameterize, or "
                "telemetry wiring within that protected mechanism. If the "
                "intended idea is a new mechanism, stop this branch attempt "
                "and use a clean branch/fork before generation. Treat that as "
                "a branch-routing signal, not as a code or screening failure."
            ),
        }
    )


def _novelty_signature_preview_retry_feedback(
    hypothesis: Mapping[str, Any],
    *,
    detail: str,
    attempt: int,
    previous_hypothesis: HypothesisProposal,
) -> dict[str, Any] | None:
    guidance = hypothesis.get("novelty_signature_guidance")
    if not isinstance(guidance, Mapping):
        return None
    missing_fields = [
        str(field).strip()
        for field in guidance.get("missing_fields") or ()
        if str(field).strip()
    ]
    if not missing_fields:
        return None
    repair_template = guidance.get("repair_template")
    if not isinstance(repair_template, Mapping):
        return None
    anchor = _hypothesis_retry_anchor(previous_hypothesis)
    return _drop_empty_dict(
        {
            "attempt": attempt,
            "source": "hypothesis_preview_gate",
            "gate_name": "proposal.schema_preview",
            "failure_code": "novelty_signature_missing_fields",
            "check": "C10_novelty",
            "failure_category": AgenticFailureCategory.CONTRACT_BOUNDARY_FAILURE.value,
            "reason": _limit_string(
                str(guidance.get("detail") or "") or detail,
                1000,
            ),
            "missing_fields": missing_fields,
            "required_fields": list(guidance.get("signature_fields") or ()),
            "repair_template": repair_template,
            "required_template": repair_template.get("required_template"),
            "mechanism_id_consistency": repair_template.get(
                "mechanism_id_consistency"
            ),
            "preserve_hypothesis": anchor,
            "protected_identity": _schema_retry_protected_identity(anchor),
            "retry_constraint": (
                "Repair only novelty_signature/schema fields named by the C10 "
                "template. Preserve the prior action, target_file, "
                "mechanism_changes ids/change_types, and telemetry activation "
                "mechanism refs; do not switch mechanisms or targets for a "
                "C10 missing-fields retry. If a strategy is unchanged, state "
                "unchanged and name the active solver map or baseline component "
                "used as the reference."
            ),
        }
    )


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


def _hypothesis_prompt_call_kind(
    *,
    attempt: int,
    semantic_rejections: list[Mapping[str, Any]],
    preview_rejections: list[Mapping[str, Any]],
    grounding_rejections: list[Mapping[str, Any]] | None = None,
) -> str:
    if attempt <= 1:
        return "hypothesis"
    previous_attempt = attempt - 1
    grounding_rejections = grounding_rejections or []
    if grounding_rejections and int(grounding_rejections[-1].get("attempt") or 0) == (
        previous_attempt
    ):
        return "hypothesis_grounding_retry"
    if preview_rejections and int(preview_rejections[-1].get("attempt") or 0) == (
        previous_attempt
    ):
        return "hypothesis_preview_retry"
    if semantic_rejections and int(semantic_rejections[-1].get("attempt") or 0) == (
        previous_attempt
    ):
        return "hypothesis_semantic_retry"
    if preview_rejections:
        return "hypothesis_preview_retry"
    if semantic_rejections:
        return "hypothesis_semantic_retry"
    if grounding_rejections:
        return "hypothesis_grounding_retry"
    return "hypothesis_retry"


def _latest_tool_observation(
    observations: list[ProposalObservation],
    tool_name: str,
) -> ProposalObservation | None:
    for observation in reversed(observations):
        if observation.tool_name == tool_name:
            return observation
    return None


def _failed_schema_check_detail(
    section: Mapping[str, Any],
    check_name: str,
) -> str:
    checks = section.get("checks")
    if not isinstance(checks, list):
        return ""
    for check in checks:
        if not isinstance(check, Mapping):
            continue
        if str(check.get("name") or "") != check_name:
            continue
        if bool(check.get("passed")):
            continue
        detail = str(check.get("detail") or "").strip()
        return f"{check_name}: {detail}" if detail else check_name
    return ""


def _compact_preview_list(
    value: Any,
    *,
    limit: int,
    max_chars: int,
) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    return [
        text
        for text in (
            _limit_string(str(item).strip(), max_chars)
            for item in list(value)[: max(0, limit)]
        )
        if text
    ]
