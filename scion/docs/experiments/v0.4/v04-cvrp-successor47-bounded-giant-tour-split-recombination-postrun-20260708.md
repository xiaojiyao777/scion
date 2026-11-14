# CVRP successor47 postrun: bounded giant-tour split recombination

Date: 2026-07-08

Run root:
`/home/clawd/research/scion-experiments/v04-cvrp-successor47-bounded-giant-tour-split-recombination-server-claw-2r-gpt55-2r-gpt55-20260708T021541Z-claw`

## Status

- Run status: valid / complete / postrun-ready.
- Stop reason: `max_rounds_exhausted`.
- Requested and completed rounds: 2 / 2.
- Model: local `gpt-5.5`.
- Current-run LLM calls: 7 total, all successful.
- Proposal/model/telemetry/postrun failures: none.
- Postrun readiness: ready.

## Result

Successor47 correctly tested a new CVRP-owned module boundary, but did not
produce promotion-grade solver evidence.

- Aggregate pair W/L/T: `49/50/13`.
- Official aggregate case W/L/T: `12/11/5`.
- Row 1: 48/48 valid pairs, pair W/L/T `22/22/4`, case W/L/T `6/6/0`,
  median delta `0.0`.
- Row 2: 64/64 valid pairs, pair W/L/T `27/28/9`, case W/L/T `8/7/1`,
  median delta `0.0`.
- Current-head branch-card case W/L/T: `7/6/3`.
- Current-head median delta: `0.5`, CI `[-6.0, 4.5]`.
- MDE: `9.9`.
- Promotion: none; gate reasons were `SCREENING_FAIL_WIN_RATE` and
  `SCREENING_MARGINAL_SIGNAL_CONTINUE`.

The short-run aggregate result is marginal/noisy, not a long-run candidate.
The CI high is below MDE, and the pair-level aggregate is almost exactly
balanced.

## Mechanism Evidence

The mechanism activated and recorded runtime; this was not an activation or
model-call failure.

- Row 1 observed phase runtime in 48/48 candidate runs, but positive mechanism
  best-delta/improvement count was `0/48`.
- Row 2 observed phase runtime in 64/64 candidate runs, but positive mechanism
  best-delta/improvement count was only `1/64`.
- Row 1 phase runtime weighted sum was `5237 ms`.
- Row 2 phase runtime weighted sum was `7915 ms`.

The generated mechanism used a new module,
`policies/baseline_modules/giant_tour_split.py`, with minimal scheduler
wiring. That preserved the v3 boundary. The failure was that the contiguous
giant-tour generation was too conservative: it almost never produced a direct
split-reconstructed improvement.

## Protected Cases

CMT2/CMT4 were present and unsafe.

- CMT2 row 1 median: `-17.5`; row 2 median: `-20.0`.
- CMT4 row 1 median: `-11.0`; row 2 median: `-11.0`.
- CMT2 row 2 pair deltas: `[-42, -3, 18, -37]`.
- CMT4 row 2 pair deltas: `[15, -53, 10, -32]`.

This blocks long-run promotion or same-mechanism tuning.

## Trace Audit

A delegated read-only audit inspected all 7 current-run LLM traces directly
under `campaign/llm_traces`.

- All calls used `gpt-5.5` through the `openai_compatible` provider and
  returned `ok: true`.
- `hypothesis_target_intent` selected
  `bounded_giant_tour_split_recombination` in
  `policies/baseline_modules/giant_tour_split.py`.
- `hypothesis` stayed bound to the same mechanism and included final objective,
  feasibility, route-count, and CMT2/CMT4 obligations.
- Tool selection read branch state, solver-design target preview, and
  `policies/baseline_algorithm.py`; then it stopped.
- Code generation produced a new module plus scheduler import/calls.

No fatal context truncation was found. The raw `TASK.md` and
`current-state.md` were not included as literal full files, but their current
content was projected into prepared successor focus and research obligations.
That was sufficient for target binding and implementation boundary control.

## Code Contract Gaps

The candidate satisfied the module-boundary requirement, but only partially
satisfied the evidence contract.

- It recorded generic `record_move(... attempted=1, accepted=0)` for all
  non-accepted paths.
- It did not distinguish `rejected_no_improvement`,
  `rejected_infeasible`, `rejected_route_count`, or `budget_stopped`.
- It did not expose route-pool/source diversity because the mechanism was
  contiguous giant-tour splitting rather than route-set recombination.

These gaps explain why postrun diagnostics were less informative, but they are
not enough to justify a telemetry-only solver follow-up. The mechanism itself
rarely produced direct effect.

## Decision

Park `bounded_giant_tour_split_recombination` for v0.4.

Do not long-run, threshold-tune, or create a successor47b solver follow-up.
The next CVRP optimization slot should use a materially different
problem-owned recombination path rather than a contiguous giant-tour split
variant.
