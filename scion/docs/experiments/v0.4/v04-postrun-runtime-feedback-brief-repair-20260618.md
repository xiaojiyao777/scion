# v0.4 Postrun Runtime Feedback Brief Repair

Date: 2026-06-18

## Purpose

TASK Phase 4 requires postrun review to verify that runtime saturation and
fresh replay behavior did not pollute the research conclusion, especially for
CVRP-style `budget_exhausting` solvers. Artifact inventory already marked
`runtime_feedback` coverage, and research-efficiency reports already exposed
fresh runtime replay drain and stage-transition drain counters. The delegated
postrun analysis brief, however, did not summarize those fields.

This repair adds a report-only `runtime_feedback_summary` to
`postrun_analysis_brief`.

## Boundary

- Report-only: yes.
- Decision input: no.
- Mutates campaign, scheduler, lifecycle, Protocol, promotion, proposal
  context, budgets, gates, or problem semantics: no.

The summary is derived only for current-run evidence. Prepared-only roots and
preflight-failed roots keep `current_run_evidence=false`, so copied resume
campaign runtime artifacts are not treated as current-run postrun evidence.

## Summary Fields

- fresh runtime replay drain attempts, executed/skipped/blocked counts,
  protocol rows, statuses, and stop reasons;
- stage-transition drain attempts, executed/skipped counts, statuses, and stop
  reasons;
- runtime budget diagnostic source count, diagnostic count, code/severity/stage
  counts, and top sanitized diagnostics from campaign summary/status.

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

Observed `runtime_feedback_summary.available=true`,
`current_run_evidence=true`, `runtime_report_count=6`, and aggregate fresh
runtime replay drain `attempts=6`, `executed=0`, `skipped=6`,
`protocol_results=0`.

## WSL Verification

After fast-forwarding the synchronized WSL checkout to `03397f39`:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py

/home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m py_compile \
  scion/tools/postrun_analysis_brief.py \
  scion/tools/postrun_artifact_inventory.py \
  scion/tools/rebuild_postrun_acceptance.py
```

Result: `12 passed`; py-compile clean.

WSL smoke check on an existing warehouse postrun root:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python \
  scion/tools/postrun_analysis_brief.py \
  /home/xjy-ubuntu/research/scion-experiments/v04-warehouse-validation-transfer-contract-rerun6r-ce5d884-20260617T152944Z \
  --format json
```

Observed `runtime_feedback_summary.available=true`,
`current_run_evidence=true`, `runtime_report_count=1`, and aggregate fresh
runtime replay drain `attempts=1`, `skipped=1`, `protocol_results=0`.
