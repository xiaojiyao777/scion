#!/usr/bin/env python3
"""Run a full Scion v3 campaign with real LLM + real solver evaluation."""
from __future__ import annotations

import logging
import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("scion.run_v3")

from scion.config.problem import ProblemSpec, ProtocolConfig, SplitManifest, SeedLedgerConfig
from scion.proposal.llm_client import LLMClient
from scion.core.models import ChampionState
from scion.runtime.workspace import WorkspaceMaterializer
from scion.runtime.subprocess_runner import LocalSubprocessRunner
from scion.protocol.experiment import ExperimentProtocol, SplitManager, SeedLedger
from scion.core.campaign import CampaignManager
from scion.verification.gate import VerificationGate

PROBLEM_DIR = Path(__file__).parent / "problems" / "warehouse_delivery"
CAMPAIGN_DIR = Path("/home/clawd/research/scion-experiments/v02-uuid-fix-validation")

# --- Load configs ---
spec = ProblemSpec.from_yaml(str(PROBLEM_DIR / "problem.yaml"))
proto_cfg = ProtocolConfig.from_yaml(str(PROBLEM_DIR / "protocol.yaml"))
split_manifest = SplitManifest.from_yaml(str(PROBLEM_DIR / "split_manifest.yaml"))
seed_ledger = SeedLedgerConfig.from_yaml(str(PROBLEM_DIR / "seed_ledger.yaml"))

# --- Real LLM client ---
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

# --- Verification Gate ---
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
max_rounds = 10

print("=" * 70)
print(f"Scion v3 Full Campaign — {datetime.now().isoformat()}")
print("=" * 70)
print(f"  Problem        : {spec.name}")
print(f"  LLM model      : {llm_client.model}")
print(f"  Max rounds     : {max_rounds}")
print(f"  Solver timeout : {spec.solver}")
print(f"  Protocol       : screening_n={proto_cfg.screening_n}, validation_n={proto_cfg.validation_n}, frozen_n={proto_cfg.frozen_n}")
print(f"  Campaign dir   : {CAMPAIGN_DIR}")
print()

t_start = time.time()
mgr.run(max_rounds=max_rounds)
t_total = time.time() - t_start

state = mgr.get_state()
print(f"\n{'=' * 70}")
print(f"Campaign finished in {t_total:.0f}s ({t_total/60:.1f}min)")
print(f"{'=' * 70}")
print(f"  Experiments    : {state['n_experiments']}")
print(f"  Champion ver   : {state['champion_version']}")
print(f"  Active branches: {state['n_active_branches']}")
for b in state.get("branches", []):
    print(f"    Branch {b['id'][:8]}… state={b['state']}")
print(f"\nLLM model: {llm_client.model}")
print(f"Cache stats: {llm_client.get_cache_stats()}")

# --- Step History ---
print("\n=== Step History Summary ===")
step_history = mgr._step_history
if not step_history:
    print("  (no steps recorded)")
for step in step_history:
    hyp_text = ""
    if step.hypothesis:
        hyp_text = (step.hypothesis.hypothesis_text or "")[:80]
    patch_info = ""
    if step.patch:
        patch_info = f" patch={step.patch.file_path}({len(step.patch.code_content or '')}B)"
    print(
        f"  Round {step.round_num:3d} branch={step.branch_id[:8]}… "
        f"decision={step.decision.value if step.decision else '?'} "
        f"contract={step.contract_passed} verify={step.verification_passed}"
        f"{patch_info}"
    )
    if step.failure_stage:
        print(f"           failure_stage={step.failure_stage}: {step.failure_detail}")
    if hyp_text:
        print(f"           hyp='{hyp_text}'")

print("\n=== Hypotheses Generated ===")
for step in step_history:
    if step.hypothesis:
        action = step.hypothesis.action
        locus = step.hypothesis.change_locus
        target = step.hypothesis.target_file or "-"
        decision = step.decision.value if step.decision else "?"
        print(f"  [{decision:15s}] locus={locus} action={action} target={target}")

print("\n=== Final State ===")
print(f"  Budget used       : {mgr._budget.used}")
print(f"  Active hypotheses : {len(mgr._branch_hypotheses)}")
print(f"  Blacklisted       : {len(mgr._hyp_store.get_by_status('blacklisted'))}")
print(f"  Total time        : {t_total:.0f}s ({t_total/60:.1f}min)")
print(f"  Archive dir       : {mgr._materializer._archive_dir}")

# --- Save summary JSON for visualization ---
summary = {
    "campaign_start": datetime.now().isoformat(),
    "total_time_sec": round(t_total, 1),
    "max_rounds": max_rounds,
    "llm_model": llm_client.model,
    "protocol": {
        "screening_n": proto_cfg.screening_n,
        "validation_n": proto_cfg.validation_n,
        "frozen_n": proto_cfg.frozen_n,
    },
    "state": state,
    "steps": [],
}
for step in step_history:
    step_data = {
        "round": step.round_num,
        "branch_id": step.branch_id,
        "decision": step.decision.value if step.decision else None,
        "contract_passed": step.contract_passed,
        "verification_passed": step.verification_passed,
        "failure_stage": step.failure_stage,
        "failure_detail": step.failure_detail,
    }
    if step.hypothesis:
        step_data["hypothesis"] = {
            "text": step.hypothesis.hypothesis_text,
            "action": step.hypothesis.action,
            "change_locus": step.hypothesis.change_locus,
            "target_file": step.hypothesis.target_file,
        }
    if step.patch:
        step_data["patch"] = {
            "file_path": step.patch.file_path,
            "action": step.patch.action,
            "code_size": len(step.patch.code_content or ""),
        }
    summary["steps"].append(step_data)

summary_path = CAMPAIGN_DIR / "campaign_summary.json"
summary_path.write_text(json.dumps(summary, indent=2, default=str))
print(f"\nSummary saved to {summary_path}")
