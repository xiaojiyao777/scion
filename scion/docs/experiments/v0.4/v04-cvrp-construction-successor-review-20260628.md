# CVRP Construction Successor Review

Date: 2026-06-28

## Scope

This report records the local successor3 CVRP run and the problem-owned review
repair it exposed. The change stays in the CVRP package: generic core,
`DecisionFeatures`, scheduler state, Protocol gates, and promotion state are not
changed.

## Run

- Root:
  `/home/clawd/research/scion-experiments/v04-cvrp-successor3-b430c646-local-1r-gpt55-20260628T133031Z-claw`
- Runtime commit: `b430c646`
- Model: `gpt-5.5`
- Resume source:
  `/home/clawd/research/scion-experiments/v04-cvrp-successor2-19811b02-local-1r-gpt55-20260628T123904Z-claw/campaign`
- Wrapper status: valid/complete, wrapper exit `0`
- Postrun readiness after rebuild: `current_run_analysis_ready=true`,
  `delegation_ready=true`, no failed required or optional checks

Command:

```bash
PYTHONPATH=scion /home/clawd/miniconda3/envs/claw/bin/python \
  scion/tools/check_postrun_acceptance.py \
  /home/clawd/research/scion-experiments/v04-cvrp-successor3-b430c646-local-1r-gpt55-20260628T133031Z-claw \
  --require-current-run-ready --format json
```

## Result

The run selected a construction seed successor:
`rotated_sweep_seed_tournament` in
`policies/baseline_modules/construction.py`.

Protocol evidence:

- 1 effective screening row
- 32/32 valid screening pairs
- 1 proposal attempt
- 0 proposal quality blocks
- champion stayed `v1`
- promotions `0`
- rows at or above CVRP MDE `0`
- top effect row: `mechanism_family=rotated_sweep_seed_tournament`,
  `gate_outcome=fail`, `win_rate=0.0`, `median_delta=0.0`,
  `ci_high=0.0`, `ci_high_below_mde=true`,
  `positive_effect_at_or_above_mde=false`

Pair-level signal was essentially neutral: one pair improved, one regressed,
and 30 tied. CMT2 and CMT4 were both all ties.

The branch was abandoned with `SCREENING_TELEMETRY_FAILED`, not because of a
proposal-loop or infrastructure failure. The formal run completed, but the
declared mechanism activation telemetry was missing. The candidate recorded
ordinary construction phase runtime, but not positive activation under the
declared mechanism id. This is a valid problem-layer rejection: construction
seed successors need a same-run seed baseline or accepted candidate-vs-baseline
delta before downstream ALNS/VNS attribution becomes meaningful.

## Repair

Before this repair, CVRP guidance text already allowed construction successors,
but `cvrp_successor_summary` only reviewed
`bounded_local_search_variant` and `destroy_repair_selection`. As a result, the
successor3 root reported `no_successor_family_protocol_evidence` even though the
agent had selected a materially different construction successor.

The repair:

- Adds `construction_seed_portfolio` to CVRP
  `SUCCESSOR_OPPORTUNITY_FAMILIES`.
- Maps `rotated_sweep_seed_tournament` and related sweep-seed aliases to
  `construction_seed_portfolio` in CVRP successor and opportunity-usage review.
- Replaces fixed two-family successor evidence requirements with a small
  problem-owned spec table so additional CVRP successor families do not require
  ad hoc unpacking.

Recomputed live brief after the repair:

- `cvrp_successor_summary.observed_successor_families`:
  `["construction_seed_portfolio"]`
- `construction_seed_portfolio.checklist_status`: `unproven`
- `construction_seed_portfolio.outcome_status`: `measured_no_positive_at_mde`
- missing requirement: `missing_activation_observed`
- objective, phase telemetry, and CMT2/CMT4 case evidence are present
- `cvrp_opportunity_usage_summary` maps both rotated-sweep proposal sessions to
  `construction_seed_portfolio` and marks them
  `opportunity_evidence_checklist_unproven`

## Interpretation

This is clean effective-research evidence for successor routing, not solver
improvement. The agent followed prior reviewed evidence away from the first two
bounded-local-search successors and tested a materially different construction
seed mechanism. The mechanism failed to prove activation/effect requirements
and did not improve at MDE.

Next CVRP work should prefer `destroy_repair_selection` or a construction seed
mechanism that explicitly records same-run seed-baseline effect evidence. Do not
add generic gates or relax telemetry checks to make this candidate pass.

## Validation

```bash
PYTHONPATH=scion /home/clawd/miniconda3/envs/claw/bin/python -m pytest -q \
  scion/scion/tests/unit/test_cvrp_postrun_review_provider.py \
  scion/scion/tests/unit/test_cvrp_research_guidance_provider.py \
  scion/scion/tests/unit/test_cvrp_opportunity_provider.py \
  scion/scion/tests/unit/test_cvrp_opportunity_usage_review.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_cvrp_postrun_opportunity_brief.py
```

Result: `45 passed`.

```bash
PYTHONPATH=scion /home/clawd/miniconda3/envs/claw/bin/python -m pytest -q \
  scion/scion/tests/unit/test_v3_problem_boundary_no_cvrp_terms_in_generic_layers.py \
  scion/scion/tests/unit/test_research_guidance_contract.py \
  scion/scion/tests/unit/test_prepared_successor_focus.py \
  scion/scion/tests/unit/core/test_scheduler_prepared_successor_focus.py \
  scion/scion/tests/unit/core/test_proposal_pipeline_launch_focus_provider.py
```

Result: `39 passed`.

Additional checks: touched-file `py_compile` passed; `git diff --check` clean.
