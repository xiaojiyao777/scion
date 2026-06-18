# v0.4 Postrun Failure Taxonomy Brief Repair

Date: 2026-06-18

## Purpose

TASK Phase 4 requires delegated postrun review to decide whether a result is a
framework/control regression, provider/infra failure, proposal/codegen/tool
failure, or algorithm-quality result. Research-efficiency reports already expose
`proposal_quality`, `failure_taxonomy`, compact `failures`, and run-status
fields, but the delegated analysis brief only listed this as a required
question.

This repair adds a report-only `failure_taxonomy_summary` to
`postrun_analysis_brief`.

## Boundary

- Report-only: yes.
- Decision input: no.
- Mutates campaign, scheduler, lifecycle, Protocol, promotion, proposal
  context, budgets, gates, or problem semantics: no.

The summary is derived only for current-run evidence. Prepared-only roots and
preflight-failed roots keep `current_run_evidence=false`, so copied resume
campaign failure artifacts are not treated as current-run postrun evidence.

## Summary Fields

- proposal attempts total/consumed;
- proposal quality blocks, ledger count, reports with blocks, and reason
  counts;
- failure taxonomy count maxima, observation counts, and source counts;
- run validity status and stop-reason counts;
- top sanitized failure examples from research-efficiency reports.

## Changed Files

- `scion/tools/postrun_analysis_brief.py`
- `scion/scion/tests/test_postrun_analysis_brief.py`

## Local Verification

```bash
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py

python -m py_compile \
  scion/tools/postrun_analysis_brief.py \
  scion/tools/postrun_artifact_inventory.py \
  scion/tools/rebuild_postrun_acceptance.py
```

Result: `12 passed`; py-compile clean.

Smoke check on an existing current-run PhaseB analysis root:

```bash
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion \
  python scion/tools/postrun_analysis_brief.py \
  /home/clawd/research/scion-experiments/v04-cvrp-baseline-strength-phaseB-analysis-20260614 \
  --format json
```

Observed `failure_taxonomy_summary.available=true`,
`current_run_evidence=true`, `failure_report_count=6`,
`proposal_attempts_total=49`, `proposal_attempts_consumed=48`, no proposal
quality blocks, and `run_validity_status_counts.valid=6`.
