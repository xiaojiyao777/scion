# Scion v0.4 Final Direct-Runtime Validation Task

*Branch: `v0.4-dev`*
*Last updated: 2026-07-13*

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
- formal completion roots must be fresh: resume state and skipped postrun
  reports are rejected;
- formal completion roots reject all forced surface/action/target bindings;
- formal warehouse and CVRP controls require `parameter_search.enabled=false`;
  the default is disabled and warehouse preflight fails closed otherwise;
- readiness and generated `run.sh` require an entirely clean repository and
  exact equality between runtime HEAD and the prepared commit; docs-only drift
  and unrelated untracked files are not exceptions;
- the manifest model is authoritative and may be `gpt-5.6-sol`; readiness
  checks exact manifest/environment consistency rather than a hard-coded model;
- historical retry/repair labels remain readable only in legacy postrun
  artifacts and do not control the direct runtime.

## Integrated Evidence

- Final collection: `1820 tests collected`.
- Full Scion suite after the final context, launch-boundary, and postrun fixes:
  `1819 passed, 1 skipped` in `492.28s`.
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

The source worktree intentionally retains unrelated/user-owned changes and
historical untracked reports, so it must not host a formal run. The next runtime
must be an isolated clean worktree at the exact integration commit;
`git_runtime_worktree_clean` remains a hard launch boundary and must not be
bypassed.

The refreshed scope classifies all `826` status paths with no ambiguity:
`792` refactor paths to include, `34` paths to preserve/exclude, and `0`
unresolved paths. The excluded set is the user-owned measurement-readiness
change plus `33` old/future untracked documents.

The integration commit contains exactly the audited refactor scope. No push or
formal experiment has occurred. The user-owned change in
`scion/docs/v0.4-measurement-readiness.md` remains outside the commit and must
remain untouched.

The first prepared warehouse root at commit `09af19d2` was never launched and
must not be reused: readiness correctly stopped on an invalid generic API-key
environment and the focus-projection required-bit regression. Rebuild from the
new commit with the dedicated proxy-key environment after readiness is green.

## Immediate Queue

1. Verify the integration commit contains the audited `792`-path refactor
   manifest and none of the `34` excluded paths.
2. From that commit, create an isolated detached clean runtime worktree;
   preserve excluded user/history files in the source worktree, rebuild
   prepared artifacts in the clean runtime root, and run the real completion
   preflight including auth/non-empty response and exact commit identity.
3. Run one warehouse production control and review proposal, code, receipts,
   Contract, Verification, Protocol, Decision, normalization events, and
   postrun artifacts. If screening continues, verify the next candidate uses
   the same branch's experiment evidence and verified source.
4. Run one clean, non-target-bound CVRP campaign from the same runtime.
5. Judge research effectiveness from actual algorithm hypotheses, executable
   multi-file code, attributable solver behavior, and full-solver outcomes.

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
