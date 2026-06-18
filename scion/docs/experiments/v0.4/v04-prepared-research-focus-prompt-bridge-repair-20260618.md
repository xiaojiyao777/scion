# Prepared Research Focus Prompt Bridge Repair

Date: 2026-06-18

## Problem

Prepared launch roots carried problem-owned `research_focus` in
`prepared_run_manifest.v1.json` and handoff reports, but hypothesis prompt
construction did not directly consume that manifest. A prepared root could pass
handoff readiness while the next agent still relied on older branch/context
signals instead of the current CVRP default-avoid, measurement-opportunity, or
warehouse champion-v2 follow-up focus.

This was a proposal-context gap, not a Decision or Protocol gap.

## Repair

- `ContextManager` now reads `PREPARED_RUN_MANIFEST` or
  `SCION_PREPARED_RUN_MANIFEST` when present and projects a bounded
  `launch_research_focus` payload into hypothesis context.
- `hypothesis_prompts` renders that payload inside `Compact Research Signals`.
- The payload is explicitly proposal-only, tainted, and excluded from
  `DecisionFeatures`.
- Prepared handoff readiness now audits the bridge through
  `prepared_research_focus_prompt_bridge`, checking both the manifest reader and
  prompt renderer markers.

## Launch Environment Export Repair

A follow-up audit of real WSL prepared roots found that `command.txt` included a
`PREPARED_RUN_MANIFEST` assignment, but the generated `run.sh` did not export
that variable. That made the bridge pass source-level tests while risking loss
of prepared focus in the real launched environment.

The CVRP and warehouse launchers now write `PREPARED_RUN_MANIFEST` into
`launch.env` and export it from generated `run.sh`. The prepared handoff audit
now requires both source markers and launch markers:

- source markers: manifest env reader, context payload, prompt renderer
- launch markers: prepared manifest exists, `launch.env` assignment, `run.sh`
  export

## Verification

Local:

```text
PYTHONPATH=scion pytest -q \
  scion/scion/tests/unit/test_hypothesis_context_profiles.py \
  scion/scion/tests/unit/test_research_surfaces_cvrp_context.py \
  scion/scion/tests/unit/test_agentic_solver_design_prompt_payloads.py \
  scion/scion/tests/unit/test_agentic_active_algorithm_facts_prompt.py \
  scion/scion/tests/unit/test_research_surfaces_generic_context.py \
  scion/scion/tests/test_rebuild_prepared_handoff.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py \
  scion/scion/tests/test_launch_readiness.py
```

Observed:

```text
101 passed
```

After adding the bridge readiness audit, focused local and WSL verification:

```text
PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_rebuild_prepared_handoff.py \
  scion/scion/tests/unit/test_hypothesis_context_profiles.py \
  scion/scion/tests/unit/test_research_surfaces_cvrp_context.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py \
  scion/scion/tests/test_launch_readiness.py
```

Observed locally:

```text
54 passed
```

Observed on WSL:

```text
54 passed
```

Focused launch-env export verification after the repair:

```text
PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py \
  scion/scion/tests/test_rebuild_prepared_handoff.py \
  scion/scion/tests/test_launch_readiness.py
```

Observed locally:

```text
35 passed in 2.75s
```

Observed on WSL:

```text
35 passed in 1.76s
```

## Prepared Roots

Current prepare-only roots were refreshed from WSL checkout `a0eb89b` after the
launch-env export repair.

CVRP:

```text
/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-postpivot-resume-ready-manifestenv-a0eb89b-1r-gpt55-20260618T222314Z-claw
```

Warehouse:

```text
/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-ready-manifestenv-a0eb89b-6r-gpt55-20260618T222325Z-claw
```

WSL strict readiness for both roots:

```text
static_ready=true
launch_ready=false
git_runtime_consistent=ok, checkout matches manifest commit at preparation time
HTTP 401, classification=not_authenticated
auth pool active=0 / expired=1 / refreshing=0 / total=1
```

Prompt readiness for both roots:

```text
ready_for_launch_prompt_audit=true
missing_required=[]
prepared_research_focus_prompt_bridge.available=true
prepared_research_focus_prompt_bridge.required=true
bridge markers:
  manifest_env_reader=true
  context_payload=true
  prompt_renderer=true
  prepared_manifest_exists=true
  launch_env_assignment=true
  run_sh_exports_manifest=true
```

No campaign was launched. Live launch remains blocked until the real
`gpt-5.5` chat completion preflight returns HTTP 200 with non-empty output.
