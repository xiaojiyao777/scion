# Scion Evidence Manifest

*Last updated: 2026-04-28*

This file is the active map from Scion claims to experiment artifacts. It exists
to prevent old quality runs or interim reports from being mistaken for the
current conclusion.

## Current v0.3 Evidence

### Formal 12-Campaign Validation

```text
base_dir = ~/research/scion-experiments/v03-final-sync-12campaign-20260426/
matrix   = 2 models x 2 variants x 3 seeds
models   = claude-sonnet-4-6, gpt-5.4-mini
variants = synthetic, production
seeds    = 11, 29, 47
result   = 12/12 campaigns completed
```

Use this evidence for:

- framework closure;
- synthetic search effectiveness;
- sync weight optimization behavior;
- prompt/objective-policy plumbing;
- lineage and status artifact completeness.

Do not use the production portion of this run as the final production claim.
It was superseded by the timeout/evidence rerun below.

Primary report:

- [v0.3-final-12campaign-analysis.md](../archive/v0.3/v0.3-final-12campaign-analysis.md)

### Production Timeout/Evidence Rerun

```text
base_dir = ~/research/scion-experiments/v03-production-timeout-fix-validation-20260428b/
variant  = production
models   = claude-sonnet-4-6, gpt-5.4-mini
seeds    = 11, 29, 47
result   = 6/6 campaigns completed
```

Use this evidence for the final v0.3 production claim.

```text
Sonnet promotions = 3/3
GPT-mini promotions = 0/3
bad metrics = 0
all metrics complete = true
```

Artifact-level evidence:

```text
all metrics files: 158
total_pairs: 3033
valid_pairs: 3033
failed_pairs: 0
incomplete metrics files: 0

promoted frozen metrics files: 3
promoted frozen total_pairs: 36
promoted frozen valid_pairs: 36
promoted frozen failed_pairs: 0
```

Sonnet promoted operators:

| Campaign | Operator | Frozen wr | Frozen median delta |
|---|---|---:|---:|
| seed11 | `cross_subcat_merge.py` | 1.0 | 30000 |
| seed29 | `upgrade_and_absorb.py` | 1.0 | 38800 |
| seed47 | `absorb_to_eliminate.py` | 1.0 | 29600 |

Primary report:

- [v0.3-production-timeout-fix-analysis.md](../archive/v0.3/v0.3-production-timeout-fix-analysis.md)

### Best Synthetic Quality Comparison

```text
base_dir = ~/research/scion-experiments/v03-final-best-quality-20260428/
file     = quality_best_champions.json
task     = best_synthetic
champion = sonnet-4-6_synthetic_seed29/champions/champion_v5
cases    = 47 CPLEX-comparable synthetic cases
```

Use this evidence for the best synthetic champion quality claim.

```text
vs v1 baseline:
  better = 45
  equal  = 2
  worse  = 0
  sum Δf1 = -2899
  median Δf1 = -17

vs CPLEX final reference:
  better = 28
  equal  = 3
  worse  = 16
  median f1 gap = -9
```

Primary report:

- [v0.3-final-visual-report.md](../archive/v0.3/v0.3-final-visual-report.md)

## Superseded Or Diagnostic Artifacts

### Old Production Quality Task In `v03-final-best-quality-20260428`

The `best_production` task in:

```text
~/research/scion-experiments/v03-final-best-quality-20260428/quality_best_champions.json
```

points to an old formal-run production champion:

```text
sonnet-4-6_production_seed29/champions/champion_v2
```

That champion hit production-scale runtime failures in the follow-up quality
run. Treat this artifact as diagnostic evidence for the v0.4 performance-aware
work, not as the final production quality conclusion.

The final production conclusion is the production timeout/evidence rerun above.

## Current v0.4 CVRP Baseline Evidence

v0.4 will add CVRP as the second real problem class. The current CVRP baseline
is staged in:

```text
vrp/
```

The local CVRPLIB instance data is intentionally excluded from git:

```text
vrp/cvrplib/
```

Use this evidence for the current CVRP baseline claim:

```text
attempted EUC_2D instances = 10330
status=ok = 10330
timeout = 0
error = 0
CVRP feasible = 10330
benchmark_feasible = 10249
```

Primary baseline report:

- [../../vrp/docs/experiment_results_seed0.md](../../vrp/docs/experiment_results_seed0.md)

Primary artifacts:

```text
vrp/results/full_experiment_seed0_final.csv
vrp/results/reference_validation_bad.csv
vrp/results/analysis_full_seed0_final/summary_by_subset.csv
vrp/results/analysis_full_seed0_final/per_instance.csv
vrp/results/analysis_full_seed0_final/top_gaps.csv
```

Subset interpretation:

- A/B/P/E are the most stable quick-regression candidates.
- X is the most useful medium-scale optimization target: 48 comparable cases,
  mean gap 5.857%, median gap 5.524%, and clear remaining improvement room.
- XL/XML mostly lack local `.sol` files, so they currently support feasibility
  and runtime checks rather than BKS gap claims.
- CMT contains extended semantics such as `DISTANCE` and `SERVICE_TIME`; treat
  negative gaps there as diagnostic, not strict CVRP optimality evidence.

The current CVRP baseline is not yet integrated as a Scion `ProblemAdapter`
under `scion/problems/cvrp`. When the adapter and campaigns land, add:

- CVRP problem package path;
- benchmark split manifest;
- adapter smoke and operator verification artifacts;
- campaign matrix;
- every campaign final champion vs baseline quality/runtime comparison.

The required v0.4 evidence schema is tracked in:

- [v0.4-evidence-harness.md](../../design/v0.4/v0.4-evidence-harness.md)
