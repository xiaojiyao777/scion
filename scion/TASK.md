# Scion v0.4 Continuous Solver Research

*Working branch: `v0.4-dev`*

*Current as of: 2026-09-20*

Follow [`../AGENTS.md`](../AGENTS.md) and [`current-state.md`](docs/status/current-state.md) before acting on this board.

## Goal and authority

[`design/scion-architecture-v3.md`](design/scion-architecture-v3.md) is the sole
architecture authority. The
[`direct-runtime addendum`](design/scion-architecture-v3-v0.4-direct-runtime-addendum.md)
narrows the current implementation but adds no second authority lifecycle.
Historical plans, completed checklist chronology, and experiment reports are
evidence, not current work queues; Git preserves the superseded long task log.

The project goal is retained solver improvement produced by Scion itself:

- Warehouse is accepted. Synthetic Scion promoted and independently retained
  `v1 -> v2 -> v3`; production-style Scion promoted and independently retained
  `v1 -> v2`.
- CVRP remains open. R3i produced a promoted development bundle, but R4 did not
  confirm that bundle against original B0, and R5 is diagnostic only.

A valid negative run improves the research record but does not complete CVRP.
v0.4 closes only when both problem packages have retained improvement under
their declared independent evidence.

## Scion boundary

Scion core is problem-neutral. A problem enters through one adapter; its
algorithm, objective, feasibility rules, research surfaces, checks, Protocol
inputs, and telemetry meanings remain problem-owned.

```text
problem adapter + complete safe current source + optional ordered H-only history
  -> agent-controlled bounded source/history research
  -> one tainted structured H -> Hypothesis Contract
  -> agent-controlled bounded code research bound to that H
  -> one tainted structured C -> Patch Contract
  -> isolated complete candidate workspace -> Verification
  -> problem-owned paired Protocol -> Safe Features
  -> deterministic Decision
  -> exact stage reuse, deeper branch research, or promotion
```

### Creative space and deterministic boundaries

- H/C are tainted and cannot author Protocol, Safe Features, Decision, scheduling,
  branch state, or promotion. H may inspect complete safe ordinary source/history;
  C receives its approved H and a complete path/content source map. The host does
  not rank history or select a mechanism.
- A live branch keeps a complete verified tree as its research head. Screening
  `CONTINUE_EXPLORE` may deepen it; Contract/Verification failure cannot enter it.
  Held-out stages reuse the exact candidate, and a provisional head is not champion.
- Contract protects structure/source boundaries; Verification protects executable
  correctness; Protocol owns paired comparative science; Safe Features are the
  only deterministic Decision input. Telemetry prose is never another gate.

### Provider/session boundary

- Every deliberate turn consumes the shared cap; provider SDK retries are zero.
  An explicit ResourceEnvelope may allow up to two charged/traced redispatches of
  one frozen request after typed transient/rate-limit/proxy-unavailable failures.
  Exhaustion rejects only that attempt and does not enter algorithm history.
- Real authentication, balance, global call cap, missing terminal/typed outcome,
  invalid initial context, and interruption remain terminal or hold outcomes.
- Transcript total characters are unbounded by default. A started explicit local
  limit is attempt-local; an oversized pre-dispatch H context stays resource-
  exhausted rather than being truncated, ranked, or summarized.
- Open-session invalid actions may be revised before export. Successful Code
  `ready` exports the latest passing patch immediately with no second closure.
  A terminal H/C is never repaired or partially resumed.

### Explicit exclusion boundary

Do not add problem mechanisms to generic core; Trust/Hash authority, identity,
registries, leases, signing, receipts, or duplicate closure; host ranking,
novelty/telemetry gates, response repair, hidden retry, compression, or partial
resume; or distribution, deployment, packaging, build, root/systemd, native-spawn,
or service work. Fresh directories, local limits, cleanup, held-out inputs, exact
candidate reuse, and one necessary local equality check remain ordinary scientific
or operational facts, not authority objects.

## Current implementation facts

- Direct V3 supports K=1/K=2 inside at most three continuous branches; K=2 is an
  H drafting strategy, not qualification. Parking, reconstruction, S2c capsules,
  forced routing, novelty scorers, leases, and old prepare/resume paths are absent.
- Screening and explicit cross-campaign history are complete ordered H-only facts;
  held-out facts never enter proposals. Workspaces are ordinary isolated trees.
- Typed outcomes, H basis, StepRecord, history, raw metrics, and minimal lineage are
  the evidence path. Reports, traces, and tmux carrier state are diagnostic only.

- Stale reconciliation now copies the complete accepted branch tree for isolated
  Verification and fresh screening against the new champion. It does not replay
  patches or merge champion edits. Decision resets the comparison's expansion
  counts; held-out stages retain exact candidate reuse.
- CLI `--source-tree` selects the complete source value for a fresh campaign.
  Initial source is copied into the campaign's read-only champion snapshot;
  optional ordered H-only history remains separate from branch/stage/provider
  state. Status reports ordinary paths for initial, champion and branch source.

One separate implementation debt remains:

- Generic models and runtime observation still carry operator-shaped names
   (`operator_pool`, `operator`, `policy`, `construction`, `portfolio`). Core has
   no direct Warehouse/CVRP branch, but these names assume an algorithm shape.
   Do not extend them; migrate their meaning toward problem-declared or opaque
   observations separately from scientific gate logic.

## Scientific checkpoint

### Warehouse

- [synthetic continuous campaign](docs/experiments/v0.4/v0.4-warehouse-v3-continuity-synthetic-36stage-r8-postrun-20260808.md)
- [synthetic independent replay](docs/experiments/v0.4/v0.4-warehouse-v3-continuity-r8-heldout-replay-postrun-20260809.md)
- [production-style campaign](docs/experiments/v0.4/v0.4-warehouse-v3-production-transfer-prod12-24stage-r1-postrun-20260809.md)
- [production-style independent replay](docs/experiments/v0.4/v0.4-warehouse-prod12-independent-heldout-v1-postrun-20260809.md)

### CVRP R3i

[`R3i`](docs/experiments/v0.4/v04-cvrp-r3i-long-run-adaptive-history-postrun-20260904.md)
completed 16 formal stages before a provider/proxy infrastructure stop. Its
cumulative v2 passed expanded screening `+2.5 [0,10.5]`, validation
`+1 [0,14.5]`, and frozen `+1.25 [0,6.5]`, then promoted. The bundle combines
four changes, including inter-route 2-for-1; this is bundle-level development
evidence, not isolated causality or retained-B0 superiority. R3i is terminal and
must not be resumed.

### CVRP R4

The [R4 fixed-candidate confirmation](docs/experiments/v0.4/v04-cvrp-r4-r3i-v2-retained-b0-confirmation-postrun-20260905.md)
completed normally as `NOT_CONFIRMED` at expanded screening. It produced 24/24
valid pairs, no feasibility/fleet/runtime failure, case W/L/T `1/0/5`, median
distance delta `0`, and CI `[0,130.5]`. Protocol returned
`SCREENING_FAIL_CASE_QUALITY`; validation, frozen, and retained evidence remained
unexposed. Exact v2 is therefore not independently confirmed better than B0.

### CVRP R5

The [R5 diagnostic](docs/experiments/v0.4/v04-cvrp-r5-v2-2for1-ablation-postrun-20260905.md)
compared exact full v2 with an ordinary complete v2 copy that differed only
by removing `_exchange_2_for_1` from the default operator registry. It completed
normally as `DIAGNOSTIC_COMPLETE`: 24/24 valid pairs, no safety/runtime failure,
case W/L/T `0/2/4`, median `0`, CI `[-281.75,0]`, and essentially equal runtime.
On this already outcome-known R4 population, inclusion was unsupported and
compatible with harm. R5 cannot promote either arm; v2-minus-2-for-1 is only the
next evidence-supported candidate.

Exact R4/R5 artifacts are linked by [`current-state.md`](docs/status/current-state.md). No experiment is active.

## Ordered active work

### P0 — Close the completed evidence

- [x] Add compact [R4](docs/experiments/v0.4/v04-cvrp-r4-r3i-v2-retained-b0-confirmation-postrun-20260905.md)
  and [R5](docs/experiments/v0.4/v04-cvrp-r5-v2-2for1-ablation-postrun-20260905.md)
  postrun analyses that link to exact raw artifacts.
- [x] Preserve both external roots unchanged. Do not backfill stages, relabel R5
  as confirmation, or turn either postrun into another closure authority.

### P1 — Give the agent a durable complete algorithm workspace

- [x] Design and implement the smallest problem-neutral representation of an
  ordinary complete algorithm workspace that survives as the research value.
- [x] Replace stale-branch accepted-patch replay with direct use of an already
  materialized complete source tree; preserve rollback and exact held-out reuse.
- [x] Allow an operator to select a complete source tree explicitly as the base
  of a fresh campaign, optionally with ordinary H-only history. Do not restore
  branch/champion/provider mutable state from a terminal campaign.
- [x] Keep this path source-value based. Add no identity, digest authority,
  registration, lease, receipt, signing, replay closure, or problem-specific
  mechanism to generic core.
- [x] Do not extend generic operator/policy/construction/portfolio taxonomy while
  implementing continuation.
- [x] Verify focused branch/reconcile/workspace/context tests first, then the full
  test suite without a live provider or campaign because this touches shared
  campaign flow.

Acceptance: a live branch can deepen one complete executable algorithm for an
arbitrarily long campaign, and a later fresh process can explicitly start from a
selected complete tree without replaying a patch chain or pretending to resume a
partial campaign.

### P1b — Separate vocabulary cleanup

- [ ] In a focused slice, move existing generic operator/policy/construction/
  portfolio meanings behind problem-owned declarations or opaque observations,
  with focused tests and no new Decision/Protocol gate.

### P2 — Next CVRP evidence rung

- [ ] After P0 and the required P1 boundary work, preregister a direct comparison
  of the complete v2-minus-2-for-1 candidate against original B0 on unseen cases
  and seeds.
- [ ] Keep complete pairs, feasibility, fleet protection, practical-effect and
  uncertainty gates. Do not weaken `SCREENING_FAIL_CASE_QUALITY` merely because
  R4 or R5 was negative.
- [ ] This documentation handoff does not launch a run. Under the user's existing
  authorization, a later agent may prepare and autonomously launch it only after
  code and scientific inputs are frozen, no experiment is active, and a fresh
  output root plus ordinary runbook checks are in place.

### v0.4 closeout

- [ ] Publish a compact cross-problem report separating framework correctness,
  research efficiency, algorithm quality, and retained improvement.
- [ ] Mark v0.4 complete only after CVRP also satisfies retained improvement;
  otherwise keep the exact next falsifiable rung open.

## Verification snapshot

- Branch/HEAD: `v0.4-dev` at `922dbc52`, aligned with the local origin ref.
  Existing handoff edits and this implementation remain uncommitted.
- Full suite: `2393 passed, 1 skipped, 0 failed` in 440.46 seconds, with no live
  provider or formal campaign. Focused tests cover source isolation, a real fresh
  process, optional H-only history, stale comparison and held-out reuse.
- Targeted Ruff (`F,E9`, excluding existing `F403,F405` star-import rules) and
  `git diff --check` passed. Three older fixtures now separate source/output
  directories; calibration projection tests use explicit fresh/stale dates.
- R4 and R5 tmux panes are dead with exit status zero; their terminal JSON files
  report `NOT_CONFIRMED` and `DIAGNOSTIC_COMPLETE`, respectively.

Documentation does not replace code verification. Use
`/home/clawd/miniconda3/envs/claw/bin/python` for later focused/full tests, with
`PYTHONPATH=scion:.` from the repository root so imports use this checkout.

## Working discipline

- Read V3 before changing runtime ownership; prefer subtraction and ordinary
  values over registries, identities, gates, manifests, or proof lifecycles.
- Keep problem semantics in problem packages and generic research capability in
  Scion core.
- Use fresh experiment roots and never overwrite, resume, or rewrite terminal
  evidence.
- Freeze code and scientific inputs before spending provider/solver budget.
- Distinguish framework correctness, process health, scientific validity, and
  algorithm improvement. None implies the next.
- Never infer promotion from a positive screen, interrupted run, diagnostic
  ablation, natural-language summary, or reconstructed candidate.
