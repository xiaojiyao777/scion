# CVRP Successor13 Postrun Review - 2026-06-29

## Scope

- Run root:
  `/home/clawd/research/scion-experiments/v04-cvrp-successor13-46b01ebb-local-2r-gpt55-2r-gpt55-20260629T031313Z-claw`
- Commit: `46b01ebb`
- Model: `gpt-5.5`
- Purpose: verify the generic prepared-successor scheduler repair, then test
  whether the active CVRP destroy/repair signal can produce positive-at-MDE
  solver evidence.

## Run Result

- Wrapper exit: `0`
- Campaign status: valid and complete
- Effective rounds completed: `2`
- Proposal attempts: `4`
- Protocol-evaluated candidates: `3`
- Formal-screened candidates: `3`
- Proposal quality blocks: `2`
- Stop reason: `max_rounds_exhausted`
- Champion version: `1`
- Promotions: `0`
- Postrun acceptance: ready
- Independent checker:
  `current_run_analysis_ready=true`, `delegation_ready=true`,
  `failed_required_checks=[]`, `failed_optional_checks=[]` after the
  report-layer mechanism-family rebuild.

The run confirms that the prepared-successor scheduler repair works: the first
new Protocol row followed the active `capacity_tightness_removal` successor
signal instead of spending the row on the reviewed
`load_compatible_ruin_recreate` branch-local repeat.

## Solver Evidence

CVRP measurement readiness remained usable but low-power:

- MDE at 80 percent power: `9.9`
- Protocol rows at or above MDE: `0`
- Postrun interpretation: `protocol_effects_below_mde_or_inconclusive`

| Metric | Mechanism | Pairs | W/L/T | Median Delta | Min | Max | Interpretation |
|---|---|---:|---:|---:|---:|---:|---|
| `2cce47aa-d63b-4ff8-b347-5c860125cd1b` | `capacity_tightness_removal` | 48/48 | 27/19/2 | 2.0 | -43.0 | 25.0 | weak positive, below MDE |
| `92f9ac74-e27d-45d3-9dfb-2834db4a4f9a` | `route_pair_crossover_repair` on the parked lineage | 32/32 | 13/12/7 | 0.0 | -45.0 | 30.0 | no positive-at-MDE |
| `7330a047-547d-42c5-a580-8f83593faec0` | `route_pair_crossover_repair` clean fork | 32/32 | 13/13/6 | 0.0 | -46.0 | 29.0 | marginal active branch, no positive-at-MDE |

Case-level signal is mixed. `capacity_tightness_removal` improved several A/E
cases, but remained negative on B-n67, P-n76/P-n101, CMT4, and X-n110. The
route-pair clean fork improved A-n64 and E-n101-k14, but CMT2, CMT4, and X-n110
remained negative or unstable; M-n200 was all ties.

## Research Behavior

Positive framework evidence:

- Bad code was blocked before Protocol by a syntax/contract preview failure.
- A parked-lineage result was not promoted and was routed to clean-fork policy.
- The clean fork recorded direct `route_pair_crossover_repair` activation and
  objective-effect telemetry.
- Postrun readiness stayed current-run scoped and report-only; no Decision
  feature, promotion state, scheduler state, or campaign state mutation was
  introduced by postrun analysis.

Report repair:

- The initial research-efficiency artifact mislabeled row 1
  `mechanism_family=route_pair_crossover_repair` even though
  `mechanism_evidence.primary_mechanism` and phase telemetry correctly
  identified `capacity_tightness_removal`. The report-layer resolver now
  prefers row-local primary mechanism evidence before branch-level family
  summaries, and the successor13 postrun acceptance artifacts were rebuilt to
  show row 1 as `capacity_tightness_removal`.

## Next Interpretation

Successor13 is effective-research evidence, not solver progress:

- Scion followed the intended active successor signal.
- It generated and rejected measurable solver candidates with direct telemetry.
- It preserved low-SNR marginal evidence without promotion.
- It still failed to produce positive-at-MDE CVRP improvement.

The active CVRP frontier is now the clean `route_pair_crossover_repair` branch
`d80e5851-58b9-43fa-870a-13a8e64fc9aa`, state `explore_expand`,
`branch_code_status=clean`, tier `marginal`. Any continuation should address
CMT2/CMT4/X-n110 losses and runtime cost directly, or move to a materially
different problem-owned mechanism. The corrected research-efficiency summary
now aligns row-level `mechanism_family` with direct primary-mechanism evidence.
