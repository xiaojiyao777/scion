# Launch Readiness Prompt/Context Guard Repair

Date: 2026-06-18

## Problem

`check_launch_readiness.py` verified prepared-root lifecycle, runtime guard,
`run.sh`, and completion preflight state, but did not require the
`prepared_handoff/prompt_context_readiness/*.json` artifact. A prepared root
could therefore be statically ready while prompt/context audit evidence was
missing, stale, or no longer matched `launch.env` and `run.sh`.

This was a launch control-plane gap, not a Decision, Protocol, scheduler, or
promotion gap.

## Repair

- Added required check `prompt_context_readiness_complete`.
- The check requires a prepared prompt/context readiness JSON artifact with
  `ready_for_launch_prompt_audit=true`, `missing_required=[]`, report-only
  boundary flags, no raw provider prompt rendering, and no campaign/scheduler or
  promotion mutation.
- The check requires
  `prepared_research_focus_prompt_bridge.required=true` and `available=true`.
- The check also rechecks live source and launch markers instead of trusting a
  stale artifact. Launch markers require `prepared_run_manifest.v1.json`,
  `launch.env` assignment, and `run.sh` export of `PREPARED_RUN_MANIFEST`.
- The check verifies artifact identity against the current prepared root and
  manifest: `run_root`, `prepared_manifest_path`, manifest commit, problem
  family, and model must match.

## Verification

Local:

```text
PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py \
  scion/scion/tests/test_rebuild_prepared_handoff.py
```

Observed:

```text
39 passed in 2.92s
```

WSL:

```text
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py \
  scion/scion/tests/test_rebuild_prepared_handoff.py
```

Observed:

```text
39 passed in 1.76s
```

## Prepared Roots

Current prepare-only roots were refreshed from WSL checkout `7f3028a`.

CVRP:

```text
/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-postpivot-resume-ready-identityguard-7f3028a-1r-gpt55-20260618T224522Z-claw
```

Warehouse:

```text
/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-ready-identityguard-7f3028a-6r-gpt55-20260618T224522Z-claw
```

Static readiness for both roots:

```text
static_ready=true
checks.prompt_context_readiness_complete.status=ok
git_runtime_consistent=ok, checkout matches manifest commit
launch_ready=false without completion preflight
```

Strict launch readiness for both roots:

```text
static_ready=true
launch_ready=false
HTTP 401, classification=not_authenticated
auth pool active=0 / expired=1 / refreshing=0 / total=1
```

No campaign was launched. Live launch remains blocked until the real
`gpt-5.5` chat completion preflight returns HTTP 200 with non-empty output.
