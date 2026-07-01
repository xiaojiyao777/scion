# CVRP successor32 design: post-repair effect credit weighting

Date: 2026-07-01

## Decision

Use `post_repair_effect_credit_weighting` as successor32.

Owner target: `policies/baseline_modules/scheduler.py`.

Mechanism family: `acceptance_or_adaptive_weighting`.

This is narrower than a search-state restart. It changes how ALNS destroy/repair
operator pairs receive adaptive-weight credit after repair, while leaving the
existing destroy operators, repair operators, local-search moves, construction
seeds, simulated annealing acceptance rule, and generic Scion core unchanged.

## Why this mechanism

Successor28/29 parked route-pair overlap follow-ups, successor30 parked bounded
cross-route double bridge polish, and successor31 parked adaptive embedded-VNS
runtime allocation. The next clean fork should not expand those lines unchanged.

The current scheduler already records `candidate_after_repair_distance` and
`candidate_after_polish_distance`, but operator weights are still credited with
coarse post-acceptance constants: `SIGMA_BEST`, `SIGMA_BETTER`, and
`SIGMA_ACCEPTED`. That mixes repair quality, embedded VNS/local polish,
simulated-annealing acceptance, and best-update effects into one operator score.

Successor32 should instead test whether crediting operator pairs from the
post-repair pre-polish objective effect gives the adaptive weights a cleaner
learning signal.

## Causal boundary

The mechanism may:

- compute a bounded post-repair credit from current/best objective before repair
  and `candidate_after_repair_distance`;
- apply that credit to destroy and repair adaptive weights;
- keep the existing final acceptance and best-update logic intact;
- record direct telemetry under `post_repair_effect_credit_weighting`.

The mechanism must not:

- add another destroy/removal pattern;
- add another repair insertion rule;
- add a local-search move or cross-route polish;
- change construction seed selection;
- tune embedded-VNS runtime share or cadence;
- change simulated annealing acceptance probability.

## Required evidence

Record telemetry tied to `post_repair_effect_credit_weighting`:

- operator pair and q;
- current and best objective before repair;
- candidate objective after repair and after polish;
- old coarse score and new post-repair credit;
- destroy and repair weights before and after segment update;
- operator selection counts;
- accepted and new-best counts;
- `context.record_move(..., delta=..., best_improved=...)` direct effect.

Formal postrun evidence must include `total_distance` median/CI/effect-to-MDE,
`rows_at_or_above_mde`, CMT2/CMT4/P-family and A/B/X case deltas, feasibility,
route count, runtime budget, and no telemetry/postrun failure.

## Launch intent

Use server-local `claw` for a two-round successor32 screening run with local
`gpt-5.5`.

Force:

- surface: `solver_design`
- action: `modify`
- target file: `policies/baseline_modules/scheduler.py`
- mechanism id: `post_repair_effect_credit_weighting`

If prepared guidance is stale, do not rely on an ad hoc override first. Update
the problem-owned guidance/catalog so the run root carries the correct design
intent.
