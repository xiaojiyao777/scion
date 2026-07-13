# Scion v0.4 Current State

*Last updated: 2026-07-13*

This is the operational resume point. Read `scion/TASK.md` first. v0.4 is in
final integration review; no experiment is running. The latest warehouse root
stopped before campaign creation on a single upstream completion timeout and
must not be restarted or reused.

## Current Decision

The refactor implementation and final scope are accepted. The initial audited
payload is `09af19d2`; the prepared-focus repair is `82dcf3fb`. The commit
containing this document includes the final postrun/preflight repair and is the
required base for a replacement clean runtime.

Do not launch successor56, resume successor55, create a targeted CVRP successor,
or bypass `git_runtime_worktree_clean`.

## Why the Refactor Was Necessary

Successor55 completed normally but remained solver-negative:

- candidate 1 pair W/L/T `10/11/27`, median `0.0`, CI `[-1.5, 0.0]`;
- candidate 2 pair W/L/T `10/9/29`, median `0.0`, CI `[-0.75, 3.0]`;
- zero promotion-grade rows and both CI highs below MDE `9.9`.

It also exposed framework failure modes:

- 12 LLM calls and `982,885` input tokens for two screened candidates;
- a correct algorithm direction blocked by exact governance metadata shape;
- successor history, target hints, telemetry dialect, and branch policy crowded
  the research problem;
- APS and postrun compatibility spread runtime truth across many helpers;
- telemetry correlation was being treated as causal evidence and gate input.

The run is now a frozen characterization fixture, not a successor template.

The visible “retry” was an old-runtime behavior, not an SDK/network retry. The
first H omitted `clean_fork_diversity_claim`; the old campaign classified that
as a proposal block that did not consume a formal round and scheduled one more
H session. Successor55 therefore used three H calls for two formal candidates.
The direct-v3 campaign now stops on the first invalid H/C response and cannot
automatically replay that provider call.

## Final Runtime Shape

```text
ProblemRuntime
  -> immutable H context
  -> one durable H provider attempt
  -> Hypothesis Contract
  -> approved H + complete SourceLedger
  -> one durable C provider attempt
  -> Patch Contract
  -> transactional workspace
  -> Verification
  -> Protocol scientific verdict
  -> safe features
  -> deterministic Decision mapping
```

Key properties:

- SDK retry is zero; every new provider call is a new durable attempt.
- Invalid structured output is labeled `invalid_response`, not repair, and any
  non-evaluated outcome stops the current campaign invocation.
- H has one canonical screening record per prior attempt.
- C has one approved hypothesis and one full multi-file source owner.
- wildcard research surfaces are expanded against the champion snapshot; every
  actual active module appears in H source and exactly once in C SourceLedger.
- context and postrun evidence are lossless; no top-N/truncation/omit-to-fit.
- CVRP live guidance is open and current-problem-owned, with no successor
  ranking, denylist, target hint, or instrumentation obligation.
- Contract uses one capability bundle and retains hard structural boundaries.
- Verification performs two candidate calls: one shared canary plus one
  determinism sample. It does not run a champion comparative slowdown veto.
- telemetry presence/actionability cannot fail Verification/Protocol or request
  another model call; real runtime faults remain hard.
- Protocol owns statistical and comparative verdicts. Decision maps them and
  does not recalculate thresholds.
- scheduler is branch-state/FIFO/active-slot only and cannot replace Decision.
- the production default is one active research branch. After an evaluated
  screening failure, the next invocation reuses that branch, giving H its
  canonical screening record and C the verified branch-current source. Wider
  branch portfolios remain explicit ablations, not the completion default or a
  budget.
- verified source, canonical screening history, and the touched-file footprint
  survive campaign reopen; durable/live records deduplicate by screening
  attempt, prior source keeps `branch_history_current` provenance, and a
  missing required verified workspace fails closed rather than falling back to
  the champion.
- generic surface fallback carries structural interface metadata only, not
  host-owned novelty, telemetry, or evidence-grading policy.
- operator-requested rounds are explicit; semantic termination budgets,
  frozen-use ledgers, circuit breakers, automatic retry counters, and hidden
  non-counting rounds are gone.
- current direct accounting reports durable H/C/provider attempts, completed
  typed Protocol rounds, candidates, and failure categories without legacy
  budget/retry quality counters.
- a hard crash that leaves a started-only attempt is reported as
  `unrecovered_in_flight`; evidence is not rewritten and no call is retried.
- scientific runtime/time-limit observations remain visible diagnostics but do
  not become Protocol or Decision reason codes.
- formal launch readiness parses the concrete command with the real CLI,
  requires completion preflight, rejects forced research targets, and rejects
  resume or skipped postrun reports;
- model readiness is configuration-driven and accepts `gpt-5.6-sol` when the
  manifest and launch environment agree.
- parameter search is disabled by default and explicitly disabled for both
  warehouse and CVRP formal controls; warehouse preflight fails closed.
- readiness and `run.sh` require the whole runtime repository to be clean and
  HEAD to equal the prepared commit exactly, including documentation state.

## Deleted Production Semantics

- APS/agentic sessions, target intent, tool selection, preview/tool registry;
- fix-code, proposal retry, partial resume, retry counters, retry scheduler;
- character/item/file/tool/session caps, truncation, top-N, compaction;
- novelty/material-difference/branch-lesson/clean-fork/same-mechanism gates;
- successor catalogs, opportunity rankings, default-avoid lists, CMT recipes;
- model-declared telemetry contracts and telemetry repair/effect-zero gates;
- heuristic branch lifecycle, plateau/stagnation steering, and soft-abandon;
- semantic termination budgets, frozen-use quotas, circuit-breaker state,
  automatic provider retry accounting, and max-round consumption flags;
- legacy agentic postrun and historical source fallbacks.

Production forbidden scans are currently clean for the K6 deletion list.

## Preserved Hard Boundaries

- response schema and typed patch parsing;
- editable/frozen path, action, import, API, interface, source digest, and
  approved-hypothesis binding;
- transactional multi-file materialization and rollback;
- syntax, feasibility, objective recomputation, state isolation,
  nondeterminism, crash, timeout, and invalid solver output;
- screening/validation/frozen split and seed isolation;
- Protocol completeness and promotion requirements;
- atomic promotion prepare/commit/recovery;
- auth, balance exhaustion, provider failure, interruption, and durable-write
  failure remain distinct typed outcomes.

## Validation Snapshot

- final collection after the latest regression additions: `1824 tests`;
- full Scion after all cleanup: `1823 passed, 1 skipped` in `485.91s`;
- final direct-writer/legacy-reader hardening: `106 passed` affected regression;
- direct warehouse/CVRP outer smokes: passed;
- scheduler/same-branch/reopen H/C evidence regression: `82 passed`;
- critical durable branch-state/failure/reopen regression: `49 passed`;
- prepared-focus builder/readiness/warehouse/CVRP regression: `115 passed`;
- post-scheduler warehouse/CVRP outer and launcher regression: `22 passed`;
- final launcher/readiness/runtime-diagnostic affected regression: `157 passed`;
- started-only/postrun artifact affected regression: `44 passed`;
- proposal/context shard: `384 passed`;
- core shard: `259 passed`;
- Contract/Verification: `173 passed`;
- Protocol/Decision: `166 passed`;
- final core/lineage/postrun cleanup: `292 + 20 passed`;
- final standard-root surrogate suite: `91 passed, 8 deselected` in `1304.93s`;
  the deselections are explicit `@slow` cases, and the warehouse adapter smoke
  now executes with path-independent absolute fixture roots;
- compile and diff checks: passed.
- affected postrun/preflight/readiness shard after the latest repair:
  `116 passed`;
- the live `gpt-5.6-sol` route returned authenticated HTTP 200/non-empty output
  immediately before the formal wrapper's next identical request hung; this is
  infra liveness evidence, not a research outcome.

## First Clean-Commit Preflight Finding

The warehouse root prepared at `09af19d2` was never launched. Real readiness
correctly stopped it for two independent reasons:

- the generic `SCION_API_KEY` environment did not contain the local proxy key;
  the replacement root must use a dedicated proxy-key environment name;
- the prompt-readiness builder marked a manifest-declared typed research-focus
  projection optional while the validator correctly required it. The builder
  now propagates `required=bool(research_focus)`; absent guidance stays optional
  and no research-quality judgment is added.

That failed prepared root is characterization evidence only and must not be
reused. Rebuild from the commit containing this repair.

The source worktree remains intentionally dirty because excluded user/history
files are preserved. It is not a formal runtime root; readiness must be run in
the isolated clean worktree at the integration commit.

## First Warehouse Launch Finding

The clean root
`v04-warehouse-direct-control-82dcf3fb-2r-gpt56sol-20260713T130254Z-claw`
started its wrapper at `13:04:12Z` and stopped at `13:05:12Z` with status `64`.
No campaign directory, execution marker, H call, C call, or candidate was
created. This is not a research result and was not retried.

The direct cause was the one `run.sh` completion preflight timing out after its
explicit 60-second provider safety timeout. The proxy stayed listening and
authenticated with one active account. Its log shows the request routed to
`gpt-5.6-sol` but no usage or HTTP terminal record; the immediately preceding
identical probe completed in 1.598 seconds. The failure is therefore classified
as an upstream/proxy-route hang, not a Scion campaign or algorithm failure.

Two framework findings followed:

- the operator workflow had manually run a live launch-readiness probe before
  `run.sh`, duplicating the launcher's authoritative preflight. The next root
  gets static/structural readiness only before launch; `run.sh` owns the sole
  real completion receipt;
- direct-runtime cleanup removed the import of
  `_prompt_context_visibility_summary` while retaining its postrun call. This
  would crash readiness for both infra-only and successful formal roots. The
  import is restored and covered through a preflight-failed-root rebuild plus
  CLI JSON/exit-code test. Authenticated timeouts are now
  `completion_timeout` and do not start an irrelevant OAuth flow.

The stopped root is immutable characterization evidence and must not be reused.
A new root requires the commit containing this repair, a new detached clean
worktree, static readiness, and an explicit operator decision to start; no
automatic restart.

## Worktree State

- branch: `v0.4-dev`;
- integration payload: `788 files changed`, `30,726 insertions`,
  `263,102 deletions` relative to the previous baseline; four rename pairs make
  those rendered entries correspond to the audited `792` underlying paths;
- status contains 33 unrelated untracked historical/future documents plus the
  user-owned tracked change below; these are excluded from the refactor scope;
- refreshed classification: `792` include, `34` exclude, `0`
  unresolved; the integration commit contains the include set only;
- renamed `check_completion_proxy.py` retains the old CLI's executable mode
  (`0755`);
- `scion/docs/v0.4-measurement-readiness.md` has a pre-existing user change and
  was deliberately not edited by this refactor;
- nothing has been pushed; one wrapper launch at `82dcf3fb` stopped in its sole
  pre-campaign completion preflight before campaign execution and is retained
  only as infra characterization evidence.

## Resume Actions

1. Verify the commit containing this document includes the postrun/preflight
   repair and excludes all `34` preserved paths.
2. Create an isolated detached clean runtime worktree at that exact commit.
   Do not stash/delete the excluded source-tree files. Prepare warehouse and
   run static/structural readiness only; do not duplicate the live completion
   probe.
3. After explicit approval, run warehouse control first; `run.sh` owns the one
   live pre-campaign completion preflight and persists its receipt.
4. If warehouse artifacts confirm the framework contract, run one open CVRP
   campaign with no successor target binding.
5. For a screening continuation, verify the second candidate remains on the
   same branch and sees the first screening evidence/current verified source.
   Treat `typed_edit_noop_dropped` or `patch_set_composition` as
   characterization-only unless explicitly reviewed.
6. Update this file with actual formal-control evidence, not implementation
   expectations.

During formal controls, poll observably at low frequency (normally every three
minutes; 2--5 minutes only when justified by state). Polling must never
schedule a replacement H/C attempt.

## Runner Notes

Server `claw`:

- repo: `/home/clawd/research/or-autoresearch-agent`;
- Python: `/home/clawd/miniconda3/envs/claw/bin/python`;
- use for focused tests and one formal run at a time.

WSL `scion`, only after a fresh connectivity and preflight check:

- repo: `/home/xjy-ubuntu/research/or-autoresearch-agent`;
- runner copy:
  `/home/xjy-ubuntu/research/or-autoresearch-agent-v04dev-runner-20260629`;
- Python: `/home/xjy-ubuntu/miniconda3/envs/scion/bin/python`;
- use for large/concurrent validation.

## Pointers

- Active task: `scion/TASK.md`
- V3 architecture: `scion/design/scion-architecture-v3.md`
- v0.4 direct-runtime addendum:
  `scion/design/scion-architecture-v3-v0.4-direct-runtime-addendum.md`
- Main audit:
  `scion/reports/v04-v3-runtime-and-research-effectiveness-audit-20260712.md`
- K6 plan:
  `scion/docs/planning/v0.4/v0.4-k6-single-proposal-runtime-deletion-plan-20260712.md`
- Successor55 postrun:
  `scion/docs/experiments/v0.4/v04-cvrp-successor55-bounded-elite-solution-pool-postrun-20260712.md`
