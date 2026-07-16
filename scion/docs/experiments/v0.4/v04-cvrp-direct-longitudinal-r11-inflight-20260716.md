# CVRP Direct Longitudinal R11/R11b Inflight

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

## R11b Fresh Replacement

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

R11b is a distinct clean root, not a resume. It is the only live generative
root and the valid replacement for the infrastructure-invalid R11 invocation.

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

## Monitoring Rules

- poll no more frequently than about three minutes;
- do not signal, mutate, resume, or launch another generative root while R11b is
  live;
- treat `8` as a requested observation count, not a retry budget or semantic
  stop rule;
- audit each terminal round before making a causal attribution;
- if a second branch opens, verify that its H sees complete safe sibling
  screening history and no hidden-stage or lifecycle leakage;
- require terminal wrapper, postrun rebuild, and readiness acceptance.
