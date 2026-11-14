# v0.4 Phase 4 Research-Continuity Coverage Repair

Date: 2026-06-18

## Purpose

`research_efficiency_report.v1.json` now exposes `research_continuity`, but the
postrun artifact inventory's Phase 4 evidence coverage still only checked the
older branch-lesson and effect-vs-MDE surfaces. Delegated postrun analysis could
therefore miss whether the explicit same-mechanism follow-up and lesson-transfer
metrics were actually present.

This repair adds `research_continuity` as a first-class Phase 4 coverage
requirement in `postrun_artifact_inventory`.

## Boundary

- Report-only: yes.
- Decision input: no.
- Mutates campaign, scheduler, lifecycle, Protocol, promotion, proposal
  context, or problem semantics: no.

The coverage flag only records whether postrun analysis has the audit artifact
needed to inspect same-mechanism follow-up, branch-lesson usage, and
weak-positive transfer.

## Changed Files

- `scion/tools/postrun_artifact_inventory.py`
- `scion/scion/tests/test_postrun_artifact_inventory.py`

## Verification

```bash
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py

python -m py_compile \
  scion/tools/postrun_artifact_inventory.py \
  scion/tools/postrun_analysis_brief.py \
  scion/tools/rebuild_postrun_acceptance.py
```

Result: `12 passed`.
