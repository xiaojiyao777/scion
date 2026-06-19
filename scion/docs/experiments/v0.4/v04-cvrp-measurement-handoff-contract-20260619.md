# v0.4 CVRP Measurement Handoff Contract

Date: 2026-06-19

## Purpose

The focused CVRP prepared handoff was carrying the right Phase 1 A/A facts, but
the launcher owned the MDE/practical-delta literals. That made future drift
easy: a prepared root could remain launch-ready with hand-written measurement
numbers instead of problem-owned declaration and calibration evidence.

This repair keeps the diagnostics proposal-visible and report-only, but derives
them from `problem-v1.yaml` measurement declarations and the declared
`calibration_ref`.

## Repair

- `scion/tools/launch_cvrp_agentic_campaign.py` builds
  `research_focus.measurement_opportunity_diagnostics` from
  `problem_v1.measurement.calibration_ref`.
- `scion/tools/postrun_artifact_inventory.py` marks the prepared contract
  incomplete unless the CVRP measurement handoff has problem-owned source,
  ready measurement status, `scion.aa_noise_floor.v1` calibration schema, and
  `DecisionFeatures` exclusion.
- The contract remains proposal/delegated-analysis guidance only. It does not
  change Decision, Protocol gates, promotion, scheduler state, or solver code.

## Verification

Local:

```bash
python -m py_compile scion/tools/launch_cvrp_agentic_campaign.py scion/tools/postrun_artifact_inventory.py scion/scion/tests/test_cvrp_agentic_launcher.py scion/scion/tests/test_launch_readiness.py
PYTHONPATH=scion pytest -q scion/scion/tests/test_cvrp_agentic_launcher.py scion/scion/tests/test_launch_readiness.py scion/scion/tests/test_cvrp_formal_readiness.py scion/scion/tests/test_problem_bridge.py
```

Result: `106 passed`.

WSL:

```bash
PYTHONPATH=scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/pytest -q scion/scion/tests/test_cvrp_agentic_launcher.py scion/scion/tests/test_launch_readiness.py scion/scion/tests/test_cvrp_formal_readiness.py scion/scion/tests/test_problem_bridge.py
```

Result: `106 passed`.

## Current Prepared Roots

Generated from WSL runtime commit `feaddec7`:

- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-measurecontract-feaddec7-6r-gpt55-20260619T183236Z-claw`
- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-measurecontract-feaddec7-1r-gpt55-20260619T183236Z-claw`

Strict WSL launch readiness with real completion preflight reports
`static_ready=true`, `launch_ready=false`, exit `64` for both roots. Static
checks include `git_runtime_worktree_clean=ok` and
`run_script_proposal_headroom_enforced=ok`; both roots also report
`problem_specific_prepared_handoff=ok`.

The CVRP prepared manifest records:

- measurement source: `problem_v1.measurement.calibration_ref`
- readiness: `status=ready`, `reason_code=ok`
- calibration schema: `scion.aa_noise_floor.v1`
- `mde_at_power_80=9.9`, `practical_screen_delta=2.0`, `n_pairs=96`

The warehouse prepared manifest records:

- measurement source: `problem_v1.measurement.calibration_ref`
- readiness: `status=ready`, `reason_code=ok`
- calibration schema: `scion.aa_noise_floor.v1`
- `mde_at_power_80=577.5`, `practical_screen_delta=0.001`, `n_pairs=36`
- related create-new calibration MDE: `1725.0`

The remaining blocker is external `gpt-5.5` provider auth, not Scion static
readiness: chat completion preflight returns HTTP `401`,
`classification=not_authenticated`, `code=invalid_api_key`, with auth pool
`active=0`, `expired=1`, `total=1`.
