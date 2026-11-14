# CVRP Successor14 Postrun Review - 2026-06-29

## Scope

- Run root:
  `/home/clawd/research/scion-experiments/v04-cvrp-successor14-9fed32ad-local-2r-gpt55-2r-gpt55-20260629T050442Z-claw`
- Commit: `9fed32ad`
- Model: `gpt-5.5`
- Purpose: continue from successor13, first testing whether the active
  `route_pair_crossover_repair` branch could address its CMT2/CMT4/X-n110
  losses, then clean-forking to a materially different CVRP-owned
  destroy/repair mechanism.

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
- Independent checker after the launcher-marker overlay repair:
  `current_run_analysis_ready=true`, `delegation_ready=true`,
  `failed_required_checks=[]`, `failed_optional_checks=[]`.

## Solver Evidence

CVRP measurement readiness remained usable:

- MDE at 80 percent power: `9.9`
- Protocol rows at or above MDE: `0`
- Research-efficiency interpretation: `all_available_ci_high_below_mde`
- Max effect/MDE ratio: `-0.353535`
- Max case-level median delta: `-3.5`

| Metric | Mechanism | Pairs | Raw W/L/T | Raw Median | Min | Max | Research-Efficiency Effect |
|---|---|---:|---:|---:|---:|---:|---|
| `f24cd9f8-8d87-4d9d-878b-b2e931052562` | `route_pair_crossover_repair` | 48/48 | 19/24/5 | -0.5 | -116.0 | 36.0 | median -3.5, CI high 6.5 < MDE |
| `6c5f32ea-54ed-42d9-b9d7-ca412bc9de1d` | `timewarp_string_removal` | 32/32 | 9/15/8 | 0.0 | -90.0 | 23.0 | median -5.25, CI high 0.0 < MDE |

Case-level signal stayed negative in the protected regions. The route-pair row
was positive on A-n64 and M-n151, but lost on B-n67, CMT2, CMT4, P-n76,
P-n101, and X-n110. The new `timewarp_string_removal` row was positive on
A-n64, but lost on B-n63, E-n101-k14, P-n65, CMT2, CMT4, and X-n110, with
M-n200 all ties.

## Research Behavior

Positive framework evidence:

- The active route-pair branch was evaluated on a full 48-pair follow-up and
  then parked as `quality_regression`; it was not promoted.
- The second round clean-forked to a distinct problem-owned destroy/repair
  mechanism, `timewarp_string_removal`, instead of repeating route-pair.
- The new mechanism completed Protocol with no candidate/champion failures and
  was abandoned/discarded after loss-heavy evidence.
- Both rows carried row-local mechanism-family evidence into
  research-efficiency, and postrun analysis stayed report-only.

Launcher/readiness repair:

- The run exposed a generic postrun readiness false optional failure:
  `postrun_report_status_marker` read the stored inventory snapshot produced
  before final launcher markers were appended to `run.log`.
- `check_postrun_acceptance.py` now overlays live current-root launcher marker
  counts on top of stored inventory marker counts. This preserves immutable
  report artifacts while letting readiness consume the final wrapper lifecycle
  facts.
- Focused validation:
  `pytest scion/scion/tests/test_check_postrun_acceptance.py scion/scion/tests/unit/test_postrun_lifecycle_acceptance_checks.py -q`
  passed (`90 passed`).

## Next Interpretation

Successor14 is effective-research evidence, not solver progress:

- Scion rejected the active marginal route-pair path after direct case evidence
  showed CMT/P/X losses persisted.
- Scion generated a materially different destroy/repair candidate and rejected
  it without promotion when the effect remained below MDE.
- The next CVRP attempt should avoid unchanged route-pair and
  `timewarp_string_removal`, and should either target a different
  problem-owned mechanism class or explicitly explain how it protects CMT2,
  CMT4, and X-n110 while preserving runtime behavior.
