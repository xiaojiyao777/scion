# CVRP Direct Longitudinal R11/R11b Terminal Report

## R11 Launch Identity and Terminal Infra Failure

- run root:
  `/home/clawd/research/scion-experiments/v04-cvrp-direct-longitudinal-r11-8r-gpt56sol-8r-gpt56sol-20260716T114132Z-claw`;
- wrapper PID: `2878751`;
- detached runtime:
  `/home/clawd/research/or-autoresearch-agent-v04-direct-runtime-6a2f6765`;
- exact pushed code commit:
  `6a2f6765ff141b8f1d17c3fae0391df73f3ac580`;
- model/runtime: `gpt-5.6-sol / direct_v3`;
- requested typed rounds: `8`;
- scientific solver subprocess fallback: `30s`;
- completion preflight: authenticated, HTTP `200`, nonempty response;
- fresh root: no resume, force controls, retry, semantic budget, or
  truncation.

The launcher persisted an empty `SCION_API_KEY` plus only the environment name
`SCION_SHARED_PROXY_KEY`; no key value appears in launch metadata or command
arguments. R11 is the first clean generative run after the R10-derived
cross-branch canonical screening continuity and reachable no-loss validation
expansion repairs. The code commit passes the focused `168` tests, the full
Scion suite (`2053` passed, one skipped), compileall, and `git diff --check`.

R11 stopped at `2026-07-16T11:44:04Z` with wrapper exit `1`. H1 and C1 each
completed exactly one provider call and C1 reached verified-candidate artifact
recording, but the filesystem had only `4.6 MiB` free. Creating
`campaign/artifacts/verified_candidate_commits/...` raised `ENOSPC`. Therefore
R11 completed zero Protocol rounds, has `invalid_no_experiments`, and is not
algorithm evidence. Postrun reports rebuilt, but readiness correctly failed.
The root is terminal and read-only; it was not resumed or retried in place.

The generated `/tmp/pytest-of-clawd` tree occupied `7.0 GiB`; most content was
full-suite temporary and garbage directories, including deliberately read-only
test snapshots. No pytest process was active. Removing only that temporary tree
restored about `7.0 GiB` free. Historical `scion-experiments` roots were not
deleted or modified.

## R11b Fresh Replacement and Terminal Identity

- run root:
  `/home/clawd/research/scion-experiments/v04-cvrp-direct-longitudinal-r11b-8r-gpt56sol-8r-gpt56sol-20260716T115118Z-claw`;
- wrapper PID: `2879552`;
- detached runtime and exact code commit: unchanged from R11;
- model/runtime: `gpt-5.6-sol / direct_v3`;
- requested typed rounds: `8`;
- scientific solver subprocess fallback: `30s`;
- completion preflight: authenticated, HTTP `200`, nonempty response;
- fresh root: no resume, force controls, retry, semantic budget, or
  truncation.

R11b is a distinct clean root, not a resume. It is the valid replacement for
the infrastructure-invalid R11 invocation, but it is now terminal and must not
be resumed.

## R11b H1/C1 Initial Audit

H1 and C1 each completed in one provider call. H1 autonomously selected a
capacity-feasible, length-one-through-three granular CROSS exchange in
`policies/baseline_modules/local_search.py`. This is a high-level near duplicate
of R10 H4, not a new algorithm family, but the implementations are not byte
duplicates:

- both start from champion v1 hash `06820ecd...`, edit only `local_search.py`,
  and register CROSS between existing swap and two-opt-star neighborhoods;
- R10 H4 used 12-NN route/position candidates and considered segment reversal;
- R11b uses 8-NN boundary-edge filtering, retains original segment orientation,
  and records a separate `cross_exchange` phase.

The verified/executable candidate identity is `82878ff8...`, patch digest is
`4c82bcab...`, and the verified artifact, normalized code content, materialized
workspace file, source digest, and champion base agree. At the audit snapshot,
all observed candidate runtimes loaded the new operator with zero errors,
valid solutions, zero fleet violation, and no route-count change. CROSS accepted
roughly 210-229 improving moves per observed pair, so it is not dead code.

The main mechanism risk remains runtime allocation. Embedded VNS consumes about
`89-91%` of candidate algorithm time, leaving only roughly 1.8-2.2 seconds for
the ALNS core. CROSS activation is nested inside the outer VNS phase, so phase
activation is trustworthy but `cross_exchange` and `vns` accepted/delta totals
must not be added as independent gains. The implementation also overlaps the
existing 1x1 swap and omits the reversal variants available in R10 H4.

Initial screening completed `32/32` valid pairs with zero candidate or champion
failure. Case evidence was `4/1/3`, pair evidence `19/11/2`, median delta
`+4.75`, and hierarchical CI `[-2.5,13]`. Protocol returned
`expand / SCREENING_EXPAND_LOW_SNR_TRAJECTORY_DIVERGENT`; Decision
`expand_screening` committed atomically.

The preregistered expanded screening then completed `48/48` valid pairs across
12 cases and four seeds, again with zero failures. Its diagnostic raw result is
case `6/5/1`, pair `30/16/2`, median `+3`, and CI `[-3.75,15.5]`. A pure
recalculation through the unchanged gate is a borderline-negative failure, but
the corresponding Protocol/Decision transaction did not commit. This raw
matrix may inform algorithm audit; it must not be represented as a formal
Decision.

Candidate/champion ALNS iterations were `1333/1633` initially and `1344/1610`
in expansion. CROSS activated in every candidate pair, with initial
attempted/accepted telemetry `5020/3562` and expanded `4996/3479`. Embedded VNS
still consumed about `84.7-85.5%` of candidate algorithm time. Thus the operator
was real and active, but its local activity did not yield a stable end-to-end
gain across the wider split.

## R11b Terminal Transaction Failure

R11b ended at `2026-07-16T12:58:38Z`. The campaign command exited zero, but
strict postrun readiness exited `64`, making the effective outer wrapper status
`64`. Status is `valid_but_incomplete`: requested rounds `8`, completed typed
Protocol rounds `1`, two actual Protocol evaluations, and one final
`not_evaluated / EVAL_RUNTIME_ERROR` projection. Readiness fails only
`execution_outcome_integrity` and remains usable for diagnostic delegation.

The exact error is:

```text
decision completion source branch is not the persisted owner
```

`EvaluationOrchestrator` persisted the source branch while
`screening_expand_count=0`, then incremented the same in-memory source to `1`
before expanded Protocol execution. After the 48-pair matrix completed,
`DecisionCompletionStore.prepare()` correctly compared the in-memory source
payload against its durable owner and failed closed. This is a P1 framework
transaction-boundary defect, not a provider, infrastructure, solver, or gate
failure. It also left the second formal candidate artifact provisional/orphaned
because artifact publication currently precedes intent preparation; canonical
history and typed completion correctly retain only the initial screening.

The repair keeps `_prepare_expand()` side-effect free, supplies prospective
counts to Protocol and DecisionFeatures, and consumes the expansion count only
on the completed Decision target. The strict source-owner guard is unchanged.
R11b remains read-only; no Decision is backfilled and no result is replayed in
place.

## Initial Proposal State

The terminal R11 root opened one branch from champion v1 hash `06820ecd...`.
H1 completed in one
provider call and autonomously proposed a capacity-feasible regret-2
pair-insertion repair in `policies/baseline_modules/destroy_repair.py`. It
coordinates removed-customer pairs by proximity, demand compatibility, and
regret across consecutive or split placements while retaining existing
capacity, route-cap, coverage, and validation rules. C1 passed far enough to
reach artifact recording, but no Protocol result exists because of `ENOSPC`.
Do not carry this proposal or candidate into R11b; the new root must generate
its own H/C trajectory.

This is an open control. No target, action, surface, or hypothesis was forced;
the elapsed-time simulated-annealing lead from R10 is audit guidance only. The
pair-insertion mechanism must be judged by its actual code diff, activation,
throughput, objective/case/pair evidence, Protocol, Decision, and formal replay
identity rather than by proposal prose.

## Disposition and Next Action

- keep both R11 and R11b terminal and read-only;
- do not resume, backfill, or reinterpret the uncommitted expansion Decision;
- the prospective-count/atomic-target repair passes focused/adjacent review,
  the full Scion suite (`2058` passed, one skipped), compileall, and diff-check;
- commit and push the repair, then launch a fresh eight-round R11c from an
  exact clean detached runtime;
- poll R11c no more frequently than about three minutes and require wrapper,
  postrun rebuild, and readiness acceptance at terminal state.
