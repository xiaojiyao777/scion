# Independent VRP Research Agent Control - 2026-06-15

## Purpose

This run is an external process-quality control for Scion v0.4 CVRP research.
The subagent was explicitly forbidden from reading `scion/`, `TASK.md`, Scion
design docs, Scion audit reports, and Scion experiment reports. It could only
study standalone `vrp/` code, non-Scion CVRPLIB data/results, and its own
experiment logs.

The purpose is not to replace Scion Protocol evidence. The purpose is to test
whether a plain Codex research process can find a plausible VRP baseline
improvement under similar local tooling, then feed that as a hypothesis/control
signal for Scion.

## Artifacts

- Root:
  `/home/clawd/research/scion-experiments/v04-independent-vrp-research-agent-20260615`
- Research log:
  `/home/clawd/research/scion-experiments/v04-independent-vrp-research-agent-20260615/research_log.md`
- Summary:
  `/home/clawd/research/scion-experiments/v04-independent-vrp-research-agent-20260615/summary.md`
- Candidate patch:
  `/home/clawd/research/scion-experiments/v04-independent-vrp-research-agent-20260615/candidate.patch`
- Paired comparison:
  `/home/clawd/research/scion-experiments/v04-independent-vrp-research-agent-20260615/paired_comparison_medium2opt.csv`

The local worktree currently contains the candidate edit in `vrp/src/solver.py`
for inspection only. It is not committed.

## Protocol

Both baseline and candidate used the standalone `vrp/` runner:

```bash
cd /home/clawd/research/or-autoresearch-agent/vrp
/usr/bin/python3 run_full_experiment.py cvrplib --subsets A B P E X --seed 0 --time-limit 0.05 --bks-time-limit 1 --large-time-limit 0 --large-dimension 2001 --workers 2 --instance-timeout 20 --timeout-slack 5 --memory-mb 2048 --vns-iterations 50 --cw-threshold 1000 --vns-threshold 200 --alns-threshold 1000 --max-destroy-customers 80 --progress-every 20
```

Evaluation set:

- Subsets: complete `A`, `B`, `P`, `E`, and `X` EUC_2D instances found by
  `vrp/src/parser.py`.
- Seed: `0`.
- Per-instance BKS time limit: `1.0s`.
- Main paired comparison counts only rows where both baseline and candidate are
  CVRP-feasible and benchmark-feasible (`routes <= bks_routes`).

## Mechanism

The final candidate is intentionally narrow:

- Keep full VNS unchanged for small instances where
  `num_customers <= vns_threshold`.
- For instances above the full VNS threshold, run `two_opt_intra` after initial
  construction and after ALNS repair.

Rationale: the largest standalone VRP gaps were concentrated on X-family
medium/large cases where full VNS is skipped. Route-internal 2-opt can remove
poor route ordering without invoking full VNS and without changing route count.

A rejected first attempt added a new `relocate_intra` operator to small-instance
VNS while also adding medium/large 2-opt polish. It improved X but regressed
A/E small cases, so the final candidate removed that operator and changed only
the medium/large polish schedule.

## Results

Raw rows:

- Baseline: `185` rows, all `ok`, all CVRP feasible, `115`
  benchmark-feasible rows.
- Final candidate: `185` rows, all `ok`, all CVRP feasible, `114`
  benchmark-feasible rows.

Paired core where both runs are benchmark-feasible (`114` rows):

| Scope | N | W/L/T | Mean Cost Delta | Median Cost Delta | Baseline Mean Gap % | Candidate Mean Gap % |
|---|---:|---:|---:|---:|---:|---:|
| ALL | 114 | 39/1/74 | -58.59 | 0.00 | 3.3243 | 3.1658 |
| A | 24 | 2/0/22 | -0.21 | 0.00 | 1.2157 | 1.1911 |
| B | 18 | 0/1/17 | 1.94 | 0.00 | 1.1260 | 1.2737 |
| E | 7 | 1/0/6 | -2.14 | 0.00 | 2.0926 | 1.8010 |
| P | 18 | 2/0/16 | -0.28 | 0.00 | 1.8965 | 1.8495 |
| X | 47 | 34/0/13 | -142.32 | -101.00 | 5.9733 | 5.6062 |

Top X improvements:

- `X-n641-k35`: `-484` cost.
- `X-n895-k37`: `-426` cost.
- `X-n801-k40`: `-421` cost.
- `X-n1001-k43`: `-366` cost.
- `X-n411-k19`: `-309` cost.

Main risks:

- `B-n45-k6` lost benchmark feasibility: baseline used 6 routes; candidate used
  7 routes.
- `B-n66-k9` was the only paired-core objective loss: `+35` cost.
- The protocol is wall-clock limited. Single-seed, single-run effects may
  include cutoff noise.
- Runtime increased on X because additional route-internal 2-opt work is run on
  medium/large instances.

## Interpretation

This is a strong external-control research signal, not Scion promotion
evidence. A plain Codex agent, without Scion context, found a targeted
medium/large VRP mechanism with clear X-family improvement and limited paired
regression in a single-seed benchmark. That makes it useful as a Scion
hypothesis seed.

The result also sharpens the Scion question. If Scion cannot generate or carry
forward a similarly simple "full VNS threshold leaves medium/large route-order
slack; add cheap intra-route polish" hypothesis, the issue is likely in Scion's
proposal context, branch lesson transfer, mechanism-continuation policy, or
problem-owned opportunity diagnostics rather than in the absence of low-level
VRP opportunities.

## Next Gate

Do not merge the standalone `vrp/` patch from this single run. The next useful
step is a controlled replay:

1. Validate the standalone patch with at least 3 seeds or repeated wall-clock
   runs on `A/B/P/E/X`.
2. Port the mechanism concept, not the exact file patch, into the Scion CVRP
   problem package as a solver-design hypothesis or direct-solver replay
   candidate.
3. Evaluate it against Scion's measurement floor and large-X runtime evidence,
   with per-case route feasibility and runtime cost reported.
