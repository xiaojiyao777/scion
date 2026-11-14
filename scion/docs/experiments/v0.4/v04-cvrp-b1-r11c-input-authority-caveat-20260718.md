# CVRP B1 R11c Input-Authority Caveat

*Date: 2026-07-18*
*Status: analysis candidate; independent review pending*

## Finding

The accepted B1 root remains byte-replayable under its frozen manifest, but its
sealed `input_snapshot` contains each selected `.vrp` file without the adjacent
same-basename `.sol` companion. The current CVRPLIB loader reads that `.sol` to
obtain both BKS distance and `bks_routes`; the canonical solver then uses
`instance.allowed_routes or instance.bks_routes` as `max_routes`.

Consequently B1 compared four profiles on the same sealed inputs, but not on
the exact R11c runtime-input semantics. Manifest-owned BKS facts remained
available to the report, while the solver instances themselves had
`bks_routes=None` and did not apply the R11c route-count bound.

This is an input-authority/materialization defect, not missing raw evidence and
not a reason to silently modify or resume the accepted root.

## Exact evidence

- accepted root:
  `/home/clawd/research/scion-experiments/v04-cvrp-b1-mechanism-matrix-20260718T074653Z-claw`;
- manifest SHA-256:
  `8e9bf79c58ce1a5b9aa1e18d1d02d828fe2c32823ea2662bd99c96b22a1589b9`;
- accepted report SHA-256:
  `833335bb497d3cd7b344c3d6b87269ae0469c2cb87ee76c52227859719a7851b`;
- accepted receipt SHA-256:
  `03d1c466d09ed84a9bbd3b6a21333311da4f739a78e57102f5fa1ca8bffd5d43`;
- sealed case files: 16 `.vrp`, zero `.sol`;
- completed raw rows: 256;
- rows whose route count exceeds the manifest case's BKS route count: 19;
- affected complete `(case, seed)` quartets: 9 of 64.

Affected rows by profile:

| Profile | Rows over manifest BKS route count |
|---|---:|
| `canonical_alns_vns` | 2 |
| `initial_vns_disabled` | 3 |
| `embedded_vns_disabled` | 7 |
| `pure_alns_no_polish` | 7 |

Affected quartets occur only in:

- `cvrplib/E/E-n101-k14.vrp`: 4 seeds;
- `cvrplib/CMT/CMT2.vrp`: 3 seeds;
- `cvrplib/B/B-n67-k10.vrp`: 2 seeds.

The accepted B1 report already records only 237/256 rows within the manifest
BKS route count, so the raw symptom was retained rather than hidden. The newly
identified defect is that this report fact did not fail the claim that the
runtime input matched R11c.

## Fixed sensitivity view

For diagnosis only, remove each of the nine affected quartets as a whole so all
four profiles remain paired. This leaves 55 quartets. `E-n101-k14` has no
remaining seed and the equal-case view therefore has 15 cases.

| Contrast versus canonical | 15-case W/L/T (canonical/profile/tie) | Median case distance delta, profile-canonical | Direction |
|---|---:|---:|---|
| `initial_vns_disabled` | 6 / 4 / 5 | 0.0 | descriptive / heterogeneous |
| `embedded_vns_disabled` | 10 / 1 / 4 | +8.0 | canonical better |
| `pure_alns_no_polish` | 11 / 0 / 4 | +15.5 | canonical better |

This sensitivity preserves the previously reported canonical direction for
embedded-VNS-disabled and pure ALNS. It does not reconstruct the counterfactual
search that the missing `max_routes` would have produced and therefore cannot
upgrade B1 to exact R11c evidence.

## Disposition

Subject to independent review:

1. retain the B1 root/report/receipt as immutable evidence under their actual
   frozen input contract;
2. narrow B1 to `accepted_with_input_authority_caveat`: useful supporting
   profile evidence, not an exact R11c runtime reproduction and not a profile
   selection or promotion decision;
3. keep F1 unlocked because F1 is an independently frozen no-LLM ancestry
   decomposition, but require F1 to seal all 16 `.vrp` plus adjacent `.sol`
   pairs and re-parse BKS route authority from the sealed copies;
4. prohibit reuse of B1's single-file case materializer by F1 or any future
   claim of R11c-equivalent execution;
5. add an exact `.vrp`/`.sol` companion closure and negative regression tests
   before any future B0/B1-style mechanism runner is accepted;
6. do not rerun B1 automatically. A corrected profile matrix requires a new
   design/root only if later F1/B2 evidence cannot answer the remaining
   mechanism question.

No accepted B1 artifact is edited, replaced, or reclassified until this
analysis passes independent integrity and science review.
