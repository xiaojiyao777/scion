# Independent VRP Baseline Research Control

Date: 2026-06-15

Purpose: run a non-Scion control in which a Codex subagent acts as an
independent VRP baseline researcher. The agent was explicitly forbidden from
reading Scion design, docs, reports, status, core, CLI, or experiment analyses.
It could only inspect the standalone `vrp/` baseline and write scratch artifacts
under `scion-experiments`.

This control asks whether a plain coding agent, without Scion's governance and
context framework, can find a plausible VRP baseline improvement and document
its research process.

## Artifacts

- Root:
  `/home/clawd/research/scion-experiments/independent-vrp-baseline-research-20260615T165347Z`
- Research log:
  `/home/clawd/research/scion-experiments/independent-vrp-baseline-research-20260615T165347Z/research_log.md`
- Scratch copy:
  `/home/clawd/research/scion-experiments/independent-vrp-baseline-research-20260615T165347Z/vrp_candidate`
- Candidate file:
  `/home/clawd/research/scion-experiments/independent-vrp-baseline-research-20260615T165347Z/vrp_candidate/src/solver.py`
- Benchmark results:
  `/home/clawd/research/scion-experiments/independent-vrp-baseline-research-20260615T165347Z/benchmark/results.csv`
- Variant summary:
  `/home/clawd/research/scion-experiments/independent-vrp-baseline-research-20260615T165347Z/benchmark/summary_by_variant.csv`
- Paired comparison:
  `/home/clawd/research/scion-experiments/independent-vrp-baseline-research-20260615T165347Z/benchmark/paired_comparison.csv`

## Mechanism

The standalone `vrp/` baseline uses ALNS plus VNS. The full-experiment
configuration skips VNS when `num_customers > vns_threshold`. The independent
researcher proposed a low-risk variant:

- keep the original full VNS path for small instances;
- for medium instances above the full VNS threshold but at or below `1000`
  customers, run only the cheap intra-route 2-opt operator;
- apply this light polish after initial construction and after ALNS repair;
- leave route count, feasibility, and data structures unchanged.

This is not a new 2-opt operator. It is a scheduling/gating change: preserve
one existing cheap neighborhood where the full VNS bundle is skipped.

## Benchmark

Command:

```bash
/home/clawd/miniconda3/envs/claw/bin/python \
  /home/clawd/research/scion-experiments/independent-vrp-baseline-research-20260615T165347Z/benchmark_runner.py
```

Design:

- standalone `vrp/` only;
- baseline original versus scratch candidate;
- `30` paired rows per variant (`10` cases x `3` seeds);
- fixed `1s` nominal time limit;
- sequential subprocess execution;
- no network and no LLM campaign.

Summary:

| variant | runs | ok | mean_gap_pct | median_gap_pct | mean_wall_time |
| --- | ---: | ---: | ---: | ---: | ---: |
| baseline | 30 | 30 | 8.7653 | 9.8646 | 1.7477 |
| candidate | 30 | 30 | 8.1732 | 8.8754 | 1.6285 |

Paired result:

- all `60` subprocesses returned `ok`;
- `17` paired rows improved, `13` tied, `0` regressed;
- X subset: `15` improved, `3` tied, `0` regressed;
- X subset average gap improved by about `0.91` percentage points.

The candidate also passed Python `compileall` in the scratch copy.

## Interpretation

This is a meaningful external control result. A plain Codex researcher, with no
Scion design or history context, found a concrete VRP mechanism, recorded the
research process, implemented it in scratch, and produced a small paired
benchmark with no observed quality regressions.

Do not overclaim:

- this is a small standalone `vrp/` benchmark, not a Scion CVRP formal protocol
  result;
- the candidate has not run the full suite;
- wall-clock stopping means small runtime differences can alter iteration
  counts;
- the contribution of initial-only polish versus repeated post-repair polish is
  not separated;
- fixed-fleet hard cases are not solved by this mechanism.

## Scion Portability Probe

A quick read-only probe found the same structural opportunity in Scion CVRP:

- `scion/scion/problems/cvrp/policies/baseline_modules/scheduler.py` runs
  embedded VNS only when `instance.customer_count <= self.vns_threshold`.
- The initial solution VNS path has the same threshold gate.
- `scion/scion/problems/cvrp/policies/baseline_modules/local_search.py`
  already registers `_two_opt_intra` as the first VNS operator.

Therefore the portable Scion hypothesis is not "add 2-opt"; Scion already has
it. The portable hypothesis is:

> For medium CVRP instances above the full VNS threshold, run a bounded
> `_two_opt_intra`-only polish after construction and/or repair, while keeping
> full VNS disabled.

This should be treated as a problem-owned solver-design candidate and evaluated
through Scion's normal Contract, Verification, Protocol, and Decision path. It
does not require putting raw VRP diagnostics into `DecisionFeatures`.

## Recommended Next Step

After the active CVRP candidate large-X replay completes, run a focused Scion
portability smoke for this mechanism:

- create a candidate patch against Scion CVRP `scheduler.py` and
  `local_search.py` only if needed;
- test current nominal and larger-X cases with direct solver replay before any
  LLM campaign;
- compare against the completed champion large-X curve and Phase A ALNS-only
  MDE;
- if the mechanism remains positive, pre-register a formal Scion candidate or
  use it as a strong hint for the next CVRP agent-debug run.
