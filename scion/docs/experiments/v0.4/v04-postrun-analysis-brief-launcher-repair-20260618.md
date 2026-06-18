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

WSL prepared-root refresh on commit `3c21ab9` produced:

- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-postpivot-resume-ready-brief-1r-gpt55-20260618T120026Z-claw`
- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-ready-brief-6r-gpt55-20260618T120027Z-claw`

Both roots have top-level `prepared` status, completion preflight, expected
`control_pair_key`, `GIT_COMMIT=3c21ab9`, `bash -n` clean `run.sh`, guarded
analysis-brief JSON/Markdown commands, and direct brief JSON smoke coverage for
the `scion.postrun_analysis_brief.v1` schema.
