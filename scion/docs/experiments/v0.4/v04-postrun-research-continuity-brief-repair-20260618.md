# v0.4 Postrun Research-Continuity Brief Repair

Date: 2026-06-18

## Purpose

`research_efficiency_report.v1.json` and postrun artifact inventories now expose
`research_continuity`, but delegated postrun analysis briefs still only showed
coverage availability. A reviewer could see that the continuity report existed
without seeing the actual same-mechanism, branch-lesson, weak-positive transfer,
and branch-shape counters that should guide the analysis.

This repair adds a report-only `research_continuity_summary` to
`postrun_analysis_brief` and adds a required delegated-analysis question for the
same surface.

## Boundary

- Report-only: yes.
- Decision input: no.
- Mutates campaign, scheduler, lifecycle, Protocol, promotion, proposal
  context, or problem semantics: no.

The summary is derived only from current-run
`postrun_acceptance/research_efficiency/*.json` reports. Prepared-only roots and
preflight-failed roots with copied resume snapshots keep
`current_run_evidence=false` and do not surface copied continuity metrics as
current-run research evidence.

## Changed Files

- `scion/tools/postrun_analysis_brief.py`
- `scion/scion/tests/test_postrun_analysis_brief.py`

## Verification

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

Result: `12 passed`.
