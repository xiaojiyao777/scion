# Scion v0.4 Current State

*Current as of: 2026-09-20*

Enter through [`../../../AGENTS.md`](../../../AGENTS.md), then read
[`../AGENT_ONBOARDING.md`](../AGENT_ONBOARDING.md) before this snapshot and
[`../../TASK.md`](../../TASK.md) after it. The sole architecture authority is
[`../../design/scion-architecture-v3.md`](../../design/scion-architecture-v3.md);
the direct-runtime addendum only narrows the current implementation. Historical
plans and experiment reports preserve evidence but do not define current runtime
authority or authorize another run.

## Checkout and verification snapshot

- Working branch: `v0.4-dev`.
- HEAD: `922dbc52` (`Record R4 retained confirmation launch`), aligned with the
  local `origin/v0.4-dev` ref. The worktree includes the existing uncommitted
  documentation handoff plus the source-continuation implementation below.
- Full suite on this worktree: `2393 passed, 1 skipped, 0 failed` in 440.46
  seconds, with no live provider or formal campaign. From the repository root:
  `env PYTHONPATH=scion:. /home/clawd/miniconda3/envs/claw/bin/python -m pytest -q scion/scion/tests`.
  The explicit import path avoids this machine's older editable installation.
- Focused continuation tests cover cold-process startup, H-only history, source
  isolation, rollback, same-file sibling drift and exact held-out reuse.
  Targeted Ruff (`F,E9`, excluding existing star-import rules `F403,F405`) and
  `git diff --check` pass. Calendar-dependent calibration diagnostics are tested
  at explicit fresh/stale dates; runtime age limits are unchanged.
- R4 and R5 both ended normally. Their retained tmux panes are dead with exit
  status zero; no experiment is currently running or authorized by this file.

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

Generic models and runtime observation still retain
operator-shaped names such as `operator_pool`, `operator`, `policy`,
`construction`, and `portfolio`; there is no direct Warehouse/CVRP branch in core,
but this taxonomy is not fully algorithm-object-neutral. Terminal or interrupted
campaign state itself must not be resumed.

The source-continuation slice adds no identities, digest authority, manifests, leases,
signing, registration, receipts or reconstruction lifecycle.
Do not add another operator/mechanism field to generic runtime.
Move existing operator-shaped observation and configuration meanings toward
problem-declared or opaque values in a separate, test-bounded cleanup; do not make
that cleanup a new scientific gate.

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

Thus v2 is not a confirmed retained-B0 improvement, and v2-minus-2-for-1 is not a
champion. Both are ordinary complete source values that may inform a later,
prospectively declared development comparison.

## Active next work

1. Keep the compact R4/R5 postruns as the current interpretation and preserve both
   raw terminal roots unchanged.
2. P1 source continuation is implemented and validated. Keep the separate P1b
   operator-shaped vocabulary cleanup bounded and outside scientific gates.
3. Treat v2-minus-2-for-1 only as the R5-supported next candidate. Before any
   retained claim, compare it directly with original B0 on unseen cases and seeds
   under a prospectively frozen complete-pair protocol.
4. This documentation update does not launch an experiment. Under the user's
   existing authorization, a later agent may prepare and autonomously launch the
   next run only after code and scientific inputs are frozen, no experiment is
   active, and a fresh root plus the runbook's ordinary scientific checks are in
   place.

Current work excludes distribution, deployment, installation, packaging, build,
root/systemd, Trust/Hash authority, object identity, leases, signing, registration,
receipts, duplicate closure, host-selected algorithm mechanisms, and new incidental
research-quality gates.
