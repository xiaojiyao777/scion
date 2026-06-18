# Postrun Analysis Brief Resume Snapshot Repair

Date: 2026-06-18

## Purpose

Keep delegated postrun analysis briefs aligned with the launch-root evidence
boundary: copied resume-campaign artifacts can be useful context, but they are
not current-run evidence for prepared-only or pre-campaign-preflight-failed
launch roots.

Inventory already moved copied campaign counts under `resume_snapshot`. The
analysis brief still exposed only the current-run top-level branch and LLM
trace summary, so reviewers could lose the explicit explanation of where copied
context went.

## Change

`postrun_analysis_brief.py` now includes the inventory `resume_snapshot` block
in JSON output and renders a Markdown `Resume Snapshot` section when copied
campaign artifacts are present.

The brief keeps current-run `branches` and `llm_traces` scoped to current-run
evidence. Copied branch, event, hypothesis, and LLM-trace counts stay under
`resume_snapshot` with `current_run_evidence=false`.

## Boundary Check

This is report-only handoff bookkeeping. It does not mutate campaign state,
scheduler state, promotion state, `DecisionFeatures`, Protocol evidence,
budgets, gates, lifecycle policy, or problem semantics.

## Verification

Focused local verification:

```bash
python -m py_compile \
  scion/tools/postrun_analysis_brief.py \
  scion/tools/postrun_artifact_inventory.py \
  scion/tools/rebuild_postrun_acceptance.py

PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py
```

Result: `12 passed`.

Focused WSL verification after syncing the same file set:

```bash
cd /home/xjy-ubuntu/research/or-autoresearch-agent

/home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m py_compile \
  scion/tools/postrun_analysis_brief.py \
  scion/tools/postrun_artifact_inventory.py \
  scion/tools/rebuild_postrun_acceptance.py

PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
/home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_rebuild_postrun_acceptance.py
```

Result: `12 passed`.

Real WSL preflight-failed smoke rebuild:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
/home/xjy-ubuntu/miniconda3/envs/scion/bin/python \
  scion/tools/rebuild_postrun_acceptance.py \
  /home/xjy-ubuntu/research/scion-experiments/v04-preflight-artifact-smoke-1r-gpt55-20260618T145653Z-claw \
  --report-stem cvrp_on_full \
  --observed-control-arm on \
  --control-pair-key cvrp.preflight-artifact-smoke:rep01 \
  --format json
```

Result:

- rebuild `complete=false`,
- current-run report families skipped with
  `pre_campaign_completion_preflight_failed`,
- analysis brief and inventory families written successfully.

Generated brief/inventory spot check:

- `brief.validity.run_validity_status=invalid_infra_only`,
- `brief.counters.effective_rounds_completed=0`,
- `brief.branches.count=0`,
- `brief.llm_traces.trace_count=0`,
- `brief.resume_snapshot.present=true`,
- `brief.resume_snapshot.current_run_evidence=false`,
- copied snapshot counts retained under `resume_snapshot`,
- Markdown contains `## Resume Snapshot` and says copied artifacts are not
  current-run evidence.

The new analysis-brief test covers a pre-campaign-preflight-failed launch root
with copied campaign DB rows and copied LLM traces. It asserts that current-run
branch and LLM-trace counts remain zero while the copied counts are present only
under `resume_snapshot` and Markdown states they are launch input, not
current-run evidence.
