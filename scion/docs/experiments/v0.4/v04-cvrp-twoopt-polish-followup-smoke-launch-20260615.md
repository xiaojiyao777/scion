# CVRP Two-Opt Polish Follow-Up Smoke Launch - 2026-06-15

## Purpose

This no-LLM follow-up tests why the prior `USE_VNS=False + _two_opt_intra`
polish smoke was aggregate-positive but failed the pre-registered large-X gate
because of repeated B-family objective regressions.

The experiment remains problem-owned CVRP solver-design evidence only. It does
not change generic core, `DecisionFeatures`, or the canonical ALNS+VNS
baseline.

## Roots

- Server root:
  `/home/clawd/research/scion-experiments/v04-cvrp-twoopt-polish-followup-smoke-20260615T1848Z`
- WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-twoopt-polish-followup-smoke-20260615T1848Z`
- WSL tmux session:
  `scion_cvrp_twoopt_followup_1848`
- WSL repo commit at launch:
  `96ba57145e1cfd3b976d530e46b4ec85f589fd47`

The WSL code commit is the repaired CVRP runtime-boundary code used by the
valid 1R behavior debug. Later server commits before this launch were
documentation-only for this direct replay path.

## Variants

The follow-up reuses the same baseline and smoke cases as the prior replay:

- Baseline: `USE_VNS=False`
- Candidate `initial_only`: `USE_VNS=False` plus `_two_opt_intra` polish only
  after initial construction; no embedded ALNS-repair polish.
- Candidate `size70`: `USE_VNS=False` plus `_two_opt_intra` initial and
  embedded polish only when `instance.customer_count >= 70`.

The `size70` gate is a diagnostic scale gate, not a production rule. It is
intended to exclude `B-n45-k6` and `B-n66-k9` while preserving `A-n80-k10` and
`M-n200-k17`, so the postrun can separate "two-opt helps medium/large
ALNS-only rows" from "two-opt destabilizes small B rows."

Read-only analysis by subagent `Goodall`
(`019ecc9b-9639-72f2-a107-4ad72e158f29`) identified the exact regressed rows in
the prior smoke:

| Case | Seed | Baseline | Candidate | Delta | Routes | Initial accepts | Embedded accepts |
|---|---:|---:|---:|---:|---:|---:|---:|
| `B-n45-k6` | 11 | 679 | 699 | +20 | 6 -> 6 | 1 | 746 |
| `B-n45-k6` | 29 | 690 | 691 | +1 | 6 -> 6 | 1 | 715 |
| `B-n66-k9` | 43 | 1344 | 1345 | +1 | 9 -> 9 | 0 | 362 |

The regressions did not correlate with infeasibility, route-count change,
runtime budget hits, or lack of activation. They most strongly correlated with
small route-count search-dynamics interference: all losses were on route counts
`6` or `9`, while all route-count `10` and `17` rows won. Loss rows also had
fewer ALNS iterations than baseline and weaker ALNS improvement. The subagent
recommended testing a size/route-count gate and an `initial_only` ablation
before any large-X replay.

## Smoke Shape

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
cd /home/xjy-ubuntu/research/scion-experiments/v04-cvrp-twoopt-polish-followup-smoke-20260615T1848Z
PARALLELISM=2 TIMEOUT_PADDING_SEC=300 bash scripts/run_wsl_followup_smoke.sh smoke
```

Expected outputs:

- `results/baseline_smoke/summary.csv`
- `results/candidate_initial_only_smoke/summary.csv`
- `results/candidate_size70_smoke/summary.csv`
- `results/smoke_compare_initial_only.paired.csv`
- `results/smoke_compare_initial_only.summary.json`
- `results/smoke_compare_size70.paired.csv`
- `results/smoke_compare_size70.summary.json`

## Acceptance

Do not launch large-X unless a variant:

- has no feasibility, route-count, or fleet regressions;
- removes repeated B-family objective regressions from the prior smoke;
- preserves a positive aggregate signal on the non-B rows;
- records nonzero expected two-opt activation when the gate says it should run;
- has a defensible algorithmic gate that is not hardcoded to case labels.

If neither variant passes, the two-opt scheduling hypothesis should be
deprioritized or reworked using targeted VNS-hit-rate instrumentation before
any expensive large-X replay.

## Boundary Note

All paired deltas, BKS/gap, runtime, case-family, size, and two-opt activation
evidence from this replay is postrun/problem-owned diagnostic material only. It
must not enter generic `DecisionFeatures`.
