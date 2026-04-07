#!/usr/bin/env python3
"""Run a Scion mock campaign with warehouse_delivery-compatible responses."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)

from scion.config.problem import ProblemSpec, ProtocolConfig, SplitManifest, SeedLedgerConfig
from scion.proposal.mock_client import MockLLMClient
from scion.core.models import ChampionState
from scion.core.termination import TerminationConfig
from scion.runtime.workspace import WorkspaceMaterializer
from scion.runtime.subprocess_runner import LocalSubprocessRunner
from scion.protocol.experiment import ExperimentProtocol, SplitManager, SeedLedger
from scion.core.campaign import CampaignManager

PROBLEM_DIR = Path(__file__).parent / "problems" / "warehouse_delivery"
CAMPAIGN_DIR = Path("/tmp/scion_mock_run")

# --- Load configs ---
spec = ProblemSpec.from_yaml(str(PROBLEM_DIR / "problem.yaml"))
proto_cfg = ProtocolConfig.from_yaml(str(PROBLEM_DIR / "protocol.yaml"))
split_manifest = SplitManifest.from_yaml(str(PROBLEM_DIR / "split_manifest.yaml"))
seed_ledger = SeedLedgerConfig.from_yaml(str(PROBLEM_DIR / "seed_ledger.yaml"))

# --- Mock LLM with warehouse_delivery-compatible responses ---
# change_locus must be in operator_categories: ["order_level", "vehicle_level"]
# target_file must match editable pattern: "operators/*.py" and not be frozen
MOCK_HYPOTHESIS = {
    "hypothesis_text": "Improve move_order operator: add greedy acceptance for cost reduction.",
    "change_locus": "order_level",
    "action": "modify",
    "target_file": "operators/move_order.py",
    "predicted_direction": "improve",
    "target_weakness": "Current move_order uses pure random target vehicle selection.",
    "expected_effect": "Reduce total cost by targeting cheaper vehicle types when possible.",
    "suggested_weight": 0.3,
}

# Read actual move_order.py to produce a valid "modified" version
move_order_path = Path(spec.root_dir) / "operators" / "move_order.py"
original_code = move_order_path.read_text()

# Slightly modified version (add a comment to make it different but still valid)
modified_code = original_code.replace(
    "class MoveOrder(Operator):",
    "class MoveOrder(Operator):  # Scion-modified: greedy cost acceptance",
)

MOCK_PATCH = {
    "file_path": "operators/move_order.py",
    "action": "modify",
    "code_content": modified_code,
    "test_hint": "Test with small instances to verify cost reduction.",
}

llm_client = MockLLMClient(
    mode="success",
    hypothesis_response=MOCK_HYPOTHESIS,
    patch_response=MOCK_PATCH,
)

# --- Build champion ---
CAMPAIGN_DIR.mkdir(parents=True, exist_ok=True)
materializer = WorkspaceMaterializer(str(CAMPAIGN_DIR))
code_hash = materializer.compute_code_hash(spec.root_dir)
champion = ChampionState(
    version=1,
    operator_pool={},
    solver_config_hash="initial",
    code_snapshot_path=spec.root_dir,
    code_snapshot_hash=code_hash,
)

# --- Build real ExperimentProtocol ---
runner = LocalSubprocessRunner()
split_mgr = SplitManager(split_manifest)
seed_mgr = SeedLedger(seed_ledger)
metrics_dir = str(CAMPAIGN_DIR / "metrics")
Path(metrics_dir).mkdir(parents=True, exist_ok=True)

experiment_protocol = ExperimentProtocol(
    protocol_config=proto_cfg,
    split_manager=split_mgr,
    seed_ledger=seed_mgr,
    runner=runner,
    time_limit_sec=30,
    metrics_dir=metrics_dir,
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
    termination_config=TerminationConfig(
        max_experiments=max_rounds * 2,
        stagnation_limit=50,
    ),
)

print(f"=== Starting mock campaign: {spec.name} (max_rounds={max_rounds}) ===")
mgr.run(max_rounds=max_rounds)

state = mgr.get_state()
print(f"\n=== Campaign finished ===")
print(f"  Experiments    : {state['n_experiments']}")
print(f"  Champion ver   : {state['champion_version']}")
print(f"  Active branches: {state['n_active_branches']}")
for b in state.get("branches", []):
    print(f"    Branch {b['id'][:8]}… state={b['state']}")
print(f"\nMock LLM calls: {llm_client.call_count}")
