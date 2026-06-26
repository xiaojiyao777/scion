# CVRP Seed-Family Review Alignment

Date: 2026-06-26

## Purpose

The proof-status follow-up root showed that CVRP proposals and prepared
opportunity guidance used the required mechanism id
`large_instance_intra_route_two_opt_seed`, while the CVRP large-twoopt postrun
review still rejected that family as seed-only guidance. That made the live run
look like it had no large-twoopt mechanism evidence even when structured
activation, objective-effect, and phase telemetry were present.

This repair keeps the distinction between requirement evidence and solver
success:

- `large_instance_intra_route_two_opt_seed` is now recognized as the prepared
  CVRP large-twoopt evidence family.
- `zero_objective_effect` counts as measured objective-effect telemetry, not as
  a positive solver outcome.
- Direct outcome readiness still requires positive-at-MDE evidence plus CMT2
  and CMT4 case protection evidence.
- The change stays inside the CVRP problem package and does not add generic
  core gates, scheduler pressure, Protocol behavior, or `DecisionFeatures`.

## Artifact Recheck

Recomputed locally on the mirrored proof-status root:

`/home/clawd/research/scion-experiments/v04-cvrp-proofstatus-followup-05ade2e0-2r-gpt55-20260625T155106Z-claw`

Observed after repair:

- `cvrp_large_twoopt_summary.interpretation`:
  `protocol_evaluated_without_large_twoopt_direct_evidence`
- `mechanism_family_available`: `true`
- `protocol_families`: `large_instance_intra_route_two_opt_seed`
- `direct_evidence_ready`: `false`
- Activation/objective/phase telemetry counts: `2/2/2`
- Positive-at-MDE rows: `0`
- Remaining direct-evidence missing fields:
  `missing_positive_effect_at_or_above_mde`,
  `missing_cmt_case_protection_evidence`
- Requirement checklist missing fields:
  `missing_cmt_case_protection_evidence`
- `required_evidence_proof.checklist_status`: `unproven`
- `cvrp_opportunity_usage_summary.usage_status`: `checklist_unproven`

Interpretation: the run now proves that the prepared seed-family mechanism was
evaluated, but it still does not prove solver success or CMT case protection.

## Validation

Commands run in local conda `claw` on the server:

```bash
conda run -n claw pytest \
  scion/scion/tests/test_cvrp_postrun_opportunity_brief.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/unit/test_cvrp_opportunity_usage_review.py \
  scion/scion/tests/unit/test_cvrp_opportunity_provider.py -q
```

Result: `51 passed`.

```bash
conda run -n claw pytest scion/scion/tests/test_check_postrun_acceptance.py -q
```

Result: `85 passed`.

```bash
conda run -n claw python -m py_compile \
  scion/scion/problems/cvrp/large_twoopt_review.py \
  scion/scion/tests/test_cvrp_postrun_opportunity_brief.py
git diff --check
```

Result: passed.

## Next Step

Do not launch another generic repair experiment for this issue. The next CVRP
run should test whether agents can now close the remaining CMT case-protection
and positive-effect evidence gaps from the problem-owned opportunity path. WSL
is not required for a short server-side diagnostic, but larger concurrent runs
should wait until the WSL runner is available again.
