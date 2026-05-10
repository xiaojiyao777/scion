"""LLM proposal lifecycle service for campaign explore steps."""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any, Callable, Mapping, MutableMapping, Protocol

from scion.core.models import (
    Branch,
    ChampionState,
    FailureEvent,
    HypothesisProposal,
    HypothesisRecord,
    PatchProposal,
    StepRecord,
    VerificationResult,
)
from scion.proposal.agentic_session import (
    AgenticProposalOutput,
    AgenticProposalRequest,
    AgenticProposalSession,
    AgenticProposalStatus,
    AgenticSessionStore,
    AgenticTerminationReason,
    AgenticToolLoopConfig,
    FileAgenticSessionArtifactStore,
    compute_agentic_idempotency_key,
    ensure_agentic_output_audit_metadata,
    resume_from_artifact,
)
from scion.proposal.engine import ProposalValidationError
from scion.proposal.llm_client import (
    LLMBalanceError,
    LLMFormatError,
    LLMRetryExhaustedError,
    LLMTimeoutError,
)
from scion.proposal.tools import (
    ContextExposurePolicy,
    ProposalToolContext,
    ProposalToolRegistry,
)

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now().isoformat()


def _json_dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def _runtime_attr(runtime: Any, name: str) -> Any:
    try:
        return getattr(runtime, name)
    except Exception:
        return None


class CreativeLayerLike(Protocol):
    def generate_hypothesis(self, context: dict[str, Any]) -> HypothesisProposal:
        ...

    def generate_code(self, context: dict[str, Any]) -> PatchProposal:
        ...

    def fix_code(self, context: dict[str, Any]) -> PatchProposal | None:
        ...


class ProblemRuntimeLike(Protocol):
    def build_hypothesis_context(self, **kwargs: Any) -> dict[str, Any]:
        ...

    def build_code_context(self, **kwargs: Any) -> dict[str, Any]:
        ...

    def build_fix_context(self, **kwargs: Any) -> dict[str, Any]:
        ...


class AgenticProposalSessionLike(Protocol):
    def run(self, request: AgenticProposalRequest) -> AgenticProposalOutput:
        ...


class BranchControllerLike(Protocol):
    def get_active_branches(self) -> list[Branch]:
        ...


class HypothesisStoreLike(Protocol):
    def get_by_status(self, status: str) -> list[HypothesisRecord]:
        ...


class ClassifierLike(Protocol):
    def classify(self, text: str) -> Any:
        ...


class CircuitBreakerLike(Protocol):
    def record_success(self) -> None:
        ...

    def record_failure(self, detail: str) -> bool:
        ...


@dataclass
class ProposalPipeline:
    """Own Round 1/Round 2/fix LLM proposal interactions.

    The service may call the injected failure handler for proposal failures, but
    it does not mutate branch promotion/evaluation state. CampaignManager keeps
    orchestration; this class owns LLM context construction and tainted proposal
    parsing boundaries.
    """

    creative: CreativeLayerLike
    problem_runtime: ProblemRuntimeLike
    classifier: ClassifierLike
    branch_controller: BranchControllerLike
    hypothesis_store: HypothesisStoreLike
    branch_workspaces: Mapping[str, str]
    champion_lock: Any
    get_champion: Callable[[], ChampionState]
    step_history: list[StepRecord]
    failure_streak: MutableMapping[str, int]
    consume_forced_locus: Callable[[], str | None]
    search_memory: Any
    get_saturation_analyzer: Callable[[], Any]
    get_baseline_metrics: Callable[[], dict[str, float] | None]
    get_latest_weight_opt_result: Callable[[], Any]
    research_log: Any
    handle_failure: Callable[[Branch, FailureEvent], None]
    circuit_breaker: CircuitBreakerLike
    mark_balance_exhausted: Callable[[], None]
    hypothesis_failure_details: MutableMapping[str, str] = field(default_factory=dict)
    use_agentic_proposal: bool = False
    agentic_session: AgenticProposalSessionLike | None = None
    agentic_artifact_dir: str | None = None
    agentic_session_timeout_sec: float | None = None
    lineage_registry: Any | None = None
    campaign_id: str = ""
    problem_id: str | None = None
    problem_spec_hash: str | None = None
    persistent_forced_locus: str | None = None
    forced_surface_action: str | None = None
    forced_surface_target_file: str | None = None
    forced_surface_diagnostic: bool = False
    agentic_outputs: MutableMapping[str, AgenticProposalOutput] = field(
        default_factory=dict
    )
    agentic_session_refs: MutableMapping[str, Mapping[str, Any]] = field(
        default_factory=dict
    )
    agentic_recovery_reports: MutableMapping[str, Mapping[str, Any]] = field(
        default_factory=dict
    )

    def generate_hypothesis(
        self,
        branch: Branch,
    ) -> tuple[HypothesisProposal | None, HypothesisRecord | None]:
        bid = branch.branch_id
        self.hypothesis_failure_details.pop(bid, None)
        siblings = [
            b for b in self.branch_controller.get_active_branches()
            if b.branch_id != bid
        ]
        branch_workspace = self.branch_workspaces.get(bid)
        champ_snapshot = self._champion_snapshot()
        transient_forced_locus = self.consume_forced_locus()
        forced_locus = self.persistent_forced_locus or transient_forced_locus
        forced_action = self.forced_surface_action if forced_locus else None
        forced_target_file = (
            self.forced_surface_target_file if forced_locus else None
        )
        forced_diagnostic = self.forced_surface_diagnostic if forced_locus else False
        if (
            forced_locus
            and self.forced_surface_diagnostic
            and self.persistent_forced_locus is None
        ):
            self.forced_surface_action = None
            self.forced_surface_target_file = None
            self.forced_surface_diagnostic = False
        context = self.problem_runtime.build_hypothesis_context(
            branch=branch,
            champion=champ_snapshot,
            active_hypotheses=self.hypothesis_store.get_by_status("active"),
            blacklist=self.hypothesis_store.get_by_status("blacklisted"),
            rejected_hypotheses=self.hypothesis_store.get_by_status("rejected"),
            sibling_branches=siblings,
            step_history=self.step_history,
            branch_workspace=branch_workspace,
            failure_streak=dict(self.failure_streak),
            forced_locus=forced_locus,
            forced_action=forced_action,
            forced_target_file=forced_target_file,
            forced_surface_diagnostic=forced_diagnostic,
            search_memory=self.search_memory,
            saturation_signals=self._compute_saturation_signals(),
            weight_opt_result=self.get_latest_weight_opt_result(),
            research_log=self.research_log,
        )
        if self._agentic_enabled:
            return self._generate_agentic_hypothesis(
                branch=branch,
                champion=champ_snapshot,
                context=context,
            )
        try:
            hypothesis = self.creative.generate_hypothesis(context)
        except LLMBalanceError as exc:
            logger.critical(
                "Branch %s: API balance exhausted - stopping campaign: %s",
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
            ProposalValidationError,
        ) as exc:
            logger.warning("Branch %s: hypothesis LLM error: %s", bid, exc)
            self.hypothesis_failure_details[bid] = str(exc)
            self.handle_failure(branch, FailureEvent(category="proposal", detail=str(exc)))
            self.circuit_breaker.record_failure(str(exc))
            return None, None

        forced_detail = self._forced_hypothesis_violation(
            hypothesis,
            forced_surface=forced_locus,
            forced_action=forced_action,
            forced_target_file=forced_target_file,
        )
        if forced_detail is not None:
            self.hypothesis_failure_details[bid] = forced_detail
            self.handle_failure(branch, FailureEvent(category="proposal", detail=forced_detail))
            self.circuit_breaker.record_failure(forced_detail)
            return None, None

        self.circuit_breaker.record_success()
        return hypothesis, self._hypothesis_record(branch, hypothesis)

    def pop_hypothesis_failure_detail(self, branch_id: str) -> str | None:
        return self.hypothesis_failure_details.pop(branch_id, None)

    def generate_code(
        self,
        branch: Branch,
        hypothesis: HypothesisProposal,
        *,
        prior_failure: str | None = None,
    ) -> PatchProposal | None:
        bid = branch.branch_id
        if self._agentic_enabled:
            return self._generate_agentic_code(
                branch=branch,
                hypothesis=hypothesis,
                prior_failure=prior_failure,
            )
        context = self.problem_runtime.build_code_context(
            branch=branch,
            hypothesis=hypothesis,
            champion=self._champion_snapshot(),
            prior_failure=prior_failure,
        )
        try:
            result = self.creative.generate_code(context)
            self.circuit_breaker.record_success()
            return result
        except LLMBalanceError as exc:
            logger.critical(
                "Branch %s: API balance exhausted - stopping campaign: %s",
                bid,
                exc,
            )
            self.mark_balance_exhausted()
            self.circuit_breaker.record_failure(str(exc))
            return None
        except (
            LLMRetryExhaustedError,
            LLMFormatError,
            LLMTimeoutError,
            ProposalValidationError,
        ) as exc:
            logger.warning("Branch %s: code LLM error: %s", bid, exc)
            self.handle_failure(branch, FailureEvent(category="proposal", detail=str(exc)))
            self.circuit_breaker.record_failure(str(exc))
            return None

    def attempt_fix(
        self,
        branch: Branch,
        patch: PatchProposal,
        verification_result: VerificationResult,
    ) -> PatchProposal | None:
        logger.info(
            "Branch %s: attempting fix_code after %s light verification failure",
            branch.branch_id,
            verification_result.first_failure or "unknown",
        )
        context = self.problem_runtime.build_fix_context(
            branch=branch,
            patch=patch,
            verification_result=verification_result,
            failure_streak=dict(self.failure_streak),
        )
        try:
            fixed = self.creative.fix_code(context)
            if fixed is None:
                logger.info("Branch %s: fix_code returned no patch", branch.branch_id)
            else:
                logger.info(
                    "Branch %s: fix_code produced patch for %s",
                    branch.branch_id,
                    fixed.file_path,
                )
            return fixed
        except LLMBalanceError as exc:
            logger.critical(
                "Branch %s: API balance exhausted during fix - stopping campaign: %s",
                branch.branch_id,
                exc,
            )
            self.mark_balance_exhausted()
            self.circuit_breaker.record_failure(str(exc))
            return None
        except (
            LLMRetryExhaustedError,
            LLMFormatError,
            LLMTimeoutError,
            ProposalValidationError,
        ) as exc:
            logger.warning("Branch %s: fix LLM error: %s", branch.branch_id, exc)
            return None

    def _champion_snapshot(self) -> ChampionState:
        with self.champion_lock:
            return self.get_champion()

    def _compute_saturation_signals(self) -> Any:
        analyzer = self.get_saturation_analyzer()
        if analyzer is None:
            return None

        from scion.proposal.saturation import extract_candidate_metrics_from_step

        current_metrics = self.get_baseline_metrics()
        for step in reversed(self.step_history):
            if step.decision is not None and step.decision.value == "promote":
                metrics = extract_candidate_metrics_from_step(step)
                if metrics:
                    current_metrics = metrics
                    break
        if current_metrics:
            return analyzer.analyze(current_metrics)
        return None

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

        return ProposalToolContext(
            session_id="pending",
            campaign_id=self.campaign_id,
            branch=branch,
            champion=champion,
            problem_spec=problem_spec,
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
        )

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
            )
            if output.status == AgenticProposalStatus.FAILED:
                detail = self._agentic_failure_detail(output)
                logger.warning(
                    "Branch %s: agentic output rejected before code generation: %s",
                    bid,
                    detail,
                )
                self.handle_failure(
                    branch,
                    FailureEvent(category="proposal", detail=detail),
                )
                self.circuit_breaker.record_failure(detail)
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
                self.handle_failure(
                    branch,
                    FailureEvent(category="proposal", detail=detail),
                )
                self.circuit_breaker.record_failure(detail)
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
                self.mark_balance_exhausted()
                self.circuit_breaker.record_failure(str(exc))
                return None
            except (
                LLMRetryExhaustedError,
                LLMFormatError,
                LLMTimeoutError,
                ProposalValidationError,
                PermissionError,
            ) as exc:
                logger.warning("Branch %s: agentic code session error: %s", bid, exc)
                self.handle_failure(
                    branch,
                    FailureEvent(category="proposal", detail=str(exc)),
                )
                self.circuit_breaker.record_failure(str(exc))
                return None

        output = self._validate_and_sanitize_agentic_output(
            branch=branch,
            champion=self._champion_snapshot(),
            output=output,
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
            self.handle_failure(branch, FailureEvent(category="proposal", detail=detail))
            self.circuit_breaker.record_failure(detail)
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
        self.handle_failure(branch, FailureEvent(category="proposal", detail=detail))
        self.circuit_breaker.record_failure(detail)
        return None

    def _agentic_output_can_continue(
        self,
        output: AgenticProposalOutput,
        hypothesis: HypothesisProposal,
    ) -> bool:
        return (
            output.status == AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY
            and output.termination_reason
            == AgenticTerminationReason.HYPOTHESIS_AWAITING_APPROVAL
            and output.hypothesis == hypothesis
            and output.patch is None
        )

    def _validate_and_sanitize_agentic_output(
        self,
        *,
        branch: Branch,
        champion: ChampionState,
        output: AgenticProposalOutput,
        forced_surface: str | None = None,
        forced_action: str | None = None,
        forced_target_file: str | None = None,
    ) -> AgenticProposalOutput:
        failures: list[str] = []
        if output.branch_id != branch.branch_id:
            failures.append(
                f"branch_id expected {branch.branch_id!r} got {output.branch_id!r}"
            )
        if (
            output.champion_version is not None
            and output.champion_version != champion.version
        ):
            failures.append(
                "champion_version expected "
                f"{champion.version!r} got {output.champion_version!r}"
            )
        champion_weight_revision = getattr(champion, "weight_revision", None)
        if (
            output.champion_weight_revision is not None
            and output.champion_weight_revision != champion_weight_revision
        ):
            failures.append(
                "champion_weight_revision expected "
                f"{champion_weight_revision!r} got {output.champion_weight_revision!r}"
            )
        if (
            self.problem_id is not None
            and output.problem_id
            and output.problem_id != self.problem_id
        ):
            failures.append(
                f"problem_id expected {self.problem_id!r} got {output.problem_id!r}"
            )
        if (
            self.problem_spec_hash is not None
            and output.problem_spec_hash
            and output.problem_spec_hash != self.problem_spec_hash
        ):
            failures.append(
                "problem_spec_hash expected "
                f"{self.problem_spec_hash!r} got {output.problem_spec_hash!r}"
            )
        if self.campaign_id and output.campaign_id != self.campaign_id:
            failures.append(
                f"campaign_id expected {self.campaign_id!r} got {output.campaign_id!r}"
            )
        if output.hypothesis is not None:
            forced_violation = self._forced_hypothesis_violation(
                output.hypothesis,
                forced_surface=forced_surface,
                forced_action=forced_action,
                forced_target_file=forced_target_file,
            )
            if forced_violation is not None:
                failures.append(forced_violation)

        patch = output.patch
        failure_detail = output.failure_detail
        if output.status != AgenticProposalStatus.COMPLETED and patch is not None:
            patch = None
            if not failure_detail:
                failure_detail = "non-completed output included unchecked patch"

        if failures:
            return replace(
                ensure_agentic_output_audit_metadata(output),
                status=AgenticProposalStatus.FAILED,
                hypothesis=None,
                patch=None,
                termination_reason=AgenticTerminationReason.ANCHOR_VALIDATION_FAILED,
                failure_detail="; ".join(failures),
            )
        if patch is not output.patch or failure_detail != output.failure_detail:
            return ensure_agentic_output_audit_metadata(
                replace(output, patch=patch, failure_detail=failure_detail)
            )
        return ensure_agentic_output_audit_metadata(output)

    @staticmethod
    def _forced_hypothesis_violation(
        hypothesis: HypothesisProposal,
        *,
        forced_surface: str | None,
        forced_action: str | None,
        forced_target_file: str | None,
    ) -> str | None:
        forced_surface = str(forced_surface or "").strip()
        if not forced_surface:
            return None
        if str(hypothesis.change_locus or "").strip() != forced_surface:
            return (
                "forced_surface_constraint: change_locus must be "
                f"{forced_surface!r}, got {hypothesis.change_locus!r}"
            )
        forced_action = str(forced_action or "").strip()
        if forced_action and str(hypothesis.action or "").strip() != forced_action:
            return (
                "forced_surface_constraint: action must be "
                f"{forced_action!r}, got {hypothesis.action!r}"
            )
        forced_target_file = str(forced_target_file or "").strip()
        if forced_target_file:
            target = str(hypothesis.target_file or "").strip()
            if target != forced_target_file:
                return (
                    "forced_surface_constraint: target_file must be "
                    f"{forced_target_file!r}, got {target!r}"
                )
        return None

    def _sanitize_pre_contract_agentic_output(
        self,
        output: AgenticProposalOutput,
    ) -> AgenticProposalOutput:
        if (
            output.status != AgenticProposalStatus.COMPLETED
            or output.patch is None
        ):
            return output
        detail = (
            output.failure_detail
            or "completed patch ignored before ContractGate-approved hypothesis"
        )
        return replace(
            output,
            status=AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY,
            patch=None,
            termination_reason=AgenticTerminationReason.HYPOTHESIS_AWAITING_APPROVAL,
            failure_detail=detail,
        )

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
        self.handle_failure(branch, FailureEvent(category="proposal", detail=detail))
        self.circuit_breaker.record_failure(detail)
        return None, None

    def _with_agentic_resume_context(
        self,
        request: AgenticProposalRequest,
    ) -> AgenticProposalRequest:
        resume_context = self._lookup_agentic_resume_context(request)
        if resume_context is None:
            return request
        return replace(request, resume_context=resume_context)

    def _lookup_agentic_resume_context(
        self,
        request: AgenticProposalRequest,
    ) -> Mapping[str, Any] | None:
        if not self.agentic_artifact_dir:
            return None
        idempotency_key = self._agentic_idempotency_key_for_request(request)
        stored = AgenticSessionStore(self.agentic_artifact_dir).find_by_idempotency_key(
            idempotency_key
        )
        if stored is None:
            return None

        report = {
            "session_id": stored.entry.session_id,
            "idempotency_key": idempotency_key,
            "artifact_ref": stored.entry.artifact_ref,
            "status": stored.entry.status,
            "termination_reason": stored.entry.termination_reason,
            "validation_ok": stored.validation.ok,
            "validation_errors": list(stored.validation.errors),
        }
        self.agentic_recovery_reports[request.branch.branch_id] = report
        if not stored.validation.ok or stored.artifact is None:
            logger.warning(
                "Branch %s: agentic recovery artifact invalid; starting fresh: %s",
                request.branch.branch_id,
                "; ".join(stored.validation.errors),
            )
            return None
        try:
            context = resume_from_artifact(stored.artifact)
        except Exception as exc:
            self.agentic_recovery_reports[request.branch.branch_id] = {
                **report,
                "validation_ok": False,
                "validation_errors": [str(exc)],
            }
            logger.warning(
                "Branch %s: agentic recovery summary failed; starting fresh: %s",
                request.branch.branch_id,
                exc,
            )
            return None
        return {
            "source": "agentic_session_store",
            "recovery_mode": "sanitized_resume_context_only",
            "artifact_ref": stored.entry.artifact_ref,
            "status": stored.entry.status,
            "termination_reason": stored.entry.termination_reason,
            "validation": {"ok": True, "errors": []},
            "resume": context,
        }

    def _agentic_idempotency_key_for_request(
        self,
        request: AgenticProposalRequest,
    ) -> str:
        key_for_request = getattr(self.agentic_session, "idempotency_key_for_request", None)
        if callable(key_for_request):
            try:
                return str(key_for_request(request))
            except Exception:
                logger.debug("agentic session idempotency hook failed", exc_info=True)
        return compute_agentic_idempotency_key(
            request,
            self._agentic_tool_loop_config(),
        )

    def _agentic_failure_detail(self, output: AgenticProposalOutput) -> str:
        reason = output.termination_reason
        reason_value = (
            reason.value
            if isinstance(reason, AgenticTerminationReason)
            else str(reason)
        )
        if output.failure_detail:
            return f"agentic_proposal:{reason_value}: {output.failure_detail}"
        return f"agentic_proposal:{reason_value}"

    def _record_agentic_lineage_event(self, output: AgenticProposalOutput) -> None:
        if self.lineage_registry is None:
            return
        payload = {
            "schema_version": output.schema_version,
            "session_id": output.session_id,
            "request_id": output.request_id,
            "idempotency_key": output.idempotency_key,
            "transcript_digest": output.transcript_digest,
            "status": output.status.value
            if isinstance(output.status, AgenticProposalStatus)
            else str(output.status),
            "termination_reason": output.termination_reason.value
            if isinstance(output.termination_reason, AgenticTerminationReason)
            else str(output.termination_reason),
            "tainted_artifact_refs": list(output.tainted_artifact_refs),
            "contract_preview_passed": output.self_check.contract_preview_passed,
            "contract_preview_codes": list(output.self_check.contract_preview_codes),
        }
        event = {
            "campaign_id": output.campaign_id or self.campaign_id,
            "branch_id": output.branch_id,
            "timestamp": _now_iso(),
            "event_kind": "agentic_proposal_session",
            "stage": "agentic_proposal",
            "contract_result": (
                "passed"
                if output.self_check.contract_preview_passed is True
                else "failed"
                if output.self_check.contract_preview_passed is False
                else "not_run"
            ),
            "verification_result": "not_run",
            "canary_result": "not_run",
            "raw_metrics_ref": "",
            "decision_features_json": "",
            "audit_payload_json": _json_dumps(payload),
        }
        try:
            self.lineage_registry.record_event(event)
        except Exception:
            logger.debug("agentic lineage event write failed", exc_info=True)

    def _record_agentic_session_ref(self, output: AgenticProposalOutput) -> None:
        self.agentic_session_refs[output.branch_id] = self._agentic_session_ref(output)

    def pop_agentic_session_ref(self, branch_id: str) -> Mapping[str, Any] | None:
        return self.agentic_session_refs.pop(branch_id, None)

    @staticmethod
    def _agentic_session_ref(output: AgenticProposalOutput) -> dict[str, Any]:
        artifact_ref = next(
            (
                ref
                for ref in reversed(output.tainted_artifact_refs)
                if str(ref).endswith("output.json")
            ),
            output.tainted_artifact_refs[-1] if output.tainted_artifact_refs else None,
        )
        return {
            "schema_version": output.schema_version,
            "session_id": output.session_id,
            "request_id": output.request_id,
            "idempotency_key": output.idempotency_key,
            "artifact_ref": artifact_ref,
            "transcript_digest": output.transcript_digest,
            "termination_reason": output.termination_reason.value
            if isinstance(output.termination_reason, AgenticTerminationReason)
            else str(output.termination_reason),
            "status": output.status.value
            if isinstance(output.status, AgenticProposalStatus)
            else str(output.status),
        }

    def _hypothesis_record(
        self,
        branch: Branch,
        hypothesis: HypothesisProposal,
    ) -> HypothesisRecord:
        cls_result = self.classifier.classify(hypothesis.hypothesis_text or "")
        return HypothesisRecord(
            hypothesis_id=str(uuid.uuid4()),
            branch_id=branch.branch_id,
            change_locus=hypothesis.change_locus,
            action=hypothesis.action,
            status="active",
            target_file=hypothesis.target_file,
            suggested_weight=hypothesis.suggested_weight,
            hypothesis_text=hypothesis.hypothesis_text,
            family_id=cls_result.family_id,
            family_source=cls_result.source,
            taxonomy_version=cls_result.taxonomy_version,
            predicted_direction=hypothesis.predicted_direction,
            target_objectives=hypothesis.target_objectives,
            protected_objectives=hypothesis.protected_objectives,
            novelty_signature=dict(hypothesis.novelty_signature or {}),
        )
