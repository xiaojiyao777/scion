"""Run the controlled CVRP end-to-end smoke experiment.

This is a local, deterministic v0.4 experiment path:

screening -> validation -> frozen -> promote -> final evidence refs

It uses checked-in synthetic controlled CVRP fixtures and MockLLMClient. It does
not read raw CVRPLIB benchmark files and does not require an API key.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from scion.config.problem import ProtocolConfig, SeedLedgerConfig, SplitManifest
from scion.core.campaign import CampaignManager
from scion.core.models import ChampionState
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


SCION_ROOT = Path(__file__).resolve().parent
CVRP_DIR = SCION_ROOT / "scion" / "problems" / "cvrp"
CONTROLLED_DIR = CVRP_DIR / "controlled"
CONTROLLED_CANARY = "controlled/data/synthetic_controlled_canary_5.vrp"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_default_output_dir(),
        help="Directory for campaign, metrics, and final evidence artifacts.",
    )
    args = parser.parse_args()

    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    campaign = _make_campaign(output_dir)

    step_results = []
    for _ in range(3):
        result = campaign.run_one_step()
        step_results.append(_step_result_summary(result))
        if result.decision and getattr(result.decision, "value", result.decision) == "promote":
            break

    champion_snapshot = Path(campaign._champion.code_snapshot_path)
    package_result = _write_final_evidence(
        output_dir=output_dir,
        campaign=campaign,
        champion_snapshot=champion_snapshot,
    )
    refs = attach_final_evidence_package(campaign._evidence_recorder, package_result)
    campaign._write_campaign_summary()

    final_quality = package_result.package.final_quality
    summary = {
        "experiment": "cvrp-controlled-e2e",
        "campaign_id": campaign._campaign_id,
        "output_dir": str(output_dir),
        "campaign_dir": str(output_dir / "campaign"),
        "champion_version": campaign._champion.version,
        "champion_snapshot": str(champion_snapshot),
        "steps": step_results,
        "final_quality": final_quality,
        "final_evidence_refs": refs,
        "artifacts": {
            key: str(path) for key, path in package_result.artifacts.items()
        },
    }
    result_path = output_dir / "e2e_result.json"
    result_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


def _default_output_dir() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path.home() / "research" / "scion-experiments" / f"v04-cvrp-controlled-e2e-{stamp}"


def _problem_v1() -> ProblemSpecV1:
    with (CVRP_DIR / "problem-v1.yaml").open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    data["root_dir"] = str(CVRP_DIR)
    data["canary_case_path"] = CONTROLLED_CANARY
    return ProblemSpecV1(**data)


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
            "target_runtime_effect": "neutral",
            "complexity_claim": "single pass over existing routes and customer ids",
            "runtime_budget_strategy": "no nested route-pair scan; bounded controlled fixture rewrite only",
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
                "            return solution.__class__(routes=((1, 2, 3, 4),))\n"
                "        if customers == {1, 2, 3, 4, 5}:\n"
                "            return solution.__class__(routes=((1, 2, 3, 4, 5),))\n"
                "        return solution\n"
            ),
            "test_hint": None,
        },
    )


def _make_campaign(output_dir: Path) -> CampaignManager:
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
        metrics_dir=str(output_dir / "metrics"),
        metric_specs=tuple(spec_v1.objectives),
        objective_policy=spec_v1.objective_policy,
        require_metric_specs=True,
    )

    bridge = bridge_problem_spec_v1(spec_v1)
    adapter = load_problem_adapter(spec_v1)
    champion = ChampionState(
        version=1,
        operator_pool={},
        solver_config_hash="cvrp-controlled-e2e",
        code_snapshot_path=str(CVRP_DIR),
        code_snapshot_hash="cvrp-controlled-baseline",
    )
    gate = VerificationGate(
        problem_spec=bridge.problem_spec,
        runner=protocol.runner,
        metrics_dir=str(output_dir / "metrics"),
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
        campaign_dir=str(output_dir / "campaign"),
        verification_gate=gate,
        experiment_protocol=protocol,
        adapter=adapter,
        operator_execute_signature=bridge.operator_execute_signature,
        termination_config=TerminationConfig(max_experiments=5, stagnation_limit=5),
    )


def _write_final_evidence(
    *,
    output_dir: Path,
    campaign: CampaignManager,
    champion_snapshot: Path,
) -> Any:
    spec_v1 = _problem_v1()
    adapter = load_problem_adapter(spec_v1)
    runner = LocalSubprocessRunner(ResourceLimits(timeout_sec=10, memory_mb=1024))
    final_manifest = load_cvrp_case_manifest(CONTROLLED_DIR / "manifests" / "final.json")
    return write_cvrp_manifest_final_evidence_package(
        final_manifest,
        config=CvrpManifestEvaluationConfig(
            campaign_id=campaign._campaign_id,
            baseline_workspace=CVRP_DIR,
            candidate_workspace=champion_snapshot,
            time_limit_sec=2,
            seeds=(0, 1),
            baseline_label="controlled-baseline",
            candidate_label=f"controlled-promoted-v{campaign._champion.version}",
            baseline_registry_path=CVRP_DIR / "registry.yaml",
            candidate_registry_path=champion_snapshot / "registry.yaml",
            output_dir=output_dir / "final_evidence",
        ),
        runner=runner,
        adapter=adapter,
    )


def _step_result_summary(result: Any) -> dict[str, Any]:
    decision = result.decision
    return {
        "action": result.action,
        "branch_id": result.branch_id,
        "decision": getattr(decision, "value", decision),
        "reason": result.reason,
        "stopped": result.stopped,
    }


if __name__ == "__main__":
    main()
