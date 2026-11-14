"""Adapter-only problem loading at the normal CLI/campaign boundary."""

from __future__ import annotations

import inspect
from pathlib import Path
from types import SimpleNamespace

import pytest

from scion.cli.commands.init_run import _load_cli_problem_adapter
from scion.config.problem import ProtocolConfig, SeedLedgerConfig, SplitManifest
from scion.core.campaign import CampaignManager
from scion.core.models import ChampionState
from scion.core.problem_runtime import ProblemRuntime
from scion.proposal.mock_client import MockLLMClient
from scion.protocol.experiment import ExperimentProtocol, SeedLedger, SplitManager
from scion.verification.gate import VerificationGate

PROBLEMS_DIR = Path(__file__).resolve().parents[2] / "problems"


@pytest.mark.parametrize(
    ("problem_path", "problem_id"),
    (
        (PROBLEMS_DIR / "cvrp" / "problem.yaml", "cvrp"),
        (
            PROBLEMS_DIR / "warehouse_delivery" / "problem-v1.yaml",
            "warehouse_delivery",
        ),
        (PROBLEMS_DIR / "toy_tsp" / "problem.yaml", "toy_tsp"),
    ),
)
def test_cli_loads_concrete_adapter_as_the_problem_owner(
    problem_path: Path,
    problem_id: str,
) -> None:
    adapter = _load_cli_problem_adapter(problem_path)
    runtime = ProblemRuntime(adapter=adapter)

    assert adapter.spec.id == problem_id
    assert runtime.spec is adapter.spec


def test_campaign_constructor_has_one_problem_input() -> None:
    parameters = inspect.signature(CampaignManager).parameters

    assert "adapter" in parameters
    assert "problem_spec" not in parameters
    assert "operator_execute_signature" not in parameters


def test_problem_runtime_overrides_caller_supplied_problem_spec() -> None:
    adapter = _load_cli_problem_adapter(PROBLEMS_DIR / "cvrp" / "problem-v1.yaml")
    warehouse = _load_cli_problem_adapter(
        PROBLEMS_DIR / "warehouse_delivery" / "problem-v1.yaml"
    )
    runtime = ProblemRuntime(adapter=adapter)
    runtime._ctx_manager = SimpleNamespace(
        build_hypothesis_context=lambda **kwargs: kwargs,
        build_code_context=lambda **kwargs: kwargs,
    )

    hypothesis_context = runtime.build_hypothesis_context(
        problem_spec=warehouse.spec
    )
    code_context = runtime.build_code_context(problem_spec=warehouse.spec)

    assert hypothesis_context["problem_spec"] is adapter.spec
    assert code_context["problem_spec"] is adapter.spec


def test_experiment_protocol_adapter_mode_rejects_secondary_problem_inputs() -> None:
    adapter = _load_cli_problem_adapter(PROBLEMS_DIR / "cvrp" / "problem-v1.yaml")
    warehouse = _load_cli_problem_adapter(
        PROBLEMS_DIR / "warehouse_delivery" / "problem-v1.yaml"
    )
    base = {
        "protocol_config": ProtocolConfig(),
        "split_manager": SplitManager(SplitManifest()),
        "seed_ledger": SeedLedger(SeedLedgerConfig()),
        "runner": object(),
        "adapter": adapter,
    }

    for name, value in (
        ("problem_spec", warehouse.spec),
        ("metric_specs", tuple(warehouse.spec.objectives)),
        ("objective_policy", warehouse.spec.objective_policy),
    ):
        with pytest.raises(TypeError, match=name):
            ExperimentProtocol(**base, **{name: value})


def test_protocol_adapter_bind_replaces_the_complete_adapter_semantics() -> None:
    warehouse = _load_cli_problem_adapter(
        PROBLEMS_DIR / "warehouse_delivery" / "problem-v1.yaml"
    )
    cvrp = _load_cli_problem_adapter(PROBLEMS_DIR / "cvrp" / "problem-v1.yaml")
    protocol = ExperimentProtocol(
        ProtocolConfig(),
        SplitManager(SplitManifest()),
        SeedLedger(SeedLedgerConfig()),
        runner=object(),
        adapter=warehouse,
    )

    protocol.set_problem_adapter(cvrp)

    assert protocol._problem_adapter is cvrp
    assert protocol.problem_spec is cvrp.spec
    assert protocol._metric_specs == tuple(cvrp.spec.objectives)
    assert protocol._objective_policy is cvrp.spec.objective_policy
    assert protocol._metric_specs != tuple(warehouse.spec.objectives)
    assert protocol.config.effect_metric == "total_distance"
    assert protocol.config.protected_objectives == ("fleet_violation",)
    assert protocol.config.runtime.runtime_model == "budget_exhausting"
    assert protocol.config.practical_delta_screen == 2.0
    assert protocol.config.practical_delta_validate == 1.0


def test_protocol_adapter_bind_without_metrics_fails_atomically() -> None:
    warehouse = _load_cli_problem_adapter(
        PROBLEMS_DIR / "warehouse_delivery" / "problem-v1.yaml"
    )
    cvrp = _load_cli_problem_adapter(PROBLEMS_DIR / "cvrp" / "problem-v1.yaml")
    protocol = ExperimentProtocol(
        ProtocolConfig(),
        SplitManager(SplitManifest()),
        SeedLedger(SeedLedgerConfig()),
        runner=object(),
        adapter=warehouse,
    )
    missing_spec = cvrp.spec.model_copy(
        update={"objectives": [], "objective_policy": None}
    )
    missing_metrics_adapter = SimpleNamespace(spec=missing_spec)

    with pytest.raises(ValueError, match="metric_specs are required"):
        protocol.set_problem_adapter(missing_metrics_adapter)

    assert protocol._problem_adapter is warehouse
    assert protocol.problem_spec is warehouse.spec
    assert protocol._metric_specs == tuple(warehouse.spec.objectives)
    assert protocol._objective_policy is warehouse.spec.objective_policy


def test_verification_gate_adapter_mode_rejects_secondary_problem_inputs() -> None:
    adapter = _load_cli_problem_adapter(PROBLEMS_DIR / "cvrp" / "problem-v1.yaml")
    warehouse = _load_cli_problem_adapter(
        PROBLEMS_DIR / "warehouse_delivery" / "problem-v1.yaml"
    )

    parameters = inspect.signature(VerificationGate).parameters
    assert "adapter" in parameters
    assert "problem_spec" not in parameters
    assert "operator_execute_signature" not in parameters
    assert "require_adapter_for_runtime" not in parameters
    assert "allow_adapter_runtime_fallback" not in parameters
    with pytest.raises(TypeError, match="problem_spec"):
        VerificationGate(problem_spec=warehouse.spec, adapter=adapter)
    with pytest.raises(TypeError, match="operator_execute_signature"):
        VerificationGate(adapter=adapter, operator_execute_signature="wrong")

    gate = VerificationGate(adapter=adapter)
    assert gate._spec is adapter.spec
    assert (
        gate._operator_execute_signature
        == adapter.spec.operator_interface.execute_signature
    )


@pytest.mark.parametrize(
    "problem_path",
    (
        PROBLEMS_DIR / "cvrp" / "problem.yaml",
        PROBLEMS_DIR / "warehouse_delivery" / "problem-v1.yaml",
    ),
)
def test_real_v1_adapter_composes_campaign_without_a_legacy_projection(
    tmp_path: Path,
    problem_path: Path,
) -> None:
    adapter = _load_cli_problem_adapter(problem_path)
    spec = adapter.spec
    protocol_config = ProtocolConfig()
    split_manifest = SplitManifest(
        screening=["screening-case"],
        validation=["validation-case"],
        frozen=["frozen-case"],
        canary=["canary-case"],
    )
    seed_ledger = SeedLedgerConfig(
        screening=[1],
        validation=[2],
        frozen=[3],
        canary=[4],
    )
    protocol = ExperimentProtocol(
        protocol_config,
        SplitManager(split_manifest),
        SeedLedger(seed_ledger),
        runner=object(),
        adapter=adapter,
    )
    manager = CampaignManager(
        protocol_config=protocol_config,
        split_manifest=split_manifest,
        seed_ledger=seed_ledger,
        llm_client=MockLLMClient(),
        champion=ChampionState(
            version=1,
            operator_pool={},
            code_snapshot_path=spec.root_dir,
        ),
        campaign_dir=str(tmp_path / spec.id),
        experiment_protocol=protocol,
        adapter=adapter,
        verification_gate=VerificationGate(),
    )

    assert manager._problem_runtime.spec is adapter.spec
    assert protocol.problem_spec is adapter.spec
    assert manager._contract_gate._spec is adapter.spec
    assert (
        manager._contract_gate._operator_signature.display
        == adapter.spec.operator_interface.execute_signature
    )
    assert manager._vgate._spec is adapter.spec
    assert manager._vgate._adapter is adapter
