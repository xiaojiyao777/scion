# CVRP Successor17 Postrun Review - 2026-06-29

## Scope

- Run root:
  `/home/clawd/research/scion-experiments/v04-cvrp-successor17-dcf08884-local-2r-gpt55-2r-gpt55-20260629T092328Z-claw`
- Commit: `dcf08884`
- Model: `gpt-5.5`
- Purpose: resume from successor16, check whether the retained granular
  construction branch can strengthen into promotion-grade evidence, and verify
  whether the inactive seed-post follow-up is handled without wasting branch
  budget.

## Run Result

- Wrapper exit: `0`
- Campaign status: valid and complete
- Effective rounds completed: `2`
- Proposal attempts: `2`
- Protocol-evaluated candidates: `2`
- Formal-screened candidates: `2`
- Proposal quality blocks: `0`
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
- Max effect/MDE ratio: `0.30303`
- Max median delta: `3.0`

| Row | Mechanism | Decision | Pairs | Pair W/L/T | Case W/L/T | Median Delta | CI | Interpretation |
|---:|---|---|---:|---:|---:|---:|---|---|
| 1 | `seed_post_optimization_selector` | `continue_explore` | 48/48 | 2/2/44 | 0/0/12 | 0.0 | [0.0, 0.0] | inactive missing activation |
| 2 | `granular_savings_seed_portfolio` | `expand_screening` | 32/32 | 16/8/8 | 4/2/2 | 3.0 | [-0.5, 12.75] | weak positive, below MDE |

The first row is not solver progress. It was scheduled as a
`pending_retry_diagnostic_followup` from the resumed branch and had no new
proposal session. The declared primary mechanism was again missing in formal
screening telemetry; objective effect was zero, and phase telemetry only showed
the generic construction/ALNS/VNS buckets.

The second row is useful but still below-MDE construction evidence. The
declared granular mechanism activated and produced positive objective
telemetry. It improved A-n64, CMT2, CMT4, and M-n200, regressed E-n101 and
P-n65, and tied B-n63 and X-n110. The effect is weaker than successor16's
48-pair granular checkpoint, so this does not close the solver gap.

## Framework Finding

Successor17 exposed one remaining prepared-run scheduling gap:

- Reviewed no-positive mechanisms were already suppressed by prepared
  successor focus, but a mechanism with repeated missing activation was not
  represented in the same field-driven scheduler contract.
- As a result, the resumed `seed_post_optimization_selector` diagnostic branch
  consumed the first Protocol row even though successor16 had already shown
  the same missing-activation failure.

The local repair is generic: prepared research focus now supports
`suppressed_mechanism_ids` in addition to `reviewed_mechanism_ids`.
Scheduler, target-intent, formal hypothesis, and schema-preview paths treat
those ids as proposal-visible prepared-run exclusions while keeping the reason
problem-owned and outside `DecisionFeatures`.

CVRP uses this field for `seed_post_optimization_selector` because successor16
and successor17 both observed missing activation. It is not added to the
reviewed no-positive catalog, because missing activation is not
evidence-complete negative solver effect.

## Next Interpretation

Successor17 is effective-research evidence plus a small scheduling repair:

- Do not promote or freeze CVRP from this run. Champion remains `v1`, and no
  row is at or above MDE.
- Keep `granular_savings_seed_portfolio` as marginal weak-positive evidence,
  not reviewed/default-avoid closure. Further continuation should be a
  stronger material variant that addresses E/P/X variability and the MDE gap.
- Suppress unchanged `seed_post_optimization_selector` for prepared scheduling.
  Revisit it only as an explicit activation repair with pre-protocol and
  formal mechanism evidence.
- Otherwise, the next CVRP attempt should move to a materially different
  non-reviewed problem-owned construction, destroy/repair, or local-search
  causal path.
