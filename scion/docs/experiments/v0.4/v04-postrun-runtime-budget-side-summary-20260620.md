# Postrun Runtime Budget Side Summary

Date: 2026-06-20
Branch: `codex/v04-evidence-repair-plan`

## Purpose

Make postrun runtime-budget diagnostics auditable for anytime solver runs by
preserving whether budget saturation came from the candidate, champion, both
sides, or only an observational budget-exhausting model.

## Issue

Protocol-level runtime budget diagnostics already carry `saturated_side` and
`repairable`, and champion-only saturation is not a candidate repair signal.
The postrun brief summary only aggregated code, severity, stage, and runtime
model counts. A delegated review could therefore see "runtime budget
saturation" without the side/repairability context needed to avoid misdirecting
agent repair toward the candidate.

## Repair

- `scion/tools/postrun_analysis_brief.py`
  - Adds `side_counts` and `repairable_counts` to
    `runtime_budget_diagnostics`.
  - Carries `saturated_side`, `repairable`, `candidate_saturated`, and
    `champion_saturated` in compact top diagnostics.
  - Renders runtime-budget side and repairability counts in markdown.
- `scion/scion/tests/test_postrun_analysis_brief.py`
  - Verifies a champion-only, budget-exhausting runtime diagnostic remains
    visible as `side_counts={"champion": 1}` and
    `repairable_counts={"false": 1}`.

## Boundary Check

This is report-only postrun evidence. It does not alter Protocol gates,
Decision, `DecisionFeatures`, scheduler state, promotion, or problem solver
semantics.

## Verification

Local:

```bash
PYTHONPATH=scion pytest -q scion/scion/tests/test_postrun_analysis_brief.py
PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_check_postrun_acceptance.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py
```

Results: `36 passed`, `73 passed`.

WSL:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_check_postrun_acceptance.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py
```

Result: `109 passed`.

## Prepared Roots

Because `scion/tools/postrun_analysis_brief.py` is covered by prepared runtime
guards, the previous prepared roots were superseded. New launch-authoritative
WSL commit: `fb03204b`. Corresponding local repair commit: `197ee67f`.

Warehouse:

`/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-size70hypctx-fb03204b-nocaps-aps0-sourceheadroom-codecap0-plannercap0-previewcap0-artifactcap0-reserve0-fullsurf-prompt96k-symbolcache-nonsolverfacts-focusitems-runtimebrief-preflight-6r-gpt55-20260620T144847Z-claw`

CVRP:

`/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-phase4-size70hypctx-fb03204b-nocaps-aps0-sourceheadroom-codecap0-plannercap0-previewcap0-artifactcap0-reserve0-fullsurf-prompt96k-symbolcache-nonsolverfacts-focusitems-runtimebrief-preflight-4r-gpt55-20260620T144847Z-claw`

Strict readiness for both roots reports `static_ready=true`,
`failed_static_required_checks=[]`, `prompt_context_readiness_complete=ok`,
`problem_specific_prepared_handoff=ok`, and `runtime_guard_commit_matches`.
The only required launch failure remains external `gpt-5.5` completion auth:
HTTP `401`, `classification=not_authenticated`, `code=invalid_api_key`.
