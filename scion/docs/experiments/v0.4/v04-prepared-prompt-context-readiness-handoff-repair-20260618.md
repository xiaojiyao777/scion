# v0.4 Prepared Prompt/Context Readiness Handoff Repair

Date: 2026-06-18

## Purpose

Close the launch-preparation audit gap between strict static launch readiness
and the actual proposal-context evidence needed for delegated review. Before
this repair, a prepared root could prove that it was not started and that its
launcher contract was complete, but it did not have a dedicated handoff artifact
showing whether the next launch had the required prompt/context signal sources:
prepared research focus, copied campaign summary/status, problem-owned CVRP or
warehouse handoff fields, and the live `research_shape_diagnostics` prompt path.

This repair is report-only. It does not render raw provider prompts, mutate
campaign state, change `DecisionFeatures`, change gates, schedule branches, or
affect promotion.

## Change

- Added prepared handoff family `prompt_context_readiness` in
  `scion/tools/rebuild_prepared_handoff.py`.
- Added schema `scion.prepared_prompt_context_readiness.v1`.
- New JSON/Markdown outputs are written under:
  `prepared_handoff/prompt_context_readiness/`.
- The report records required, optional, and launch-time-generated signal
  sources. Required missing sources set
  `readiness.ready_for_launch_prompt_audit=false`; rebuild itself still remains
  a report-generation operation.
- CVRP required sources include prepared `research_focus`, copied
  campaign summary/status, measurement/opportunity handoff diagnostics,
  default-avoid directions, direct-effect rules, decision-boundary text, and
  current-checkout `research_shape_diagnostics` prompt markers.
- Warehouse required sources include prepared `research_focus`, copied
  campaign summary/status, champion-v2 follow-up framing, required evidence,
  default-avoid directions, decision-boundary text, and current-checkout
  `research_shape_diagnostics` prompt markers.
- CVRP and warehouse launchers now declare `prompt_context_readiness` in
  `prepared_handoff_families`, so newly prepared roots advertise the artifact.

## Boundary Check

- `decision_features_excluded=true`.
- `quality_judgment=false`.
- `campaign_state_mutated=false`.
- `scheduler_state_mutated=false`.
- `promotion_state_mutated=false`.
- `raw_provider_prompt_rendered=false`.
- Problem-specific semantics remain in launcher/prepared-manifest handoff fields
  and the report-only artifact; generic runtime Decision input is unchanged.

## Verification

Local:

```bash
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion \
python -m py_compile \
  scion/tools/rebuild_prepared_handoff.py \
  scion/tools/launch_cvrp_agentic_campaign.py \
  scion/tools/launch_warehouse_agentic_campaign.py

PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion \
pytest -q scion/scion/tests/test_rebuild_prepared_handoff.py

PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion \
pytest -q \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py

PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion \
pytest -q \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_launch_readiness.py
```

Results:

- `py_compile`: passed.
- `test_rebuild_prepared_handoff.py`: `1 passed`.
- CVRP/Warehouse launcher tests: `23 passed`.
- Postrun inventory/analysis brief/launch readiness tests: `27 passed`.

WSL focused verification after syncing the changed files:

```bash
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
/home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m py_compile \
  /home/xjy-ubuntu/research/or-autoresearch-agent/scion/tools/rebuild_prepared_handoff.py \
  /home/xjy-ubuntu/research/or-autoresearch-agent/scion/tools/launch_cvrp_agentic_campaign.py \
  /home/xjy-ubuntu/research/or-autoresearch-agent/scion/tools/launch_warehouse_agentic_campaign.py

cd /home/xjy-ubuntu/research/or-autoresearch-agent
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
/home/xjy-ubuntu/miniconda3/envs/scion/bin/python -m pytest -q \
  scion/scion/tests/test_rebuild_prepared_handoff.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py
```

Results:

- `py_compile`: passed.
- Focused WSL tests: `24 passed`.

## Prepared Root Rebuild Results

CVRP prepared root:

`/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-postpivot-resume-ready-shapesignal-2f620ee-1r-gpt55-20260618T210606Z-claw`

New handoff artifacts:

- `prepared_handoff/prompt_context_readiness/cvrp_on_full.prepared_prompt_context_readiness.v1.json`
- `prepared_handoff/prompt_context_readiness/cvrp_on_full.prepared_prompt_context_readiness.md`

Result:

- `ready_for_launch_prompt_audit=true`
- `missing_required=[]`
- Required CVRP sources all available.
- `copied_branch_snapshot` and `prompt_manifest_history` are optional and
  marked `runtime_generated_after_launch=true` because this prepared CVRP root
  has copied summary/status but no current branch list or prompt-manifest
  references yet.

Warehouse prepared root:

`/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-ready-shapesignal-2f620ee-6r-gpt55-20260618T210606Z-claw`

New handoff artifacts:

- `prepared_handoff/prompt_context_readiness/warehouse_on_full.prepared_prompt_context_readiness.v1.json`
- `prepared_handoff/prompt_context_readiness/warehouse_on_full.prepared_prompt_context_readiness.md`

Result:

- `ready_for_launch_prompt_audit=true`
- `missing_required=[]`
- Required warehouse sources all available.
- Copied branch snapshot is available with one branch in copied summary/status.

Static launch readiness remains true for both prepared roots. The runtime guard
paths exclude `scion/tools`, so adding the handoff family does not invalidate
the current `2f620ee` prepared roots. `check_launch_readiness.py --format json`
reports `static_ready=true` and
`git_runtime_consistent=ok` with detail
`checkout differs, but runtime guard paths are unchanged`.

## Residual Risk

This report does not prove that a live provider prompt will be good. It proves
that the prepared root has the required prompt/context signal sources before
launch and that missing launch-time-only sources are explicitly marked instead
of inferred. Live launch is still blocked until `gpt-5.5` completion preflight
returns a real non-empty chat completion.
