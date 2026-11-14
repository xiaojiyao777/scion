# Decision Finalizer

## Scope

Current source reviewed:

- `scion/scion/core/decision_finalizer.py`
- selected call sites in `campaign.py`, `branch_step_runner.py`,
  `explore_step/pipeline.py`, and `campaign_composition.py`
- selected lineage code in `evidence_recording/lineage.py`
- selected lifecycle policy code in `branch_lifecycle_policy.py`
- selected promotion path code in `promotion_lifecycle.py` and
  `promotion_service.py`
- selected tests in:
  - `scion/scion/tests/unit/core/test_decision_finalizer_lifecycle.py`
  - `scion/scion/tests/unit/core/test_decision_finalizer_park_lifecycle.py`
  - `scion/scion/tests/unit/core/test_decision_finalizer_rollback_lifecycle.py`
  - `scion/scion/tests/test_campaign_success_contract.py`
  - `scion/scion/tests/test_campaign_summary_promote.py`

## Current Understanding

`DecisionFinalizer.apply(...)` is the side-effect boundary after
`EvaluationOrchestrator` and `DecisionEngine` have produced a `Decision`,
reason codes, and optionally a lifecycle action.

High-level flow:

```text
decision + reason codes + lifecycle action
  -> normalize effective reason codes / lifecycle action
  -> pre-sync terminal evidence for ABANDON
  -> prepare promotion plan for PROMOTE
  -> record decision lineage
  -> apply branch/workspace/hypothesis side effects
  -> return StepResult with loop-accounting flags
```

The main paths are:

- `PROMOTE`: prepare promotion before lineage, commit promotion, record lineage
  after commit, and return a promoted `StepResult`.
- `CONTINUE`: record lineage, then update lifecycle evidence, branch status,
  workspace/checkpoint state, hypothesis status, and branch-controller state.
- `ABANDON`: sync terminal branch evidence before lineage, record lineage, then
  archive/clean workspace and remove the active branch from campaign maps.

`DecisionFinalizer` does not run policy. It interprets already-decided actions
such as `retain_head`, `park_lineage`, `rollback_to_checkpoint`, and telemetry
repair lifecycle actions.

## Positive Boundary Observations

- The finalizer is mostly a side-effect applier. Policy ownership remains in
  `DecisionEngine` / `BranchLifecyclePolicy`, with the finalizer receiving
  `decision`, `reason_codes`, and `lifecycle_action`.
- Terminal abandon evidence is explicitly synchronized before lineage is
  recorded. Tests cover this ordering.
- Promotion prepare and commit failures return `decision=None` and avoid
  advancing the champion in the tested failure paths.
- Retain, park, rollback, and telemetry-repair lifecycle paths have focused
  unit coverage.
- Legacy lifecycle reason codes alone do not trigger lifecycle side effects.
  This avoids accidental parking/retention from diagnostic text alone, though
  it creates the side-channel risk recorded below.

## Risks And Findings

### F-FINALIZER-001 [P1] Lifecycle archive/soft-abandon accounting depends on pre-finalizer branch state

Older campaign-level soft abandon explicitly avoids incrementing the hard
abandon counter. The lifecycle policy can still map soft lifecycle outcomes to
`Decision.ABANDON`. `DecisionFinalizer.apply(...)` has a compatibility branch
that returns `action="soft_abandon"` if the branch controller already reports
the branch as `ABANDONED`; otherwise it falls through to `_abandon(...)`, where
hard-abandon accounting is unconditional.

Evidence:

- `scion/scion/core/campaign.py:672`
- `scion/scion/core/campaign.py:683`
- `scion/scion/core/campaign.py:707`
- `scion/scion/core/campaign.py:716`
- `scion/scion/core/branch_lifecycle_policy.py:116`
- `scion/scion/core/branch_lifecycle_policy.py:119`
- `scion/scion/core/decision.py:355`
- `scion/scion/core/decision.py:365`
- `scion/scion/core/evaluation_orchestrator.py:179`
- `scion/scion/core/evaluation_orchestrator.py:185`
- `scion/scion/core/decision_finalizer.py:208`
- `scion/scion/core/decision_finalizer.py:224`
- `scion/scion/core/decision_finalizer.py:717`
- `scion/scion/core/decision_finalizer.py:720`

Why this matters:

- `soft_abandon`, `park_lineage`, and `archive_lineage` are lifecycle/archive
  concepts, not necessarily hard evidence that the campaign should terminate for
  repeated hard abandon.
- The previous `_apply_soft_abandon(...)` path states that soft abandon is
  intentionally not counted in `_recent_abandoned_count`.
- `EvaluationOrchestrator` stores lifecycle action as metadata, but it does not
  pre-apply branch-controller abandon state. The finalizer therefore depends on
  another path having already marked the branch abandoned before `apply(...)`
  runs if it wants the soft-abandon return branch.
- The finalizer-level abstraction still collapses a lifecycle-derived
  `Decision.ABANDON` into hard abandon accounting when that pre-abandoned state
  is absent.

Impact:

- Low-signal lifecycle archival can potentially trip stagnation or termination
  controls intended for hard abandons.
- The audit trail loses a clean accounting distinction between hard terminal
  rejection and lifecycle archival.

Suggested fix direction:

- Make abandon accounting lifecycle-aware in `DecisionFinalizer._abandon(...)`.
- Treat `lifecycle_action="archive_lineage"` as the source of truth for soft
  archival semantics instead of relying on pre-finalizer branch-controller
  state.
- If current design intentionally treats lifecycle archive as hard abandon,
  update the naming and docs so `soft_abandon`/`archive_lineage` do not imply
  weaker accounting.
- Add a regression test for lifecycle `archive_lineage` or `soft_abandon` that
  asserts the expected hard-abandon counter behavior.

### F-FINALIZER-002 [P2] Continue-path lineage is recorded before finalizer lifecycle mutations

For non-promote decisions, `DecisionFinalizer.apply(...)` records lineage before
calling `_continue_explore(...)`. `_continue_explore(...)` then mutates branch
evidence and lifecycle state: screening feedback, telemetry repair metadata,
branch code status, active/parked state, mechanism ids, zero-win streaks,
hypothesis status, and branch-controller state.

Evidence:

- `scion/scion/core/decision_finalizer.py:167`
- `scion/scion/core/decision_finalizer.py:178`
- `scion/scion/core/decision_finalizer.py:180`
- `scion/scion/core/decision_finalizer.py:191`
- `scion/scion/core/decision_finalizer.py:366`
- `scion/scion/core/decision_finalizer.py:421`
- `scion/scion/core/decision_finalizer.py:441`
- `scion/scion/core/decision_finalizer.py:453`
- `scion/scion/core/decision_finalizer.py:482`
- `scion/scion/core/decision_finalizer.py:511`
- `scion/scion/core/evidence_recording/lineage.py:123`
- `scion/scion/core/evidence_recording/lineage.py:164`
- `scion/scion/core/evidence_recording/lineage.py:228`
- `scion/scion/core/evidence_recording/lineage.py:279`

Why this matters:

- The lineage event and decision payload capture branch state, code status,
  telemetry outcome, screening feedback tier, and mechanism ids.
- On continue/retain/park/rollback paths, those captured fields can describe
  the pre-finalizer branch rather than the post-finalizer branch.
- Abandon has a dedicated pre-lineage terminal evidence sync, but continue
  lifecycle paths do not have an equivalent pre-lineage sync.

Impact:

- Append-only decision lineage can say a branch was `clean` or generic
  `active`, while the finalizer immediately marks it as
  `telemetry_wiring_suspect`, `active_weak_positive`, `parked_lineage`, or
  another post-decision lifecycle state.
- Downstream audit and summary consumers need to know whether lineage fields are
  pre-finalizer or post-finalizer, but the current field names do not expose
  that distinction.

Suggested fix direction:

- Either record continue-path lineage after lifecycle mutations, or explicitly
  split pre-finalizer and post-finalizer lifecycle evidence.
- If scheduler-result lineage is the intended post-finalizer record, document
  that contract and ensure summaries do not treat decision lineage as the final
  branch state snapshot.

### F-FINALIZER-003 [P2] Lifecycle action is a required side channel, not derivable from reason codes

`DecisionFinalizer._effective_lifecycle_action(...)` only accepts an explicit
`lifecycle_action`. It intentionally ignores lifecycle-like reason codes.
Continue lifecycle behavior then depends on exact lifecycle action strings such
as `retain_head`, `park_lineage`, and `rollback_to_checkpoint`.

Evidence:

- `scion/scion/core/campaign.py:776`
- `scion/scion/core/campaign.py:783`
- `scion/scion/core/campaign.py:821`
- `scion/scion/core/campaign.py:824`
- `scion/scion/core/decision_finalizer.py:339`
- `scion/scion/core/decision_finalizer.py:360`
- `scion/scion/core/decision_finalizer.py:937`
- `scion/scion/core/decision_finalizer.py:949`
- `scion/scion/tests/unit/core/test_decision_finalizer_park_lifecycle.py:641`
- `scion/scion/tests/unit/core/test_decision_finalizer_park_lifecycle.py:737`

Why this matters:

- This is partly intentional: tests verify legacy lifecycle reason codes alone
  do not park a lineage.
- It also means alternate callers must pass the lifecycle action side channel
  correctly. Reason codes that appear to say `park_lineage` or `retain_head`
  are not enough.

Impact:

- Any compatibility path, test harness, or future caller that forwards
  `decision_reason_codes` but forgets `lifecycle_action` can silently discard,
  continue, or retain differently from the policy result.
- The API surface has two related but not interchangeable concepts:
  diagnostic/reason evidence and executable lifecycle action.

Suggested fix direction:

- Keep lifecycle action explicit, but make it a required field in a structured
  decision outcome object instead of a parallel optional argument.
- Add a defensive assertion/log when lifecycle-looking reason codes are present
  but `lifecycle_action` is empty.
- Document the finalizer contract: reason codes are evidence only; lifecycle
  action is the executable side-effect command.

## Deferred Follow-Up

- Promotion transaction behavior should be reviewed as its own module. The
  finalizer delegates promotion prepare/commit to `promotion_lifecycle.py` and
  `promotion_service.py`; partial commit ordering and champion persistence
  should be audited there rather than overloading this module note.

## Open Questions

- Is lifecycle archive intended to count as hard abandon in v0.4, or should the
  older soft-abandon accounting distinction remain authoritative?
- Which lineage record should downstream summaries treat as the final state:
  decision lineage, scheduler-result lineage, or both with explicit pre/post
  semantics?
- Should `DecisionFinalizer.apply(...)` accept a single immutable decision
  outcome object from `EvaluationOrchestrator` to prevent reason/action drift?
