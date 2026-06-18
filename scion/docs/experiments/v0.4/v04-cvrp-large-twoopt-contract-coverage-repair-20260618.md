# CVRP Large Two-Opt Contract Coverage Repair - 2026-06-18

## Purpose

Make the large-instance intra-route two-opt seed a machine-checked prepared
contract requirement, not only launcher text. This closes the gap where a future
prepared root could drop the seed or its unbounded-fallback default-avoid line
while postrun artifact inventory still reported CVRP handoff coverage as
complete.

This remains report/control-plane coverage only. It does not change
`DecisionFeatures`, Protocol gates, scheduler state, promotion, or the CVRP
solver.

## Change

- `scion/tools/postrun_artifact_inventory.py`
  - Adds `large_instance_intra_route_two_opt_seed` to
    `CVRP_REQUIRED_MEASURABLE_OPPORTUNITY_TOKENS`.
  - Adds `unbounded large-instance two-opt fallback` to
    `CVRP_REQUIRED_DEFAULT_AVOID_TOKENS`.
- `scion/scion/tests/test_postrun_artifact_inventory.py`
  - Updates the CVRP prepared manifest fixture and asserts the new tokens are
    not missing from prepared contract checks.
- `scion/scion/tests/test_launch_readiness.py`
  - Updates the launch-readiness prepared-root fixture so static readiness
    represents the current CVRP prepared contract.

## Verification

```bash
PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_postrun_artifact_inventory.py \
  scion/scion/tests/test_cvrp_agentic_launcher.py \
  scion/scion/tests/test_postrun_analysis_brief.py \
  scion/scion/tests/test_launch_readiness.py
# 47 passed
```

## Interpretation

The next CVRP prepared roots must carry both sides of the large-twoopt seed:

- the allowed research direction:
  `large_instance_intra_route_two_opt_seed`;
- the disallowed shortcut:
  `unbounded large-instance two-opt fallback`.

This makes delegated postrun analysis and launch readiness fail closed if the
seed guidance is silently dropped before the next agentic run.
