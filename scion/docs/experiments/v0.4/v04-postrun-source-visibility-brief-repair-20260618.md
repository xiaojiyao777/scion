# v0.4 Postrun Source Visibility Brief Repair

Date: 2026-06-18

## Purpose

TASK Phase 4 requires code-phase prompts to preserve direct visibility of the
champion/current-branch/target source needed to modify or judge the research
object. Prompt manifests already record `code_phase_source_guarantees`,
`code_file_visibility_ledger`, and
`hypothesis_target_source_visibility_ledger`, but postrun delegated analysis
only saw prompt-family token density and omitted/truncated section counts.

This repair carries compact source-visibility fingerprints into
`proposal_trajectory_manifest` traces and aggregates them in
`postrun_analysis_brief`.

## Boundary

- Report-only: yes.
- Decision input: no.
- Mutates campaign, scheduler, lifecycle, Protocol, promotion, proposal
  context, budgets, gates, or problem semantics: no.
- Raw prompts, raw responses, patch bodies, and source bodies are excluded.

The new fields summarize booleans, status counts, source-category counts, and
missing required source paths. They do not expose raw source text.

## Summary Fields

- Code-phase target/protected/required-integration/algorithm-read source visible
  counts.
- Code-phase missing target/protected/required-source trace counts.
- Code target source-status and prompt-visibility status counts.
- Hypothesis target source trace/required/visible/not-visible counts.
- Hypothesis target source visibility-status counts.

## Changed Files

- `scion/scion/core/proposal_trajectory_artifacts.py`
- `scion/tools/postrun_analysis_brief.py`
- `scion/scion/tests/test_proposal_trajectory_artifacts.py`
- `scion/scion/tests/test_postrun_analysis_brief.py`

## Local Verification

```bash
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q \
  scion/scion/tests/test_proposal_trajectory_artifacts.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py

python -m py_compile \
  scion/scion/core/proposal_trajectory_artifacts.py \
  scion/tools/postrun_analysis_brief.py \
  scion/tools/postrun_artifact_inventory.py \
  scion/tools/rebuild_postrun_acceptance.py
```

Result: `29 passed`; py-compile clean.

The local experiment archive does not currently contain a real
`agentic_sessions/prompt_manifests/*.json` sample for a live smoke. The focused
tests construct sanitized hypothesis/code prompt manifests and verify both the
trajectory fingerprint and postrun brief aggregation paths.

## WSL Verification

After pushing commit `3c2cbd3a`, the WSL checkout fast-forwarded to the same
branch and passed the focused suite:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  /home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/test_proposal_trajectory_artifacts.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py

/home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m py_compile \
  scion/scion/core/proposal_trajectory_artifacts.py \
  scion/tools/postrun_analysis_brief.py \
  scion/tools/postrun_artifact_inventory.py \
  scion/tools/rebuild_postrun_acceptance.py
```

Result: `29 passed`; py-compile clean.

The WSL experiment archive also did not contain a real
`campaign/agentic_sessions/prompt_manifests/*.json` sample for a live smoke, so
the WSL verification is limited to the focused generated-manifest and brief
aggregation tests.
