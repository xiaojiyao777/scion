# CVRP Postprojection Successor Portfolio

Date: 2026-06-28

## Purpose

The CVRP opportunity and commitment repairs made the agent prove the
large-instance intra-route two-opt checklist instead of treating weak
proposal-visible signal as solver progress. The follow-up run tested whether
that repaired loop could produce clean current-run evidence and whether the
prepared large-twoopt opportunity should remain the next required mechanism.

## Run Evidence

Local run root:

`/home/clawd/research/scion-experiments/v04-cvrp-postprojection-followup-e687d758-local-4r-gpt55-4r-gpt55-20260628T065805Z-claw`

The root finished valid/complete and postrun-ready:

- `wrapper_exit_status=0`
- `campaign_exit_status=complete`
- `last_stop_reason=max_rounds_exhausted`
- `postrun_acceptance_status=ready`
- `current_run_analysis_ready=true`
- `delegation_ready=true`
- no failed required postrun-acceptance checks

Framework research behavior is clean:

- 4 of 4 effective rounds completed.
- 4 formal screened candidates and 4 screening Protocol metric rows.
- 0 validation/frozen rows, 0 promotions, champion stayed `v1`.
- 0 proposal-quality blocks.
- Active research shape is `deep_focused`.
- Same-mechanism follow-up was selected for all observed opportunities.
- Branch-lesson usage and opportunity commitments are visible in prompt/report
  summaries.

Solver outcome is negative:

- Latest screening row: 32/32 valid, 0 wins, 1 loss, 31 ties.
- Positive rows: 0.
- Rows at or above CVRP MDE: 0.
- All available CI highs are below MDE.
- `required_evidence_proof.checklist_status=proven`.
- CMT2/CMT4 protected-case evidence is observed.
- Large-twoopt direct outcome evidence remains
  `measured_no_positive_at_mde`, so direct positive-at-MDE evidence is absent.

## Interpretation

This is useful v0.4 framework evidence but not solver progress. The loop now
gets from prepared opportunity visibility to code commitment to current-run
checklist proof without generic core learning CVRP-specific mechanism rules.
The important result is that the prepared
`large_instance_intra_route_two_opt_seed` opportunity has been reviewed:
activation/objective/phase evidence and CMT2/CMT4 protection are proven, but
the measured solver effect is still below MDE.

Therefore the next CVRP branch slot should not keep treating
`large_instance_intra_route_two_opt_seed` as a hard first-attempt mechanism.
It should rotate to a materially different CVRP-owned successor opportunity,
preferably one of:

- `bounded_local_search_variant`
- `destroy_repair_selection`

Any same-seed revisit now needs an explicit reason why a new causal path
invalidates the reviewed no-positive-at-MDE conclusion.

## Repair

The repair is problem-owned:

- `scion.problems.cvrp.research_guidance` no longer emits a hard required
  mechanism for `large_instance_intra_route_two_opt_seed`.
- CVRP research focus carries `reviewed_mechanism_ids` and
  `successor_opportunity_families`.
- CVRP measurement diagnostics rank successor families ahead of the reviewed
  large-twoopt seed.
- CVRP opportunity requirements add successor direct-effect requirements only
  when current-run postrun evidence proves the large-twoopt checklist but
  measures no positive-at-MDE effect.
- CVRP prompt-bridge readiness accepts either the legacy
  `highest_current_followup` projection or the new
  `highest_current_successor` projection.

Generic core, Protocol gates, scheduler behavior, lifecycle handling,
runtime pressure, promotion behavior, and `DecisionFeatures` are unchanged.

## Validation

Commands run locally with conda `claw`:

```bash
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion \
  /home/clawd/miniconda3/envs/claw/bin/python -m pytest \
  scion/scion/tests/unit/test_cvrp_opportunity_provider.py \
  scion/scion/tests/unit/test_cvrp_research_guidance_provider.py \
  scion/scion/tests/unit/test_cvrp_measurement_diagnostics.py \
  scion/scion/tests/unit/test_cvrp_opportunity_rendering.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py -q
```

Result: `33 passed`.

```bash
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion \
  /home/clawd/miniconda3/envs/claw/bin/python -m pytest \
  scion/scion/tests/unit/test_research_surfaces_cvrp_context.py \
  scion/scion/tests/unit/test_problem_prepared_handoff_ports.py -q
```

Result: `7 passed`.

```bash
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion \
  /home/clawd/miniconda3/envs/claw/bin/python -m pytest \
  scion/scion/tests/unit/test_cvrp_opportunity_provider.py \
  scion/scion/tests/unit/test_cvrp_research_guidance_provider.py \
  scion/scion/tests/unit/test_cvrp_measurement_diagnostics.py \
  scion/scion/tests/unit/test_cvrp_opportunity_rendering.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/unit/test_research_surfaces_cvrp_context.py \
  scion/scion/tests/unit/test_problem_prepared_handoff_ports.py \
  scion/scion/tests/test_rebuild_prepared_handoff.py -q
```

Result: `46 passed`.

```bash
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion \
  /home/clawd/miniconda3/envs/claw/bin/python -m pytest \
  scion/scion/tests/test_launch_readiness.py -q
```

Result after commit: `117 passed`.

```bash
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion \
  /home/clawd/miniconda3/envs/claw/bin/python \
  scion/tools/check_postrun_acceptance.py \
  /home/clawd/research/scion-experiments/v04-cvrp-postprojection-followup-e687d758-local-4r-gpt55-4r-gpt55-20260628T065805Z-claw \
  --require-current-run-ready --format json
```

Result: `current_run_analysis_ready=true`, `delegation_ready=true`,
`failed_required_checks=[]`, and no optional failed checks.

## Code-Quality Note

Touched production CVRP files remain below the 1000-line warning threshold.
Two touched launcher/rebuild test files were already above 1000 lines; this
repair only updates assertions there. Further changes in those tests should
split fixtures/assertion helpers before adding more behavior.
