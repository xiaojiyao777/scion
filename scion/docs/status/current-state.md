# Scion v0.4 Current State

*Last updated: 2026-07-14*

This is the operational resume point. Read `scion/TASK.md` first and use
`scion/design/scion-architecture-v3.md` as the architecture tie-breaker.

No experiment is running. The warehouse R3 lifecycle is resolved. Its
round-2 candidate passed expanded screening, but the same cumulative branch
failed eval-only validation on the larger locked split and is now `abandoned`.
The validation wrapper and the repaired campaign-scoped postrun path are fully
green. Do not retry, freeze, modify, or promote this branch. The first fresh
CVRP control stopped before proposal generation on an incorrect external data
root; it contains no algorithm result and was not retried. A distinct corrected
R2 root was prepared at `6ec0db55` but guarded readiness rejected it before any
provider call; it is also not launchable. A distinct R3 CVRP root is now fully
audited and prepared-only at pushed `1978b426`; it has not called the provider.

## Current Decision

Commit `64137fc3` is pushed on `v0.4-dev` and was the exact clean runtime for
the failed pre-campaign CVRP root. Commit `9c88ef6a` contains the resumed-
postrun scope repair and was the exact validation runtime. The warehouse result
remains a useful negative research lifecycle: Scion found a broad screening
signal, expanded it, escalated the same candidate without another model call,
and correctly rejected it when it failed to generalize.

The launcher-integrity repair is pushed at `6ec0db55`. It validates the
final explicit data root before creating a run root, repeats that check before
provider access, pins the complete 81-file identity, rechecks it after campaign
execution, redacts proxy auth receipts to readiness-only fields, keeps the key
out of argv, and creates the receipt under `umask 077`. Do not carry warehouse
target hints or mechanism instructions into CVRP, and do not auto-retry the
failed root.

The first clean prepare after that commit exposed two narrow static-auditor
drifts: identity SHA metadata was interpreted as a path, and the receipt
allowlist did not recognize the exact `chmod 600` line. The minimal follow-up
is pushed at `1978b426`. The new R3 root passes guarded-wrapper readiness,
formal data identity, secret-hygiene, and native first-H context audits. Keep it
prepared-only until explicit operator authorization.

## Run Roots

Formal fresh R3 root:

`/home/clawd/research/scion-experiments/v04-warehouse-direct-repaired-context-confirm-r3-2r-gpt56sol-20260714T135820Z-claw`

Expanded-screening continuation root:

`/home/clawd/research/scion-experiments/v04-warehouse-r3-same-candidate-expand-1r-gpt56sol-20260714T142050Z-claw`

Same-candidate validation root:

`/home/clawd/research/scion-experiments/v04-warehouse-r3-same-candidate-validation-1r-gpt56sol-20260714T145307Z-claw`

Failed pre-campaign CVRP root:

`/home/clawd/research/scion-experiments/v04-cvrp-direct-open-control-r1-2r-gpt56sol-20260714T151358Z-claw`

Superseded prepared-only CVRP root:

`/home/clawd/research/scion-experiments/v04-cvrp-direct-open-control-r2-2r-gpt56sol-20260714T161411Z-claw`

Current audited prepared-only CVRP root:

`/home/clawd/research/scion-experiments/v04-cvrp-direct-open-control-r3-2r-gpt56sol-20260714T163231Z-claw`

The first root is the fresh formal confirmation. The second and third are
copied-state, diagnostic/non-formal continuations used only to evaluate the
exact same cumulative candidate. Do not blur their wrapper status or evidence
scope.

The CVRP root is infrastructure evidence only. Its healthy completion probe
was followed by a split-data resolution failure before any H/C proposal call.
Do not resume or relaunch it.

The R2 root made no provider call. Its identity is correct, but its exact commit
cannot pass guarded readiness because the static auditors predate the follow-up.
Do not edit or launch it.

The CVRP R3 root is the only launch candidate. It remains prepared-only with no
PID, provider trace, live preflight receipt, or campaign execution artifact.
Do not replace, resume, or auto-retry it.

## CVRP R3 Prelaunch Evidence

- prepared/runtime commit: clean detached `1978b426`;
- model/rounds/solver limit: `gpt-5.6-sol`, `2`, `30` seconds per solver
  subprocess;
- force surface/action/target: all empty;
- formal data identity: 81 files, digest
  `ca7e470ec8d1f3569a690d10df5a170c4994108c71fecf5aa1a7a76b42630743`;
- generated wrapper embeds that digest in both pre/post checks and matches its
  prepared run.sh SHA anchor;
- guarded-wrapper readiness: `true`, with no required or optional failures;
- `launch_ready=false` only because no separate live completion was sent; the
  wrapper owns the sole live pre-campaign completion preflight;
- `launch.env` and the data identity receipt are mode `0600`; secret-field scans
  are empty and the API key value is not persisted;
- provider calls, campaign markers, scheduler/promotion mutation: none.

The native first-H projection contains only the `solver_design` surface and 12
targetable entries: 11 concrete CVRP algorithm files plus the declared
`policies/baseline_modules/*.py` wildcard. It contains open algorithm guidance
and zero matches for successor, target-intent, forced targeting, mechanism
ranking/denylist, telemetry gate, candidate caps, retry/backoff, truncation, or
semantic budget. Independent review reports P0/P1/P2=`0/0/0`.

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

## CVRP Pre-Campaign Failure and Repair

- prepared/runtime commit: `64137fc3`;
- model/preflight: `gpt-5.6-sol`, authenticated HTTP 200, non-empty response;
- proposal/code calls: `0 / 0`;
- solver pairs: `0`;
- failure: 40 formal external cases absent under the detached worktree's
  partial `vrp/` directory;
- retry/restart: none;
- failed receipt: proxy key and account identity explicitly removed with a
  security-redaction marker.

The repaired launcher accepts an explicit data root and validates only that
exact path; an ambient valid root cannot hide a bad prepared path. Generated
run.sh repeats the check before completion preflight. Completion receipts keep
only authenticated state and pool counts, take the key from the environment,
and are created with owner-only permissions.

The external main-checkout dataset is not tracked by git and is writable. The
audited formal input set is 40 `.vrp` files, 40 sibling `.sol` files, and the
package canary. Its ordered identity digest is
`ca7e470ec8d1f3569a690d10df5a170c4994108c71fecf5aa1a7a76b42630743`.
The repaired prepared contract records this identity, and the generated wrapper
requires it before provider access and after execution.

Repair verification is complete: `134` focused tests pass; the standard full
suite passes `1872 passed, 1 skipped` in `496.65s`; compileall, diff-check,
generated run.sh syntax, live identity construction, and independent formal-
path P0/P1/P2 review are green.

The subsequent two-auditor follow-up passes `124` focused tests and the standard
full suite at `1875 passed, 1 skipped` in `502.33s`. Its chmod reference
allowlist accepts only the exact generated command and rejects appended shell
operations; compileall, `git diff --check`, and independent P0/P1/P2 review are
green.

## Worktree State

- branch: `v0.4-dev`; audited runtime commit `1978b426` is pushed;
- intended changes now: the CVRP R3 prelaunch report, `TASK.md`, and this file;
- `scion/docs/v0.4-measurement-readiness.md` is a pre-existing user-owned
  tracked change and must remain excluded;
- unrelated untracked historical/future documents must remain excluded;
- the current CVRP prepared root uses clean detached runtime
  `/home/clawd/research/or-autoresearch-agent-v04-direct-runtime-1978b426`.

## Resume Actions

1. Commit and push only the R3 prelaunch report plus compact status updates;
   leave the run root unchanged and prepared-only.
2. Launch that exact audited root only after explicit operator authorization.
   Supply `SCION_SHARED_PROXY_KEY` only in process environment; do not send a
   separate probe because run.sh owns the sole live completion preflight.
3. Poll about every three minutes and never retry, replace, resume, or silently
   repair a failed run.
4. After a terminal outcome, audit H/C receipts, solver pairs, lineage,
   algorithmic materiality, runtime, and postrun readiness before continuation
   or promotion.

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
- CVRP pre-campaign failure:
  `scion/docs/experiments/v0.4/v04-cvrp-direct-open-control-r1-precampaign-failure-20260714.md`
