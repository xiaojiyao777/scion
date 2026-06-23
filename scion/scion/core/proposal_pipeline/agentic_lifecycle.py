"""Agentic hypothesis/code orchestration and failure lifecycle routing."""
from __future__ import annotations

import logging
from dataclasses import replace
from typing import Any, Mapping

from scion.core.models import (
    Branch,
    ChampionState,
    FailureEvent,
    HypothesisProposal,
    HypothesisRecord,
    PatchProposal,
)
from scion.core.research_process_guidance_audit import (
    extract_research_process_guidance_audit,
)
from scion.core.status_reporter import is_provider_balance_exhausted_detail
from scion.proposal.agentic_session import (
    AgenticFailureCategory,
    AgenticProposalOutput,
    AgenticProposalStatus,
    AgenticTerminationReason,
)
from scion.proposal.context.branch_followup import (
    BRANCH_FOLLOWUP_POLICY_VIOLATION,
    validate_weak_positive_followup_hypothesis,
)
from scion.proposal.engine import ProposalValidationError
from scion.proposal.llm_client import (
    LLMBalanceError,
    LLMFormatError,
    LLMRateLimitError,
    LLMRetryExhaustedError,
    LLMTimeoutError,
    LLMTransientProviderError,
    is_llm_transient_api_error,
)
from scion.proposal.negative_facts import render_negative_fact_block

from .boundaries import _active_problem_boundary_surfaces_for_runtime
from .classification import (
    AgenticFailureRoutingSignal,
    _agentic_failure_routing_signal,
)
from .constants import FRAMEWORK_CONTROL_FAILURE
from .utils import _agentic_value, _now_iso

logger = logging.getLogger(__name__)


class AgenticLifecycleMixin:
    def _generate_agentic_hypothesis(
        self,
        *,
        branch: Branch,
        champion: ChampionState,
        context: dict[str, Any],
    ) -> tuple[HypothesisProposal | None, HypothesisRecord | None]:
        bid = branch.branch_id
        try:
            request = self._with_agentic_resume_context(
                self._build_agentic_request(
                    branch=branch,
                    champion=champion,
                    hypothesis_context=context,
                )
            )
            output = self._recover_agentic_partial_hypothesis_output(request)
            if output is None:
                output = self._get_agentic_session().run(request)
        except LLMBalanceError as exc:
            logger.critical(
                "Branch %s: API balance exhausted in agentic proposal session: %s",
                bid,
                exc,
            )
            self.hypothesis_failure_details[bid] = str(exc)
            self.mark_balance_exhausted()
            self.circuit_breaker.record_failure(str(exc))
            return None, None
        except (
            LLMRetryExhaustedError,
            LLMFormatError,
            LLMTimeoutError,
            LLMTransientProviderError,
            LLMRateLimitError,
            ProposalValidationError,
            PermissionError,
        ) as exc:
            return self._record_agentic_failure(branch, str(exc), None)

        output = self._validate_and_sanitize_agentic_output(
            branch=branch,
            champion=champion,
            output=output,
            forced_surface=(
                request.tool_context.forced_surface if request.tool_context else None
            ),
            forced_action=(
                request.tool_context.forced_action if request.tool_context else None
            ),
            forced_target_file=(
                request.tool_context.forced_target_file
                if request.tool_context
                else None
            ),
            active_problem_boundary_surfaces=(
                request.tool_context.active_problem_boundary_surfaces
                if request.tool_context
                else ()
            ),
        )
        output = self._sanitize_pre_contract_agentic_output(output)
        if (
            output.status != AgenticProposalStatus.FAILED
            and output.hypothesis is not None
        ):
            followup_check = validate_weak_positive_followup_hypothesis(
                branch,
                output.hypothesis,
                step_history=self.step_history,
            )
            if not followup_check.allowed:
                output = replace(
                    output,
                    status=AgenticProposalStatus.FAILED,
                    termination_reason=(
                        AgenticTerminationReason.HYPOTHESIS_APPROVAL_FAILED
                    ),
                    failure_detail=followup_check.detail,
                    failure_category=AgenticFailureCategory.PREMISE_CONTRADICTED,
                    structured_rejection={
                        **followup_check.structured_rejection(),
                        "failure_code": BRANCH_FOLLOWUP_POLICY_VIOLATION,
                    },
                )
        self._record_agentic_lineage_event(output)
        self._record_agentic_session_ref(
            output,
            guidance_audit=extract_research_process_guidance_audit(
                context.get("branch_followup_policy_payload")
            ),
        )
        self.agentic_outputs[bid] = output
        if output.status == AgenticProposalStatus.FAILED:
            return self._record_agentic_failure(
                branch,
                self._agentic_failure_detail(output),
                output,
            )
        if output.hypothesis is None:
            return self._record_agentic_failure(
                branch,
                self._agentic_failure_detail(output),
                output,
            )

        self.circuit_breaker.record_success()
        self._stage_agentic_quality_feedback_for_code(bid)
        return output.hypothesis, self._hypothesis_record(branch, output.hypothesis)

    def _generate_agentic_code(
        self,
        *,
        branch: Branch,
        hypothesis: HypothesisProposal,
        prior_failure: str | None,
    ) -> PatchProposal | None:
        bid = branch.branch_id
        output = self.agentic_outputs.pop(bid, None)
        if output is not None:
            output = self._validate_and_sanitize_agentic_output(
                branch=branch,
                champion=self._champion_snapshot(),
                output=output,
                active_problem_boundary_surfaces=(
                    _active_problem_boundary_surfaces_for_runtime(
                        self.problem_runtime,
                    )
                ),
                approved_hypothesis=hypothesis,
            )
            if output.status == AgenticProposalStatus.FAILED:
                detail = self._agentic_failure_detail(output)
                logger.warning(
                    "Branch %s: agentic output rejected before code generation: %s",
                    bid,
                    detail,
                )
                self._record_agentic_code_failure(
                    branch,
                    detail=detail,
                    output=output,
                )
                return None
            if output.is_completed:
                self.circuit_breaker.record_success()
                self._clear_agentic_quality_feedback(bid)
                self._clear_agentic_code_quality_feedback(bid)
                return output.patch
            if not self._agentic_output_can_continue(output, hypothesis):
                detail = self._agentic_failure_detail(output)
                logger.warning(
                    "Branch %s: agentic proposal session ended without patch: %s",
                    bid,
                    detail,
                )
                self._record_agentic_code_failure(
                    branch,
                    detail=detail,
                    output=output,
                )
                return None

        if output is None or self._agentic_output_can_continue(output, hypothesis):
            try:
                request = self._with_agentic_resume_context(
                    self._build_agentic_request(
                        branch=branch,
                        champion=self._champion_snapshot(),
                        hypothesis_context=None,
                        prior_failure=prior_failure,
                        approved_hypothesis=hypothesis,
                    )
                )
                output = self._get_agentic_session().run(request)
            except LLMBalanceError as exc:
                logger.critical(
                    "Branch %s: API balance exhausted in agentic code session: %s",
                    bid,
                    exc,
                )
                self.hypothesis_failure_details[bid] = str(exc)
                self.mark_balance_exhausted()
                self.circuit_breaker.record_failure(str(exc))
                return None
            except (
                LLMRetryExhaustedError,
                LLMFormatError,
                LLMTimeoutError,
                LLMTransientProviderError,
                LLMRateLimitError,
                ProposalValidationError,
                PermissionError,
            ) as exc:
                logger.warning("Branch %s: agentic code session error: %s", bid, exc)
                self.hypothesis_failure_details[bid] = str(exc)
                category = "infra" if is_llm_transient_api_error(exc) else "proposal"
                self.handle_failure(
                    branch,
                    FailureEvent(category=category, detail=str(exc)),
                )
                if category != "infra":
                    self.circuit_breaker.record_failure(str(exc))
                return None

        output = self._validate_and_sanitize_agentic_output(
            branch=branch,
            champion=self._champion_snapshot(),
            output=output,
            active_problem_boundary_surfaces=(
                request.tool_context.active_problem_boundary_surfaces
                if request.tool_context
                else ()
            ),
            approved_hypothesis=hypothesis,
        )
        self._record_agentic_lineage_event(output)
        self._record_agentic_session_ref(output)
        if output.status == AgenticProposalStatus.FAILED:
            detail = self._agentic_failure_detail(output)
            logger.warning(
                "Branch %s: agentic output rejected before code generation: %s",
                bid,
                detail,
            )
            self._record_agentic_code_failure(
                branch,
                detail=detail,
                output=output,
            )
            return None

        if output.is_completed:
            self.circuit_breaker.record_success()
            self._clear_agentic_quality_feedback(bid)
            self._clear_agentic_code_quality_feedback(bid)
            return output.patch

        detail = self._agentic_failure_detail(output)
        logger.warning(
            "Branch %s: agentic proposal session ended without patch: %s",
            bid,
            detail,
        )
        self._record_agentic_code_failure(
            branch,
            detail=detail,
            output=output,
        )
        return None

    def _record_agentic_failure(
        self,
        branch: Branch,
        detail: str,
        output: AgenticProposalOutput | None,
    ) -> tuple[None, None]:
        logger.warning(
            "Branch %s: agentic proposal session failed: %s",
            branch.branch_id,
            detail,
        )
        if output is not None:
            self.agentic_outputs[branch.branch_id] = output
        self.hypothesis_failure_details[branch.branch_id] = detail
        if is_provider_balance_exhausted_detail(detail):
            self.mark_balance_exhausted()
            self.circuit_breaker.record_failure(detail)
            return None, None
        routing_signal = _agentic_failure_routing_signal(output, detail)
        self._record_agentic_failure_lifecycle(
            branch,
            detail,
            output,
            routing_signal,
        )
        if output is not None and routing_signal.quality_blocked:
            self._remember_agentic_quality_block(branch, detail, output)
            return None, None
        if not routing_signal.record_circuit_failure:
            return None, None
        self.circuit_breaker.record_failure(detail)
        return None, None

    def _record_agentic_code_failure(
        self,
        branch: Branch,
        *,
        detail: str,
        output: AgenticProposalOutput | None,
    ) -> None:
        self.hypothesis_failure_details[branch.branch_id] = detail
        if is_provider_balance_exhausted_detail(detail):
            self.mark_balance_exhausted()
            self.circuit_breaker.record_failure(detail)
            return
        routing_signal = _agentic_failure_routing_signal(output, detail)
        self._record_agentic_failure_lifecycle(
            branch,
            detail,
            output,
            routing_signal,
        )
        if output is not None and routing_signal.quality_blocked:
            self._remember_agentic_quality_block(branch, detail, output)
            return
        if not routing_signal.record_circuit_failure:
            return
        self.circuit_breaker.record_failure(detail)

    def _record_agentic_failure_lifecycle(
        self,
        branch: Branch,
        detail: str,
        output: AgenticProposalOutput | None,
        routing_signal: AgenticFailureRoutingSignal | None = None,
    ) -> None:
        if routing_signal is None:
            routing_signal = _agentic_failure_routing_signal(output, detail)
        if routing_signal.quality_blocked:
            logger.info(
                "Branch %s: agentic quality block recorded outside infra/proposal streaks: %s",
                branch.branch_id,
                detail,
            )
            return
        if routing_signal.repair_policy_violation:
            logger.info(
                "Branch %s: agentic repair policy block recorded outside "
                "infra/proposal streaks: %s",
                branch.branch_id,
                detail,
            )
            return
        if routing_signal.lifecycle_category == FRAMEWORK_CONTROL_FAILURE:
            logger.info(
                "Branch %s: agentic control timeout recorded outside proposal streaks: %s",
                branch.branch_id,
                detail,
            )
            self.handle_failure(
                branch,
                FailureEvent(category=FRAMEWORK_CONTROL_FAILURE, detail=detail),
            )
            return
        if routing_signal.lifecycle_category == "infra":
            logger.info(
                "Branch %s: agentic transient LLM API failure routed as infra: %s",
                branch.branch_id,
                detail,
            )
            self.handle_failure(branch, FailureEvent(category="infra", detail=detail))
            return
        self.handle_failure(branch, FailureEvent(category="proposal", detail=detail))

    def _remember_agentic_quality_block(
        self,
        branch: Branch,
        detail: str,
        output: AgenticProposalOutput,
    ) -> None:
        rejection = (
            dict(output.structured_rejection)
            if isinstance(output.structured_rejection, dict)
            else {}
        )
        entry: dict[str, Any] = {
            "source": "agentic_quality_block",
            "recorded_at": _now_iso(),
            "session_id": output.session_id,
            "status": _agentic_value(output.status),
            "termination_reason": _agentic_value(output.termination_reason),
            "failure_category": _agentic_value(output.failure_category),
            "failure_code": str(
                rejection.get("failure_code")
                or rejection.get("code")
                or output.failure_category
                or ""
            ),
            "agent_block_reason": str(
                rejection.get("agent_block_reason") or "agent_quality_blocked"
            ),
            "detail": str(detail or "")[:1600],
        }
        mechanism = _mechanism_id_from_agentic_hypothesis(output.hypothesis)
        if mechanism:
            entry["mechanism"] = mechanism
        for key in (
            "gate_name",
            "mechanism",
            "premise_check",
            "reason",
            "retry_constraint",
            "repair_template",
            "fact_ids",
            "fact_packet_digest",
            "source_fact_digest",
            "provenance",
            "fact_provenance",
            "snapshot_digest",
            "variant_allowed",
            "contradicted_span",
            "matched_span",
            "allowed_variant_guidance",
            "missing_claims",
            "missing_code_elements",
            "changed_files",
        ):
            value = rejection.get(key)
            if value not in (None, "", [], {}):
                entry[key] = value
        bucket = self.agentic_quality_feedback.setdefault(branch.branch_id, [])
        bucket.append(entry)
        del bucket[:-3]

    def _attach_agentic_quality_feedback_context(
        self,
        context: dict[str, Any],
        branch_id: str,
        *,
        phase: str,
    ) -> list[Mapping[str, Any]]:
        include_staged_code_feedback = phase == "code"
        quality_feedback = self._agentic_quality_feedback_for_context(
            branch_id,
            include_staged_code_feedback=include_staged_code_feedback,
        )
        if not quality_feedback:
            return []
        context["agentic_prior_quality_blocks"] = quality_feedback
        if phase == "code":
            context["agentic_prior_quality_block_rule"] = (
                "Previous agentic proposal attempts on this branch were blocked "
                "before protocol because the candidate crossed a hard boundary, "
                "objective, contract, schema, or activation gate. Treat these "
                "as hard code repair constraints for this patch: implement the "
                "cited retry_constraint, gate, failure_code, or missing "
                "diagnostic in code before emitting a near-same mechanism. If "
                "the approved hypothesis intentionally moved away from the "
                "blocked mechanism, state that difference in premise_check_reason "
                "and avoid repeating the cited failure pattern."
            )
        else:
            context["agentic_prior_quality_block_rule"] = (
                "Previous agentic proposal attempts on this branch were blocked "
                "before code because the candidate crossed a hard boundary, "
                "objective, contract, schema, or activation gate. Treat these "
                "as hard research constraints: repair the cited contract issue "
                "before continuing near the same mechanism, and use the cited "
                "source/gate/failure_code/reason as the grounding evidence."
            )
        negative_fact_block = render_negative_fact_block(
            prior_quality_blocks=quality_feedback
        )
        if negative_fact_block:
            existing = str(context.get("agentic_negative_fact_block") or "").strip()
            context["agentic_negative_fact_block"] = (
                f"{existing}\n{negative_fact_block}"
                if existing
                else negative_fact_block
            )
        return quality_feedback

    def _stage_agentic_quality_feedback_for_code(self, branch_id: str) -> None:
        quality_feedback = self._agentic_quality_feedback_for_context(branch_id)
        self._clear_agentic_quality_feedback(branch_id)
        if not quality_feedback:
            self._clear_agentic_code_quality_feedback(branch_id)
            return
        self.agentic_code_quality_feedback[branch_id] = quality_feedback

    def _agentic_quality_feedback_for_context(
        self,
        branch_id: str,
        *,
        include_staged_code_feedback: bool = False,
    ) -> list[Mapping[str, Any]]:
        buckets: list[list[Mapping[str, Any]]] = [
            list(self.agentic_quality_feedback.get(branch_id, ()))
        ]
        if include_staged_code_feedback:
            buckets.append(list(self.agentic_code_quality_feedback.get(branch_id, ())))
        feedback: list[Mapping[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()
        for bucket in buckets:
            for item in bucket:
                key = (
                    str(item.get("session_id") or ""),
                    str(item.get("failure_code") or ""),
                    str(item.get("recorded_at") or ""),
                )
                if key in seen:
                    continue
                seen.add(key)
                feedback.append(item)
        return feedback

    def _clear_agentic_quality_feedback(self, branch_id: str) -> None:
        self.agentic_quality_feedback.pop(branch_id, None)

    def _clear_agentic_code_quality_feedback(self, branch_id: str) -> None:
        self.agentic_code_quality_feedback.pop(branch_id, None)


def _mechanism_id_from_agentic_hypothesis(
    hypothesis: HypothesisProposal | None,
) -> str:
    if hypothesis is None:
        return ""
    for change in getattr(hypothesis, "mechanism_changes", ()) or ():
        value = (
            change.get("id")
            if isinstance(change, dict)
            else getattr(change, "id", None)
        )
        text = str(value or "").strip()
        if text:
            return text
    signature = getattr(hypothesis, "novelty_signature", None)
    if isinstance(signature, dict):
        for key in ("mechanism_id", "improvement_strategy", "algorithm_family"):
            text = str(signature.get(key) or "").strip()
            if text:
                return text
    return str(getattr(hypothesis, "change_locus", "") or "").strip()
