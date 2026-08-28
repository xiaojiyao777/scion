from __future__ import annotations

import gc
from pathlib import Path
from typing import Any

import pytest

from scion.core import campaign_composition as campaign_composition_module
from scion.core import initial_screening_controls_composition as controls_composition
from scion.core import (
    initial_screening_declaration_composition as declaration_composition,
)
from scion.core import initial_screening_research_context as research_context_schema
from scion.core import (
    initial_screening_research_context_composition as research_composition,
)
from scion.core import (
    initial_screening_research_context_integration as integration_module,
)
from scion.core import initial_screening_research_context_io as research_context_io
from scion.core import (
    initial_screening_research_context_validation as research_context_validation,
)
from scion.core.campaign import CampaignManager
from scion.core.campaign_composition import (
    _prepare_initial_screening_controls_setup,
)
from scion.core.code_research_limits import CodeResearchLimits
from scion.core.initial_screening_problem_spec import (
    _InitialScreeningProblemSpecRequest,
)
from scion.core.initial_screening_research_context import (
    _ERROR,
    _FILENAME,
    _InitialScreeningLoadedHistoryAvailable,
    _InitialScreeningResearchContextError,
    _InitialScreeningResearchContextRequest,
)
from scion.core.initial_screening_study_controls import (
    _FILENAME as _CONTROLS_FILENAME,
)
from scion.core.initial_screening_study_controls import (
    _InitialScreeningStudyControlsRequest,
)
from scion.core.initial_screening_study_provider_policy import (
    _InitialScreeningProviderPolicyRequest,
)
from scion.core.models import Branch, BranchState, ChampionState
from scion.core.qualification import QualificationOnlyConfig
from scion.core.resource_envelope import ResourceEnvelope
from scion.problem.loader import load_problem_adapter
from scion.proposal.llm.client import LLMClient
from scion.protocol.experiment import ExperimentProtocol, SeedLedger, SplitManager
from scion.runtime.runner import ResourceLimits
from scion.runtime.subprocess_runner import LocalSubprocessRunner
from scion.tests.test_cvrp_controlled_campaign import CVRP_DIR
from scion.tests.unit.core.test_initial_screening_problem_spec import _cvrp_inputs
from scion.tests.unit.core.test_initial_screening_study_controls import (
    _ledger,
    _protocol_config,
    _split,
)


def _active_manager(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> CampaignManager:
    gc.collect()
    spec_v1, bridge, _adapter = _cvrp_inputs()
    adapter = load_problem_adapter(spec_v1)
    config = _protocol_config()
    manifest = _split()
    ledger = _ledger()
    protocol = ExperimentProtocol(
        protocol_config=config,
        split_manager=SplitManager(manifest),
        seed_ledger=SeedLedger(ledger),
        runner=LocalSubprocessRunner(ResourceLimits(timeout_sec=30, memory_mb=512)),
        time_limit_sec=31,
        metrics_dir=str(tmp_path / "external-metrics"),
        metric_specs=bridge.metric_specs,
        objective_policy=bridge.objective_policy,
        problem_spec=bridge.problem_spec,
    )
    monkeypatch.setenv("SCION_REASONING_EFFORT", "high")
    return CampaignManager(
        problem_spec=bridge.problem_spec,
        protocol_config=config,
        split_manifest=manifest,
        seed_ledger=ledger,
        llm_client=LLMClient(
            model="gpt-5.6-sol",
            api_key="private-context-declaration-secret",
            base_url="https://provider.example",
            timeout_sec=61.0,
        ),
        champion=ChampionState(
            version=1,
            operator_pool={},
            code_snapshot_path=str(CVRP_DIR),
        ),
        campaign_dir=str(tmp_path / "campaign"),
        experiment_protocol=protocol,
        adapter=adapter,
        operator_execute_signature=bridge.operator_execute_signature,
        qualification_only=QualificationOnlyConfig(
            max_proposal_attempts=2,
            max_verified_candidate_chains=2,
            max_formal_screening_stages=2,
            development_boundary_mode="initial_screening_only_v1",
        ),
        resource_envelope=ResourceEnvelope(
            provider_call_cap=200,
            outer_hardwall_sec=60,
        ),
        code_research_limits=CodeResearchLimits(max_hypothesis_candidates=1),
        _initial_screening_study_controls=(
            _InitialScreeningStudyControlsRequest(requested_rounds=2)
        ),
        _initial_screening_provider_policy=_InitialScreeningProviderPolicyRequest(),
        _initial_screening_problem_spec=_InitialScreeningProblemSpecRequest(),
        _initial_screening_research_context=(
            _InitialScreeningResearchContextRequest(
                research_input={
                    "current_question": "What bounded change should be tested?",
                    "observations": [],
                },
                loaded_history=_InitialScreeningLoadedHistoryAvailable(records=()),
            )
        ),
    )


def _assert_fixed_research_context_error(error: BaseException) -> None:
    assert type(error) is _InitialScreeningResearchContextError
    assert error.args == (_ERROR,)
    assert error.__cause__ is None
    assert error.__context__ is None
    assert "private" not in repr(error)


def _assert_no_control_or_research_leaf(tmp_path: Path) -> None:
    campaign_dir = tmp_path / "campaign"
    assert not (campaign_dir / _CONTROLS_FILENAME).exists()
    assert not (campaign_dir / _FILENAME).exists()


@pytest.mark.parametrize(
    ("mode", "problem_declaration"),
    (("s2c1", None), ("s2c3", None), ("s2c5a", object())),
)
def test_default_off_preserves_old_controls_impl_call_surface(
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    problem_declaration: Any,
) -> None:
    expected = object()

    def old_impl(
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
        verification_gate: Any,
        operator_execute_signature: Any,
        research_input: Any,
        research_history: Any,
        resource_envelope: Any,
        code_research_limits: Any,
        qualification_only: Any,
        problem_declaration: Any,
    ) -> Any:
        assert owner is expected
        return expected

    monkeypatch.setattr(
        controls_composition,
        "_prepare_initial_screening_controls_setup_impl",
        old_impl,
    )
    result = _prepare_initial_screening_controls_setup(
        owner=expected,
        request=mode,
        problem_spec=None,
        protocol_config=None,
        split_manifest=None,
        seed_ledger=None,
        champion=None,
        campaign_dir="campaign",
        experiment_protocol=None,
        adapter=None,
        verification_gate=None,
        operator_execute_signature=None,
        research_input=None,
        research_history=(),
        resource_envelope=None,
        code_research_limits=None,
        qualification_only=None,
        problem_declaration=problem_declaration,
    )

    assert result is expected


@pytest.mark.parametrize(
    ("mode", "controls", "provider", "problem"),
    (
        ("plain", None, None, None),
        ("s2c1", object(), None, None),
        ("s2c3", object(), object(), None),
        ("s2c5a", object(), object(), object()),
    ),
)
def test_default_off_preserves_old_campaign_composition_call_surface(
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    controls: Any,
    provider: Any,
    problem: Any,
) -> None:
    calls: list[str] = []

    def old_compose(
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
        verification_gate: Any = None,
        operator_execute_signature: Any = None,
        research_input: Any = None,
        research_history: Any = (),
        resource_envelope: Any = None,
        code_research_limits: Any = None,
        qualification_only: Any = None,
        _initial_screening_study_controls: Any = None,
        _initial_screening_provider_policy: Any = None,
        _initial_screening_problem_spec: Any = None,
    ) -> None:
        assert type(owner) is CampaignManager
        calls.append(mode)

    monkeypatch.setattr(
        campaign_composition_module,
        "compose_campaign_services",
        old_compose,
    )
    CampaignManager(
        problem_spec=None,
        protocol_config=None,
        split_manifest=None,
        seed_ledger=None,
        llm_client=None,
        champion=None,
        campaign_dir="campaign",
        experiment_protocol=None,
        adapter=None,
        _initial_screening_study_controls=controls,
        _initial_screening_provider_policy=provider,
        _initial_screening_problem_spec=problem,
    )

    assert calls == [mode]


def test_active_campaign_failure_has_fixed_context_precedence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("private nested failure")

    monkeypatch.setattr(
        campaign_composition_module,
        "compose_campaign_services",
        fail,
    )
    with pytest.raises(_InitialScreeningResearchContextError) as captured:
        CampaignManager(
            problem_spec=None,
            protocol_config=None,
            split_manifest=None,
            seed_ledger=None,
            llm_client=None,
            champion=None,
            campaign_dir="private/campaign/path",
            experiment_protocol=None,
            adapter=None,
            _initial_screening_study_controls=object(),
            _initial_screening_provider_policy=object(),
            _initial_screening_problem_spec=object(),
            _initial_screening_research_context=object(),
        )

    error = captured.value
    assert error.args == (_ERROR,)
    assert error.__cause__ is None
    assert error.__context__ is None
    assert "private" not in repr(error)


def test_active_rejects_replaced_top_compose_before_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def replacement(*_args: Any, **_kwargs: Any) -> None:
        nonlocal calls
        calls += 1

    monkeypatch.setattr(
        campaign_composition_module,
        "compose_campaign_services",
        replacement,
    )
    with pytest.raises(_InitialScreeningResearchContextError) as captured:
        _active_manager(tmp_path, monkeypatch)

    _assert_fixed_research_context_error(captured.value)
    assert calls == 0
    _assert_no_control_or_research_leaf(tmp_path)


def test_active_rejects_replaced_declaration_resolver_before_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def replacement(_name: str) -> Any:
        nonlocal calls
        calls += 1
        return lambda *_args, **_kwargs: None

    monkeypatch.setattr(
        declaration_composition,
        "_validated_research_context_integration_entry",
        replacement,
    )
    with pytest.raises(_InitialScreeningResearchContextError) as captured:
        _active_manager(tmp_path, monkeypatch)

    _assert_fixed_research_context_error(captured.value)
    assert calls == 0
    _assert_no_control_or_research_leaf(tmp_path)


def test_active_rejects_replaced_declaration_finalizer_before_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def replacement(*_args: Any, **_kwargs: Any) -> None:
        nonlocal calls
        calls += 1

    monkeypatch.setattr(
        declaration_composition,
        "_finalize_initial_screening_declarations",
        replacement,
    )
    with pytest.raises(_InitialScreeningResearchContextError) as captured:
        _active_manager(tmp_path, monkeypatch)

    _assert_fixed_research_context_error(captured.value)
    assert calls == 0
    _assert_no_control_or_research_leaf(tmp_path)


def test_active_rejects_replaced_controls_installer_resolver_before_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def replacement() -> Any:
        nonlocal calls
        calls += 1
        return lambda *_args, **_kwargs: None

    monkeypatch.setattr(
        controls_composition,
        "_validated_research_context_runtime_installer",
        replacement,
    )
    with pytest.raises(_InitialScreeningResearchContextError) as captured:
        _active_manager(tmp_path, monkeypatch)

    _assert_fixed_research_context_error(captured.value)
    assert calls == 0
    _assert_no_control_or_research_leaf(tmp_path)


def test_active_campaign_error_ignores_replaced_schema_token(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        research_context_schema,
        "_ERROR",
        "PRIVATE_BODY_SENTINEL",
    )
    with pytest.raises(_InitialScreeningResearchContextError) as captured:
        _active_manager(tmp_path, monkeypatch)

    _assert_fixed_research_context_error(captured.value)
    _assert_no_control_or_research_leaf(tmp_path)


def test_active_materializer_error_ignores_replaced_validation_token(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = _active_manager(tmp_path, monkeypatch)
    calls = 0

    def replacement(*_args: Any, **_kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        raise RuntimeError("private replaced materializer")

    monkeypatch.setattr(
        research_context_validation,
        "_ERROR",
        "PRIVATE_BODY_SENTINEL",
    )
    monkeypatch.setattr(
        integration_module,
        "_materialize_research_context_h_fields",
        replacement,
    )
    branch = Branch(
        branch_id="b1-token-drift",
        state=BranchState.NEW,
        base_champion_id=1,
    )
    with pytest.raises(_InitialScreeningResearchContextError) as captured:
        manager._problem_runtime.build_hypothesis_context(
            branch=branch,
            champion=manager._champion,
        )

    _assert_fixed_research_context_error(captured.value)
    assert calls == 0


def test_active_rejects_replaced_composition_prepare_before_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def replacement(*_args: Any, **_kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        raise RuntimeError("private replaced prepare")

    monkeypatch.setattr(
        research_composition,
        "_prepare_initial_screening_research_context",
        replacement,
    )
    with pytest.raises(_InitialScreeningResearchContextError) as captured:
        _active_manager(tmp_path, monkeypatch)

    _assert_fixed_research_context_error(captured.value)
    assert calls == 0


def test_active_rejects_replaced_fourth_publisher_before_call_or_leaf(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def replacement(*_args: Any, **_kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        raise RuntimeError("private replaced publisher")

    monkeypatch.setattr(research_context_io, "_publish_fourth_control", replacement)
    with pytest.raises(_InitialScreeningResearchContextError) as captured:
        _active_manager(tmp_path, monkeypatch)

    _assert_fixed_research_context_error(captured.value)
    assert calls == 0
    assert not (tmp_path / "campaign" / _FILENAME).exists()


@pytest.mark.parametrize(
    ("name", "replacement"),
    (
        ("_LOCAL_FUNCTIONS", ()),
        ("_has_exact_methods", lambda *_args, **_kwargs: True),
        ("_CAPSULE_ATTRIBUTE", "_private_replaced_capsule"),
        ("__name__", "private.replaced.integration"),
    ),
)
def test_active_integration_drift_has_fixed_error_before_work(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    replacement: Any,
) -> None:
    monkeypatch.setattr(integration_module, name, replacement)
    with pytest.raises(_InitialScreeningResearchContextError) as captured:
        _active_manager(tmp_path, monkeypatch)

    _assert_fixed_research_context_error(captured.value)
    assert not (tmp_path / "campaign" / _FILENAME).exists()


def test_active_rejects_replaced_integration_validator_before_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def replacement() -> None:
        nonlocal calls
        calls += 1
        raise RuntimeError("private replaced integration validator")

    monkeypatch.setattr(
        integration_module,
        "_validate_integration_dependencies",
        replacement,
    )
    with pytest.raises(_InitialScreeningResearchContextError) as captured:
        _active_manager(tmp_path, monkeypatch)

    _assert_fixed_research_context_error(captured.value)
    assert calls == 0
    assert not (tmp_path / "campaign" / _FILENAME).exists()


def test_default_off_does_not_call_integration_validator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    expected = object()

    def bomb() -> None:
        nonlocal calls
        calls += 1
        raise RuntimeError("private integration validator")

    def old_impl(**_kwargs: Any) -> Any:
        return expected

    monkeypatch.setattr(
        integration_module,
        "_validate_integration_dependencies",
        bomb,
    )
    monkeypatch.setattr(
        controls_composition,
        "_prepare_initial_screening_controls_setup_impl",
        old_impl,
    )
    result = _prepare_initial_screening_controls_setup(
        owner=expected,
        request=object(),
        problem_spec=None,
        protocol_config=None,
        split_manifest=None,
        seed_ledger=None,
        champion=None,
        campaign_dir="campaign",
        experiment_protocol=None,
        adapter=None,
        verification_gate=None,
        operator_execute_signature=None,
        research_input=None,
        research_history=(),
        resource_envelope=None,
        code_research_limits=None,
        qualification_only=None,
        problem_declaration=None,
    )

    assert result is expected
    assert calls == 0


def test_full_cvrp_active_path_joins_runtime_and_materializes_fresh_h(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = _active_manager(tmp_path, monkeypatch)
    runtime = manager._problem_runtime
    context_manager = runtime.ctx_manager
    capsule = manager._initial_screening_research_context.capsule

    assert manager._initial_screening_research_context_active is True
    assert runtime._initial_screening_research_context_capsule is capsule
    assert context_manager._initial_screening_research_context_capsule is capsule
    assert manager._proposal_pipeline.problem_runtime is runtime
    assert runtime.research_input is None
    assert runtime.research_history == ()
    assert (tmp_path / "campaign" / _FILENAME).is_file()
    assert not (tmp_path / "campaign" / "research_input.json").exists()

    branch = Branch(
        branch_id="b1",
        state=BranchState.NEW,
        base_champion_id=1,
    )
    first = runtime.build_hypothesis_context(branch=branch, champion=manager._champion)
    first["research_question"]["current_question"] = "mutated"
    first["prior_research_observations"].append({"mutated": True})
    second = runtime.build_hypothesis_context(branch=branch, champion=manager._champion)

    assert second["research_question"] == {
        "current_question": "What bounded change should be tested?"
    }
    assert second["prior_research_observations"] == []
