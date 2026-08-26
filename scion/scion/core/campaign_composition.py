"""Campaign service composition helpers.

This module owns the constructor-time wiring for CampaignManager.  The manager
remains the public facade and callback owner; service construction lives here so
new runtime boundaries do not keep growing campaign.py.
"""

from __future__ import annotations

import os
import threading
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from scion.contract.gate import ContractGate
from scion.core.async_weight_opt import (
    AsyncWeightOptCoordinator,
    bounded_terminal_wait_timeout,
)
from scion.core.branch import BranchController
from scion.core.branch_step_runner import BranchStepRunner
from scion.core.campaign_loop import CampaignLoop
from scion.core.code_development import CodeDevelopmentEvaluator
from scion.core.code_research_limits import (
    CodeResearchLimits,
    normalize_code_research_limits,
    write_code_research_limits,
)
from scion.core.decision_coordinator import DecisionCoordinator
from scion.core.decision_finalizer import DecisionFinalizer
from scion.core.evaluation_orchestrator import EvaluationOrchestrator
from scion.core.evidence_recording import EvidenceRecorder
from scion.core.explore_step.pipeline import ExploreStepPipeline
from scion.core.models import ChampionState
from scion.core.problem_runtime import ProblemRuntime
from scion.core.production_boundary import (
    validate_fresh_campaign_output,
    validate_production_campaign_boundary,
)
from scion.core.promotion_service import PromotionService
from scion.core.proposal_pipeline import (
    ProposalPipeline,
)
from scion.core.proposal_runtime_telemetry import ProposalRuntimeTelemetry
from scion.core.qualification import (
    QualificationOnlyConfig,
    QualificationRuntime,
    normalize_qualification_only_config,
)
from scion.core.research_history import problem_id_from_spec
from scion.core.research_input import write_research_input
from scion.core.research_rejection_finalizer import ResearchRejectionFinalizer
from scion.core.research_surface_index import editable_patterns
from scion.core.resource_envelope import (
    ProviderCallBudget,
    ResourceEnvelope,
    normalize_resource_envelope,
    write_resource_envelope,
)
from scion.core.scheduler import Scheduler
from scion.core.status_reporter import StatusReporter
from scion.core.verification_factory import CampaignVerificationFactory
from scion.core.weight_opt_committer import WeightOptCommitter
from scion.core.workspace_service import WorkspaceService
from scion.lineage.registry import LineageRegistry
from scion.proposal.engine import CreativeLayer
from scion.runtime.workspace import WorkspaceMaterializer
from scion.verification.development import (
    declared_development_problem_package_paths,
    declared_development_suites,
    declared_development_workspace_paths,
    validate_development_closure_boundary,
)


@dataclass(frozen=True, repr=False)
class _InitialScreeningControlsSetup:
    code_research_limits: CodeResearchLimits
    resource_envelope: ResourceEnvelope
    qualification: QualificationOnlyConfig
    protocol_config: Any
    split_manifest: Any
    seed_ledger: Any
    experiment_protocol: Any
    problem_runtime: ProblemRuntime
    contract_gate: ContractGate
    verification_gate: Any
    development_suites: tuple[Any, ...]
    development_workspace_paths: tuple[str, ...]
    development_problem_package_paths: tuple[str, ...]
    runtime_inputs: Any

    def __repr__(self) -> str:
        return "_InitialScreeningControlsSetup(<redacted>)"

    __str__ = __repr__


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
        "editable_patterns": editable_patterns(problem_spec),
    }


def _normalize_campaign_boundaries(
    *,
    code_research_limits: Any | None,
    qualification_only: Any | None,
    resource_envelope: Any | None,
) -> tuple[
    CodeResearchLimits | None,
    ResourceEnvelope | None,
    QualificationOnlyConfig | None,
]:
    """Validate proposal-study composition before any campaign root is created."""

    normalized_code = (
        None
        if code_research_limits is None
        else normalize_code_research_limits(code_research_limits)
    )
    normalized_qualification = normalize_qualification_only_config(qualification_only)
    k2_candidates = (
        normalized_code is not None and normalized_code.max_hypothesis_candidates == 2
    )
    initial_only = (
        normalized_qualification is not None
        and normalized_qualification.initial_screening_only
    )
    normalized_resource = None
    if k2_candidates or initial_only:
        normalized_resource = normalize_resource_envelope(resource_envelope)
    if k2_candidates:
        bounded_resource = cast(ResourceEnvelope, normalized_resource)
        if normalized_qualification is None:
            raise ValueError("max_hypothesis_candidates=2 requires qualification_only")
        if bounded_resource.provider_call_cap is None:
            raise ValueError(
                "max_hypothesis_candidates=2 requires resource envelope "
                "provider_call_cap"
            )
        if bounded_resource.outer_hardwall_sec is None:
            raise ValueError(
                "max_hypothesis_candidates=2 requires resource envelope "
                "outer_hardwall_sec"
            )
    if initial_only:
        bounded_resource = cast(ResourceEnvelope, normalized_resource)
        if normalized_code is None:
            raise ValueError(
                "initial_screening_only_v1 requires bounded code_research_limits"
            )
        if bounded_resource.provider_call_cap is None:
            raise ValueError(
                "initial_screening_only_v1 requires resource envelope provider_call_cap"
            )
        if bounded_resource.outer_hardwall_sec is None:
            raise ValueError(
                "initial_screening_only_v1 requires resource envelope "
                "outer_hardwall_sec"
            )
    return normalized_code, normalized_resource, normalized_qualification


def _prepare_initial_screening_controls_setup(
    *,
    owner: Any,
    request: Any,
    problem_spec: Any,
    protocol_config: Any,
    split_manifest: Any,
    seed_ledger: Any,
    champion: Any,
    campaign_dir: str,
    experiment_protocol: Any,
    adapter: Any,
    verification_gate: Any | None,
    operator_execute_signature: str | None,
    research_input: Any | None,
    research_history: Any,
    resource_envelope: Any | None,
    code_research_limits: Any | None,
    qualification_only: Any | None,
) -> _InitialScreeningControlsSetup:
    """Publish and return one fixed-error, config-subset runtime setup."""

    from scion.core.initial_screening_study_controls import (
        _ERROR,
        _bind_controls_publication,
        _InitialScreeningStudyControlsError,
        _prepare_initial_screening_runtime_inputs,
        _write_initial_screening_study_controls,
    )

    failed = False
    result: _InitialScreeningControlsSetup | None = None
    try:
        from scion.core.campaign import CampaignManager

        if type(owner) is not CampaignManager:
            raise TypeError
        if verification_gate is not None:
            raise ValueError
        runtime_inputs = _prepare_initial_screening_runtime_inputs(
            request=request,
            qualification=qualification_only,
            code_research_limits=code_research_limits,
            resource_envelope=resource_envelope,
            protocol_config=protocol_config,
            split_manifest=split_manifest,
            seed_ledger=seed_ledger,
            experiment_protocol=experiment_protocol,
            campaign_dir=campaign_dir,
        )
        frozen_config = runtime_inputs.protocol_config
        frozen_manifest = runtime_inputs.split_manifest
        frozen_ledger = runtime_inputs.seed_ledger
        frozen_protocol = runtime_inputs.experiment_protocol
        if type(champion) is not ChampionState:
            raise TypeError
        champion_storage = vars(champion)
        if type(champion_storage) is not dict or any(
            type(key) is not str for key in champion_storage
        ):
            raise TypeError
        champion_snapshot_path = champion_storage.get("code_snapshot_path")
        if (
            type(champion_snapshot_path) is not str
            or not champion_snapshot_path
            or "\x00" in champion_snapshot_path
        ):
            raise TypeError

        development_suites = declared_development_suites(problem_spec)
        development_workspace_paths = declared_development_workspace_paths(problem_spec)
        development_problem_package_paths = declared_development_problem_package_paths(
            problem_spec
        )
        validate_development_closure_boundary(
            problem_spec=problem_spec,
            suites=development_suites,
            workspace_paths=development_workspace_paths,
            problem_package_paths=development_problem_package_paths,
            split_manifest=frozen_manifest,
            champion_root=champion_snapshot_path,
        )
        problem_runtime = ProblemRuntime(
            problem_spec=problem_spec,
            adapter=adapter,
            split_manifest=frozen_manifest,
            seed_ledger=frozen_ledger,
            research_input=research_input,
            research_history=research_history,
            development_suites=development_suites,
        )
        contract_gate = ContractGate(
            problem_spec,
            operator_execute_signature=operator_execute_signature,
            adapter=adapter,
            champion_snapshot_provider=lambda: getattr(
                getattr(owner, "_champion", champion),
                "code_snapshot_path",
                None,
            ),
        )
        frozen_protocol.set_problem_adapter(adapter)
        installed_verification_gate = CampaignVerificationFactory.build(
            problem_spec=problem_spec,
            verification_gate=verification_gate,
            experiment_protocol=frozen_protocol,
            campaign_dir=campaign_dir,
            adapter=adapter,
            operator_execute_signature=operator_execute_signature,
        )
        validate_production_campaign_boundary(
            problem_spec=problem_spec,
            experiment_protocol=frozen_protocol,
            adapter=adapter,
            split_manifest=frozen_manifest,
            seed_ledger=frozen_ledger,
            verification_gate=installed_verification_gate,
        )
        protected_roots = _initial_screening_protected_roots(
            problem_spec=problem_spec,
            champion=champion,
            split_manifest=frozen_manifest,
            development_suites=development_suites,
        )
        publication = _write_initial_screening_study_controls(
            campaign_dir,
            runtime_inputs.payload_bytes,
            protected_roots=protected_roots,
        )
        runtime_inputs = _bind_controls_publication(runtime_inputs, publication)
        result = _InitialScreeningControlsSetup(
            code_research_limits=runtime_inputs.code_research_limits,
            resource_envelope=runtime_inputs.resource_envelope,
            qualification=runtime_inputs.qualification,
            protocol_config=frozen_config,
            split_manifest=frozen_manifest,
            seed_ledger=frozen_ledger,
            experiment_protocol=frozen_protocol,
            problem_runtime=problem_runtime,
            contract_gate=contract_gate,
            verification_gate=installed_verification_gate,
            development_suites=development_suites,
            development_workspace_paths=development_workspace_paths,
            development_problem_package_paths=development_problem_package_paths,
            runtime_inputs=runtime_inputs,
        )
    except Exception:  # noqa: BLE001 - sanitize the private opt-in boundary
        failed = True
    if failed or result is None:
        raise _InitialScreeningStudyControlsError(_ERROR)
    return result


def _initial_screening_protected_roots(
    *,
    problem_spec: Any,
    champion: Any,
    split_manifest: Any,
    development_suites: tuple[Any, ...],
) -> tuple[str, ...]:
    spec_v1 = getattr(problem_spec, "spec_v1", problem_spec)
    candidates = [
        getattr(champion, "code_snapshot_path", None),
        getattr(spec_v1, "root_dir", None),
        *(getattr(split_manifest, "safe_data_roots", ()) or ()),
        *(getattr(suite, "source_root", None) for suite in development_suites),
    ]
    roots: list[str] = []
    for candidate in candidates:
        if candidate is None:
            continue
        if type(candidate) is not str or not candidate or "\x00" in candidate:
            raise TypeError
        root = str(Path(candidate).expanduser().resolve(strict=False))
        if root not in roots:
            roots.append(root)
    return tuple(roots)


def _prepare_legacy_campaign_inputs(
    *,
    problem_spec: Any,
    adapter: Any,
    split_manifest: Any,
    seed_ledger: Any,
    champion: Any,
    campaign_dir: str,
    research_input: Any | None,
    research_history: Any,
    resource_envelope: Any | None,
    code_research_limits: Any | None,
    qualification_only: Any | None,
) -> tuple[
    CodeResearchLimits | None,
    ResourceEnvelope | None,
    QualificationOnlyConfig | None,
    ProblemRuntime,
    tuple[Any, ...],
    tuple[str, ...],
    tuple[str, ...],
]:
    validate_fresh_campaign_output(campaign_dir)
    normalized_code, normalized_resource, normalized_qualification = (
        _normalize_campaign_boundaries(
            code_research_limits=code_research_limits,
            qualification_only=qualification_only,
            resource_envelope=resource_envelope,
        )
    )
    development_suites: tuple[Any, ...] = ()
    development_workspace_paths: tuple[str, ...] = ()
    development_problem_package_paths: tuple[str, ...] = ()
    if normalized_code is not None:
        development_suites = declared_development_suites(problem_spec)
        development_workspace_paths = declared_development_workspace_paths(problem_spec)
        development_problem_package_paths = declared_development_problem_package_paths(
            problem_spec
        )
        validate_development_closure_boundary(
            problem_spec=problem_spec,
            suites=development_suites,
            workspace_paths=development_workspace_paths,
            problem_package_paths=development_problem_package_paths,
            split_manifest=split_manifest,
            champion_root=getattr(champion, "code_snapshot_path", None),
        )
    problem_runtime = ProblemRuntime(
        problem_spec=problem_spec,
        adapter=adapter,
        split_manifest=split_manifest,
        seed_ledger=seed_ledger,
        research_input=research_input,
        research_history=research_history,
        development_suites=development_suites,
    )
    return (
        normalized_code,
        normalized_resource,
        normalized_qualification,
        problem_runtime,
        development_suites,
        development_workspace_paths,
        development_problem_package_paths,
    )


def _install_protocol_boundary(
    owner: Any,
    *,
    controls_setup: _InitialScreeningControlsSetup | None,
    problem_spec: Any,
    split_manifest: Any,
    seed_ledger: Any,
    adapter: Any,
    verification_gate: Any | None,
    operator_execute_signature: str | None,
    campaign_dir: str,
) -> None:
    if controls_setup is not None:
        from scion.core.initial_screening_study_controls import (
            _bind_controls_metrics_directory,
        )

        owner._vgate = controls_setup.verification_gate
        owner._initial_screening_study_controls = _bind_controls_metrics_directory(
            owner._initial_screening_study_controls
        )
        owner._experiment_protocol._progress_callback = owner._on_protocol_progress
        return
    os.makedirs(str(campaign_dir) + "/metrics", exist_ok=True)
    if hasattr(owner._experiment_protocol, "set_problem_adapter"):
        owner._experiment_protocol.set_problem_adapter(adapter)
    owner._vgate = CampaignVerificationFactory.build(
        problem_spec=problem_spec,
        verification_gate=verification_gate,
        experiment_protocol=owner._experiment_protocol,
        campaign_dir=str(campaign_dir),
        adapter=adapter,
        operator_execute_signature=operator_execute_signature,
    )
    validate_production_campaign_boundary(
        problem_spec=problem_spec,
        experiment_protocol=owner._experiment_protocol,
        adapter=adapter,
        split_manifest=split_manifest,
        seed_ledger=seed_ledger,
        verification_gate=owner._vgate,
    )
    if hasattr(owner._experiment_protocol, "set_progress_callback"):
        owner._experiment_protocol.set_progress_callback(owner._on_protocol_progress)


def _initialize_controls_proposal_state(
    proposal_pipeline: ProposalPipeline,
    controls_setup: _InitialScreeningControlsSetup | None,
) -> None:
    if controls_setup is not None:
        proposal_pipeline._last_hypothesis_rejection_reason = None


def _prepare_provider_policy_inputs(
    request: Any,
    controls_request: Any,
    llm_client: Any,
) -> Any | None:
    from scion.core.initial_screening_study_provider_policy import (
        _ERROR as _PROVIDER_POLICY_ERROR,
    )
    from scion.core.initial_screening_study_provider_policy import (
        _InitialScreeningProviderPolicyError,
        _prepare_initial_screening_provider_policy,
        _reject_reused_provider_client_without_marker,
    )

    _reject_reused_provider_client_without_marker(request, llm_client)
    if request is None:
        return None
    if controls_request is None:
        raise _InitialScreeningProviderPolicyError(_PROVIDER_POLICY_ERROR)
    return _prepare_initial_screening_provider_policy(request, llm_client)


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
    experiment_protocol: Any,
    adapter: Any,
    verification_gate: Any | None = None,
    operator_execute_signature: str | None = None,
    research_input: Any | None = None,
    research_history: Any = (),
    resource_envelope: Any | None = None,
    code_research_limits: Any | None = None,
    qualification_only: Any | None = None,
    _initial_screening_study_controls: Any | None = None,
    _initial_screening_provider_policy: Any | None = None,
) -> None:
    """Install CampaignManager services and state on *owner*."""
    provider_policy_inputs = _prepare_provider_policy_inputs(
        _initial_screening_provider_policy,
        _initial_screening_study_controls,
        llm_client,
    )
    controls_setup: _InitialScreeningControlsSetup | None = None
    if _initial_screening_study_controls is None:
        (
            normalized_code_research_limits,
            normalized_resource_envelope,
            normalized_qualification_only,
            problem_runtime,
            _development_suites,
            development_workspace_paths,
            development_problem_package_paths,
        ) = _prepare_legacy_campaign_inputs(
            problem_spec=problem_spec,
            adapter=adapter,
            split_manifest=split_manifest,
            seed_ledger=seed_ledger,
            champion=champion,
            campaign_dir=campaign_dir,
            research_input=research_input,
            research_history=research_history,
            resource_envelope=resource_envelope,
            code_research_limits=code_research_limits,
            qualification_only=qualification_only,
        )
    else:
        controls_setup = _prepare_initial_screening_controls_setup(
            owner=owner,
            request=_initial_screening_study_controls,
            problem_spec=problem_spec,
            protocol_config=protocol_config,
            split_manifest=split_manifest,
            seed_ledger=seed_ledger,
            champion=champion,
            campaign_dir=campaign_dir,
            experiment_protocol=experiment_protocol,
            adapter=adapter,
            verification_gate=verification_gate,
            operator_execute_signature=operator_execute_signature,
            research_input=research_input,
            research_history=research_history,
            resource_envelope=resource_envelope,
            code_research_limits=code_research_limits,
            qualification_only=qualification_only,
        )
        if provider_policy_inputs is not None:
            from scion.core.initial_screening_study_provider_policy import (
                _publish_initial_screening_provider_policy,
            )

            provider_policy_inputs = _publish_initial_screening_provider_policy(
                provider_policy_inputs,
                controls_setup.runtime_inputs.publication,
            )
            owner._initial_screening_provider_policy_active = True
            owner._initial_screening_provider_policy = provider_policy_inputs
        normalized_code_research_limits = controls_setup.code_research_limits
        normalized_resource_envelope = controls_setup.resource_envelope
        normalized_qualification_only = controls_setup.qualification
        protocol_config = controls_setup.protocol_config
        split_manifest = controls_setup.split_manifest
        seed_ledger = controls_setup.seed_ledger
        experiment_protocol = controls_setup.experiment_protocol
        problem_runtime = controls_setup.problem_runtime
        development_workspace_paths = controls_setup.development_workspace_paths
        development_problem_package_paths = (
            controls_setup.development_problem_package_paths
        )
    owner._problem_runtime = problem_runtime
    owner._protocol_config = protocol_config
    owner._resource_envelope = (
        normalized_resource_envelope
        if normalized_resource_envelope is not None
        else normalize_resource_envelope(resource_envelope)
    )
    owner._provider_call_budget = ProviderCallBudget(
        owner._resource_envelope.provider_call_cap
    )
    owner._code_research_limits = normalized_code_research_limits
    owner._proposal_runtime_telemetry = (
        None
        if normalized_code_research_limits is None
        else ProposalRuntimeTelemetry(
            owner._provider_call_budget,
            max_hypothesis_candidates=(
                normalized_code_research_limits.max_hypothesis_candidates
            ),
        )
    )
    owner._qualification_only_config = normalized_qualification_only
    owner._qualification_runtime = (
        QualificationRuntime(owner._qualification_only_config)
        if owner._qualification_only_config is not None
        else None
    )
    owner._initial_screening_study_controls_active = controls_setup is not None
    owner._initial_screening_study_controls = (
        None if controls_setup is None else controls_setup.runtime_inputs
    )
    owner._split_manifest = split_manifest
    owner._seed_ledger = seed_ledger
    owner._llm_client = llm_client
    owner._champion = champion
    owner._campaign_dir = campaign_dir
    # Campaign IDs are ordinary labels used to group records.
    owner._campaign_id = Path(campaign_dir).name or "campaign"
    owner._status_reporter = StatusReporter(campaign_dir)
    owner._last_status_result = None
    owner._current_status_progress = None
    owner._last_stop_reason = None
    owner._external_stop_requested = False
    owner._branch_ctrl = BranchController()
    owner._scheduler = (
        Scheduler()
        if controls_setup is None
        else controls_setup.runtime_inputs.scheduler
    )
    owner._contract_gate = (
        ContractGate(
            problem_spec,
            operator_execute_signature=operator_execute_signature,
            adapter=adapter,
            champion_snapshot_provider=lambda: getattr(
                owner._champion,
                "code_snapshot_path",
                None,
            ),
        )
        if controls_setup is None
        else controls_setup.contract_gate
    )
    owner._decision_coordinator = DecisionCoordinator(config=protocol_config)
    from scion.core.features import SafeFeatureExtractor

    owner._feature_extractor = SafeFeatureExtractor()
    owner._creative = CreativeLayer(
        llm_client,
        trace_dir=f"{campaign_dir}/llm_traces",
        provider_call_budget=owner._provider_call_budget,
    )

    family_taxonomy = getattr(owner._problem_runtime.spec, "family_taxonomy", None)
    owner._experiment_protocol = experiment_protocol
    owner._materializer = WorkspaceMaterializer(
        campaign_dir,
        **_materializer_kwargs_from_problem_spec(problem_spec),
    )
    owner._code_development_evaluator = (
        None
        if owner._code_research_limits is None
        else CodeDevelopmentEvaluator(
            materializer=owner._materializer,
            problem_spec=problem_spec,
            suites=owner._problem_runtime.development_suites,
            workspace_paths=development_workspace_paths,
            problem_package_paths=development_problem_package_paths,
            limits=owner._code_research_limits,
            operator_execute_signature=operator_execute_signature,
        )
    )
    _install_protocol_boundary(
        owner,
        controls_setup=controls_setup,
        problem_spec=problem_spec,
        split_manifest=split_manifest,
        seed_ledger=seed_ledger,
        adapter=adapter,
        verification_gate=verification_gate,
        operator_execute_signature=operator_execute_signature,
        campaign_dir=campaign_dir,
    )

    def _read_promotion_weights(registry_path: str) -> dict[str, float]:
        if (
            owner._problem_runtime.spec.parameter_search.enabled
            and owner._experiment_protocol is not None
        ):
            from scion.runtime.pool_manager import read_weights

            return read_weights(registry_path)
        return {}

    owner._promotion_service = PromotionService(
        snapshot_root=owner._materializer._champions_dir,
        materializer=owner._materializer,
        set_champion=owner._set_promoted_champion,
        promote_branch=owner._transition_promoted_branch,
        mark_stale=owner._branch_ctrl.mark_all_stale,
        read_weights_fn=_read_promotion_weights,
    )

    os.makedirs(campaign_dir, exist_ok=True)
    if owner._code_research_limits is not None:
        write_code_research_limits(campaign_dir, owner._code_research_limits)
    owner._registry = LineageRegistry(os.path.join(campaign_dir, "scion.db"))
    owner._evidence_recorder = EvidenceRecorder(
        campaign_id=owner._campaign_id,
        campaign_dir=campaign_dir,
        status_reporter=owner._status_reporter,
        registry=owner._registry,
        model_id=getattr(llm_client, "model", None),
        protocol_version=getattr(protocol_config, "version", None),
        family_taxonomy=family_taxonomy,
        problem_id=problem_id_from_spec(problem_spec),
    )
    if owner._problem_runtime.research_input is not None:
        write_research_input(
            campaign_dir,
            owner._problem_runtime.research_input,
        )
    write_resource_envelope(campaign_dir, owner._resource_envelope)
    owner._branch_workspaces = {}
    owner._branch_patches = {}
    owner._step_history = []
    owner._round_num = 0

    owner._n_experiments = 0
    owner._start_time = datetime.now()

    owner._balance_exhausted = False
    owner._research_preflight_checked = False
    owner._async_stop_deferral_depth = 0

    owner._champion_lock = threading.Lock()
    owner._workspace_service = WorkspaceService(
        materializer=owner._materializer,
        branch_controller=owner._branch_ctrl,
        branch_workspaces=owner._branch_workspaces,
        champion_lock=owner._champion_lock,
        get_champion=lambda: owner._champion,
    )
    owner._proposal_pipeline = ProposalPipeline(
        creative=owner._creative,
        problem_runtime=owner._problem_runtime,
        branch_workspaces=owner._branch_workspaces,
        champion_lock=owner._champion_lock,
        get_champion=lambda: owner._champion,
        step_history=owner._step_history,
        mark_balance_exhausted=lambda: _mark_balance_exhausted(owner),
        code_research_limits=owner._code_research_limits,
        code_development_evaluator=owner._code_development_evaluator,
        record_hypothesis_candidate_completed=(
            owner._proposal_runtime_telemetry.record_hypothesis_candidate_completed
            if owner._proposal_runtime_telemetry is not None
            else None
        ),
        record_hypothesis_candidate_selected=(
            owner._proposal_runtime_telemetry.record_hypothesis_candidate_selected
            if owner._proposal_runtime_telemetry is not None
            else None
        ),
    )
    _initialize_controls_proposal_state(owner._proposal_pipeline, controls_setup)
    owner._research_rejection_finalizer = ResearchRejectionFinalizer(
        campaign_id=owner._campaign_id,
        registry=owner._registry,
        workspace_service=owner._workspace_service,
        branch_patches=owner._branch_patches,
    )
    owner._weight_opt_coord = AsyncWeightOptCoordinator(owner)
    owner._weight_opt_committer = WeightOptCommitter(
        event_source=owner._weight_opt_coord,
        champion_lock=owner._champion_lock,
        get_champion=lambda: owner._champion,
        set_champion=lambda champion: setattr(owner, "_champion", champion),
        branch_controller=owner._branch_ctrl,
        registry=owner._registry,
        campaign_id=owner._campaign_id,
    )
    owner._decision_finalizer = DecisionFinalizer(
        branch_controller=owner._branch_ctrl,
        branch_patches=owner._branch_patches,
        require_promotable_branch=owner._require_promotable_branch,
        promote_branch=owner._promote_branch,
        record_step_lineage=owner._record_step_lineage,
        discard_branch_workspace=owner._workspace_service.discard_branch_workspace,
        accept_candidate=owner._workspace_service.accept_candidate,
        reject_candidate=owner._workspace_service.reject_candidate,
        initial_screening_only=(
            owner._qualification_only_config is not None
            and owner._qualification_only_config.initial_screening_only
        ),
        registry=owner._registry,
        campaign_id=owner._campaign_id,
    )
    owner._evaluation_orchestrator = EvaluationOrchestrator(
        branch_controller=owner._branch_ctrl,
        champion_lock=owner._champion_lock,
        get_champion=lambda: owner._champion,
        branch_patches=owner._branch_patches,
        branch_workspaces=owner._branch_workspaces,
        experiment_protocol_provider=(
            owner._provide_experiment_protocol
            if controls_setup is not None
            else (lambda: owner._experiment_protocol)
        ),
        feature_extractor=owner._feature_extractor,
        decision_coordinator=owner._decision_coordinator,
        campaign_id=owner._campaign_id,
        registry=owner._registry,
        materializer=owner._materializer,
        begin_status_progress=owner._begin_status_progress,
        end_status_progress=owner._end_status_progress,
        increment_experiment_count=lambda: setattr(
            owner,
            "_n_experiments",
            owner._n_experiments + 1,
        ),
    )
    owner._explore_step_pipeline = ExploreStepPipeline(
        branch_controller=owner._branch_ctrl,
        contract_gate=owner._contract_gate,
        verification_gate=owner._vgate,
        registry=owner._registry,
        campaign_id=owner._campaign_id,
        get_champion=lambda: owner._champion,
        branch_patches=owner._branch_patches,
        branch_workspaces=owner._branch_workspaces,
        increment_round=owner._increment_round,
        generate_hypothesis=owner._round1_generate_hypothesis,
        generate_code=owner._round2_generate_code,
        record_step=owner._record_step,
        setup_workspace=owner._setup_workspace,
        apply_patch=owner._workspace_service.apply_candidate_patch,
        verify_candidate=owner._workspace_service.verify_candidate,
        reject_candidate=owner._workspace_service.reject_candidate,
        discard_branch_workspace=owner._workspace_service.discard_branch_workspace,
        discard_inflight_workspaces=(
            owner._workspace_service.discard_inflight_workspaces
        ),
        initial_screening_only=(
            owner._qualification_only_config is not None
            and owner._qualification_only_config.initial_screening_only
        ),
        finalize_research_rejection=owner._research_rejection_finalizer.finalize,
        evaluate=owner._evaluate,
        apply_decision_and_finalize=owner._apply_decision_and_finalize,
        reserve_proposal_attempt=(
            owner._qualification_runtime.reserve_proposal_attempt
            if owner._qualification_runtime is not None
            else (lambda: None)
        ),
        proposal_attempt_scope=(
            owner._proposal_runtime_telemetry.attempt_scope
            if owner._proposal_runtime_telemetry is not None
            else (lambda _round_num: nullcontext())
        ),
        record_hypothesis_exported=(
            owner._proposal_runtime_telemetry.record_hypothesis_exported
            if owner._proposal_runtime_telemetry is not None
            else (lambda: None)
        ),
        record_patch_completed=(
            owner._proposal_runtime_telemetry.record_patch_completed
            if owner._proposal_runtime_telemetry is not None
            else (lambda: None)
        ),
        record_code_candidate_ready=(
            owner._proposal_runtime_telemetry.record_code_candidate_ready
            if owner._proposal_runtime_telemetry is not None
            else (lambda: None)
        ),
        begin_result_commit=owner._begin_async_stop_deferral,
        end_result_commit=owner._end_async_stop_deferral,
        update_status_progress=owner._update_status_progress,
        step_history=owner._step_history,
    )
    owner._branch_step_runner = BranchStepRunner(
        branch_controller=owner._branch_ctrl,
        scheduler=owner._scheduler,
        champion_lock=owner._champion_lock,
        get_champion=lambda: owner._champion,
        branch_workspaces=owner._branch_workspaces,
        branch_patches=owner._branch_patches,
        experiment_protocol_provider=(
            owner._provide_experiment_protocol
            if controls_setup is not None
            else (lambda: owner._experiment_protocol)
        ),
        contract_gate=owner._contract_gate,
        verification_gate=owner._vgate,
        drain_weight_opt_events=owner._drain_weight_opt_events,
        should_stop=owner.should_stop,
        get_last_stop_reason=lambda: owner._last_stop_reason,
        setup_workspace=owner._setup_workspace,
        evaluate=owner._evaluate,
        apply_decision_and_finalize=owner._apply_decision_and_finalize,
        record_step=owner._record_step,
        run_explore_step=owner._explore_step_pipeline.run,
        run_eval_step_callback=owner._run_eval_step,
        run_reconcile_step_callback=owner._run_reconcile_step,
        increment_round=owner._increment_round,
        registry=owner._registry,
        campaign_id=owner._campaign_id,
        apply_reconcile_candidate=(owner._workspace_service.apply_candidate_patch),
        verify_reconcile_candidate=(owner._workspace_service.verify_candidate),
        reject_reconcile_candidate=(owner._workspace_service.reject_candidate),
        qualification_only=owner._qualification_only_config is not None,
        qualification_runtime=owner._qualification_runtime,
        discard_branch_workspace=owner._workspace_service.discard_branch_workspace,
    )
    owner._campaign_loop = CampaignLoop(
        write_status=lambda **kwargs: owner._write_status(**kwargs),
        drain_weight_opt_events=lambda: owner._drain_weight_opt_events(),
        should_stop=lambda: owner.should_stop(),
        get_last_stop_reason=lambda: owner._last_stop_reason,
        set_last_stop_reason=lambda reason: setattr(owner, "_last_stop_reason", reason),
        run_one_step=(
            (lambda: owner._run_scheduled_step())
            if owner._qualification_only_config is not None
            else (lambda: owner.run_one_step())
        ),
        write_terminal_artifacts=lambda result: owner._write_terminal_artifacts(result),
        get_final_wait_timeout=lambda: bounded_terminal_wait_timeout(
            getattr(
                owner._problem_runtime.spec.parameter_search,
                "final_wait_timeout_sec",
                600.0,
            )
        ),
        wait_weight_opt_all=lambda timeout: owner._weight_opt_coord.wait_all(
            timeout=timeout
        ),
        qualification_runtime=owner._qualification_runtime,
        park_qualification_chain=owner._park_qualification_chain,
        retire_initial_screening_study_chain=(
            owner._retire_initial_screening_study_chain
        ),
        begin_async_stop_deferral=owner._begin_async_stop_deferral,
        end_async_stop_deferral=owner._end_async_stop_deferral,
    )
    if controls_setup is not None:
        from scion.core.initial_screening_study_controls import (
            _register_initial_screening_controls_owner,
        )

        _register_initial_screening_controls_owner(
            owner,
            owner._initial_screening_study_controls,
        )
    if provider_policy_inputs is not None:
        from scion.core.initial_screening_study_provider_policy import (
            _finalize_initial_screening_provider_policy,
        )

        _finalize_initial_screening_provider_policy(owner, provider_policy_inputs)


def required_service_names() -> tuple[str, ...]:
    """Key services expected after composition."""
    return (
        "_vgate",
        "_evidence_recorder",
        "_branch_step_runner",
        "_proposal_pipeline",
        "_campaign_loop",
    )
