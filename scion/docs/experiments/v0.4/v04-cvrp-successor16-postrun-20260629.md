# CVRP Successor16 Postrun Review - 2026-06-29

## Scope

- Run root:
  `/home/clawd/research/scion-experiments/v04-cvrp-successor16-78bf620c-local-2r-gpt55-2r-gpt55-20260629T075652Z-claw`
- Commit: `78bf620c`
- Model: `gpt-5.5`
- Purpose: resume from successor15, follow the active
  `granular_savings_seed_portfolio` construction branch first, and verify
  whether same-branch follow-up can convert weak-positive evidence into
  promotion-grade signal.

## Run Result

- Wrapper exit: `0`
- Campaign status: valid and complete
- Effective rounds completed: `2`
- Proposal attempts: `4`
- Protocol-evaluated candidates: `2`
- Formal-screened candidates: `2`
- Proposal quality blocks: `2`
- Stop reason: `max_rounds_exhausted`
- Champion version: `1`
- Promotions: `0`
- Postrun acceptance: ready
- Independent checker:
  `current_run_analysis_ready=true`, `delegation_ready=true`,
  `failed_required_checks=[]`, `failed_optional_checks=[]`.

## Solver Evidence

CVRP measurement readiness remained usable:

- MDE at 80 percent power: `9.9`
- Protocol rows at or above MDE: `0`
- Research-efficiency interpretation:
  `protocol_effects_below_mde_or_inconclusive`
- Max effect/MDE ratio: `0.454545`
- Max median delta: `4.5`

| Row | Mechanism | Decision | Pairs | Pair W/L/T | Case W/L/T | Median Delta | CI | Interpretation |
|---:|---|---|---:|---:|---:|---:|---|---|
| 1 | `granular_savings_seed_portfolio` | `continue_explore` | 48/48 | 32/13/3 | 7/1/4 | 4.5 | [-0.5, 12.75] | marginal positive, below MDE |
| 2 | `seed_post_optimization_selector` | `expand_screening` | 32/32 | 1/0/31 | 0/0/8 | 0.0 | [0.0, 0.0] | inactive missing activation |

The first row is useful follow-up evidence: the declared granular mechanism
activated, produced positive phase/objective telemetry, and improved the prior
successor15 median from `3.5` to `4.5`. It is still not promotion evidence:
the CI low is negative, the row remains below the `9.9` MDE, and postrun
classified it as marginal rather than weak-positive exploit evidence.

The second row should not be treated as solver progress. Its declared primary
mechanism, `seed_post_optimization_selector`, was not observed in formal
screening telemetry; all cases tied, objective effect was zero, and the
postrun opportunity diagnostic says the primary mechanism was not evaluated or
did not trigger.

## Research Behavior

Positive framework evidence:

- Prepared guidance followed the active successor15 granular construction
  branch first instead of repeating reviewed route-pair, timewarp, or
  load-complement destroy/repair paths.
- Two pre-protocol candidates were blocked for legitimate quality reasons:
  `edge_guided_repair_tournament` failed activation/runtime diagnostics, and
  `seed_ordering_tournament` failed a telemetry contract boundary check.
- Both accepted candidates reached complete formal screening with no failed
  pairs.
- Postrun analysis remained report-only:
  `DecisionFeatures`, campaign state, scheduler state, and promotion state were
  excluded from postrun mutation.

## Next Interpretation

Successor16 is effective-research evidence, not solver-improvement closure:

- Do not record `granular_savings_seed_portfolio` as reviewed/default-avoid.
  It remains the retained best checkpoint but only warrants material follow-up
  variants such as trigger, schedule, threshold, or composition changes; do not
  repeat it unchanged.
- Do not record `seed_post_optimization_selector` as
  `measured_no_positive_at_mde`; its result is inactive/missing activation, not
  evidence-complete negative solver effect. Unchanged repetition should be
  default-avoid, while an explicit activation-path repair remains permissible.
- The next CVRP run should either materially refine the granular construction
  path, repair `seed_post_optimization_selector` activation with direct
  mechanism evidence, or choose a materially different non-reviewed CVRP-owned
  causal path.
