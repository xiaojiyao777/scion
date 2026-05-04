"""Controlled CVRP campaign smoke using synthetic checked-in fixtures."""
from __future__ import annotations

import json
from pathlib import Path

import yaml

from scion.config.problem import ProtocolConfig, SeedLedgerConfig, SplitManifest
from scion.core.campaign import CampaignManager
from scion.core.models import ChampionState, Decision, ExperimentStage
from scion.core.termination import TerminationConfig
from scion.evidence import (
    CvrpManifestEvaluationConfig,
    attach_final_evidence_package,
    load_cvrp_case_manifest,
    write_cvrp_manifest_final_evidence_package,
)
from scion.problem.bridge import bridge_problem_spec_v1
from scion.problem.loader import load_problem_adapter
from scion.problem.spec import ProblemSpecV1
from scion.protocol.experiment import ExperimentProtocol, SeedLedger, SplitManager
from scion.proposal.mock_client import MockLLMClient
from scion.runtime.runner import ResourceLimits
from scion.runtime.subprocess_runner import LocalSubprocessRunner
from scion.verification.gate import VerificationGate


CVRP_DIR = Path(__file__).resolve().parents[1] / "problems" / "cvrp"
CONTROLLED_DIR = CVRP_DIR / "controlled"
CONTROLLED_CANARY = "controlled/data/synthetic_controlled_canary_5.vrp"


def _problem_v1() -> ProblemSpecV1:
    with open(CVRP_DIR / "problem-v1.yaml", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    data["root_dir"] = str(CVRP_DIR)
    data["canary_case_path"] = CONTROLLED_CANARY
    return ProblemSpecV1(**data)


def _load_controlled_runtime(
    tmp_path: Path,
) -> tuple[ExperimentProtocol, ProblemSpecV1, ProtocolConfig, SplitManifest, SeedLedgerConfig]:
    spec_v1 = _problem_v1()
    protocol_config = ProtocolConfig.from_yaml(CONTROLLED_DIR / "protocol.yaml")
    split_manifest = SplitManifest.from_yaml(CONTROLLED_DIR / "split_manifest.yaml")
    seed_ledger = SeedLedgerConfig.from_yaml(CONTROLLED_DIR / "seed_ledger.yaml")
    runner = LocalSubprocessRunner(ResourceLimits(timeout_sec=10, memory_mb=1024))
    protocol = ExperimentProtocol(
        protocol_config=protocol_config,
        split_manager=SplitManager(split_manifest),
        seed_ledger=SeedLedger(seed_ledger),
        runner=runner,
        time_limit_sec=1,
        metrics_dir=str(tmp_path / "metrics"),
        metric_specs=tuple(spec_v1.objectives),
        objective_policy=spec_v1.objective_policy,
        require_metric_specs=True,
    )
    return protocol, spec_v1, protocol_config, split_manifest, seed_ledger


def _mock_llm() -> MockLLMClient:
    return MockLLMClient(
        hypothesis_response={
            "hypothesis_text": "Add a bounded controlled route improver for synthetic CVRP smoke.",
            "change_locus": "route_local",
            "action": "create_new",
            "target_file": None,
            "predicted_direction": "exploratory",
            "target_weakness": "controlled CVRP route ordering",
            "expected_effect": "Improve only the checked-in synthetic controlled route shapes.",
            "suggested_weight": 0.1,
            "target_objectives": ["total_distance"],
            "protected_objectives": ["fleet_violation"],
            "objective_tradeoff_policy": "preserve fleet_violation before distance",
            "no_op_condition": "unrecognized controlled customer sets return the original solution",
            "risk_to_higher_priority": "none for route-count preserving controlled changes",
        },
        patch_response={
            "file_path": "operators/controlled_route_improver.py",
            "action": "create",
            "code_content": (
                "class ControlledRouteImprover:\n"
                "    def execute(self, solution, instance, rng):\n"
                "        customers = set()\n"
                "        for route in solution.routes:\n"
                "            customers.update(route)\n"
                "        if customers == {1, 2, 3, 4}:\n"
                "            if instance.route_load((1, 2, 3, 4)) > instance.capacity:\n"
                "                return solution\n"
                "            return solution.__class__(routes=((1, 2, 3, 4),))\n"
                "        if customers == {1, 2, 3, 4, 5}:\n"
                "            if instance.route_load((1, 2, 3, 4, 5)) > instance.capacity:\n"
                "                return solution\n"
                "            return solution.__class__(routes=((1, 2, 3, 4, 5),))\n"
                "        return solution\n"
            ),
            "test_hint": None,
        },
    )


def _make_campaign(tmp_path: Path) -> CampaignManager:
    proto, spec_v1, protocol_config, split_manifest, seed_ledger = _load_controlled_runtime(
        tmp_path
    )
    bridge = bridge_problem_spec_v1(spec_v1)
    adapter = load_problem_adapter(spec_v1)
    champion = ChampionState(
        version=1,
        operator_pool={},
        solver_config_hash="cvrp-controlled-smoke",
        code_snapshot_path=str(CVRP_DIR),
        code_snapshot_hash="cvrp-controlled-baseline",
    )
    gate = VerificationGate(
        problem_spec=bridge.problem_spec,
        runner=proto.runner,
        metrics_dir=str(tmp_path / "metrics"),
        adapter=adapter,
        strict_runtime_checks=True,
        require_adapter_for_runtime=True,
        operator_execute_signature=bridge.operator_execute_signature,
    )
    return CampaignManager(
        problem_spec=bridge.problem_spec,
        protocol_config=protocol_config,
        split_manifest=split_manifest,
        seed_ledger=seed_ledger,
        llm_client=_mock_llm(),
        champion=champion,
        campaign_dir=str(tmp_path / "campaign"),
        verification_gate=gate,
        experiment_protocol=proto,
        adapter=adapter,
        operator_execute_signature=bridge.operator_execute_signature,
        termination_config=TerminationConfig(max_experiments=5, stagnation_limit=5),
    )


def test_controlled_protocol_split_seed_load_and_use_vrp_paths() -> None:
    protocol = ProtocolConfig.from_yaml(CONTROLLED_DIR / "protocol.yaml")
    split_manifest = SplitManifest.from_yaml(CONTROLLED_DIR / "split_manifest.yaml")
    seed_ledger = SeedLedgerConfig.from_yaml(CONTROLLED_DIR / "seed_ledger.yaml")

    assert protocol.version == "0.4-cvrp-controlled-smoke"
    assert split_manifest.screening == [
        "controlled/data/synthetic_screening_micro_5.vrp",
        "controlled/data/synthetic_screening_split_6.vrp",
    ]
    assert split_manifest.canary == [CONTROLLED_CANARY]
    assert seed_ledger.screening == [0]
    assert seed_ledger.canary == [0]
    assert all("vrp/cvrplib" not in path.lower() for path in split_manifest.screening)


def test_controlled_screening_runs_complete_on_synthetic_vrp_cases(
    tmp_path: Path,
) -> None:
    proto, _, _, split_manifest, seed_ledger = _load_controlled_runtime(tmp_path)

    result = proto.run_experiment(
        ExperimentStage.SCREENING,
        candidate_ws=str(CVRP_DIR),
        champion_ws=str(CVRP_DIR),
        hypothesis_action="create_new",
    )

    assert result.stage == ExperimentStage.SCREENING
    assert result.case_ids == tuple(split_manifest.screening)
    assert result.seed_set == tuple(seed_ledger.screening)
    assert result.stats.n_cases == 2
    assert result.stats.ties == 2
    assert result.raw_metrics_ref

    raw_metrics = json.loads(Path(result.raw_metrics_ref).read_text(encoding="utf-8"))
    assert raw_metrics["complete"] is True
    assert raw_metrics["valid_pairs"] == 2
    assert raw_metrics["failed_pairs"] == 0


def test_controlled_campaign_one_step_then_manual_final_evidence_refs(
    tmp_path: Path,
) -> None:
    campaign = _make_campaign(tmp_path)

    result = campaign.run_one_step()

    assert result.action == "create_branch"
    assert result.decision == Decision.QUEUE_VALIDATE
    assert campaign._n_experiments == 1
    assert len(campaign._step_history) == 1
    step = campaign._step_history[0]
    assert step.protocol_result is not None
    assert step.protocol_result.stage == ExperimentStage.SCREENING
    assert step.protocol_result.case_ids == (
        "controlled/data/synthetic_screening_micro_5.vrp",
        "controlled/data/synthetic_screening_split_6.vrp",
    )
    assert step.protocol_result.seed_set == (0,)

    spec_v1 = _problem_v1()
    adapter = load_problem_adapter(spec_v1)
    runner = LocalSubprocessRunner(ResourceLimits(timeout_sec=10, memory_mb=1024))
    final_manifest = load_cvrp_case_manifest(
        CONTROLLED_DIR / "manifests" / "final.json"
    )
    package_result = write_cvrp_manifest_final_evidence_package(
        final_manifest,
        config=CvrpManifestEvaluationConfig(
            campaign_id=campaign._campaign_id,
            baseline_workspace=CVRP_DIR,
            candidate_workspace=CVRP_DIR,
            time_limit_sec=2,
            seeds=(0, 1),
            baseline_label="controlled-baseline",
            candidate_label="controlled-candidate",
            output_dir=tmp_path / "final_evidence",
        ),
        runner=runner,
        adapter=adapter,
    )
    refs = attach_final_evidence_package(
        campaign._evidence_recorder,
        package_result,
    )
    campaign._write_campaign_summary()

    summary_path = Path(campaign._campaign_dir) / "campaign_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert refs == {"final_quality": summary["final_evidence_refs"]["final_quality"]}
    assert summary["final_evidence_refs"]["final_quality"]["n_cases"] == 4
    assert summary["final_evidence_refs"]["final_quality"]["problem_id"] == "cvrp"
    assert all(path.exists() for path in package_result.artifacts.values())
    assert "final_evidence_refs" not in summary["steps"][0]


def test_controlled_campaign_promotes_then_attaches_better_final_evidence(
    tmp_path: Path,
) -> None:
    campaign = _make_campaign(tmp_path)

    first = campaign.run_one_step()
    second = campaign.run_one_step()
    third = campaign.run_one_step()

    assert first.decision == Decision.QUEUE_VALIDATE
    assert second.action == "validate"
    assert second.decision == Decision.QUEUE_FROZEN
    assert third.action == "frozen"
    assert third.decision == Decision.PROMOTE
    assert campaign._champion.version == 2

    stages = [
        step.protocol_result.stage
        for step in campaign._step_history
        if step.protocol_result is not None
    ]
    assert stages == [
        ExperimentStage.SCREENING,
        ExperimentStage.VALIDATION,
        ExperimentStage.FROZEN,
    ]

    champion_snapshot = Path(campaign._champion.code_snapshot_path)
    assert (champion_snapshot / "operators" / "controlled_route_improver.py").is_file()
    registry_text = (champion_snapshot / "registry.yaml").read_text(encoding="utf-8")
    assert "controlled_route_improver" in registry_text
    assert "ControlledRouteImprover" in registry_text

    spec_v1 = _problem_v1()
    adapter = load_problem_adapter(spec_v1)
    runner = LocalSubprocessRunner(ResourceLimits(timeout_sec=10, memory_mb=1024))
    final_manifest = load_cvrp_case_manifest(
        CONTROLLED_DIR / "manifests" / "final.json"
    )
    package_result = write_cvrp_manifest_final_evidence_package(
        final_manifest,
        config=CvrpManifestEvaluationConfig(
            campaign_id=campaign._campaign_id,
            baseline_workspace=CVRP_DIR,
            candidate_workspace=champion_snapshot,
            time_limit_sec=2,
            seeds=(0, 1),
            baseline_label="controlled-baseline",
            candidate_label="controlled-promoted-v2",
            baseline_registry_path=CVRP_DIR / "registry.yaml",
            candidate_registry_path=champion_snapshot / "registry.yaml",
            output_dir=tmp_path / "final_evidence_promoted",
        ),
        runner=runner,
        adapter=adapter,
    )

    assert package_result.package.final_quality["n_cases"] == 4
    assert package_result.package.final_quality["better_vs_baseline"] == 4
    assert package_result.package.final_quality["worse_vs_baseline"] == 0
    assert all(
        row["comparison"] == "better"
        for row in package_result.package.per_case_quality
    )

    refs = attach_final_evidence_package(
        campaign._evidence_recorder,
        package_result,
    )
    campaign._write_campaign_summary()

    summary = json.loads(
        (Path(campaign._campaign_dir) / "campaign_summary.json").read_text(
            encoding="utf-8"
        )
    )
    assert refs == {"final_quality": summary["final_evidence_refs"]["final_quality"]}
    assert summary["final_evidence_refs"]["final_quality"]["n_cases"] == 4
    assert summary["final_evidence_refs"]["final_quality"]["candidate_label"] == (
        "controlled-promoted-v2"
    )
    assert "final_evidence_refs" not in summary["steps"][0]
    assert "final_evidence_refs" not in summary["steps"][1]
    assert "final_evidence_refs" not in summary["steps"][2]
