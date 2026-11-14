# v0.4 Warehouse Measurement Handoff Contract

Date: 2026-06-19

## Purpose

Warehouse already had a compact problem-owned A/A calibration at
`surrogate/calibration/aa_noise_floor.json`, but the prepared launcher only
handed agents textual runtime/plateau guidance. That left the current v2
follow-up vulnerable to treating fast completion, cost-compression noise, or
plateau claims as ungrounded prompt text instead of problem-owned measurement
context.

This repair keeps the handoff proposal-visible and report-only while deriving
it from `problem-v1.yaml` measurement declarations and the declared
`calibration_ref`.

## Repair

- `scion/tools/launch_warehouse_agentic_campaign.py` builds
  `research_focus.measurement_opportunity_diagnostics` from the rewritten
  run-root `problem-v1.yaml` and the resolved warehouse calibration artifact.
- `scion/tools/postrun_artifact_inventory.py` marks the prepared contract
  incomplete unless the warehouse measurement handoff has problem-owned source,
  ready measurement status, `scion.aa_noise_floor.v1` calibration schema, and
  `DecisionFeatures` exclusion.
- `scion/tools/rebuild_prepared_handoff.py` exposes
  `warehouse_measurement_runtime_handoff` as a required prepared prompt-context
  signal.
- The contract remains proposal/delegated-analysis guidance only. It does not
  change Decision, Protocol gates, promotion, scheduler state, or solver code.

## Verification

Local:

```bash
PYTHONPATH=scion python -m py_compile scion/tools/launch_warehouse_agentic_campaign.py scion/tools/postrun_artifact_inventory.py scion/tools/rebuild_prepared_handoff.py
PYTHONPATH=scion pytest -q scion/scion/tests/test_warehouse_agentic_launcher.py scion/scion/tests/test_launch_readiness.py scion/scion/tests/test_problem_bridge.py scion/scion/tests/unit/test_problem_measurement_artifacts.py
```

Result: `97 passed`.

WSL:

```bash
PYTHONPATH=scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/pytest -q scion/scion/tests/test_warehouse_agentic_launcher.py scion/scion/tests/test_launch_readiness.py scion/scion/tests/test_problem_bridge.py scion/scion/tests/unit/test_problem_measurement_artifacts.py
```

Result: `97 passed`.

## Current Prepared Roots

Generated from WSL runtime commit `feaddec7`:

- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-measurecontract-feaddec7-6r-gpt55-20260619T183236Z-claw`
- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-measurecontract-feaddec7-1r-gpt55-20260619T183236Z-claw`

Strict WSL launch readiness with real completion preflight reports
`static_ready=true`, `launch_ready=false` for both roots. Static checks include
`prepared_contract_complete=ok`, `problem_specific_prepared_handoff=ok`,
`git_runtime_consistent=ok`, and `git_runtime_worktree_clean=ok`.

The warehouse prepared manifest records:

- measurement source: `problem_v1.measurement.calibration_ref`
- readiness: `status=ready`, `reason_code=ok`
- calibration schema: `scion.aa_noise_floor.v1`
- metric/runtime: `total_cost`, `runtime_model=comparative`,
  `pairing_validity=trajectory_divergent`
- `mde_at_power_80=577.5`, `practical_screen_delta=0.001`, `n_pairs=36`
- related create-new calibration MDE: `1725.0`

The remaining blocker is external `gpt-5.5` provider auth, not Scion static
readiness: chat completion preflight returns HTTP `401`,
`classification=not_authenticated`, `code=invalid_api_key`.
