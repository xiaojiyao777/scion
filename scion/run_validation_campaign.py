#!/usr/bin/env python3
"""Scion v0.3 Post-Optimization Validation Campaign Runner.

Usage:
    python run_validation_campaign.py --model claude-sonnet-4-6 --seed 11
    python run_validation_campaign.py --model gpt-5.4-mini --seed 11
    python run_validation_campaign.py --model claude-sonnet-4-6 --variant production --seed 11

Outputs to: ~/research/scion-experiments/<base-dir>/<model>_<variant>_seed<N>/
"""
from __future__ import annotations

import argparse
import logging
import os
import random
import sys
import json
import time
from pathlib import Path
from datetime import datetime

import yaml

parser = argparse.ArgumentParser(description="v0.3 Post-Optimization Validation")
parser.add_argument("--model", required=True, help="LLM model ID")
parser.add_argument("--variant", default="synthetic", choices=["synthetic", "production"],
                    help="dataset variant / split manifest to use")
parser.add_argument("--seed", required=True, type=int)
parser.add_argument("--max-rounds", type=int, default=100)
parser.add_argument("--splits-weight", type=int, default=1000)
parser.add_argument("--base-dir", default="v03-post-opt",
                    help="subdir under ~/research/scion-experiments/ (default: v03-post-opt)")
parser.add_argument("--protocol", default=None,
                    help="optional explicit protocol yaml path")
parser.add_argument("--weight-opt-execution", choices=["sync", "async"], default="sync",
                    help="weight optimization execution mode (default: sync for 2-core validation hosts)")
parser.add_argument("--weight-opt-final-wait", type=float, default=None,
                    help="async final wait timeout in seconds; omit for config default")
args = parser.parse_args()

random.seed(args.seed)
os.environ["SCION_SPLITS_WEIGHT"] = str(args.splits_weight)

SCION_DIR = Path(__file__).parent
PROBLEM_DIR = SCION_DIR / "problems" / "warehouse_delivery"
EXP_BASE = Path.home() / "research" / "scion-experiments" / args.base_dir

model_short = args.model.replace("claude-", "").replace(".", "")
campaign_name = f"{model_short}_{args.variant}_seed{args.seed}"
CAMPAIGN_DIR = EXP_BASE / campaign_name
CAMPAIGN_DIR.mkdir(parents=True, exist_ok=True)

log_file = CAMPAIGN_DIR / "campaign.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(str(log_file)),
        logging.StreamHandler(),
    ],
)
# Silence noisy third-party loggers
for _lib in ("httpcore", "httpx", "anthropic", "openai", "urllib3"):
    logging.getLogger(_lib).setLevel(logging.WARNING)
logger = logging.getLogger("scion.validation")

MANIFEST_MAP = {
    "synthetic": PROBLEM_DIR / "split_manifest.yaml",
    "production": PROBLEM_DIR / "split_manifest_prod.yaml",
}
PROTOCOL_MAP = {
    "synthetic": PROBLEM_DIR / "protocol.yaml",
    "production": PROBLEM_DIR / "protocol_prod.yaml",
}
MANIFEST = MANIFEST_MAP[args.variant]
PROTOCOL = Path(args.protocol).expanduser() if args.protocol else PROTOCOL_MAP[args.variant]
if not PROTOCOL.exists():
    raise FileNotFoundError(f"protocol file not found: {PROTOCOL}")

logger.info("=" * 70)
logger.info("v0.3 Post-Optimization Validation — %s", datetime.now().isoformat())
logger.info("=" * 70)
logger.info("  Model     : %s", args.model)
logger.info("  Variant   : %s", args.variant)
logger.info("  Seed      : %d", args.seed)
logger.info("  Max rounds: %d", args.max_rounds)
logger.info("  Splits wt : %d", args.splits_weight)
logger.info("  Protocol  : %s", PROTOCOL)
logger.info("  Output    : %s", CAMPAIGN_DIR)
logger.info("=" * 70)

sys.path.insert(0, str(SCION_DIR))
from scion.config.problem import ProblemSpec, ProtocolConfig, SplitManifest, SeedLedgerConfig
from scion.proposal.llm_client import LLMClient
from scion.core.models import ChampionState
from scion.runtime.workspace import WorkspaceMaterializer
from scion.runtime.subprocess_runner import LocalSubprocessRunner
from scion.protocol.experiment import ExperimentProtocol, SplitManager, SeedLedger
from scion.core.campaign import CampaignManager
from scion.verification.gate import VerificationGate
from scion.problem.loader import load_problem_adapter
from scion.problem.spec import ProblemSpecV1


def _assert_protocol_matches_variant(
    variant: str,
    protocol_path: Path,
    protocol_config: ProtocolConfig,
) -> None:
    """Fail fast on split/protocol mismatch.

    Production and synthetic experiments use different gate/sample policies.
    Accidentally pairing a production split with the generic protocol silently
    changes the experiment contract, so this runner rejects that configuration.
    """
    marker = f"{protocol_path.name} {protocol_config.version}".lower()
    is_prod_protocol = "prod" in marker or "production" in marker
    if variant == "production" and not is_prod_protocol:
        raise ValueError(
            "variant=production requires a production protocol. "
            f"Got {protocol_path} (version={protocol_config.version!r})."
        )
    if variant == "synthetic" and is_prod_protocol:
        raise ValueError(
            "variant=synthetic must not use a production protocol. "
            f"Got {protocol_path} (version={protocol_config.version!r})."
        )

# --- Load configs ---
spec = ProblemSpec.from_yaml(str(PROBLEM_DIR / "problem.yaml"))
spec.parameter_search.execution = args.weight_opt_execution
if args.weight_opt_final_wait is not None:
    spec.parameter_search.final_wait_timeout_sec = args.weight_opt_final_wait
with open(PROBLEM_DIR / "problem-v1.yaml", encoding="utf-8") as fh:
    adapter_spec = ProblemSpecV1(**yaml.safe_load(fh))
adapter = load_problem_adapter(adapter_spec)
proto_cfg = ProtocolConfig.from_yaml(str(PROTOCOL))
_assert_protocol_matches_variant(args.variant, PROTOCOL, proto_cfg)
split_manifest = SplitManifest.from_yaml(str(MANIFEST))
seed_ledger = SeedLedgerConfig.from_yaml(str(PROBLEM_DIR / "seed_ledger.yaml"))

# --- LLM client ---
llm_client = LLMClient(model=args.model)

# --- Build champion ---
materializer = WorkspaceMaterializer(
    str(CAMPAIGN_DIR),
    frozen_patterns=frozenset(spec.search_space.frozen) if spec.search_space.frozen else None,
)
code_hash = materializer.compute_code_hash(spec.root_dir)
champion = ChampionState(
    version=1,
    operator_pool={},
    solver_config_hash="initial",
    code_snapshot_path=spec.root_dir,
    code_snapshot_hash=code_hash,
)

# --- Experiment protocol (with generic metric_specs) ---
runner = LocalSubprocessRunner()
split_mgr = SplitManager(split_manifest)
seed_mgr = SeedLedger(seed_ledger)

experiment_protocol = ExperimentProtocol(
    protocol_config=proto_cfg,
    split_manager=split_mgr,
    seed_ledger=seed_mgr,
    runner=runner,
    time_limit_sec=spec.solver.time_limit_sec if spec.solver else 300,
    metrics_dir=str(CAMPAIGN_DIR / "metrics"),
    metric_specs=adapter_spec.objectives,
    objective_policy=adapter_spec.objective_policy,
    require_metric_specs=True,
)

verification_gate = VerificationGate(
    problem_spec=spec,
    runner=runner,
    adapter=adapter,
    strict_runtime_checks=True,
    require_adapter_for_runtime=True,
    operator_execute_signature=adapter_spec.operator_interface.execute_signature,
)

# --- Campaign Manager (with adapter + lower bounds) ---
mgr = CampaignManager(
    problem_spec=spec,
    protocol_config=proto_cfg,
    split_manifest=split_manifest,
    seed_ledger=seed_ledger,
    llm_client=llm_client,
    champion=champion,
    campaign_dir=str(CAMPAIGN_DIR),
    experiment_protocol=experiment_protocol,
    verification_gate=verification_gate,
    adapter=adapter,
    operator_execute_signature=adapter_spec.operator_interface.execute_signature,
    objective_lower_bounds={"subcategory_splits": 0.0},
)

# --- Run ---
t_start = time.time()

config = {
    "model": args.model,
    "variant": args.variant,
    "seed": args.seed,
    "max_rounds": args.max_rounds,
    "splits_weight": args.splits_weight,
    "manifest": str(MANIFEST),
    "protocol": str(PROTOCOL),
    "protocol_version": proto_cfg.version,
    "objective_policy": adapter_spec.objective_policy.model_dump(),
    "objectives": [m.model_dump() for m in adapter_spec.objectives],
    "started_at": datetime.now().isoformat(),
    "campaign_dir": str(CAMPAIGN_DIR),
    "post_opt": True,
    "weight_opt_execution": spec.parameter_search.execution,
    "weight_opt_final_wait_timeout_sec": spec.parameter_search.final_wait_timeout_sec,
    "parameter_search": spec.parameter_search.model_dump(),
    "changes": [
        "tendency-based context (no MANDATORY CONSTRAINT)",
        "early-stop: budget_efficiency (idle>60%) + diminishing_returns",
        "V5 CANDIDATE→light (fix retry enabled)",
        "cross-branch failure sharing",
        "adapter-driven problem summary + operator interface",
        "generic ObjectiveComparison (no ObjectiveBreakdown)",
    ],
}
(CAMPAIGN_DIR / "experiment_config.json").write_text(json.dumps(config, indent=2))

logger.info("Starting campaign...")
mgr.run(max_rounds=args.max_rounds)
t_total = time.time() - t_start

# --- Summary ---
state = mgr.get_state()
logger.info("Campaign finished in %.0fs (%.1fh)", t_total, t_total / 3600)
logger.info("  Experiments: %d", state["n_experiments"])
logger.info("  Champion v%d", state["champion_version"])

runner_summary = {
    **config,
    "finished_at": datetime.now().isoformat(),
    "total_time_sec": round(t_total, 1),
    "state": state,
    "llm_cache_stats": llm_client.get_cache_stats(),
    "steps": [],
}
for step in mgr._step_history:
    step_data = {
        "round": step.round_num,
        "branch_id": step.branch_id,
        "decision": step.decision.value if step.decision else None,
        "contract_passed": step.contract_passed,
        "verification_passed": step.verification_passed,
        "failure_stage": step.failure_stage,
        "failure_detail": (step.failure_detail or "")[:300] if step.failure_detail else None,
    }
    if step.hypothesis:
        step_data["hypothesis"] = {
            "text": (step.hypothesis.hypothesis_text or "")[:300],
            "action": step.hypothesis.action,
            "locus": step.hypothesis.change_locus,
            "target": step.hypothesis.target_file,
        }
    if step.protocol_result:
        pr = step.protocol_result
        step_data["protocol"] = {
            "stage": pr.stage.value if hasattr(pr.stage, 'value') else str(pr.stage),
            "win_rate": pr.stats.win_rate,
            "median_delta": pr.stats.median_delta,
            "gate_outcome": pr.gate_outcome,
        }
    runner_summary["steps"].append(step_data)

runner_summary_path = CAMPAIGN_DIR / "validation_runner_summary.json"
runner_summary_path.write_text(json.dumps(runner_summary, indent=2, default=str))

summary_path = CAMPAIGN_DIR / "campaign_summary.json"
if summary_path.exists():
    try:
        summary = json.loads(summary_path.read_text())
    except Exception:
        summary = {}
else:
    summary = {}

summary.update({
    "validation_runner": {
        **config,
        "finished_at": runner_summary["finished_at"],
        "total_time_sec": runner_summary["total_time_sec"],
    },
    "state": state,
    "llm_cache_stats": llm_client.get_cache_stats(),
})
summary_path.write_text(json.dumps(summary, indent=2, default=str))
logger.info("Summary saved to %s", summary_path)
logger.info("Runner summary saved to %s", runner_summary_path)
