# v0.4 Launch Readiness Strict Launch Mode Repair

Date: 2026-06-18

## Purpose

`check_launch_readiness.py` already separated `static_ready` from
`launch_ready`, but its default CLI exit code still followed the static
readiness-style `ready` field when completion preflight was skipped. That is
useful for prepare-time handoff snapshots, but it is too easy for launch
automation or an operator to treat a static check as proof that a prepared root
is startable.

This repair adds an explicit strict launch mode for the final pre-launch check.

## Change

- Added `check_launch_readiness.py --require-launch-ready`.
- The flag implies `--completion-preflight`.
- In this mode, the CLI exits `0` only when `launch_ready=true`; otherwise it
  exits `64`.
- Completion-preflight `operator_action.rerun_command` now points to
  `--require-launch-ready --format json`.

Default static checks remain available for prepare-time report snapshots.

## Boundary Check

- Report-only readiness behavior.
- No campaign, scheduler, promotion, Protocol, Decision, `DecisionFeatures`,
  lifecycle, budget, or problem-semantic mutation.
- The stricter exit mode protects launch automation only; it does not act as a
  research-quality gate.

## Verification

Local:

```bash
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q \
  scion/scion/tests/test_launch_readiness.py
# 11 passed

PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py \
  scion/scion/tests/test_rebuild_prepared_handoff.py \
  scion/scion/tests/test_postrun_artifact_inventory.py
# 45 passed
```

WSL after fast-forwarding to `7308544`:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py \
  scion/scion/tests/test_rebuild_prepared_handoff.py \
  scion/scion/tests/test_postrun_artifact_inventory.py
# 45 passed
```

## Current Prepared Roots

Because this repair changes `scion/tools`, the previous `317cacb` prepared
roots are no longer the current launch targets. New roots were prepared from
checkout `7308544` without launching:

- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-postpivot-resume-ready-strictlaunch-7308544-1r-gpt55-20260618T192932Z-claw`
- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-ready-strictlaunch-7308544-6r-gpt55-20260618T192933Z-claw`

Both new roots have:

- `prepared_run_manifest.git.commit=7308544`
- prepared handoff rebuild `complete=true`
- prepared handoff rebuild `checkout_commit=7308544`
- `static_ready=true`
- `launch_ready=false` in the static prepared snapshot because completion
  preflight is intentionally skipped for prepare-time reports
- all CVRP/warehouse `problem_specific_requirements` available

Running strict launch readiness on both new roots currently returns exit `64`:

- `static_ready=true`
- `launch_ready=false`
- `ready=false`
- completion preflight `failed`
- `classification=not_authenticated`
- HTTP `401`
- login URL present

Launch remains blocked until the same command returns `launch_ready=true`:

```bash
scion/tools/check_launch_readiness.py <prepared-root> \
  --require-launch-ready \
  --format json
```

## Acceptance

Accepted as a Phase 4 launch-safety/auditability repair. The current prepared
roots are aligned to the latest guarded source, and the operator-facing launch
check now has a single exit-code-safe command for real start readiness.
