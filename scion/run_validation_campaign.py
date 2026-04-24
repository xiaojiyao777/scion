#!/usr/bin/env python3
"""Scion v0.3 Post-Optimization Validation Campaign Runner.

Usage:
    python run_validation_campaign.py --model claude-sonnet-4-6 --seed 11
    python run_validation_campaign.py --model gpt-5.4-mini --seed 11

Outputs to: ~/research/scion-experiments/v03-post-opt/<model>_synthetic_seed<N>/
"""
from __future__ import annotations

import argparse
import logging
import os
import random
import sys
import json
import time
import types
from pathlib import Path
from datetime import datetime

parser = argparse.ArgumentParser(description="v0.3 Post-Optimization Validation")
parser.add_argument("--model", required=True, help="LLM model ID")
parser.add_argument("--seed", required=True, type=int)
parser.add_argument("--max-rounds", type=int, default=100)
parser.add_argument("--splits-weight", type=int, default=1000)
parser.add_argument("--base-dir", default="v03-post-opt",
                    help="subdir under ~/research/scion-experiments/ (default: v03-post-opt)")
args = parser.parse_args()

random.seed(args.seed)
os.environ["SCION_SPLITS_WEIGHT"] = str(args.splits_weight)

SCION_DIR = Path(__file__).parent
PROBLEM_DIR = SCION_DIR / "problems" / "warehouse_delivery"
EXP_BASE = Path.home() / "research" / "scion-experiments" / args.base_dir

model_short = args.model.replace("claude-", "").replace(".", "")
campaign_name = f"{model_short}_synthetic_seed{args.seed}"
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

MANIFEST = PROBLEM_DIR / "split_manifest.yaml"

logger.info("=" * 70)
logger.info("v0.3 Post-Optimization Validation — %s", datetime.now().isoformat())
logger.info("=" * 70)
logger.info("  Model     : %s", args.model)
logger.info("  Variant   : synthetic")
logger.info("  Seed      : %d", args.seed)
logger.info("  Max rounds: %d", args.max_rounds)
logger.info("  Splits wt : %d", args.splits_weight)
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

# --- Load configs ---
spec = ProblemSpec.from_yaml(str(PROBLEM_DIR / "problem.yaml"))
proto_cfg = ProtocolConfig.from_yaml(str(PROBLEM_DIR / "protocol.yaml"))
split_manifest = SplitManifest.from_yaml(str(MANIFEST))
seed_ledger = SeedLedgerConfig.from_yaml(str(PROBLEM_DIR / "seed_ledger.yaml"))

# --- Build adapter (bridge old ProblemSpec → adapter interface) ---
from scion.problems.warehouse_delivery.adapter import WarehouseDeliveryAdapter
adapter_spec = types.SimpleNamespace(
    root_dir=spec.root_dir,
    oracle_path=spec.oracle_path,
    display_name=spec.name,
    description=spec.description,
    search_space=spec.search_space,
    operator_interface=types.SimpleNamespace(
        categories=[
            types.SimpleNamespace(name=cat) for cat in spec.operator_categories
        ]
    ),
)
adapter = WarehouseDeliveryAdapter(adapter_spec)

# --- Metric specs for generic comparison ---
from scion.problem.spec import ObjectiveMetricSpec
metric_specs = [
    ObjectiveMetricSpec(name="subcategory_splits", direction="minimize", priority=1),
    ObjectiveMetricSpec(name="total_cost", direction="minimize", priority=2),
]

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
    metric_specs=metric_specs,
)

verification_gate = VerificationGate(problem_spec=spec, runner=runner, adapter=adapter)

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
    objective_lower_bounds={"subcategory_splits": 0.0},
)

# --- Run ---
t_start = time.time()

config = {
    "model": args.model,
    "variant": "synthetic",
    "seed": args.seed,
    "max_rounds": args.max_rounds,
    "splits_weight": args.splits_weight,
    "manifest": str(MANIFEST),
    "started_at": datetime.now().isoformat(),
    "campaign_dir": str(CAMPAIGN_DIR),
    "post_opt": True,
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

summary = {
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
    summary["steps"].append(step_data)

(CAMPAIGN_DIR / "campaign_summary.json").write_text(json.dumps(summary, indent=2, default=str))
logger.info("Summary saved to %s/campaign_summary.json", CAMPAIGN_DIR)
