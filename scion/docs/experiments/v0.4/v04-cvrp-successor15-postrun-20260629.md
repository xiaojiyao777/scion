# CVRP Successor15 Postrun Review - 2026-06-29

## Scope

- Run root:
  `/home/clawd/research/scion-experiments/v04-cvrp-successor15-dc0603c6-local-2r-gpt55-2r-gpt55-20260629T064208Z-claw`
- Commit: `dc0603c6`
- Model: `gpt-5.5`
- Purpose: continue from successor14 after recording route-pair and timewarp
  evidence as reviewed/default-avoid, verify that prepared guidance suppresses
  those repeats, and look for a new CVRP-owned solver-design path.

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
- Max effect/MDE ratio: `0.353535`
- Max median delta: `3.5`

| Round | Mechanism | Decision | Pairs | W/L/T | Median Delta | CI | Interpretation |
|---:|---|---|---:|---:|---:|---|---|
| 1 | `load_complement_pair_removal` | `abandon` | 32/32 | 10/17/5 | -4.75 | [-8.75, 0.0] | loss-heavy, reviewed/default-avoid |
| 2 | `granular_savings_seed_portfolio` | `expand_screening` | 32/32 | 17/8/7 | 3.5 | [0.0, 12.75] | weak positive, below MDE, active follow-up |

`load_complement_pair_removal` improved A-n64 but lost on B-n63, E-n101,
P-n65, CMT4, and X-n110, with CMT2 slightly negative. This is sufficient
negative destroy/repair evidence for problem-owned reviewed/default-avoid
guidance.

`granular_savings_seed_portfolio` is not promotion evidence, but it is the best
current CVRP forward signal. Case medians were positive on A-n64, CMT2, CMT4,
and M-n200; B-n63 tied; E-n101 and P-n65 were mixed; X-n110 carried a one-loss
caveat. The branch remains active as weak-positive construction evidence.

## Research Behavior

Positive framework evidence:

- Prepared guidance did not repeat successor14 route-pair or timewarp paths.
- The first new clean fork, `load_complement_pair_removal`, was measured and
  abandoned after negative direct objective evidence.
- The second row moved to a distinct construction seed-portfolio mechanism and
  kept it active as weak-positive evidence instead of promoting below-MDE
  signal.
- Postrun analysis remained report-only:
  `DecisionFeatures`, campaign state, scheduler state, and promotion state were
  excluded from postrun mutation.
- Failure taxonomy remained clean: no code-generation, stale-source,
  tool-timeout, or verification-heavy observations.

## Next Interpretation

Successor15 is effective-research evidence, not solver-improvement closure:

- Record `load_complement_pair_removal` as reviewed/default-avoid
  no-positive-at-MDE destroy/repair evidence.
- Do not record `granular_savings_seed_portfolio` as reviewed/default-avoid.
  It should be followed as an active weak-positive construction branch.
- The next CVRP run should first verify or refine the granular construction
  path, preserving CMT2/CMT4/M gains while addressing the X-n110 caveat, E/P
  mixed cases, and runtime-saturation observability.
