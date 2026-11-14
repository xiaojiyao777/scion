# CVRP Mechanism Matrix and Size70/Two-Opt Repair

Date: 2026-06-17
Branch: `codex/v04-evidence-repair-plan`
Base commit: `5630697`

## Purpose

CVRP/VRP remains a v0.4 effectiveness target. The next useful step is not a
long blind LLM campaign, but a problem-owned diagnostic and one narrow active
solver repair:

- expose a no-LLM family/slice/mechanism matrix that compares the canonical
  ALNS+VNS baseline, ALNS-only, and a size70/two-opt candidate surface;
- keep BKS, gap, family, slice, route-regression, VNS, and mechanism diagnostics
  out of generic `DecisionFeatures`;
- make the active solver execute a bounded intra-route two-opt polish when full
  VNS is skipped on size70+ cases, so the solver path has an auditable
  lightweight local-search fallback rather than a silent VNS hole.

This is CVRP-owned diagnostic/solver work. It does not change generic Decision,
Protocol thresholds, branch governance, or the v3 tainted-output boundary.

## Changes

Active solver path:

- `scion/problems/cvrp/policies/baseline_modules/config.py` adds
  `SIZE70_TWO_OPT_MIN_CUSTOMERS = 70`.
- `scion/problems/cvrp/policies/baseline_modules/local_search.py` adds
  `_two_opt_intra_polish(...)` with explicit phase telemetry.
- `scion/problems/cvrp/policies/baseline_modules/scheduler.py` runs the
  polish during initial construction and embedded search only when full VNS is
  skipped and `customer_count >= 70`.
- Runtime tests cover both the active fallback path and the below-size70
  unchanged full-VNS path.

No-LLM mechanism matrix:

- `scion/problems/cvrp/evidence/mechanism_matrix.py` defines the CVRP-owned
  manifest/result schema, mechanism specs, case loading, reserved diagnostic
  fields, and solver-output summarization.
- `scion/tools/cvrp_mechanism_matrix.py` writes a deterministic manifest,
  prepares overlay workspaces, runs or dry-runs jobs, and emits `results.json`
  plus `summary.csv`.
- The matrix mechanisms are:
  - `canonical_alns_vns`
  - `alns_only`
  - `size70_two_opt_candidate`

## Boundary Check

The matrix is report-only. Its manifest records:

- `generic_decision_inputs_changed: false`
- a decision-boundary note stating that CVRP family, slice, BKS, gap,
  route-regression, and mechanism diagnostics are problem-owned report fields
  only and must not enter generic `DecisionFeatures`.

The active solver repair stays inside the CVRP problem-owned policy package.
It records solver telemetry through the existing runtime context and does not
change Decision feature extraction or Protocol gate semantics.

## Validation

Main worktree validation:

```bash
PYTHONPATH=scion pytest -q \
  scion/scion/tests/test_cvrp_solver_algorithm_runtime.py \
  scion/scion/tests/test_cvrp_solver_vrp_smoke.py \
  scion/scion/tests/test_cvrp_solver_operator_runtime.py
```

Result: `15 passed`.

```bash
PYTHONPATH=scion pytest -q \
  scion/scion/tests/unit/test_research_surfaces_solver_design_scheduler.py \
  scion/scion/tests/unit/test_research_surfaces_solver_design_baseline_api.py \
  scion/scion/tests/unit/test_cvrp_active_solver_map_provider.py
```

Result: `18 passed`.

```bash
PYTHONPATH=scion pytest -q \
  scion/scion/tests/unit/evidence/test_cvrp_mechanism_matrix.py \
  scion/scion/tests/test_cvrp_runtime_curve_tool.py
```

Result: `6 passed`.

Additional checks passed:

- `python -m py_compile` on changed CVRP source/test/tool files.
- `git diff --check`.
- Matrix dry-run smoke with one screening case and seed `11`.
- Matrix tiny live smoke with one screening case, seed `11`, and
  `--time-budget-sec 1`.

Tiny smoke result on `A-n64-k9`, seed `11`, one-second budget:

| Mechanism | Distance | BKS gap | Delta vs canonical | Accepted moves | Best delta | Stop |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `canonical_alns_vns` | `1453.0` | `3.7116%` | `0.0` | `26` | `87.0` | `time_limit` |
| `alns_only` | `1479.0` | `5.5675%` | `26.0` | `9` | `0.0` | `completed` |
| `size70_two_opt_candidate` | `1478.0` | `5.4961%` | `25.0` | `26` | `15.0` | `completed` |

The live smoke confirms that the overlay workspaces are not empty shells:
`alns_only` disables VNS, while `size70_two_opt_candidate` changes VNS threshold
and local-search operator composition, producing distinct phase telemetry.

## Next Gate

After committing and syncing a clean runner checkout to WSL, run a small no-LLM
CVRP matrix across family/slice samples before launching any longer LLM
campaign. The goal is to identify where candidate mechanisms have measurable
headroom against canonical ALNS+VNS and where ALNS-only exposes easier but
noncanonical research surfaces.
