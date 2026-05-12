"""CVRP protocol smoke tests using tiny synthetic fixtures only."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import yaml

from scion.config.problem import ProtocolConfig, SplitManifest, SeedLedgerConfig
from scion.core.campaign import CampaignManager
from scion.core.models import ChampionState
from scion.core.termination import TerminationConfig
from scion.core.models import ExperimentStage
from scion.problem.bridge import bridge_problem_spec_v1
from scion.problem.loader import load_problem_adapter
from scion.problem.spec import ProblemSpecV1
from scion.protocol.experiment import ExperimentProtocol, SeedLedger, SplitManager
from scion.proposal.mock_client import MockLLMClient
from scion.runtime.runner import ResourceLimits
from scion.runtime.subprocess_runner import LocalSubprocessRunner
from scion.verification.gate import VerificationGate


CVRP_DIR = Path(__file__).resolve().parents[1] / "problems" / "cvrp"


def _problem_v1() -> ProblemSpecV1:
    with open(CVRP_DIR / "problem-v1.yaml", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    data["root_dir"] = str(CVRP_DIR)
    return ProblemSpecV1(**data)


def _make_protocol(tmp_path: Path) -> tuple[ExperimentProtocol, ProblemSpecV1]:
    spec_v1 = _problem_v1()
    protocol = ProtocolConfig.from_yaml(CVRP_DIR / "protocol.yaml")
    split_manifest = SplitManifest.from_yaml(CVRP_DIR / "split_manifest.yaml")
    seed_ledger = SeedLedgerConfig.from_yaml(CVRP_DIR / "seed_ledger.yaml")
    runner = LocalSubprocessRunner(ResourceLimits(timeout_sec=10, memory_mb=1024))
    return (
        ExperimentProtocol(
            protocol_config=protocol,
            split_manager=SplitManager(split_manifest),
            seed_ledger=SeedLedger(seed_ledger),
            runner=runner,
            time_limit_sec=1,
            metrics_dir=str(tmp_path / "metrics"),
            metric_specs=tuple(spec_v1.objectives),
            objective_policy=spec_v1.objective_policy,
            require_metric_specs=True,
            problem_spec=spec_v1,
        ),
        spec_v1,
    )


def test_cvrp_protocol_yaml_loads_and_is_disjoint() -> None:
    protocol = ProtocolConfig.from_yaml(CVRP_DIR / "protocol.yaml")
    split_manifest = SplitManifest.from_yaml(CVRP_DIR / "split_manifest.yaml")
    seed_ledger = SeedLedgerConfig.from_yaml(CVRP_DIR / "seed_ledger.yaml")

    assert protocol.version == "0.4-cvrp-smoke"
    assert split_manifest.canary == ["data/tiny_canary.json"]
    assert seed_ledger.screening == [11, 29]


def test_cvrp_local_subprocess_runner_outputs_route_objective() -> None:
    runner = LocalSubprocessRunner(ResourceLimits(timeout_sec=10, memory_mb=1024))

    result = runner.run_solver(
        workdir=str(CVRP_DIR),
        instance_path="data/tiny_5.json",
        seed=11,
        time_limit_sec=1,
        registry_path="",
    )

    assert result.success is True
    assert result.output is not None
    assert result.output.feasible is True
    assert result.output.objective["fleet_violation"] == 0
    assert result.output.objective["total_distance"] == 8.0


def test_cvrp_protocol_canary_passes_with_adapter_valid_outputs(tmp_path: Path) -> None:
    proto, spec_v1 = _make_protocol(tmp_path)
    adapter = load_problem_adapter(spec_v1)

    result = proto.run_canary(str(CVRP_DIR), str(CVRP_DIR))

    assert result.passed is True

    inst = adapter.load_instance(str(CVRP_DIR / "data" / "tiny_5.json"))
    raw = json.loads((CVRP_DIR / "data" / "tiny_5.json").read_text())
    assert raw["name"] == inst.name


def test_cvrp_protocol_screening_runs_complete_with_metric_specs(tmp_path: Path) -> None:
    proto, _ = _make_protocol(tmp_path)

    result = proto.run_experiment(
        ExperimentStage.SCREENING,
        candidate_ws=str(CVRP_DIR),
        champion_ws=str(CVRP_DIR),
        hypothesis_action="modify",
    )

    assert result.stage == ExperimentStage.SCREENING
    assert result.stats.n_cases == 2
    assert result.stats.ties == 2
    assert result.stats.wins == 0
    assert result.stats.losses == 0
    assert result.case_ids == ("data/tiny_5.json", "data/tiny_6.json")
    assert result.seed_set == (11, 29)
    assert result.pair_feedback
    assert result.raw_metrics_ref

    raw_metrics = json.loads(Path(result.raw_metrics_ref).read_text())
    assert raw_metrics["complete"] is True
    assert raw_metrics["total_pairs"] == 4
    assert raw_metrics["attempted_pairs"] == 4
    assert raw_metrics["valid_pairs"] == 4
    assert raw_metrics["failed_pairs"] == 0
    assert all(
        pair["decisive_metric"] in (None, "tie")
        for pair in raw_metrics["pairs"]
    )


def test_cvrp_protocol_algorithm_blueprint_metrics_preserve_required_runtime_fields(
    tmp_path: Path,
) -> None:
    candidate_ws = tmp_path / "cvrp_candidate"
    shutil.copytree(CVRP_DIR, candidate_ws)
    (candidate_ws / "policies" / "algorithm_blueprint.py").write_text(
        "\n".join(
            [
                "def algorithm_plan(instance, time_limit_sec):",
                "    return {",
                "        'enabled': True,",
                "        'construction_methods': ['nearest_neighbor', 'demand_descending'],",
                "        'construction_keep_top_k': 2,",
                "        'construction_bias': 0.0,",
                "        'baseline_time_fraction': 0.75,",
                "        'operator_round_limit': 0,",
                "        'post_baseline_operators_enabled': False,",
                "        'local_search': {",
                "            'enabled_components': ['intra_route_2opt'],",
                "            'rounds': 1,",
                "            'top_k': 16,",
                "        },",
                "        'restart': {'enabled': False, 'stagnation_rounds': 0},",
                "    }",
                "",
            ]
        ),
        encoding="utf-8",
    )
    proto, _ = _make_protocol(tmp_path)

    result = proto.run_experiment(
        ExperimentStage.SCREENING,
        candidate_ws=str(candidate_ws),
        champion_ws=str(CVRP_DIR),
        hypothesis_action="modify",
        selected_surface="algorithm_blueprint",
    )

    assert result.selected_surface == "algorithm_blueprint"
    surface_summary = result.candidate_surface_runtime_summary
    assert surface_summary["selected_surface"] == "algorithm_blueprint"
    assert surface_summary["candidate_pairs"] == 4
    assert surface_summary["fields"]["algorithm_plan"]["present"] == 4
    assert surface_summary["fields"]["algorithm_phases_executed"]["present"] == 4
    assert surface_summary["fields"]["algorithm_blueprint_errors"]["failed"] == 0

    raw_metrics = json.loads(Path(result.raw_metrics_ref).read_text())
    assert raw_metrics["candidate_surface_runtime_summary"] == surface_summary
    pair_runtime = raw_metrics["pairs"][0]["candidate_runtime"]
    assert pair_runtime["algorithm_blueprint_active"] is True
    assert pair_runtime["algorithm_plan"]["enabled"] is True
    assert pair_runtime["algorithm_baseline_time_fraction"] == 0.75
    assert pair_runtime["algorithm_phases_executed"]
    assert pair_runtime["algorithm_local_search_components"] == ["intra_route_2opt"]


def test_cvrp_protocol_solver_design_metrics_preserve_route_pool_runtime_fields(
    tmp_path: Path,
) -> None:
    candidate_ws = tmp_path / "cvrp_candidate"
    shutil.copytree(CVRP_DIR, candidate_ws)
    (candidate_ws / "policies" / "main_search_strategy.py").write_text(
        "\n".join(
            [
                "def main_search_plan(instance, time_limit_sec):",
                "    return {",
                "        'enabled': True,",
                "        'problem_adaptation': {",
                "            'strategy_family': 'baseline_intensification',",
                "            'instance_profile': {'customer_count': instance.customer_count},",
                "            'phase_objective': 'phase_best_distance',",
                "            'component_roles': {'route_pool_recombination': 'primary'},",
                "            'fallback_order': ['route_pool_recombination'],",
                "            'evidence_targets': ['main_search_route_pool_sample_count', 'main_search_route_pool_size', 'main_search_route_pool_branch_calls', 'main_search_route_pool_recombined_routes'],",
                "        },",
                "        'construction': {'methods': ['nearest_neighbor'], 'keep_top_k': 1, 'bias': 0.0},",
                "        'baseline': {'time_fraction': 0.2, 'params': {}},",
                "        'improvement': {'enabled_components': ['route_pool_recombination'], 'rounds': 1, 'top_k': 16},",
                "        'acceptance': {'min_distance_improvement': 0.0},",
                "        'restart': {'enabled': False, 'stagnation_rounds': 0, 'max_restarts': 0},",
                "        'perturbation': {'enabled': False, 'strength': 1, 'max_perturbations': 0},",
                "        'post_baseline_operators_enabled': False,",
                "        'operator_round_limit': 0,",
                "    }",
                "",
            ]
        ),
        encoding="utf-8",
    )
    proto, _ = _make_protocol(tmp_path)

    result = proto.run_experiment(
        ExperimentStage.SCREENING,
        candidate_ws=str(candidate_ws),
        champion_ws=str(CVRP_DIR),
        hypothesis_action="modify",
        selected_surface="solver_design",
    )

    surface_summary = result.candidate_surface_runtime_summary
    assert surface_summary["selected_surface"] == "solver_design"
    assert (
        surface_summary["fields"]["main_search_route_pool_sample_count"]["present"]
        == 4
    )
    assert surface_summary["fields"]["main_search_route_pool_size"]["present"] == 4
    assert (
        surface_summary["fields"]["main_search_route_pool_branch_calls"]["present"]
        == 4
    )
    assert (
        surface_summary["fields"]["main_search_route_pool_recombined_routes"][
            "present"
        ]
        == 4
    )

    raw_metrics = json.loads(Path(result.raw_metrics_ref).read_text())
    pair_runtime = raw_metrics["pairs"][0]["candidate_runtime"]
    assert pair_runtime["main_search_components"] == ["route_pool_recombination"]
    assert "main_search_route_pool_sample_count" in pair_runtime
    assert "main_search_route_pool_size" in pair_runtime
    assert "main_search_route_pool_branch_calls" in pair_runtime
    assert "main_search_route_pool_recombined_routes" in pair_runtime


def test_cvrp_campaign_manager_reaches_real_screening_with_mock_llm(tmp_path: Path) -> None:
    proto, spec_v1 = _make_protocol(tmp_path)
    bridge = bridge_problem_spec_v1(spec_v1)
    adapter = load_problem_adapter(spec_v1)
    runner = proto.runner
    problem_spec = bridge.problem_spec
    champion = ChampionState(
        version=1,
        operator_pool={},
        solver_config_hash="cvrp-smoke",
        code_snapshot_path=str(CVRP_DIR),
        code_snapshot_hash="cvrp-baseline",
    )
    llm = MockLLMClient(
        hypothesis_response={
            "hypothesis_text": "Add a bounded no-op route-local operator for smoke validation.",
            "change_locus": "route_local",
            "action": "create_new",
            "target_file": None,
            "predicted_direction": "exploratory",
            "target_weakness": "campaign wiring",
            "expected_effect": "No behavioral change; validates CVRP campaign plumbing.",
            "suggested_weight": 0.1,
            "target_objectives": ["total_distance"],
            "protected_objectives": ["fleet_violation"],
            "objective_tradeoff_policy": "preserve fleet_violation before distance",
            "no_op_condition": "always returns the original solution",
            "risk_to_higher_priority": "none for no-op",
        },
        patch_response={
            "file_path": "operators/noop_smoke.py",
            "action": "create",
            "code_content": (
                "class NoOpSmoke:\n"
                "    def execute(self, solution, instance, rng):\n"
                "        return solution\n"
            ),
            "test_hint": None,
        },
    )
    gate = VerificationGate(
        problem_spec=problem_spec,
        runner=runner,
        metrics_dir=str(tmp_path / "metrics"),
        adapter=adapter,
        strict_runtime_checks=True,
        require_adapter_for_runtime=True,
        operator_execute_signature=bridge.operator_execute_signature,
    )
    campaign = CampaignManager(
        problem_spec=problem_spec,
        protocol_config=ProtocolConfig.from_yaml(CVRP_DIR / "protocol.yaml"),
        split_manifest=SplitManifest.from_yaml(CVRP_DIR / "split_manifest.yaml"),
        seed_ledger=SeedLedgerConfig.from_yaml(CVRP_DIR / "seed_ledger.yaml"),
        llm_client=llm,
        champion=champion,
        campaign_dir=str(tmp_path / "campaign"),
        verification_gate=gate,
        experiment_protocol=proto,
        adapter=adapter,
        operator_execute_signature=bridge.operator_execute_signature,
        termination_config=TerminationConfig(max_experiments=5, stagnation_limit=5),
        force_surface="route_local",
    )

    result = campaign.run_one_step()

    assert result.action == "create_branch"
    assert campaign._n_experiments == 1
    assert len(campaign._step_history) == 1
    step = campaign._step_history[0]
    assert step.protocol_result is not None
    assert step.protocol_result.stage == ExperimentStage.SCREENING
    assert step.protocol_result.stats.n_cases == 2
    assert step.protocol_result.case_ids == ("data/tiny_5.json", "data/tiny_6.json")
    assert step.protocol_result.raw_metrics_ref

    raw_metrics = json.loads(Path(step.protocol_result.raw_metrics_ref).read_text())
    assert raw_metrics["complete"] is True
    assert raw_metrics["failed_pairs"] == 0
    assert raw_metrics["valid_pairs"] == 4
