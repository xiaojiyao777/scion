# Campaign Entry And Outer Loop

## Scope

Current source reviewed:

- `scion/scion/cli/commands/init_run.py`
- `scion/scion/core/campaign.py`
- `scion/scion/core/campaign_composition.py`
- `scion/scion/core/campaign_loop.py`
- `scion/scion/core/branch_step_runner.py`
- `scion/scion/core/scheduler.py`
- `scion/scion/core/branch.py`
- `scion/scion/core/models.py`
- `scion/scion/core/step_result.py`

Engineering map used only as an index:

- `scion/docs/engineering/framework-code-map/01-core-campaign.md`

## Current Understanding

The active CLI path is `scion run` in `init_run.py`.

The command starts from legacy `problem.yaml`, then prefers `problem-v1.yaml`
when present. The v1 spec is bridged back into the legacy runtime shape while
also loading the problem adapter, metric specs, objective policy, and operator
execute signature. The CLI then constructs:

- `ExperimentProtocol`
- `VerificationGate`
- initial `ChampionState`
- `CampaignManager`

`CampaignManager` is mostly a public facade and compatibility layer. Its
constructor delegates service wiring to `compose_campaign_services`, and most
runtime behavior lives in injected services.

The outer loop is `CampaignLoop.run()`. It owns invocation-level lifecycle:
status writing, weight-opt drain, governance checks, circuit breaker checks,
branch-step dispatch, stagnation checks, and final summary/status writes.

`BranchStepRunner.run_one_step()` is the branch dispatch boundary. It performs
active-slot reconciliation, asks `Scheduler.select_next()`, then routes to one
of:

- create new branch then explore;
- existing explore branch;
- eval-only validation/frozen/screening-expand path;
- stale reconcile path;
- scheduler skip/capacity block.

`Scheduler` is no longer the simple v3 hard-priority/FIFO scheduler. It still
prioritizes ready validation/frozen/stale states, but v0.4 adds active-slot
capacity, weak-positive follow-up, runtime-evidence pressure, same-mechanism
follow-up, clean-fork routing, and low-value active-slot release/reclaim rules.

## Confirmed Boundary Notes

- `CampaignManager` delegates proposal/evaluation/promotion/evidence behavior
  instead of owning it directly.
- `CampaignLoop` does not inspect LLM output or protocol raw metrics. It works
  from `StepResult` accounting fields and stop/go callbacks.
- Branch transitions remain centralized in `BranchController`.

## Risks And Findings

### R-CORE-001 [P2] Scheduler documentation drift

The engineering map summarizes Scheduler as hard-priority plus FIFO, but current
source has a broader portfolio policy with active-slot and branch-lifecycle
routing. This is not necessarily a bug, but it means old docs are too compressed
to reason about current campaign behavior.

Evidence:

- `scion/scion/core/scheduler.py::Scheduler.select_next`
- `scion/scion/core/scheduling/*`

Impact:

- Run analysis can misinterpret why a branch was selected, parked, skipped, or
  replaced by a clean fork.
- Future changes to scheduler policy risk accidentally mixing proposal guidance,
  lifecycle policy, and resource accounting unless reviewed as a dedicated
  module.

Follow-up:

- Audit `core/scheduling/*` as its own module.
- Update the engineering map only after source-level review.

### R-CORE-002 [P2] Round-count terminology is operationally easy to misread

`CampaignLoop.run(max_rounds=...)` treats requested rounds as effective screened
rounds, not total loop iterations. Proposal quality blocks, telemetry repair,
validation repair, branch lifecycle policy blocks, stale reconcile steps, and
scheduler active-slot blocks have separate counters and limits.

Evidence:

- `scion/scion/core/campaign_loop.py::CampaignLoop.run`
- `scion/scion/core/step_result.py::StepResult`

Impact:

- Stopped or partial runs can look inconsistent if analyzed with the old
  assumption that `--rounds` means total branch steps.
- Status/summary fields must remain explicit about effective rounds versus
  proposal attempts and lifecycle attempts.

Follow-up:

- When auditing evidence/status, verify that `run_validity`,
  `campaign_summary.json`, and status projections preserve this distinction.

## Next Module Links

The main new-candidate path from this module is
`ExploreStepPipeline.run()`, covered in
[02-explore-step-pipeline.md](02-explore-step-pipeline.md).
