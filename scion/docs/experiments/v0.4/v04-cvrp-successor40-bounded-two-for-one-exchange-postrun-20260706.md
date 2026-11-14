# v0.4 CVRP Successor40 Postrun: Bounded Two-for-One Exchange

Date: 2026-07-06

Run root:
`/home/clawd/research/scion-experiments/v04-cvrp-successor40-bounded-two-for-one-exchange-server-2r-gpt55-20260706T035458Z-claw`

Commit: `547c4e5f`

## Verdict

Successor40 completed valid/complete/postrun-ready with local `gpt-5.5`, two
effective screening rows, and no promotion. Do not long-run this line. Treat
unchanged `bounded_two_for_one_exchange` and the guarded load-imbalance
follow-up as reviewed below-MDE evidence for v0.4.

The run did prove the target-intent binding and code path worked: live
target-intent, hypothesis, code, smoke, verification, and formal candidates
stayed on `policies/baseline_modules/local_search.py` and
`bounded_two_for_one_exchange`. The solver mechanism activated with direct
runtime/objective telemetry. The evidence was still below MDE and loss-prone.

## Screening Rows

| Row | Mechanism action | Median delta | CI | Pair W/L/T | Case W/L/T | Decision |
|---|---|---:|---|---:|---:|---|
| 1 | add `bounded_two_for_one_exchange` | 0.0 | [-6.0, 1.0] | 9/12/11 | 1/1/6 | continue_explore |
| 2 | guarded same-mechanism refinement | 0.0 | [-2.0, 0.0] | 4/8/20 | 1/2/5 | continue_explore; lineage parked |

Measurement readiness was `ready`, but MDE remained 9.9. Both row CI highs
were below MDE.

## Case Pattern

Row 1:

- A-n64-k9 was the only positive case gate: median +8.0.
- B-n63-k10 was negative: median -3.0, including one -40.0 loss.
- CMT2 was negative: median -7.5.
- CMT4 was mostly tied with one loss: median 0.0, mean -1.5.
- X-n110-k13 was negative: median -6.0, including one -46.0 loss.
- M-n200-k17 was all ties.

Row 2:

- The guarded refinement reduced runtime and many losses, but mostly by
  suppressing activation into ties.
- A-n64-k9 stayed weak-positive: median +3.0.
- B-n63-k10 worsened: median -7.0.
- CMT2 remained negative: median -2.0.
- CMT4, M, and X became all ties.

## Mechanism Quality Notes

The first implementation inserted `_bounded_two_for_one_exchange` before
`_two_opt_star`, scanned bounded route pairs, and accepted up to two strict
2-for-1 / 1-for-2 two-route exchanges. It produced direct objective-effect
telemetry on most pairs, but the local strict delta did not translate into
aggregate solver improvement. The likely failure mode is trajectory
interference: an early local gain changes the downstream budget-exhausting
VNS/ALNS path and can lose more than it gains on B, CMT2, and X cases.

The second implementation added load-imbalance gating, a minimum delta margin,
and at most one accepted move. It cut median phase runtime from roughly 3.9s
to roughly 0.5s and protected CMT4/M/X by no-op behavior, but it did not create
a positive final objective signal. It also remained negative on B and CMT2.

This is not primarily a measurement-gate false negative. The rows are
below-MDE, but the case pattern is not a plausible near-promotion signal: row 1
is mixed and loss-heavy; row 2 is mostly no-op with residual losses.

## LLM/Quality Observations

The run had 13 LLM traces:

- 4 `hypothesis_target_intent`
- 4 `hypothesis`
- 2 `tool_selection`
- 3 `code`

All used local `gpt-5.5`; no model availability issue was observed.

Two hypothesis attempts were quality-blocked before code generation because
the model named the right mechanism but did not put `material_difference` and
`branch_lesson_usage.clean_fork_diversity_claim` in the exact structured shape
required by the CVRP solver-design causal-path contract. The later attempts
recovered after retry constraints.

One code attempt required retry because `mechanism_changes` was omitted from
the patch payload. The retry repaired the identity mismatch and completed.

These are proposal-quality/structured-output stability issues, not evidence
that the agent saw a truncated or wrong target. The prepared successor40
obligations and target file were visible enough for the successful attempts to
stay on mechanism and file.

## Next Action

Park same-mechanism successor40 follow-up for v0.4. The next CVRP slot should
clean-fork to a different CVRP-owned causal path, with direct mechanism
objective-effect telemetry and explicit CMT2/CMT4 protection. Do not spend the
next slot on another bounded two-for-one exchange threshold/gating variant
unless a new design explains why the B/CMT2 losses and row-2 no-op collapse no
longer apply.

Implemented follow-up: CVRP research guidance now treats
`bounded_two_for_one_exchange` as reviewed/default-avoid evidence and blocks
unchanged successor40 repeats in the hypothesis-quality default-avoid gate.
The next prepared target is successor41 `route_skeleton_regret_repair`, a
repair-boundary clean fork with direct pre-VNS repair-effect telemetry.
