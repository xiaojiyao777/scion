# v0.4 Postrun Protocol Accounting Brief Repair

Date: 2026-06-18

## Purpose

TASK Phase 4 requires delegated postrun review to answer whether a run completed
enough formal candidates and protocol rows to support its requested effective
budget. Research-efficiency reports already expose `effective_budget`,
`attempts`, `protocol_rows`, `formal_candidates`,
`formal_candidate_artifacts`, `stage_rows`, and reconciliation fields, but the
delegated postrun analysis brief did not summarize those accounting surfaces.

This repair adds a report-only `protocol_accounting_summary` to
`postrun_analysis_brief`.

## Boundary

- Report-only: yes.
- Decision input: no.
- Mutates campaign, scheduler, lifecycle, Protocol, promotion, proposal
  context, budgets, gates, or problem semantics: no.

The summary is derived only for current-run evidence. Prepared-only roots and
preflight-failed roots keep `current_run_evidence=false`, so copied resume
campaign accounting artifacts are not treated as current-run postrun evidence.

## Summary Fields

- effective budget counter, requested/effective rounds, completion count, and
  stop reasons;
- proposal/verification attempt counts;
- protocol metric rows, evaluated candidates, effective protocol rounds, and
  protocol stage counts;
- formal screened/evaluated candidate counters and formal-candidate artifact
  row/index status;
- stage rows for screening, validation, frozen, and fresh-runtime replay;
- reconciliation status counts.

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

Observed `protocol_accounting_summary.available=true`,
`current_run_evidence=true`, `accounting_report_count=6`,
`requested_rounds=48`, `effective_rounds_completed=48`,
`protocol_metric_results=48`, `formal_candidate_artifacts.row_count=33`, and
`stage_rows.screening=48`.
