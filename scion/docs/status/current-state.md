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

CVRP remains open. M8 is complete: the normal `scion run` path accepts an
optional bounded `--research-input`, records it once in a fresh campaign, and
lets a problem-owned provider project ordered observations into H. Raw evidence
does not enter C, Protocol or Decision; C still receives the Contract-approved
H and editable source. Generic Scion has no CVRP/Warehouse evidence fields or
branches, and no registry, identity, hash, receipt or reopen lifecycle was
added. The design and implementation boundary are recorded in the
[autonomous prior-evidence research design](../experiments/v0.4/v04-scion-autonomous-prior-evidence-research-design-20260817.md).

M8 validation collected 1,635 tests. A broad 301-test provider-/solver-free
selection passed, including a 21-test independent boundary suite covering
exactly-once H exposure, order, absent/differently-shaped inputs, recursive
sensitive-field rejection, C isolation, authority isolation and generic-core
domain neutrality. Production Ruff F/E9, touched-file Ruff import checks,
in-memory compilation and `git diff --check` passed.

The M9 resource prerequisite is also complete. Commit `9ae49b21` adds optional
`--provider-call-cap` and `--outer-hardwall-sec` to the normal CLI. H and C
share one in-memory pre-dispatch counter; exhaustion produces
`RESOURCE_EXHAUSTED / PROVIDER_CALL_CAP_EXHAUSTED` without another provider
request or trace. The outer watchdog uses SIGTERM rather than the provider's
SIGALRM, interrupts a hung provider, and lets the runner's `BaseException` path
kill and unregister an active solver child before terminalization as
`INTERRUPTED / OUTER_HARDWALL_EXCEEDED`. Configured limits are written once as
ordinary `resource_envelope.json`; no registry or proof lifecycle was added.

M9 is terminal
`PRE_MGR_RUN_FRESH_OUTPUT_SELF_COLLISION / ONE_SHOT_CONSUMED`. Its exact
carrier passed source, input, output-absence and local proxy metadata checks.
Before `mgr.run`, however, `ExperimentProtocol` created the campaign `metrics/`
directory and `CampaignManager` then rejected that directory under the fresh
output invariant. The preserved root contains only that empty directory. H,
C, Contract, Verification, Protocol, Safe Features, Decision, provider
generation, solver and scientific observations are all zero; no typed campaign
terminal exists. This is a framework launch-path finding, not evidence about
Agent research effectiveness or CVRP algorithm quality. The exact preparation
and terminal record are in the
[M9 preregistration](../experiments/v0.4/v04-cvrp-m9-autonomous-m7-prior-development-screen-preregistration-20260817.md).

The next development task is to correct this generic initialization-order bug
and validate it offline. The M9 root must remain preserved. No deletion,
repair, live retry, resume, replacement campaign, later development stage,
R67 recovery or formal rung is authorized.

## Current validation rule

Current safe validation collected 1,668 tests and passed a broad 276-test
provider-/solver-free core/proposal/CLI selection; the 44-test resource-envelope
and signal subset also passed. Production Ruff F/E9, touched-file Ruff import
checks and formatting, in-memory compilation of 446 Python files, CLI help and
`git diff --check` passed with bytecode and pytest caches disabled.

M9 preparation additionally passed 139 isolated prior-input, context-boundary,
provider-cap and hardwall tests. All three YAML files load through production
config types; the production CVRP parser loads every selected instance and
companion solution; exact case/seed overlap checks and the 32-subprocess,
1,100 subject-second and 1,580 guarded-solver-second arithmetic pass. The
explicit `python -S -B -m scion.cli.main` entry resolves the current repository
modules and exposes the new CLI flags. These checks made no provider request,
solver call or campaign directory.

Post-attempt read-only audit found one `0700` root containing one empty `0700`
`metrics/` directory, with zero files and symlinks and no live related process.
The tracked worktree and index remained clean and production source still
matched `9ae49b21`. The bounded proxy metadata checks succeeded, but provider
generation and solver counts remained zero.

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
