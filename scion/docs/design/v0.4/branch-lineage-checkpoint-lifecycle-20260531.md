# Branch Lineage Checkpoint Lifecycle Design

Date: 2026-05-31  
Status: proposed design  
Scope: Scion generic branch lifecycle, checkpoint, rollback, and active branch
budgeting. Problem-specific diagnostics remain in problem packages/adapters.

## Evidence Inputs

This design follows the 12-round branch-governance validation:

- campaign:
  `/home/clawd/research/scion-experiments/v04-v3-branch-governance-gpt55-12r-20260531T135018Z-claw`
- analysis:
  `/home/clawd/research/scion-experiments/v04-v3-branch-governance-gpt55-12r-20260531T135018Z-claw/analysis/branch_governance_trace_analysis_12r.md`

The run showed that same-branch follow-up now happens, but regressed
refinements can still make the system treat "bad latest head" and "bad whole
lineage" too similarly.

## Context

The 12-round branch-governance recheck showed that Scion now behaves
branch-centrically: weak-positive, marginal, and no-effect heads receive
same-branch follow-up when appropriate, while new mechanisms use clean forks.
The remaining lifecycle ambiguity is not whether branches should continue, but
what exactly is abandoned when a follow-up regresses.

The clearest example is `f8b68af8`: the first head produced a useful
weak-positive signal, but a later same-branch refinement regressed. The current
system can checkpoint active weak-positive workspaces, but branch lifecycle is
still too coarse conceptually: a regressed head, the last useful checkpoint, and
the whole lineage are not the same object.

## Design Goals

- Preserve useful scientific information and code checkpoints when a lineage
  has shown real evidence.
- Avoid letting no-effect, marginal, or repeatedly regressed lineages consume
  all active branch capacity.
- Keep generic core independent of problem semantics. Scion may reason about
  evidence tiers, deltas, runtime, diagnostics, and lineage budgets; CVRP
  mechanism attribution and opportunity diagnostics belong in the CVRP package.
- Keep Decision evidence deterministic and auditable. Tainted proposal text may
  inform future prompts, but it must not directly control promotion.
- Make branch state explainable to future agents: current head health, best
  checkpoint health, rollback count, and allowed next actions should be visible.

## Non-Goals

- Do not change champion promotion criteria.
- Do not encode CVRP, route, customer, capacity, ALNS, or VNS semantics in the
  generic lifecycle controller.
- Do not retain every screened branch forever. Retention must be bounded by
  explicit lineage budgets.
- Do not hide failed refinements. A rollback restores code state, but the failed
  head remains auditable negative evidence.

## Terminology

- **Lineage**: the conceptual branch history rooted at a clean fork or promoted
  champion snapshot. A lineage may have multiple screened heads over time.
- **Head**: the current code workspace for a lineage.
- **Checkpoint**: a restorable screened code snapshot plus generic evidence
  summary. Checkpoints are not necessarily active heads.
- **Last-good checkpoint**: the best retained checkpoint according to generic
  evidence ordering.
- **Refinement head**: a same-lineage patch intended to improve the current
  head or last-good checkpoint.
- **Lineage abandon**: stop scheduling the lineage entirely.
- **Head abandon**: discard only the current regressed refinement head and
  restore or retain a previous checkpoint.

## Evidence Tiers

Generic evidence tiers should remain ordered but not overclaiming:

1. `promotable`: passed the formal promotion gate.
2. `weak_positive`: case wins exceed losses and confidence interval does not
   clearly cross negative support.
3. `marginal`: some positive signal but mixed or uncertain evidence.
4. `no_effect`: activated or valid but all-tie / zero-effect evidence.
5. `diagnostic`: telemetry/runtime/activation issue requiring repair or
   problem-package diagnosis.
6. `regression`: quality/runtime regression relative to champion or previous
   branch head.
7. `invalid`: contract, verification, runtime crash, or schema failure.

Only `promotable` changes champion. Other tiers shape branch lifecycle and
future proposal context.

## Checkpoint Selection

Scion should keep at most a small bounded checkpoint set per lineage:

- `best_quality_checkpoint`: best generic objective evidence, usually
  weak-positive or marginal.
- `best_runtime_checkpoint`: optional, only if quality is not worse and runtime
  evidence is confident.
- `last_valid_checkpoint`: most recent verified/screened valid head.

For v0.4, one `best_quality_checkpoint` plus one `last_valid_checkpoint` is
enough. The current filesystem checkpoint mechanism can evolve into this
explicit store.

Checkpoint metadata should include:

```yaml
BranchCheckpoint:
  checkpoint_id: string
  branch_id: string
  lineage_id: string
  parent_checkpoint_id: string|null
  workspace_ref: string
  patch_digest: string
  code_hash: string
  branch_code_status: string
  screening_tier: string
  evidence:
    wins: int
    losses: int
    ties: int
    median_delta: float|null
    ci_low: float|null
    ci_high: float|null
    runtime_ratio_median: float|null
    runtime_regression_rate: float|null
  diagnostics:
    gate_observation_reason_codes: [string]
    lifecycle_action_reason_codes: [string]
    telemetry_outcome: string|null
  counters:
    followup_count: int
    rollback_count: int
    stale_count: int
```

## Lifecycle Actions

Current binary "keep exploring vs soft abandon" should be refined into explicit
actions:

- `retain_head`: current head becomes the active lineage head.
- `retain_checkpoint`: current head is not active, but its evidence remains in
  branch-local memory.
- `rollback_to_checkpoint`: discard current regressed head and restore the
  best checkpoint as active.
- `park_lineage`: keep checkpoint/memory, remove from active scheduling until
  capacity or diagnostic conditions improve.
- `archive_lineage`: stop scheduling the lineage; keep audit artifacts.
- `clean_fork_required`: reject unrelated mechanism on a non-clean lineage and
  choose a clean fork instead.

`soft_abandon` should become a public umbrella reason, not the only internal
action.

## Rollback Policy

Rollback is appropriate when all are true:

- The lineage has a restorable checkpoint with better evidence than the current
  head.
- The current head is a same-branch refinement.
- The current head regressed by generic evidence:
  - losses materially exceed wins, or
  - median delta is negative, or
  - CI is non-positive, or
  - confident runtime regression violates objective policy, or
  - repeated no-effect diagnostic exceeded its retry limit.

Rollback should restore code and metadata to the checkpoint, then record:

- `rollback_count += 1`
- `last_regressed_head_ref`
- `rollback_reason_codes`
- `head_status=regressed_archived`
- `lineage_status=active_weak_positive`, `active_marginal`, or `parked`

Rollback should not silently erase the failed refinement. The failed head
remains useful negative evidence for future prompts.

## Lineage Budget

To control compute space, scheduling should use bounded budgets:

- `max_active_lineages`: existing active branch capacity.
- `max_checkpoints_per_lineage`: default 2.
- `max_rollbacks_per_lineage`: default 1 for no-effect/marginal, 2 for
  weak-positive.
- `max_same_mechanism_followups`: default 2 before forced park or clean fork.
- `max_no_effect_followups`: default 1 unless problem-package diagnostics
  identify a concrete repair focus.
- `max_marginal_followups`: default 1 unless evidence improves.
- `lineage_cooldown_rounds`: temporarily skip a parked lineage before retrying.

These budgets are generic and should be configurable. They must not encode
problem-specific mechanism names.

## Scheduling Priority

When choosing the next branch:

1. Required repair / pending retry / telemetry diagnostic repair.
2. Weak-positive lineage with remaining follow-up budget and no recent
   regression.
3. Restored checkpoint that has not yet received a post-rollback refinement.
4. Marginal lineage with concrete branch-local feedback and remaining budget.
5. No-effect lineage only if diagnostics name a specific integration/effect
   path or if active capacity would otherwise be unused.
6. Clean fork for new mechanism.
7. Parked lineage after cooldown, only if it has a useful checkpoint.

This prevents no-effect heads from occupying active capacity indefinitely while
still retaining their memory.

## Agent Context

Future APS prompts should expose a compact branch card:

```text
branch_id=<id>
lineage_status=active_weak_positive|active_marginal|active_no_effect|parked
current_head_status=<tier>
best_checkpoint_status=<tier>
rollback_count=<n>/<limit>
same_mechanism_followups=<n>/<limit>
last_regression_reason=<codes>
allowed_next_actions=tune|integrate|repair|parameterize|clean_fork
forbidden_next_actions=unchanged_repeat|unrelated_mechanism_on_same_branch
```

The prompt must distinguish:

- "This lineage is bad" from "the latest refinement was bad."
- "Checkpoint retained" from "current head retained."
- "No-effect diagnostic" from "weak-positive signal."

## Evidence And Reporting

Campaign summary and lineage should include:

- final active heads;
- parked lineages;
- archived lineages;
- checkpoint inventory;
- rollback events;
- per-lineage follow-up counts;
- best checkpoint evidence;
- current head evidence;
- reason-code groups:
  - `gate_observation_reason_codes`
  - `lifecycle_action_reason_codes`
  - `rollback_reason_codes`

Experiment analysis should be branch-centric by default after v0.4:

- reconstruct lineage;
- compare current head to best checkpoint;
- decide whether longer runs need more exploration or better diagnostics.

## Implementation Plan

### Phase 1: Schema And Reporting

- Add a generic `BranchCheckpointRecord` model or extend existing
  `BranchWorkspaceCheckpoint` into an auditable checkpoint registry.
- Add lineage counters to `Branch` or a sidecar store:
  - rollback count;
  - follow-up count;
  - no-effect/marginal/weak-positive streaks;
  - parked/cooldown state.
- Extend campaign summary with checkpoint inventory and current-vs-best head
  health.

### Phase 2: Rollback Semantics

- Replace "regressed weak-positive follow-up" special-case behavior with a
  generic `rollback_to_checkpoint` action.
- Support rollback for weak-positive and optionally marginal lineages; park
  no-effect lineages unless diagnostics are concrete.
- Preserve failed head artifacts as negative evidence.

### Phase 3: Scheduler Budgeting

- Teach scheduler to score lineages by evidence tier, checkpoint quality,
  remaining budget, cooldown, and recent regression.
- Prefer clean forks when active lineage slots are occupied by parked/no-effect
  heads.
- Keep existing exact decision gates unchanged.

### Phase 4: APS Branch Card

- Add branch card projection to hypothesis/code context.
- Ensure same-branch follow-up prompts cite best checkpoint and latest failed
  head separately.
- Keep problem-specific opportunity fields adapter-owned.

### Phase 5: Validation

Targeted tests:

- weak-positive checkpoint survives a bad refinement via rollback;
- marginal branch parks after failed follow-up;
- no-effect branch does not consume active capacity after diagnostic budget;
- clean fork is selected when all active branches are parked;
- failed refinement appears in branch-local memory but not as active head;
- current head and best checkpoint are distinct in summary.

Experiment sequence:

1. targeted synthetic lifecycle tests;
2. 4R smoke with forced same-branch regression;
3. 8R branch-governance run;
4. 16R run only if branch pool health remains interpretable.

## Open Decisions

- Whether marginal lineages get rollback or only park-after-failure.
- Default rollback/follow-up budgets.
- Whether checkpoint scoring should prefer non-negative CI over higher raw wins.
- How to age out old checkpoints when champion changes.
- Whether checkpoint workspace storage should be filesystem copy, patch replay,
  or content-addressed snapshot.

## Recommended Defaults

For v0.4:

- Keep at most two checkpoints per lineage.
- Roll back weak-positive once; second regression parks or archives.
- Marginal gets one follow-up; if it fails, park rather than archive if capacity
  allows.
- No-effect gets one diagnostic follow-up only when diagnostics are actionable;
  otherwise park.
- Archive a parked lineage when its checkpoint is older than the current
  champion revision or after repeated scheduler skips with no new evidence.
