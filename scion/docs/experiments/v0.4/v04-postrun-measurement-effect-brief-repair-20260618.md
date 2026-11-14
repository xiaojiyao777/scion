# v0.4 Postrun Measurement Effect Brief Repair

Date: 2026-06-18

## Purpose

TASK Phase 4 requires candidate evidence to be interpreted against A/A MDE and
case-level variance, not only aggregate win rate. Research-efficiency reports
already expose `measurement_readiness` and `protocol_effects_vs_mde`, and
postrun artifact inventory already checks that the report exists. The delegated
postrun analysis brief, however, only showed coverage availability and did not
summarize the effect-vs-MDE conclusion.

This repair adds a report-only `measurement_effect_summary` to
`postrun_analysis_brief`.

## Boundary

- Report-only: yes.
- Decision input: no.
- Mutates campaign, scheduler, lifecycle, Protocol, promotion, proposal
  context, or problem semantics: no.

The summary is derived only from current-run
`postrun_acceptance/research_efficiency/*.json` reports. Prepared roots and
preflight-failed roots with copied resume snapshots keep
`current_run_evidence=false`, so copied measurement/effect reports are not
misreported as current-run research evidence.

## Summary Fields

- measurement readiness status/reason/MDE;
- effect-vs-MDE interpretation;
- protocol row counts;
- rows at or above MDE;
- rows whose CI high is below MDE;
- max effect-to-MDE ratio;
- top sanitized effect rows without raw metrics refs.

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

Result: `12 passed`; py-compile clean.

WSL verification after fast-forwarding the synchronized checkout to
`54dc48d2`:

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
