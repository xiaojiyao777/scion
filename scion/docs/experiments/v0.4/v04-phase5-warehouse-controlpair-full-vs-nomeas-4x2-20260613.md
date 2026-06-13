# Warehouse Control-Pair Full vs No-Measurement Diagnostics

Date: 2026-06-13

Run root:
`/home/clawd/research/scion-experiments/v04-phase5-warehouse-controlpair-full-vs-nomeas-4x2-8r-20260613T011820Z-claw`

Postrun artifacts:
`/home/clawd/research/scion-experiments/v04-phase5-warehouse-controlpair-full-vs-nomeas-4x2-8r-20260613T011820Z-claw/postrun_acceptance`

## Purpose

This is a Phase 5 strong-control proposal-context experiment for warehouse.
It isolates prompt-visible measurement diagnostics while preserving broader
branch and cross-branch research context.

Both arms use `measurement_governance=on`. The arms differ only in
`--proposal-context-ablation`:

- `full`: measurement diagnostics are visible in hypothesis prompts.
- `no-measurement-diagnostics`: measurement diagnostics are hidden from
  hypothesis prompts, while branch/cross-branch research context remains
  visible.

This is not deterministic LLM replay and not a full governance ON/OFF test.
Matched `control_pair_key` values are report-layer metadata used to identify
pre-registered repeat pairs.

## Launch

The run launched from commit `bd8bfd8e020be2a51d1268070870c7ee2ff6b2ce` on
branch `codex/v04-evidence-repair-plan`.

Configuration from `launch.env`:

- problem: `scion/problems/warehouse_delivery/problem.yaml`
- protocol: `scion/problems/warehouse_delivery/protocol_prod.yaml`
- split: `scion/problems/warehouse_delivery/split_manifest_prod.yaml`
- seeds: `scion/problems/warehouse_delivery/seed_ledger.yaml`
- model: local `gpt-5.5`, `SCION_BASE_URL=http://127.0.0.1:8080`
- repeats: 4 order-balanced pairs
- rounds: 8 per cell
- time limit: `--time-limit-sec 30`
- controls: `--disable-early-stop`, `--agentic-proposal`,
  `--agentic-session-timeout-sec 900`
- manifest key prefix: `warehouse.full-vs-nomeas`

All 8 cells exited `0`.

| Repeat | Arm | Start UTC | End UTC | Exit |
| --- | --- | --- | --- | ---: |
| rep01 | full | 2026-06-13T01:16:41Z | 2026-06-13T01:43:39Z | 0 |
| rep01 | no-measurement-diagnostics | 2026-06-13T01:43:39Z | 2026-06-13T02:21:16Z | 0 |
| rep02 | no-measurement-diagnostics | 2026-06-13T02:21:16Z | 2026-06-13T02:50:59Z | 0 |
| rep02 | full | 2026-06-13T02:50:59Z | 2026-06-13T03:16:32Z | 0 |
| rep03 | full | 2026-06-13T03:16:32Z | 2026-06-13T03:43:31Z | 0 |
| rep03 | no-measurement-diagnostics | 2026-06-13T03:43:31Z | 2026-06-13T04:05:59Z | 0 |
| rep04 | no-measurement-diagnostics | 2026-06-13T04:05:59Z | 2026-06-13T04:49:13Z | 0 |
| rep04 | full | 2026-06-13T04:49:13Z | 2026-06-13T05:23:42Z | 0 |

## Protocol Results

Every cell is `run_validity.valid=true`, `complete=true`, and
`completed_requested_rounds=true`.

| Cell | Effective protocol rows | Completed budget counter | Screening rows | Validation | Frozen | Fresh replay | Champion promotions | Latest champion | Attempts | Quality blocks |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| rep01/full | 8 | 8 | 9 | 0 | 0 | 1 | 0 | 1 | 8 | 0 |
| rep01/no-measurement-diagnostics | 8 | 8 | 6 | 1 | 1 | 0 | 1 | 2 | 8 | 0 |
| rep02/full | 8 | 8 | 8 | 0 | 0 | 0 | 0 | 1 | 8 | 0 |
| rep02/no-measurement-diagnostics | 8 | 8 | 9 | 0 | 0 | 1 | 0 | 1 | 9 | 1 |
| rep03/full | 6 | 8 | 6 | 0 | 0 | 0 | 0 | 1 | 13 | 4 |
| rep03/no-measurement-diagnostics | 8 | 8 | 8 | 0 | 0 | 0 | 0 | 1 | 8 | 0 |
| rep04/full | 7 | 8 | 7 | 0 | 0 | 0 | 0 | 1 | 10 | 1 |
| rep04/no-measurement-diagnostics | 9 | 8 | 6 | 2 | 1 | 0 | 1 | 2 | 10 | 2 |

Aggregate by arm:

| Arm | Promotions | Effective protocol rows | Screening rows | Validation | Frozen | Fresh replay | Attempts | Quality blocks |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| full | 0 | 29 | 30 | 0 | 0 | 1 | 39 | 5 |
| no-measurement-diagnostics | 2 | 33 | 29 | 3 | 2 | 1 | 35 | 3 |

`effective_rounds_completed` is the budget counter used for max-round
completion. It can differ from `effective_protocol_rounds` when verification or
quality-blocked attempts consume budget but do not produce protocol metric rows,
or when validation/frozen protocol rows are reported in the protocol-row total.

## Screening Quality

Aggregate screening evidence favored `no-measurement-diagnostics`.

| Arm | Screening experiments | Case W/L/T | Case WR | Pair W/L/T | Pair WR |
| --- | ---: | --- | ---: | --- | ---: |
| full | 30 | 53/34/149 | 0.225 | 171/129/172 | 0.362 |
| no-measurement-diagnostics | 34 | 72/29/143 | 0.295 | 196/95/197 | 0.402 |

Promotion dossiers confirm two real warehouse promotion paths in
`no-measurement-diagnostics`:

- `rep01/no-measurement-diagnostics`: hypothesis
  `a74d5a4e-5ad9-4349-b54d-98ec39645bd1`, branch `92e094d8...`,
  target `operators/merge_vehicles.py`, promoted to champion v2. Screening
  passed with `8/0/6`, median delta `875.0`; validation passed with `5/0/0`,
  median delta `28400.0`; frozen passed with `4/0/0`, median delta `30200.0`.
- `rep04/no-measurement-diagnostics`: hypothesis
  `2b7a3f7e-b899-4a5b-894b-d624fe2570c1`, branch `db8e2d7a...`,
  target `operators/split_safe_cost_repack.py`, promoted to champion v2.
  Screening expanded with `8/1/7`, median delta `775.0`; validation expanded
  with `5/0/0`, median delta `0.0`; frozen passed with `4/0/0`, median delta
  `47150.0`.

The second promotion has a caveat: validation runtime evidence was marked
`insufficient` and hierarchical validation remained uncertain, but frozen
runtime evidence was high-confidence and the frozen hierarchical gate passed.

## Branch Research Shape

The full arm explored deeper branches; the no-measurement arm produced stronger
acceptance outcomes.

| Cell | Branches | Max depth | Mean depth | Depths |
| --- | ---: | ---: | ---: | --- |
| rep01/full | 3 | 4 | 2.67 | 4, 2, 2 |
| rep01/no-measurement-diagnostics | 4 | 2 | 1.25 | 2, 1, 1, 1 |
| rep02/full | 4 | 4 | 2.00 | 4, 2, 1, 1 |
| rep02/no-measurement-diagnostics | 3 | 3 | 2.33 | 3, 2, 2 |
| rep03/full | 4 | 4 | 2.25 | 4, 2, 2, 1 |
| rep03/no-measurement-diagnostics | 4 | 3 | 1.50 | 3, 1, 1, 1 |
| rep04/full | 5 | 3 | 1.60 | 3, 2, 1, 1, 1 |
| rep04/no-measurement-diagnostics | 4 | 2 | 1.25 | 2, 1, 1, 1 |

Aggregate branch depth:

| Arm | Branches | Max depth | Mean depth |
| --- | ---: | ---: | ---: |
| full | 16 | 4 | 2.06 |
| no-measurement-diagnostics | 15 | 3 | 1.53 |

SQLite lineage checks found no orphan or cross-branch `parent_hypothesis_id`
violations. Same-branch continuation therefore remains reconstructable for
postrun analysis without entering `DecisionFeatures`.

Interpretation: prompt-visible measurement diagnostics did not improve
warehouse acceptance outcomes in this experiment. The full arm tended to spend
more effort on deeper same-branch search and generated more LLM calls, but this
did not translate into validation, frozen, or promotion evidence. The
no-measurement arm made shallower trajectories that found two strong promotion
paths.

## Prompt And Trajectory Checks

Hypothesis prompt manifests confirmed intended context isolation:

| Arm | Hypothesis manifests | Measurement diagnostics | Compact research | Cross-branch map | Branch lessons | Branch history | Sibling branches | Research char share avg | Governance char share avg |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| full | 62 | 62 | 62 | 62 | 62 | 62 | 62 | 0.361 | 0.080 |
| no-measurement-diagnostics | 46 | 0 | 46 | 46 | 46 | 46 | 46 | 0.330 | 0.089 |

Both arms retained `current_champion_research_code` in every hypothesis prompt.
`current_branch_code` appears only when a current branch code context exists
for that proposal phase. All inspected hypothesis manifests have
`proposal_visibility_only=true` and `decision_features_excluded=true`.

The postrun generated 8 manifests and 4 compares. All compares use matched
keys:

| Repeat | Control key | Observational only | Deterministic LLM replay | Label |
| --- | --- | ---: | ---: | --- |
| rep01 | `warehouse.full-vs-nomeas:rep01` | false | false | `control_pair_key_matched_not_deterministic_llm_replay` |
| rep02 | `warehouse.full-vs-nomeas:rep02` | false | false | `control_pair_key_matched_not_deterministic_llm_replay` |
| rep03 | `warehouse.full-vs-nomeas:rep03` | false | false | `control_pair_key_matched_not_deterministic_llm_replay` |
| rep04 | `warehouse.full-vs-nomeas:rep04` | false | false | `control_pair_key_matched_not_deterministic_llm_replay` |

The compare artifacts show large trajectory divergence, which is expected:
the key pairs the repeats, but it does not replay the same LLM trajectory.
Formal-candidate joins still rely on conservative report-only attribution and
have missing joins, especially in full arm repeats with many partial or failed
sessions. This limits fine-grained causal trajectory claims.

## Leakage And Boundary Checks

Report artifacts are non-mutating and excluded from decision inputs:

- `report_only=true`
- `decision_features_excluded=true`
- `campaign_state_mutated=false`
- `promotion_state_mutated=false`
- raw prompt/response/patch body exclusion flags are set correctly

The initial raw-string leakage scan found `raw_prompt` only as the safety flag
`raw_prompt_saved=false` in prompt manifests. No manifest stored raw prompt
content.

No `no-measurement-diagnostics` hypothesis prompt contained
`problem_measurement_diagnostics`.

## Conclusion

This experiment is valid Phase 5 strong-control evidence for prompt-visible
measurement diagnostics on warehouse, but it is not a full governance-value
conclusion.

Findings:

1. The explicit control-pair report path worked: all repeat compares have
   matched keys, are report-only, non-mutating, and correctly state that LLM
   replay is not deterministic.
2. Measurement diagnostics visibility was cleanly isolated in hypothesis
   prompts while branch/cross-branch research context stayed visible in both
   arms.
3. `no-measurement-diagnostics` outperformed `full` on acceptance outcomes in
   this run: 2 promotions, 3 validation rows, and 2 frozen rows versus none for
   `full`.
4. `full` produced deeper branch research, more sessions/traces, and more
   research-token volume, but those deeper trajectories did not produce stronger
   warehouse evidence.
5. The result argues against rendering measurement diagnostics as a large
   always-visible prompt block for warehouse. It does not argue against the
   problem-owned measurement declaration layer, because measurement governance
   remained ON in both arms.

Next steps:

- Keep `no-measurement-diagnostics` as the better warehouse prompt baseline for
  the next rung unless a problem needs measurement diagnostics to shape proposal
  selection.
- Replace always-visible measurement diagnostics with a compact or on-demand
  prompt summary, while preserving deterministic protocol/runtime/lifecycle
  measurement governance.
- Do not adopt `minimal-research-context`; prior evidence showed that it removes
  too much branch/cross-branch research memory.
- Add a follow-up check for promotion-path robustness on the two promoted
  patches, especially the rep04 validation-uncertain/frozen-pass path.
- Keep CVRP out of formal Phase 5 governance-value conclusions until its
  measurement-power problem is resolved.
