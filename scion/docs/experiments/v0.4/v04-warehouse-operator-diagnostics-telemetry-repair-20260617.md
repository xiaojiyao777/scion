# Warehouse Operator Diagnostics Telemetry Repair

*Date: 2026-06-17*
*Status: implemented locally; short warehouse field gate pending*

## Trigger

The valid warehouse data-root repair rerun stayed screening-only. Branch-level
analysis showed two different screening-positive operators wrote
`validation_transfer_diagnostics` dictionaries, but formal metrics still
reported activation/effect diagnostics as `not_declared`.

This was a problem-owned measurement wiring defect: accepted warehouse patches
could satisfy the patch-quality hook with local counters that the solver never
exported and the telemetry guard could not consume.

## Repair

The repair keeps the v3 boundary intact:

- no Decision/Protocol promotion gates changed;
- no LLM text, raw prompt context, or branch lessons were added to
  `DecisionFeatures`;
- warehouse semantics remain in the warehouse problem package and surrogate
  solver.

Implementation choices:

- `surrogate/solver.py` now collects each dynamically loaded operator
  instance's `self.validation_transfer_diagnostics` after VNS and exports
  normalized standard counters under
  `runtime.operator_diagnostics.{mechanism}.*`.
- Both warehouse `problem-v1.yaml` files declare those fields as
  mechanism-scoped activation/effect telemetry for `order_level` and
  `vehicle_level`.
- `WarehouseDeliveryAdapter.validate_patch_quality` now fails closed when a
  patch only maintains a local diagnostics dictionary. Accepted patches must
  initialize/update `self.validation_transfer_diagnostics` on the operator
  instance with the standard keys the solver can export.

## Verification

Commands run:

```text
PYTHONPATH=scion python -m pytest scion/scion/tests/unit/test_warehouse_target_preview.py -q
python -m pytest surrogate/tests/test_solver_operator_diagnostics.py surrogate/tests/test_solver.py::TestSmallInstance::test_dynamic_operator_diagnostics_serialized -q
PYTHONPATH=scion python -m pytest scion/scion/tests/unit/core/test_proposal_pipeline_quality_blocks.py scion/scion/tests/unit/test_runtime_telemetry_guard.py scion/scion/tests/unit/test_runtime_telemetry_guard_mechanism_diagnostics.py -q
python -m pytest surrogate/tests/test_solver.py -q
PYTHONPATH=scion python -m pytest surrogate/tests/test_scion_warehouse_adapter_smoke.py -q
git diff --check
```

Results:

- warehouse target/patch-quality tests: `18 passed`;
- solver diagnostics/registry tests: `3 passed`;
- proposal pipeline plus telemetry guard tests: `54 passed`;
- surrogate solver tests: `13 passed`;
- warehouse adapter smoke tests: `2 passed`.
- whitespace check: clean.

Main-thread review found one bug after the worker implementation: registry
diagnostics were initially keyed by class name only. The final solver path now
uses `registry.yaml` `name` as the primary mechanism id, with class names only
as fallback, so `fill_and_downsize` and `locked_anchor_repack` match the
declared telemetry paths.

## Next Gate

Run a short warehouse production `6R` field gate from this repair commit. Accept
only if:

- the run remains `valid` with formal protocol rows;
- at least one screening-positive candidate has consumed
  `operator_diagnostics.{mechanism}.*` telemetry in the formal metrics;
- local-only fake diagnostics are absent from accepted patches;
- any remaining screening-only outcome is explained by objective/pair evidence
  and declared activation/effect diagnostics, not by `not_declared` telemetry.
