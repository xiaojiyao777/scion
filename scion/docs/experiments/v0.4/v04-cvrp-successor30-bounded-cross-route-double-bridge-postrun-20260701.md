# CVRP Successor30 Bounded Cross-Route Double-Bridge Postrun - 2026-07-01

## Run

- Run root:
  `/home/clawd/research/scion-experiments/v04-cvrp-successor30-bounded-cross-route-double-bridge-server-2r-gpt55-20260701T052131Z-claw`
- Runner: server-local `claw`
- Commit: `9cfee8e3`
- Model: local `gpt-5.5`
- Forced target: `solver_design` / `modify` /
  `policies/baseline_modules/local_search.py`
- Required mechanism id:
  `bounded_cross_route_double_bridge_polish`
- Wrapper status: `finished`, exit `0`
- Validity: `valid`
- Completeness: `complete`
- Postrun acceptance: `ready`
- Stop reason: `max_rounds_exhausted`

Postrun artifacts:

- analysis brief:
  `postrun_acceptance/analysis_brief/cvrp_on_full.postrun_analysis_brief.md`
- research efficiency:
  `postrun_acceptance/research_efficiency/cvrp_on_full.research_efficiency.v1.json`
- summary:
  `postrun_acceptance/summaries/cvrp_on_full.summary.json`
- readiness:
  `postrun_acceptance/readiness/cvrp_on_full.postrun_acceptance_readiness.v1.json`

## Health

- Requested rounds: `2`
- Effective rounds completed: `2`
- Effective protocol rows: `2`
- Screening protocol rows: `2`
- Proposal attempts: `3`
- Proposal quality blocks: `1`
- Verification-consumed candidates: `2`
- Telemetry failures: `0`
- Failure report: `total_failures=0`
- LLM calls: `gpt-5.5=12`

The run is operationally healthy and analysis-ready. Postrun readiness reported
no failed required or optional checks, remained report-only, and did not mutate
campaign, promotion, or scheduler state.

The single proposal-quality block was a useful fail-closed guard, not solver
evidence. Static quality rejected the first patch because the hypothesis
claimed a cross-route or up-to-four-routes double-bridge perturbation, but the
patch appeared to operate on a single route only.

## Result Summary

Successor30 did not produce promotion-grade CVRP evidence. It did answer the
focused mechanism question: the required
`bounded_cross_route_double_bridge_polish` mechanism was selected, implemented
in `local_search.py`, and reached formal screening. The measured effect was
zero.

Aggregate effect-vs-MDE:

- interpretation: `all_available_ci_high_below_mde`
- MDE at 80% power: `9.9`
- protocol rows: `2`
- positive rows: `0`
- nonpositive rows: `2`
- rows at or above MDE: `0`
- rows below MDE: `2`
- rows with CI high below MDE: `2`
- max median delta: `0.0`
- max effect/MDE ratio: `0.0`
- screening pass rate: `0.0`
- screening case wins/losses/ties: `0 / 0 / 16`
- screening pair wins/losses/ties: `0 / 8 / 56`
- champion promotions: `0`

## Protocol Rows

Row 1, `bounded_cross_route_double_bridge_polish`:

- decision: `continue_explore`
- gate outcome: `fail`
- win rate: `0.0`
- median delta: `0.0`
- CI: `[0.0, 0.0]`
- effect/MDE ratio: `0.0`
- mechanism evidence: activation observed; objective effect zero
- reason codes:
  `SCREENING_FAIL_WIN_RATE`,
  `SCREENING_ZERO_WIN_STREAK_CONTINUE`
- case medians:
  - `A-n64=0.0`
  - `B-n63=0.0`
  - `CMT2=0.0`
  - `CMT4=0.0`
  - `E-n101-k14=0.0`
  - `M-n200=0.0`
  - `P-n65=0.0`
  - `X-n110=0.0`

Row 2, `bounded_cross_route_double_bridge_polish` follow-up:

- decision: `continue_explore`
- gate outcome: `fail`
- win rate: `0.0`
- median delta: `0.0`
- CI: `[0.0, 0.0]`
- effect/MDE ratio: `0.0`
- mechanism evidence: activation observed; primary effect zero
- reason codes:
  `SCREENING_FAIL_WIN_RATE`,
  `SCREENING_ZERO_WIN_STREAK_CONTINUE`,
  `SCREENING_RUNTIME_EVIDENCE_INCOMPLETE_PRESSURE`,
  `SCREENING_TELEMETRY_EFFECT_ZERO_DIAGNOSTIC`,
  `TELEMETRY_EFFECT_ZERO_DIAGNOSTIC`
- case medians:
  - `A-n64=0.0`
  - `B-n63=0.0`
  - `CMT2=0.0`
  - `CMT4=0.0`
  - `E-n101-k14=0.0`
  - `M-n200=0.0`
  - `P-n65=0.0`
  - `X-n110=0.0`

## Mechanism Telemetry

The mechanism was active and consumed time, but it did not produce accepted
improving moves:

- Row-level phase runtime was present for
  `bounded_cross_route_double_bridge_polish`.
- Telemetry effect-zero diagnostics reported:
  - `candidate_present=64`
  - `candidate_positive=0`
  - `candidate_zero=64`
  - surface fields:
    `solver_algorithm_phase_improvement_counts.bounded_cross_route_double_bridge_polish`
    and
    `solver_algorithm_phase_best_delta.bounded_cross_route_double_bridge_polish`
- Raw per-run examples show nonzero phase runtime, valid solutions, and
  `solver_algorithm_best_delta=0.0`.

## Interpretation

Successor30 is framework-positive and solver-negative. It shows the launch
binding, static-quality guard, same-mechanism retry, direct mechanism
telemetry, and postrun readiness all work. It does not show useful CVRP solver
research progress toward v0.4 closeout.

The lifecycle decision remained `continue_explore`, but for v0.4 acceptance
reading this should not be treated as a reason to keep spending branches on
unchanged `bounded_cross_route_double_bridge_polish`. The run already includes
same-mechanism follow-up and direct effect telemetry, and both rows stayed at
exact zero median delta with CI high below MDE.

## Follow-Up

- Treat unchanged `bounded_cross_route_double_bridge_polish` as
  reviewed/default-avoid for v0.4.
- Do not interpret `continue_explore` as solver-positive evidence.
- Do not spend the next branch on a renamed single-route double bridge,
  `_two_opt_star` tail exchange, ordinary Or-opt, route-segment swap, or the
  same two-route internal-fragment bridge.
- Before successor31, run a short design review for a materially different
  CVRP-owned causal path. The review should explicitly decide whether another
  bounded-local-search mechanism is still justified, or whether the next slot
  should move away from local search after route-segment, ejection-chain,
  route-pair overlap, and double-bridge lines all failed to reach useful
  effect.
