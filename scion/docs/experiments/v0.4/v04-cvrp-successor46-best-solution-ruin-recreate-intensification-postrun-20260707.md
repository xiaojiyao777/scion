# v0.4 CVRP successor46 best-solution ruin/recreate intensification postrun

Date: 2026-07-07

## Status

Successor46 is complete and valid, but not promotion-grade. Do not long-run the
unchanged candidate.

Run root:

`/home/clawd/research/scion-experiments/v04-cvrp-successor46-best-solution-ruin-recreate-intensification-server-claw-2r-gpt55-2r-gpt55-20260707T115720Z-claw`

Launcher summary:

- Status: `finished`
- Validity: `valid`
- Completeness: `complete`
- Stop reason: `max_rounds_exhausted`
- Postrun acceptance: `ready`
- Model calls: `gpt-5.5`
- Effective screening rows: `2`
- Proposal-quality blocks: `0`

## Result

Both screening rows were below MDE with no final objective effect.

- Screening pair W/L/T: `4/4/104`
- Screening case W/L/T: `0/0/28`
- Max median delta: `0.0`
- Max effect-to-MDE ratio: `0.0`
- Rows at or above MDE: `0`
- MDE at 80% power: `9.9`

Row-level postrun evidence:

- Row 1: `expand_screening`, median delta `0.0`, CI `[0.0, 0.0]`,
  win rate `0.0`; mechanism activation was missing.
- Row 2: `continue_explore`, median delta `0.0`, CI `[0.0, 0.0]`,
  win rate `0.0`; mechanism activation was observed, but effect was zero.

The round-2 mechanism runtime bucket for
`best_solution_ruin_recreate_intensification` was only `62 ms` weighted sum and
`62 ms` max, so the mechanism was barely exercised.

## LLM Trace Audit

The current-run `campaign/llm_traces/` directory contained eight current-run
traces. Nested copied or resume campaign traces were not used for this audit.

- `hypothesis_target_intent`: `1`
- `hypothesis`: `2`
- `tool_selection`: `4`
- `code`: `1`

All eight calls used `gpt-5.5` and completed successfully. Target intent,
formal hypothesis, and code generation all stayed bound to
`best_solution_ruin_recreate_intensification` in
`policies/baseline_modules/best_solution_intensification.py`.

The first formal hypothesis had a schema retry because it referenced an
invalid expected telemetry field shape. The retry fixed that. Code generation
had full source visibility and did not show target binding or context
truncation failure.

## Candidate Quality

The generated patch created one CVRP-owned module and added minimal scheduler
wiring, which is the right v3 boundary. It did not move CVRP semantics into
generic core or Decision code.

The implementation did not fully satisfy the successor46 design contract:

- It consumed the main RNG stream for rejected attempts. The hypothesis asked
  for rejected-attempt RNG or trajectory isolation.
- It triggered only after `stagnation_iterations >= segment_length`. Row 1 did
  not trigger, and row 2 triggered only once.
- It recorded attempted/accepted moves but did not separate
  `rejected_no_improvement`, `rejected_infeasible`, `rejected_route_count`, or
  `budget_stopped`.
- It did not attribute an explicit mechanism-owned best update beyond the
  accepted move record.
- CMT2/CMT4 were present in protocol coverage, but mechanism activation did not
  occur on those protected cases, so protected-case evidence is only
  protocol-level coverage, not mechanism-level proof.

## Interpretation

This is a valid weak/no-effect result, not an infrastructure failure.

The main cause is mechanism opportunity and implementation activation, not LLM
provider failure. The idea reached code, but a late single best-copy
ruin/recreate attempt after VNS-polished search gives little opportunity to
improve the incumbent. The generated implementation further reduced
evaluability by triggering too rarely and not isolating rejected RNG effects.

Two-round screening is noisy, so pair-level wins and losses should not be
overinterpreted. The zero median, zero CI high, zero case-gate wins, and the
single zero-effect activation are still enough to reject an unchanged long run.

## Next Step

Allow at most one narrow contract-repair follow-up:

`best_solution_ruin_recreate_intensification_activation_repair`

This is not threshold tuning and not a broad same-mechanism optimization. It is
only justified to test whether the original design contract can be made
observable:

- isolate rejected-attempt RNG with a child RNG or restore main RNG state;
- use a bounded stagnation trigger that produces measurable activation in a
  short screen without hardcoding cases or seeds;
- record attempted, accepted, rejected-no-improvement, rejected-infeasible,
  rejected-route-count, and budget-stopped outcomes;
- record final post-VNS candidate-vs-best delta and accepted/new-best
  attribution;
- require CMT2/CMT4 protected-case activation or record a mechanism-level
  caveat.

If this repair still produces zero objective effect, park the best-solution
ruin/recreate intensification line for v0.4 and clean-fork to a materially
different CVRP-owned causal path.
