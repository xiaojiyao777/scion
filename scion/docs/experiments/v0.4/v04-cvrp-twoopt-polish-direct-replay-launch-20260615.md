# CVRP Two-Opt Polish Direct Replay Launch - 2026-06-15

## Purpose

This no-LLM direct replay tests the strongest independent VRP-control hypothesis
inside Scion's CVRP problem package without changing generic core or
`DecisionFeatures`.

Hypothesis: under the weaker `USE_VNS=False` ALNS-only research surface, cheap
`_two_opt_intra` polish after construction and ALNS repair may recover route
ordering quality that the disabled full VNS would otherwise miss.

This is problem-owned CVRP solver-design evidence only. It is not a promotion
claim and does not alter the canonical ALNS+VNS baseline.

## Roots

- Server root:
  `/home/clawd/research/scion-experiments/v04-cvrp-twoopt-polish-direct-replay-20260615T1820Z`
- WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-twoopt-polish-direct-replay-20260615T1820Z`
- WSL tmux smoke session:
  `scion_cvrp_twoopt_smoke_20260615T1820Z`
- Server repo branch:
  `codex/v04-evidence-repair-plan`

## Candidate Construction

The replay creates experiment-owned copied CVRP problem-package workspaces from
the current WSL checkout:

- `workspaces/baseline_alns_only`: applies `patches/alns_only.patch`
- `workspaces/candidate_twoopt_polish`: applies
  `patches/alns_only_twoopt_polish.patch`

The baseline patch only sets:

```python
USE_VNS = False
```

The candidate patch also reuses existing `_two_opt_intra` and runs it when full
VNS is skipped or disabled:

- initial construction phase: `two_opt_polish_initial`
- embedded ALNS repair phase: `two_opt_polish_embedded`

The patch records phase and move telemetry so the postrun can distinguish a
real mechanism activation from a no-op objective tie.

## Smoke Design

The launched smoke replays baseline and candidate on a small paired set before
large-X:

- Cases:
  - `cvrplib/B/B-n45-k6.vrp`
  - `cvrplib/B/B-n66-k9.vrp`
  - `cvrplib/A/A-n80-k10.vrp`
  - `cvrplib/M/M-n200-k17.vrp`
- Seeds: `11`, `29`, `43`
- Time limit: `30s`
- Parallelism: `2`
- Timeout padding: `300s`
- No LLM calls and no APS calls

Launch command on WSL:

```bash
cd /home/xjy-ubuntu/research/scion-experiments/v04-cvrp-twoopt-polish-direct-replay-20260615T1820Z
PARALLELISM=2 TIMEOUT_PADDING_SEC=300 bash scripts/run_wsl_direct_replay.sh smoke
```

Expected smoke outputs:

- `results/baseline_smoke/summary.csv`
- `results/candidate_smoke/summary.csv`
- `results/smoke_compare.paired.csv`
- `results/smoke_compare.summary.json`

## Large-X Gate

Large-X is not launched automatically. It should run only if smoke shows:

- no feasibility regressions;
- no route-count regressions on paired completed rows;
- no repeated B-family objective regression;
- candidate two-opt phase telemetry is nonzero or the postrun explains why it
  is a principled no-op;
- invalid/timeout rows are not worse than baseline.

If accepted, the large-X replay should run the candidate against the completed
ALNS-only champion large-X curve:

- Cases: `X-n401-k29`, `X-n573-k30`, `X-n641-k35`, `X-n1001-k43`
- Seeds: `61`, `67`, `89`
- Multipliers: `1`, `4`
- Baseline summary:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-largeX-runtime-curve-20260615T150454Z/summary.csv`

## Boundary Note

All BKS gap, runtime, best-update, two-opt activation, and paired-delta evidence
from this replay is postrun/proposal-context material only. It must not enter
generic `DecisionFeatures`. If this replay is positive, the next LLM campaign
should pass the result as a concise human-approved problem-owned hypothesis
seed, not as a deterministic promotion feature.

## Smoke Result

The smoke completed on WSL at `2026-06-15T18:33:13Z` and was synced back to the
server root. Wrapper exit was `0`.

Summary artifact:

`/home/clawd/research/scion-experiments/v04-cvrp-twoopt-polish-direct-replay-20260615T1820Z/results/smoke_compare.summary.json`

Aggregate paired result:

- Completed pairs: `12`
- W/L/T: `9/3/0`
- Mean candidate-minus-baseline delta: `-3.4167`
- Median candidate-minus-baseline delta: `-3.5`
- Route-count regressions: `0`
- Fleet regressions: `0`
- Candidate best-update count: `134`
- Candidate two-opt accepts: `9` initial and `3739` embedded

By case:

- `A-n80-k10`: W/L/T `3/0/0`, mean delta `-3.0`
- `B-n45-k6`: W/L/T `1/2/0`, mean delta `+5.3333`
- `B-n66-k9`: W/L/T `2/1/0`, mean delta `-3.6667`
- `M-n200-k17`: W/L/T `3/0/0`, mean delta `-12.3333`

Gate decision: do not launch large-X from this smoke as-is. The candidate was
active and had no route/fleet regression, and the aggregate signal was positive,
but the pre-registered large-X gate required no repeated B-family objective
regression. The smoke has two B-family losses on `B-n45-k6` and one on
`B-n66-k9`. Treat this as a promising but unstable scheduling hypothesis that
needs narrower gating or B-family-specific explanation before any expensive
large-X replay.

Read-only postrun analysis by subagent `Carson`
(`019ecc90-853a-7111-a164-166df16f2de6`) confirmed this gate decision. The
recommended next gate is narrower follow-up, not large-X and not full rejection:
keep the mechanism in CVRP problem-owned experiment patches and explain or gate
the B-family regressions before spending large-X budget.
