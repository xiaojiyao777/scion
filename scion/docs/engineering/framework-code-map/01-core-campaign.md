# Core Campaign

> Current boundary update (2026-09-21): the source-continuation, observation and reconcile
> sections below describe current direct-v3 code. Other sections retain the
> historical map's scope and must be checked against current source.

## Complete source continuation (current)

`cli/commands/init_run.py` accepts `--source-tree`, defaulting to the problem
root, and reads any problem-local registry from that tree. The initial
`ChampionState.code_snapshot_path` is the existing plain source input;
`campaign_composition.py` validates that the fresh output is outside it and uses
`WorkspaceMaterializer.create_champion_snapshot()` to copy it into the campaign.
The snapshot is read-only and an existing snapshot is never overwritten.
`CampaignManager` checks research-surface availability on the selected snapshot.
The adapter continues to own problem, feasibility and objective semantics.

No prior campaign state is loaded. Branches, stage counters and provider calls
start fresh; explicitly supplied `research_history` is ordinary H-only context.
Status reports `initial_source_tree`, `champion_source_tree` and the source path
of each live branch. These are locations, not authority or resume tokens.

## Problem-owned runtime observations (current)

`ProtocolResult.candidate_runtime_counters` replaces the seven fixed
operator/policy/construction/portfolio counter attributes. The Protocol
observation helper aggregates fields from existing problem telemetry
declarations; `evidence_recording/summary.py` carries the opaque mapping.
Raw pair diagnostics preserve scalar and event values without an algorithm
namespace allowlist. The host no longer infers `no_accepted_moves` as a failure.
Actual execution failure attribution, Safe Features and scientific gates are
unchanged. `evaluation_pipeline.py` excludes arbitrary problem counters from
held-out exposed summaries. Historical terminal artifacts are not migrated.

This is a bounded observation cleanup. The legacy `OperatorConfig` and
`ChampionState.operator_pool` configuration path remains separate debt.

## Scope / Sources

Sources read: `scion/scion/core/campaign.py`, `campaign_composition.py`, `campaign_loop.py`, `branch.py`, `branch_step_runner.py`, `explore_step_pipeline.py`, `evaluation_orchestrator.py`, `decision_finalizer.py`, `promotion_lifecycle.py`, `promotion_service.py`, `scheduler.py`, `campaign_governance.py`, `termination.py`, `workspace_lifecycle.py`, `models.py`, and CLI wiring in `scion/scion/cli/main.py`.

## Service Ownership

`CampaignManager` is the public runtime facade, not the place where most campaign behavior now lives. Its constructor calls `compose_campaign_services`, which installs runtime services and mutable campaign state on the manager. Backward-compatible properties in `CampaignManager` expose old attribute names while state is owned by services such as `ProblemRuntime`, `PlateauController`, and `AsyncWeightOptCoordinator`.

Key services installed by `campaign_composition.py`:

- `ProblemRuntime`: owns legacy `ProblemSpec`, optional adapter, and adapter-aware `ContextManager`.
- `BranchController`: owns branch state transitions and code hash bookkeeping.
- `Scheduler`: selects branch work through deterministic priority plus
  lifecycle/resource governance.
- `ProposalPipeline`: owns LLM proposal/code/fix calls.
- `ExploreStepPipeline`: owns Round 1/Round 2/contract/workspace/verification/screening.
- `EvaluationOrchestrator`: owns protocol execution glue and decision coordination.
- `DecisionFinalizer`: applies deterministic decision side effects.
- `PromotionLifecycleService` and `PromotionService`: prepare, persist, commit, stale-mark, and weight-optimize promoted champions.
- `EvidenceRecorder`, `LineageRegistry`, `ChampionStore`, `BranchStore`, `HypothesisStore`: persistence/evidence services.
- `CampaignGovernanceService`, `TerminationChecker`, `StagnationDetector`, `PlateauController`: stop/diversification policy.

## Outer Loop

`CampaignLoop.run()` in `scion/scion/core/campaign_loop.py` is the outer lifecycle:

1. Write initial `status.json`.
2. Until `effective_rounds_completed` reaches `max_rounds`, drain completed
   weight optimization events.
3. Ask `CampaignGovernanceService.should_stop()`.
4. Stop immediately if the LLM circuit breaker is tripped.
5. Run one branch step through `CampaignManager.run_one_step()`. Some steps are
   non-counted attempts with their own limits.
6. Write status with the last `StepResult`.
7. Run stagnation and soft-stagnation checks.
8. On loop exit, terminalize active branches only for max-round exhaustion.
9. Write `campaign_summary.json`, wait for weight optimization, drain again, rewrite summary/status.

The loop does not know proposal, evaluation, or promotion details. It depends on injected callbacks.

## Branch Stepping

`BranchStepRunner` in `scion/scion/core/branch_step_runner.py` is the branch dispatch boundary. It first drains weight-opt events and checks stop state, then ticks blocked infra branches, then asks `Scheduler.select_next()`.

Scheduler selection in `scion/scion/core/scheduler.py`:

1. High-priority formal work: `READY_FROZEN`, `READY_VALIDATE`, stale reconcile,
   and active validation/frozen/expand states are considered before ordinary
   research exploration.
2. Research branches are routed by pending retry/diagnostic repair,
   weak-positive follow-up, same-branch refinement sampling, runtime-evidence
   pressure, plateau/lifecycle reroute, same-mechanism requirements, clean
   research preference, and budgeted/fair selection.
3. New clean branches are admitted only through active-slot capacity policy.
   Scheduler may prefer a clean fork, report `at_capacity`, or rely on
   decision-origin park/reclaim metadata to exclude/reclaim low-value lineages
   from active-slot accounting.

`BLOCKED_INFRA` and parked/released lineages are not schedulable as ordinary
branch work. Pending retries still sort ahead inside some candidate pools and
ties use `updated_at`/`created_at`, but that is not the whole scheduling policy.
Treat active-slot, clean-fork, park/reclaim, and lifecycle routing as
resource/scheduling governance, not Decision-layer promotion/abandon logic.

## Branch State Model

Branch states and decisions are declared in `scion/scion/core/models.py`. Legal transitions are enforced by `BranchController` in `scion/scion/core/branch.py`:

- `CONTINUE_EXPLORE` keeps or returns a branch to `EXPLORE`.
- `EXPAND_SCREENING` moves to or remains in `EXPLORE_EXPAND`.
- `QUEUE_VALIDATE` moves screening successes to `READY_VALIDATE`.
- `schedule_branch()` advances `READY_VALIDATE` to `VALIDATING` and `READY_FROZEN` to `FROZEN_TESTING`.
- `EXPAND_VALIDATION` moves `VALIDATING` to `VALIDATING_EXPAND`.
- `QUEUE_FROZEN` moves validation successes to `READY_FROZEN`.
- `PROMOTE` is valid only from `FROZEN_TESTING`.
- `ABANDON` is allowed from any branch state.

`BranchController.next_stage()` maps branch state to experiment stage: explore states to screening, validating states to validation, and `FROZEN_TESTING` to frozen.

## Explore Path

`ExploreStepPipeline.run()` is the full candidate creation and first evaluation path:

1. Increment round and rounds-since-promote.
2. Generate or reuse a pending hypothesis.
3. Validate the hypothesis through `ContractGate.validate_hypothesis()`.
4. Generate code through `ProposalPipeline.generate_code()`.
5. Validate the patch through `ContractGate.validate_patch()`.
6. Create or reuse a workspace via `WorkspaceLifecycleService`.
7. Apply the patch, optionally syncing `registry.yaml`.
8. Run `VerificationGate`.
9. For light verification failures, attempt one LLM fix path.
10. Record verification pass and mark current hypothesis.
11. Defer if async weight optimization made the branch stale during explore.
12. Evaluate screening through `EvaluationOrchestrator`.
13. Apply decision through `DecisionFinalizer`.
14. Write a `StepRecord`.

Every early failure path writes a `StepRecord` with `decision=None` and a `failure_stage`, so proposal/code/contract/workspace/verification failures are visible in campaign summaries and future context.

`ProposalPipeline` now enforces two proposal-side research-boundary guards
before code generation. Forced-surface diagnostics still require the exact
declared surface/action/target. Separately, when a problem declares a
`solver_design` surface and no forced diagnostic is active, CVRP-style
problem-object hypotheses must keep `change_locus` on that active boundary.
APS tool context and final hypothesis prompts carry the same rule, and
completed APS outputs with failed schema/target/Contract self-check evidence
are converted to proposal failures before a patch reaches workspace
materialization.

Heavy verification failures usually blacklist the failed hypothesis as a
globally failed approach. `ExploreStepPipeline` treats declared
`solver_design` surfaces differently: a heavy failure under that top-level
problem-object boundary marks only the candidate implementation rejected, then
routes the branch failure normally. This preserves generic failure accounting
while preventing one invalid solver-design implementation from retiring the
whole problem-level research boundary.

## Eval-Only Path

Validation, validation expand, frozen, and screening expand reuse candidate workspaces via `BranchStepRunner.run_eval_step()`. This path expects branch workspace, hypothesis, patch, and canonical `HypothesisRecord` to exist. It then:

1. Runs `EvaluationOrchestrator.evaluate()`.
2. Increments round and budget/experiment counters through the orchestrator.
3. Applies decision through `DecisionFinalizer`.
4. Writes a `StepRecord` containing protocol result and decision reason codes.

Missing eval workspace/hypothesis is treated as an abandon/hard-abandon condition rather than silently passing.

## Stale and Reconcile

Promotion and weight optimization can stale active branches. `BranchController.mark_all_stale()` marks active non-frozen branches `STALE` after champion promotion. `mark_stale_for_weight_update()` marks selected active states `STALE_WEIGHT_UPDATE` after weight revision changes.

`BranchStepRunner.run_reconcile_step()` re-evaluates the complete accepted tree:

1. Copy the existing branch workspace into isolated staging, preserving every
   file and its problem-owned configuration. Do not apply archived patches or
   merge new champion code.
2. Carry the source's existing Contract acceptance; no new proposal is exported.
3. Run Verification against the new champion, retaining the single local
   candidate-content equality check before Protocol.
4. Run fresh screening through Protocol, Safe Features and Decision.
5. On continuation, `DecisionFinalizer` binds the accepted tree and the new
   comparison champion, resets expansion counts and applies the typed Decision.
   Expansion and held-out stages reuse that exact candidate.

The last accepted H/C remains ordinary evidence. `base_source_ref` points to the
branch head; `base_champion_version` records the new comparator. Missing source
or infrastructure yields a typed operational stop/hold without reconstruction.
Verification rejection cannot modify the prior clean tree. A failed scientific
screen can still keep the verified tree under `CONTINUE_EXPLORE`.

## Budget and Termination

There are several budget/stop layers:

- `BudgetState` tracks broad experiment budget and is consumed after protocol evaluation.
- `FrozenBudgetLedger` limits frozen uses per campaign.
- `TerminationChecker` stops on max experiments, wall clock, hard stagnation, no progress possible, or early stop.
- `CampaignGovernanceService` delays early stop when validation/frozen work is pending.
- Hard stagnation gets a one-time diversification escape before final termination.
- Soft stagnation forces a non-dominant locus through `PlateauController` instead of stopping.
- Circuit breaker stops after repeated LLM failures.
- API balance exhaustion sets campaign-level stop state through `ProposalPipeline`.

`max_rounds` and CLI `--rounds` use `effective_rounds_completed` as the budget
counter. They are not total loop steps and not proposal-attempt targets. Counted
formal candidate steps consume the budget; proposal-quality blocks,
telemetry/validation repair attempts, branch lifecycle policy blocks, reconcile
lifecycle steps, and scheduler active-slot blocks use separate counters and
limits. In status/summary artifacts, read `total_rounds` as a legacy/external
attempt surface and compare it with `campaign_steps`, `proposal_attempts_total`,
`proposal_attempts_consumed`, `formal_screened_candidates`, and
`protocol_evaluated_candidates` before interpreting run completeness.

The important boundary is that stop/go policy is centralized in governance/loop services; proposal/evaluation services report facts and failures rather than stopping the loop directly.
