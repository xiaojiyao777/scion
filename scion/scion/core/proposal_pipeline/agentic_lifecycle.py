"""Agentic hypothesis/code orchestration and failure lifecycle routing."""
from __future__ import annotations

import logging
from typing import Any

from scion.core.models import (
    Branch,
    ChampionState,
    FailureEvent,
    HypothesisProposal,
    HypothesisRecord,
    PatchProposal,
)
from scion.core.status_reporter import is_provider_balance_exhausted_detail
from scion.proposal.agentic_session import (
    AgenticProposalOutput,
    AgenticProposalStatus,
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

from .boundaries import _active_problem_boundary_surfaces_for_runtime
from .classification import (
    _agentic_detail_is_framework_boundary,
    _agentic_output_is_llm_transient_api_error,
    _agentic_output_is_control_timeout,
    _agentic_output_is_quality_blocked,
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
        self._record_agentic_lineage_event(output)
        self._record_agentic_session_ref(output)
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
        self._clear_agentic_quality_feedback(bid)
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
        self._record_agentic_failure_lifecycle(branch, detail, output)
        if output is not None and _agentic_output_is_quality_blocked(output):
            self._remember_agentic_quality_block(branch, detail, output)
            return None, None
        if _agentic_detail_is_framework_boundary(detail):
            return None, None
        if _agentic_output_is_control_timeout(output, detail):
            return None, None
        if _agentic_output_is_llm_transient_api_error(output, detail):
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
        self._record_agentic_failure_lifecycle(branch, detail, output)
        if output is not None and _agentic_output_is_quality_blocked(output):
            self._remember_agentic_quality_block(branch, detail, output)
            return
        if _agentic_detail_is_framework_boundary(detail):
            return
        if _agentic_output_is_control_timeout(output, detail):
            return
        if _agentic_output_is_llm_transient_api_error(output, detail):
            return
        self.circuit_breaker.record_failure(detail)

    def _record_agentic_failure_lifecycle(
        self,
        branch: Branch,
        detail: str,
        output: AgenticProposalOutput | None,
    ) -> None:
        if output is not None and _agentic_output_is_quality_blocked(output):
            logger.info(
                "Branch %s: agentic quality block recorded outside infra/proposal streaks: %s",
                branch.branch_id,
                detail,
            )
            return
        if _agentic_output_is_control_timeout(output, detail):
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
        if _agentic_output_is_llm_transient_api_error(output, detail):
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
        for key in (
            "gate_name",
            "mechanism",
            "premise_check",
            "reason",
            "retry_constraint",
            "fact_ids",
            "fact_packet_digest",
            "source_fact_digest",
            "provenance",
        ):
            value = rejection.get(key)
            if value not in (None, "", [], {}):
                entry[key] = value
        bucket = self.agentic_quality_feedback.setdefault(branch.branch_id, [])
        bucket.append(entry)
        del bucket[:-3]

    def _agentic_quality_feedback_for_context(
        self,
        branch_id: str,
    ) -> list[Mapping[str, Any]]:
        return list(self.agentic_quality_feedback.get(branch_id, ()))

    def _clear_agentic_quality_feedback(self, branch_id: str) -> None:
        self.agentic_quality_feedback.pop(branch_id, None)
