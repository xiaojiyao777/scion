# V0.4 Postrun Analysis Brief Launcher Repair

Date: 2026-06-18

## Purpose

The next CVRP and warehouse runs are launch-prepared but blocked on the
`gpt-5.5` completion route. Once a run completes, the main session needs a
small, deterministic handoff artifact it can give to an experiment-analysis
subagent without re-explaining the full postrun protocol.

This repair adds `scion/tools/postrun_analysis_brief.py` and wires both agentic
launchers to write JSON and Markdown briefs under
`postrun_acceptance/analysis_brief/` before the final artifact inventory is
written.

## Boundary Check

- This is report-only postrun bookkeeping and delegation support.
- It does not change Proposal, Contract, Verification, Protocol, Decision,
  `DecisionFeatures`, lifecycle, scheduling, promotion, or problem semantics.
- The brief summarizes validity, required artifact paths, Phase 4 evidence
  coverage, and required analysis questions. It does not judge research quality.
- Tainted LLM traces, postrun diagnostics, and free-form analysis remain outside
  `DecisionFeatures`.

## Changed Behavior

When `POSTRUN_REPORTS=1`, the CVRP and warehouse launchers now generate:

- `postrun_acceptance/analysis_brief/*.postrun_analysis_brief.v1.json`
- `postrun_acceptance/analysis_brief/*.postrun_analysis_brief.md`

The artifact inventory now includes the `analysis_brief` report family, so the
final inventory can confirm that the delegation brief was generated.

Historical or manually launched runs can generate the same brief directly:

```bash
python scion/tools/postrun_analysis_brief.py --format markdown "$RUN_ROOT"
python scion/tools/postrun_analysis_brief.py --format json "$RUN_ROOT"
```

## Verification

```bash
PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py
python -m py_compile \
  scion/tools/postrun_analysis_brief.py \
  scion/tools/postrun_artifact_inventory.py \
  scion/tools/launch_cvrp_agentic_campaign.py \
  scion/tools/launch_warehouse_agentic_campaign.py
```

Result:

- `27 passed`
- `py_compile` passed
