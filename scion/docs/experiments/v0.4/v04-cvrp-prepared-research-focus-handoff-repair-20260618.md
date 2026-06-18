# CVRP Prepared Research-Focus Handoff Repair

Date: 2026-06-18
Branch: `codex/v04-evidence-repair-plan`

## Purpose

Prepared CVRP launch roots already told delegated reviewers to check whether
the next solver mechanism was materially different from rejected/default-avoid
directions, but the prepared manifest did not carry the actual current avoid
list or route-merge exception rule. That made the handoff depend on the reviewer
re-reading `TASK.md` and `current-state.md` correctly.

This repair makes the current CVRP research focus explicit in prepared launch
handoff artifacts while keeping it report-only.

## Change

- `launch_cvrp_agentic_campaign.py` writes `research_focus` into the prepared
  run manifest with:
  - the current default-avoid CVRP mechanism list;
  - the route-merge exception rule;
  - the construction-seed objective-effect rule;
  - an explicit boundary statement that the focus must not enter
    `DecisionFeatures`, Protocol gates, promotion input, or scheduler state.
- `postrun_artifact_inventory.py` preserves optional prepared-manifest
  `research_focus` in the prepared-run contract and renders it in inventory
  Markdown.
- `postrun_analysis_brief.py` renders the same optional focus in delegated
  analysis briefs.

## Boundary

This is a CVRP/problem-owned launch and analysis-handoff repair. It changes no
Decision, Protocol, gate, lifecycle, scheduler, promotion, or solver behavior.
The new fields are report-only prepared-root metadata and are excluded from
`DecisionFeatures`.

## Acceptance

- `PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q scion/scion/tests/test_cvrp_agentic_launcher.py scion/scion/tests/test_postrun_artifact_inventory.py scion/scion/tests/test_launch_readiness.py`
  - Result: `25 passed`.
- `PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q scion/scion/tests/test_cvrp_agentic_launcher.py scion/scion/tests/test_warehouse_agentic_launcher.py scion/scion/tests/test_postrun_artifact_inventory.py scion/scion/tests/test_rebuild_postrun_acceptance.py scion/scion/tests/test_launch_readiness.py`
  - Result: `36 passed`.
- `python -m py_compile scion/tools/launch_cvrp_agentic_campaign.py scion/tools/postrun_artifact_inventory.py scion/tools/postrun_analysis_brief.py`
  - Result: passed.
- A temporary prepared CVRP root confirmed:
  - manifest `research_focus.scope=report_only_prepared_handoff`;
  - `route-merge absorption` appears in `default_avoid_directions`;
  - prepared analysis brief JSON carries the same focus;
  - prepared analysis brief Markdown contains `Current research focus`;
  - prepared inventory Markdown contains `Prepared Research Focus`.

## Next

Regenerate the launch-prepared CVRP root from the synchronized WSL checkout so
the actual next launch root carries this research-focus handoff. Launch remains
blocked until `check_launch_readiness.py <prepared-root> --completion-preflight`
reports `launch_ready=true`.
