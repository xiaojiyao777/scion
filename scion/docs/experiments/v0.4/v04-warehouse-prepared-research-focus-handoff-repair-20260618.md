# Warehouse Prepared Research-Focus Handoff Repair

Date: 2026-06-18
Branch: `codex/v04-evidence-repair-plan`

## Purpose

The warehouse champion-`v2` prepared follow-up already stated the broad goal:
test whether the accepted v0.4 positive research path can continue improving.
Its prepared manifest did not carry the concrete research focus needed for
delegated postrun analysis: what champion `v2` represents, what evidence is
required before calling the next run continuous improvement or plateau, and
which familiar false-plateau signals must be separated from protocol evidence.

This repair makes that warehouse focus explicit in prepared launch handoff
artifacts while keeping it report-only.

## Change

- `launch_warehouse_agentic_campaign.py` writes `research_focus` into the
  prepared run manifest with:
  - the accepted champion-`v2` checkpoint;
  - the post-`v2` continuous-improvement question;
  - required evidence for branch transfer, quality-block interpretation,
    split-preserving cost-compression telemetry, and warehouse runtime-model
    explanation;
  - default-avoid analysis mistakes such as restarting from baseline, treating
    proposal-quality blocks as plateau evidence, or treating
    `split_delta_sum==0` as no effect when `cost_delta_sum` is positive;
  - an explicit boundary statement that the focus must not enter
    `DecisionFeatures`, Protocol gates, promotion input, or scheduler state.
- `postrun_analysis_brief.py` and `postrun_artifact_inventory.py` render
  optional `accepted_checkpoint` and `required_evidence` fields when a prepared
  manifest includes research-focus metadata.

## Boundary

This is a warehouse/problem-owned launch and analysis-handoff repair. It
changes no Decision, Protocol, gate, lifecycle, scheduler, promotion, solver,
or warehouse operator behavior. The new fields are report-only prepared-root
metadata and are excluded from `DecisionFeatures`.

## Acceptance

- `PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q scion/scion/tests/test_warehouse_agentic_launcher.py scion/scion/tests/test_cvrp_agentic_launcher.py scion/scion/tests/test_postrun_artifact_inventory.py scion/scion/tests/test_launch_readiness.py`
  - Result: `33 passed`.
- `PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q scion/scion/tests/test_cvrp_agentic_launcher.py scion/scion/tests/test_warehouse_agentic_launcher.py scion/scion/tests/test_postrun_artifact_inventory.py scion/scion/tests/test_rebuild_postrun_acceptance.py scion/scion/tests/test_launch_readiness.py`
  - Result: `36 passed`.
- `python -m py_compile scion/tools/launch_warehouse_agentic_campaign.py scion/tools/postrun_artifact_inventory.py scion/tools/postrun_analysis_brief.py`
  - Result: passed.
- A temporary prepared warehouse root confirmed:
  - manifest `research_focus.scope=report_only_prepared_handoff`;
  - `Champion v2` appears in `accepted_checkpoint`;
  - `split_delta_sum==0` appears in default-avoid guidance;
  - prepared analysis brief JSON carries the same focus;
  - prepared analysis brief Markdown contains `Required evidence`;
  - prepared inventory Markdown contains `Prepared Research Focus`.

## Next

Regenerate the launch-prepared warehouse root from the synchronized WSL checkout
so the actual next warehouse launch root carries this research-focus handoff.
Launch remains blocked until
`check_launch_readiness.py <prepared-root> --completion-preflight` reports
`launch_ready=true`.
