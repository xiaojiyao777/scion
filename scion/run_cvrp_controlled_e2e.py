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
from scion.core.telemetry_validation import screened_experiment_effective
from scion.core.termination import TerminationConfig
from scion.evidence import attach_final_evidence_package
from scion.problems.cvrp.evidence import (
    CvrpManifestEvaluationConfig,
    load_cvrp_case_manifest,
    write_cvrp_manifest_final_evidence_package,
)
from scion.problem.bridge import bridge_problem_spec_v1
from scion.problem.loader import load_problem_adapter
from scion.problem.spec import ProblemSpecV1
from scion.protocol.experiment import ExperimentProtocol, SeedLedger, SplitManager
from scion.proposal.edit_protocol.normalization import source_digest_for_content
from scion.proposal.mock_client import MockLLMClient
from scion.runtime.runner import ResourceLimits
from scion.runtime.subprocess_runner import LocalSubprocessRunner
from scion.verification.gate import VerificationGate


SCION_ROOT = Path(__file__).resolve().parent
CVRP_DIR = SCION_ROOT / "scion" / "problems" / "cvrp"
CONTROLLED_DIR = CVRP_DIR / "controlled"
VRP_DIR = CVRP_DIR.parents[3] / "vrp"
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
    _validate_smoke_success(
        campaign=campaign,
        final_quality=final_quality,
        output_dir=output_dir,
    )
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


def _baseline_algorithm_solve_patch(new_solve: str) -> dict[str, Any]:
    source = (CVRP_DIR / "policies" / "baseline_algorithm.py").read_text(
        encoding="utf-8"
    )
    old_solve = source[source.index("def solve(") :]
    return {
        "file_path": "policies/baseline_algorithm.py",
        "action": "modify",
        "edit_intent": "exact_replace",
        "source_digest": source_digest_for_content(source + "\n"),
        "old_string": old_solve,
        "new_string": new_solve if new_solve.endswith("\n") else new_solve + "\n",
        "replace_all": False,
        "test_hint": None,
    }


def _mock_llm() -> MockLLMClient:
    return MockLLMClient(
        hypothesis_response={
            "hypothesis_text": "Use a bounded solver-design route ordering pass for synthetic CVRP smoke.",
            "change_locus": "solver_design",
            "action": "modify",
            "target_file": "policies/baseline_algorithm.py",
            "predicted_direction": "exploratory",
            "target_weakness": "controlled CVRP route ordering",
            "expected_effect": "Improve only the checked-in synthetic controlled route shapes.",
            "suggested_weight": 0.1,
            "target_objectives": ["total_distance"],
            "protected_objectives": ["fleet_violation"],
            "objective_tradeoff_policy": "preserve fleet_violation before distance",
            "no_op_condition": "unrecognized controlled customer sets return the original solution",
            "risk_to_higher_priority": "none for route-count preserving controlled changes",
            "target_runtime_effect": "preserve",
            "complexity_claim": "O(n log n) route ordering with one bounded pass.",
            "runtime_budget_strategy": "Use one deterministic pass and emit solver-design telemetry.",
            "novelty_signature": {
                "algorithm_family": "controlled_solver_design_smoke",
                "construction_strategy": "ascending_single_route_when_capacity_allows",
                "improvement_strategy": "bounded_route_ordering",
                "acceptance_strategy": "strict_capacity_preserving",
                "runtime_budget_strategy": "single_pass",
            },
        },
        patch_response=_baseline_algorithm_solve_patch(
            (
                "def solve(instance, rng, time_limit_sec, context):\n"
                "    ordered = tuple(sorted(instance.customer_ids))\n"
                "    if ordered and instance.route_load(ordered) <= instance.capacity:\n"
                "        solution = context.make_solution((ordered,))\n"
                "    else:\n"
                "        solution = context.nearest_neighbor()\n"
                "    context.record_iteration('controlled_order_probe', 1)\n"
                "    context.record_move('controlled_order_probe', attempted=1, accepted=1, delta=0.0)\n"
                "    context.set_stop_reason('controlled_order_completed')\n"
                "    return solution\n"
            )
        ),
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
        problem_spec=spec_v1,
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
        force_surface="solver_design",
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
            data_roots=(VRP_DIR,),
            baseline_label="controlled-baseline",
            candidate_label=f"controlled-promoted-v{campaign._champion.version}",
            baseline_registry_path=CVRP_DIR / "registry.yaml",
            candidate_registry_path=champion_snapshot / "registry.yaml",
            output_dir=output_dir / "final_evidence",
        ),
        runner=runner,
        adapter=adapter,
    )


def _validate_smoke_success(
    *,
    campaign: CampaignManager,
    final_quality: dict[str, Any],
    output_dir: Path,
) -> None:
    protocol_steps = [
        step
        for step in campaign._step_history
        if getattr(step, "protocol_result", None) is not None
    ]
    effective_steps = [
        step
        for step in protocol_steps
        if screened_experiment_effective(step.protocol_result)
    ]

    reasons: list[str] = []
    if not protocol_steps:
        reasons.append("no campaign step reached ExperimentProtocol")
    if not effective_steps:
        reasons.append("no campaign step counted as an effective screened experiment")

    n_cases = int(final_quality.get("n_cases", 0) or 0)
    n_ok = int(final_quality.get("n_ok", 0) or 0)
    n_error = int(final_quality.get("n_error", 0) or 0)
    if n_error != 0:
        reasons.append(f"final_quality n_error={n_error}, expected 0")
    if n_ok != n_cases:
        reasons.append(f"final_quality n_ok={n_ok}, expected n_cases={n_cases}")
    if n_cases == 0:
        reasons.append("final_quality n_cases=0")

    if reasons:
        detail = "; ".join(reasons)
        raise SystemExit(
            f"controlled CVRP smoke failed closed: {detail}; output_dir={output_dir}"
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
