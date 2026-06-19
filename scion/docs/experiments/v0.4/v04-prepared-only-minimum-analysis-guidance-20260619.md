# v0.4 Prepared-Only Minimum Analysis Guidance

Date: 2026-06-19

## Purpose

Prepared launch roots should not show current-run branch, LLM, and Protocol
inspection instructions in their markdown analysis brief. The previous repair
separated prepared-only required answers from postrun research-quality answers,
but the markdown `Minimum Delegated Analysis` section still displayed the
current-run analysis checklist below the prepared-only stop instruction.

## Change

- Markdown minimum delegated-analysis guidance now branches by lifecycle.
- Prepared-only briefs ask reviewers to inspect prepared contracts,
  launch-readiness, prompt-context readiness, problem-specific prepared handoff,
  zero current-run counters, missing postrun acceptance evidence, and completion
  preflight operator status.
- Prepared-only briefs no longer show the current-run branch/LLM/Protocol
  inspection checklist before launch.
- Invalid infra-only and valid current-run briefs keep separate review guidance.

## Boundary Check

- This is report-only delegated-review guidance.
- It does not change Decision, `DecisionFeatures`, Protocol gates, lifecycle,
  scheduler, promotion, proposal selection, or problem solver semantics.
- It does not add budgets, truncation, compression, or generic gate tightening.

## Current Prepared Roots

WSL checkout: `270d21c`

- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-ready-270d21c-6r-gpt55-20260619T012731Z-claw`
- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-bounded-ready-270d21c-1r-gpt55-20260619T012732Z-claw`

Both roots are prepare-only and not started.

## Artifact Evidence

Both prepared analysis briefs now render:

- `Inspect prepared_run_contract, launch_readiness, prompt_context_readiness,
  and problem-specific prepared handoff.`
- `Confirm zero current-run counters and no postrun_acceptance evidence.`
- `Do not analyze copied campaign artifacts as current-run research evidence.`
- `If completion preflight failed, verify operator_action/login status and stop
  before launch.`
- `Decide whether the next action is launch-readiness recheck or launch.`

Neither prepared brief renders the current-run `Start branch-centric` or
`For valid runs, inspect target intent` instructions.

## Readiness Evidence

Both roots report:

- `static_ready=true`
- `launch_ready=false`
- `git_runtime_consistent=ok`
- `problem_specific_prepared_handoff=ok`
- `prompt_context_readiness_complete=ok`
- completion preflight `failed`
- HTTP `401`, `classification=not_authenticated`, `code=invalid_api_key`
- auth pool `active=0`, `total=1`; the non-active state may appear as expired
  or refreshing across repeated preflights

The current blocker remains external `gpt-5.5` auth, not prepared-root static
readiness.

## Verification

Local:

```bash
PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py \
  scion/scion/tests/test_rebuild_prepared_handoff.py \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py
# 70 passed
```

WSL:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py \
  scion/scion/tests/test_rebuild_prepared_handoff.py \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py
# 70 passed
```

## Acceptance

Accepted as the current prepared-root review and launch-readiness refresh. Once
`gpt-5.5` auth is restored and strict launch readiness reports
`launch_ready=true`, these are the current warehouse and CVRP roots to launch.
