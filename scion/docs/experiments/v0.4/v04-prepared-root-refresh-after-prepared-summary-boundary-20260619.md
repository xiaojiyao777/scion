# v0.4 Prepared Root Refresh After Prepared-Summary Boundary Guard

Date: 2026-06-19

## Purpose

Launch readiness now requires prepared-only analysis briefs to carry the
problem-family matching prepared summary (`warehouse_followup_summary` or
`cvrp_large_twoopt_summary`) with the current schema and report-only,
non-quality-judgment, `DecisionFeatures`-excluded boundary markers. The change
touched `scion/tools/check_launch_readiness.py`, a guarded runtime path, so both
unstarted prepared roots were regenerated before launch.

## Boundary Check

- This is launch-readiness validation of prepared delegated-review artifacts.
- It does not change Decision, `DecisionFeatures`, Protocol gates, lifecycle,
  scheduler, promotion, proposal selection, or solver semantics.
- CVRP and warehouse semantics remain in problem-owned prepared/postrun summary
  layers.

## Current Prepared Roots

WSL checkout: `54907f9`

- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-prepsummary-54907f9-6r-gpt55-20260619T090021Z-claw`
- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-prepsummary-54907f9-1r-gpt55-20260619T090034Z-claw`

Both roots are prepare-only and not started.

## Readiness Evidence

Both roots report:

- `static_ready=true`
- `launch_ready=false`
- `prepared_analysis_brief_current=ok`
- `prompt_context_readiness_complete=ok`
- `problem_specific_prepared_handoff=ok`
- `postrun_families_complete=ok`
- `run_script_strict_postrun_readiness=ok`
- `git_runtime_consistent=ok`
- `run_script_runtime_guard_enforced=ok`
- `run_script_postrun_reports_after_campaign=ok`
- `run_script_data_root_failure_reports=ok`
- `run_script_api_key_env_failure_reports=ok`
- `runtime_guard_paths_cover_launch_tools=ok`
- `runtime_guard_paths_cover_problem_runtime=ok`
- completion preflight `failed`, HTTP `401`, `code=invalid_api_key`
- auth pool `active=0`, `total=1`

The current blocker remains external `gpt-5.5` auth, not prepared-root static
readiness.

## Verification

Local:

```bash
PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py
# 93 passed
```

WSL:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py
# 93 passed
```

## Acceptance

Accepted as the current prepared-root refresh after prepared problem-summary
boundary checks. Do not launch either root until strict launch readiness reports
`launch_ready=true`.
