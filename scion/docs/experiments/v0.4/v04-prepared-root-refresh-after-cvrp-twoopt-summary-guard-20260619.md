# v0.4 Prepared Root Refresh After CVRP Two-Opt Summary Guard

Date: 2026-06-19

## Purpose

The CVRP large two-opt postrun summary guard changed
`postrun_analysis_brief.py`, which is part of the prepared-root runtime guard
set. The existing warehouse and CVRP prepared roots were still unstarted, so
both were regenerated from the synchronized WSL checkout before any launch.

## Current Prepared Roots

WSL checkout: `529b9ef`

- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-ready-529b9ef-6r-gpt55-20260619T003636Z-claw`
- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-bounded-ready-529b9ef-1r-gpt55-20260619T003637Z-claw`

Both roots are prepare-only and not started.

## Handoff Evidence

Warehouse:

- `git.commit=529b9ef`
- `control_pair_key=warehouse.v2-followup:rep01`
- `prompt_context_readiness.ready_for_launch_prompt_audit=true`
- Warehouse problem-specific handoff items all report `available=true`.

CVRP:

- `git.commit=529b9ef`
- `control_pair_key=cvrp.large-twoopt-bounded:rep01`
- `prompt_context_readiness.ready_for_launch_prompt_audit=true`
- CVRP problem-specific handoff items all report `available=true`, including
  `cvrp_large_twoopt_bounded_constraints_handoff`.

## Strict Launch Readiness

Both roots report:

- `static_ready=true`
- `launch_ready=false`
- `prompt_context_readiness_complete=ok`
- `git_runtime_consistent=ok`
- completion preflight `failed`
- HTTP `401`, `classification=not_authenticated`, `code=invalid_api_key`
- auth pool `active=0`, `total=1`

The current blocker remains external `gpt-5.5` auth, not prepared-root static
readiness.

## Verification

Local:

```bash
PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py \
  scion/scion/tests/test_launch_readiness.py
# 57 passed
```

WSL:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py \
  scion/scion/tests/test_launch_readiness.py
# 57 passed
```

## Acceptance

Accepted as the current prepared-root refresh. Once `gpt-5.5` auth is restored,
launch the warehouse v2 follow-up first, then the CVRP bounded large-twoopt
follow-up.
