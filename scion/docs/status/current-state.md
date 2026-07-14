# Scion v0.4 Current State

*Last updated: 2026-07-14*

This is the operational resume point. Read `scion/TASK.md` first and use
`scion/design/scion-architecture-v3.md` as the architecture tie-breaker.

No experiment is running. The warehouse R3 lifecycle is resolved. Its
round-2 candidate passed expanded screening, but the same cumulative branch
failed eval-only validation on the larger locked split and is now `abandoned`.
The validation wrapper and the repaired campaign-scoped postrun path are fully
green. Do not retry, freeze, modify, or promote this branch.

## Current Decision

Commit `9c88ef6a` is pushed on `v0.4-dev`. It contains the resumed-postrun scope
repair and is the exact runtime commit for validation. The result is a useful
negative research lifecycle: Scion found a broad screening signal, expanded
it, escalated the same candidate without another model call, and correctly
rejected it when it failed to generalize.

The next experiment is one fresh, clean, open, non-target-bound CVRP direct
control. First commit and push this validation status update, then prepare a
new detached clean runtime at that exact docs commit so formal readiness sees
an exact clean repository. Do not carry warehouse target hints or mechanism
instructions into CVRP.

## Run Roots

Formal fresh R3 root:

`/home/clawd/research/scion-experiments/v04-warehouse-direct-repaired-context-confirm-r3-2r-gpt56sol-20260714T135820Z-claw`

Expanded-screening continuation root:

`/home/clawd/research/scion-experiments/v04-warehouse-r3-same-candidate-expand-1r-gpt56sol-20260714T142050Z-claw`

Same-candidate validation root:

`/home/clawd/research/scion-experiments/v04-warehouse-r3-same-candidate-validation-1r-gpt56sol-20260714T145307Z-claw`

The first root is the fresh formal confirmation. The second and third are
copied-state, diagnostic/non-formal continuations used only to evaluate the
exact same cumulative candidate. Do not blur their wrapper status or evidence
scope.

## Formal R3 Evidence

- model: `gpt-5.6-sol`;
- prepared/runtime commit: `d57d6cd6`;
- guarded readiness: passed without a separate live probe;
- preflight: authenticated HTTP 200, non-empty response;
- requested/evaluated rounds: `2/2`;
- durable provider calls: H=`2`, C=`2`, total=`4`;
- retries or replacement attempts: `0`;
- one branch across both rounds:
  `52b0b193-7bc3-469c-97a2-216b494b4e4a`;
- both candidates: Contract pass, Verification pass, Canary pass;
- campaign and outer wrapper: green;
- postrun required/optional checks: green;
- decision/outcome identity: complete and consistent;
- champion: version 1, unchanged.

Actual H/C contexts contained none of the removed telemetry-counter,
telemetry-guard, validation-transfer, top-k/max-candidate,
runtime-budget-strategy, retry, or truncation text. H2 received round 1's
canonical result; C2 received its verified current branch source.

The run used no Scion prompt/session/tool/file/item/token budget, semantic
termination budget, or truncation. The 30-second solver time limit is a
scientific subprocess fact.

## Algorithm Result

### Round 1

The agent replaced `operators/destroy_rebuild.py` with a subcategory-focused
beam destroy/rebuild search.

- case W/L/T: `2/2/2`;
- pair W/L/T: `5/5/2`;
- primary `subcategory_splits` delta: always `0`;
- total-cost median delta: `-1150`, CI `[-10175, 550]`;
- runtime ratio: `3.2567`;
- Decision: `continue_explore / RUNTIME_REGRESSION`.

### Round 2 initial screen

The same branch then replaced `operators/merge_vehicles.py` with a directed
best-of-k vehicle merge. The H6 lookup key matches the oracle exactly:
`f"{destination_country},{ship_method}"`.

- case W/L/T: `3/0/3`;
- pair W/L/T: `8/1/3`;
- primary delta: always `0`;
- total-cost median delta: `+775`, CI `[150, 3000]`;
- statistical status: positive;
- Decision: `expand_screening`.

### Same-candidate expanded screen

The continuation used the scheduler's eval-only path. Trace count remained
four, so there was no new H/C call.

- evaluated invocation rounds: `1/1`;
- cases / pairs: `14 / 28`;
- valid / failed pairs: `28 / 0`;
- case W/L/T: `7/0/7`;
- pair W/L/T: `19/2/7`;
- primary median/CI: `0 / [0, 0]`;
- total-cost median delta: `+625`, CI `[300, 1600]`;
- fresh runtime ratio: `0.7004`, confidence high;
- runtime delta: `-279 ms`, regression rate `0.4286`;
- Protocol: pass;
- Decision: `queue_validate`;
- branch state: `ready_validate`;
- screening expansion count: `1`.

This is the first strong warehouse signal, but attribution is incomplete. The
branch still contains round 1's slower destroy/rebuild change, both changes
alter RNG consumption, and current artifacts have no direct operator
call/acceptance/causal-effect evidence. `_PAIR_LIMIT=24` also slices only after
full directed `O(V^2)` pair enumeration. Six larger candidate pairs reached
about 30 seconds even though the fresh median was faster than champion.

### Same-candidate validation

The validation continuation kept the same branch/workspace/code identity and
made no H/C call. It evaluated five cases with seeds `7/19/83`.

The copied `campaign/status.json` still displays cumulative H=`2`, C=`2` from
the source campaign. Current campaign proposal-transition count is zero, and
all four trace files are byte-identical pre-launch artifacts; use those scoped
facts rather than the inherited counters when auditing eval-only behavior.

- pairs: `15/15` valid, no solver failure;
- case W/L/T: `2/3/0`;
- pair W/L/T: `6/9/0`;
- primary `subcategory_splits` median: `0`, CI `[0,1]`;
- case win rate: `0.40`, below validation minimum `0.55`;
- runtime ratio: `1.578`;
- runtime delta: `+11072 ms`;
- runtime regression rate: `13/15`;
- Decision: `abandon / VALIDATION_FAIL_NO_HIERARCHICAL_GAIN`;
- final branch state: `abandoned`;
- champion: unchanged; no frozen run or promotion.

`val_l01` improved splits by one on all seeds but worsened cost by
`8000--11500`. `val_lx02` tied on splits and improved cost on all seeds.
`val_l02`, `val_l04`, and `val_lx01` tied on splits and lost cost on all nine
pairs. Even ignoring the hierarchical primary metric, the five case-level
cost effects have median `-8300`. Twelve candidate runs were near 30 seconds.
The screening signal was local to the smaller screen and did not generalize to
the 308--457-order validation distribution.

All production screening, validation, frozen, and canary fixtures have empty
`amount_limits`, so the corrected H6 code path is not experimentally exercised.
Validation contained many locked orders and all 15 pairs remained feasible, so
the cumulative candidate is lock-safe on this surface. Locked-order counts were
`12/49/43/15/58`. H6 remains untested because every amount-limit map is empty.

## Resume-Postrun False Failure

The expanded campaign is valid and its campaign wrapper exited `0`, but the
original outer wrapper exited `64` on
`summary_lineage_outcome_counts_mismatch`.

The copied database contains:

- source campaign `acbb5338-...`: two evaluated outcomes;
- current campaign `94d52219-...`: one evaluated outcome;
- cumulative total: three evaluated outcomes.

Postrun compared the current summary count `1` with cumulative count `3`. The
repair preserves cumulative top-level event audit counts but uses the current
summary/status campaign ID for execution-outcome and decision-correlation
integrity. If current identity exists and its durable outcome is absent, the
gate still fails closed. If a legacy schema cannot establish campaign scope,
the counts are marked incomparable rather than mixed.

Current-source verification against the real root now reports:

- cumulative evaluated: `3`;
- scoped campaign: `94d52219-a51d-4215-ada5-e5f98ea72c93`;
- scoped evaluated: `1`;
- comparable: `true`;
- consistent: `true`;
- decision/outcome consistency: `consistent`.

Focused postrun/lineage coverage passes, the full Scion suite passes
`1859 passed, 1 skipped` in `494.65s`, and compileall plus
`git diff --check` pass.

The validation root proves the fix in a real continuation: its current campaign
`a24b5d73-...` has one evaluated outcome, the copied database has four
cumulative evaluated outcomes across three campaign IDs, current scoped
summary/lineage counts are `1/1`, decision consistency is `consistent`, and
postrun readiness has no required or optional failure.

## Worktree State

- branch: `v0.4-dev` at pushed `9c88ef6a`;
- intended changes now: validation results in the R3 report, `TASK.md`, and
  this file only;
- `scion/docs/v0.4-measurement-readiness.md` is a pre-existing user-owned
  tracked change and must remain excluded;
- unrelated untracked historical/future documents must remain excluded;
- validation ran from clean detached runtime
  `/home/clawd/research/or-autoresearch-agent-v04-direct-runtime-9c88ef6a`.

## Resume Actions

1. Complete the independent validation-result audit and diff/exclusion check.
2. Stage, commit, and push only the R3 report, `TASK.md`, and this file under
   the user's existing authorization.
3. Create a detached clean runtime at that exact commit.
4. Prepare one fresh two-round CVRP direct control with no target/action/surface
   binding, parameter search disabled, `gpt-5.6-sol`, strict postrun reports,
   and completion preflight inside the guarded wrapper.
5. Require guarded-wrapper launch readiness, then inspect the prepared actual
   provider context for successor, target-file, mechanism-ranking, telemetry,
   budget, retry, and truncation noise. Do not send a separate live probe.
6. Launch only after those checks pass. Supply `SCION_SHARED_PROXY_KEY` only in
   process environment, poll about every three minutes, and never retry.

## Runner Notes

Server `claw`:

- repo: `/home/clawd/research/or-autoresearch-agent`;
- Python: `/home/clawd/miniconda3/envs/claw/bin/python`;
- use for focused tests and one experiment at a time.

WSL `scion` is reserved for large/concurrent work after a fresh connectivity
and preflight check.

## Pointers

- Active task: `scion/TASK.md`
- V3 architecture: `scion/design/scion-architecture-v3.md`
- v0.4 direct-runtime addendum:
  `scion/design/scion-architecture-v3-v0.4-direct-runtime-addendum.md`
- Main audit:
  `scion/reports/v04-v3-runtime-and-research-effectiveness-audit-20260712.md`
- Warehouse R2 control:
  `scion/docs/experiments/v0.4/v04-warehouse-direct-control-r2-436b6e12-postrun-20260714.md`
- Warehouse R3 plus expanded screening:
  `scion/docs/experiments/v0.4/v04-warehouse-direct-context-confirm-r3-d57d6cd6-postrun-20260714.md`
