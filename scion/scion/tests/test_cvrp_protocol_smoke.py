"""CVRP protocol smoke tests using tiny synthetic fixtures only."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import yaml

from scion.config.problem import (
    ProblemSpec,
    ProtocolConfig,
    SplitManifest,
    SeedLedgerConfig,
)
from scion.core.campaign import CampaignManager
from scion.core.models import ChampionState
from scion.core.models import ExperimentStage
from scion.problem.bridge import bridge_problem_spec_v1, load_problem_spec_v1_from_yaml
from scion.problem.loader import load_problem_adapter
from scion.problem.spec import ProblemSpecV1
from scion.protocol.experiment import ExperimentProtocol, SeedLedger, SplitManager
from scion.proposal.mock_client import MockLLMClient
from scion.runtime.runner import ResourceLimits
from scion.runtime.subprocess_runner import LocalSubprocessRunner
from scion.verification.gate import VerificationGate


CVRP_DIR = Path(__file__).resolve().parents[1] / "problems" / "cvrp"


def _baseline_algorithm_solve_patch(new_solve: str) -> dict:
    source = (CVRP_DIR / "policies" / "baseline_algorithm.py").read_text(
        encoding="utf-8"
    )
    old_solve = source[source.index("def solve(") :]
    return {
        "file_path": "policies/baseline_algorithm.py",
        "action": "modify",
        "edit_intent": "exact_replace",
        "old_string": old_solve,
        "new_string": new_solve if new_solve.endswith("\n") else new_solve + "\n",
        "replace_all": False,
        "test_hint": None,
    }


def _problem_v1() -> ProblemSpecV1:
    with open(CVRP_DIR / "problem-v1.yaml", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    data["root_dir"] = str(CVRP_DIR)
    return ProblemSpecV1(**data)


def _make_protocol(tmp_path: Path) -> tuple[ExperimentProtocol, ProblemSpecV1]:
    spec_v1 = _problem_v1()
    bridge = bridge_problem_spec_v1(spec_v1)
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
            metric_specs=bridge.metric_specs,
            objective_policy=bridge.objective_policy,
            require_metric_specs=True,
            problem_spec=bridge.problem_spec,
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


def test_cvrp_smoke_problem_specs_keep_parameter_search_disabled() -> None:
    legacy = ProblemSpec.from_yaml(CVRP_DIR / "problem.yaml")
    spec_v1 = load_problem_spec_v1_from_yaml(CVRP_DIR / "problem-v1.yaml")

    assert legacy.parameter_search.enabled is False
    assert spec_v1.parameter_search.enabled is False


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


def test_cvrp_screening_keeps_static_case_coverage_when_all_solver_pairs_fail(
    tmp_path: Path,
) -> None:
    candidate_ws = tmp_path / "failing_candidate"
    shutil.copytree(CVRP_DIR, candidate_ws)
    (candidate_ws / "policies" / "baseline_algorithm.py").write_text(
        "def solve(instance, rng, time_limit_sec, context):\n"
        "    raise RuntimeError('synthetic candidate failure')\n",
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

    assert result.stats.valid_pairs == 0
    assert result.stats.candidate_failed_pairs == 4
    evidence = result.mechanism_evidence["evidence"]
    assert evidence["coverage"]["provider_inputs"] == 2
    assert evidence["coverage"]["runtime_pairs"] == 0
    assert evidence["instance_feasibility"]["coverage"] == {
        "requested_cases": 2,
        "observed_cases": 0,
        "unavailable_cases": 2,
        "reference_route_cases": 0,
        "reference_route_source_counts": {
            "allowed_routes": 0,
            "benchmark_reference_routes": 0,
        },
    }
    assert str(candidate_ws) not in json.dumps(evidence, sort_keys=True)


def test_cvrp_protocol_solver_design_metrics_preserve_required_runtime_fields(
    tmp_path: Path,
) -> None:
    candidate_ws = tmp_path / "cvrp_candidate"
    shutil.copytree(CVRP_DIR, candidate_ws)
    (candidate_ws / "policies" / "baseline_algorithm.py").write_text(
        "\n".join(
            [
                "def solve(instance, rng, time_limit_sec, context):",
                "    solution = context.nearest_neighbor()",
                "    context.record_phase('candidate_construct', 1)",
                "    context.record_iteration('candidate_probe', 1)",
                "    context.record_move('candidate_probe', attempted=1, accepted=0)",
                "    context.set_stop_reason('candidate_completed')",
                "    return solution",
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

    assert result.selected_surface == "solver_design"
    surface_summary = result.candidate_surface_runtime_summary
    assert surface_summary["selected_surface"] == "solver_design"
    assert surface_summary["candidate_pairs"] == 4
    assert surface_summary["fields"]["solver_algorithm_loaded"]["present"] == 4
    assert surface_summary["fields"]["solver_algorithm_active"]["failed"] == 0
    assert surface_summary["fields"]["solver_algorithm_errors"]["failed"] == 0
    assert surface_summary["fields"]["solver_algorithm_search_iterations"]["present"] == 4
    assert surface_summary["fields"]["solver_algorithm_move_attempts"]["present"] == 4

    raw_metrics = json.loads(Path(result.raw_metrics_ref).read_text())
    assert raw_metrics["candidate_surface_runtime_summary"] == surface_summary
    pair_runtime = raw_metrics["pairs"][0]["candidate_runtime"]
    assert pair_runtime["solver_algorithm_path"] == "policies/baseline_algorithm.py"
    assert pair_runtime["solver_algorithm_active"] is True
    assert pair_runtime["solver_algorithm_stop_reason"] == "candidate_completed"
    assert pair_runtime["solver_algorithm_search_iterations"] == 1
    assert pair_runtime["solver_algorithm_move_attempts"] == 1
    assert "candidate_construct" in pair_runtime["solver_algorithm_phase_runtime_ms"]
    evidence = result.mechanism_evidence["evidence"]
    assert evidence["schema_version"] == (
        "scion.cvrp.proposal_mechanism_evidence.v1"
    )
    assert evidence["instance_feasibility"]["coverage"] == {
        "requested_cases": 2,
        "observed_cases": 0,
        "unavailable_cases": 2,
        "reference_route_cases": 0,
        "reference_route_source_counts": {
            "allowed_routes": 0,
            "benchmark_reference_routes": 0,
        },
    }
    rendered_evidence = json.dumps(evidence, sort_keys=True)
    assert str(candidate_ws) not in rendered_evidence
    assert "case_path" not in rendered_evidence


def test_cvrp_protocol_solver_design_metrics_preserve_phase_runtime_fields(
    tmp_path: Path,
) -> None:
    candidate_ws = tmp_path / "cvrp_candidate"
    shutil.copytree(CVRP_DIR, candidate_ws)
    (candidate_ws / "policies" / "baseline_algorithm.py").write_text(
        "\n".join(
            [
                "def solve(instance, rng, time_limit_sec, context):",
                "    solution = context.nearest_neighbor()",
                "    context.record_phase('construction', 1)",
                "    context.record_iteration('route_pool_recombination', 2)",
                "    context.record_move('route_pool_recombination', attempted=3, accepted=1, delta=0.0)",
                "    context.record_solution_progress(",
                "        initial_route_count=3,",
                "        final_route_count=2,",
                "        initial_total_distance=12.0,",
                "        final_total_distance=10.5,",
                "        budget_hit=False,",
                "    )",
                "    context.set_stop_reason('phase_probe_completed')",
                "    return solution",
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
    assert surface_summary["fields"]["solver_algorithm_phase_runtime_ms"]["present"] == 4
    assert surface_summary["fields"]["solver_algorithm_accepted_moves"]["present"] == 4
    assert surface_summary["fields"]["solver_algorithm_actionability_summary"][
        "present"
    ] == 4

    raw_metrics = json.loads(Path(result.raw_metrics_ref).read_text())
    pair_runtime = raw_metrics["pairs"][0]["candidate_runtime"]
    assert pair_runtime["solver_algorithm_stop_reason"] == "phase_probe_completed"
    assert pair_runtime["solver_algorithm_accepted_moves"] == 1
    assert pair_runtime["solver_algorithm_neutral_accepted_moves"] == 1
    assert pair_runtime["solver_algorithm_search_iterations"] == 2
    assert pair_runtime["solver_algorithm_move_attempts"] == 3
    assert pair_runtime["solver_algorithm_phase_move_attempts"][
        "route_pool_recombination"
    ] == 3
    assert pair_runtime["solver_algorithm_phase_accepted_moves"][
        "route_pool_recombination"
    ] == 1
    summary = pair_runtime["solver_algorithm_actionability_summary"]
    assert summary["accepted_no_measurable_objective_effect"] is True
    assert summary["candidate_emitted_no_measurable_objective_effect"] is True
    assert summary["route_count_delta_final_minus_initial"] == -1
    assert summary["total_distance_improvement_from_initial"] == 1.5
    assert summary["phases"]["route_pool_recombination"]["status"] == (
        "accepted_no_measurable_objective_effect"
    )


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
            "hypothesis_text": "Add a solver-design smoke path for plumbing validation.",
            "change_locus": "solver_design",
            "action": "modify",
            "target_file": "policies/baseline_algorithm.py",
            "predicted_direction": "exploratory",
            "target_weakness": "campaign wiring",
            "expected_effect": "No behavioral change; validates CVRP campaign plumbing.",
            "suggested_weight": 0.1,
        },
        patch_response=_baseline_algorithm_solve_patch(
            (
                "def solve(instance, rng, time_limit_sec, context):\n"
                "    solution = context.nearest_neighbor()\n"
                "    context.record_iteration('smoke_probe', 1)\n"
                "    context.record_move('smoke_probe', attempted=1, accepted=0)\n"
                "    return solution\n"
            )
        ),
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
    )

    result = campaign.run_one_step()
    if result.action == "create_branch" and not result.formal_protocol_evaluated:
        result = campaign.run_one_step()

    assert result.action in {
        "create_branch",
        "explore",
        "validate",
        "promote",
        "abandon",
        "noop",
    }
    assert result.formal_protocol_evaluated is True
    assert campaign._n_experiments >= 1
    assert campaign._step_history
    step = next(
        item
        for item in campaign._step_history
        if item.protocol_result is not None
        and item.protocol_result.stage == ExperimentStage.SCREENING
    )
    assert step.protocol_result is not None
    assert step.protocol_result.stage == ExperimentStage.SCREENING
    assert step.protocol_result.stats.n_cases == 2
    assert step.protocol_result.case_ids == ("data/tiny_5.json", "data/tiny_6.json")
    assert step.protocol_result.raw_metrics_ref

    raw_metrics = json.loads(Path(step.protocol_result.raw_metrics_ref).read_text())
    assert raw_metrics["complete"] is True
    assert raw_metrics["failed_pairs"] == 0
    assert raw_metrics["valid_pairs"] == 4
