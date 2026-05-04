# CVRP Controlled Synthetic Fixtures

These files are the first stable CVRP controlled-run inputs for Scion v0.4.
They are deliberately tiny, synthetic CVRPLIB-style cases with sibling `.sol`
reference files. They are intended for local smoke campaigns and final evidence
plumbing, not for benchmark claims.

Paths in the manifests are relative to `scion/problems/cvrp`, so a runner using
that directory as its workspace can pass them directly as instance paths.

The stage split is fixed:

- `screening`: quick candidate signal checks
- `validation`: promotion-quality checks
- `frozen`: holdout-style checks
- `final`: post-campaign final evidence checks

Each stage has disjoint case ids. Runtime budgets and seeds are declared in
`budgets.json`; manifests also carry their stage seed list so they can be used
directly by manifest-driven final evaluation.

`protocol.yaml`, `split_manifest.yaml`, and `seed_ledger.yaml` define the short
controlled campaign smoke path. Their canary also uses a synthetic controlled
`.vrp/.sol` fixture.
