# CVRP Successor18b Postrun Review - 2026-06-29

## Scope

- Run root:
  `/home/clawd/research/scion-experiments/v04-cvrp-successor18b-43d3f64a-local-2r-gpt55-2r-gpt55-20260629T110423Z-claw`
- Commit: `43d3f64a`
- Model: `gpt-5.5`
- Purpose: verify the mechanism-granular prepared successor scheduler repair
  and continue successor17 from the mixed branch containing both suppressed
  `seed_post_optimization_selector` evidence and still-live
  `granular_savings_seed_portfolio` evidence.

## Run Result

- Wrapper exit: `0`
- Campaign status: valid and complete
- Effective rounds completed: `2`
- Proposal attempts: `2`
- Protocol-evaluated candidates: `2`
- Formal-screened candidates: `2`
- Proposal quality blocks: `0`
- Active-slot blocked attempts: `0`
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
- Max effect/MDE ratio: `0.505051`
- Max median delta: `5.0`

| Row | Mechanism | Decision | Pairs | Win Rate | Pair W/L/T | Median Delta | CI | Interpretation |
|---:|---|---|---:|---:|---:|---:|---|---|
| 1 | `granular_savings_seed_portfolio` | `continue_explore` | 48/48 | 0.583 | 32/14/2 | 5.0 | [-2.75, 12.75] | positive but below MDE |
| 2 | `exact_short_route_polish` | `continue_explore` | 32/32 | 0.250 | 8/20/4 | -5.75 | [-20.25, 0.5] | loss-heavy quality regression |

The first row confirms the scheduler fix at runtime: the mixed branch was not
blocked only because it still contained a non-suppressed mechanism. The
granular mechanism activated and kept positive aggregate signal, with strong
CMT2, CMT4, and M-n200 case medians, but the row remained below MDE and had
B/P losses.

The second row tried a construction follow-up,
`exact_short_route_polish`. It activated but produced loss-heavy evidence:
CMT2 median delta `-80.0`, CMT4 median delta `-33.5`, CI high `0.5`, and
effect/MDE `-0.580808`. The branch was parked as quality-regression evidence.

## Framework Finding

Successor18b verifies the generic repair from commit `43d3f64a`:

- Prepared successor focus can suppress problem-provided mechanism ids without
  labeling them as reviewed no-positive evidence.
- Scheduler branch exclusion is mechanism-granular: a branch is excluded only
  when all visible branch mechanism ids are reviewed or suppressed.
- Mixed branches remain schedulable, while proposal and target-intent
  authority must still reject any direct selection of suppressed ids.

No active-slot block occurred in this run.

## Next Interpretation

Successor18b is framework-positive but solver-negative:

- Do not promote or freeze CVRP from this run. Champion remains `v1`, and no
  row is at or above MDE.
- Move `granular_savings_seed_portfolio` into reviewed/default-avoid
  problem-owned evidence: it has now been expanded through repeated
  follow-ups and remains below MDE.
- Move `exact_short_route_polish` into reviewed/default-avoid problem-owned
  evidence because the follow-up was loss-heavy and parked the branch.
- Keep `seed_post_optimization_selector` suppressed, not reviewed. Revisit it
  only as an explicit activation repair with pre-protocol and formal mechanism
  evidence.
- The next CVRP attempt should clean-fork to a materially different
  non-reviewed problem-owned construction, destroy/repair, or local-search
  causal path.
