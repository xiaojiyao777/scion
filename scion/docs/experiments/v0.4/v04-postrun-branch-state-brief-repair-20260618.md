# v0.4 Postrun Branch State Brief Repair

Date: 2026-06-18

## Purpose

TASK Phase 4 requires delegated postrun review to inspect branch-level research:
branch depth, hypothesis state, event/decision shape, rollback/checkpoint
behavior, and whether a run did real research or only framework control work.
`postrun_artifact_inventory` already scopes branch, event, hypothesis, and LLM
trace counts to current-run evidence, but `postrun_analysis_brief` only exposed
branch ids/counts.

This repair adds a report-only `branch_research_state_summary` to
`postrun_analysis_brief`.

## Boundary

- Report-only: yes.
- Decision input: no.
- Mutates campaign, scheduler, lifecycle, Protocol, promotion, proposal
  context, budgets, gates, or problem semantics: no.

The summary is derived only for current-run evidence. Prepared-only roots and
preflight-failed roots keep `current_run_evidence=false`, so copied resume
campaign branch/event/hypothesis artifacts are not treated as current-run
postrun evidence.

## Summary Fields

- branch count, lineage count, branch-state counts;
- branches with hypotheses, events, sessions, traces;
- rollback total and branches with rollback;
- branch failure-code counts;
- hypothesis counts by status, action, and change locus;
- event counts by kind, decision, and stage;
- top sanitized branch rows with counts only.

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

Smoke check on an existing current-run CVRP agentic root:

```bash
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion \
  python scion/tools/postrun_analysis_brief.py \
  /home/clawd/research/scion-experiments/v04-cvrp-constructionpivot-guidance-f462133-local-agentic-1r-gpt55-20260618T075218Z-claw \
  --format json
```

Observed `branch_research_state_summary.available=true`,
`current_run_evidence=true`, `branch_count=1`, `lineage_count=1`,
`branch_state_counts.explore=1`, `events_by_kind.proposal_fail=1`, and
`events_by_kind.scheduler_result=1`.

## WSL Verification

After pushing commit `b483b361`, the WSL checkout fast-forwarded to the same
branch and passed the focused suite:

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

WSL smoke check on an existing current-run CVRP root:

```text
ROOT=/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-route-merge-pivot-guidance-agentic-1r-gpt55-20260618T031817Z-claw
available=true
current_run_evidence=true
branch_count=1
lineage_count=1
branch_state_counts=explore_expand=1
events_by_kind=agentic_proposal_session=2,decision=1,experiment=1,scheduler_result=2
top_branch=8b1621af-a5e2-4267-8245-1c521d316fc1
top_branch_state=explore_expand
```
