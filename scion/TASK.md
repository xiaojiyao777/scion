# Scion v0.4 Final Direct-Runtime Validation Task

*Branch: `v0.4-dev`*
*Last updated: 2026-07-14*

This is the active task source. Start here and then read
`scion/docs/status/current-state.md`. Experiment chronology belongs in focused
reports, not in this file.

## Objective

v0.4 remains open until the final integrated commit proves that the same small
V3 runtime can conduct useful research on both warehouse and CVRP.

The implementation target is now fixed:

```text
complete safe problem context
  -> one durable Hypothesis call
  -> structural Hypothesis Contract
  -> one durable Code call bound to the approved hypothesis and SourceLedger
  -> structural Patch Contract
  -> Workspace -> Verification -> Protocol -> Safe Features -> Decision
```

Do not rebuild APS, add another proposal repair loop, restore successor-specific
steering, or launch a formal experiment from the transition worktree.

## Authority and Non-Negotiable Boundaries

- Architecture authority: `scion/design/scion-architecture-v3.md`; conflicting
  early retry/budget/novelty/context examples are narrowed by
  `scion/design/scion-architecture-v3-v0.4-direct-runtime-addendum.md`.
- LLM output is tainted. It cannot write Decision inputs or scheduler state.
- Problem semantics remain problem-owned; generic core has no CVRP/warehouse
  algorithm policy.
- Contract owns schema, path, source, interface, import, API, and approved-H
  binding.
- Verification owns executable correctness: syntax, interface, state leak,
  feasibility, objective consistency, nondeterminism, crash, and timeout.
- Protocol owns comparative scientific verdicts and split/seed isolation.
- Decision deterministically maps the trusted Protocol verdict and hard safety
  flags to a branch action; it does not recompute scientific thresholds.
- Promotion remains atomic and requires complete formal evidence.
- Server-local `claw` is the focused/single-run environment. WSL `scion` is the
  large/concurrent runner only after connectivity and preflight are rechecked.

## Current Accepted Implementation

### Single proposal runtime

- warehouse and CVRP use the same direct V3 path;
- one H call and one C call per normal candidate attempt;
- provider SDK retry is zero; failure terminates the durable attempt;
- invalid H/C output is recorded as `invalid_response`, projects to a typed
  non-evaluated outcome, and stops the current campaign invocation;
- a hard process/host loss may leave only the durable `started` row; postrun
  classifies it as `unrecovered_in_flight` without forging evidence or retrying;
- interruption, infra failure, invalid response, research rejection, and
  evaluated outcome remain distinct;
- the operator supplies `requested_rounds`; the runtime has no semantic
  termination budget, frozen-use ledger, circuit breaker, automatic retry
  counter, or hidden non-counting round;
- APS sessions, target intent, tool selection, fix-code, retry/resume state,
  session budgets, compact-to-fit, and legacy agentic postrun joins are deleted.

### Context and source authority

- `ProposalContextSnapshot` is the immutable prompt input owner;
- H context contains current problem/source facts and one canonical record for
  each visible screening attempt;
- C context contains one approved hypothesis and one complete `SourceLedger`;
- declared research-surface wildcards are expanded once against the champion
  snapshot, so H source and C ledger cover every actual active module rather
  than only a stale static API manifest;
- multi-file patches retain per-file owner, provenance, content, and digest;
- no Scion content cap, item/file limit, top-N, truncation, omitted marker, or
  summary substitution remains on the production proposal path;
- CVRP prompt context contains no successor id, nearest-reviewed requirement,
  mechanism ranking, denylist, CMT recipe, target-file hint, or instrumentation
  obligation.

### Single hard owners

- Contract resolves one immutable problem capability bundle per validation;
- Verification shares one candidate canary across V5/V6/V7 and performs only
  one additional same-seed run for nondeterminism;
- comparative slowdown is not a pre-Protocol V9 rejection;
- telemetry completeness/actionability is diagnostic, not a gate or retry;
- generic problem-surface fallback exposes structural interface facts only; it
  does not inject evidence grading, telemetry, or novelty policy into H/C;
- scientific runtime/time-limit observations remain diagnostic evidence and are
  not duplicated into Protocol or Decision reason codes;
- Protocol alone owns win rate, delta, CI, runtime comparison, low-SNR, and
  statistical-expand verdicts;
- scheduler is state/priority/FIFO/active-slot management only; branch lessons,
  clean-fork, same-mechanism, marginal/no-effect streaks, and stagnation advice
  do not override Decision or steer the provider.
- the v0.4 production default is one active research branch, so a screening
  `CONTINUE_EXPLORE` iterates the same scientific direction and the next H/C
  consume its canonical experiment evidence and verified current source;
  those facts and the touched-file footprint survive a campaign reopen without
  duplicate history, while a missing required verified workspace fails closed;
  explicit wider Scheduler configurations remain available only for later
  breadth ablation and are not a semantic budget.

### Formal launch boundary

- prepared commands are parsed by the real current CLI before launch;
- `--launch` requires a real completion preflight;
- operator readiness uses `--require-guarded-wrapper-launch-ready`, which makes
  no provider call and proves that `run.sh` contains exactly one executable
  preflight, one receipt path/redirection, fail-closed reporting, and a
  campaign marker after the preflight exit path;
- formal completion roots must be fresh: resume state and skipped postrun
  reports are rejected;
- formal completion roots reject all forced surface/action/target bindings;
- formal warehouse and CVRP controls require `parameter_search.enabled=false`;
  the default is disabled and warehouse preflight fails closed otherwise;
- readiness and generated `run.sh` require an entirely clean repository and
  exact equality between runtime HEAD and the prepared commit; docs-only drift
  and unrelated untracked files are not exceptions;
- both direct launchers bind the final `run.sh` bytes with SHA-256 in
  `launch.env` and the prepared manifest; guarded readiness requires both
  anchors to equal the on-disk script, so the prepared root must not be edited
  between readiness and operator launch;
- the manifest model is authoritative and may be `gpt-5.6-sol`; readiness
  checks exact manifest/environment consistency rather than a hard-coded model;
- historical retry/repair labels remain readable only in legacy postrun
  artifacts and do not control the direct runtime.

## Integrated Evidence

- Commit `d57d6cd6` contains the operational warehouse-spec parity, exact H6
  source contract, and decision-identity repair; it passed the full suite
  (`1852 passed, 1 skipped`) and is pushed on `v0.4-dev`.
- Its clean formal warehouse R3 confirmation completed two evaluated rounds on
  one branch with exactly two H and two C calls and no retry. Actual H/C
  contexts contained none of the removed telemetry-counter, telemetry-guard,
  validation-transfer, top-k/max-candidate, runtime-budget-strategy, retry, or
  truncation instructions. Both rounds passed Contract, Verification, Canary,
  and postrun readiness.
- R3 round 2 produced a positive directed-merge signal: initial case W/L/T
  `3/0/3`, pair `8/1/3`, total-cost median `+775`, CI `[150, 3000]`. Scion
  correctly chose `expand_screening`.
- An eval-only continuation reused the exact candidate without another
  provider call and expanded to 14 cases / 28 pairs: case W/L/T `7/0/7`, pair
  `19/2/7`, total-cost median `+625`, CI `[300, 1600]`, fresh runtime ratio
  `0.7004`, Protocol pass, Decision `queue_validate`.
- The same cumulative candidate then completed eval-only validation with no
  provider call: 15/15 valid pairs, case W/L/T `2/3/0`, pair `6/9/0`, primary
  median `0`, CI `[0,1]`, runtime ratio `1.578`, and runtime regression rate
  `13/15`. Decision was
  `abandon / VALIDATION_FAIL_NO_HIERARCHICAL_GAIN`; the branch is abandoned,
  and no frozen run or promotion occurred.
- The first fresh CVRP control root stopped before proposal generation because
  the detached worktree's partial `vrp/` directory did not contain the
  gitignored formal CVRPLIB dataset. The completion preflight was healthy, but
  campaign initialization rejected all 40 external cases. No H/C call,
  candidate, or solver pair exists, and the root was not retried.
- That pre-campaign failure exposed two launcher defects now under repair:
  prepare did not resolve every split case against the final explicit data
  root, and the persisted proxy auth receipt copied the proxy key and account
  identity. The failed receipt has been explicitly redacted. The repair adds
  exact-root prepare validation, a wrapper recheck before provider access,
  auth-field allowlisting, environment-only key transfer, and secure receipt
  creation.
- The completed repair also pins the 81-file CVRP data identity as a literal in
  both generated pre/post checks under the existing run.sh SHA anchor. It passes
  `134` focused tests and the standard full suite (`1872 passed, 1 skipped` in
  `496.65s`); compileall, diff-check, generated-script syntax, and independent
  formal-path P0/P1/P2 review are green.
- The first corrected prepare at `6ec0db55` made no provider call but guarded
  readiness exposed two static auditor drifts: the prepared contract treated
  the identity SHA as a path, and the receipt-reference allowlist rejected the
  exact `chmod 600` hardening line. The minimal follow-up passes `124` focused
  tests and the standard full suite (`1875 passed, 1 skipped` in `502.33s`).
  Its chmod allowlist accepts only the exact generated command and rejects
  appended shell operations. That prepared-only root is superseded and must
  not be launched.
- That continuation exposed one narrow postrun bug: current summary outcome
  counts were compared with cumulative copied-database counts across two
  campaign IDs. The experiment is valid; the current repair scopes integrity
  to the summary campaign while retaining cumulative audit counts.
- Commit `436b6e12` contains the preceding direct proposal-context and postrun
  repair, passed the full suite (`1848 passed, 1 skipped`), and is pushed on
  `v0.4-dev`.
- Its clean formal warehouse R2 control completed two evaluated rounds on one
  branch with exactly two H and two C calls and no retry. Both substantive new
  operators passed Contract, Verification, Canary, and `20/20` screening
  pairs; the second H consumed the first screening result and the second C
  SourceLedger contained the first operator as verified
  `branch_history_current` source.
- The two algorithms were solver-negative. R1 case W/L/T was `1/1/8`, cost
  median `+50`, CI `[-325, 250]`; R2 was `0/3/7`, cost median `-150`, CI
  `[-2500, 400]`, runtime ratio `2.2983`. No promotion occurred.
- R2 exposed two framework defects before CVRP: the formal launcher still read
  a stale top-level warehouse `problem-v1.yaml` containing telemetry/top-k/
  runtime-budget prompt noise, and postrun falsely treated two identity-less
  duplicate decision projections as non-evaluated despite two exact evaluated
  outcomes. The completed repair aligns provider-visible research surfaces,
  enforces full spec parity, persists full decision identity, and keeps legacy
  identity-less rows diagnostic rather than invalid.
- The completed repair collects `1853` tests and passes the full Scion suite:
  `1852 passed, 1 skipped` in `492.99s`; the focused affected shard passes
  `206` tests, and compileall plus `git diff --check` pass.
- The preceding guarded-readiness baseline at `b1464171` passed
  `1835 passed, 1 skipped` in `496.64s`.
- Direct warehouse and CVRP outer smokes pass through
  Contract -> Verification -> Protocol -> Decision.
- The serial-iteration regression proves two screening failures use one branch,
  exactly two H and two C calls, prior screening evidence in the second H, and
  prior verified branch source in the second C SourceLedger. A process-reopen
  regression proves the same H history, `branch_history_current` C provenance,
  and cumulative workspace after reconstruction; the latest focused shard
  passes `82` tests.
- Warehouse/CVRP outer paths plus both formal launchers pass `22` tests after
  the scheduler change.
- Critical branch-state persistence no longer swallows SQLite write failures;
  the focused durable-state/failure/reopen shard passes `49` tests.
- The first clean-commit warehouse readiness attempt exposed and repaired a
  builder/validator drift in `prepared_research_focus_projection.required`;
  manifest-declared focus is now required while absent focus remains optional.
  The affected builder/readiness/warehouse/CVRP shard passes `115` tests.
- The next clean warehouse root reached its sole launch-boundary completion
  preflight, but that request hung upstream for the explicit 60-second provider
  safety timeout. The wrapper stopped with status `64` before creating a
  campaign and did not retry. Proxy evidence shows an authenticated active
  account and a routed request with no usage or HTTP terminal record; the same
  probe had completed successfully immediately beforehand.
- That infra-only root exposed a direct-refactor regression in postrun
  readiness: `_prompt_context_visibility_summary` was still called after its
  import had been deleted. The import and a real preflight-failed-root CLI
  regression are restored. Timeout is now classified as
  `completion_timeout`, and an authenticated timeout no longer starts an OAuth
  login flow or suggests an auth repair. The affected shard passes `116` tests.
- The prepared-root readiness surface now separates `prepared_audit`,
  `guarded_wrapper_launch`, and `external_live_probe`. Only the guarded workflow
  is used for formal launch: it proves the wrapper capability without sending
  a model request, while `launch_ready` remains an explicit diagnostic live
  probe and must not be chained before `run.sh`. The launcher/readiness focused
  matrix passes `117` tests, including receipt reassignment, independently
  late marker, indirect receipt rebinding, and dynamically composed duplicate
  proxy counterexamples. The final independent audit reports P0=0/P1=0 for
  prepared-root `run.sh` drift with unchanged digest anchors.
- Unit/core integrated shard: `259 passed`; final core/lineage focused cleanup:
  `292 passed` plus `20` affected postrun tests.
- Proposal/context unit shard: `384 passed`.
- Contract/Verification: `173 passed`; Protocol/Decision: `166 passed`.
- Final launcher/readiness/runtime-diagnostic regressions passed (`157` affected
  tests), including exact-clean commit, parameter-search-off, fresh-start,
  no-resume, no-skip-postrun, and configuration-driven model checks.
- Started-only postrun classification and related artifact readers passed `44`
  affected tests.
- Final direct-attempt writer/legacy-reader regression: `106 passed`.
- The final standard-root surrogate suite completed `91 passed, 8 deselected`
  in `1304.93s`; the deselections are the explicit `@slow` cases from
  `surrogate/pytest.ini`. Its warehouse adapter smoke now binds absolute fixture
  paths and executes instead of depending on pytest's working directory.
- `compileall`, `git diff --check`, direct outer smokes, and production
  forbidden-symbol scans pass.
- Production `proposal/` is now `46` Python files / `8,281` lines, down from
  the audited `202` files / about `75.6k` lines.
- The integration diff reports `788 files changed`, `30,726 insertions`, and
  `263,102 deletions`; four rename pairs make these `788` rendered entries
  correspond to the audited `792` underlying paths. This deletion-heavy
  payload is the reviewed scope recorded by the commit containing this file.

## Current Blocker

The warehouse R3 lifecycle is complete and its branch remains `abandoned`.
The first CVRP control attempt produced no algorithm evidence: it failed before
proposal generation on an incorrect external-data-root binding. No experiment
is running, and automatic retry remains prohibited.

The immediate blocker is pushing the verified narrow readiness follow-up, not
VRP algorithm quality. The repair pins all 40 formal `.vrp`
files, their 40 sibling `.sol` files, and the package canary in the prepared
contract; the wrapper verifies the same identity before provider access and
after campaign execution. After the repair is pushed, create a new detached
runtime at that exact commit.

Preserve the excluded user-owned
`scion/docs/v0.4-measurement-readiness.md` change and unrelated untracked
history.

## Immediate Queue

1. Stage, commit, and push only the verified prepared-contract/readiness
   follow-up, its tests, and status docs under
   the existing authorization.
2. Create an isolated detached clean runtime at that exact commit.
3. Prepare a distinct fresh two-round CVRP direct control with explicit
   `--data-root`, no target/action/surface binding, parameter search disabled,
   `gpt-5.6-sol`, strict postrun reports, and completion preflight inside the
   guarded wrapper.
4. Confirm the prepared 81-file identity receipt, then require guarded-wrapper
   readiness and inspect the actual H context for
   successor IDs, target-file/mechanism steering, telemetry,
   budget, retry, or truncation noise. Do not send a separate live probe.
5. Do not treat the corrected root as an automatic retry. Launch only under
   explicit operator authorization after those checks pass. Supply the shared
   proxy key only in process environment, poll about every three minutes, and
   never retry.

Do not close v0.4 merely because framework tests pass. Close it only after both
formal controls show that the simplified agent performs useful research without
reintroducing governance noise.

## Test and Run Discipline

- no prompt/session/tool/file/item/token budget or truncation experiment;
- provider-native required parameters and scientific subprocess/solver timeouts
  remain explicit correctness facts;
- no hidden retry, automatic same-prompt repair, or partial provider resume;
- experiment polling is observational and low-frequency (normally every three
  minutes, or 2--5 minutes when justified by state), never a trigger for
  another provider attempt;
- ordinary exact-replace materialization may record
  `typed_edit_normalization`; any `typed_edit_noop_dropped` or
  `patch_set_composition` makes the run characterization-only unless the raw
  response and canonical patch receive explicit human review;
- no formal run from a dirty tree or stale prepared root;
- preserve unrelated dirty files;
- stage/commit/push only with explicit user authorization.

## Pointers

- Current state: `scion/docs/status/current-state.md`
- V3 authority: `scion/design/scion-architecture-v3.md`
- v0.4 V3 addendum:
  `scion/design/scion-architecture-v3-v0.4-direct-runtime-addendum.md`
- Main audit:
  `scion/reports/v04-v3-runtime-and-research-effectiveness-audit-20260712.md`
- Gate/host-control audit:
  `scion/reports/v04-gate-and-host-control-audit-20260712.md`
- K6 implementation plan:
  `scion/docs/planning/v0.4/v0.4-k6-single-proposal-runtime-deletion-plan-20260712.md`
- Successor55 postrun:
  `scion/docs/experiments/v0.4/v04-cvrp-successor55-bounded-elite-solution-pool-postrun-20260712.md`
- Formal warehouse `b1464171` postrun:
  `scion/docs/experiments/v0.4/v04-warehouse-direct-control-b1464171-postrun-20260713.md`
- Formal warehouse R2 `436b6e12` postrun:
  `scion/docs/experiments/v0.4/v04-warehouse-direct-control-r2-436b6e12-postrun-20260714.md`
- Formal warehouse R3 plus expanded screening:
  `scion/docs/experiments/v0.4/v04-warehouse-direct-context-confirm-r3-d57d6cd6-postrun-20260714.md`
