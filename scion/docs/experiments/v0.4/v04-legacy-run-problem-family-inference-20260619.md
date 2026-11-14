# v0.4 Legacy Run Problem-Family Inference

Date: 2026-06-19

## Purpose

The warehouse champion-v2 validation-transfer run predates prepared-run
manifests. Rebuilding its postrun bundle with current tools previously allowed
`current_run_analysis_ready=true` while `warehouse_followup_summary` stayed
unavailable because `problem_family` was `None`. That hid exactly the warehouse
question v0.4 needs to answer: whether post-v2 follow-up is continuous useful
research, a real plateau, or an incomplete handoff.

## Change

- `postrun_artifact_inventory.py` now infers a missing legacy launched-run
  problem family from deterministic artifacts only:
  - `run.log` or `campaign/run.log` `Starting campaign: warehouse_delivery|cvrp`
    markers.
  - `campaign/weight_opt_v2` as a warehouse fallback.
- The prepared contract still reports `contract_complete=false` when
  `prepared_run_manifest.v1.json` is absent.
- The inferred fields are report-only:
  `problem_family_source`, `problem_family_inferred`, and
  `problem_family_inference_evidence`.
- Downstream postrun readiness now routes legacy warehouse/CVRP runs through the
  matching problem-specific summary checks instead of silently skipping them.

## Real-Run Evidence

Historical warehouse root inspected:

`/home/clawd/research/scion-experiments/v04-warehouse-validation-transfer-contract-rerun6r-ce5d884-20260617T152944Z/rep01/full_context`

Before rebuilding with the fix, the existing bundle now fails readiness instead
of being accepted:

```text
check_postrun_acceptance --require-current-run-ready rc=64
delegation_ready=True
current_run_analysis_ready=False
problem_summary_actionability=failed
expected_problem_family=warehouse_delivery
expected_summary=warehouse_followup_summary
reason=missing_problem_specific_summary
```

After rebuilding with current tools:

```text
rebuild_postrun_acceptance complete=1
check_postrun_acceptance --require-current-run-ready rc=64
warehouse_followup_summary.problem_family=warehouse_delivery
warehouse_followup_summary.available=True
warehouse_followup_summary.current_run_evidence=True
warehouse_followup_summary.handoff_complete=False
warehouse_followup_summary.interpretation=protocol_evaluated_handoff_incomplete
warehouse_followup_summary.evidence_gaps=[warehouse_handoff_requirements_incomplete]
champion_progress_summary.current_champion_version=2
champion_progress_summary.promotion_experiment_count=1
```

This is the desired fail-closed result: the old run remains useful evidence that
warehouse can promote to champion v2, but it cannot be used as a complete
post-v2 plateau or continuity conclusion without the current warehouse handoff.

## Verification

Local:

```bash
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion \
  pytest -q scion/scion/tests/test_check_postrun_acceptance.py
# 43 passed

PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion \
  pytest -q \
  scion/scion/tests/test_postrun_analysis_brief.py::test_warehouse_followup_summary_prepared_only_requires_launch \
  scion/scion/tests/test_postrun_analysis_brief.py::test_warehouse_followup_summary_marks_protocol_evaluated_plateau_review_ready
# 2 passed
```

WSL:

```bash
cd /home/xjy-ubuntu/research/or-autoresearch-agent
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/test_check_postrun_acceptance.py
# 43 passed
```

## Prepared Root Refresh

Because `scion/tools` is in the prepared-root runtime guard, the warehouse and
CVRP prepared roots were refreshed from WSL commit `266d4a8b`.

Warehouse:

`/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-legacyfamily-266d4a8b-preflight-6r-gpt55-20260619T221633Z-claw`

CVRP:

`/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-phase4-legacyfamily-266d4a8b-preflight-4r-gpt55-20260619T221634Z-claw`

WSL strict launch readiness for both roots:

```text
static_ready=True
launch_ready=False
completion_preflight=failed
http_status=401
classification=not_authenticated
code=invalid_api_key
auth_pool.active=0
auth_pool.expired=1
manifest.git.commit=266d4a8b
```

The roots were mirrored locally under `/home/clawd/research/scion-experiments/`.
Local mirror readiness is not launch-authoritative because prepared handoff
artifacts intentionally record WSL absolute paths; use WSL readiness for launch.

## Boundary Check

- This is report-only postrun evidence routing.
- It does not change Decision, `DecisionFeatures`, Protocol gates, lifecycle,
  scheduler, promotion, proposal selection, or solver semantics.
- CVRP/warehouse semantics remain problem-owned; the generic checker only routes
  to the appropriate report-only summary when deterministic runtime artifacts
  identify the problem family.

## Acceptance

Accepted as a v0.4 postrun auditability repair. Legacy launched runs can no
longer appear analysis-ready merely because they lack a prepared manifest and
therefore lack `problem_family`.
