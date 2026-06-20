# Screening Marginal Gate And Decision Alignment

Date: 2026-06-20
Branch: `codex/v04-evidence-repair-plan`

## Purpose

Align protocol screening-gate reporting with Decision routing for marginal
screening evidence. In v0.4, screening pass is a diagnostic validation
candidate, not promotion.

## Issue

Before this repair, high-win-rate screening evidence with non-negative but
sub-practical median delta could be reported by `screening_gate()` as
`unclear`/`SCREENING_DELTA_TOO_SMALL`, while `DecisionEngine` routed the same
shape to validation as `SCREENING_PASS_MARGINAL_DELTA`.

That drift made protocol reports and Decision outcomes disagree about the same
screening result. It was especially harmful for v0.4 research recovery because
low-SNR but non-negative solver-design ideas should be eligible for diagnostic
validation, while clearly negative effects must still fail closed.

## Repair

- `scion/scion/protocol/gates.py`
  - High win rate and practical median delta still returns screening `pass`.
  - High win rate with non-negative median delta below practical threshold now
    returns screening `pass` with `SCREENING_PASS_MARGINAL_DELTA`.
  - High win rate with negative median delta returns `unclear` with
    `SCREENING_INCONCLUSIVE_HIGH_WIN_NEGATIVE_EFFECT`.
- `scion/scion/tests/test_protocol_stats_gates.py`
  - Added regression coverage for marginal non-negative evidence and high-win
    negative median effect.

## Boundary Check

The repair is generic protocol accounting. It does not add CVRP, warehouse,
BKS, case gap, mechanism ranking, or prompt-derived data to `DecisionFeatures`.
Problem-owned measurement diagnostics remain proposal/context guidance or
readiness evidence only.

## Verification

Local:

```bash
PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_protocol_stats_gates.py \
  scion/scion/tests/test_decision_screening.py

PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_protocol_stats_gates.py \
  scion/scion/tests/test_protocol_failure_runtime.py \
  scion/scion/tests/test_protocol_surface_runtime.py \
  scion/scion/tests/test_decision_screening.py \
  scion/scion/tests/unit/core/test_branch_lifecycle_policy.py

PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_decision_feature_extraction.py \
  scion/scion/tests/unit/test_agentic_feedback_screening.py \
  scion/scion/tests/unit/test_runtime_feedback_guidance.py \
  scion/scion/tests/test_sprint_e2_context_runtime.py

PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_campaign_basics_continue.py \
  scion/scion/tests/test_campaign_screening_verification_run.py \
  scion/scion/tests/unit/core/test_decision_finalizer_lifecycle.py
```

Results: `92 passed`, `156 passed`, `54 passed`, `50 passed`.

WSL:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/test_protocol_stats_gates.py \
  scion/scion/tests/test_decision_screening.py \
  scion/scion/tests/test_protocol_failure_runtime.py \
  scion/scion/tests/test_protocol_surface_runtime.py \
  scion/scion/tests/unit/core/test_branch_lifecycle_policy.py \
  scion/scion/tests/test_decision_feature_extraction.py \
  scion/scion/tests/unit/test_agentic_feedback_screening.py \
  scion/scion/tests/unit/test_runtime_feedback_guidance.py \
  scion/scion/tests/test_sprint_e2_context_runtime.py \
  scion/scion/tests/test_campaign_basics_continue.py \
  scion/scion/tests/test_campaign_screening_verification_run.py \
  scion/scion/tests/unit/core/test_decision_finalizer_lifecycle.py
```

Result: `260 passed`.

## Prepared Roots

Because `scion/scion/protocol/gates.py` is a runtime-guard path, the previous
prepared roots were superseded. New launch-authoritative WSL commit:
`c6f4eac0`. Corresponding local repair commit: `6e59e5d5`.

Warehouse:

`/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-size70hypctx-c6f4eac0-nocaps-aps0-sourceheadroom-codecap0-plannercap0-previewcap0-artifactcap0-reserve0-fullsurf-prompt96k-symbolcache-nonsolverfacts-focusitems-gatesem-preflight-6r-gpt55-20260620T142827Z-claw`

CVRP:

`/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-phase4-size70hypctx-c6f4eac0-nocaps-aps0-sourceheadroom-codecap0-plannercap0-previewcap0-artifactcap0-reserve0-fullsurf-prompt96k-symbolcache-nonsolverfacts-focusitems-gatesem-preflight-4r-gpt55-20260620T142827Z-claw`

Strict readiness for both roots reports:

- `static_ready=true`
- `launch_ready=false`
- `failed_static_required_checks=[]`
- `failed_required_checks=["completion_preflight"]`
- `git_runtime_guard_commit_consistent=ok`
- `problem_specific_prepared_handoff=ok`
- `prompt_context_readiness_complete=ok`

The remaining blocker is external WSL `gpt-5.5` provider auth:
HTTP `401`, `classification=not_authenticated`, `code=invalid_api_key`,
auth pool `active=0`, `total=1`.

## Next Operator Step

Refresh the WSL `gpt-5.5` proxy login, then rerun:

```bash
PY=/home/xjy-ubuntu/miniconda3/envs/scion/bin/python
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  "$PY" /home/xjy-ubuntu/research/or-autoresearch-agent/scion/tools/check_launch_readiness.py \
  <prepared-root> --require-launch-ready --format json
```

Launch only after `launch_ready=true`.
