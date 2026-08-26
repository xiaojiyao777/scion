from __future__ import annotations

import gc
import json
import os
import stat
import weakref
from pathlib import Path
from types import MethodType, SimpleNamespace
from typing import Any, Self, cast, get_type_hints

import pytest

from scion.config.problem import (
    ProblemSpec,
    ProtocolConfig,
    SearchSpace,
    SeedLedgerConfig,
    SplitManifest,
)
from scion.core.campaign import CampaignManager
from scion.core.campaign_composition import _InitialScreeningControlsSetup
from scion.core.code_research_limits import CodeResearchLimits
from scion.core.initial_screening_study_controls import (
    _ERROR,
    _FILENAME,
    _LIMITATIONS,
    _REGISTERED_OWNERS,
    _SCHEMA_VERSION,
    _SCOPE,
    _InitialScreeningStudyControlsError,
    _InitialScreeningStudyControlsRequest,
)
from scion.core.models import ChampionState
from scion.core.proposal_runtime_telemetry import ProposalRuntimeTelemetry
from scion.core.qualification import QualificationOnlyConfig
from scion.core.resource_envelope import ProviderCallBudget, ResourceEnvelope
from scion.problem.spec import ObjectiveMetricSpec, ObjectivePolicySpec
from scion.protocol.experiment import ExperimentProtocol, SeedLedger, SplitManager
from scion.runtime.runner import ResourceLimits
from scion.runtime.subprocess_runner import LocalSubprocessRunner


class _NoCallClient:
    model = "private-controls-no-call"

    def call_with_tool(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise AssertionError("config-subset construction dispatched a provider")


def _wrong_bound_method(*_args: Any, **_kwargs: Any) -> None:
    return None


def _qualification(cap: int = 2) -> QualificationOnlyConfig:
    return QualificationOnlyConfig(
        max_proposal_attempts=cap,
        max_verified_candidate_chains=cap,
        max_formal_screening_stages=cap,
        development_boundary_mode="initial_screening_only_v1",
    )


def _protocol_config() -> ProtocolConfig:
    return ProtocolConfig.model_validate(
        {
            "version": "controls-v1",
            "screening": {
                "n_cases_modify": 2,
                "n_cases_create": 2,
                "n_seeds": 1,
                "expand_n_seeds": None,
                "expand_to_modify": 3,
                "expand_to_create": 3,
                "priority_case_ids": ["cases/alpha.vrp"],
                "expose": "full",
                "require_expanded_for_pass": False,
            },
            "canary": {
                "cases": ["cases/canary.vrp"],
                "seeds": [97],
            },
            "runtime": {
                "runtime_model": "comparative",
                "max_runtime_ratio": 1.75,
                "tie_speedup_ratio": 0.8,
                "tie_min_runtime_pairs": 2,
                "time_limits": {
                    "stage_defaults": {"screening": 17, "canary": 9},
                    "rules": [
                        {
                            "time_limit_sec": 23,
                            "stages": ["screening"],
                            "case_globs": ["*beta.vrp"],
                        }
                    ],
                },
            },
            "effect_metric": "cost",
            "protected_objectives": ["feasible"],
            "case_aggregation": "paired_effect_median",
            "case_equivalence_band": 0.125,
        }
    )


def _split() -> SplitManifest:
    return SplitManifest(
        version="controls-split-v1",
        screening=["cases/alpha.vrp", "cases/beta.vrp", "cases/gamma.vrp"],
        validation=["cases/validation.vrp"],
        frozen=["cases/frozen.vrp"],
        canary=["cases/canary.vrp"],
        safe_data_roots=[],
    )


def _ledger() -> SeedLedgerConfig:
    return SeedLedgerConfig(
        version="controls-seeds-v1",
        screening=[11, 29],
        validation=[41],
        frozen=[53],
        canary=[97],
    )


def _problem(root: Path) -> ProblemSpec:
    return ProblemSpec(
        name="private_controls_problem",
        root_dir=str(root),
        operator_categories=["local_search"],
        search_space=SearchSpace(
            editable=["operators/*.py"],
            frozen=["solver.py"],
            import_whitelist=["math"],
        ),
    )


def _manager(
    tmp_path: Path,
    *,
    request: _InitialScreeningStudyControlsRequest | None = None,
    campaign_dir: Path | None = None,
    protocol_config: ProtocolConfig | None = None,
    split_manifest: SplitManifest | None = None,
    seed_ledger: SeedLedgerConfig | None = None,
    strict_case_paths: bool = True,
    operator_execute_signature: str | None = None,
    protocol_metrics_dir: Path | None = None,
    protocol_mutator: Any | None = None,
    boundary_mutator: Any | None = None,
    provider_call_cap: int = 200,
    manager_type: type[CampaignManager] = CampaignManager,
    champion_snapshot_path: Any | None = None,
    boundary_overrides: dict[str, Any] | None = None,
) -> tuple[CampaignManager, dict[str, Any], dict[str, Any]]:
    champion_root = tmp_path / "champion"
    (champion_root / "operators").mkdir(parents=True, exist_ok=True)
    (champion_root / "operators" / "local_search.py").write_text(
        "class LocalSearch:\n    pass\n",
        encoding="utf-8",
    )
    (champion_root / "solver.py").write_text("# solver\n", encoding="utf-8")
    config = protocol_config or _protocol_config()
    manifest = split_manifest or _split()
    ledger = seed_ledger or _ledger()
    metric = ObjectiveMetricSpec(
        name="cost",
        direction="minimize",
        priority=1,
        tie_tolerance=0.25,
        weight=1.0,
    )
    objective = ObjectivePolicySpec(
        mode="weighted_sum",
        expose_weights_to_llm=False,
    )
    runner = LocalSubprocessRunner(ResourceLimits(timeout_sec=30, memory_mb=512))
    protocol = ExperimentProtocol(
        protocol_config=config,
        split_manager=SplitManager(manifest),
        seed_ledger=SeedLedger(ledger),
        runner=runner,
        time_limit_sec=31,
        metrics_dir=str(protocol_metrics_dir or (tmp_path / "external-metrics")),
        metric_specs=(metric,),
        objective_policy=objective,
        problem_spec=_problem(champion_root),
    )
    protocol._strict_case_paths = strict_case_paths
    if protocol_mutator is not None:
        protocol_mutator(protocol)
    spec = protocol.problem_spec
    qualification = _qualification()
    resource = ResourceEnvelope(
        provider_call_cap=provider_call_cap,
        outer_hardwall_sec=60,
    )
    code_limits = CodeResearchLimits(max_hypothesis_candidates=1)
    qualification_input = qualification
    resource_input = resource
    code_limits_input = code_limits
    if boundary_overrides is not None:
        qualification_input = boundary_overrides.get("qualification", qualification)
        resource_input = boundary_overrides.get("resource", resource)
        code_limits_input = boundary_overrides.get("code_limits", code_limits)
    if boundary_mutator is not None:
        boundary_mutator(qualification, code_limits, resource)
    manager = manager_type(
        problem_spec=spec,
        protocol_config=config,
        split_manifest=manifest,
        seed_ledger=ledger,
        llm_client=_NoCallClient(),
        champion=ChampionState(
            version=1,
            operator_pool={},
            code_snapshot_path=(
                str(champion_root)
                if champion_snapshot_path is None
                else champion_snapshot_path
            ),
        ),
        campaign_dir=str(campaign_dir or (tmp_path / "campaign")),
        experiment_protocol=protocol,
        adapter=SimpleNamespace(spec=spec),
        operator_execute_signature=operator_execute_signature,
        qualification_only=qualification_input,
        resource_envelope=resource_input,
        code_research_limits=code_limits_input,
        _initial_screening_study_controls=request,
    )
    return (
        manager,
        {
            "config": config,
            "manifest": manifest,
            "ledger": ledger,
            "qualification": qualification,
            "resource": resource,
            "code_limits": code_limits,
            "protocol": protocol,
            "runner": runner,
        },
        {
            "metric": metric,
            "objective": objective,
        },
    )


def _fixed_error(error: BaseException) -> None:
    assert type(error) is _InitialScreeningStudyControlsError
    assert str(error) == _ERROR
    assert error.args == (_ERROR,)
    assert error.__cause__ is None
    assert error.__context__ is None


def test_opt_in_writes_exact_private_subset_before_workspace_side_effect(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scion.core import campaign_composition

    campaign_dir = tmp_path / "campaign"
    original_init = campaign_composition.WorkspaceMaterializer.__init__
    observed: list[set[str]] = []

    def guarded_init(self: Any, root: str, **kwargs: Any) -> None:
        observed.append({entry.name for entry in Path(root).iterdir()})
        original_init(self, root, **kwargs)

    monkeypatch.setattr(
        campaign_composition.WorkspaceMaterializer,
        "__init__",
        guarded_init,
    )
    manager, aliases, objectives = _manager(
        tmp_path,
        request=_InitialScreeningStudyControlsRequest(requested_rounds=2),
        campaign_dir=campaign_dir,
    )

    assert observed == [{_FILENAME}]
    controls_path = campaign_dir / _FILENAME
    payload = json.loads(controls_path.read_text(encoding="utf-8"))
    assert set(payload) == {
        "schema_version",
        "scope",
        "limitations",
        "campaign",
        "code_research_limits",
        "resource_envelope",
        "protocol",
    }
    assert payload["schema_version"] == (
        "scion.initial_screening_study_controls.config_subset.v1"
    )
    assert payload["scope"] == "CONFIG_SUBSET_ONLY"
    expected_limitations = (
        "PROBLEM_SPEC_UNVERIFIED",
        "PROBLEM_ADAPTER_UNVERIFIED",
        "RESEARCH_INPUT_UNVERIFIED",
        "RESEARCH_HISTORY_UNVERIFIED",
        "VERIFICATION_CONFIG_AND_RUNTIME_UNVERIFIED",
        "PROVIDER_REQUEST_POLICY_UNVERIFIED",
        "REMOTE_PROVIDER_BACKEND_IDENTITY_UNVERIFIED",
        "SOURCE_CARRIER_UNVERIFIED",
        "B0_CONTENT_UNVERIFIED",
        "STUDY_MANIFEST_UNVERIFIED",
        "POPULATION_FRESHNESS_UNVERIFIED",
        "ARM_ROOT_LAUNCH_ORDER_UNVERIFIED",
        "EXTERNAL_HARDWALL_ENFORCEMENT_UNVERIFIED",
        "PROTOCOL_RUNNER_BACKEND_AND_RUNTIME_ENFORCEMENT_UNVERIFIED",
        "PROTOCOL_CODE_CONSTANTS_UNVERIFIED",
        "ROOT_LIFETIME_FRESHNESS_UNVERIFIED",
        "MATCHED_RESULT_UNAUTHORIZED",
        "LIVE_EXECUTION_UNAUTHORIZED",
        "STUDY_GO_UNAUTHORIZED",
    )
    assert _LIMITATIONS == expected_limitations
    assert tuple(payload["limitations"]) == expected_limitations
    assert set(payload["campaign"]) == {
        "campaign_mode",
        "development_boundary_mode",
        "qualification_limits",
        "requested_rounds",
        "scheduler",
    }
    assert set(payload["protocol"]) == {
        "canary",
        "initial_screening",
        "safe_data_roots",
        "strict_case_paths",
        "time_limit_fallback_sec",
        "version",
    }
    assert set(payload["protocol"]["initial_screening"]) == {
        "cases_by_action",
        "effect_policy",
        "measurement_readiness",
        "resolved_time_limits",
        "runtime_time_limits",
        "screening_gate",
        "seeds",
        "selection",
    }
    assert set(payload["protocol"]["canary"]) == {
        "cases",
        "resolved_time_limits",
        "seeds",
    }
    assert payload["campaign"]["requested_rounds"] == 2
    assert payload["campaign"]["scheduler"] == {"max_active_branches": 3}
    assert payload["protocol"]["strict_case_paths"] is True
    assert payload["protocol"]["initial_screening"]["cases_by_action"] == {
        "create_new": ["cases/alpha.vrp", "cases/gamma.vrp"],
        "modify_or_remove": ["cases/alpha.vrp", "cases/gamma.vrp"],
    }
    assert payload["protocol"]["initial_screening"]["seeds"] == [11, 29]
    assert payload["protocol"]["initial_screening"]["resolved_time_limits"] == [
        {"case_ref": "cases/alpha.vrp", "time_limit_sec": 17},
        {"case_ref": "cases/gamma.vrp", "time_limit_sec": 17},
    ]
    assert payload["protocol"]["canary"]["resolved_time_limits"] == [
        {"case_ref": "cases/canary.vrp", "time_limit_sec": 9}
    ]
    assert payload["protocol"]["initial_screening"]["effect_policy"][
        "metric_specs"
    ] == [
        {
            "direction": "minimize",
            "name": "cost",
            "priority": 1,
            "tie_tolerance": 0.25,
            "weight": 1.0,
        }
    ]
    assert stat.S_IMODE(campaign_dir.stat().st_mode) == 0o700
    assert stat.S_IMODE(controls_path.stat().st_mode) == 0o600
    assert controls_path.stat().st_nlink == 1
    assert manager._protocol_config is manager._experiment_protocol.config
    assert manager._problem_runtime.split_manifest is manager._split_manifest
    assert manager._problem_runtime.seed_ledger is manager._seed_ledger
    assert manager._scheduler is manager._initial_screening_study_controls.scheduler
    assert manager._experiment_protocol.metrics_dir == str(campaign_dir / "metrics")
    assert manager._vgate._metrics_dir == str(campaign_dir / "metrics")
    assert stat.S_IMODE((campaign_dir / "metrics").stat().st_mode) == 0o700
    assert list((campaign_dir / "metrics").iterdir()) == []
    assert manager._protocol_config is not aliases["config"]
    assert manager._split_manifest is not aliases["manifest"]
    assert manager._seed_ledger is not aliases["ledger"]
    assert manager._experiment_protocol._metric_specs[0] is not objectives["metric"]
    assert manager._experiment_protocol._objective_policy is not objectives["objective"]
    assert manager._qualification_only_config is not aliases["qualification"]
    assert manager._code_research_limits is not aliases["code_limits"]
    assert manager._resource_envelope is not aliases["resource"]
    assert aliases["protocol"].metrics_dir == str(tmp_path / "external-metrics")
    assert aliases["runner"]._progress_callback is None


def test_opt_in_detaches_caller_models_and_run_accepts_exact_a(tmp_path: Path) -> None:
    manager, aliases, objectives = _manager(
        tmp_path,
        request=_InitialScreeningStudyControlsRequest(requested_rounds=2),
    )
    artifact = (tmp_path / "campaign" / _FILENAME).read_bytes()
    aliases["config"].screening.n_cases_modify = 1
    aliases["manifest"].screening[0] = "cases/caller-mutated.vrp"
    aliases["ledger"].screening[0] = 999
    objectives["metric"].name = "caller_mutated_metric"
    objectives["objective"].mode = "single"
    object.__setattr__(
        aliases["qualification"], "development_boundary_mode", "qualification_v1"
    )
    object.__setattr__(aliases["code_limits"], "max_read_calls", 99)
    object.__setattr__(aliases["resource"], "provider_call_cap", 1)
    assert (tmp_path / "campaign" / _FILENAME).read_bytes() == artifact
    assert manager._protocol_config.screening.n_cases_modify == 2
    assert manager._split_manifest.screening[0] == "cases/alpha.vrp"
    assert manager._seed_ledger.screening[0] == 11
    assert manager._experiment_protocol._metric_specs[0].name == "cost"
    assert manager._experiment_protocol._objective_policy.mode == "weighted_sum"
    assert manager._qualification_only_config.initial_screening_only
    assert manager._code_research_limits.max_read_calls == 3
    assert manager._resource_envelope.provider_call_cap == 200

    calls: list[str] = []
    manager._run_research_environment_preflight = lambda: calls.append("preflight")

    def run_terminal(*, requested_rounds: int) -> str:
        calls.append(f"run:{requested_rounds}")
        return "terminal"

    manager._campaign_loop.run = run_terminal
    assert manager.run(2) == "terminal"
    assert calls == ["preflight", "run:2"]


@pytest.mark.parametrize("value", [True, 2.0, "2", 1, 3])
def test_opt_in_round_gate_is_exact_and_precedes_preflight(
    tmp_path: Path,
    value: object,
) -> None:
    manager, _aliases, _objectives = _manager(
        tmp_path,
        request=_InitialScreeningStudyControlsRequest(requested_rounds=2),
    )
    manager._run_research_environment_preflight = lambda: pytest.fail(
        "preflight ran before controls gate"
    )

    with pytest.raises(_InitialScreeningStudyControlsError) as caught:
        manager.run(value)  # type: ignore[arg-type]

    _fixed_error(caught.value)
    assert not (tmp_path / "campaign" / "status.json").exists()


@pytest.mark.parametrize(
    "mutation",
    [
        "config",
        "split",
        "seed",
        "metric",
        "objective",
        "time_limit",
        "strict_case_paths",
        "scheduler",
        "code_limits",
        "resource",
        "qualification",
        "qualification_mode",
        "branch_scheduler",
        "branch_gate",
        "explore_gate",
        "proposal_limits",
        "evaluator_limits",
        "provider_budget",
        "loop_qualification",
        "retirement_callback",
        "park_callback",
        "reserve_callback",
        "attempt_callback",
        "protocol_provider",
        "branch_protocol_provider",
        "metrics_dir",
        "metrics_equal_str",
        "vgate_metrics_dir",
        "vgate_metrics_equal_str",
        "initial_only_flag",
        "decision_initial_only_flag",
    ],
)
def test_run_gate_rejects_installed_consumer_drift(
    tmp_path: Path,
    mutation: str,
) -> None:
    manager, _aliases, _objectives = _manager(
        tmp_path,
        request=_InitialScreeningStudyControlsRequest(requested_rounds=2),
    )
    if mutation == "config":
        manager._protocol_config.screening.n_cases_modify = 1
    elif mutation == "split":
        manager._split_manifest.screening[0] = "cases/drift.vrp"
    elif mutation == "seed":
        manager._seed_ledger.screening[0] = 101
    elif mutation == "metric":
        manager._experiment_protocol._metric_specs[0].name = "drift"
    elif mutation == "objective":
        manager._experiment_protocol._objective_policy.mode = "single"
    elif mutation == "time_limit":
        manager._experiment_protocol.time_limit_sec = 99
    elif mutation == "strict_case_paths":
        manager._experiment_protocol._strict_case_paths = False
    elif mutation == "scheduler":
        manager._scheduler._max_active_branches = 1
    elif mutation == "code_limits":
        manager._code_research_limits = CodeResearchLimits()
    elif mutation == "resource":
        manager._resource_envelope = ResourceEnvelope(200, 60)
    elif mutation == "qualification":
        manager._qualification_only_config = _qualification()
    elif mutation == "qualification_mode":
        object.__setattr__(
            manager._qualification_only_config,
            "development_boundary_mode",
            "qualification_v1",
        )
    elif mutation == "branch_scheduler":
        manager._branch_step_runner.scheduler = type(manager._scheduler)()
    elif mutation == "branch_gate":
        manager._branch_step_runner.verification_gate = object()
    elif mutation == "explore_gate":
        manager._explore_step_pipeline.verification_gate = object()
    elif mutation == "proposal_limits":
        manager._proposal_pipeline.code_research_limits = CodeResearchLimits()
    elif mutation == "evaluator_limits":
        object.__setattr__(
            manager._code_development_evaluator,
            "limits",
            CodeResearchLimits(),
        )
    elif mutation == "provider_budget":
        manager._creative._provider_calls._provider_call_budget = None
    elif mutation == "loop_qualification":
        manager._campaign_loop.qualification_runtime = None
    elif mutation == "retirement_callback":
        manager._campaign_loop.retire_initial_screening_study_chain = MethodType(
            _wrong_bound_method,
            manager,
        )
    elif mutation == "park_callback":
        manager._campaign_loop.park_qualification_chain = MethodType(
            _wrong_bound_method,
            manager,
        )
    elif mutation == "reserve_callback":
        manager._explore_step_pipeline.reserve_proposal_attempt = MethodType(
            _wrong_bound_method,
            manager._qualification_runtime,
        )
    elif mutation == "attempt_callback":
        manager._explore_step_pipeline.proposal_attempt_scope = MethodType(
            _wrong_bound_method,
            manager._proposal_runtime_telemetry,
        )
    elif mutation == "protocol_provider":
        manager._evaluation_orchestrator.experiment_protocol_provider = lambda: None
    elif mutation == "branch_protocol_provider":
        manager._branch_step_runner.experiment_protocol_provider = lambda: None
    elif mutation == "metrics_dir":
        manager._experiment_protocol.metrics_dir = str(tmp_path / "elsewhere")
    elif mutation == "metrics_equal_str":
        manager._experiment_protocol.metrics_dir = type(
            "EqualStr",
            (str,),
            {"__eq__": lambda self, _other: True, "__ne__": lambda self, _other: False},
        )(str(tmp_path / "champion"))
    elif mutation == "vgate_metrics_dir":
        manager._vgate._metrics_dir = str(tmp_path / "elsewhere")
    elif mutation == "vgate_metrics_equal_str":
        manager._vgate._metrics_dir = type(
            "EqualStr",
            (str,),
            {"__eq__": lambda self, _other: True, "__ne__": lambda self, _other: False},
        )(str(tmp_path / "champion"))
    elif mutation == "initial_only_flag":
        manager._explore_step_pipeline.initial_screening_only = False
    elif mutation == "decision_initial_only_flag":
        manager._decision_finalizer.initial_screening_only = False
    manager._run_research_environment_preflight = lambda: pytest.fail(
        "preflight ran after consumer drift"
    )

    with pytest.raises(_InitialScreeningStudyControlsError) as caught:
        manager.run(2)

    _fixed_error(caught.value)


def test_run_gate_does_not_execute_replaced_protocol_provider(
    tmp_path: Path,
) -> None:
    manager, _aliases, _objectives = _manager(
        tmp_path,
        request=_InitialScreeningStudyControlsRequest(requested_rounds=2),
    )
    calls: list[str] = []

    def side_effecting_provider() -> Any:
        calls.append("called")
        return manager._experiment_protocol

    manager._evaluation_orchestrator.experiment_protocol_provider = (
        side_effecting_provider
    )
    with pytest.raises(_InitialScreeningStudyControlsError) as caught:
        manager.run(2)

    _fixed_error(caught.value)
    assert calls == []


@pytest.mark.parametrize(
    "kind",
    ["qualification", "code_limits", "resource", "config", "split", "seed"],
)
def test_opt_in_rejects_claimed_serializer_shadows_before_root(
    tmp_path: Path,
    kind: str,
) -> None:
    config = _protocol_config()
    manifest = _split()
    ledger = _ledger()

    def mutate_boundaries(
        qualification: QualificationOnlyConfig,
        code_limits: CodeResearchLimits,
        resource: ResourceEnvelope,
    ) -> None:
        targets = {
            "qualification": (qualification, "to_projection"),
            "code_limits": (code_limits, "to_primitive"),
            "resource": (resource, "to_primitive"),
        }
        if kind in targets:
            target, name = targets[kind]
            object.__setattr__(target, name, dict)

    model_targets = {
        "config": config,
        "split": manifest,
        "seed": ledger,
    }
    if kind in model_targets:
        object.__setattr__(model_targets[kind], "model_dump", lambda **_kwargs: {})

    with pytest.raises(_InitialScreeningStudyControlsError) as caught:
        _manager(
            tmp_path,
            request=_InitialScreeningStudyControlsRequest(requested_rounds=2),
            protocol_config=config,
            split_manifest=manifest,
            seed_ledger=ledger,
            boundary_mutator=mutate_boundaries,
        )

    _fixed_error(caught.value)
    assert not (tmp_path / "campaign").exists()


@pytest.mark.parametrize("surface", ["qualification", "code_limits", "resource"])
def test_opt_in_freezes_boundaries_before_behavioral_comparisons(
    tmp_path: Path,
    surface: str,
) -> None:
    hooks: list[str] = []

    class SideEffectInt(int):
        def __eq__(self, _other: object) -> bool:
            hooks.append("integer-equality")
            return True

    class SideEffectStr(str):
        def __eq__(self, _other: object) -> bool:
            hooks.append("string-equality")
            return True

    def mutate_boundaries(
        qualification: QualificationOnlyConfig,
        code_limits: CodeResearchLimits,
        resource: ResourceEnvelope,
    ) -> None:
        if surface == "qualification":
            object.__setattr__(
                qualification,
                "development_boundary_mode",
                SideEffectStr("initial_screening_only_v1"),
            )
        elif surface == "code_limits":
            object.__setattr__(
                code_limits,
                "max_hypothesis_candidates",
                SideEffectInt(1),
            )
        else:
            object.__setattr__(resource, "provider_call_cap", SideEffectInt(200))

    with pytest.raises(_InitialScreeningStudyControlsError) as caught:
        _manager(
            tmp_path,
            request=_InitialScreeningStudyControlsRequest(requested_rounds=2),
            boundary_mutator=mutate_boundaries,
        )

    _fixed_error(caught.value)
    assert hooks == []
    assert not (tmp_path / "campaign").exists()


@pytest.mark.parametrize("surface", ["boundary_mapping", "split_list"])
def test_opt_in_rejects_raw_container_subclasses_without_hooks(
    tmp_path: Path,
    surface: str,
) -> None:
    hooks: list[str] = []

    class SideEffectDict(dict):
        def __iter__(self) -> Any:
            hooks.append("mapping-iteration")
            return super().__iter__()

        def items(self) -> Any:
            hooks.append("mapping-items")
            return super().items()

        def get(self, *_args: Any, **_kwargs: Any) -> Any:
            hooks.append("mapping-get")
            return super().get(*_args, **_kwargs)

    class SideEffectList(list):
        def __iter__(self) -> Any:
            hooks.append("list-iteration")
            return super().__iter__()

    boundary_overrides: dict[str, Any] | None = None
    manifest = _split()
    if surface == "boundary_mapping":
        boundary_overrides = {
            "code_limits": SideEffectDict(
                CodeResearchLimits(max_hypothesis_candidates=1).to_primitive()
            )
        }
    else:
        object.__setattr__(
            manifest,
            "screening",
            SideEffectList(manifest.screening),
        )

    with pytest.raises(_InitialScreeningStudyControlsError) as caught:
        _manager(
            tmp_path,
            request=_InitialScreeningStudyControlsRequest(requested_rounds=2),
            split_manifest=manifest,
            boundary_overrides=boundary_overrides,
        )

    _fixed_error(caught.value)
    assert hooks == []
    assert not (tmp_path / "campaign").exists()


def test_legacy_campaign_still_normalizes_boundary_mappings(tmp_path: Path) -> None:
    manager, _aliases, _objectives = _manager(
        tmp_path,
        request=None,
        boundary_overrides={
            "qualification": {
                "max_proposal_attempts": 2,
                "max_verified_candidate_chains": 2,
                "max_formal_screening_stages": 2,
                "development_boundary_mode": "qualification_v1",
            },
            "code_limits": CodeResearchLimits(
                max_hypothesis_candidates=1
            ).to_primitive(),
            "resource": {
                "provider_call_cap": 200,
                "outer_hardwall_sec": 60,
            },
        },
    )

    assert type(manager._qualification_only_config) is QualificationOnlyConfig
    assert type(manager._code_research_limits) is CodeResearchLimits
    assert type(manager._resource_envelope) is ResourceEnvelope
    assert manager._qualification_only_config.development_boundary_mode == (
        "qualification_v1"
    )
    assert not (tmp_path / "campaign" / _FILENAME).exists()


@pytest.mark.parametrize(
    "kind",
    [
        "qualification",
        "code_limits",
        "resource",
        "config",
        "screening",
        "canary",
        "screening_gate",
        "runtime",
        "time_limits",
        "time_rule",
        "readiness",
        "split",
        "seed",
        "metric",
        "objective",
    ],
)
def test_run_gate_rejects_claimed_config_tree_instance_shadows(
    tmp_path: Path,
    kind: str,
) -> None:
    manager, _aliases, _objectives = _manager(
        tmp_path,
        request=_InitialScreeningStudyControlsRequest(requested_rounds=2),
    )
    targets: dict[str, tuple[Any, str]] = {
        "qualification": (manager._qualification_only_config, "to_projection"),
        "code_limits": (manager._code_research_limits, "to_primitive"),
        "resource": (manager._resource_envelope, "to_primitive"),
        "config": (manager._protocol_config, "_resolve_delta_reference"),
        "screening": (manager._protocol_config.screening, "model_dump"),
        "canary": (manager._protocol_config.canary, "model_dump"),
        "screening_gate": (
            manager._protocol_config.gates.screening,
            "model_dump",
        ),
        "runtime": (manager._protocol_config.runtime, "model_dump"),
        "time_limits": (
            manager._protocol_config.runtime.time_limits,
            "resolve",
        ),
        "time_rule": (
            manager._protocol_config.runtime.time_limits.rules[0],
            "matches",
        ),
        "readiness": (
            manager._protocol_config.measurement_readiness,
            "to_readiness_status_payload",
        ),
        "split": (manager._split_manifest, "model_dump"),
        "seed": (manager._seed_ledger, "model_dump"),
        "metric": (manager._experiment_protocol._metric_specs[0], "model_dump"),
        "objective": (manager._experiment_protocol._objective_policy, "model_dump"),
    }
    target, name = targets[kind]
    object.__setattr__(target, name, lambda *_args, **_kwargs: {})
    manager._run_research_environment_preflight = lambda: pytest.fail(
        "preflight ran after claimed config shadow"
    )

    with pytest.raises(_InitialScreeningStudyControlsError) as caught:
        manager.run(2)

    _fixed_error(caught.value)


@pytest.mark.parametrize(
    "mutation",
    [
        "qualification_mode",
        "metric_direction",
        "split_canary",
        "split_safe_roots",
        "seed_screening",
        "screening_priority",
        "time_rule_stages",
        "config_dict",
        "config_evil_key",
    ],
)
def test_run_gate_rejects_nonbuiltin_claimed_config_shapes_before_use(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    from scion.core import initial_screening_study_controls_validation as controls

    manager, _aliases, _objectives = _manager(
        tmp_path,
        request=_InitialScreeningStudyControlsRequest(requested_rounds=2),
    )
    hooks: list[str] = []

    class SideEffectStr(str):
        __hash__ = str.__hash__

        def __eq__(self, _other: object) -> bool:
            hooks.append("str-equality")
            return True

        def __ne__(self, _other: object) -> bool:
            hooks.append("str-inequality")
            return False

    class SideEffectList(list):
        def __iter__(self) -> Any:
            hooks.append("list-iteration")
            return super().__iter__()

    class SideEffectTuple(tuple):
        def __iter__(self) -> Any:
            hooks.append("tuple-iteration")
            return super().__iter__()

    class HiddenDict(dict):
        def __iter__(self) -> Any:
            hooks.append("dict-iteration")
            return super().__iter__()

    if mutation == "qualification_mode":
        object.__setattr__(
            manager._qualification_only_config,
            "development_boundary_mode",
            SideEffectStr("initial_screening_only_v1"),
        )
    elif mutation == "metric_direction":
        object.__setattr__(
            manager._experiment_protocol._metric_specs[0],
            "direction",
            SideEffectStr("minimize"),
        )
    elif mutation == "split_canary":
        object.__setattr__(
            manager._split_manifest,
            "canary",
            SideEffectList(manager._split_manifest.canary),
        )
    elif mutation == "split_safe_roots":
        object.__setattr__(
            manager._split_manifest,
            "safe_data_roots",
            SideEffectList(manager._split_manifest.safe_data_roots),
        )
    elif mutation == "seed_screening":
        object.__setattr__(
            manager._seed_ledger,
            "screening",
            SideEffectList(manager._seed_ledger.screening),
        )
    elif mutation == "screening_priority":
        object.__setattr__(
            manager._protocol_config.screening,
            "priority_case_ids",
            SideEffectTuple(manager._protocol_config.screening.priority_case_ids),
        )
    elif mutation == "time_rule_stages":
        rule = manager._protocol_config.runtime.time_limits.rules[0]
        object.__setattr__(rule, "stages", SideEffectTuple(rule.stages))
    elif mutation == "config_dict":
        hidden_storage = HiddenDict(vars(manager._protocol_config))
        hidden_storage["_resolve_delta_reference"] = lambda *_args: 0.125
        object.__setattr__(manager._protocol_config, "__dict__", hidden_storage)
    else:
        evil_storage = dict(vars(manager._protocol_config))
        version = evil_storage.pop("version")
        evil_storage[SideEffectStr("version")] = version
        object.__setattr__(manager._protocol_config, "__dict__", evil_storage)
    monkeypatch.setattr(
        controls,
        "_validate_controls_publication",
        lambda *_args, **_kwargs: hooks.append("controls-filesystem"),
    )
    monkeypatch.setattr(
        controls,
        "_validate_private_child_directory",
        lambda *_args, **_kwargs: hooks.append("metrics-filesystem"),
    )
    manager._run_research_environment_preflight = lambda: pytest.fail(
        "preflight ran after nonbuiltin claimed config shape"
    )

    with pytest.raises(_InitialScreeningStudyControlsError) as caught:
        manager.run(2)

    _fixed_error(caught.value)
    assert hooks == []


@pytest.mark.parametrize(
    ("surface", "method"),
    [
        ("protocol", "run_experiment"),
        ("protocol", "run_canary"),
        ("protocol", "_select_cases"),
        ("protocol", "_select_seeds"),
        ("protocol", "resolve_time_limit_sec"),
        ("protocol", "time_limit_policy_summary"),
        ("protocol", "_emit_progress"),
        ("protocol", "_resolve_case_path"),
        ("protocol", "_resolve_case_path_status"),
        ("protocol", "_compare_objectives"),
        ("protocol", "_compute_delta"),
        ("split", "get_cases"),
        ("split", "get_canary_cases"),
        ("split", "safe_data_roots"),
        ("seed", "get_seeds"),
        ("seed", "get_canary_seeds"),
    ],
)
def test_run_gate_rejects_post_constructor_protocol_method_shadows(
    tmp_path: Path,
    surface: str,
    method: str,
) -> None:
    manager, _aliases, _objectives = _manager(
        tmp_path,
        request=_InitialScreeningStudyControlsRequest(requested_rounds=2),
    )
    protocol = manager._experiment_protocol
    target = {
        "protocol": protocol,
        "split": protocol.split_manager,
        "seed": protocol.seed_ledger,
    }[surface]
    calls: list[str] = []
    setattr(target, method, lambda *_args, **_kwargs: calls.append(method))

    with pytest.raises(_InitialScreeningStudyControlsError) as caught:
        manager.run(2)

    _fixed_error(caught.value)
    assert calls == []


@pytest.mark.parametrize(
    "kind",
    [
        "scheduler",
        "budget_consume",
        "provider_call",
        "creative_hypothesis",
        "creative_code",
        "creative_code_research",
        "creative_hypothesis_research",
        "creative_finalize",
    ],
)
def test_run_gate_rejects_claimed_execution_method_shadows(
    tmp_path: Path,
    kind: str,
) -> None:
    manager, _aliases, _objectives = _manager(
        tmp_path,
        request=_InitialScreeningStudyControlsRequest(requested_rounds=2),
    )
    targets = {
        "scheduler": (manager._scheduler, "select_next"),
        "budget_consume": (manager._provider_call_budget, "consume"),
        "provider_call": (manager._creative._provider_calls, "call"),
        "creative_hypothesis": (manager._creative, "generate_direct_hypothesis"),
        "creative_code": (manager._creative, "generate_direct_code"),
        "creative_code_research": (
            manager._creative,
            "call_code_research_turn",
        ),
        "creative_hypothesis_research": (
            manager._creative,
            "call_hypothesis_research_turn",
        ),
        "creative_finalize": (manager._creative, "call_code_research_finalize"),
    }
    target, method = targets[kind]
    setattr(target, method, lambda *_args, **_kwargs: None)

    with pytest.raises(_InitialScreeningStudyControlsError) as caught:
        manager.run(2)

    _fixed_error(caught.value)


@pytest.mark.parametrize("gate_value", [None, lambda: None])
def test_mutable_legacy_gate_attribute_cannot_disable_validation(
    tmp_path: Path,
    gate_value: object,
) -> None:
    manager, _aliases, _objectives = _manager(
        tmp_path,
        request=_InitialScreeningStudyControlsRequest(requested_rounds=2),
    )
    manager._initial_screening_study_controls_gate = gate_value
    manager._protocol_config.screening.n_cases_modify = 1

    with pytest.raises(_InitialScreeningStudyControlsError) as caught:
        manager.run(2)

    _fixed_error(caught.value)


@pytest.mark.parametrize("mutation", ["marker", "carrier"])
def test_activation_marker_and_carrier_must_remain_consistent(
    tmp_path: Path,
    mutation: str,
) -> None:
    manager, _aliases, _objectives = _manager(
        tmp_path,
        request=_InitialScreeningStudyControlsRequest(requested_rounds=2),
    )
    if mutation == "marker":
        manager._initial_screening_study_controls_active = False
    else:
        manager._initial_screening_study_controls = None

    with pytest.raises(_InitialScreeningStudyControlsError) as caught:
        manager.run(2)

    _fixed_error(caught.value)


def test_clearing_both_owner_gate_attributes_cannot_masquerade_as_legacy(
    tmp_path: Path,
) -> None:
    manager, _aliases, _objectives = _manager(
        tmp_path,
        request=_InitialScreeningStudyControlsRequest(requested_rounds=2),
    )
    manager._initial_screening_study_controls_active = False
    manager._initial_screening_study_controls = None
    gc.collect()

    with pytest.raises(_InitialScreeningStudyControlsError) as caught:
        manager.run("99")  # type: ignore[arg-type]

    _fixed_error(caught.value)


@pytest.mark.parametrize(
    "mutation",
    ["requested_rounds", "payload", "publication", "component"],
)
def test_registered_baseline_rejects_coordinated_carrier_rebaselining(
    tmp_path: Path,
    mutation: str,
) -> None:
    manager, _aliases, _objectives = _manager(
        tmp_path,
        request=_InitialScreeningStudyControlsRequest(requested_rounds=2),
    )
    carrier = manager._initial_screening_study_controls
    if mutation == "requested_rounds":
        object.__setattr__(carrier, "requested_rounds", 3)
    elif mutation == "payload":
        object.__setattr__(carrier, "payload_bytes", b"{}\n")
    elif mutation == "publication":
        relocated = tmp_path / "relocated-campaign"
        (tmp_path / "campaign").rename(relocated)
        object.__setattr__(carrier.publication, "campaign_dir", str(relocated))
        manager._campaign_dir = str(relocated)
        manager._experiment_protocol.metrics_dir = str(relocated / "metrics")
        manager._vgate._metrics_dir = str(relocated / "metrics")
    else:
        replacement = _qualification()
        object.__setattr__(carrier, "qualification", replacement)
        manager._qualification_only_config = replacement
        manager._qualification_runtime.config = replacement
    manager._run_research_environment_preflight = lambda: pytest.fail(
        "preflight ran after carrier rebaselining"
    )

    with pytest.raises(_InitialScreeningStudyControlsError) as caught:
        manager.run(2)

    _fixed_error(caught.value)


@pytest.mark.parametrize(
    "mutation",
    [
        "runtime_rounds",
        "runtime_payload",
        "baseline_campaign",
        "baseline_evil_key",
        "publication_fingerprints",
    ],
)
def test_carrier_shape_validation_precedes_equality_and_filesystem(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    from scion.core import initial_screening_study_controls_validation as controls

    manager, _aliases, _objectives = _manager(
        tmp_path,
        request=_InitialScreeningStudyControlsRequest(requested_rounds=2),
    )
    runtime = manager._initial_screening_study_controls
    assert runtime is not None
    publication = runtime.publication
    assert publication is not None
    baseline = _REGISTERED_OWNERS[manager]
    hooks: list[str] = []

    class SideEffectInt(int):
        def __eq__(self, _other: object) -> bool:
            hooks.append("int-equality")
            return True

        def __ne__(self, _other: object) -> bool:
            hooks.append("int-inequality")
            return False

    class SideEffectBytes(bytes):
        def __eq__(self, _other: object) -> bool:
            hooks.append("bytes-equality")
            return True

        def __ne__(self, _other: object) -> bool:
            hooks.append("bytes-inequality")
            return False

    class SideEffectStr(str):
        __hash__ = str.__hash__

        def __eq__(self, _other: object) -> bool:
            hooks.append("str-equality")
            return True

        def __ne__(self, _other: object) -> bool:
            hooks.append("str-inequality")
            return False

    class SideEffectTuple(tuple):
        def __iter__(self) -> Any:
            hooks.append("tuple-iteration")
            return super().__iter__()

        def __eq__(self, _other: object) -> bool:
            hooks.append("tuple-equality")
            return True

    if mutation == "runtime_rounds":
        object.__setattr__(runtime, "requested_rounds", SideEffectInt(2))
    elif mutation == "runtime_payload":
        object.__setattr__(
            runtime, "payload_bytes", SideEffectBytes(runtime.payload_bytes)
        )
    elif mutation == "baseline_campaign":
        object.__setattr__(
            baseline, "campaign_dir", SideEffectStr(baseline.campaign_dir)
        )
    elif mutation == "baseline_evil_key":
        hidden = dict(vars(baseline))
        campaign_dir = hidden.pop("campaign_dir")
        hidden[SideEffectStr("campaign_dir")] = campaign_dir
        object.__setattr__(baseline, "__dict__", hidden)
    else:
        object.__setattr__(
            publication,
            "directory_fingerprints",
            SideEffectTuple(publication.directory_fingerprints),
        )
    monkeypatch.setattr(
        controls,
        "_validate_controls_publication",
        lambda *_args, **_kwargs: hooks.append("filesystem"),
    )
    monkeypatch.setattr(
        controls,
        "_validate_private_child_directory",
        lambda *_args, **_kwargs: hooks.append("metrics-filesystem"),
    )
    manager._run_research_environment_preflight = lambda: hooks.append("preflight")

    with pytest.raises(_InitialScreeningStudyControlsError) as caught:
        manager.run(2)

    _fixed_error(caught.value)
    assert hooks == []


def test_direct_service_type_validation_precedes_properties_and_filesystem(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scion.core import initial_screening_study_controls_validation as controls

    manager, _aliases, _objectives = _manager(
        tmp_path,
        request=_InitialScreeningStudyControlsRequest(requested_rounds=2),
    )
    hooks: list[str] = []

    class SideEffectService:
        @property
        def code_research_limits(self) -> object:
            hooks.append("service-property")
            return manager._code_research_limits

    manager._proposal_pipeline = SideEffectService()
    monkeypatch.setattr(
        controls,
        "_validate_controls_publication",
        lambda *_args, **_kwargs: hooks.append("controls-filesystem"),
    )
    monkeypatch.setattr(
        controls,
        "_validate_private_child_directory",
        lambda *_args, **_kwargs: hooks.append("metrics-filesystem"),
    )
    manager._run_research_environment_preflight = lambda: hooks.append("preflight")

    with pytest.raises(_InitialScreeningStudyControlsError) as caught:
        manager.run(2)

    _fixed_error(caught.value)
    assert hooks == []


def test_weak_registration_does_not_retain_campaign_owner(tmp_path: Path) -> None:
    from scion.core.initial_screening_study_controls import _REGISTERED_OWNERS

    gc.collect()
    baseline_size = len(_REGISTERED_OWNERS)
    manager, _aliases, _objectives = _manager(
        tmp_path,
        request=_InitialScreeningStudyControlsRequest(requested_rounds=2),
    )
    owner_ref = weakref.ref(manager)
    assert len(_REGISTERED_OWNERS) == baseline_size + 1

    del manager
    gc.collect()

    assert owner_ref() is None
    assert len(_REGISTERED_OWNERS) == baseline_size


def test_opt_in_rejects_campaign_manager_subclass_before_root(
    tmp_path: Path,
) -> None:
    class _CampaignSubclass(CampaignManager):
        pass

    with pytest.raises(_InitialScreeningStudyControlsError) as caught:
        _manager(
            tmp_path,
            request=_InitialScreeningStudyControlsRequest(requested_rounds=2),
            manager_type=_CampaignSubclass,
        )

    _fixed_error(caught.value)
    assert not (tmp_path / "campaign").exists()

    legacy, _aliases, _objectives = _manager(
        tmp_path / "legacy",
        request=None,
        manager_type=_CampaignSubclass,
    )
    assert type(legacy) is _CampaignSubclass


def test_legacy_subclass_run_does_not_touch_controls_fields_or_hash_owner(
    tmp_path: Path,
) -> None:
    hooks: list[str] = []

    class _LegacySubclass(CampaignManager):
        @property
        def __dict__(self) -> dict[str, Any]:
            hooks.append("dict-property")
            raise AssertionError("legacy owner __dict__ descriptor was invoked")

        @__dict__.setter
        def __dict__(self, _value: dict[str, Any]) -> None:
            hooks.append("dict-setter")
            raise AssertionError("legacy owner __dict__ descriptor was assigned")

        def __hash__(self) -> int:
            hooks.append("hash")
            raise AssertionError("legacy owner was hashed")

        def __getattribute__(self, name: str) -> Any:
            if name.startswith("_initial_screening_study_controls"):
                hooks.append(name)
                raise AssertionError("legacy controls field was dynamically read")
            return super().__getattribute__(name)

    legacy, _aliases, _objectives = _manager(
        tmp_path,
        request=None,
        manager_type=_LegacySubclass,
    )
    legacy._run_research_environment_preflight = lambda: None
    legacy._campaign_loop.run = lambda *, requested_rounds: requested_rounds

    assert legacy.run("99") == 99  # type: ignore[arg-type]
    assert hooks == []


def test_opt_in_class_drift_cannot_masquerade_as_legacy(tmp_path: Path) -> None:
    hooks: list[str] = []

    class _DriftedCampaign(CampaignManager):
        @property
        def __dict__(self) -> dict[str, Any]:
            hooks.append("dict-property")
            raise AssertionError("drifted owner __dict__ descriptor was invoked")

        @__dict__.setter
        def __dict__(self, _value: dict[str, Any]) -> None:
            hooks.append("dict-setter")
            raise AssertionError("drifted owner __dict__ descriptor was assigned")

    manager, _aliases, _objectives = _manager(
        tmp_path,
        request=_InitialScreeningStudyControlsRequest(requested_rounds=2),
    )
    manager._initial_screening_study_controls_active = False
    manager._initial_screening_study_controls = None
    gc.collect()
    manager.__class__ = _DriftedCampaign
    manager._run_research_environment_preflight = lambda: pytest.fail(
        "preflight ran after opt-in owner class drift"
    )

    with pytest.raises(_InitialScreeningStudyControlsError) as caught:
        manager.run(2)

    _fixed_error(caught.value)
    assert hooks == []


@pytest.mark.parametrize(
    "kind",
    ["retire", "park", "reserve", "attempt_scope", "protocol_provider"],
)
def test_run_gate_anchors_paired_callbacks_to_class_functions(
    tmp_path: Path,
    kind: str,
) -> None:
    manager, _aliases, _objectives = _manager(
        tmp_path,
        request=_InitialScreeningStudyControlsRequest(requested_rounds=2),
    )
    if kind == "retire":
        replacement = MethodType(_wrong_bound_method, manager)
        manager._retire_initial_screening_study_chain = replacement
        manager._campaign_loop.retire_initial_screening_study_chain = replacement
    elif kind == "park":
        replacement = MethodType(_wrong_bound_method, manager)
        manager._park_qualification_chain = replacement
        manager._campaign_loop.park_qualification_chain = replacement
    elif kind == "reserve":
        runtime = manager._qualification_runtime
        replacement = MethodType(_wrong_bound_method, runtime)
        runtime.reserve_proposal_attempt = replacement
        manager._explore_step_pipeline.reserve_proposal_attempt = replacement
    elif kind == "attempt_scope":
        runtime = manager._proposal_runtime_telemetry
        replacement = MethodType(_wrong_bound_method, runtime)
        runtime.attempt_scope = replacement
        manager._explore_step_pipeline.proposal_attempt_scope = replacement
    else:
        replacement = MethodType(_wrong_bound_method, manager)
        manager._provide_experiment_protocol = replacement
        manager._evaluation_orchestrator.experiment_protocol_provider = replacement
        manager._branch_step_runner.experiment_protocol_provider = replacement

    with pytest.raises(_InitialScreeningStudyControlsError) as caught:
        manager.run(2)

    _fixed_error(caught.value)


def test_method_anchor_rejects_callable_spoof_without_property_hooks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scion.core import initial_screening_study_controls_validation as controls

    manager, _aliases, _objectives = _manager(
        tmp_path,
        request=_InitialScreeningStudyControlsRequest(requested_rounds=2),
    )
    hooks: list[str] = []

    class CallableSpoof:
        @property
        def __self__(self) -> object:
            hooks.append("self-property")
            return manager

        @property
        def __func__(self) -> object:
            hooks.append("func-property")
            return CampaignManager._retire_initial_screening_study_chain

        def __call__(self, *_args: Any, **_kwargs: Any) -> None:
            hooks.append("call")

    manager._campaign_loop.retire_initial_screening_study_chain = CallableSpoof()
    monkeypatch.setattr(
        controls,
        "_validate_controls_publication",
        lambda *_args, **_kwargs: hooks.append("controls-filesystem"),
    )
    monkeypatch.setattr(
        controls,
        "_validate_private_child_directory",
        lambda *_args, **_kwargs: hooks.append("metrics-filesystem"),
    )

    with pytest.raises(_InitialScreeningStudyControlsError) as caught:
        manager.run(2)

    _fixed_error(caught.value)
    assert hooks == []


@pytest.mark.parametrize(
    "surface",
    ["scheduler", "verification", "branch", "explore", "decision"],
)
def test_claimed_service_scalars_reject_subtypes_before_filesystem(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    surface: str,
) -> None:
    from scion.core import initial_screening_study_controls_validation as controls

    manager, _aliases, _objectives = _manager(
        tmp_path,
        request=_InitialScreeningStudyControlsRequest(requested_rounds=2),
    )
    hooks: list[str] = []

    class SideEffectInt(int):
        def __eq__(self, _other: object) -> bool:
            hooks.append("integer-equality")
            return True

    class SideEffectStr(str):
        def __eq__(self, _other: object) -> bool:
            hooks.append("string-equality")
            return True

    class SideEffectBool:
        def __eq__(self, _other: object) -> bool:
            hooks.append("boolean-equality")
            return True

        def __bool__(self) -> bool:
            hooks.append("boolean-coercion")
            return True

    if surface == "scheduler":
        manager._scheduler._max_active_branches = SideEffectInt(3)
    elif surface == "verification":
        manager._vgate._metrics_dir = SideEffectStr(str(tmp_path / "campaign/metrics"))
    elif surface == "branch":
        manager._branch_step_runner.qualification_only = SideEffectBool()
    elif surface == "explore":
        manager._explore_step_pipeline.initial_screening_only = SideEffectBool()
    else:
        manager._decision_finalizer.initial_screening_only = SideEffectBool()
    monkeypatch.setattr(
        controls,
        "_validate_controls_publication",
        lambda *_args, **_kwargs: hooks.append("controls-filesystem"),
    )
    monkeypatch.setattr(
        controls,
        "_validate_private_child_directory",
        lambda *_args, **_kwargs: hooks.append("metrics-filesystem"),
    )

    with pytest.raises(_InitialScreeningStudyControlsError) as caught:
        manager.run(2)

    _fixed_error(caught.value)
    assert hooks == []


@pytest.mark.parametrize("kind", ["budget", "proposal"])
def test_run_gate_rejects_snapshot_method_with_wrong_self(
    tmp_path: Path,
    kind: str,
) -> None:
    manager, _aliases, _objectives = _manager(
        tmp_path,
        request=_InitialScreeningStudyControlsRequest(requested_rounds=2),
    )
    if kind == "budget":
        other = ProviderCallBudget(manager._provider_call_budget.cap)
        manager._provider_call_budget.snapshot = MethodType(
            ProviderCallBudget.snapshot,
            other,
        )
    else:
        other = ProposalRuntimeTelemetry(
            manager._provider_call_budget,
            max_hypothesis_candidates=1,
        )
        manager._proposal_runtime_telemetry.snapshot = MethodType(
            ProposalRuntimeTelemetry.snapshot,
            other,
        )

    with pytest.raises(_InitialScreeningStudyControlsError) as caught:
        manager.run(2)

    _fixed_error(caught.value)


@pytest.mark.parametrize(
    "mutation",
    [
        "qualification_started",
        "qualification_bool_counter",
        "qualification_pending",
        "qualification_set_subclass",
        "qualification_dict_subclass",
        "qualification_method_shadow",
        "provider_used",
        "provider_bool_used",
        "provider_dict_subclass",
        "provider_custom_lock",
        "provider_locked",
        "proposal_attempt",
        "proposal_orphan",
        "proposal_locked",
        "proposal_list_subclass",
        "candidate_cap_bool",
        "branch_controller_dict_subclass",
        "workspace_dict_subclass",
        "patch_dict_subclass",
        "history_list_subclass",
        "round",
        "history",
        "branch",
        "external_stop",
        "preflight_checked",
        "last_stop_reason",
        "last_status_result",
        "deferral_bool",
        "post_return_deferral",
    ],
)
def test_run_gate_requires_exact_pristine_runtime_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    from scion.core import initial_screening_study_controls_validation as controls

    manager, _aliases, _objectives = _manager(
        tmp_path,
        request=_InitialScreeningStudyControlsRequest(requested_rounds=2),
    )
    runtime = manager._qualification_runtime
    locked: Any | None = None
    structural_mutations = {
        "qualification_bool_counter",
        "qualification_set_subclass",
        "qualification_dict_subclass",
        "qualification_method_shadow",
        "provider_bool_used",
        "provider_dict_subclass",
        "provider_custom_lock",
        "proposal_list_subclass",
        "candidate_cap_bool",
        "branch_controller_dict_subclass",
        "workspace_dict_subclass",
        "patch_dict_subclass",
        "history_list_subclass",
        "deferral_bool",
    }
    structural_hooks: list[str] = []
    if mutation in structural_mutations:
        monkeypatch.setattr(
            controls,
            "_validate_controls_publication",
            lambda *_args, **_kwargs: structural_hooks.append("controls-filesystem"),
        )
        monkeypatch.setattr(
            controls,
            "_validate_private_child_directory",
            lambda *_args, **_kwargs: structural_hooks.append("metrics-filesystem"),
        )
    if mutation == "qualification_started":
        runtime.started = True
    elif mutation == "qualification_bool_counter":
        runtime.proposal_attempts = False
    elif mutation == "qualification_pending":
        runtime.pending_expansion_branch_id = "private-branch"
    elif mutation == "qualification_set_subclass":
        runtime.verified_candidate_branch_ids = type("EqualSet", (set,), {})()
    elif mutation == "qualification_dict_subclass":
        runtime.candidate_screening_stage_counts = type("EqualDict", (dict,), {})()
    elif mutation == "qualification_method_shadow":
        runtime.can_start_proposal = lambda: True
    elif mutation == "provider_used":
        manager._provider_call_budget.consume(request_kind="hypothesis")
    elif mutation == "provider_bool_used":
        manager._provider_call_budget._used = False
    elif mutation == "provider_dict_subclass":
        manager._provider_call_budget._by_request_kind = type(
            "EqualDict",
            (dict,),
            {},
        )(manager._provider_call_budget._by_request_kind)
    elif mutation == "provider_custom_lock":
        manager._provider_call_budget._lock = SimpleNamespace(
            locked=lambda: False,
        )
    elif mutation == "provider_locked":
        locked = manager._provider_call_budget._lock
        locked.acquire()
    elif mutation == "proposal_attempt":
        manager._proposal_runtime_telemetry.attempt_scope(1).__enter__()
    elif mutation == "proposal_orphan":
        manager._proposal_runtime_telemetry._active = object()
    elif mutation == "proposal_locked":
        locked = manager._proposal_runtime_telemetry._lock
        locked.acquire()
    elif mutation == "proposal_list_subclass":
        manager._proposal_runtime_telemetry._attempts = type("EqualList", (list,), {})()
    elif mutation == "candidate_cap_bool":
        manager._proposal_runtime_telemetry._max_hypothesis_candidates = True
    elif mutation == "branch_controller_dict_subclass":
        manager._branch_ctrl._branches = type("EqualDict", (dict,), {})()
    elif mutation == "workspace_dict_subclass":
        manager._branch_workspaces = type("EqualDict", (dict,), {})()
    elif mutation == "patch_dict_subclass":
        manager._branch_patches = type("EqualDict", (dict,), {})()
    elif mutation == "history_list_subclass":
        manager._step_history = type("EqualList", (list,), {})()
    elif mutation == "round":
        manager._round_num = 1
    elif mutation == "history":
        manager._step_history.append(object())
    elif mutation == "branch":
        manager._branch_ctrl._branches["private"] = object()
    elif mutation == "external_stop":
        manager._external_stop_requested = True
    elif mutation == "preflight_checked":
        manager._research_preflight_checked = True
    elif mutation == "last_stop_reason":
        manager._last_stop_reason = "private"
    elif mutation == "last_status_result":
        manager._last_status_result = {}
    elif mutation == "deferral_bool":
        manager._async_stop_deferral_depth = False
    else:
        manager._campaign_loop._post_return_deferral_active = True

    manager._run_research_environment_preflight = lambda: pytest.fail(
        "preflight ran after pre-run state consumption"
    )
    with pytest.raises(_InitialScreeningStudyControlsError) as caught:
        manager.run(2)

    if locked is not None:
        locked.release()
    _fixed_error(caught.value)
    assert structural_hooks == []


@pytest.mark.parametrize(
    "mutation",
    [
        "rejection_counts",
        "rejection_last",
        "active_candidate",
        "rejection_counts_subclass",
        "active_candidates_subclass",
        "rejection_last_missing",
    ],
)
def test_run_gate_requires_pristine_proposal_and_candidate_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    from scion.core import initial_screening_study_controls_validation as controls

    manager, _aliases, _objectives = _manager(
        tmp_path,
        request=_InitialScreeningStudyControlsRequest(requested_rounds=2),
    )
    hooks: list[str] = []
    structural = mutation.endswith("_subclass") or mutation == "rejection_last_missing"
    if mutation == "rejection_counts":
        manager._proposal_pipeline._hypothesis_rejection_counts["PRIVATE"] = 1
    elif mutation == "rejection_last":
        manager._proposal_pipeline._last_hypothesis_rejection_reason = "PRIVATE"
    elif mutation == "active_candidate":
        manager._explore_step_pipeline._active_candidates["private"] = object()
    elif mutation == "rejection_counts_subclass":
        manager._proposal_pipeline._hypothesis_rejection_counts = type(
            "EqualDict",
            (dict,),
            {},
        )()
    elif mutation == "active_candidates_subclass":
        manager._explore_step_pipeline._active_candidates = type(
            "EqualDict",
            (dict,),
            {},
        )()
    else:
        cast(dict[str, Any], vars(manager._proposal_pipeline)).pop(
            "_last_hypothesis_rejection_reason"
        )
    if structural:
        monkeypatch.setattr(
            controls,
            "_validate_controls_publication",
            lambda *_args, **_kwargs: hooks.append("controls-filesystem"),
        )
        monkeypatch.setattr(
            controls,
            "_validate_private_child_directory",
            lambda *_args, **_kwargs: hooks.append("metrics-filesystem"),
        )
    manager._run_research_environment_preflight = lambda: hooks.append("preflight")

    with pytest.raises(_InitialScreeningStudyControlsError) as caught:
        manager.run(2)

    _fixed_error(caught.value)
    assert hooks == []


def test_run_gate_rejects_bool_provider_cap_even_when_equal_to_one(
    tmp_path: Path,
) -> None:
    manager, _aliases, _objectives = _manager(
        tmp_path,
        request=_InitialScreeningStudyControlsRequest(requested_rounds=2),
        provider_call_cap=1,
    )
    manager._provider_call_budget._cap = True

    with pytest.raises(_InitialScreeningStudyControlsError) as caught:
        manager.run(2)

    _fixed_error(caught.value)


@pytest.mark.parametrize(
    "authority",
    ["branch_controller", "workspaces", "patches", "history"],
)
def test_run_gate_rejects_empty_owner_replacement_over_polluted_consumers(
    tmp_path: Path,
    authority: str,
) -> None:
    manager, _aliases, _objectives = _manager(
        tmp_path,
        request=_InitialScreeningStudyControlsRequest(requested_rounds=2),
    )
    if authority == "branch_controller":
        original = manager._branch_ctrl
        original._branches["private"] = object()
        manager._branch_ctrl = type(original)()
    elif authority == "workspaces":
        manager._branch_workspaces["private"] = "/private/workspace"
        manager._branch_workspaces = {}
    elif authority == "patches":
        manager._branch_patches["private"] = object()
        manager._branch_patches = {}
    else:
        manager._step_history.append(object())
        manager._step_history = []
    manager._run_research_environment_preflight = lambda: pytest.fail(
        "preflight ran after shared-state authority replacement"
    )

    with pytest.raises(_InitialScreeningStudyControlsError) as caught:
        manager.run(2)

    _fixed_error(caught.value)


@pytest.mark.parametrize("tamper", ["bytes", "mode", "replace", "root_replace"])
def test_run_gate_revalidates_published_root_and_leaf(
    tmp_path: Path,
    tamper: str,
) -> None:
    manager, _aliases, _objectives = _manager(
        tmp_path,
        request=_InitialScreeningStudyControlsRequest(requested_rounds=2),
    )
    path = tmp_path / "campaign" / _FILENAME
    if tamper == "bytes":
        path.write_text("{}\n", encoding="utf-8")
    elif tamper == "mode":
        os.chmod(tmp_path / "campaign", 0o755)
    elif tamper == "replace":
        body = path.read_bytes()
        path.unlink()
        path.write_bytes(body)
        os.chmod(path, 0o600)
    else:
        body = path.read_bytes()
        (tmp_path / "campaign").rename(tmp_path / "detached-campaign")
        (tmp_path / "campaign").mkdir(mode=0o700)
        path.write_bytes(body)
        os.chmod(path, 0o600)
        (tmp_path / "campaign/metrics").mkdir(mode=0o700)
    manager._run_research_environment_preflight = lambda: pytest.fail(
        "preflight ran after artifact drift"
    )

    with pytest.raises(_InitialScreeningStudyControlsError) as caught:
        manager.run(2)

    _fixed_error(caught.value)


@pytest.mark.parametrize("tamper", ["symlink", "file"])
def test_run_gate_requires_bound_empty_private_metrics_directory(
    tmp_path: Path,
    tamper: str,
) -> None:
    manager, _aliases, _objectives = _manager(
        tmp_path,
        request=_InitialScreeningStudyControlsRequest(requested_rounds=2),
    )
    metrics = tmp_path / "campaign" / "metrics"
    if tamper == "symlink":
        metrics.rmdir()
        metrics.symlink_to(tmp_path / "champion", target_is_directory=True)
    else:
        (metrics / "pre-run-private.json").write_text("{}", encoding="utf-8")
    manager._run_research_environment_preflight = lambda: pytest.fail(
        "preflight ran after metrics directory drift"
    )

    with pytest.raises(_InitialScreeningStudyControlsError) as caught:
        manager.run(2)

    _fixed_error(caught.value)


def test_run_revalidates_publication_before_runtime_consumers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scion.core import initial_screening_study_controls_validation as controls

    manager, _aliases, _objectives = _manager(
        tmp_path,
        request=_InitialScreeningStudyControlsRequest(requested_rounds=2),
    )
    (tmp_path / "campaign" / _FILENAME).write_text("{}\n", encoding="utf-8")
    calls: list[str] = []

    def forbidden_runtime_check(*_args: Any, **_kwargs: Any) -> None:
        calls.append("runtime")

    monkeypatch.setattr(
        controls, "_validate_installed_runtime", forbidden_runtime_check
    )
    with pytest.raises(_InitialScreeningStudyControlsError) as caught:
        manager.run(2)

    _fixed_error(caught.value)
    assert calls == []


def test_publication_rewalk_rejects_root_swap_during_leaf_verification(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scion.core import initial_screening_study_controls_io as controls_io

    manager, _aliases, _objectives = _manager(
        tmp_path,
        request=_InitialScreeningStudyControlsRequest(requested_rounds=2),
    )
    original = controls_io._verify_leaf_bytes
    calls = 0

    def swapping_verify(*args: Any, **kwargs: Any) -> None:
        nonlocal calls
        calls += 1
        original(*args, **kwargs)
        if calls == 1:
            campaign = tmp_path / "campaign"
            campaign.rename(tmp_path / "detached-campaign")
            campaign.mkdir(mode=0o700)

    monkeypatch.setattr(controls_io, "_verify_leaf_bytes", swapping_verify)
    with pytest.raises(_InitialScreeningStudyControlsError) as caught:
        manager.run(2)

    _fixed_error(caught.value)
    assert calls == 1


def test_opt_in_rejects_protocol_instance_method_shadows_before_root(
    tmp_path: Path,
) -> None:
    shadows = {
        "_select_cases": lambda *_args, **_kwargs: ["cases/private-shadow.vrp"],
        "resolve_time_limit_sec": lambda *_args, **_kwargs: 999,
        "run_experiment": lambda *_args, **_kwargs: pytest.fail("shadow executed"),
    }

    def install_shadows(protocol: ExperimentProtocol) -> None:
        for name, value in shadows.items():
            setattr(protocol, name, value)

    with pytest.raises(_InitialScreeningStudyControlsError) as caught:
        _manager(
            tmp_path,
            request=_InitialScreeningStudyControlsRequest(requested_rounds=2),
            protocol_mutator=install_shadows,
        )

    _fixed_error(caught.value)
    assert not (tmp_path / "campaign").exists()


@pytest.mark.parametrize("surface", ["split_manager", "seed_ledger"])
def test_opt_in_rejects_nested_protocol_wrapper_before_property_access(
    tmp_path: Path,
    surface: str,
) -> None:
    hooks: list[str] = []

    class NestedProperty:
        def __getattribute__(self, name: str) -> Any:
            if name in {"_manifest", "_ledger"}:
                hooks.append(name)
                pytest.fail("nested protocol property was accessed")
            return object.__getattribute__(self, name)

    def replace_nested_wrapper(protocol: ExperimentProtocol) -> None:
        setattr(protocol, surface, NestedProperty())

    with pytest.raises(_InitialScreeningStudyControlsError) as caught:
        _manager(
            tmp_path,
            request=_InitialScreeningStudyControlsRequest(requested_rounds=2),
            protocol_mutator=replace_nested_wrapper,
        )

    _fixed_error(caught.value)
    assert hooks == []
    assert not (tmp_path / "campaign").exists()


def test_opt_in_rebinds_caller_metrics_without_touching_source_or_runner(
    tmp_path: Path,
) -> None:
    source_metrics = tmp_path / "champion"
    manager, aliases, _objectives = _manager(
        tmp_path,
        request=_InitialScreeningStudyControlsRequest(requested_rounds=2),
        protocol_metrics_dir=source_metrics,
    )

    assert aliases["protocol"].metrics_dir == str(source_metrics)
    assert aliases["runner"]._progress_callback is None
    assert manager._experiment_protocol.metrics_dir == str(
        tmp_path / "campaign/metrics"
    )
    assert not (source_metrics / _FILENAME).exists()


def test_campaign_manager_constructor_type_hints_remain_runtime_resolvable() -> None:
    hints = get_type_hints(CampaignManager.__init__)

    assert hints["_initial_screening_study_controls"] == Any | None


def test_ordinary_initial_only_has_no_controls_artifact_and_keeps_round_coercion(
    tmp_path: Path,
) -> None:
    manager, _aliases, _objectives = _manager(tmp_path, request=None)

    assert not (tmp_path / "campaign" / _FILENAME).exists()
    manager._run_research_environment_preflight = lambda: None
    manager._campaign_loop.run = lambda *, requested_rounds: requested_rounds
    assert manager.run("99") == 99  # type: ignore[arg-type]


@pytest.mark.parametrize("relation", ["inside_champion", "contains_champion"])
def test_opt_in_rejects_campaign_source_overlap_with_fixed_error(
    tmp_path: Path,
    relation: str,
) -> None:
    campaign = (
        tmp_path / "champion" / "nested-campaign"
        if relation == "inside_champion"
        else tmp_path
    )

    with pytest.raises(_InitialScreeningStudyControlsError) as caught:
        _manager(
            tmp_path,
            request=_InitialScreeningStudyControlsRequest(requested_rounds=2),
            campaign_dir=campaign,
        )

    _fixed_error(caught.value)
    assert not (campaign / _FILENAME).exists()


@pytest.mark.parametrize("kind", ["existing_directory", "root_symlink"])
def test_opt_in_requires_a_new_literal_campaign_root(
    tmp_path: Path,
    kind: str,
) -> None:
    campaign = tmp_path / "campaign"
    if kind == "existing_directory":
        campaign.mkdir()
    else:
        target = tmp_path / "redirected"
        target.mkdir()
        campaign.symlink_to(target, target_is_directory=True)

    with pytest.raises(_InitialScreeningStudyControlsError) as caught:
        _manager(
            tmp_path,
            request=_InitialScreeningStudyControlsRequest(requested_rounds=2),
        )

    _fixed_error(caught.value)
    assert not (campaign / _FILENAME).exists()


def test_opt_in_rejects_symlinked_ancestor_without_following_it(
    tmp_path: Path,
) -> None:
    target = tmp_path / "redirected-parent"
    target.mkdir()
    linked = tmp_path / "linked-parent"
    linked.symlink_to(target, target_is_directory=True)

    with pytest.raises(_InitialScreeningStudyControlsError) as caught:
        _manager(
            tmp_path,
            request=_InitialScreeningStudyControlsRequest(requested_rounds=2),
            campaign_dir=linked / "campaign",
        )

    _fixed_error(caught.value)
    assert not (target / "campaign").exists()


@pytest.mark.parametrize("replacement", ["hardlink", "symlink", "fifo"])
def test_run_gate_rejects_noncanonical_controls_leaf(
    tmp_path: Path,
    replacement: str,
) -> None:
    manager, _aliases, _objectives = _manager(
        tmp_path,
        request=_InitialScreeningStudyControlsRequest(requested_rounds=2),
    )
    path = tmp_path / "campaign" / _FILENAME
    if replacement == "hardlink":
        os.link(path, tmp_path / "controls-hardlink")
    else:
        path.unlink()
        if replacement == "symlink":
            target = tmp_path / "private-target"
            target.write_bytes(b"private body")
            path.symlink_to(target)
        else:
            os.mkfifo(path, mode=0o600)

    with pytest.raises(_InitialScreeningStudyControlsError) as caught:
        manager.run(2)

    _fixed_error(caught.value)


@pytest.mark.parametrize("failure", ["partial_write", "fsync"])
def test_publication_io_failure_is_fixed_and_never_reaches_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    from scion.core import initial_screening_study_controls_io as controls_io

    if failure == "partial_write":
        original_write = controls_io.os.write
        calls = 0

        def fail_after_one_byte(fd: int, body: bytes) -> int:
            nonlocal calls
            calls += 1
            if calls == 1:
                return original_write(fd, body[:1])
            raise OSError("private-path-and-body")

        monkeypatch.setattr(controls_io.os, "write", fail_after_one_byte)
    else:
        monkeypatch.setattr(
            controls_io.os,
            "fsync",
            lambda _fd: (_ for _ in ()).throw(OSError("private-fsync")),
        )

    with pytest.raises(_InitialScreeningStudyControlsError) as caught:
        _manager(
            tmp_path,
            request=_InitialScreeningStudyControlsRequest(requested_rounds=2),
        )

    _fixed_error(caught.value)
    assert not (tmp_path / "campaign/status.json").exists()
    assert "private" not in repr(caught.value)


def test_directory_emptiness_check_consumes_one_entry_and_closes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scion.core import initial_screening_study_controls_io as controls_io

    next_calls = 0
    closed = False
    body_reads: list[str] = []

    class PrivateEntry:
        @property
        def name(self) -> str:
            body_reads.append("name")
            return "private-entry"

    class Entries:
        def __enter__(self) -> Self:
            return self

        def __exit__(self, *_args: object) -> None:
            nonlocal closed
            closed = True

        def __iter__(self) -> Entries:
            return self

        def __next__(self) -> PrivateEntry:
            nonlocal next_calls
            next_calls += 1
            if next_calls > 1:
                pytest.fail("directory iterator consumed more than one entry")
            return PrivateEntry()

    monkeypatch.setattr(controls_io.os, "scandir", lambda _fd: Entries())

    with pytest.raises(_InitialScreeningStudyControlsError) as caught:
        _manager(
            tmp_path,
            request=_InitialScreeningStudyControlsRequest(requested_rounds=2),
        )

    _fixed_error(caught.value)
    assert next_calls == 1
    assert closed is True
    assert body_reads == []
    assert not (tmp_path / "campaign/status.json").exists()


def test_explicit_opt_in_sanitizes_post_publication_composition_errors_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scion.core import campaign_composition

    def fail_materializer(*_args: Any, **_kwargs: Any) -> None:
        raise OSError("private-root/materializer-body")

    monkeypatch.setattr(
        campaign_composition.WorkspaceMaterializer,
        "__init__",
        fail_materializer,
    )
    with pytest.raises(_InitialScreeningStudyControlsError) as caught:
        _manager(
            tmp_path / "opt-in",
            request=_InitialScreeningStudyControlsRequest(requested_rounds=2),
        )
    _fixed_error(caught.value)
    assert (tmp_path / "opt-in/campaign" / _FILENAME).is_file()

    with pytest.raises(OSError, match="private-root/materializer-body"):
        _manager(tmp_path / "legacy", request=None)


def test_publication_fsyncs_parent_leaf_root_and_metrics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scion.core import initial_screening_study_controls_io as controls_io

    original = controls_io.os.fsync
    calls: list[int] = []

    def recording_fsync(fd: int) -> None:
        calls.append(fd)
        original(fd)

    monkeypatch.setattr(controls_io.os, "fsync", recording_fsync)
    _manager(
        tmp_path,
        request=_InitialScreeningStudyControlsRequest(requested_rounds=2),
    )

    assert len(calls) >= 4


def test_fixed_writer_cap_cannot_be_overridden(tmp_path: Path) -> None:
    from scion.core.initial_screening_study_controls import (
        _MAX_BYTES,
        _write_initial_screening_study_controls,
    )

    root = tmp_path / "oversize"
    with pytest.raises(_InitialScreeningStudyControlsError) as caught:
        _write_initial_screening_study_controls(
            str(root),
            b"x" * (_MAX_BYTES + 1),
            protected_roots=(),
        )

    _fixed_error(caught.value)
    assert not root.exists()


def test_opt_in_rejects_unsafe_protocol_and_invalid_signature_before_root(
    tmp_path: Path,
) -> None:
    with pytest.raises(_InitialScreeningStudyControlsError) as caught:
        _manager(
            tmp_path,
            request=_InitialScreeningStudyControlsRequest(requested_rounds=2),
            strict_case_paths=False,
        )
    _fixed_error(caught.value)
    assert not (tmp_path / "campaign").exists()

    other = tmp_path / "other"
    with pytest.raises(_InitialScreeningStudyControlsError) as caught:
        _manager(
            other,
            request=_InitialScreeningStudyControlsRequest(requested_rounds=2),
            operator_execute_signature="not a python signature",
        )
    _fixed_error(caught.value)
    assert not (other / "campaign").exists()


def test_opt_in_rejects_nonexact_protected_root_without_hooks(
    tmp_path: Path,
) -> None:
    hooks: list[str] = []

    class SideEffectStr(str):
        def __hash__(self) -> int:
            hooks.append("hash")
            return super().__hash__()

        def __eq__(self, _other: object) -> bool:
            hooks.append("equality")
            return False

        def __fspath__(self) -> str:
            hooks.append("fspath")
            return str(self)

    with pytest.raises(_InitialScreeningStudyControlsError) as caught:
        _manager(
            tmp_path,
            request=_InitialScreeningStudyControlsRequest(requested_rounds=2),
            champion_snapshot_path=SideEffectStr(str(tmp_path / "champion")),
        )

    _fixed_error(caught.value)
    assert hooks == []
    assert not (tmp_path / "campaign").exists()


def test_private_carriers_and_errors_do_not_repr_identity_or_control_bodies(
    tmp_path: Path,
) -> None:
    request = _InitialScreeningStudyControlsRequest(requested_rounds=2)
    manager, _aliases, _objectives = _manager(tmp_path, request=request)
    sentinels = (_SCHEMA_VERSION, _SCOPE, _LIMITATIONS[0], _FILENAME)
    payload = (tmp_path / "campaign" / _FILENAME).read_bytes()
    runtime = manager._initial_screening_study_controls
    assert runtime is not None
    publication = runtime.publication
    assert publication is not None
    baseline = _REGISTERED_OWNERS[manager]
    setup = object.__new__(_InitialScreeningControlsSetup)

    manager._experiment_protocol._emit_progress(
        stage="screening",
        case="cases/alpha.vrp",
        seed=11,
        status="running",
    )

    carriers = (
        (request, "_InitialScreeningStudyControlsRequest(<redacted>)"),
        (runtime, "_InitialScreeningRuntimeInputs(<redacted>)"),
        (baseline, "_RegisteredControlsBaseline(<redacted>)"),
        (publication, "_ControlsPublication(<redacted>)"),
        (setup, "_InitialScreeningControlsSetup(<redacted>)"),
    )
    for carrier, expected in carriers:
        assert repr(carrier) == str(carrier) == expected
        assert "0x" not in expected
        assert str(tmp_path) not in expected
        assert all(value not in expected for value in sentinels)
    with pytest.raises(_InitialScreeningStudyControlsError) as caught:
        manager.run(False)
    _fixed_error(caught.value)
    assert all(value not in str(caught.value) for value in sentinels)
    assert all(value not in repr(caught.value) for value in sentinels)
    for path in (tmp_path / "campaign").rglob("*"):
        if path.is_file() and path.name != _FILENAME:
            body = path.read_bytes()
            assert all(value.encode() not in body for value in sentinels)
            assert payload not in body


def test_private_controls_have_no_package_export() -> None:
    from scion import core

    assert not hasattr(core, "InitialScreeningStudyControlsRequest")
    assert not hasattr(core, "_InitialScreeningStudyControlsRequest")
