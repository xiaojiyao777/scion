# Independent VRP Research Agent D - 2026-06-15

## Purpose

This is an external-control VRP-only research artifact. The subagent was a
fresh, non-forked plain Codex researcher and was forbidden from reading
`scion/`, `TASK.md`, Scion design docs, status docs, or experiment reports.

The goal was to test whether an uncontaminated Codex research subject can study
the standalone `vrp/` baseline, run bounded experiments, and produce a useful
candidate or negative research record. This is process-control and hypothesis
seed evidence only. It is not Scion Protocol evidence and does not alter
`DecisionFeatures`.

## Artifacts

- Root:
  `/home/clawd/research/scion-experiments/v04-independent-vrp-research-agent-20260615d`
- Research log:
  `/home/clawd/research/scion-experiments/v04-independent-vrp-research-agent-20260615d/research_log.md`
- Baseline reproduction:
  `/home/clawd/research/scion-experiments/v04-independent-vrp-research-agent-20260615d/baseline_reproduction.md`
- Hypotheses:
  `/home/clawd/research/scion-experiments/v04-independent-vrp-research-agent-20260615d/hypotheses.md`
- Candidate comparison rows:
  `/home/clawd/research/scion-experiments/v04-independent-vrp-research-agent-20260615d/experiments.csv`
- Final report:
  `/home/clawd/research/scion-experiments/v04-independent-vrp-research-agent-20260615d/final_report.md`
- Candidate patch:
  `/home/clawd/research/scion-experiments/v04-independent-vrp-research-agent-20260615d/candidate.patch`

The subagent reported that all source edits stayed inside the artifact work
copy and that solver experiments were run serially.

## Baseline Reproduction

The baseline reproduction covered four real CVRPLIB cases plus one additional
seed for `B-n78-k10`:

| case | seed | budget_s | baseline objective | routes | runtime_s |
| --- | ---: | ---: | ---: | ---: | ---: |
| `A/A-n32-k5.vrp` | 0 | 1 | 784.0 | 5 | 1.0009 |
| `B/B-n78-k10.vrp` | 0 | 1 | 1251.0 | 11 | 1.0108 |
| `B/B-n78-k10.vrp` | 1 | 1 | 1251.0 | 11 | 1.0429 |
| `X/X-n101-k25.vrp` | 0 | 1 | 28425.0 | 27 | 1.1200 |
| `X/X-n200-k36.vrp` | 0 | 2 | 61796.0 | 38 | 3.1002 |

`X-n200-k36` exceeded the nominal 2s budget because the standalone baseline
runs initial VNS outside a strict time check. Treat that as baseline runtime
semantics to validate before expensive replay.

## Candidate Result

The selected candidate is H3, `route_elimination`. The patch adds a VNS
neighborhood that tries to delete one route and greedily reinsert its customers
into other routes, accepting only if total cost does not increase.

Reported comparison signal:

| case | seed | objective delta | route delta | note |
| --- | ---: | ---: | ---: | --- |
| `B/B-n78-k10.vrp` | 0 | 0.0 | -1 | route-count improvement |
| `B/B-n78-k10.vrp` | 1 | -1.0 | -1 | objective and route improvement |
| `X/X-n101-k25.vrp` | 0 | 0.0 | 0 | neutral |
| `X/X-n200-k36.vrp` | 0 | -376.0 | -1 | objective and route improvement |
| `A/A-n32-k5.vrp` | 0 | 0.0 | 0 | neutral |

Other explored candidates were not selected:

- H1 periodic VNS was mixed: improved `B-n78-k10 seed0` and `X-n200-k36`, but
  regressed `X-n101-k25` by `+348` objective and `+1` route.
- H4 regret-4 repair was neutral on the B smoke and slower.
- H3b final-only route elimination preserved some signal but was weaker than H3
  on `X-n200-k36`.

## Interpretation

This is a positive external-control research signal: a plain Codex researcher,
without Scion context, found a small route-count-pressure mechanism with
non-negative smoke behavior on the tested rows and objective/route improvement
on `B-n78-k10 seed1` and `X-n200-k36 seed0`.

It is not merge-ready evidence. The case/seed count is small, the largest row
already has loose runtime semantics, and the candidate adds another VNS
neighborhood that can increase runtime. The next useful step is an independent
no-LLM validation replay, not direct adoption into Scion.

Recommended validation before using this as a Scion hypothesis seed:

- Run H3 against standalone baseline on broader `A/B/P/E` quick cases and a
  selected `X` subset.
- Use at least three seeds on B and X rows.
- Record route count, objective, feasibility, and runtime separately.
- Add timing around initial VNS or otherwise document that pre-loop VNS can
  exceed nominal budgets.

## Boundary Note

This artifact may inform future problem-owned hypothesis seeds. It must not be
treated as Scion Protocol evidence, promotion evidence, or generic Decision
input.
