# Scion v0.4 Current State

*Current as of: 2026-09-22*

Enter through [`../../../AGENTS.md`](../../../AGENTS.md), then read
[`../AGENT_ONBOARDING.md`](../AGENT_ONBOARDING.md) before this snapshot and
[`../../TASK.md`](../../TASK.md) after it. The sole architecture authority is
[`../../design/scion-architecture-v3.md`](../../design/scion-architecture-v3.md);
the direct-runtime addendum only narrows the current implementation. Historical
plans and experiment reports preserve evidence but do not define current runtime
authority or authorize another run.

## Checkout and verification snapshot

- Working branch: `v0.4-dev`.
- P1 and the R4/R5 documentation handoff were committed as `a112e60c`.
  P1b observation cleanup and R6 preparation were committed as `e405bfd2`.
  R6 launched from that clean revision; subsequent status edits are docs-only.
- P1b full suite: `2397 passed, 1 skipped, 0 failed` in 436.38
  seconds, with no live provider or formal campaign. From the repository root:
  `env PYTHONPATH=scion:. /home/clawd/miniconda3/envs/claw/bin/python -m pytest -q scion/scion/tests`.
  The explicit import path avoids this machine's older editable installation.
- Focused continuation tests cover cold-process startup, H-only history, source
  isolation, rollback, same-file sibling drift and exact held-out reuse.
  Targeted Ruff (`F,E9`, excluding existing star-import rules `F403,F405`) and
  `git diff --check` pass. Calendar-dependent calibration diagnostics are tested
  at explicit fresh/stale dates; runtime age limits are unchanged.
- P1b focused observation/evidence/boundary tests: 103 passed; additional
  campaign/held-out regression tests: 48 passed. The previous P1 suite passed
  2393 tests. Protocol gates and Safe Features are unchanged.
- R4, R5 and R6 are terminal. R6 ended normally at expanded screening as
  `NOT_CONFIRMED`; its terminal file was written by `16:44:12.811Z` on September
  21. Its tmux pane is now dead with status zero. Raw terminal and
  metric evidence below establish completion independently of the carrier.
- R7 completed normally at `2026-09-22T03:23:30.659934+00:00` after 12 evaluated
  screening stages and one Contract rejection. No promotion or held-out stage.
  Its final positive initial screen requests expansion, but the terminal campaign
  must not resume. The pane is dead; JSON, not carrier status, establishes completion.
- R8 launched once at `2026-09-22T14:45:38.550230+00:00` in
  `scion-r8-r7-final-b0-20260922`, driver PID 117138. Runtime is unchanged;
  preparation adds docs, frozen prospective inputs and an input test only, atop
  launch HEAD `75ce0265`; the docs/input/test diff was frozen before execution
  and is being committed after launch at the user's request. Fixed-funnel/R7/R8 tests: 27 passed
  in 0.55 s; read-only `--check` returned `PREPARED` before launch. Source
  snapshots exist and strict canary has passed; expanded screening is executing.
  No terminal or completed formal-stage result yet at this launch check.

A new session must re-run the ordinary read-only `git` and tmux checks in
`AGENTS.md`. A commit label, tmux pane, summary, or this prose is not scientific
authority; read the exact terminal and metric artifacts linked below.

## Current runtime truth

Scion is a problem-neutral research engine. Problem algorithms, objective and
feasibility semantics, research surfaces, checks, protocol inputs, and telemetry
meanings stay in problem-owned packages. Generic core only carries typed values
through this path:

```text
problem adapter + complete safe source/history
  -> agent H research -> tainted H -> Hypothesis Contract
  -> agent C research -> tainted C -> Patch Contract
  -> isolated complete candidate workspace -> Verification
  -> problem-owned Protocol -> Safe Features -> deterministic Decision
  -> exact stage reuse, branch continuation, or promotion
```

### Persistent algorithm research space

Within a live campaign, a branch's `current` value is a complete ordinary source
tree. After Contract and Verification pass and screening completes,
`CONTINUE_EXPLORE` retains that candidate as the branch's verified provisional
head even when the scientific screen fails. The next H receives the complete safe
screening evidence and the next C edits that complete source tree. Contract or
Verification failure falls back to the last clean branch source; held-out stages
reuse the exact candidate and cannot be bypassed.

This live-branch path gives the agent depth without a host mechanism selector.
When a champion change makes another branch stale, reconcile now copies that
branch's already materialized complete tree for isolated Verification and fresh
screening against the new champion. It does not replay accepted patches or merge
champion edits. Prior H/C records remain evidence. Missing source holds the
invocation rather than reconstructing code. Decision reanchors the comparator
and resets expansion counts; later held-out stages reuse the exact candidate.

CLI `--source-tree` explicitly selects an ordinary complete directory as a fresh
baseline; absent that option, the problem root is used. Campaign composition
copies the initial source into a read-only champion snapshot. CLI versions,
branches, stages and provider counters start fresh, with optional ordered H-only
`--research-history`. Status exposes `initial_source_tree`,
`champion_source_tree` and `branches[].source_tree` as ordinary paths.

P1b replaces the seven fixed operator/policy/construction/portfolio Protocol
counter attributes with `candidate_runtime_counters`, aggregated from existing
problem declarations and carried opaquely into evidence summaries. Scalar/event
raw observations no longer use an algorithm-prefix allowlist. The host no longer
infers failure from attempted-but-unaccepted moves; actual runtime audit and
Protocol/Decision gates are unchanged. Arbitrary problem counters are excluded
from held-out exposed summaries. Historical artifacts are not rewritten.

`OperatorConfig`, `ChampionState.operator_pool` and their legacy configuration
management remain separate debt. Core has no direct Warehouse/CVRP branch, but
these interfaces still assume an algorithm shape. Terminal or interrupted
campaign state itself must not be resumed.

The source-continuation slice adds no identities, digest authority, manifests, leases,
signing, registration, receipts or reconstruction lifecycle.
Do not add another operator/mechanism field to generic runtime.
Keep future configuration cleanup separate and test-bounded; do not make it a
new scientific gate.

### Provider and bounded-session semantics

- Provider SDK retries are zero. An explicit ResourceEnvelope may redispatch the
  same frozen request a finite number of times after typed transient failures;
  every physical dispatch is charged and best-effort traced.
- Exhausting transient redispatches or a local turn/result/transcript bound after a
  session has started rejects only that attempt and schedules a fresh H. These
  operational rows do not become algorithm-failure history.
- H/C transcript total characters are unbounded by default. If a user explicitly
  sets a bound that the complete initial H context cannot satisfy before the first
  dispatch, the invocation remains `RESOURCE_EXHAUSTED`; source/history must not be
  truncated, ranked, compacted, or summarized to fit.
- A passing Code draft exported with `ready` is terminal for that session and does
  not require a second provider confirmation or closure. If the turn loop ends with
  an already passing frozen draft but no `ready`, the one final decision is only
  `finalize_patch` or `abandon`.
- The local proxy's exact synthetic no-usable-account 401 is temporary provider
  unavailability. Real/non-exact authentication, balance, explicit global call cap,
  missing provider terminal response, invalid local context, missing typed outcome,
  and interruption remain terminal or hold outcomes.

Contract, Verification, complete-pair Protocol, held-out isolation, feasibility,
protected objectives, and deterministic Decision remain necessary research
boundaries. Algorithm novelty, host mechanism preference, telemetry prose, and
incidental operational limits are not promotion gates.

## Accepted scientific state

Warehouse has demonstrated retained improvement: synthetic Scion promoted and
independently retained `v1 -> v2 -> v3`, and production-style Scion promoted and
independently retained `v1 -> v2`.

CVRP remains open:

- [`R3i`](../experiments/v0.4/v04-cvrp-r3i-long-run-adaptive-history-postrun-20260904.md)
  promoted cumulative v2 after complete expanded screening, validation, and frozen
  passes. The bundle combines dynamic perturbation frontier, post-repair
  admissibility/small-route consolidation, orientation-changing 2-opt-star, and
  inter-route 2-for-1. This is exact-bundle evidence, not component causality or
  retained superiority over original B0. R3i later stopped on provider/proxy
  infrastructure and is terminal, not resumable.
- [`R4 postrun`](../experiments/v0.4/v04-cvrp-r4-r3i-v2-retained-b0-confirmation-postrun-20260905.md)
  compared exact v2 directly with original R3i B0 on a fresh effect population.
  It completed normally as `NOT_CONFIRMED` at expanded screening: 24/24 valid
  pairs, no failures or fleet regression, case W/L/T `1/0/5`, median distance
  delta `0`, CI `[0,130.5]`, and `SCREENING_FAIL_CASE_QUALITY`. The sole winning
  case reversed sign across seeds. R4 therefore found safe but sparse/unstable
  benefit and did not expose validation, frozen, or retained stages. See the
  [terminal](/home/clawd/research/scion-experiments/v04-cvrp-r4-r3i-v2-retained-b0-confirmation-20260904/terminal.json)
  and [metric](/home/clawd/research/scion-experiments/v04-cvrp-r4-r3i-v2-retained-b0-confirmation-20260904/metrics/ab7e221a-0d68-497c-a18e-87e80451cfe1.json).
- [`R5 postrun`](../experiments/v0.4/v04-cvrp-r5-v2-2for1-ablation-postrun-20260905.md)
  records a provider-free, case-conditioned diagnostic of exact full v2 versus an
  ordinary v2 copy with only the `_exchange_2_for_1` registry entry removed. It
  completed normally as `DIAGNOSTIC_COMPLETE`: 24/24 valid pairs, no failures or
  fleet regression, case W/L/T `0/2/4`, median `0`, CI `[-281.75,0]`, and
  essentially equal runtime. On this already outcome-known R4 population, the
  result does not support including 2-for-1 and is compatible with harm on two
  cases. It is diagnostic only and cannot promote either arm. See the
  [preregistration](/home/clawd/research/scion-experiment-inputs/v04-cvrp-r5-v2-2for1-ablation-20260904/PREREGISTRATION.md),
  [terminal](/home/clawd/research/scion-experiments/v04-cvrp-r5-v2-2for1-ablation-20260904/terminal.json),
  and [metric](/home/clawd/research/scion-experiments/v04-cvrp-r5-v2-2for1-ablation-20260904/metrics/72cbb5bf-1b86-4f12-aa7c-b4ba1d8e21b7.json).

- [R6 postrun](../experiments/v0.4/v04-cvrp-r6-minus-2for1-b0-postrun-20260921.md):
  exact minus-2-for-1 versus original B0 completed 24/24 valid pairs, with no
  failures or fleet regression. Case W/L/T `2/1/3`, median `0`, CI
  `[-258,97.75]`; `SCREENING_FAIL_CASE_QUALITY` / `CONTINUE_EXPLORE`, terminal
  `NOT_CONFIRMED`. Later stages stayed unopened. X-n351-k40 lost at all four
  seeds. Both arms on both large cases had zero ALNS iterations after initial
  VNS consumed the algorithm-local budget. This is observational, not component
  causality. Server cleanup overlapped R6; its performance estimates are
  exploratory because host resource contention cannot be bounded. The original
  negative Decision is preserved. Exact
  [terminal](/home/clawd/research/scion-experiments/v04-cvrp-r6-minus-2for1-b0-20260921/terminal.json)
  and [metric](/home/clawd/research/scion-experiments/v04-cvrp-r6-minus-2for1-b0-20260921/metrics/c9a5fe82-83d3-4897-8ea8-3b428b1c208b.json).

Neither v2 nor minus-2-for-1 is a confirmed retained-B0 improvement. Both are
ordinary complete source values. Selecting the latter as R7's fresh local
baseline does not confer that scientific status.

- [R7 postrun](../experiments/v0.4/v04-cvrp-r7-autonomous-source-continuation-postrun-20260922.md):
  139 provider dispatches, 12 H/C attempts, 11 distinct evaluated candidates,
  12 screening stages, 90/90 valid pairs and no fleet regression. One positive
  initial screen became negative on expansion. The final C-branch candidate
  (`candidate-3bsvzm8k`) instead finished at initial W/L/T `2/0/1`, median `40`,
  CI `[0,608.5]`, with `SCREENING_EXPAND_REQUIRED_FOR_PASS`; no promotion.
  All three surviving complete branch trees match ordinary C continuation.
  X-n351-k40 ran zero ALNS iterations in both arms across all 26 pairs, and
  identical-comparator repeats vary greatly. Its final positive delta cannot
  be attributed to the changed ALNS code; tai100a's +38/+42 is only a discovery
  signal. R7's default champion-first order was not counterbalanced. Exact
  [summary](/home/clawd/research/scion-experiments/v04-cvrp-r7-autonomous-source-continuation-20260921/campaign_summary.json)
  and [final metric](/home/clawd/research/scion-experiments/v04-cvrp-r7-autonomous-source-continuation-20260921/metrics/24ac3290-cb42-4a19-bcd4-46f36fe4fc65.json).

## Active next work

1. Preserve the compact R4–R7 postruns and all raw terminal/source roots.
2. P1 source continuation is implemented and validated; P1b observation cleanup
   is implemented. Legacy configuration/pool terminology remains out of this slice.
3. R6 is closed without confirmation; its pre-R3 retained block remains
   unexecuted. Independent
   [Warehouse wiring diagnostics](../experiments/v0.4/v04-p1b-warehouse-aa-control-postrun-20260921.md)
   preserve the first shared-infeasible result and the second complete 4/4 A/A
   ties with deterministic negative Decision. They are not improvement evidence.
4. [R8](../experiments/v0.4/v04-cvrp-r8-r7-final-b0-preregistration-20260922.md)
   is running: R7's exact final C tree is frozen and compared with original B0
   using the existing provider-free, AB/BA-counterbalanced fixed funnel and
   seeds above 60,000. Screening remains outcome-known adaptive development;
   validation, frozen and the original retained block are still unopened.
   Gates and solver source are unchanged. This is not R7 resumption or proof
   of its pending minus-2-for-1 contrast. Fresh output:
   `/home/clawd/research/scion-experiments/v04-cvrp-r8-r7-final-b0-20260922`.
   Read its ordinary `input.json`, `terminal.json` when present and exact metric
   references. During measurement, freeze code/inputs and avoid overlapping
   tests, maintenance or another experiment. Do not restart the fresh output.

Current work excludes distribution, deployment, installation, packaging, build,
root/systemd, Trust/Hash authority, object identity, leases, signing, registration,
receipts, duplicate closure, host-selected algorithm mechanisms, and new incidental
research-quality gates.
