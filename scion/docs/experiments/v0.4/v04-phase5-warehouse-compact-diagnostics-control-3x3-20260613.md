# v0.4 Phase 5 Warehouse Compact Diagnostics Control 3x3

*Date: 2026-06-13*
*Run root: `/home/clawd/research/scion-experiments/v04-phase5-warehouse-compact-diagnostics-control-3x3-4r-20260613T092510Z-claw`*
*Launch commit: `0eca84f`*

## Purpose

This run is the longer follow-up to the 2R compact diagnostics shakedown. It
tests whether the compact prompt surface is usable across repeated warehouse
campaign cells after removing the large standalone measurement diagnostics
block.

This is still not the final governance-value matrix. Every arm keeps
`measurement_governance=on`; only proposal-visible prompt context changes.
The report-only `control_pair_key` gives matched postrun pairing by repeat, but
it is not deterministic LLM replay.

## Configuration

- Problem: `scion/problems/warehouse_delivery/problem.yaml`
- Protocol: `scion/problems/warehouse_delivery/protocol_prod.yaml`
- Split: `scion/problems/warehouse_delivery/split_manifest_prod.yaml`
- Seeds: `scion/problems/warehouse_delivery/seed_ledger.yaml`
- Model: local `gpt-5.5` proxy
- Repeats: `3`
- Arms: `full`, `compact-measurement-diagnostics`,
  `no-measurement-diagnostics`
- Rounds per cell: `4`
- Solver cap: uniform `30s`
- Early stop: disabled
- Agentic proposal timeout: `600s`
- Control key: `warehouse.compactdiag-control:<repeat>`
- Arm order:
  - `rep01`: full -> compact -> no-measurement
  - `rep02`: compact -> no-measurement -> full
  - `rep03`: no-measurement -> full -> compact

## Completion

All 9 cells exited `0`; no `run_errors.log` was produced. Postrun acceptance is
complete: 9 summaries, 9 failure reports, 9 proposal trajectory manifests, and
9 pairwise compares exist under `postrun_acceptance`.

Non-fatal candidate failures occurred in rep02:

- `rep02/compact-measurement-diagnostics`: one `code_generation_failed`
  `old_string_not_found` on `operators/merge_vehicles.py`.
- `rep02/no-measurement-diagnostics`: one same `old_string_not_found` failure.
- `rep02/no-measurement-diagnostics`: one branch abandoned fast after two
  verification-heavy failures.

Those failures are campaign trajectory evidence, not wrapper failures.

## Aggregate Results

| arm | experiments | validation | frozen | promotions | case W/L/T | pair W/L/T | decisions | candidates | sessions/traces |
| --- | ---: | ---: | ---: | ---: | --- | --- | --- | ---: | ---: |
| `full` | 12 | 0 | 0 | 0 | `16/14/58` | `52/47/77` | abandon 4, continue 8 | 15 | `24/76` |
| `compact-measurement-diagnostics` | 13 | 0 | 0 | 0 | `21/9/74` | `73/48/87` | continue 11, expand 1, abandon 1 | 12 | `25/75` |
| `no-measurement-diagnostics` | 12 | 0 | 0 | 0 | `25/13/68` | `78/50/84` | continue 6, expand 1, abandon 5 | 15 | `25/74` |

All arms had `screening_pass_rate=0.0` and ended at champion v1. The pair-level
win rate was highest for `no-measurement-diagnostics` (`36.79%`) and close for
compact (`35.10%`), but no arm reached validation, frozen, or promotion. This
run therefore does not establish a quality winner.

Status accounting across the three repeats:

- `full`: 12 proposal attempts, 11 effective protocol rounds, 1 verification
  failure, 0 quality blocks, 1 fresh-runtime replay protocol row.
- `compact-measurement-diagnostics`: 14 proposal attempts, 12 effective
  protocol rounds, 1 verification failure, 2 quality blocks, 1 fresh-runtime
  replay protocol row.
- `no-measurement-diagnostics`: 14 proposal attempts, 11 effective protocol
  rounds, 2 verification failures, 2 quality blocks, 1 fresh-runtime replay
  protocol row.

All nine cells were `valid`, `complete`, and stopped because max rounds were
exhausted.

## Prompt Contract

The prompt visibility contract passed in all hypothesis/preview manifests.

| arm | hypothesis manifests | measurement visibility | standalone diagnostics | compact diagnostics |
| --- | ---: | --- | ---: | ---: |
| `full` | 24 | `full` | 24 | 24 |
| `compact-measurement-diagnostics` | 22 | `compact` | 0 | 22 |
| `no-measurement-diagnostics` | 22 | `suppressed` | 0 | 0 measurement-key hits |

Every arm preserved the broader research context in hypothesis prompts:
`cross_branch_research_map`, `branch_lesson_usage_context`,
`experiment_history_this_branch`, `sibling_branches`, and
`current_champion_research_code` appeared in all counted hypothesis manifests.

Code-phase target source visibility was true for every code manifest in all
arms. Caveat: each arm had two code manifests where optional full-algorithm-read
visibility was false, producing two `protected_source_visible=false` records per
arm. Required integration source visibility remained true.

## Boundary Checks

The report-only trajectory artifacts stayed outside the v3 decision boundary:

- 9/9 manifests have `report_only=true`,
  `comparison_is_decision_input=false`, `campaign_state_mutated=false`,
  `scheduler_state_mutated=false`, and `promotion_state_mutated=false`.
- 9/9 manifests and compares have `raw_prompt_excluded=true`,
  `raw_response_excluded=true`, `patch_body_excluded=true`, and
  `decision_features_excluded=true`.
- Leakage scan found no `prompt_text`, `llm_response`, `code_content`,
  `bks_gap`, `aa_rows`, or `provider_visible_prompt` in `postrun_acceptance`.
- The `no-measurement-diagnostics` arm had no
  `Problem Measurement Diagnostics`, `problem_measurement_diagnostics`, or
  `compact_problem_measurement_diagnostics` hits in agentic session artifacts.

All 9 compares have matched control keys and report:

- `observational_only=false`
- `llm_deterministic_replay=false`
- `causal_replay_label=control_pair_key_matched_not_deterministic_llm_replay`

Interpretation: the report pairing is pre-registered and matched; the LLM
trajectories still diverge and are not causal replays.

## Branch Trajectory

Compact did not damage branch-depth behavior.

- `full`: 7 branches total; states were abandoned 4, active/explore 2, parked
  lineage 1. Maximum inferred branch depth was 3 hypotheses. Three branches had
  multiple hypotheses.
- `compact-measurement-diagnostics`: 6 branches total; states were
  active/explore 4, parked lineage 1, abandoned 1. Maximum inferred branch depth
  was 3 hypotheses. Five branches had multiple hypotheses.
- `no-measurement-diagnostics`: 9 branches total; states were abandoned 6,
  active/explore 2, parked lineage 1. Maximum inferred branch depth was
  3 hypotheses. Two branches had multiple hypotheses.

Representative same-mechanism follow-up:

- `full`: a `subcategory_consolidation` branch reached 3 hypotheses and
  4 screening events before parking as no-effect; a cost-tightening branch
  reached 3 hypotheses and remained active marginal.
- `compact-measurement-diagnostics`: a `same_subcategory_pack_upgrade` branch
  reached 2 hypotheses and 4 screening events before parking no-effect; a
  `cost_fill_order_move` branch reached 3 hypotheses and remained active
  marginal.
- `no-measurement-diagnostics`: a `subcategory_capacity_consolidate` branch
  reached 3 hypotheses and 4 screening events before parking on runtime
  regression; one expanded branch still ended on runtime/budget saturation.

This is useful trajectory evidence, but because no arm reached validation or
promotion it is not evidence that one prompt arm produces better accepted
research.

## Interpretation

The compact prompt surface is accepted as a viable Phase 5 baseline candidate:
it removes the large standalone measurement diagnostics section, keeps bounded
measurement signal available, and preserves branch/cross-branch research
memory. It also maintains branch follow-up behavior at least as well as the
other prompt arms in this run.

This run does not justify immediate on-demand diagnostics. Both compact and
no-measurement stopped at screening only; there is no clear evidence that
compact failed because it lacked detailed pull-based measurement facts.

Next recommended design:

- Use `compact-measurement-diagnostics` as the main prompt baseline candidate.
- Keep `no-measurement-diagnostics` as a strong ablation arm and `full` as a
  reference arm.
- Increase repeats and/or rounds only if the goal is a stronger prompt-context
  value claim; otherwise move to a pre-registered `compact+on-demand` arm only
  if the experiment question is specifically whether detailed measurement facts
  are needed.
- For any future validation/frozen/promotion or strong screening-expand
  candidate, run activation-complete fixed-candidate replay before using it as
  governance-value evidence.
