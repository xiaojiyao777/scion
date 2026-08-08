"""Campaign service composition helpers.

This module owns the constructor-time wiring for CampaignManager.  The manager
remains the public facade and callback owner; service construction lives here so
new runtime boundaries do not keep growing campaign.py.
"""

from __future__ import annotations

import os
import threading
import uuid
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any

from scion.contract.gate import ContractGate
from scion.core.async_weight_opt import (
    AsyncWeightOptCoordinator,
    bounded_terminal_wait_timeout,
)
from scion.core.branch import BranchController
from scion.core.candidate_evaluation import (
    candidate_evaluation,
    candidate_evaluation_pending,
)
from scion.core.branch_step_runner import BranchStepRunner
from scion.core.campaign_adapters import _workspace_service_for
from scion.core.campaign_loop import CampaignLoop
from scion.core.decision_coordinator import DecisionCoordinator
from scion.core.decision_finalizer import DecisionFinalizer
from scion.core.evaluation_orchestrator import EvaluationOrchestrator
from scion.core.evidence_recorder import EvidenceRecorder
from scion.core.explore_step_pipeline import ExploreStepPipeline
from scion.core.failure_lifecycle import FailureLifecycleService
from scion.core.models import (
    ChampionState,
    HypothesisProposal,
    HypothesisRecord,
    OperatorConfig,
)
from scion.core.production_boundary import (
    is_adapter_backed_production_campaign,
    validate_production_campaign_boundary,
)
from scion.core.problem_runtime import ProblemRuntime
from scion.core.problem_identity import problem_id_anchor
from scion.core.promotion_lifecycle import PromotionLifecycleService
from scion.core.promotion_service import PromotionService
from scion.core.research_rejection_finalizer import ResearchRejectionFinalizer
from scion.core.proposal_pipeline import (
    ProposalPipeline,
)
from scion.core.research_surface_index import editable_identity_patterns
from scion.core.scheduler import Scheduler
from scion.core.status_reporter import StatusReporter
from scion.core.verification_factory import CampaignVerificationFactory
from scion.core.weight_opt_committer import WeightOptCommitter
from scion.core.workspace_lifecycle import WorkspaceLifecycleService
from scion.failure.router import FailureRouter
from scion.lineage.branch_store import BranchStore, HypothesisStore
from scion.lineage.research_champion_store import ChampionStore
from scion.lineage.registry import LineageRegistry
from scion.proposal.classifier import HypothesisFamilyClassifier
from scion.proposal.engine import CreativeLayer
from scion.runtime.workspace import WorkspaceMaterializer


def _mark_balance_exhausted(owner: Any) -> None:
    owner._balance_exhausted = True
    if not getattr(owner, "_external_stop_requested", False):
        owner.request_stop("api_balance_exhausted")


def _pattern_set(patterns: Any) -> frozenset[str] | None:
    normalized = frozenset(
        pattern
        for pattern in (str(value).strip() for value in (patterns or ()))
        if pattern
    )
    return normalized or None


def _materializer_kwargs_from_problem_spec(
    problem_spec: Any,
) -> dict[str, Any]:
    search_space = getattr(problem_spec, "search_space", None)
    return {
        "frozen_patterns": _pattern_set(getattr(search_space, "frozen", ())),
        "editable_patterns": editable_identity_patterns(problem_spec),
    }


def compose_campaign_services(
    owner: Any,
    *,
    problem_spec: Any,
    protocol_config: Any,
    split_manifest: Any,
    seed_ledger: Any,
    llm_client: Any,
    champion: Any,
    campaign_dir: str,
    verification_gate: Any | None = None,
    experiment_protocol: Any | None = None,
    adapter: Any | None = None,
    operator_execute_signature: str | None = None,
    allow_non_strict_runtime_verification: bool = False,
    allow_skeleton_mode: bool = False,
) -> None:
    """Install CampaignManager services and state on *owner*."""
    production_campaign = is_adapter_backed_production_campaign(
        problem_spec=problem_spec,
        adapter=adapter,
        allow_skeleton=allow_skeleton_mode,
    )
    owner._problem_runtime = ProblemRuntime(
        problem_spec=problem_spec,
        adapter=adapter,
        split_manifest=split_manifest,
        seed_ledger=seed_ledger,
    )
    owner._protocol_config = protocol_config
    owner._split_manifest = split_manifest
    owner._seed_ledger = seed_ledger
    owner._llm_client = llm_client
    owner._champion = champion
    owner._campaign_dir = campaign_dir
    owner._campaign_id = str(uuid.uuid4())
    owner._status_reporter = StatusReporter(campaign_dir)
    owner._last_status_result = None
    owner._current_status_progress = None
    owner._last_stop_reason = None
    owner._external_stop_requested = False
    owner._branch_ctrl = BranchController()
    owner._scheduler = Scheduler()
    owner._contract_gate = ContractGate(
        problem_spec,
        operator_execute_signature=operator_execute_signature,
        adapter=adapter,
        champion_snapshot_provider=lambda: getattr(
            owner._champion,
            "code_snapshot_path",
            None,
        ),
    )
    owner._decision_coordinator = DecisionCoordinator(config=protocol_config)
    from scion.core.features import SafeFeatureExtractor

    owner._feature_extractor = SafeFeatureExtractor()
    owner._failure_router = FailureRouter()
    owner._creative = CreativeLayer(
        llm_client,
        trace_dir=f"{campaign_dir}/llm_traces",
    )

    family_taxonomy = getattr(owner._spec, "family_taxonomy", None)
    owner._classifier = HypothesisFamilyClassifier(
        taxonomy=family_taxonomy,
        taxonomy_version=getattr(family_taxonomy, "version", "v1"),
    )
    owner._materializer = WorkspaceMaterializer(
        campaign_dir,
        **_materializer_kwargs_from_problem_spec(problem_spec),
    )
    owner._experiment_protocol = experiment_protocol
    if hasattr(owner._experiment_protocol, "set_problem_adapter"):
        owner._experiment_protocol.set_problem_adapter(adapter)
    os.makedirs(str(campaign_dir) + "/metrics", exist_ok=True)
    owner._vgate = CampaignVerificationFactory.build(
        problem_spec=problem_spec,
        verification_gate=verification_gate,
        experiment_protocol=experiment_protocol,
        campaign_dir=str(campaign_dir),
        adapter=adapter,
        operator_execute_signature=operator_execute_signature,
        allow_non_strict_runtime_verification=allow_non_strict_runtime_verification,
        allow_skeleton_mode=allow_skeleton_mode,
    )
    validate_production_campaign_boundary(
        problem_spec=problem_spec,
        experiment_protocol=experiment_protocol,
        adapter=adapter,
        split_manifest=split_manifest,
        seed_ledger=seed_ledger,
        verification_gate=owner._vgate,
        allow_skeleton=allow_skeleton_mode,
    )
    if hasattr(owner._experiment_protocol, "set_progress_callback"):
        owner._experiment_protocol.set_progress_callback(owner._on_protocol_progress)

    def _read_promotion_weights(registry_path: str) -> dict[str, float]:
        if (
            owner._spec.parameter_search.enabled
            and owner._experiment_protocol is not None
        ):
            from scion.runtime.pool_manager import read_weights

            return read_weights(registry_path)
        return {}

    owner._promotion_service = PromotionService(
        snapshot_root=owner._materializer._champions_dir,
        materializer=owner._materializer,
        commit_champion=owner._commit_promoted_champion_state,
        persist_champion=owner._persist_promoted_champion,
        promote_branch=owner._transition_promoted_branch,
        mark_stale=owner._branch_ctrl.mark_all_stale,
        persist_branch_states=owner._persist_all_branch_states,
        read_weights_fn=_read_promotion_weights,
    )

    os.makedirs(campaign_dir, exist_ok=True)
    owner._registry = LineageRegistry(os.path.join(campaign_dir, "scion.db"))
    owner._campaign_id = owner._registry.claim_campaign_id(owner._campaign_id)
    owner._hyp_store = HypothesisStore(owner._registry)
    owner._branch_store = BranchStore(owner._registry)
    owner._evidence_recorder = EvidenceRecorder(
        campaign_id=owner._campaign_id,
        campaign_dir=campaign_dir,
        status_reporter=owner._status_reporter,
        registry=owner._registry,
        state_provider=owner.get_state_snapshot,
        model_id=getattr(llm_client, "model", None),
        protocol_version=getattr(protocol_config, "version", None),
        family_taxonomy=family_taxonomy,
    )
    owner._champion_store = ChampionStore(
        os.path.join(campaign_dir, "scion.db"),
        os.path.join(campaign_dir, "champions"),
    )
    _persist_initial_champion(owner)

    owner._branch_workspaces = {}
    owner._branch_hypotheses = {}
    owner._branch_patches = {}
    owner._decision_reason_codes = {}
    owner._decision_engine_reason_codes = {}
    owner._diagnostic_reason_codes = {}
    owner._bypass_reason_codes = {}
    owner._decision_feature_snapshots = {}
    owner._branch_current_hypothesis = {}
    owner._step_history = []
    owner._round_num = 0
    _restore_persisted_active_branches(owner)
    owner._round_num = _restored_round_num(owner)

    owner._n_experiments = 0
    owner._start_time = datetime.now()

    owner._balance_exhausted = False
    owner._research_preflight_checked = False

    from scion.core.token_usage import TokenUsageTracker

    owner._token_tracker = TokenUsageTracker()
    if hasattr(llm_client, "set_token_tracker"):
        llm_client.set_token_tracker(owner._token_tracker)

    owner._failure_streak = {}
    owner._total_failures = {}
    owner._failure_lifecycle = FailureLifecycleService(
        failure_router=owner._failure_router,
        failure_streak=owner._failure_streak,
        total_failures=owner._total_failures,
        branch_controller=owner._branch_ctrl,
        branch_hypotheses=owner._branch_hypotheses,
        branch_patches=owner._branch_patches,
        branch_store=owner._branch_store,
        registry=owner._registry,
        campaign_id=owner._campaign_id,
    )

    owner._champion_lock = threading.Lock()
    owner._workspace_lifecycle = WorkspaceLifecycleService(
        materializer=owner._materializer,
        branch_controller=owner._branch_ctrl,
        branch_workspaces=owner._branch_workspaces,
        branch_patches=owner._branch_patches,
        champion_lock=owner._champion_lock,
        get_champion=lambda: owner._champion,
    )
    owner._proposal_pipeline = ProposalPipeline(
        creative=owner._creative,
        problem_runtime=owner._problem_runtime,
        classifier=owner._classifier,
        branch_controller=owner._branch_ctrl,
        hypothesis_store=owner._hyp_store,
        branch_workspaces=owner._branch_workspaces,
        champion_lock=owner._champion_lock,
        get_champion=lambda: owner._champion,
        step_history=owner._step_history,
        handle_failure=owner._handle_failure,
        mark_balance_exhausted=lambda: _mark_balance_exhausted(owner),
        campaign_branches_provider=owner._branch_store.load_all,
        lineage_registry=owner._registry,
        campaign_id=owner._campaign_id,
        problem_id=problem_id_anchor(problem_spec),
    )
    owner._research_rejection_finalizer = ResearchRejectionFinalizer(
        campaign_id=owner._campaign_id,
        registry=owner._registry,
        branch_store=owner._branch_store,
        hypothesis_store=owner._hyp_store,
        workspace_lifecycle=owner._workspace_lifecycle,
        branch_hypotheses=owner._branch_hypotheses,
        branch_patches=owner._branch_patches,
        branch_current_hypothesis=owner._branch_current_hypothesis,
        discard_approved_hypothesis_binding=(
            owner._proposal_pipeline.discard_approved_hypothesis_binding
        ),
    )
    owner._weight_opt_coord = AsyncWeightOptCoordinator(owner)
    owner._weight_opt_committer = WeightOptCommitter(
        event_source=owner._weight_opt_coord,
        champion_lock=owner._champion_lock,
        get_champion=lambda: owner._champion,
        set_champion=lambda champion: setattr(owner, "_champion", champion),
        champion_store=owner._champion_store,
        branch_controller=owner._branch_ctrl,
        persist_branch_states=owner._persist_all_branch_states,
        registry=owner._registry,
        campaign_id=owner._campaign_id,
    )
    owner._promotion_lifecycle = PromotionLifecycleService(
        promotion_service=owner._promotion_service,
        branch_controller=owner._branch_ctrl,
        branch_workspaces=owner._branch_workspaces,
        branch_current_hypothesis=owner._branch_current_hypothesis,
        champion_lock=owner._champion_lock,
        get_champion=lambda: owner._champion,
        set_champion=lambda champion: setattr(owner, "_champion", champion),
        get_champion_store=lambda: owner._champion_store,
        hypothesis_store=owner._hyp_store,
        get_weight_opt_coord=lambda: owner._weight_opt_coord,
        get_weight_opt_committer=lambda: owner._weight_opt_committer,
        get_parameter_search_execution=lambda: getattr(
            owner._spec.parameter_search,
            "execution",
            "async",
        ),
    )
    owner._decision_finalizer = DecisionFinalizer(
        branch_controller=owner._branch_ctrl,
        branch_store=owner._branch_store,
        hypothesis_store=owner._hyp_store,
        branch_workspaces=owner._branch_workspaces,
        branch_hypotheses=owner._branch_hypotheses,
        branch_patches=owner._branch_patches,
        branch_current_hypothesis=owner._branch_current_hypothesis,
        prepare_promoted_champion=owner._prepare_promoted_champion,
        require_promotable_branch=owner._require_promotable_branch,
        commit_promote_plan=owner._commit_promote_plan,
        handle_failure=owner._handle_failure,
        record_step_lineage=owner._record_step_lineage,
        decision_reason_codes_for=owner._decision_reason_codes_for,
        decision_provenance_for=owner._decision_provenance_for,
        discard_branch_workspace=lambda branch_id: _workspace_service_for(
            owner
        ).discard_branch_workspace(branch_id),
        persist_branch_state=owner._persist_branch_state,
        decision_features_for=lambda branch_id: owner._decision_feature_snapshots.get(
            branch_id
        ),
        pending_candidate_patch=lambda branch: _workspace_service_for(
            owner
        ).pending_candidate_patch(branch.branch_id),
        accept_candidate=lambda branch, code_hash, workspace: _workspace_service_for(
            owner
        ).accept_candidate(branch, code_hash, workspace),
        reject_candidate=lambda branch, workspace: _workspace_service_for(
            owner
        ).reject_candidate(
            branch,
            workspace,
        ),
    )
    owner._evaluation_orchestrator = EvaluationOrchestrator(
        branch_controller=owner._branch_ctrl,
        champion_lock=owner._champion_lock,
        get_champion=lambda: owner._champion,
        branch_patches=owner._branch_patches,
        branch_workspaces=owner._branch_workspaces,
        branch_hypotheses=owner._branch_hypotheses,
        branch_current_hypothesis=owner._branch_current_hypothesis,
        experiment_protocol_provider=lambda: owner._experiment_protocol,
        feature_extractor=owner._feature_extractor,
        decision_coordinator=owner._decision_coordinator,
        decision_reason_codes=owner._decision_reason_codes,
        decision_engine_reason_codes=owner._decision_engine_reason_codes,
        diagnostic_reason_codes=owner._diagnostic_reason_codes,
        bypass_reason_codes=owner._bypass_reason_codes,
        decision_feature_snapshots=owner._decision_feature_snapshots,
        campaign_id=owner._campaign_id,
        registry=owner._registry,
        materializer=owner._materializer,
        hypothesis_store=owner._hyp_store,
        persist_branch_state=owner._persist_branch_state,
        begin_status_progress=owner._begin_status_progress,
        end_status_progress=owner._end_status_progress,
        increment_experiment_count=lambda: setattr(
            owner,
            "_n_experiments",
            owner._n_experiments + 1,
        ),
        require_experiment_protocol=(production_campaign),
    )
    owner._explore_step_pipeline = ExploreStepPipeline(
        branch_controller=owner._branch_ctrl,
        contract_gate=owner._contract_gate,
        verification_gate=owner._vgate,
        hypothesis_store=owner._hyp_store,
        registry=owner._registry,
        campaign_id=owner._campaign_id,
        get_champion=lambda: owner._champion,
        branch_hypotheses=owner._branch_hypotheses,
        branch_patches=owner._branch_patches,
        branch_current_hypothesis=owner._branch_current_hypothesis,
        branch_workspaces=owner._branch_workspaces,
        failure_streak=owner._failure_streak,
        increment_round=owner._increment_round,
        generate_hypothesis=owner._round1_generate_hypothesis,
        generate_code=owner._round2_generate_code,
        handle_failure=owner._handle_failure,
        record_step=owner._record_step,
        setup_workspace=owner._setup_workspace,
        apply_patch=lambda branch, workspace, patch, **kwargs: _workspace_service_for(
            owner
        ).apply_candidate_patch(branch, workspace, patch, **kwargs),
        reject_candidate_workspace=lambda branch, workspace: _workspace_service_for(
            owner
        ).reject_candidate(branch, workspace),
        finalize_research_rejection=owner._research_rejection_finalizer.finalize,
        evaluate=owner._evaluate,
        apply_decision_and_finalize=owner._apply_decision_and_finalize,
        decision_reason_codes_for=owner._decision_reason_codes_for,
        decision_provenance_for=owner._decision_provenance_for,
        proposal_failure_detail_for=owner._proposal_failure_detail_for,
        proposal_execution_outcome_for=owner._proposal_execution_outcome_for,
        proposal_session_ref_for=owner._proposal_session_ref_for,
        persist_branch_state=owner._persist_branch_state,
        update_status_progress=owner._update_status_progress,
        step_history=owner._step_history,
    )
    owner._branch_step_runner = BranchStepRunner(
        branch_controller=owner._branch_ctrl,
        scheduler=owner._scheduler,
        champion_lock=owner._champion_lock,
        get_champion=lambda: owner._champion,
        branch_store=owner._branch_store,
        branch_workspaces=owner._branch_workspaces,
        branch_hypotheses=owner._branch_hypotheses,
        branch_patches=owner._branch_patches,
        branch_current_hypothesis=owner._branch_current_hypothesis,
        experiment_protocol_provider=lambda: owner._experiment_protocol,
        contract_gate=owner._contract_gate,
        verification_gate=owner._vgate,
        drain_weight_opt_events=owner._drain_weight_opt_events,
        should_stop=owner.should_stop,
        get_last_stop_reason=lambda: owner._last_stop_reason,
        persist_branch_state=owner._persist_branch_state,
        setup_workspace=owner._setup_workspace,
        apply_patch=lambda branch, workspace, patch, **kwargs: _workspace_service_for(
            owner
        ).apply_patch(branch, workspace, patch, **kwargs),
        evaluate=owner._evaluate,
        apply_decision_and_finalize=owner._apply_decision_and_finalize,
        record_step=owner._record_step,
        record_scheduler_result=owner._record_scheduler_result,
        decision_reason_codes_for=owner._decision_reason_codes_for,
        decision_provenance_for=owner._decision_provenance_for,
        run_explore_step=owner._explore_step_pipeline.run,
        run_eval_step_callback=owner._run_eval_step,
        run_reconcile_step_callback=owner._run_reconcile_step,
        increment_round=owner._increment_round,
        hypothesis_store=owner._hyp_store,
        registry=owner._registry,
        campaign_id=owner._campaign_id,
        apply_reconcile_candidate=(
            lambda branch, workspace, patch, **kwargs: _workspace_service_for(
                owner
            ).apply_candidate_patch(branch, workspace, patch, **kwargs)
        ),
        reject_reconcile_candidate=(
            lambda branch, workspace: _workspace_service_for(owner).reject_candidate(
                branch,
                workspace,
            )
        ),
    )
    owner._campaign_loop = CampaignLoop(
        write_status=lambda **kwargs: owner._write_status(**kwargs),
        drain_weight_opt_events=lambda: owner._drain_weight_opt_events(),
        should_stop=lambda: owner.should_stop(),
        get_last_stop_reason=lambda: owner._last_stop_reason,
        set_last_stop_reason=lambda reason: setattr(owner, "_last_stop_reason", reason),
        run_one_step=lambda: owner.run_one_step(),
        write_campaign_summary=lambda: owner._write_campaign_summary(),
        get_final_wait_timeout=lambda: bounded_terminal_wait_timeout(
            getattr(
                owner._spec.parameter_search,
                "final_wait_timeout_sec",
                600.0,
            )
        ),
        wait_weight_opt_all=lambda timeout: owner._weight_opt_coord.wait_all(
            timeout=timeout
        ),
    )


def required_service_names() -> tuple[str, ...]:
    """Key services expected after composition."""
    return (
        "_vgate",
        "_evidence_recorder",
        "_branch_step_runner",
        "_proposal_pipeline",
        "_campaign_loop",
    )


def _persist_initial_champion(owner: Any) -> None:
    """Persist the base champion so campaign evidence has a real v1 anchor."""
    current = owner._champion_store.get_current()
    if current is not None:
        owner._champion = _reanchor_current_champion_snapshot(owner, current)
        return

    champion = owner._champion
    source_path = os.path.abspath(champion.code_snapshot_path)
    champions_root = os.path.abspath(str(owner._materializer._champions_dir))
    snapshot_path = source_path

    # Avoid recursively copying a problem root into a campaign directory that
    # lives inside that same root. The DB anchor is still useful in that layout.
    if os.path.commonpath([source_path, champions_root]) != source_path:
        snapshot_path = owner._materializer.create_champion_snapshot(
            champion,
            str(owner._materializer._champions_dir),
        )

    persisted = ChampionState(
        version=champion.version,
        operator_pool=_normalize_operator_pool(champion.operator_pool),
        solver_config_hash=champion.solver_config_hash,
        code_snapshot_path=snapshot_path,
        code_snapshot_hash=owner._materializer.compute_snapshot_hash(snapshot_path),
        promotion_experiment_id=champion.promotion_experiment_id,
        promoted_at=champion.promoted_at,
        promotion_dossier_ref=champion.promotion_dossier_ref,
        weight_revision=champion.weight_revision,
    )
    owner._champion_store.promote(persisted)
    owner._champion = persisted


def _restore_persisted_active_branches(owner: Any) -> None:
    """Restore schedulable branch state when reopening an existing campaign."""
    for branch in owner._branch_store.load_all_active():
        persisted_summary = branch.branch_evidence_summary or {}
        marker = candidate_evaluation(branch)
        if candidate_evaluation_pending(branch):
            raise RuntimeError(
                f"Branch {branch.branch_id}: pending candidate requires a fresh "
                "campaign; staging paths are intentionally not reconstructed"
            )
        if "verified_candidate_commit" in persisted_summary and marker is None:
            raise RuntimeError(
                f"Branch {branch.branch_id}: legacy verified candidate state cannot "
                "be resumed; stop this campaign instead of reconstructing it from artifacts"
            )
        owner._branch_ctrl.restore_branch(branch)
        workspace = os.path.join(owner._campaign_dir, "workspaces", branch.branch_id)
        if owner._branch_ctrl.get_code_base(branch.branch_id) != "branch_workspace":
            workspace = ""
        else:
            if not os.path.isdir(workspace):
                raise RuntimeError(
                    f"Branch {branch.branch_id}: persisted verified workspace is unavailable"
                )
            expected_hash = branch.last_clean_code_hash
            if branch.current_code_hash != expected_hash:
                raise RuntimeError(
                    f"Branch {branch.branch_id}: persisted branch hashes are not clean"
                )
            actual_hash = owner._materializer.compute_code_hash(workspace)
            if actual_hash != expected_hash:
                raise RuntimeError(
                    f"Branch {branch.branch_id}: persisted verified workspace hash mismatch"
                )
            owner._branch_workspaces[branch.branch_id] = workspace

        active_hypothesis = _latest_candidate_hypothesis_for_branch(
            owner._hyp_store,
            branch.branch_id,
        )
        if candidate_evaluation_pending(branch) and (
            active_hypothesis is None
            or marker is None
            or marker["hypothesis_id"] != active_hypothesis.hypothesis_id
        ):
            raise RuntimeError(
                f"Branch {branch.branch_id}: pending evaluation ownership conflict"
            )
        if active_hypothesis is not None:
            owner._branch_current_hypothesis[branch.branch_id] = active_hypothesis
            owner._branch_hypotheses[branch.branch_id] = (
                _hypothesis_proposal_from_record(active_hypothesis)
            )


def _restored_round_num(owner: Any) -> int:
    """Continue durable screening round identities across campaign reopen."""

    maximum = 0
    for branch in owner._branch_ctrl._branches.values():
        history = (branch.branch_evidence_summary or {}).get(
            "canonical_screening_history",
            (),
        )
        if not isinstance(history, list):
            continue
        for record in history:
            if not isinstance(record, dict):
                continue
            round_num = record.get("round_num")
            if isinstance(round_num, bool):
                continue
            try:
                maximum = max(maximum, int(round_num))
            except (TypeError, ValueError):
                continue
    return maximum


def _terminalize_rolled_back_hypothesis(
    owner: Any,
    branch: Any,
    hypothesis_id: str | None,
) -> None:
    if not hypothesis_id:
        raise RuntimeError(
            f"Branch {branch.branch_id}: rolled-back promotion has no hypothesis owner"
        )
    record = owner._hyp_store.get_one(hypothesis_id)
    if record is None or record.branch_id != branch.branch_id:
        raise RuntimeError(
            f"Branch {branch.branch_id}: rolled-back promotion ownership conflict"
        )
    if record.status == "active":
        owner._hyp_store.mark_status(hypothesis_id, "blocked_infra")
        return
    if record.status not in {
        "blocked_infra",
        "rejected",
        "research_rejected",
        "not_evaluated",
        "resource_exhausted",
    }:
        raise RuntimeError(
            f"Branch {branch.branch_id}: rolled-back hypothesis status conflict"
        )


def _latest_candidate_hypothesis_for_branch(
    hypothesis_store: Any,
    branch_id: str,
) -> HypothesisRecord | None:
    records = [
        record
        for record in hypothesis_store.get_by_branch(branch_id)
        if record.status in {"active", "advanced"}
    ]
    return records[-1] if records else None


def _hypothesis_proposal_from_record(record: HypothesisRecord) -> HypothesisProposal:
    return HypothesisProposal(
        hypothesis_text=record.hypothesis_text or "",
        change_locus=record.change_locus,
        action=record.action,  # type: ignore[arg-type]
        target_file=record.target_file,
        predicted_direction=record.predicted_direction,
        suggested_weight=record.suggested_weight,
    )


def _reanchor_current_champion_snapshot(
    owner: Any, current: ChampionState
) -> ChampionState:
    """Prefer the copied campaign's local champion snapshot when hashes match."""
    current_path = os.path.abspath(current.code_snapshot_path)
    campaign_dir = os.path.abspath(owner._campaign_dir)
    if os.path.commonpath([current_path, campaign_dir]) == campaign_dir:
        return current

    local_path = os.path.join(
        campaign_dir,
        "champions",
        f"champion_v{current.version}",
    )
    if not os.path.isdir(local_path):
        return current
    local_hash = owner._materializer.compute_snapshot_hash(local_path)
    if local_hash != current.code_snapshot_hash:
        return current
    return replace(current, code_snapshot_path=local_path)


def _normalize_operator_pool(
    operator_pool: dict[str, Any],
) -> dict[str, OperatorConfig]:
    """Normalize legacy name->weight pools before persistence."""
    normalized: dict[str, OperatorConfig] = {}
    for name, cfg in (operator_pool or {}).items():
        if isinstance(cfg, OperatorConfig):
            normalized[name] = cfg
            continue
        required_attrs = ("name", "file_path", "category", "weight", "class_name")
        if all(hasattr(cfg, attr) for attr in required_attrs):
            normalized[name] = OperatorConfig(
                name=cfg.name,
                file_path=cfg.file_path,
                category=cfg.category,
                weight=float(cfg.weight),
                class_name=cfg.class_name,
            )
            continue
        if isinstance(cfg, dict):
            normalized[name] = OperatorConfig(
                name=str(cfg.get("name", name)),
                file_path=str(cfg.get("file_path", f"operators/{name}.py")),
                category=str(cfg.get("category", name)),
                weight=float(cfg.get("weight", 1.0)),
                class_name=str(cfg.get("class_name", name)),
            )
            continue
        normalized[name] = OperatorConfig(
            name=name,
            file_path=f"operators/{name}.py",
            category=name,
            weight=float(cfg),
            class_name=name,
        )
    return normalized
