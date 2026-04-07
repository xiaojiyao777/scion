#!/usr/bin/env python3
"""Run a full Scion mock campaign with ExperimentProtocol (real solver evaluation)."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)

from scion.config.problem import ProblemSpec, ProtocolConfig, SplitManifest, SeedLedgerConfig
from scion.proposal.llm_client import LLMClient
from scion.core.models import ChampionState
from scion.runtime.workspace import WorkspaceMaterializer
from scion.runtime.subprocess_runner import LocalSubprocessRunner
from scion.protocol.experiment import ExperimentProtocol, SplitManager, SeedLedger
from scion.core.campaign import CampaignManager

PROBLEM_DIR = Path(__file__).parent / "problems" / "warehouse_delivery"
CAMPAIGN_DIR = Path("/tmp/scion_full_run")

# --- Load configs ---
spec = ProblemSpec.from_yaml(str(PROBLEM_DIR / "problem.yaml"))
proto_cfg = ProtocolConfig.from_yaml(str(PROBLEM_DIR / "protocol.yaml"))
split_manifest = SplitManifest.from_yaml(str(PROBLEM_DIR / "split_manifest.yaml"))
seed_ledger = SeedLedgerConfig.from_yaml(str(PROBLEM_DIR / "seed_ledger.yaml"))

# --- Real LLM client (aihubmix / Anthropic) ---
llm_client = LLMClient()

# --- Build champion ---
CAMPAIGN_DIR.mkdir(parents=True, exist_ok=True)
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

# --- Build ExperimentProtocol with real solver ---
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

# --- Run ---
max_rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 3

mgr = CampaignManager(
    problem_spec=spec,
    protocol_config=proto_cfg,
    split_manifest=split_manifest,
    seed_ledger=seed_ledger,
    llm_client=llm_client,
    champion=champion,
    campaign_dir=str(CAMPAIGN_DIR),
    experiment_protocol=experiment_protocol,
)

print(f"=== Starting full campaign: {spec.name} (max_rounds={max_rounds}) ===")
print(f"    Solver time limit: {spec.solver}")
print(f"    Protocol: screening_n={proto_cfg.screening_n}, validation_n={proto_cfg.validation_n}")
print()

mgr.run(max_rounds=max_rounds)

state = mgr.get_state()
print(f"\n=== Campaign finished ===")
print(f"  Experiments    : {state['n_experiments']}")
print(f"  Champion ver   : {state['champion_version']}")
print(f"  Active branches: {state['n_active_branches']}")
for b in state.get("branches", []):
    print(f"    Branch {b['id'][:8]}… state={b['state']}")
print(f"\nLLM model: {llm_client.model}")
