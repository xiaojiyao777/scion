# Scion v0.4 Current State

*Last updated: 2026-07-14*

This is the operational resume point. Read `scion/TASK.md` first and use
`scion/design/scion-architecture-v3.md` as the architecture tie-breaker.

No experiment is running. The clean formal warehouse R3 confirmation is
complete and green. Its round-2 candidate then passed an eval-only expanded
screen on the same branch without another provider call and is now
`ready_validate`. Before validation, land the narrow postrun fix that scopes
current-invocation outcome integrity by campaign ID.

## Current Decision

Commit `d57d6cd6` is pushed on `v0.4-dev` and is the exact runtime commit for
R3. R3 proves that the repaired prompt/source contract reached the operational
formal launcher and that the direct runtime can produce a promising algorithm
signal without the old governance noise.

The same-candidate expanded screen earned `queue_validate`; it did not earn
promotion. Do not generate another H/C pair, start a new warehouse hypothesis,
or launch CVRP yet. First commit the postrun scope repair, then reopen the
expanded campaign from a clean detached runtime and run its eval-only
validation step.

## Run Roots

Formal fresh R3 root:

`/home/clawd/research/scion-experiments/v04-warehouse-direct-repaired-context-confirm-r3-2r-gpt56sol-20260714T135820Z-claw`

Expanded-screening continuation root:

`/home/clawd/research/scion-experiments/v04-warehouse-r3-same-candidate-expand-1r-gpt56sol-20260714T142050Z-claw`

The first root is the fresh formal confirmation. The second is a copied-state,
diagnostic/non-formal continuation used only to evaluate the exact same
candidate. Do not blur their wrapper status or evidence scope.

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

All production screening, validation, frozen, and canary fixtures have empty
`amount_limits`, so the corrected H6 code path is not experimentally exercised.
Validation does contain many locked orders and will exercise that separate
feasibility rule. The available validation surface is five cases times three
seeds (`15` pairs); locked-order counts are `12/49/43/15/58`.

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

## Worktree State

- branch: `v0.4-dev` at pushed `d57d6cd6`;
- intended changes: postrun campaign-scope repair, regression tests, R3 report,
  `TASK.md`, and this file;
- `scion/docs/v0.4-measurement-readiness.md` is a pre-existing user-owned
  tracked change and must remain excluded;
- unrelated untracked historical/future documents must remain excluded;
- do not run validation from this dirty source worktree.

## Resume Actions

1. Finish the full suite, compileall, diff/exclusion review, and independent
   read-only patch audit.
2. Stage, commit, and push only the intended repair/report/operating-doc files
   under the user's existing authorization.
3. Create a detached clean runtime at the exact new commit.
4. Prepare one diagnostic/non-formal continuation from the expanded campaign
   with `requested_rounds=1`. This is explicit invocation scope, not a semantic
   budget.
5. Confirm prelaunch state is `ready_validate`, trace count remains four, no
   provider call is scheduled, current code hash is
   `b214e9e18fcbf86c5b58ae58aed1be0db1cfd1daf57f3e874bda6bbe8c42d069`,
   and the cumulative workspace retains destroy/rebuild digest
   `4910ad450fb8bf8a876b0d3287ce9322e5600a4a87e156e95e36b4ea1a22cc36`
   plus merge digest
   `6e251c9f5bba4562bc2893cc4d56e10c9e74fa9874a2afacb0fa9428f144dcd5`
   and registry digest
   `4a3f8c737bb02cd3b87230ae4dad4a758287e0fef3ffb82e810a3f0592c212f1`.
6. Launch the eval-only validation step with `SCION_SHARED_PROXY_KEY` supplied
   only by the process environment; do not persist its value. Poll
   observationally about every three minutes and never schedule a retry.
7. Run frozen evaluation only if validation deterministically queues it. Do not
   promote or start CVRP from screening evidence alone.

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
