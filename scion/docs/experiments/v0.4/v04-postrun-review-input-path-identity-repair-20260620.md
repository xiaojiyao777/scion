# v0.4 Postrun Review-Input Path Identity Repair

Date: 2026-06-20

## Purpose

Close a narrow stale-evidence gap in postrun acceptance. Review-input summary
consistency already recomputed aggregate and entry detail from current
research-efficiency reports, but its comparison removed every `path` field to
avoid local/WSL absolute-path drift. That allowed a shape-correct summary entry
to keep an old run-root path without being distinguished from the current run.

## Change

- `scion/tools/check_postrun_acceptance.py`
  - Preserve `path` fields during summary comparison as a normalized tail
    signature instead of dropping them.
  - The signature uses the final four path components, so local and WSL mirrors
    with the same run-root basename still compare equal while old run roots or
    stale artifact names fail.
- `scion/scion/tests/test_check_postrun_acceptance.py`
  - Added a regression that rewrites a protocol-accounting entry path to a
    stale run root while leaving the rest of the summary current. Readiness now
    fails with `protocol_accounting_summary_entries_mismatch`.

## Boundary Check

This is a report-only postrun readiness check. It does not change Protocol,
Decision, `DecisionFeatures`, scheduler behavior, proposal context, or solver
semantics. The v3 boundary remains intact: delegated review receives stronger
current-run evidence validation, while deterministic promotion and abandonment
logic remain unchanged.

## Verification

Local:

```bash
PYTHONPATH=scion pytest -q scion/scion/tests/test_check_postrun_acceptance.py
PYTHONPATH=scion pytest -q scion/scion/tests/test_postrun_analysis_brief.py scion/scion/tests/test_rebuild_postrun_acceptance.py scion/scion/tests/test_check_postrun_acceptance.py
git diff --check
```

Results:

- `68 passed`
- `110 passed`
- `git diff --check` passed

WSL:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py \
  scion/scion/tests/test_check_postrun_acceptance.py
```

Result:

- `110 passed`
