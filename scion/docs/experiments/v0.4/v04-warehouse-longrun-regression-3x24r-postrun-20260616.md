# Warehouse Longrun Regression 3x24R Postrun - 2026-06-16

## Scope And Boundary

This postrun analyzes the WSL warehouse longrun regression check launched from
`v04-warehouse-longrun-regression-3x24r-launch-20260616.md`.

Architecture boundary: per `scion/design/scion-architecture-v3.md`, prompt,
context, trace, branch-card, branch-lesson, and LLM-output artifacts are
report/audit material only. Promotion interpretation below is based on
deterministic protocol outputs, verification outcomes, frozen metrics, and
persisted campaign accounting. Prompt/context findings are not treated as
Decision inputs.

Artifact roots:

- WSL source:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z`
- Server synced copy:
  `/home/clawd/research/scion-experiments/v04-warehouse-longrun-regression-3x24r-20260616T071323Z`

The server copy was synced from WSL after wrapper completion.

## Wrapper And Cell Status

Top-level wrapper status:

| Field | Value |
|---|---:|
| status | finished |
| started_at_utc | 2026-06-16T07:16:00Z |
| finished_at_utc | 2026-06-16T10:16:01Z |
| top-level exit_code | 0 |
| commit | f384884 |
| requested shape | 3 repeats x 24 rounds |
| parallelism | 2 |
| measurement_governance | on |
| context arm | compact-measurement-diagnostics |

Per-cell exits:

| Repeat | Start UTC | End UTC | Exit |
|---|---:|---:|---:|
| rep01 | 2026-06-16T07:16:00Z | 2026-06-16T08:50:47Z | 0 |
| rep02 | 2026-06-16T07:31:00Z | 2026-06-16T09:01:21Z | 0 |
| rep03 | 2026-06-16T08:50:48Z | 2026-06-16T10:16:00Z | 0 |

No wrapper, tmux, or cell-level crash occurred.

## Run Accounting

Use `effective_rounds_completed` for requested-round budget completion and
`protocol_metric_results` for actual completed protocol metric rows.

| Repeat | Requested | Effective rounds | Effective protocol rounds | Protocol rows | Screening | Validation | Frozen | Fresh replay rows | Verification-failure budget rows | Formal candidates | Promotions | Final champion |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| rep01 | 24 | 24 | 24 | 25 | 22 | 2 | 1 | 1 | 1 | 21 | 1 | v2 |
| rep02 | 24 | 24 | 24 | 24 | 21 | 2 | 1 | 0 | 0 | 24 | 0 | v1 |
| rep03 | 24 | 24 | 22 | 22 | 19 | 2 | 1 | 0 | 2 | 19 | 1 | v2 |

Aggregate:

- Cells completed: 3/3.
- Repeats with at least one promotion: 2/3.
- Total champion promotions: 2.
- Best continuous promotion depth in any repeat: 1 promotion. No repeat showed a
  multi-promotion chain comparable to the v0.3 strongest synthetic 4-promotion
  run.
- All repeats produced Protocol rows and reached at least one frozen decision;
  no repeat is a 0-Protocol launch/preflight failure.

## Promotion And Champion Quality

### rep01

Final champion: `v2`, promoted from branch
`98676170-43e4-4030-827c-4f334429aa55`, hypothesis
`7aa8657e-1fa3-4f46-af44-5aaf848c7fc5`, patch file
`operators/merge_vehicles.py`.

Protocol chain:

| Stage | Gate | Cases | Wins | Losses | Ties | Win rate | Median delta | CI low | CI high | Runtime confidence |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| screening | pass | 14 | 8 | 0 | 6 | 0.571 | 950 | 400 | 4500 | low_cached_champion |
| validation | expand/exhausted marginal pass | 5 | 5 | 0 | 0 | 1.000 | 0 | 0 | 1 | low_cached_champion |
| frozen | pass | 4 | 4 | 0 | 0 | 1.000 | 50400 | 46200 | 58000 | high |

Frozen pair-level supplement: 12/12 pair wins, pair median delta 52200,
sum delta 619600, median runtime ratio 0.933, runtime regression rate 0.0.

Interpretation: valid single promotion, not continuous promotion. It shows
production warehouse research still can promote under v0.4, but much of the
budget was spent in proposal-quality drain before/around the promotion.

### rep02

Final champion: `v1`, no promotion.

The run reached frozen through branch
`345a246c-3d1e-4eb4-aede-dcf1eec27af7`, hypothesis
`497f5537-d6da-48fa-9ffb-05e6a194417c`, patch file
`operators/swap_orders.py`, then abandoned.

Frozen result:

- Pair comparison: 6 wins, 6 losses.
- Frozen median delta: -400.
- Frozen CI: [-4100, 3500].
- Pair sum delta: -2300.
- Median runtime ratio: 0.904, runtime regression rate 0.0.

The generated summary reports a plateau signal:
`subcategory_consolidation` repeated across the recent window with flat
win-rate spread 0.00.

Interpretation: real plateau/frozen failure, not framework launch failure. The
cell reached Protocol and frozen, but the candidate did not clear the frozen
quality gate.

### rep03

Final champion: `v2`, promoted from branch
`47ec47f1-09d9-4057-ae51-a6ba13279e40`, hypothesis
`8670e9f5-6a1d-4e5b-a2b0-217bf62e1a19`, patch file
`operators/cost_preserving_tail_refit.py`.

The champion pool added a new vehicle-level operator:
`cost_preserving_tail_refit`.

Protocol chain:

| Stage | Gate | Cases | Wins | Losses | Ties | Win rate | Median delta | CI low | CI high | Runtime confidence |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| screening | pass | 10 | 6 | 0 | 4 | 0.600 | 850 | 200 | 2050 | low_cached_champion |
| validation | expand/exhausted marginal pass | 5 | 5 | 0 | 0 | 1.000 | 0 | 0 | 1 | low_cached_champion |
| frozen | pass | 4 | 4 | 0 | 0 | 1.000 | 15000 | 12900 | 25700 | high |

Frozen pair-level supplement: 12/12 pair wins, pair median delta 14150,
sum delta 190300, median runtime ratio 0.946, runtime regression rate 0.0.

Interpretation: valid single promotion. It is a stronger evidence point than a
screening-only signal, but it still does not demonstrate sustained promotion
cadence.

## Production Reference And v0.3 Comparison

The requested v0.3 reference says:

- Production rerun after evidence/runtime fixes: Sonnet 3/3 campaigns promoted.
- Strongest synthetic Sonnet campaign reached 4 continuous structural
  promotions, v2 through v5.
- v0.3 production Sonnet frozen median deltas were about 29600, 30000, and
  38800 in the cited final visual report.

This v0.4 warehouse run:

- promoted in 2/3 repeats, not 3/3;
- produced 2 total promotions, not a continuous chain;
- produced one large frozen effect (`rep01`, md 50400), one moderate frozen
  effect (`rep03`, md 15000), and one frozen failure (`rep02`, md -400);
- ran production warehouse protocol/split/seeds, not the old synthetic matrix.

External production-reference gap was not recomputed by this run. The available
run artifacts compare candidates to the active champion, not to a fresh MILP or
CPLEX production reference. Per the v0.3 reference caveats and v3 boundary,
external gap/BKS/MILP information should remain report-only and must not be
treated as promotion evidence. The safest quality statement is therefore:
v0.4 still finds production improvements over its active champion, but this
3x24R result is weaker than v0.3's production 3/3 promotion cadence and far
weaker than the strongest v0.3 synthetic continuous-promotion trajectory.

## Per-Repeat Classification

| Repeat | Classification | Basis |
|---|---|---|
| rep01 | single promotion with proposal-path drain | 1 frozen pass and v2 champion; 21 proposal-quality blocks; critical proposal-quality-loop stagnation signal |
| rep02 | real plateau/frozen failure | reached frozen but abandoned; frozen md -400; generated plateau signal on repeated subcategory-consolidation mechanism |
| rep03 | single promotion with late plateau/drain | 1 frozen pass and v2 champion; 15 proposal-quality blocks; 2 heavy verification failures; plateau warning on repeated subcategory-consolidation mechanism |

None of the repeats should be classified as pre-Protocol/framework failure.
All three produced screening, validation, and frozen evidence.

## Branch Behavior

Branch depth by hypothesis count:

| Repeat | Deepest branches | Notes |
|---|---|---|
| rep01 | 7 hypotheses on `6a7632b1`, 5 on `b31289b9`, 5 on `943c0d2f`, 5 on `579465a8` | Deep same-mechanism iteration existed, but often stayed weak/no-effect or blocked by branch-lesson quality. Promoted branch had 1 hypothesis with screening/validation/frozen progression. |
| rep02 | 5 hypotheses on `e9278cc3`, `e7ee4097`, `b5e19c66`; 4 on `e0b22a0b` | The frozen path came from a one-hypothesis branch and failed. Other branches mostly repeated no-effect/marginal mechanisms. |
| rep03 | 7 hypotheses on `5f83d92b`, 5 on `a31b6330`, `9931c959`, `461dc035`; 3 on promoted branch `47ec47f1` | Same-mechanism continuation occurred, with several stale/parked lineages after champion change. Promoted branch produced the new `cost_preserving_tail_refit` operator. |

Clean-fork and branch-lesson accounting:

| Repeat | Branch-lesson usage present | Semantic satisfied | Clean-fork contrast satisfied | Preserved same-branch lessons | Block pattern |
|---|---:|---:|---:|---:|---|
| rep01 | 22 | 18 | 21 | 10 | 21 proposal-quality blocks |
| rep02 | 21 | 19 | 19 | 9 | 14 proposal-quality blocks |
| rep03 | 21 | 19 | 20 | 9 | 15 proposal-quality blocks |

The semantic layer is partially working: most recorded usage passed semantic
projection, and clean-fork contrasts were usually present. The failure mode is
still expensive: many LLM attempts included branch_lesson_usage material that
did not satisfy required target/action/mechanism linkage, causing pre-Protocol
quality blocks.

## Prompt And Context Composition

All known hypothesis traces used
`compact-measurement-diagnostics`:

| Repeat | Sessions | Traces | Known ablation traces | Prompt manifests | Branch-lesson truncated traces |
|---|---:|---:|---:|---:|---:|
| rep01 | 60 | 130 | 73 | 130 | 44 |
| rep02 | 55 | 120 | 62 | 120 | 51 |
| rep03 | 55 | 107 | 62 | 107 | 52 |

Prompt block family token-estimate share:

| Repeat | General | Research signal | Tool selection | Tool observation | Feedback | Governance |
|---|---:|---:|---:|---:|---:|---:|
| rep01 | 38.2% | 30.1% | 11.9% | 7.9% | 6.9% | 4.9% |
| rep02 | 35.7% | 34.0% | 11.8% | 7.7% | 6.1% | 4.6% |
| rep03 | 35.5% | 35.7% | 9.2% | 7.5% | 7.2% | 4.7% |

Compact research signals are still truncated and partially drowned. Research
signal share improved to roughly one-third of prompt volume, but general and
tool-selection/tool-observation payloads still consume about half of the visible
context. Branch-lesson context was truncated in 44-52 traces per repeat. This
matches the observed failure mode: the model often saw enough compact lessons
to mention them, but not enough or not in the right structure to satisfy the
machine semantic linkage checks.

## Failure And Drain Classes

Generated acceptance failure files report zero fatal acceptance failures for all
repeats. The important failures are non-fatal but research-efficiency relevant:

| Repeat | Proposal quality blocks | Patch/code edit failures | Old-string failures | Tool timeouts | Heavy verification failures | Fresh-runtime replay rows | Unresolved fresh-runtime drain |
|---|---:|---:|---:|---:|---:|---:|---|
| rep01 | 21 | 1 | 1 | 2 | 1 | 1 | pressure existed, no schedulable replay candidate |
| rep02 | 14 | 2 | 2 | 0 | 0 | 0 | pressure existed, no schedulable replay candidate |
| rep03 | 15 | 0 | 0 | 1 | 2 | 0 | pressure existed, no schedulable replay candidate |

Specific observed classes:

- `branch_lesson_usage_semantic_mismatch` and
  `branch_lesson_usage_linkage_unrecognized` drove most proposal-quality blocks.
- `old_string_not_found in operators/merge_vehicles.py` occurred once in
  `rep01` and twice in `rep02`.
- Heavy verification failures were V5 solution-consistency failures in `rep01`
  and `rep03`.
- Stale-source/old-string failures were present through `old_string_not_found`;
  no separate `stale_source` taxonomy count was reported.
- Fresh-runtime replay drain did not produce a useful closure in any repeat:
  each repeat ended with fresh champion runtime pressure but no scheduler-eligible
  structured replay candidate. `rep01` did record one non-counted fresh-runtime
  replay Protocol row, but the terminal drain still ended unresolved.
- No model repair attempts or model repair failures were reported in the status
  accounting.

## Conclusion

The run is valid as a longrun regression check and was successfully synced to
the server artifact root. It does not show a catastrophic v0.4 warehouse
framework regression: all cells finished with exit 0, all reached Protocol and
frozen, and 2/3 repeats promoted. It also does not recover the v0.3 promotion
cadence: v0.3 production Sonnet was 3/3 after fixes, and the strongest v0.3
synthetic run showed 4 continuous promotions; this v0.4 warehouse run produced
only isolated single promotions and substantial proposal/context drain.

The main postrun finding is not "warehouse has no opportunity." It is:
v0.4 warehouse can still find production improvements, but compact measurement
diagnostics and branch-lesson semantics are not yet efficient enough to sustain
continuous promotion. The limiting path is proposal/context/code-edit quality,
plus unresolved fresh-runtime replay closure, not wrapper/preflight failure.
