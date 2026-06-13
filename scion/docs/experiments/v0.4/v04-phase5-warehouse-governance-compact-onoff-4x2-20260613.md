# v0.4 Phase 5 Warehouse Compact Governance ON/OFF 4x2

*Date: 2026-06-13*
*Run root: `/home/clawd/research/scion-experiments/v04-phase5-warehouse-governance-compact-onoff-4x2-8r-20260613T115956Z-claw`*
*Launch commit: `e1e4c4809bab7c3666229523f3ff04a5fbc93d47`*

## Purpose

This run is the first warehouse Phase 5 measurement-governance ON/OFF control
after accepting `compact-measurement-diagnostics` as the prompt baseline
candidate.

Both arms use the same warehouse production protocol/split/seeds, local
`gpt-5.5`, disabled early stop, `8` requested effective attempts per cell,
uniform `30s` solver cap, and compact proposal context. The only intended
campaign setting difference is:

- `on_compact`: `--measurement-governance on`
- `record_only_compact`: `--measurement-governance record-only`

Matched `control_pair_key=warehouse.gov-compact-onoff:<repeat>` values are
report-layer metadata. They pair the repeats but do not replay the same LLM
trajectory.

## Configuration

- Problem: `scion/problems/warehouse_delivery/problem.yaml`
- Problem V1 spec used for fixed replay:
  `scion/problems/warehouse_delivery/problem-v1.yaml`
- Protocol: `scion/problems/warehouse_delivery/protocol_prod.yaml`
- Split: `scion/problems/warehouse_delivery/split_manifest_prod.yaml`
- Seeds: `scion/problems/warehouse_delivery/seed_ledger.yaml`
- Model: local `gpt-5.5`, `SCION_BASE_URL=http://127.0.0.1:8080`
- Repeats: `4`
- Arms: `on_compact`, `record_only_compact`
- Requested rounds per cell: `8`
- Solver cap: uniform `30s`
- Early stop: disabled
- Agentic proposal timeout: `900s`
- Order:
  - `rep01`: on -> record-only
  - `rep02`: record-only -> on
  - `rep03`: on -> record-only
  - `rep04`: record-only -> on

The launch worktree was clean for tracked files at commit `e1e4c48` except for
two pre-existing unrelated untracked paths recorded in `launch.env`.

## Completion

All 8 cells exited `0`; no `run_errors.log` was produced. Postrun acceptance
created summaries, failure reports, proposal trajectory manifests, and compares
for all four repeat pairs.

| Repeat | Arm | Start UTC | End UTC | Exit |
| --- | --- | --- | --- | ---: |
| rep01 | on | 2026-06-13T12:01:37Z | 2026-06-13T12:33:42Z | 0 |
| rep01 | record-only | 2026-06-13T12:33:42Z | 2026-06-13T13:18:43Z | 0 |
| rep02 | record-only | 2026-06-13T13:18:45Z | 2026-06-13T13:49:36Z | 0 |
| rep02 | on | 2026-06-13T13:49:36Z | 2026-06-13T14:15:22Z | 0 |
| rep03 | on | 2026-06-13T14:15:24Z | 2026-06-13T14:47:38Z | 0 |
| rep03 | record-only | 2026-06-13T14:47:38Z | 2026-06-13T15:20:30Z | 0 |
| rep04 | record-only | 2026-06-13T15:20:32Z | 2026-06-13T15:47:11Z | 0 |
| rep04 | on | 2026-06-13T15:47:11Z | 2026-06-13T16:21:18Z | 0 |

## Protocol Results

Every cell completed the max-round budget counter
`effective_rounds_completed=8` and stopped with `max_rounds_exhausted`.
That budget counter is not the same thing as formal candidate count or protocol
metric rows.

| Cell | Effective budget | Protocol rows | Formal screened | Screening rows | Validation | Frozen | Champion | Sessions/traces | Quality blocks | Fresh drain |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| rep01/on | 8 | 8 | 8 | 9 | 0 | 0 | v1 | 16/51 | 0 | 1 exec, 1 skip |
| rep01/record-only | 8 | 9 | 7 | 7 | 1 | 1 | v2 | 13/40 | 2 | 0 exec, 1 skip |
| rep02/on | 8 | 8 | 8 | 8 | 0 | 0 | v1 | 14/44 | 0 | 0 exec, 1 skip |
| rep02/record-only | 8 | 9 | 9 | 10 | 0 | 0 | v1 | 19/58 | 2 | 1 exec, 1 skip |
| rep03/on | 8 | 9 | 9 | 10 | 0 | 0 | v1 | 19/60 | 2 | 1 exec, 1 skip |
| rep03/record-only | 8 | 7 | 7 | 7 | 0 | 0 | v1 | 19/57 | 2 | 0 exec, 1 skip |
| rep04/on | 8 | 6 | 6 | 7 | 0 | 0 | v1 | 19/56 | 1 | 1 exec, 1 skip |
| rep04/record-only | 8 | 6 | 6 | 8 | 0 | 0 | v1 | 16/45 | 0 | 2 exec, 1 skip |

Aggregate status accounting:

| Arm | Summary experiments | Promotions | Validation | Frozen | Formal screened | Screening rows | Sessions/traces | Quality blocks | Fresh drain exec |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| on | 34 | 0 | 0 | 0 | 31 | 34 | 68/211 | 3 | 3 |
| record-only | 34 | 1 | 1 | 1 | 29 | 32 | 67/200 | 6 | 3 |

Aggregate screening summaries:

| Arm | Case W/L/T | Decisions |
| --- | --- | --- |
| on | 45/32/177 | abandon 7, continue 25, expand 1, queue_validate 1 |
| record-only | 40/20/184 | abandon 8, continue 22, expand 1, queue_validate 1, queue_frozen 1, promote 1 |

Raw trajectory therefore shows one promotion only in `record_only`, while ON
has one strong screening expand/queue-validate path in rep02. This raw result
is observational only because LLM trajectories, candidate counts, formal
artifacts, and retry histories diverged.

## Fixed-Candidate Replay

Two strong candidates were replayed with the same candidate patch under both
measurement-governance arms. The first attempt used the legacy warehouse
`problem.yaml` and failed because fixed replay directly expects
`ProblemSpecV1`; rerunning with `problem-v1.yaml` succeeded. This problem-spec
bridge mismatch is a tooling repair item.

| Source | Candidate | Source outcome | Replay result |
| --- | --- | --- | --- |
| rep01/record-only | `070b6e4eb3046487` | promoted to v2 in the original trajectory | ON and record-only both `SCREENING_EXPAND`; canary passed; W/L/T 3/0/3; median delta 950.0; CI [0.0, 9325.0] |
| rep02/on | `d31c53b19d23ca4f` | strong screening expand then queue_validate in the original trajectory | ON and record-only both `SCREENING_EXPAND`; canary passed; W/L/T 5/1/4; median delta 875.0; CI [-350.0, 2775.0] |

Replay artifacts:

- `fixed_candidate_replay/rep01_record_only_promoted/fixed_candidate_replay_comparison_v1spec.v1.json`
- `fixed_candidate_replay/rep02_on_strong/fixed_candidate_replay_comparison_v1spec.v1.json`

Both comparisons are report-only, have `comparison_is_decision_input=false`,
mutate no campaign/scheduler/promotion state, exclude `DecisionFeatures`, and
exclude raw paired rows and measurement diagnostics.

Interpretation: the strongest candidate-level evidence does not show an ON vs
record-only difference. The original rep01 record-only promotion cannot be
credited to governance being off; it includes LLM trajectory and lifecycle path
differences after the candidate was generated.

## Accounting And Failure Findings

The run is valid, but it exposes report/accounting debt that must be fixed
before treating Phase 5 governance evidence as clean.

- `effective_rounds_completed` is the max-round budget counter. It can differ
  from `effective_protocol_rounds`, `formal_screened_candidates`,
  `screening_protocol_results`, and formal artifact count.
- Heavy verification failures consume effective budget but do not create
  protocol rows. Example: `rep04/on` finished with budget `8`, protocol `6`,
  formal `6`.
- Fresh-runtime replay drain can add post-budget screening rows. Example:
  `rep04/record-only` finished with formal `6`, screening rows `8`, and
  fresh drain `2 exec / 1 skip`.
- Formal candidate artifacts can exceed formal screened counters because one
  hypothesis can produce multiple candidate artifacts. `rep04/on` had 8
  artifacts from 6 hypotheses and 6 formal screened candidates.
- Failure reports showed `total_failures=0` for every cell even though run logs
  recorded non-fatal code-generation failures and timeouts. Those failures are
  research-efficiency evidence and should appear in a stable postrun failure
  taxonomy.

Observed non-fatal failures:

- `old_string_not_found in operators/merge_vehicles.py`: rep01 record-only,
  rep02 record-only, rep03 on, rep03 record-only, rep04 on.
- `stale_source for operators/merge_vehicles.py`: rep04 on.
- `Tool call timeout`: rep03 on once, rep04 on twice.
- `abandon_fast after 2 consecutive 'verification_heavy' failures`:
  rep04 record-only.

## Branch Research Shape

Both arms show real within-branch follow-up, not only one-off attempts. The
cleaner branch-depth view counts distinct formal protocol hypotheses per
branch, excluding fresh-replay rows, code retries, and duplicate candidate
artifacts for the same hypothesis.

| Arm | Branches | True formal hypotheses | Max true depth | Mean true depth | Multi-formal branches | Follow-up | Same-family follow-up | Same-target follow-up |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| on | 17 | 30 | 4 | 1.76 | 10 | 16 | 8 | 13 |
| record-only | 16 | 28 | 3 | 1.75 | 9 | 15 | 5 | 12 |

Representative branch follow-up:

- `rep02/on` branch `5bec56cf...` produced four formal events modifying
  `operators/move_order.py`.
- `rep01/record-only` branch `1daa7ae6...` produced the full
  expand -> validate -> frozen -> promote path for `operators/merge_vehicles.py`.
- `rep04/record-only` branches `85ad848a...` and `a14c4100...` each produced
  three formal continue-explore events on newly created cost/subcategory
  operators.
- `rep04/on` branch `7f1cd616...` reached three formal events, but also
  included old-string/stale-source failures and a tool timeout chain. Treat it
  as mixed branch depth, not clean research progress.

Artifact/event counters can overstate research depth because a single
hypothesis may produce more than one candidate artifact or retry record. The
postrun research-efficiency report should therefore publish both artifact counts
and true formal-hypothesis depth.

## Prompt And Source Visibility

Compact context behaved as intended at the measurement-diagnostics layer:

- 411 API-visible prompt manifests were produced.
- Call kinds: 65 hypothesis, 58 hypothesis-preview retry, 210 tool-selection,
  and 78 code manifests.
- `context_profile_metadata.measurement_diagnostics_visibility` was `compact`
  in 63 manifests and `suppressed` in 60 manifests.
- No manifest sections contained a standalone `Problem Measurement Diagnostics`
  block.
- Hypothesis prompts retained branch/cross-branch research context and current
  champion research code.

The code phase still has a source-visibility/patch-identity gap:

- 67/78 code manifests satisfied the checked source visibility guarantee.
- 11/78 code manifests recorded `missing_required_source_paths` for existing
  operator modifications, while still marking the target source visible.
- This aligns with observed `old_string_not_found` and `stale_source` failures
  on `operators/merge_vehicles.py`.

Source/code visibility therefore must remain protected during compression, and
the manifest/report layer needs clearer source identity diagnostics for modify
operations.

## Boundary Checks

All four proposal-trajectory compares passed the report-only boundary checks:

- `report_only=true`
- `llm_deterministic_replay=false`
- `causal_replay_label=control_pair_key_matched_not_deterministic_llm_replay`
- `comparison_is_decision_input=false`
- `campaign_state_mutated=false`
- `scheduler_state_mutated=false`
- `promotion_state_mutated=false`
- `raw_prompt_excluded=true`
- `raw_response_excluded=true`
- `patch_body_excluded=true`
- `decision_features_excluded=true`

The fixed-candidate replay comparisons also stayed outside campaign,
scheduler, promotion, and Decision state.

## Interpretation

This run completes the planned compact-baseline governance ON/OFF matrix, but
it does not establish a governance-value winner.

What is supported:

- The ON/OFF switch can run through four warehouse repeat pairs with compact
  context and complete report-only artifacts.
- Compact context remains usable without the large standalone measurement block.
- Warehouse still produces strong candidate patches; fixed replay confirms two
  such patches are positive screening-expand candidates.
- Candidate-level fixed replay shows no ON/record-only difference for the two
  strongest candidates tested.

What is not supported:

- The raw rep01 record-only promotion is not causal evidence that governance
  OFF is better. The fixed screening replay for that candidate is identical
  under ON and record-only.
- The absence of ON promotions is not evidence that governance ON is worse.
  The ON arm had a separate strong candidate in rep02, and trajectories were
  not deterministic LLM replays.
- The current report surfaces are not yet clear enough to summarize research
  efficiency from one counter.

## Next Repairs

Before running another formal governance-value matrix, v0.4 should repair:

1. Postrun accounting summary: show effective budget, protocol rows, formal
   candidates, artifact rows, fresh-runtime drain rows, validation/frozen rows,
   quality blocks, verification-heavy failures, and code-generation failures in
   one stable report.
2. Failure taxonomy: include non-fatal agentic/code/timeout/verification-heavy
   failures in failure reports or a dedicated research-efficiency report.
3. Code-phase source identity: ensure modify operations keep required source
   visibility and patch-source digests aligned, especially for existing
   operator files.
4. Fixed replay problem bridge: either accept legacy `problem.yaml` through the
   same bridge as campaign run or fail early with a clear instruction to use
   `problem-v1.yaml`.
5. Candidate replay scope: fixed replay currently validates screening-stage
   candidate behavior; validation/frozen/promotion causal claims still need an
   explicit replay path or a documented limitation.

The queued CVRP/VRP ALNS+VNS vs ALNS-only baseline-strength contrast remains
useful, but it should start after these warehouse governance-run findings are
recorded and the immediate replay/accounting/source-identity repairs are
planned.
