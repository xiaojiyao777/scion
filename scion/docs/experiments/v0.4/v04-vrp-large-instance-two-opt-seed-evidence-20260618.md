# VRP Large-Instance Two-Opt Seed Evidence - 2026-06-18

## Purpose

This direct WSL replay tested a small external-control mechanism seed found
outside a Scion campaign: when a CVRP instance is above the VNS threshold, run
`two_opt_intra` instead of skipping local search entirely.

This is problem-owned mechanism seed evidence only. It is not Scion Protocol
evidence, promotion evidence, or an accepted solver change. It must not enter
`DecisionFeatures`.

## Artifacts

- Result JSON:
  `/home/clawd/research/scion-experiments/v04-vrp-large-instance-two-opt-seed-20260618T230604Z/results.json`
- WSL checkout:
  `/home/xjy-ubuntu/research/or-autoresearch-agent`, commit `62d2f9c`
- Baseline worktree:
  `/tmp/or-agent-vrp-baseline`, detached at `62d2f9c`
- Candidate worktree:
  `/tmp/or-agent-vrp-candidate`, detached at `62d2f9c` plus the current
  uncommitted server diff in `vrp/src/solver.py`
- Data root:
  `/home/xjy-ubuntu/research/or-autoresearch-agent/vrp/cvrplib/XL`
- Solver time limit:
  `2s`

Candidate diff shape:

```diff
+        elif self.use_vns and self.time_limit > 0:
+            two_opt_intra(solution)
+            solution.remove_empty_routes()
...
+                elif self.use_vns:
+                    two_opt_intra(candidate)
+                    candidate.remove_empty_routes()
```

## Result

All eight paired rows completed and were feasible. The candidate won every
paired objective comparison.

| case | seed | baseline cost | candidate cost | delta | baseline elapsed | candidate elapsed | baseline iters | candidate iters | routes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `XL-n1234-k55` | 0 | 102645 | 102194 | -451 | 14.268s | 14.314s | 2 | 2 | 55 -> 55 |
| `XL-n1234-k55` | 1 | 102645 | 102194 | -451 | 15.166s | 15.140s | 2 | 2 | 55 -> 55 |
| `XL-n1608-k39` | 0 | 219388 | 54549 | -164839 | 4.163s | 5.124s | 1 | 1 | 39 -> 40 |
| `XL-n1608-k39` | 1 | 220822 | 54549 | -166273 | 4.071s | 5.403s | 1 | 1 | 39 -> 40 |
| `XL-n1981-k13` | 0 | 220071 | 36879 | -183192 | 2.931s | 13.533s | 1 | 0 | 13 -> 13 |
| `XL-n1981-k13` | 1 | 225239 | 36879 | -188360 | 21.098s | 13.784s | 1 | 0 | 13 -> 13 |
| `XL-n2028-k617` | 0 | 761677 | 720712 | -40965 | 0.003s | 0.072s | 0 | 0 | 729 -> 729 |
| `XL-n2028-k617` | 1 | 761677 | 720712 | -40965 | 0.003s | 0.070s | 0 | 0 | 729 -> 729 |

Summary:

- Completed pairs: `8/8`
- Feasible pairs: `8/8`
- W/L/T: `8/0/0`
- Route regressions: `2/8` by count, both on `XL-n1608-k39`; objective
  improved sharply in those same rows.

## Interpretation

The quality signal is real enough to treat large-instance intra-route polish as
a CVRP mechanism seed. It also explains a weakness in the current large
instance baseline: above `vns_threshold`, Scion/VRP can skip local search even
when cheap intra-route improvement remains available.

The candidate is not acceptance-ready because the runtime semantics are soft.
`two_opt_intra` is repeated first-improvement with no deadline argument. VNS
also has no deadline. `ALNSVNSSolver.solve()` checks `time_limit` only between
outer iterations, so construction, VNS, and local-search calls can overrun the
nominal solver budget. The replay makes that visible: with `time_limit=2`,
`XL-n1981-k13` candidate rows spent about `13.5s` in initial polish, while a
baseline row also reached about `21.1s`.

## Next Gate

Do not commit the current `vrp/src/solver.py` diff as-is.

Use this as a problem-owned research-focus seed for the next CVRP work only if
the implementation is made budget-aware or the protocol explicitly treats the
local-search call as part of a declared soft-budget runtime model. A suitable
next Scion hypothesis would test a deadline-aware large-instance intra-route
polish schedule against the same split and require pair-level objective,
feasibility, route-count, and wall-clock evidence.

Keep BKS gaps, case hardness, operator activation, route-count movement, and
runtime-overrun diagnostics in problem-owned reports or proposal context. They
must remain outside `DecisionFeatures`, scheduler scoring, promotion, and
generic gates.
