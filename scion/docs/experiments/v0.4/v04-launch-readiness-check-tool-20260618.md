# Launch Readiness Check Tool

Date: 2026-06-18

## Purpose

Make the next CVRP/warehouse prepared-root launch a single auditable decision
instead of a loose sequence of manual checks. The tool is intended for the
current v0.4 state where roots are prepared but live `gpt-5.5` completion
preflight is still the launch blocker.

## Change

Added `scion/tools/check_launch_readiness.py`.

The tool is report-only and reads the existing postrun inventory/contract
projection. It checks:

- prepared-only/not-started lifecycle,
- zero current-run counters,
- prepared-run contract completeness,
- runtime git guard consistency,
- expected postrun report families,
- `run.sh` syntax,
- automatic preflight-failure acceptance reporting,
- absence of `exit.txt` and `postrun_acceptance` on the launch root,
- optional real chat-completion preflight via `--completion-preflight`.

It reports both `static_ready` and `launch_ready`. `launch_ready` is true only
when `--completion-preflight` is required and succeeds.

CVRP and warehouse launchers now also write the static readiness report into
`prepared_handoff/launch_readiness/` when preparing a root. That artifact is a
handoff snapshot only; operators must rerun the tool with `--completion-preflight`
immediately before launch.

## Boundary Check

This tool does not change campaign state, scheduler state, promotion state,
Decision, `DecisionFeatures`, Protocol gates, budgets, lifecycle policy, or
problem semantics. It is a launcher/readiness guard for human/operator use.

## Verification

Focused local verification:

```bash
PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py
```

Result: `36 passed`.

Compile check:

```bash
python -m py_compile scion/tools/check_launch_readiness.py
```

Result: passed.

Static checks against the prepared CVRP and warehouse roots returned
`static_ready=true` and `launch_ready=false` with completion preflight skipped.
Requiring completion preflight correctly returned unready while the local proxy
still returned HTTP `401`.

## Operator Command

After re-login, require the real completion preflight before launching:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
/home/xjy-ubuntu/miniconda3/envs/scion/bin/python \
  scion/tools/check_launch_readiness.py \
  /home/xjy-ubuntu/research/scion-experiments/v04-cvrp-postpivot-resume-ready-preflightguard2-1r-gpt55-20260618T134635Z-claw \
  --completion-preflight \
  --format json
```

Launch only when `launch_ready=true`.
