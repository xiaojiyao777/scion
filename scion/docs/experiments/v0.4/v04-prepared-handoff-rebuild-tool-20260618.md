# v0.4 Prepared Handoff Rebuild Tool

Date: 2026-06-18

## Purpose

Prepared CVRP and warehouse roots can wait for LLM auth while reporting tooling
continues to improve. The current active roots were still unstarted, but their
already-written `prepared_handoff/` artifacts predated the latest CVRP and
warehouse problem-specific coverage repairs. This repair adds a report-only
rebuild path so prepared-root handoff artifacts can be refreshed without
launching a campaign or mutating runtime state.

## Change

- Added `scion/tools/rebuild_prepared_handoff.py`.
- CVRP and warehouse launchers now use the shared rebuild path when preparing
  new roots.
- The rebuild writes prepared analysis briefs, artifact inventories,
  launch-readiness snapshots, and
  `prepared_handoff/rebuild/prepared_handoff_rebuild.v1.json`.

## Boundary Check

- The rebuild is report-only.
- It does not start the campaign.
- It does not mutate campaign state, scheduler state, promotion state,
  `DecisionFeatures`, Protocol evidence, or problem solver semantics.
- Rebuilt CVRP/warehouse problem-specific requirements remain delegated-review
  handoff evidence, not deterministic Decision input.

## Current Active Root Refresh

Current rebuild verification checkout: `399db52`.

Refreshed on WSL:

- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-bounded-ready-399db52-1r-gpt55-20260619T015826Z-claw`
- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-ready-399db52-6r-gpt55-20260619T015826Z-claw`

Both rebuild manifests report:

- `complete=true`
- `campaign_state_mutated=false`
- `scheduler_state_mutated=false`
- `promotion_state_mutated=false`
- `decision_features_excluded=true`

Prepared manifest commits are root-specific. The current CVRP and warehouse
roots were regenerated after later runtime-guard and prepared-only review
guidance changes so the manifest and current handoff tooling agree:

- CVRP: `prepared_manifest_commit=399db52`
- Warehouse: `prepared_manifest_commit=399db52`

## Problem-Specific Coverage

CVRP rebuilt analysis brief and inventory now expose all required
`problem_specific_requirements`:

- `cvrp_decision_boundary_handoff`
- `cvrp_default_avoid_handoff`
- `cvrp_direct_effect_rules_handoff`
- `cvrp_large_twoopt_seed_handoff`
- `cvrp_large_twoopt_unbounded_default_avoid_handoff`
- `cvrp_low_snr_reason_handoff`
- `cvrp_measurable_opportunity_handoff`
- `cvrp_measurement_mde_handoff`

Warehouse rebuilt analysis brief and inventory now expose all required
`problem_specific_requirements`:

- `warehouse_continuous_plateau_question`
- `warehouse_decision_boundary_handoff`
- `warehouse_default_avoid_handoff`
- `warehouse_required_evidence_handoff`
- `warehouse_v2_checkpoint_handoff`

All listed brief and inventory requirements were verified with
`available=true`.

## Launch Readiness

The refreshed active roots remain unstarted and statically ready, but they must
not be launched yet:

- CVRP: `static_ready=true`, `launch_ready=false`, `ready=false`
- Warehouse: `static_ready=true`, `launch_ready=false`, `ready=false`
- Strict launch readiness exits `64` for both roots.
- Completion preflight failed for both with HTTP `401`,
  `classification=not_authenticated`, and `code=invalid_api_key`.
- The proxy auth pool reported `active=0` and `total=1`; the non-active
  account may appear as expired or refreshing.

Launch remains blocked until `/v1/chat/completions` returns HTTP `200` with a
non-empty `gpt-5.5` completion.

## Verification

Local focused checks:

```bash
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q \
  scion/scion/tests/test_rebuild_prepared_handoff.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py \
  scion/scion/tests/test_launch_readiness.py
# 33 passed

PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion python -m py_compile \
  scion/tools/rebuild_prepared_handoff.py \
  scion/tools/launch_cvrp_agentic_campaign.py \
  scion/tools/launch_warehouse_agentic_campaign.py \
  scion/scion/tests/test_rebuild_prepared_handoff.py

git diff --check -- \
  scion/tools/rebuild_prepared_handoff.py \
  scion/tools/launch_cvrp_agentic_campaign.py \
  scion/tools/launch_warehouse_agentic_campaign.py \
  scion/scion/tests/test_rebuild_prepared_handoff.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py
```

WSL extended checks after fast-forwarding the WSL checkout to `86d8561`:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/test_rebuild_prepared_handoff.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py \
  scion/scion/tests/test_proposal_trajectory_artifacts.py
# 67 passed
```

## Acceptance

Accepted as a Phase 4 prepared-root handoff repair. The active CVRP and
warehouse roots now carry current delegated-analysis coverage while remaining
unstarted. The only current launch blocker is external `gpt-5.5` auth, not the
prepared-root handoff contract.
