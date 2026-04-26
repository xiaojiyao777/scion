# MILP Bounds Package

Generated from `surrogate/cplex-final-20260426/` by:

```bash
conda run -n claw python surrogate/import_milp_bounds.py
```

This directory is the compact report-only benchmark source consumed by
`WarehouseDeliveryAdapter.estimate_lower_bound()`.

Current contents:
- 78 non-infeasible benchmark files.
- 68 CPLEX `optimal` files.
- 9 CPLEX verified feasible incumbent files.
- 1 CPLEX timeout reference file (`instance_prod_val_lx02.json`), not an exact
  optimum.
- 5 CPLEX infeasible data-generation cases are intentionally absent.

The CPLEX source package remains the audit source for full solver status,
verification details, and HiGHS comparison.
