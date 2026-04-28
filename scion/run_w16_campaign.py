#!/usr/bin/env python3
"""Scion v0.3 W16 Validation Campaign Runner.

Usage:
    python run_w16_campaign.py --model claude-sonnet-4-6 --variant synthetic --seed 11
    python run_w16_campaign.py --model gpt-5.4-mini --variant production --seed 29

Outputs to: ~/research/scion-experiments/v03-validation/<model>_<variant>_seed<N>/
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

# --- Args ---
parser = argparse.ArgumentParser(description="W16 Validation Campaign")
parser.add_argument("--model", required=True, help="LLM model ID")
parser.add_argument("--variant", required=True, choices=["synthetic", "production"])
parser.add_argument("--seed", required=True, type=int, help="Campaign seed (11/29/47)")
parser.add_argument("--max-rounds", type=int, default=100)
parser.add_argument("--splits-weight", type=int, default=1000)
args = parser.parse_args()

# --- Deterministic init ---
random.seed(args.seed)
os.environ["SCION_SPLITS_WEIGHT"] = str(args.splits_weight)

# --- Paths ---
SCION_DIR = Path(__file__).parent
PROBLEM_DIR = SCION_DIR / "problems" / "warehouse_delivery"
EXP_BASE = Path.home() / "research" / "scion-experiments" / "v03-validation"

model_short = args.model.replace("claude-", "").replace(".", "")
campaign_name = f"{model_short}_{args.variant}_seed{args.seed}"
CAMPAIGN_DIR = EXP_BASE / campaign_name
CAMPAIGN_DIR.mkdir(parents=True, exist_ok=True)

# --- Logging ---
log_file = CAMPAIGN_DIR / "campaign.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(str(log_file)),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("scion.w16")

# --- Variant → manifest ---
MANIFEST_MAP = {
    "synthetic": PROBLEM_DIR / "split_manifest.yaml",
    "production": PROBLEM_DIR / "split_manifest_prod.yaml",
}

logger.info("=" * 70)
logger.info("W16 Validation Campaign — %s", datetime.now().isoformat())
logger.info("=" * 70)
logger.info("  Model     : %s", args.model)
logger.info("  Variant   : %s", args.variant)
logger.info("  Seed      : %d", args.seed)
logger.info("  Max rounds: %d", args.max_rounds)
logger.info("  Splits wt : %d", args.splits_weight)
logger.info("  Output    : %s", CAMPAIGN_DIR)
logger.info("  Manifest  : %s", MANIFEST_MAP[args.variant])
logger.info("=" * 70)

# --- Imports ---
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
split_manifest = SplitManifest.from_yaml(str(MANIFEST_MAP[args.variant]))
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

# --- Experiment protocol ---
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
)

verification_gate = VerificationGate(problem_spec=spec, runner=runner)

# --- Campaign Manager ---
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
)

# --- Run ---
t_start = time.time()

# Save config before starting
config = {
    "model": args.model,
    "variant": args.variant,
    "seed": args.seed,
    "max_rounds": args.max_rounds,
    "splits_weight": args.splits_weight,
    "manifest": str(MANIFEST_MAP[args.variant]),
    "started_at": datetime.now().isoformat(),
    "campaign_dir": str(CAMPAIGN_DIR),
}
(CAMPAIGN_DIR / "experiment_config.json").write_text(json.dumps(config, indent=2))

mgr.run(max_rounds=args.max_rounds)
t_total = time.time() - t_start

# --- Summary ---
state = mgr.get_state()
logger.info("Campaign finished in %.0fs (%.1fh)", t_total, t_total / 3600)
logger.info("  Experiments: %d", state["n_experiments"])
logger.info("  Champion v%d", state["champion_version"])

# Save summary
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
    }
    if step.hypothesis:
        step_data["hypothesis"] = {
            "text": (step.hypothesis.hypothesis_text or "")[:200],
            "action": step.hypothesis.action,
            "locus": step.hypothesis.change_locus,
            "target": step.hypothesis.target_file,
        }
    summary["steps"].append(step_data)

(CAMPAIGN_DIR / "campaign_summary.json").write_text(json.dumps(summary, indent=2, default=str))
logger.info("Summary saved to %s/campaign_summary.json", CAMPAIGN_DIR)
