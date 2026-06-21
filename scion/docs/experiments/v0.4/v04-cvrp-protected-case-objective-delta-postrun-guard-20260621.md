# v0.4 CVRP Protected-Case Objective Delta Postrun Guard

Date: 2026-06-21

## Purpose

The CVRP bounded large-two-opt follow-up requires current-run CMT2/CMT4
case-level protection evidence. The previous postrun summary path could treat
shape-correct protected-case payloads with only feasibility, route count, case
names, or free-text continuity notes as enough to mark a bounded two-opt summary
review-ready. That was too weak: protected-case evidence must include numeric
objective or distance delta evidence.

## Repair

- `scion/tools/postrun_analysis_brief.py` now requires numeric objective,
  distance, cost, improvement, or delta-like evidence for protected CMT cases.
- Boolean, string, route-count-only, feasible-only, and generic case-name
  payloads no longer satisfy the protected-case evidence requirement.
- This stays in postrun/readiness interpretation. It does not add CVRP
  semantics to `DecisionFeatures`, promotion input, scheduler state, or core
  Scion decision logic.

Commits:

- Local: `5bc93f16 Require CVRP protected-case objective deltas`
- WSL: `13abbbef Require CVRP protected-case objective deltas`

## Evidence

Focused regression tests:

```text
PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_postrun_analysis_brief.py::test_cvrp_large_twoopt_summary_rejects_cmt_route_or_feasibility_only_evidence \
  scion/scion/tests/test_postrun_analysis_brief.py::test_cvrp_large_twoopt_summary_requires_cmt_case_protection_evidence \
  scion/scion/tests/test_postrun_analysis_brief.py::test_cvrp_large_twoopt_summary_marks_bounded_twoopt_review_ready
3 passed

PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_check_postrun_acceptance.py::test_postrun_acceptance_rejects_cvrp_ready_summary_with_cmt_route_only_input \
  scion/scion/tests/test_check_postrun_acceptance.py::test_postrun_acceptance_rejects_cvrp_ready_summary_with_seed_family_input \
  scion/scion/tests/test_check_postrun_acceptance.py::test_postrun_acceptance_rejects_cvrp_ready_summary_with_cross_route_twoopt_star_phase
3 passed
```

Full affected local suites:

```text
PYTHONPATH=scion pytest -q scion/scion/tests/test_postrun_analysis_brief.py
39 passed

PYTHONPATH=scion pytest -q scion/scion/tests/test_check_postrun_acceptance.py
83 passed

PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_launch_readiness.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_rebuild_prepared_handoff.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_check_postrun_acceptance.py
270 passed
```

WSL verification after rsync:

```text
PYTHONPATH=scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_check_postrun_acceptance.py
122 passed
```

## Prepared Roots

Because the repair touched `scion/tools`, launch-authoritative prepared roots
were regenerated on WSL from runtime commit `13abbbef` and mirrored back for
inspection.

- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-wh-v2-13abbbef-resumecont-6r-gpt55-20260621T030244Z-claw`
- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-twoopt-13abbbef-resumecont-4r-gpt55-20260621T030244Z-claw`

Strict launch readiness for both roots:

- `static_ready=true`
- `launch_ready=false`
- `failed_static_required_checks=[]`
- `failed_required_checks=["completion_preflight"]`
- `runtime_guard_status=ok`
- `prepared_runtime_commit=13abbbef`
- WSL HEAD may include later docs-only status commits after prepare; strict
  readiness accepts that only when guarded runtime paths are unchanged since
  prepare
- `completion_http_status=401`
- `completion_classification=not_authenticated`
- `completion_code=invalid_api_key`
- auth pool: `active=0`, `total=1`; expired/refreshing substate is volatile
  and should not be used as an operational distinction unless active auth
  becomes available

Do not launch either root until strict readiness on WSL reports
`launch_ready=true`.
