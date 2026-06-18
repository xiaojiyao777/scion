# v0.4 Postrun Prompt-Context Visibility Brief Repair

Date: 2026-06-18

## Purpose

The June 11 audits identify prompt/context degradation and source visibility as
remaining v0.4 risks: delegated reviewers need to know whether the agent saw the
research object, source/code surface, and useful research signal before judging
research quality.

Postrun artifact inventory already exposed `source_visibility` as a Phase 4
coverage requirement, and proposal trajectory manifests already store
sanitized prompt-manifest fingerprints. The postrun analysis brief, however,
did not summarize those fingerprints. A delegated reviewer could see that source
visibility evidence existed without seeing the prompt family balance,
visibility-ledger presence, omitted/truncated section counts, or prompt signal
density by family.

This repair adds a report-only `prompt_context_visibility_summary` to
`postrun_analysis_brief`. The summary includes:

- prompt manifest reference/load counts;
- visibility-ledger digest counts;
- block-family token and character totals;
- omitted/truncated section trace counts;
- prompt signal density for `research_signal`, `source_code`, `cross_branch`,
  and `governance` families;
- a report-only density interpretation such as whether governance token load
  exceeds research/source signal.

## Boundary

- Report-only: yes.
- Decision input: no.
- Mutates campaign, scheduler, lifecycle, Protocol, promotion, proposal
  context, or problem semantics: no.
- Raw prompt, raw response, and patch body exposure: no.

The summary is derived only from current-run
`postrun_acceptance/manifests/*.json` proposal trajectory manifests. Prepared
roots and preflight-failed roots with copied resume snapshots keep
`current_run_evidence=false`, so copied prompt/context fingerprints are not
misreported as current-run research evidence.

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

Result: `12 passed`; py-compile clean. The test fixture checks that signal
density is derived from sanitized family accounting and remains report-only and
outside `DecisionFeatures`.

WSL verification after fast-forwarding the synchronized checkout to
`a2aa48bc`:

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
