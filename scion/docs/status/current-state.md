# Scion v0.4 Current State

*Last updated: 2026-08-17*

Read [`../../TASK.md`](../../TASK.md) first. The sole architecture authority is
[`../../design/scion-architecture-v3.md`](../../design/scion-architecture-v3.md).
The direct-runtime addendum narrows current implementation examples only.
Historical experiment reports and Git history preserve chronology; they do not
create current execution authority.

## Objective

Warehouse acceptance is complete. Synthetic Warehouse reached and independently
retained `v1 -> v2 -> v3`; production-style Warehouse reached and independently
retained `v1 -> v2`.

CVRP remains open. B0/v1 is champion. No candidate has completed the declared
screening -> validation -> frozen -> deterministic promotion -> independent B0
retention chain. A valid negative observation or partial stage does not close
the task.

## Current boundary

The only active research path is:

```text
safe complete problem/source context
  -> Hypothesis -> Hypothesis Contract
  -> Code using the same Contract-approved ordinary H value -> Patch Contract
  -> isolated Workspace -> Verification
  -> problem Protocol -> Safe Features -> deterministic Decision
```

Retain ordinary references, exact scientific source/stage reuse, fixed
case/seed selection, minimal append-only lineage and local subprocess isolation.
Remove self-proof lifecycle: object/capability identities, owner registries,
leases, issuance/claim/spend, registration, nonce, intent/commit/closure,
activation/reopen proof, source-acceptance receipts, self-hashing manifests,
duplicate digest closure, promotion/readiness dossiers and authorization
refreeze/sentinel state machines.

Distribution, deployment, installation, packaging, reproducible-build,
root/systemd/D-Bus/cgroup/native-spawn and H11 authority work are outside the
current project boundary.

`Frozen Holdout`, split manifests, seed ledgers, ordinary source references,
problem-owned operator registries, new-directory collision protection and
subprocess cleanup remain scientific or operational mechanisms, not authority
lifecycles.

## Accepted evidence

- Warehouse exact results and roots remain in the linked experiment reports in
  [`../../TASK.md`](../../TASK.md).
- CVRP R3 contains a complete positive quality screen followed by an externally
  interrupted validation. It is valid partial science, not a promotion and not
  a resumable candidate.
- Later CVRP diagnostics and short experiments remain preserved under
  [`../experiments/v0.4/`](../experiments/v0.4/) and in the
  [longitudinal mechanism audit](../experiments/v0.4/v0.4-cvrp-longitudinal-mechanism-reopen-audit-20260815.md).
- R67 is terminal `PREP_INVALID / AUTHORIZED_PREFLIGHT_LIVE_CONTROL_ROOT_COLLISION / KNOWN_ZERO_BEFORE_SCIENTIFIC_DELEGATION`: solver, provider, Protocol and Decision observations are zero, the one-shot was consumed, and no candidate-quality conclusion exists; the complete historical record remains in its
  [preregistration](../experiments/v0.4/v0.4-cvrp-r67-provider-free-r3-cumulative-exact-source-full-funnel-confirmation-preregistration-20260815.md).
- M7-FC1 is terminal `CANDIDATE_SUBJECT_VETO`. Initial screening expanded and
  fresh expanded screening passed, but validation stopped on candidate
  `X-n200-k36`, seed 2069, after the runtime audit reported a solver algorithm
  error. No validation result, frozen result, promotion or retained-B0 result
  exists; the exact evidence and claim boundary remain in its
  [preregistration](../experiments/v0.4/v04-cvrp-m7-fc1-r3-cumulative-new-population-full-funnel-preregistration-20260816.md).

## Active work

`TASK.md` modules M0-M6 are closed. The subtraction removed the dormant
platform/activation stack, mutable owner and candidate graphs, prompt/source
identity, two-phase promotion, duplicate scheduler/status/accounting closures,
provider-call receipts and historical compatibility readers. The live path now
passes ordinary values directly: the Contract-approved H enters C in the same
call, one `CandidateWorkspace` enters Verification and Protocol, Decision
selects one branch action, and promotion is one operation.

M7-FC1 ran once under explicit authorization and is terminal
`CANDIDATE_SUBJECT_VETO / ONE_SHOT_CONSUMED`. Initial screening completed 32/32
valid pairs and expanded; fresh expanded screening completed 96/96 valid pairs
and passed. Validation then stopped on candidate `X-n200-k36`, seed 2069,
because the runtime audit reported an algorithm error while packing customer
106 into 36 routes. No validation stage metrics, frozen stage, promotion
snapshot or retained-B0 result exists.

CVRP remains open. The next work is scientific redesign from this exact
negative evidence. No repair, retry, resume, replacement, substitution, R67
recovery or automatic next formal rung is authorized.

## Current validation rule

Final isolated validation collected 1,570 tests and passed 512 provider-/formal-
run-free behavioral tests plus a 24-test stale-fixture recheck. Production Ruff
F/E9, in-memory compilation of 248 production Python files, CLI help and
`git diff --check` passed. The checks used an isolated `python -S -B` environment
with bytecode and pytest caches disabled.

No provider or formal scientific launch ran during this subtraction. Two early
local smoke/e2e pytest selections were interrupted after being recognized as
out of scope and may briefly have started local solver subprocesses; therefore
this work is not described as globally solver-zero and produced no scientific
result.

Tests whose only purpose is to prove an obsolete identity/hash/receipt/closure
topology are deleted rather than repaired. An offline reachability search may
confirm removal, but it does not become another runtime gate.

## Documentation roles

- [`../../TASK.md`](../../TASK.md): prospective modules and acceptance.
- This file: compact current operating truth.
- [`v0.4-history.md`](v0.4-history.md): curated historical milestones.
- [`../experiments/v0.4/`](../experiments/v0.4/): exact experiment designs,
  results, terminal records and claim boundaries.
- `docs/planning/v0.4/`: historical plans unless `TASK.md` explicitly adopts a
  current item.

Do not append raw authorization text, hash inventories, per-run counters or
experiment chronology here. Preserve those only in their experiment record.
