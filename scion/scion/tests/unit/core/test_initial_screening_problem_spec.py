from __future__ import annotations

import builtins
import copy
import json
import stat
from pathlib import Path
from typing import Any

import pytest

from scion.config.problem import ProblemSpec
from scion.config.problem import SolverConfig as LegacySolverConfig
from scion.core.campaign import CampaignManager
from scion.core.code_research_limits import CodeResearchLimits
from scion.core.initial_screening_problem_spec import (
    _ERROR,
    _FILENAME,
    _LIMITATIONS,
    _MAX_BYTES,
    _PROJECTION_KEYS,
    _SCHEMA_VERSION,
    _SCOPE,
    _canonical_problem_spec_payload,
    _freeze_problem_spec_inputs,
    _InitialScreeningProblemSpecError,
    _InitialScreeningProblemSpecRequest,
    _prepare_initial_screening_problem_spec,
)
from scion.core.initial_screening_study_controls import (
    _ERROR as _CONTROLS_ERROR,
)
from scion.core.initial_screening_study_controls import (
    _InitialScreeningStudyControlsError,
    _InitialScreeningStudyControlsRequest,
)
from scion.core.initial_screening_study_provider_policy import (
    _InitialScreeningProviderPolicyRequest,
)
from scion.core.models import ChampionState
from scion.core.problem_runtime import ProblemRuntime
from scion.core.qualification import QualificationOnlyConfig
from scion.core.resource_envelope import ResourceEnvelope
from scion.problem import bridge as problem_bridge_module
from scion.problem.bridge import (
    ProblemSpecBridge,
    bridge_problem_spec_v1,
    load_problem_spec_v1_from_yaml,
)
from scion.problem.loader import load_problem_adapter
from scion.problem.spec import (
    OperatorInterfaceSpec,
    ProblemAdapterRef,
    ProblemSpecV1,
    SearchSpaceSpec,
)
from scion.proposal.llm.client import LLMClient
from scion.protocol.experiment import ExperimentProtocol, SeedLedger, SplitManager
from scion.runtime.runner import ResourceLimits
from scion.runtime.subprocess_runner import LocalSubprocessRunner
from scion.tests.test_cvrp_controlled_campaign import CVRP_DIR
from scion.tests.unit.core.test_initial_screening_study_controls import (
    _ledger,
    _protocol_config,
    _split,
)
from scion.tests.unit.core.test_initial_screening_study_controls import (
    _manager as _controls_manager,
)


def _cvrp_inputs() -> tuple[ProblemSpecV1, ProblemSpecBridge, Any]:
    spec_path = Path(__file__).parents[3] / "problems" / "cvrp" / "problem-v1.yaml"
    spec_v1 = load_problem_spec_v1_from_yaml(spec_path)
    bridge = bridge_problem_spec_v1(spec_v1)
    return spec_v1, bridge, load_problem_adapter(spec_v1)


def test_problem_spec_marker_is_zero_value_and_redacted() -> None:
    marker = _InitialScreeningProblemSpecRequest()

    assert vars(marker) == {}
    assert repr(marker) == "_InitialScreeningProblemSpecRequest(<redacted>)"
    assert str(marker) == repr(marker)
    assert "0x" not in repr(marker)


def test_problem_spec_declaration_is_exact_root_free_canonical_payload() -> None:
    spec_v1, bridge, adapter = _cvrp_inputs()
    inputs = _freeze_problem_spec_inputs(
        bridge.problem_spec,
        adapter,
        bridge.operator_execute_signature,
    )
    raw = inputs.payload_bytes
    payload = json.loads(raw)

    assert set(payload) == {
        "schema_version",
        "scope",
        "limitations",
        "problem_spec_v1",
    }
    assert payload["schema_version"] == _SCHEMA_VERSION
    assert payload["scope"] == _SCOPE
    assert tuple(payload["limitations"]) == _LIMITATIONS
    assert set(payload["problem_spec_v1"]) == set(_PROJECTION_KEYS)
    assert len(_PROJECTION_KEYS) == 30
    assert "root_dir" not in payload["problem_spec_v1"]
    assert str(spec_v1.root_dir).encode() not in raw
    assert len(raw) <= _MAX_BYTES
    assert raw == (
        json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )
    assert raw == _canonical_problem_spec_payload(inputs.spec_v1)
    assert inputs.spec_v1 is not spec_v1
    assert inputs.problem_spec is not bridge.problem_spec
    assert inputs.adapter is not adapter
    assert inputs.adapter.spec is inputs.spec_v1
    assert inputs.problem_spec.spec_v1 is inputs.spec_v1
    assert inputs.root_dir == spec_v1.root_dir
    assert _FILENAME == "initial_screening_problem_spec.json"


def _problem_manager(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> CampaignManager:
    _spec_v1, bridge, adapter = _cvrp_inputs()
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
            api_key="private-problem-declaration-secret",
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
    )


def _fixed_problem_error(error: BaseException) -> None:
    assert type(error) is _InitialScreeningProblemSpecError
    assert error.args == (_ERROR,)
    assert error.__cause__ is None
    assert error.__context__ is None


def test_problem_spec_opt_in_publishes_third_leaf_before_runtime_side_effects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = _problem_manager(tmp_path, monkeypatch)
    leaf = tmp_path / "campaign" / _FILENAME
    payload = json.loads(leaf.read_bytes())

    assert payload["schema_version"] == _SCHEMA_VERSION
    assert stat.S_IMODE(leaf.stat().st_mode) == 0o600
    assert leaf.stat().st_nlink == 1
    assert (
        manager._problem_runtime.spec
        is manager._initial_screening_problem_spec.problem_spec
    )
    assert (
        manager._problem_runtime.adapter
        is manager._initial_screening_problem_spec.adapter
    )
    assert manager._problem_runtime.spec.spec_v1 is (
        manager._initial_screening_problem_spec.spec_v1
    )


@pytest.mark.parametrize("close_target", ["attached", "root"])
def test_postcommit_close_errors_do_not_revoke_problem_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    close_target: str,
) -> None:
    import fcntl
    import os

    from scion.core import initial_screening_problem_spec_io

    original_close = os.close
    problem_leaf_closed = False
    failures: list[str] = []

    def close_with_postcommit_error(fd: int) -> None:
        nonlocal problem_leaf_closed
        try:
            target = os.readlink(f"/proc/self/fd/{fd}")
        except OSError:
            target = ""
        access_mode = fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_ACCMODE
        original_close(fd)
        if (
            not failures
            and target.endswith(f"/{_FILENAME}")
            and access_mode == os.O_WRONLY
        ):
            problem_leaf_closed = True
            if close_target == "attached":
                failures.append(close_target)
                raise OSError("injected postcommit attached close error")
        elif (
            close_target == "root"
            and not failures
            and problem_leaf_closed
            and target.endswith("/campaign")
        ):
            failures.append(close_target)
            raise OSError("injected postcommit root close error")

    monkeypatch.setattr(
        initial_screening_problem_spec_io.os, "close", close_with_postcommit_error
    )

    manager = _problem_manager(tmp_path, monkeypatch)

    assert failures == [close_target]
    assert (
        type(manager._initial_screening_problem_spec.publication.leaf_fingerprint)
        is tuple
    )
    assert (tmp_path / "campaign" / _FILENAME).read_bytes() == (
        manager._initial_screening_problem_spec.payload_bytes
    )


def test_problem_spec_run_gate_accepts_exact_direct_consumers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = _problem_manager(tmp_path, monkeypatch)
    calls: list[object] = []
    manager._run_research_environment_preflight = lambda: calls.append("preflight")

    def run_terminal(*, requested_rounds: int) -> str:
        calls.append(requested_rounds)
        return "terminal"

    manager._campaign_loop.run = run_terminal

    assert manager.run(2) == "terminal"
    assert calls == ["preflight", 2]


def test_problem_spec_run_gate_rejects_direct_alias_before_preflight(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = _problem_manager(tmp_path, monkeypatch)
    manager._problem_runtime._spec = object()
    manager._run_research_environment_preflight = lambda: pytest.fail(
        "preflight ran before problem declaration gate"
    )

    with pytest.raises(_InitialScreeningProblemSpecError) as caught:
        manager.run(2)

    _fixed_problem_error(caught.value)


def test_problem_spec_consumer_class_drift_fails_before_campaign_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        ProblemRuntime,
        "build_hypothesis_context",
        lambda self, **kwargs: kwargs,
    )

    with pytest.raises(_InitialScreeningProblemSpecError) as caught:
        _problem_manager(tmp_path, monkeypatch)

    assert caught.value.args == (_ERROR,)
    assert not (tmp_path / "campaign").exists()


def test_problem_spec_operator_signature_structure_is_joined_at_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = _problem_manager(tmp_path, monkeypatch)
    object.__setattr__(manager._contract_gate._operator_signature, "args", ("self",))
    manager._run_research_environment_preflight = lambda: pytest.fail(
        "preflight ran before problem declaration gate"
    )

    with pytest.raises(_InitialScreeningProblemSpecError) as caught:
        manager.run(2)

    assert caught.value.args == (_ERROR,)


def test_s2c1_only_calls_the_legacy_controls_setup_signature(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scion.core import campaign_composition

    original = campaign_composition._prepare_initial_screening_controls_setup
    calls: list[str] = []

    def old_setup(
        *,
        owner: object,
        request: object,
        problem_spec: object,
        protocol_config: object,
        split_manifest: object,
        seed_ledger: object,
        champion: object,
        campaign_dir: str,
        experiment_protocol: object,
        adapter: object,
        verification_gate: object,
        operator_execute_signature: object,
        research_input: object,
        research_history: object,
        resource_envelope: object,
        code_research_limits: object,
        qualification_only: object,
    ) -> object:
        calls.append("old")
        return original(
            owner=owner,
            request=request,
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

    monkeypatch.setattr(
        campaign_composition,
        "_prepare_initial_screening_controls_setup",
        old_setup,
    )
    _controls_manager(
        tmp_path,
        request=_InitialScreeningStudyControlsRequest(requested_rounds=2),
    )

    assert calls == ["old"]


@pytest.mark.parametrize("mode", ["legacy", "controls", "provider"])
def test_default_off_paths_do_not_call_problem_declaration_helpers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    from scion.core import initial_screening_declaration_composition

    monkeypatch.setattr(
        initial_screening_declaration_composition,
        "_prepare_initial_screening_declarations",
        lambda **kwargs: pytest.fail("default-off path called S2c5 helper"),
    )
    request = (
        None
        if mode == "legacy"
        else _InitialScreeningStudyControlsRequest(requested_rounds=2)
    )
    provider_request = (
        _InitialScreeningProviderPolicyRequest() if mode == "provider" else None
    )
    client = None
    if mode == "provider":
        monkeypatch.setenv("SCION_REASONING_EFFORT", "high")
        client = LLMClient(
            model="gpt-5.6-sol",
            api_key="default-off-secret",
            base_url="https://provider.example",
            timeout_sec=61.0,
        )
    _controls_manager(
        tmp_path,
        request=request,
        llm_client=client,
        provider_policy_request=provider_request,
    )


@pytest.mark.parametrize("mode", ["legacy", "controls", "provider"])
def test_default_off_runs_do_not_import_or_call_problem_validation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    from scion.core import initial_screening_problem_spec_validation

    request = (
        None
        if mode == "legacy"
        else _InitialScreeningStudyControlsRequest(requested_rounds=2)
    )
    provider_request = (
        _InitialScreeningProviderPolicyRequest() if mode == "provider" else None
    )
    client = None
    if mode == "provider":
        monkeypatch.setenv("SCION_REASONING_EFFORT", "high")
        client = LLMClient(
            model="gpt-5.6-sol",
            api_key="default-run-secret",
            base_url="https://provider.example",
            timeout_sec=61.0,
        )
    manager, _aliases, _objectives = _controls_manager(
        tmp_path,
        request=request,
        llm_client=client,
        provider_policy_request=provider_request,
    )
    monkeypatch.setattr(
        initial_screening_problem_spec_validation,
        "_prepare_problem_spec_run_validation",
        lambda *args, **kwargs: pytest.fail("default run called problem validation"),
    )
    original_import = builtins.__import__

    def guarded_import(
        name: str,
        globals: Any = None,
        locals: Any = None,
        fromlist: Any = (),
        level: int = 0,
    ) -> Any:
        if name.startswith("scion.core.initial_screening_problem_spec"):
            pytest.fail("default run imported the problem boundary")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    manager._run_research_environment_preflight = lambda: None
    manager._campaign_loop.run = lambda *, requested_rounds: (
        "terminal",
        requested_rounds,
    )

    assert manager.run(2) == ("terminal", 2)


def test_default_off_controls_error_does_not_import_problem_error_type(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager, _aliases, _objectives = _controls_manager(
        tmp_path,
        request=_InitialScreeningStudyControlsRequest(requested_rounds=2),
    )
    original_import = builtins.__import__

    def guarded_import(
        name: str,
        globals: Any = None,
        locals: Any = None,
        fromlist: Any = (),
        level: int = 0,
    ) -> Any:
        if name.startswith("scion.core.initial_screening_problem_spec"):
            pytest.fail("controls error imported the problem boundary")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded_import)

    with pytest.raises(_InitialScreeningStudyControlsError) as caught:
        manager.run(3)

    assert caught.value.args == (_CONTROLS_ERROR,)
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None


def test_registered_problem_owner_cannot_clear_both_markers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = _problem_manager(tmp_path, monkeypatch)
    del vars(manager)["_initial_screening_problem_spec_active"]
    del vars(manager)["_initial_screening_problem_spec"]
    manager._run_research_environment_preflight = lambda: pytest.fail(
        "preflight ran after problem marker clear"
    )

    with pytest.raises(_InitialScreeningProblemSpecError) as caught:
        manager.run(2)

    _fixed_problem_error(caught.value)


def test_legacy_composition_failure_does_not_import_problem_boundary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scion.core import campaign_composition

    def fail_composition(*args: object, **kwargs: object) -> None:
        raise RuntimeError("legacy composition failure")

    original_import = builtins.__import__

    def guarded_import(
        name: str,
        globals: Any = None,
        locals: Any = None,
        fromlist: Any = (),
        level: int = 0,
    ) -> Any:
        if name == "scion.core.initial_screening_problem_spec":
            pytest.fail("legacy failure imported the problem boundary")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(
        campaign_composition, "compose_campaign_services", fail_composition
    )
    monkeypatch.setattr(builtins, "__import__", guarded_import)
    with pytest.raises(RuntimeError, match="legacy composition failure"):
        CampaignManager(
            problem_spec=None,
            protocol_config=None,
            split_manifest=None,
            seed_ledger=None,
            llm_client=None,
            champion=None,
            campaign_dir="unused",
            experiment_protocol=None,
            adapter=None,
        )


@pytest.mark.parametrize(
    ("model_type", "field_name", "replacement"),
    [
        (ProblemSpecV1, "description", "hidden-description"),
        (ProblemSpecV1, "development_workspace_paths", []),
        (ProblemSpecV1, "root_dir", "/tmp/hidden-root"),
        (ProblemSpecV1, "adapter", None),
        (ProblemSpecV1, "id", "hidden-id"),
        (
            OperatorInterfaceSpec,
            "execute_signature",
            "execute(self) -> None",
        ),
        (ProblemAdapterRef, "import_path", "hidden.module:Adapter"),
        (LegacySolverConfig, "time_limit_sec", 1),
    ],
)
def test_problem_model_field_class_shadows_fail_before_campaign_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    model_type: type,
    field_name: str,
    replacement: object,
) -> None:
    _spec_v1, bridge, adapter = _cvrp_inputs()
    monkeypatch.setattr(
        model_type,
        field_name,
        property(lambda self: replacement),
        raising=False,
    )

    with pytest.raises(_InitialScreeningProblemSpecError) as caught:
        _prepare_initial_screening_problem_spec(
            _InitialScreeningProblemSpecRequest(),
            _InitialScreeningStudyControlsRequest(requested_rounds=2),
            _InitialScreeningProviderPolicyRequest(),
            bridge.problem_spec,
            adapter,
            bridge.operator_execute_signature,
        )

    _fixed_problem_error(caught.value)
    assert not (tmp_path / "campaign").exists()


def test_nested_model_dump_override_fails_before_first_leaf(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_model_dump = SearchSpaceSpec.model_dump

    def drifted_model_dump(self: SearchSpaceSpec, *args: Any, **kwargs: Any) -> Any:
        return original_model_dump(self, *args, **kwargs)

    monkeypatch.setattr(SearchSpaceSpec, "model_dump", drifted_model_dump)

    with pytest.raises(_InitialScreeningProblemSpecError) as caught:
        _problem_manager(tmp_path, monkeypatch)

    _fixed_problem_error(caught.value)
    assert not (tmp_path / "campaign").exists()


def test_bridge_result_class_global_drift_fails_before_first_leaf(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        problem_bridge_module,
        "ProblemSpecBridge",
        lambda **kwargs: ProblemSpecBridge(**kwargs),
    )

    with pytest.raises(_InitialScreeningProblemSpecError) as caught:
        _problem_manager(tmp_path, monkeypatch)

    _fixed_problem_error(caught.value)
    assert not (tmp_path / "campaign").exists()


def test_bridge_instance_accessor_drift_fails_before_first_leaf(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_getattribute = ProblemSpecBridge.__getattribute__

    def drifted_getattribute(self: ProblemSpecBridge, name: str) -> Any:
        if name == "operator_execute_signature":
            return "execute(self) -> None"
        return original_getattribute(self, name)

    monkeypatch.setattr(
        ProblemSpecBridge,
        "__getattribute__",
        drifted_getattribute,
    )

    with pytest.raises(_InitialScreeningProblemSpecError) as caught:
        _problem_manager(tmp_path, monkeypatch)

    _fixed_problem_error(caught.value)
    assert not (tmp_path / "campaign").exists()


def test_adapter_constructor_model_surface_drift_is_rejected_without_hook(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _spec_v1, bridge, adapter = _cvrp_inputs()
    adapter_type = type(adapter)
    original_init = adapter_type.__init__
    hooks: list[str] = []

    def hooked_signature(self: OperatorInterfaceSpec) -> str:
        hooks.append("field")
        return "execute(self) -> None"

    def mutating_init(self: Any, spec: ProblemSpecV1) -> None:
        original_init(self, spec)
        monkeypatch.setattr(
            OperatorInterfaceSpec,
            "execute_signature",
            property(hooked_signature),
            raising=False,
        )

    monkeypatch.setattr(adapter_type, "__init__", mutating_init)

    with pytest.raises(_InitialScreeningProblemSpecError) as caught:
        _prepare_initial_screening_problem_spec(
            _InitialScreeningProblemSpecRequest(),
            _InitialScreeningStudyControlsRequest(requested_rounds=2),
            _InitialScreeningProviderPolicyRequest(),
            bridge.problem_spec,
            adapter,
            bridge.operator_execute_signature,
        )

    _fixed_problem_error(caught.value)
    assert hooks == []


def test_adapter_constructor_legacy_bridge_surface_drift_has_zero_hooks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _spec_v1, bridge, adapter = _cvrp_inputs()
    adapter_type = type(adapter)
    original_init = adapter_type.__init__
    hooks: list[str] = []

    def mutating_init(self: Any, spec: ProblemSpecV1) -> None:
        original_init(self, spec)

        def hooked_spec_v1(legacy: ProblemSpec) -> ProblemSpecV1:
            hooks.append("legacy")
            return spec

        monkeypatch.setattr(
            ProblemSpec,
            "spec_v1",
            property(hooked_spec_v1),
            raising=False,
        )

    monkeypatch.setattr(adapter_type, "__init__", mutating_init)

    with pytest.raises(_InitialScreeningProblemSpecError) as caught:
        _prepare_initial_screening_problem_spec(
            _InitialScreeningProblemSpecRequest(),
            _InitialScreeningStudyControlsRequest(requested_rounds=2),
            _InitialScreeningProviderPolicyRequest(),
            bridge.problem_spec,
            adapter,
            bridge.operator_execute_signature,
        )

    _fixed_problem_error(caught.value)
    assert hooks == []


def test_postconstruction_model_surface_drift_fails_before_io_or_preflight(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scion.core import initial_screening_study_controls_validation

    manager = _problem_manager(tmp_path, monkeypatch)
    hooks: list[str] = []

    def hooked_signature(self: OperatorInterfaceSpec) -> str:
        hooks.append("field")
        return "execute(self) -> None"

    monkeypatch.setattr(
        OperatorInterfaceSpec,
        "execute_signature",
        property(hooked_signature),
        raising=False,
    )
    monkeypatch.setattr(
        initial_screening_study_controls_validation,
        "_validate_controls_publication",
        lambda *args, **kwargs: pytest.fail("filesystem rewalk ran"),
    )
    manager._run_research_environment_preflight = lambda: pytest.fail(
        "preflight ran before problem declaration gate"
    )

    with pytest.raises(_InitialScreeningProblemSpecError) as caught:
        manager.run(2)

    _fixed_problem_error(caught.value)
    assert hooks == []


def test_postconstruction_legacy_bridge_surface_drift_has_zero_hooks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from scion.core import initial_screening_study_controls_validation

    manager = _problem_manager(tmp_path, monkeypatch)
    frozen_v1 = manager._initial_screening_problem_spec.spec_v1
    hooks: list[str] = []

    def hooked_spec_v1(self: ProblemSpec) -> ProblemSpecV1:
        hooks.append("legacy")
        return frozen_v1

    monkeypatch.setattr(
        ProblemSpec,
        "spec_v1",
        property(hooked_spec_v1),
        raising=False,
    )
    monkeypatch.setattr(
        initial_screening_study_controls_validation,
        "_validate_controls_publication",
        lambda *args, **kwargs: pytest.fail("filesystem rewalk ran"),
    )
    manager._run_research_environment_preflight = lambda: pytest.fail(
        "preflight ran before problem declaration gate"
    )

    with pytest.raises(_InitialScreeningProblemSpecError) as caught:
        manager.run(2)

    _fixed_problem_error(caught.value)
    assert hooks == []


def test_problem_model_fields_registry_drift_fails_before_campaign_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _spec_v1, bridge, adapter = _cvrp_inputs()
    changed = dict(ProblemSpecV1.model_fields)
    changed.pop("description")
    monkeypatch.setattr(ProblemSpecV1, "model_fields", changed)

    with pytest.raises(_InitialScreeningProblemSpecError) as caught:
        _prepare_initial_screening_problem_spec(
            _InitialScreeningProblemSpecRequest(),
            _InitialScreeningStudyControlsRequest(requested_rounds=2),
            _InitialScreeningProviderPolicyRequest(),
            bridge.problem_spec,
            adapter,
            bridge.operator_execute_signature,
        )

    _fixed_problem_error(caught.value)
    assert not (tmp_path / "campaign").exists()


def test_problem_model_field_info_identity_drift_fails_before_campaign_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _spec_v1, bridge, adapter = _cvrp_inputs()
    changed = dict(ProblemSpecV1.model_fields)
    changed["description"] = copy.copy(changed["description"])
    monkeypatch.setattr(ProblemSpecV1, "model_fields", changed)

    with pytest.raises(_InitialScreeningProblemSpecError) as caught:
        _prepare_initial_screening_problem_spec(
            _InitialScreeningProblemSpecRequest(),
            _InitialScreeningStudyControlsRequest(requested_rounds=2),
            _InitialScreeningProviderPolicyRequest(),
            bridge.problem_spec,
            adapter,
            bridge.operator_execute_signature,
        )

    _fixed_problem_error(caught.value)
    assert not (tmp_path / "campaign").exists()


@pytest.mark.parametrize("mutation", ["leaf", "carrier", "service_shadow"])
def test_problem_run_failures_keep_the_problem_error_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    manager = _problem_manager(tmp_path, monkeypatch)
    if mutation == "leaf":
        (tmp_path / "campaign" / _FILENAME).write_bytes(b"{}\n")
    elif mutation == "carrier":
        vars(manager._initial_screening_problem_spec)["hidden"] = None
    else:
        manager._proposal_pipeline.generate_hypothesis = lambda **kwargs: kwargs
    manager._run_research_environment_preflight = lambda: pytest.fail(
        "preflight ran before problem declaration gate"
    )

    with pytest.raises(_InitialScreeningProblemSpecError) as caught:
        manager.run(2)

    _fixed_problem_error(caught.value)


@pytest.mark.parametrize(
    ("service_name", "field_name"),
    [
        ("_code_development_evaluator", "operator_execute_signature"),
        ("_vgate", "_operator_execute_signature"),
        ("_evidence_recorder", "_research_history_writer"),
    ],
)
def test_problem_run_primitive_joins_reject_equality_spoofs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    service_name: str,
    field_name: str,
) -> None:
    class EqAny:
        def __eq__(self, other: object) -> bool:
            return True

        def __ne__(self, other: object) -> bool:
            return False

    manager = _problem_manager(tmp_path, monkeypatch)
    service = vars(manager)[service_name]
    if service_name == "_evidence_recorder":
        service = vars(service)[field_name]
        field_name = "problem_id"
    object.__setattr__(service, field_name, EqAny())
    manager._run_research_environment_preflight = lambda: pytest.fail(
        "preflight ran before problem declaration gate"
    )

    with pytest.raises(_InitialScreeningProblemSpecError) as caught:
        manager.run(2)

    _fixed_problem_error(caught.value)
