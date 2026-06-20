# v0.4 Warehouse Missed Same-Mechanism Readiness Guard

Date: 2026-06-20

## Purpose

Warehouse v0.4 acceptance requires distinguishing a real post-v2 plateau from a
missed continuous-improvement opportunity. A plateau-ready problem summary must
therefore stay consistent with the current research-continuity review input,
including missed same-mechanism follow-up opportunities.

## Change

- `check_postrun_acceptance.py` now compares
  `warehouse_followup_summary.evidence.research_continuity.same_mechanism_missed`
  against the recomputed `research_continuity_summary` signal.
- Failure details now include summary/input `same_mechanism_missed` values for
  delegated review debugging.
- The guard remains report-only postrun readiness logic and does not affect
  Decision, `DecisionFeatures`, Protocol gates, scheduler state, promotion, or
  problem semantics.

## Verification

```bash
PYTHONPATH=scion python -m py_compile \
  scion/tools/check_postrun_acceptance.py \
  scion/scion/tests/test_check_postrun_acceptance.py
# clean

PYTHONPATH=scion pytest \
  scion/scion/tests/test_check_postrun_acceptance.py::test_postrun_acceptance_rejects_warehouse_plateau_ready_with_missed_same_mechanism -q
# 1 passed

PYTHONPATH=scion pytest scion/scion/tests/test_check_postrun_acceptance.py -q
# 67 passed

PYTHONPATH=scion pytest \
  scion/scion/tests/test_postrun_analysis_brief.py::test_warehouse_followup_summary_rejects_depth_only_unselected_same_mechanism \
  scion/scion/tests/test_postrun_analysis_brief.py::test_warehouse_followup_summary_requires_review_inputs_after_protocol_eval \
  scion/scion/tests/test_postrun_analysis_brief.py::test_warehouse_followup_summary_keeps_screened_only_out_of_plateau_review -q
# 3 passed
```

WSL after applying the same patch as commit `63b8b353`:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m py_compile \
  scion/tools/check_postrun_acceptance.py \
  scion/scion/tests/test_check_postrun_acceptance.py
# clean

PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest \
  scion/scion/tests/test_check_postrun_acceptance.py::test_postrun_acceptance_rejects_warehouse_plateau_ready_with_missed_same_mechanism -q
# 1 passed

PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest \
  scion/scion/tests/test_check_postrun_acceptance.py -q
# 67 passed
```

## Prepared Root Refresh

Current WSL prepared roots were regenerated from runtime commit `63b8b353` and
mirrored locally:

- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-size70hypctx-63b8b353-preflight-6r-gpt55-20260620T092950Z-claw`
- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-phase4-size70hypctx-63b8b353-preflight-4r-gpt55-20260620T092950Z-claw`

Strict launch readiness for both roots reports `static_ready=true`,
`launch_ready=false`, `failed_static_required_checks=[]`, and
`failed_required_checks=["completion_preflight"]`. The remaining blocker is the
external WSL `gpt-5.5` proxy auth response: HTTP `401`,
`classification=not_authenticated`, `code=invalid_api_key`, with auth pool
`active=0`, `total=1`.
