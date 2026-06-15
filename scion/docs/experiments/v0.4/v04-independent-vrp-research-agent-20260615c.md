# Independent VRP Research Agent Control C - 2026-06-15

## Purpose

This is a fourth external-control run for Scion v0.4 CVRP research. The
subagent `Anscombe` (`019ecc8e-d45e-7983-b346-3621f90d38f4`) was launched as a
fresh, non-forked agent so it would not inherit Scion task context or prior
Scion conclusions.

This is intentionally not a Scion task. It tests whether a plain Codex research
subject can improve the standalone `vrp/` baseline and document its research
process without reading Scion rules, design documents, status reports, prompts,
or experiment analyses.

## Boundaries

The subagent was instructed:

- Do not read or use files under `scion/`.
- Do not read Scion design docs, `TASK.md`, audit/status docs, experiment
  reports, or Scion prompts.
- Inspect and edit only standalone VRP files, especially under `vrp/`.
- Keep all changes isolated in a separate worktree.
- Do not commit or push.

## Roots

- Main repo:
  `/home/clawd/research/or-autoresearch-agent`
- Suggested isolated worktree:
  `/home/clawd/research/or-autoresearch-agent-vrp-control-20260615c`
- Artifact root:
  `/home/clawd/research/scion-experiments/v04-independent-vrp-research-agent-20260615c`

## Required Outputs

- `research_log.md`: chronological hypotheses, commands, failures, evidence,
  and decisions.
- `candidate.patch`: patch against the standalone VRP worktree, if a candidate
  is found.
- `results/`: raw JSON/CSV paired-run outputs.
- `summary.md`: final report with benchmark shape, W/L/T, mean/median objective
  delta, feasibility and route-count regressions, runtime impact, and whether
  the result is strong enough to feed back to Scion as a hypothesis.

## Interpretation Contract

This run can produce external-control hypothesis seeds only. It is not Scion
Protocol evidence, does not change the canonical CVRP baseline, and must not be
used as a Decision feature. Any promising mechanism must be translated into a
problem-owned Scion CVRP candidate and replayed through the v0.4 measurement
and Protocol gates before adoption.

## Result

The subagent completed the run and restored its isolated worktree to baseline.
No commit or push was made, and no `candidate.patch` was created because no
tested candidate was defensible enough to retain.

Artifacts:

- Research log:
  `/home/clawd/research/scion-experiments/v04-independent-vrp-research-agent-20260615c/research_log.md`
- Summary:
  `/home/clawd/research/scion-experiments/v04-independent-vrp-research-agent-20260615c/summary.md`
- Results:
  `/home/clawd/research/scion-experiments/v04-independent-vrp-research-agent-20260615c/results`

The control used real standalone CVRPLIB data from:

`/home/clawd/research/or-autoresearch-agent/vrp/cvrplib`

Benchmark shape:

- Subset: CVRPLIB `A`
- Cases: `27` EUC_2D instances
- Seed: `0`
- Runner: `/usr/bin/python3 vrp/run_full_experiment.py`
- Time settings: `--time-limit 0.02`, `--bks-time-limit 0.2`,
  `--large-time-limit 0`
- Workers: `4`

Rejected candidates:

- C1: post-repair VNS gated by objective margins
- C2: C1 plus periodic VNS every third iteration
- C3: VNS operator ordering changed to inter-route-first
- C4: post-repair VNS gated by pre-polish acceptance
- C5: smaller ALNS destroy ratio, `5-25%`
- C6: larger ALNS destroy ratio, `15-50%`

All six candidates had worse mean objective than baseline. Positive delta is
worse:

| Attempt | W/L/T | Mean objective delta | Median delta | Feas regressions | Route regressions | Mean time delta |
|---|---:|---:|---:|---:|---:|---:|
| C1 | 5/7/15 | +3.185 | 0.000 | 0 | 0 | -0.030s |
| C2 | 6/5/16 | +1.519 | 0.000 | 0 | 0 | -0.016s |
| C3 | 4/2/21 | +0.741 | 0.000 | 0 | 0 | -0.010s |
| C4 | 6/9/12 | +3.852 | 0.000 | 0 | 0 | -0.039s |
| C5 | 6/8/13 | +2.630 | 0.000 | 0 | 0 | -0.022s |
| C6 | 4/9/14 | +2.519 | 0.000 | 0 | 0 | -0.009s |

Conclusion: this is negative external-control evidence. It shows a plain Codex
VRP researcher can run a clean hypothesis/paired-smoke process, but it did not
find a standalone VRP improvement. The result should not feed Scion a mechanism
hypothesis. It does, however, strengthen the interpretation that the earlier
real-CVRPLIB two-opt scheduling signal remains the strongest external-control
VRP hypothesis so far, while coarse VNS scheduling and destroy-ratio changes
should be deprioritized without more targeted instrumentation.
