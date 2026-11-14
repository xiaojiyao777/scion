# CVRP Controlled Case Tiers

These files define the CVRP research-object protocol used by Scion v0.4
campaigns. The generic Scion core only sees opaque case paths and split names;
CVRP-specific provenance, BKS metadata, and mechanism-opportunity coverage live
in this adapter-owned directory.

## Source Assets

The primary case source is the existing VRP/CVRPLIB asset tree:

- `vrp/cvrplib/**`: checked-in CVRPLIB `.vrp` and `.sol` files.
- `vrp/results/full_experiment_seed0_final.csv`: seed-0 baseline ledger used
  to select reproducible clean cases.
- `vrp/results/reference_validation_bad.csv`: exclusion ledger for known
  invalid, unsupported, or mismatched references.

`split_manifest.yaml` declares `safe_data_roots: ../../../../../vrp`, so protocol
runs can resolve `cvrplib/...` case paths without copying benchmark data into
candidate workspaces. The synthetic controlled canary remains as the smoke
boundary fixture.

## Tier Design

- `canary`: one tiny synthetic runability case, used as smoke/veto plumbing.
- `screening`: 12 clean CVRPLIB cases, dimensions 19-60, 2-9 BKS routes,
  covering small sanity, construction-sensitive, multi-route, route-pair, and
  local ordering opportunities without being dominated by two tiny ties.
- `validation`: 8 clean CVRPLIB cases, dimensions 63-101, 4-10 BKS routes,
  with seeds 0 and 1 for stronger promotion evidence.
- `frozen`: 8 disjoint holdout CVRPLIB cases, dimensions 72-121, 4-14 BKS
  routes, also with seeds 0 and 1.
- `final`: 12 disjoint post-campaign evidence cases, dimensions 68-167, 7-18
  BKS routes, including larger X/M/CMT cases for heavier statistical checks.

## Inclusion And Exclusion Rules

Selected cases must have:

- existing `.vrp` and sibling `.sol` assets under `vrp/cvrplib`;
- a seed-0 baseline row in `full_experiment_seed0_final.csv`;
- `status=ok`, solver feasible, benchmark feasible, BKS and BKS route metadata;
- `route_gap=0`, so the baseline satisfies the reference fleet count;
- no appearance in `reference_validation_bad.csv`.

Cases are excluded when references are known bad, unsupported by the current
loader, infeasible or route-count mismatched under the baseline, too large for
early controlled tiers, or lacking clear objective/BKS metadata.

Runtime budgets and seeds are declared in `budgets.json`; JSON manifests mirror
the CSV selections and carry source ledger/provenance metadata.
