# Warehouse Guidance Binding And Launcher Status Repair

*Date: 2026-06-23*
*Scope: v0.4 framework/status repair; no Decision, Protocol, scheduler, solver,
or experiment-root mutation*

## Trigger

Current WSL warehouse positive-control root:

`/home/xjy-ubuntu/research/scion-experiments/v04-wh-v2-positive-65115459-current-8r-gpt55-20260623T084049Z-claw`

The run finished wrapper/postrun-ready, but only completed 1 effective round
from champion `v2` before stopping at `repeated_quality_block_signature`.
Postrun summary showed no actionability gap and substantive same-mechanism
continuity, but 5 proposal quality blocks. The blocking pattern was a contract
contradiction:

- Warehouse typed guidance ids such as `warehouse_champion_v2_checkpoint` and
  `validation_transfer_continuation` are research-context/evidence axes.
- Existing warehouse operator patches export runtime telemetry under concrete
  operator ids such as `operator_diagnostics.move_order.*`.
- The generic launch-focus projection treated typed guidance ids as hard
  `required_mechanism_ids`, while the warehouse telemetry-identity guard
  required concrete operator ids.

Thus either choice was blocked: concrete operator ids failed the required-id
guard, and context ids failed warehouse telemetry identity.

The same live checks also exposed an operator-facing lifecycle issue: during a
live run, root `run_status.json` remained `prepared/prepared_only=true` until
the campaign ended, even though `campaign/run_status.json` was already
`running`.

## Repair

Research guidance now distinguishes rendered context from hard hypothesis
binding:

- `RequiredMechanism.hypothesis_mechanism_binding` defaults to `required`.
- `context_only` mechanisms still serialize, render, and count for readiness
  path coverage.
- `launch_research_guidance_payload()["required_mechanism_ids"]` includes only
  mechanisms whose binding is `required`.
- Warehouse marks its three v2/validation-transfer/runtime handoff mechanisms
  as `context_only`.
- CVRP keeps `large_instance_intra_route_two_opt_seed` as the default
  hard-bound `required` mechanism.

Launcher status now has a shared running-status writer:

- `tools/write_launcher_running_status.py` writes root `run_status.json` as
  `status=running`, `prepared_only=false` after launch/auth/git/data-root
  guards pass and before completion preflight or campaign execution.
- CVRP and warehouse generated `run.sh` use the shared writer.
- postrun inventory treats running-status writer failure as a pre-campaign
  infra failure.

## Boundary

These repairs keep the v3 boundary intact. The generic layer sees only a
neutral binding enum and launcher lifecycle status. Warehouse/CVRP meaning
remains in problem-owned providers and validators. No raw problem diagnostics,
LLM text, telemetry rows, or launcher status enter `DecisionFeatures`.

## Tests

Local focused tests:

```bash
PYTHONPATH=scion python -m pytest -q \
  scion/scion/tests/test_launcher_running_status.py \
  scion/scion/tests/test_completion_preflight_status.py \
  scion/scion/tests/unit/test_research_guidance_contract.py \
  scion/scion/tests/unit/test_warehouse_research_guidance_provider.py \
  scion/scion/tests/unit/test_cvrp_research_guidance_provider.py \
  scion/scion/tests/unit/test_agentic_schema_hypothesis_surface.py::test_schema_preview_blocks_missing_launch_focus_required_mechanism \
  scion/scion/tests/unit/test_agentic_schema_hypothesis_surface.py::test_schema_preview_allows_launch_focus_required_mechanism \
  scion/scion/tests/test_cvrp_agentic_launcher.py::test_cvrp_agentic_launcher_prepare_writes_run_files \
  scion/scion/tests/test_warehouse_agentic_launcher.py::test_warehouse_agentic_launcher_prepare_writes_rewritten_run_files \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  -k 'launcher or infra or prepared_only or research_guidance or warehouse_provider or cvrp_research_guidance or required_mechanism or running_status or completion_preflight'
```

Result: `30 passed, 14 deselected`.

Broader focused set:

```bash
PYTHONPATH=scion python -m pytest -q \
  scion/scion/tests/test_launcher_running_status.py \
  scion/scion/tests/test_completion_preflight_status.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_warehouse_agentic_launcher.py \
  scion/scion/tests/unit/test_research_guidance_contract.py \
  scion/scion/tests/unit/test_warehouse_research_guidance_provider.py \
  scion/scion/tests/unit/test_cvrp_research_guidance_provider.py \
  scion/scion/tests/unit/test_agentic_schema_hypothesis_surface.py \
  scion/scion/tests/unit/test_agentic_session_hypothesis_preview_retry.py \
  -k 'launcher or running_status or completion_preflight or research_guidance or warehouse_provider or cvrp_research_guidance or required_mechanism or launch_focus_required_mechanism'
```

Result: `52 passed, 47 deselected`.

Additional checks:

- `PYTHONPATH=scion python -m pytest -q scion/scion/tests/test_postrun_artifact_inventory.py`
  -> `17 passed`.
- `PYTHONPATH=scion python -m py_compile ...` on changed tools/modules/tests.
- `git diff --check`.

## Next Use

Do not interpret the warehouse positive-control root as a real plateau. It is
current-run-ready evidence for the guidance-binding bug. After the live CVRP
solver-depth run finishes, synchronize the repaired checkout to WSL and rerun
the warehouse champion-`v2` positive-control path from a clean prepared root.
