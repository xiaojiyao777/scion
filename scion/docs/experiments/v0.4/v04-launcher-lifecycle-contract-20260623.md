# v0.4 Launcher Lifecycle Contract Repair

*Date: 2026-06-23*
*Scope: Design J in `scion/design/v0.4-effective-research-repair-design.md`*

## Purpose

CVRP and warehouse launchers had converged on the same outer wrapper behavior:
load `launch.env`, resolve auth, guard the runtime checkout, write root running
status, run completion preflight, write the campaign execution marker, execute
`scion run`, rebuild postrun acceptance, and annotate final wrapper status.

The behavior was accepted, but it was duplicated inside two large launcher
scripts. Design J moves that outer lifecycle behind a typed generic
`LauncherLifecyclePlan` and deterministic renderer. Problem-owned launchers
still build the campaign command and any problem-specific pre-campaign guards.

## Boundary Check

- Generic lifecycle owns only operator/runtime wrapper semantics.
- CVRP forced target arguments remain in the CVRP command plan.
- Warehouse data-root validation remains a warehouse-owned
  `PreCampaignGuard`.
- No CVRP case ids, BKS/gap facts, warehouse operator ids, mechanism ids, raw
  calibration rows, scheduler state, Protocol inputs, promotion decisions, or
  `DecisionFeatures` are consumed by the lifecycle renderer.

## Implementation

- Added `scion/scion/launcher/lifecycle.py` with
  `CampaignCommandPlan`, `PreCampaignGuard`, `LauncherLifecyclePlan`, and
  `render_run_sh`.
- Updated `scion/tools/launch_cvrp_agentic_campaign.py` to construct the CVRP
  command plan and call the generic renderer.
- Updated `scion/tools/launch_warehouse_agentic_campaign.py` to construct the
  warehouse command plan and inject the warehouse data-root guard through
  `PreCampaignGuard`.
- Added `scion/scion/tests/test_launcher_lifecycle.py` for generic renderer
  order and marker coverage.

## Verification

Local focused checks, run with the available local Python environment because
the server does not have a conda environment named `scion`:

```bash
git diff --check
PYTHONPATH=scion python -m py_compile \
  scion/scion/launcher/__init__.py \
  scion/scion/launcher/lifecycle.py \
  scion/tools/launch_cvrp_agentic_campaign.py \
  scion/tools/launch_warehouse_agentic_campaign.py \
  scion/scion/tests/test_launcher_lifecycle.py
PYTHONPATH=scion python -m pytest -q \
  scion/scion/tests/test_launcher_lifecycle.py \
  scion/scion/tests/test_launcher_running_status.py \
  scion/scion/tests/test_completion_preflight_status.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py \
  -k 'launcher or running_status or completion_preflight'
PYTHONPATH=scion python -m pytest -q \
  scion/scion/tests/test_postrun_artifact_inventory.py
PYTHONPATH=scion python -m pytest -q \
  scion/scion/tests/test_launch_readiness.py \
  -k 'campaign_execution_marker or completion_preflight_enforced or postrun_reports_after_campaign or data_root_failure_reports or api_key_env_failure_reports'
```

Observed results:

- `git diff --check`: passed.
- `py_compile`: passed.
- Focused launcher/lifecycle tests: `33 passed`.
- Postrun artifact inventory: `17 passed`.
- Launch-readiness marker/order focused tests: `3 passed, 112 deselected`.

The broader launch-readiness completion-preflight tests were not accepted as a
pre-commit signal in the dirty local worktree because the prepared roots
correctly failed `git_runtime_worktree_clean` on the modified runtime guard
paths. Rerun those checks from a clean committed worktree before syncing to
WSL.

## WSL Status

The repair is not synced to WSL yet. The CVRP solver-depth run
`/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-solverdepth-65115459-postauthority-6r-gpt55-20260623T084213Z-claw`
is still running from WSL commit `65115459`; do not rsync runtime paths until
that run exits.
