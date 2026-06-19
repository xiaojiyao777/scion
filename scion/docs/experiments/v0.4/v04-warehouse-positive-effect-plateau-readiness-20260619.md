# Warehouse Positive-Effect vs Plateau Readiness

Date: 2026-06-19

## Purpose

Tighten warehouse follow-up postrun review so a protocol-evaluated positive
effect at or above MDE cannot be mislabeled as
`protocol_evaluated_plateau_review_ready`.

## Change

- `warehouse_followup_summary.evidence.measurement_effect` now includes a
  deterministic measurement signal:
  `effect_signal`, `positive_effect_at_or_above_mde`,
  `plateau_consistent`, and `all_ci_high_below_mde`.
- Warehouse plateau-ready interpretation requires measurement to be
  plateau-consistent.
- Positive at-or-above-MDE warehouse evidence routes to
  `protocol_evaluated_positive_effect_review_ready`.
- Postrun acceptance recomputes the warehouse measurement signal from
  `measurement_effect_summary.aggregate` and rejects summaries whose
  interpretation disagrees with the review inputs.

All signals remain report-only postrun readiness evidence. They do not enter
Decision, `DecisionFeatures`, promotion, scheduler state, or solver semantics.

## Verification

Local command:

```bash
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q \
  scion/scion/tests/test_rebuild_prepared_handoff.py \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_check_postrun_acceptance.py
```

Result:

```text
159 passed in 40.26s
```

WSL command:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/test_rebuild_prepared_handoff.py \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_check_postrun_acceptance.py
```

Result:

```text
159 passed in 27.32s
```

## Prepared Roots

Because this repair touched `scion/tools`, the active prepared roots were
regenerated on WSL from runtime commit `be6cb8b5` and mirrored locally.

Warehouse WSL:

`/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-posplateau-be6cb8b5-preflight-6r-gpt55-20260619T232818Z-claw`

Warehouse local mirror:

`/home/clawd/research/scion-experiments/v04-warehouse-v2-followup-posplateau-be6cb8b5-preflight-6r-gpt55-20260619T232818Z-claw`

CVRP WSL:

`/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-phase4-posplateau-be6cb8b5-preflight-4r-gpt55-20260619T232819Z-claw`

CVRP local mirror:

`/home/clawd/research/scion-experiments/v04-cvrp-large-twoopt-phase4-posplateau-be6cb8b5-preflight-4r-gpt55-20260619T232819Z-claw`

Strict WSL launch readiness for both roots:

```text
static_ready=True
launch_ready=False
failed_required_checks=[completion_preflight]
failed_static_required_checks=[]
completion_preflight=failed
http_status=401
classification=not_authenticated
code=invalid_api_key
auth_pool.active=0
auth_pool.expired=1
auth_pool.refreshing=0
```

Live launch remains blocked until the WSL `gpt-5.5` completion preflight
succeeds.
