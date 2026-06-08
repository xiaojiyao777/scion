# Promotion Lifecycle / Promotion Service / Champion Lineage

## Scope

Current source reviewed:

- `scion/scion/core/promotion_lifecycle.py`
- `scion/scion/core/promotion_service.py`
- promotion call sites in `decision_finalizer.py`, `campaign.py`, and
  `campaign_composition.py`
- champion/branch persistence in `lineage/champion_store.py`,
  `lineage/branch_store.py`, and `lineage/registry.py`
- promotion lineage code in `evidence_recording/lineage.py`
- weight-revision follow-up in `async_weight_opt.py` and
  `weight_opt_committer.py`
- selected tests in:
  - `scion/scion/tests/unit/core/test_promotion_service.py`
  - `scion/scion/tests/test_campaign_success_contract.py`
  - `scion/scion/tests/test_campaign_summary_promote.py`
  - `scion/scion/tests/unit/core/test_weight_opt_committer.py`
  - `scion/scion/tests/unit/core/test_async_weight_opt.py`

## Current Understanding

Promotion is split across three layers:

```text
DecisionFinalizer
  -> require frozen promotable branch
  -> prepare immutable PromotionPlan
  -> inject promotion_experiment_id into plan.champion
  -> commit PromotionPlan
  -> record PROMOTE lineage with the same promotion_experiment_id

PromotionLifecycleService
  -> adapt generic promotion hooks to CampaignManager state
  -> persist champion, install in-memory champion, transition promoted branch
  -> mark sibling branches stale
  -> record search-memory promotion context
  -> launch or run weight optimization

PromotionService
  -> prepare filesystem snapshot
  -> commit injected mutation hooks in fixed order
```

The default prepare path copies the candidate workspace into
`champions/champion_v<N>`, freezes it, reads `registry.yaml` when present,
computes the snapshot hash, and returns an immutable `PromotionPlan`.

The production commit hook order is:

```text
persist_champion
  -> before_commit
  -> commit_champion
  -> promote_branch
  -> mark_stale
  -> persist_branch_states
  -> on_promoted_branch
  -> start_weight_optimization
```

`commit_pool` and `after_commit` exist in `PromotionService` but are not wired
in the current production composition.

## Positive Boundary Observations

- Prepare and commit are split. `PromotionService.prepare(...)` is documented
  and tested to mutate only snapshot filesystem state, not champion/branch
  campaign state.
- Promotion precondition is explicit: a promoted branch must be in
  `FROZEN_TESTING` before promotion can be prepared.
- `PromotionPlan` is frozen and wraps mutable mappings in `MappingProxyType`.
  Unit tests cover this immutability.
- Champion store failure is tested to abort later promotion side effects:
  champion is not installed in memory, branches are not marked stale, optimizer
  is not launched, and no `decision=promote` row is written.
- `ChampionStore` is append-only for `(version, weight_revision)`, and weight
  optimization uses a separate same-version revision row rather than replacing
  the structural champion row.
- Weight optimization commit is main-threaded. It verifies the current champion
  version and weight revision before installing an optimized revision, and tests
  cover stale async event discard.

## Risks And Findings

### F-PROMOTE-001 [P1] Promotion commit can partially advance durable champion state

`PromotionService.commit(...)` runs each mutation hook sequentially with no
transaction or phase-aware recovery. The first production hook persists the new
champion row. Later hooks reset counters, install the in-memory champion,
transition the branch, mark sibling branches stale, persist branch rows, and
record search memory.

Evidence:

- Hook order in production composition:
  - `scion/scion/core/campaign_composition.py:218`
  - `scion/scion/core/campaign_composition.py:228`
- Sequential commit with no transaction:
  - `scion/scion/core/promotion_service.py:141`
  - `scion/scion/core/promotion_service.py:169`
- Durable champion insert:
  - `scion/scion/core/promotion_lifecycle.py:155`
  - `scion/scion/core/promotion_lifecycle.py:157`
  - `scion/scion/lineage/champion_store.py:139`
  - `scion/scion/lineage/champion_store.py:157`
- Later mutable effects:
  - `scion/scion/core/promotion_lifecycle.py:103`
  - `scion/scion/core/promotion_lifecycle.py:126`
  - `scion/scion/core/promotion_service.py:155`
  - `scion/scion/core/promotion_service.py:160`
- Finalizer catches any commit exception and returns `decision=None`:
  - `scion/scion/core/decision_finalizer.py:682`
  - `scion/scion/core/decision_finalizer.py:696`
- Current tests cover only the first hook failing:
  - `scion/scion/tests/unit/core/test_promotion_service.py:229`
  - `scion/scion/tests/unit/core/test_promotion_service.py:266`
  - `scion/scion/tests/test_campaign_summary_promote.py:129`
  - `scion/scion/tests/test_campaign_summary_promote.py:178`

Why this matters:

- If `persist_champion` succeeds but `before_commit`, `commit_champion`,
  `promote_branch`, `mark_stale`, `on_promoted_branch`, or `after_commit`
  raises, the durable champion table may already contain `v<N+1>` while the
  finalizer reports no promotion.
- Depending on the failing hook, campaign memory may still point to the old
  champion, the promoted branch may not be `PROMOTED`, sibling branches may not
  be `STALE`, and promotion lineage may not be recorded.
- `BranchStore.save(...)` uses a separate SQLite connection and
  `INSERT OR REPLACE`; `CampaignManager._persist_all_branch_states(...)` catches
  and logs branch persistence failures, so branch persistence can fail silently
  and is not part of a single atomic promotion boundary.

Impact:

- Restart/resume paths that read `ChampionStore.get_current()` can see a
  champion version that the in-memory campaign and branch lineage never
  committed.
- The finalizer may route a partially committed promotion through infra failure
  handling, which can further mutate the already-promoted branch.
- A retry after a partial commit can collide with the existing
  `(version, weight_revision)` champion row or reuse/delete the prepared
  snapshot path.

Suggested fix direction:

- Make promotion commit phase-aware. After the champion row is durably written,
  failures should be treated as recovery/repair of a committed promotion, not
  as `decision=None`.
- Add fault-injection tests for each hook after `persist_champion`, especially
  `commit_champion`, `promote_branch`, and `mark_stale`.
- Prefer one durable promotion transaction or outbox over separate best-effort
  hooks. At minimum, persist a promotion commit marker with enough data to
  recover branch state and lineage idempotently on restart.

### F-PROMOTE-002 [P1] Champion `promotion_experiment_id` can point to a missing lineage row

`DecisionFinalizer._promote(...)` creates `promotion_event_id`, writes it into
the promoted `ChampionState`, commits that champion, and only then records
promotion lineage. The lineage writer catches registry failures and does not
return an error to the finalizer.

Evidence:

- Promotion id is inserted into the champion before commit:
  - `scion/scion/core/decision_finalizer.py:675`
  - `scion/scion/core/decision_finalizer.py:681`
- Champion row persists the id:
  - `scion/scion/lineage/champion_store.py:139`
  - `scion/scion/lineage/champion_store.py:157`
- Lineage is recorded after commit returns:
  - `scion/scion/core/decision_finalizer.py:682`
  - `scion/scion/core/decision_finalizer.py:708`
- Registry writes are best-effort:
  - `scion/scion/core/evidence_recording/lineage.py:318`
  - `scion/scion/core/evidence_recording/lineage.py:335`
- Happy-path test asserts the link exists:
  - `scion/scion/tests/test_campaign_success_contract.py:78`
  - `scion/scion/tests/test_campaign_success_contract.py:87`

Why this matters:

- `promotion_experiment_id` is the structural audit link from a champion row to
  the frozen experiment that justified promotion.
- If `record_event(...)` fails after the champion row is inserted, the champion
  can permanently reference a non-existent experiment event. `record_decision`
  can also fail independently.
- Because the lineage writer swallows these exceptions, `DecisionFinalizer`
  returns `Decision.PROMOTE` and callers see a successful promotion.

Impact:

- Champion history can become non-auditable even though the promotion appears
  successful in the campaign result.
- Downstream reports that join champion rows to experiment events by
  `promotion_experiment_id` can silently lose the promotion proof.

Suggested fix direction:

- Make the promotion experiment event mandatory for structural promotion, or
  persist a promotion outbox record before champion commit and complete it
  idempotently after commit.
- If best-effort lineage remains acceptable for ordinary steps, add a stricter
  path for `decision=promote` where missing event insertion prevents or flags
  champion activation.
- Add a test with a registry that raises on `record_event(...)` and assert the
  desired invariant: either no champion row is activated, or a recoverable
  pending-promotion marker exists.

### F-PROMOTE-003 [P2] Sync weight optimization can run before structural promotion lineage is recorded

`PromotionLifecycleService.commit_promote_plan(...)` calls
`start_weight_optimization(...)` before returning to `DecisionFinalizer`.
`DecisionFinalizer` records promotion lineage only after `commit_promote_plan`
returns. In `parameter_search.execution == "sync"` mode, weight optimization can
run, drain, persist a new champion weight revision, and update in-memory
champion state before the structural promotion lineage row is written.

Evidence:

- Weight optimization starts inside `commit_promote_plan(...)`:
  - `scion/scion/core/promotion_lifecycle.py:92`
  - `scion/scion/core/promotion_lifecycle.py:101`
- Sync mode drains before returning:
  - `scion/scion/core/promotion_lifecycle.py:165`
  - `scion/scion/core/promotion_lifecycle.py:176`
- Weight optimization can install `v<N>_r<M+1>` into campaign memory:
  - `scion/scion/core/weight_opt_committer.py:122`
  - `scion/scion/core/weight_opt_committer.py:157`
- Promotion lineage is recorded after commit returns:
  - `scion/scion/core/decision_finalizer.py:697`
  - `scion/scion/core/decision_finalizer.py:708`
- Lineage records the current champion weight revision:
  - `scion/scion/core/evidence_recording/lineage.py:143`
  - `scion/scion/core/evidence_recording/lineage.py:144`

Why this matters:

- The structural promotion plan creates champion `v<N>_r<M>`. Sync weight opt
  can immediately create `v<N>_r<M+1>` before the promotion event is written.
- The promotion lineage row can therefore capture the optimized revision as the
  current champion, while the frozen experiment justified the structural
  promotion before weight optimization.
- `WeightOptCommitter` intentionally preserves the structural
  `promotion_experiment_id` on optimized revisions, so both `v<N>_r<M>` and
  `v<N>_r<M+1>` can point to the same promotion event.

Impact:

- Reports may blur "candidate promoted against frozen protocol" with "weights
  optimized after promotion".
- Debugging a promotion can show a branch evaluated against one weight revision
  and a promotion event stamped with a later champion revision.

Suggested fix direction:

- Record structural promotion lineage before launching synchronous weight
  optimization, or pass the `PromotionPlan.champion` snapshot explicitly into
  lineage recording instead of reading the mutable current champion.
- Keep weight optimization invalidation as a separate event, and ensure summary
  code treats it as a post-promotion revision rather than part of the frozen
  promotion decision.
- Add a sync-mode improved-weight test that asserts the promotion lineage row
  and weight update invalidation row have unambiguous revision semantics.

## Open Questions

- Should a missing `registry.yaml` remain a legacy fallback to the previous
  operator pool during promotion, or should adapter-backed production campaigns
  fail closed when the promoted snapshot lacks a registry?
- Should `PromotionService.commit(...)` continue to expose generic hook order,
  or should the production campaign use a narrower transaction object with
  explicit phases and recovery semantics?
- On resume, which source of truth wins if `ChampionStore.get_current()` is
  ahead of branch-store and experiment-event promotion lineage?
