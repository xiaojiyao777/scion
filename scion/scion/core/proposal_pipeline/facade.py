"""LLM proposal lifecycle service for campaign explore steps."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, MutableMapping

from scion.core.branch_hygiene import (
    branch_hygiene_context,
    branch_hygiene_guidance,
    branch_workspace_for_proposal,
)
from scion.core.branch_repair_policy import (
    is_branch_lifecycle_policy_block_detail,
    validate_repair_focused_hypothesis,
)
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
from scion.core.explore_step.branch_lesson_usage import project_branch_lesson_records
from scion.core.research_process_guidance_audit import (
    extract_research_process_guidance_audit,
)
from scion.core.status_reporter import is_provider_balance_exhausted_detail
from scion.proposal.agentic_session import AgenticProposalOutput
from scion.proposal.engine import ProposalValidationError
from scion.proposal.engine.hypothesis_context_profiles import (
    filter_hypothesis_context_for_prompt,
)
from scion.proposal.context.branch_followup import (
    validate_weak_positive_followup_hypothesis,
)
from scion.proposal.llm_client import (
    LLMBalanceError,
    LLMFormatError,
    LLMRateLimitError,
    LLMRetryExhaustedError,
    LLMTimeoutError,
    LLMTransientProviderError,
    is_llm_transient_api_error,
)

from .agentic_lifecycle import AgenticLifecycleMixin
from .agentic_refs import AgenticRefsMixin
from .agentic_requests import AgenticRequestMixin
from .agentic_validation import AgenticValidationMixin
from .boundaries import (
    BoundaryValidationMixin,
    _active_problem_boundary_surfaces_for_runtime,
)
from .protocols import (
    AgenticProposalSessionLike,
    BranchControllerLike,
    CircuitBreakerLike,
    ClassifierLike,
    CreativeLayerLike,
    HypothesisStoreLike,
    ProblemRuntimeLike,
)
from .problem_quality import (
    validate_problem_hypothesis_quality,
    validate_problem_patch_quality,
)
from .records import ProposalRecordMixin

logger = logging.getLogger(__name__)


_PROPOSAL_CONTEXT_SESSION_REF_FIELDS = (
    "branch_lesson_records",
    "branch_lesson_usage_requirement",
    "cross_branch_research_audit_records",
    "cross_branch_research_status",
)


def _compact_proposal_context_session_ref(
    context: Mapping[str, Any],
) -> dict[str, Any]:
    """Return bounded proposal-visible context metadata for durable refs."""

    ref: dict[str, Any] = {"schema_version": "proposal-context-ref.v1"}
    records = context.get("branch_lesson_records")
    compact_records = project_branch_lesson_records(records)
    if compact_records:
        ref["branch_lesson_records"] = compact_records
    requirement = context.get("branch_lesson_usage_requirement")
    if isinstance(requirement, Mapping):
        ref["branch_lesson_usage_requirement"] = dict(requirement)
    audit_records = context.get("cross_branch_research_audit_records")
    if isinstance(audit_records, (list, tuple)):
        compact_audit_records = [
            dict(record)
            for record in audit_records[:8]
            if isinstance(record, Mapping)
        ]
        if compact_audit_records:
            ref["cross_branch_research_audit_records"] = compact_audit_records
    if (
        ref.get("branch_lesson_records")
        or ref.get("branch_lesson_usage_requirement")
        or ref.get("cross_branch_research_audit_records")
    ):
        ref["cross_branch_research_status"] = "available"
    return ref if len(ref) > 1 else {}


def _merge_proposal_context_session_ref(
    existing: Mapping[str, Any] | None,
    addition: Mapping[str, Any],
) -> dict[str, Any]:
    merged = dict(existing or {})
    if not addition:
        return merged
    if not merged.get("schema_version"):
        merged["schema_version"] = addition.get(
            "schema_version",
            "proposal-context-ref.v1",
        )
    for key in _PROPOSAL_CONTEXT_SESSION_REF_FIELDS:
        value = addition.get(key)
        if value not in (None, "", [], {}, ()):
            merged[key] = value
    return merged


@dataclass
class ProposalPipeline(
    AgenticLifecycleMixin,
    AgenticRefsMixin,
    AgenticRequestMixin,
    AgenticValidationMixin,
    BoundaryValidationMixin,
    ProposalRecordMixin,
):
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
    split_manifest: Any | None = None
    seed_ledger: Any | None = None
    campaign_id: str = ""
    problem_id: str | None = None
    problem_spec_hash: str | None = None
    split_manifest_hash: str | None = None
    seed_ledger_hash: str | None = None
    production_campaign: bool = False
    require_agentic_problem_anchors: bool = False
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
    agentic_quality_feedback: MutableMapping[str, list[Mapping[str, Any]]] = field(
        default_factory=dict
    )
    agentic_code_quality_feedback: MutableMapping[
        str, list[Mapping[str, Any]]
    ] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.production_campaign and self._agentic_enabled:
            self.require_agentic_problem_anchors = True

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
        branch_workspace = branch_workspace_for_proposal(
            branch,
            self.branch_workspaces,
        )
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
        context["branch_hygiene"] = branch_hygiene_context(branch)
        context["branch_hygiene_guidance"] = branch_hygiene_guidance(branch)
        guidance_audit = extract_research_process_guidance_audit(
            context.get("branch_followup_policy_payload")
        )
        if guidance_audit:
            self.agentic_session_refs[bid] = {
                "schema_version": "proposal-context-ref.v1",
                "research_process_guidance_audit": guidance_audit,
            }
        self._attach_agentic_quality_feedback_context(
            context,
            bid,
            phase="hypothesis",
        )
        context_session_ref = _compact_proposal_context_session_ref(context)
        prompt_context = filter_hypothesis_context_for_prompt(context)
        if context_session_ref:
            self.agentic_session_refs[bid] = _merge_proposal_context_session_ref(
                self.agentic_session_refs.get(bid),
                context_session_ref,
            )
        if self._agentic_enabled:
            return self._generate_agentic_hypothesis(
                branch=branch,
                champion=champ_snapshot,
                context=prompt_context,
            )
        try:
            hypothesis = self.creative.generate_hypothesis(prompt_context)
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
            LLMTransientProviderError,
            LLMRateLimitError,
            ProposalValidationError,
        ) as exc:
            if is_provider_balance_exhausted_detail(exc):
                logger.critical(
                    "Branch %s: API balance exhausted - stopping campaign: %s",
                    bid,
                    exc,
                )
                self.hypothesis_failure_details[bid] = str(exc)
                self.mark_balance_exhausted()
                self.circuit_breaker.record_failure(str(exc))
                return None, None
            logger.warning("Branch %s: hypothesis LLM error: %s", bid, exc)
            self.hypothesis_failure_details[bid] = str(exc)
            category = "infra" if is_llm_transient_api_error(exc) else "proposal"
            self.handle_failure(
                branch,
                FailureEvent(category=category, detail=str(exc)),
            )
            if category != "infra":
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
        boundary_detail = self._active_problem_boundary_violation(
            hypothesis,
            active_problem_boundary_surfaces=(
                ()
                if forced_locus
                else _active_problem_boundary_surfaces_for_runtime(
                    self.problem_runtime,
                )
            ),
            forced_surface=forced_locus,
        )
        if boundary_detail is not None:
            self.hypothesis_failure_details[bid] = boundary_detail
            self.handle_failure(
                branch,
                FailureEvent(category="proposal", detail=boundary_detail),
            )
            self.circuit_breaker.record_failure(boundary_detail)
            return None, None
        repair_check = validate_repair_focused_hypothesis(
            branch,
            hypothesis,
            step_history=self.step_history,
        )
        if not repair_check.allowed:
            self.hypothesis_failure_details[bid] = repair_check.detail
            if is_branch_lifecycle_policy_block_detail(repair_check.detail):
                logger.info(
                    "Branch %s: branch lifecycle policy blocked proposal: %s",
                    bid,
                    repair_check.detail,
                )
            else:
                self.handle_failure(
                    branch,
                    FailureEvent(category="proposal", detail=repair_check.detail),
                )
                self.circuit_breaker.record_failure(repair_check.detail)
            return None, None

        followup_check = validate_weak_positive_followup_hypothesis(
            branch,
            hypothesis,
            step_history=self.step_history,
        )
        if not followup_check.allowed:
            self.hypothesis_failure_details[bid] = followup_check.detail
            self.handle_failure(
                branch,
                FailureEvent(category="proposal", detail=followup_check.detail),
            )
            self.circuit_breaker.record_failure(followup_check.detail)
            return None, None

        quality_check = validate_problem_hypothesis_quality(
            self.problem_runtime,
            branch,
            hypothesis,
            step_history=self.step_history,
        )
        if not quality_check.allowed:
            self.hypothesis_failure_details[bid] = quality_check.detail
            self.handle_failure(
                branch,
                FailureEvent(category="proposal", detail=quality_check.detail),
            )
            self.circuit_breaker.record_failure(quality_check.detail)
            return None, None

        self.circuit_breaker.record_success()
        self._clear_agentic_quality_feedback(bid)
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
            branch_workspace=branch_workspace_for_proposal(
                branch,
                self.branch_workspaces,
            ),
            step_history=self.step_history,
        )
        context["branch_hygiene"] = branch_hygiene_context(branch)
        context["branch_hygiene_guidance"] = branch_hygiene_guidance(branch)
        self._attach_agentic_quality_feedback_context(
            context,
            bid,
            phase="code",
        )
        try:
            result = self.creative.generate_code(context)
            quality_check = validate_problem_patch_quality(
                self.problem_runtime,
                branch,
                hypothesis,
                result,
                step_history=self.step_history,
            )
            if not quality_check.allowed:
                self.hypothesis_failure_details[bid] = quality_check.detail
                self.handle_failure(
                    branch,
                    FailureEvent(category="proposal", detail=quality_check.detail),
                )
                self.circuit_breaker.record_failure(quality_check.detail)
                return None
            self.circuit_breaker.record_success()
            self._clear_agentic_quality_feedback(bid)
            self._clear_agentic_code_quality_feedback(bid)
            return result
        except LLMBalanceError as exc:
            logger.critical(
                "Branch %s: API balance exhausted - stopping campaign: %s",
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
        ) as exc:
            if is_provider_balance_exhausted_detail(exc):
                logger.critical(
                    "Branch %s: API balance exhausted - stopping campaign: %s",
                    bid,
                    exc,
                )
                self.hypothesis_failure_details[bid] = str(exc)
                self.mark_balance_exhausted()
                self.circuit_breaker.record_failure(str(exc))
                return None
            logger.warning("Branch %s: code LLM error: %s", bid, exc)
            self.hypothesis_failure_details[bid] = str(exc)
            category = "infra" if is_llm_transient_api_error(exc) else "proposal"
            self.handle_failure(
                branch,
                FailureEvent(category=category, detail=str(exc)),
            )
            if category != "infra":
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
            LLMTransientProviderError,
            LLMRateLimitError,
            ProposalValidationError,
        ) as exc:
            if is_provider_balance_exhausted_detail(exc):
                logger.critical(
                    "Branch %s: API balance exhausted during fix - stopping campaign: %s",
                    branch.branch_id,
                    exc,
                )
                self.mark_balance_exhausted()
                self.circuit_breaker.record_failure(str(exc))
                return None
            logger.warning("Branch %s: fix LLM error: %s", branch.branch_id, exc)
            return None
