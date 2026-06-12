# v0.4 Warehouse Proposal Context Ablation Formal Repeat

*Date: 2026-06-12*
*Branch: `codex/v04-evidence-repair-plan`*
*Executor commit: `171648c4204d`*
*Status: valid 3x3x8 proposal-context ablation evidence; observational only*

## Summary

The warehouse proposal-context ablation formal repeat completed cleanly. It ran
three independent repeats of three free-running prompt-context arms, each with
`measurement_governance=on`, local `gpt-5.5`, warehouse production
protocol/split/seeds, `--rounds 8`, uniform `--time-limit-sec 30`,
`--disable-early-stop`, and `--agentic-proposal`.

All nine cells exited `0` and were valid complete runs. No arm promoted beyond
champion v1. The run is valid evidence about proposal-context behavior and
research efficiency, but it is not a causal governance-value conclusion:
proposal trajectories are free-running LLM trajectories and all generated
proposal-trajectory comparisons are explicitly `observational_only=true`.

The main signal is:

- `full` produced the best evidence quality in this repeat set: the strongest
  aggregate screening rates, two queue-validate paths, one actual validation
  row, the only frozen row, and zero fresh-runtime replay rows.
- `no-measurement-diagnostics` successfully removed prompt-visible measurement
  diagnostics while preserving other research context. It reached one
  validation row but no frozen row.
- `minimal-research-context` produced the most replayable formal candidates but
  sharply reduced useful research signal density, reached no validation/frozen
  rows, and triggered fresh-runtime replay in all three repeats.

## Artifacts

Run root:

`/home/clawd/research/scion-experiments/v04-phase5-warehouse-context-ablation-formal-3x3-8r-20260612T114219Z-claw`

Postrun acceptance artifacts:

`/home/clawd/research/scion-experiments/v04-phase5-warehouse-context-ablation-formal-3x3-8r-20260612T114219Z-claw/postrun_acceptance`

Key files:

- `launch.env`
- `cell_status.tsv`
- `postrun_acceptance/manifests/*.proposal_trajectory_manifest.v1.json`
- `postrun_acceptance/compares/*.compare.json`
- `postrun_acceptance/summaries/*.summary.json`
- `postrun_acceptance/failures/*.failures.json`

Launch record:

```text
schema=scion.context_ablation_formal_repeats.v1
branch=codex/v04-evidence-repair-plan
commit=171648c4204d
model=gpt-5.5
measurement_governance=on
proposal_context_arms=full,no-measurement-diagnostics,minimal-research-context
repeats=3
rounds=8
time_limit_sec=30
agentic_session_timeout_sec=900
disable_early_stop=true
execution_order=rep01:full,no-measurement-diagnostics,minimal-research-context;rep02:minimal-research-context,full,no-measurement-diagnostics;rep03:no-measurement-diagnostics,minimal-research-context,full
caveat=free_running_llm_trajectories_observational_only;postrun_fixed_candidate_replay_required;branch_code_sequence_join_is_report_fallback
```

Manifest generation:

```bash
ROOT=/home/clawd/research/scion-experiments/v04-phase5-warehouse-context-ablation-formal-3x3-8r-20260612T114219Z-claw
REPO=/home/clawd/research/or-autoresearch-agent
ACC="$ROOT/postrun_acceptance"
export PYTHONPATH="$REPO/scion"

for rep in rep01 rep02 rep03; do
  for arm in full no-measurement-diagnostics minimal-research-context; do
    python -m scion.cli.main report proposal-trajectory-manifest \
      --campaign-dir "$ROOT/$rep/$arm/campaign" \
      --observed-control-arm on \
      --output "$ACC/manifests/${rep}_${arm}.proposal_trajectory_manifest.v1.json"
  done
done
```

## V3 Boundary And Report Guardrails

The postrun analysis preserves the v3 boundary:

- LLM prompts, prompt manifests, proposal trajectories, branch lessons, and
  context-ablation fingerprints are tainted proposal/report material.
- Decision and promotion evidence comes from deterministic protocol/status
  artifacts, not from prompt text or trajectory summaries.
- Generated manifests and compares are report-only and non-mutating.

All nine proposal-trajectory manifests set:

- `report_only=true`
- `decision_features_excluded=true`
- `comparison_is_decision_input=false`
- `campaign_state_mutated=false`
- `scheduler_state_mutated=false`
- `promotion_state_mutated=false`
- `raw_prompt_excluded=true`
- `raw_response_excluded=true`
- `patch_body_excluded=true`

All nine compares set `observational_only=true` and
`llm_deterministic_replay=false`.

Prompt manifest loading was complete in every manifest:

| Arm | Prompt refs loaded |
| --- | ---: |
| `full` | 117 / 117 |
| `no-measurement-diagnostics` | 132 / 132 |
| `minimal-research-context` | 139 / 139 |

Context-arm fingerprints were unmixed in all nine manifests. Unknown traces
were code/tool-selection traces whose prompt manifests do not carry hypothesis
context-ablation metadata.

A recursive generated-artifact key scan found no raw prompt/response, message,
code-content, patch-content, diff/body/content payload, raw metrics, BKS/gap,
A/A pair evidence, or `DecisionFeatures` payload leakage beyond exclusion flag
field names such as `patch_body_excluded`.

## Cell Results

| Cell | Effective rows | Protocol rows | Formal artifacts / screened | Verification failures | LLM H/C/T | Fresh replay | Stages | Champion | Stop |
| --- | ---: | ---: | ---: | ---: | --- | --- | --- | ---: | --- |
| `rep01/full` | 8 | 7 | 7 / 7 | 1 | 16/9/23 | `not_selected_no_pending` / 0 | screening 7 | 1 | max rounds |
| `rep01/no-measurement-diagnostics` | 8 | 7 | 7 / 7 | 1 | 16/8/20 | `not_selected_no_pending` / 0 | screening 7 | 1 | max rounds |
| `rep01/minimal-research-context` | 8 | 9 | 8 / 8 | 0 | 15/8/23 | `selected_succeeded` / 1 | screening 9 | 1 | max rounds |
| `rep02/full` | 8 | 8 | 7 / 8 | 0 | 13/7/19 | `not_selected_no_pending` / 0 | screening 8 | 1 | max rounds |
| `rep02/no-measurement-diagnostics` | 8 | 8 | 7 / 7 | 0 | 13/7/20 | `not_selected_no_pending` / 0 | screening 7, validation 1 | 1 | max rounds |
| `rep02/minimal-research-context` | 8 | 10 | 8 / 8 | 0 | 16/8/24 | `selected_succeeded` / 2 | screening 10 | 1 | max rounds |
| `rep03/full` | 8 | 8 | 5 / 6 | 0 | 10/6/14 | `not_selected_no_pending` / 0 | screening 6, validation 1, frozen 1 | 1 | max rounds |
| `rep03/no-measurement-diagnostics` | 8 | 9 | 7 / 7 | 1 | 16/8/24 | `selected_succeeded` / 2 | screening 9 | 1 | max rounds |
| `rep03/minimal-research-context` | 8 | 10 | 8 / 8 | 0 | 15/8/22 | `selected_succeeded` / 2 | screening 10 | 1 | max rounds |

All nine cells were valid and complete. The `failure` reports had empty
breakdowns. The `verification_failure_consumed_candidates` counter is still
important for accounting because consumed verification failures can explain
effective-round/formal-artifact differences.

## Prompt Signal Density

Aggregate prompt block-family token estimates:

| Arm | Total tokens | Research signal | General | Governance | Tool selection | Tool observation | Source context |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `full` | 1,629,864 | 282,217 / 17.32% | 595,922 / 36.56% | 66,711 / 4.09% | 496,534 / 30.46% | 123,977 / 7.61% | 1,602 / 0.10% |
| `no-measurement-diagnostics` | 1,837,975 | 335,340 / 18.25% | 650,897 / 35.41% | 78,028 / 4.25% | 572,981 / 31.17% | 138,062 / 7.51% | 1,404 / 0.08% |
| `minimal-research-context` | 1,521,974 | 58,345 / 3.83% | 661,207 / 43.44% | 66,860 / 4.39% | 588,302 / 38.65% | 142,925 / 9.39% | 1,184 / 0.08% |

The minimal arm materially harmed useful research signal density. Its pooled
`research_signal` share fell to `3.83%`, and repeat-level shares stayed low
at `3.64%`, `3.65%`, and `4.22%`. In hypothesis prompts specifically,
research-signal share was `9.18%`, compared with `35.27%` for full.

The no-measurement arm did what it was supposed to do: measurement diagnostics
were absent from `45/45` unique hypothesis prompt manifests while compact
research, cross-branch maps, branch lessons, branch history, global failures,
and sibling-branch context remained present in `45/45`. Its hypothesis
research-signal share was `36.48%`, slightly above full.

The minimal arm was therefore too blunt. It retained measurement diagnostics
in `46/46` hypothesis prompts, but removed cross-branch maps, branch lessons,
and branch-history context in `0/46`; that appears to be the main reason
research signal density collapsed.

## Research Efficiency

Aggregate protocol/research results by arm:

| Arm | Validation/frozen reach | Promotions | Screening case WR | Screening pair WR | Branch depth | Formal candidate shape |
| --- | --- | ---: | ---: | ---: | --- | --- |
| `full` | queue-validate 2; actual validation 1; frozen 1 | 0 | 35/162 = 0.216 | 113/324 = 0.349 | avg 2.18, max 4 | 19 formal: 5 create, 14 modify; 10 vehicle, 9 order |
| `no-measurement-diagnostics` | queue-validate 1; actual validation 1; frozen 0 | 0 | 28/170 = 0.165 | 97/340 = 0.285 | avg 2.00, max 4 | 21 formal: 8 create, 13 modify; 15 vehicle, 6 order |
| `minimal-research-context` | no validation/frozen | 0 | 28/230 = 0.122 | 110/460 = 0.239 | avg 2.07, max 4 | 24 formal: 14 create, 10 modify; 19 vehicle, 5 order |

The full arm showed the best evidence quality: strongest aggregate screening
rates, fewer LLM/tool-selection calls in the strongest repeat, no
fresh-runtime replay rows, and the only frozen-stage row.

The no-measurement arm preserved enough research context to reach validation
once, but it did not reach frozen and showed weaker aggregate screening signal
than full.

The minimal arm generated more formal candidate artifacts and more
vehicle-level `create_new` breadth, but that breadth did not translate into
validation/frozen reach. It also triggered `fresh_runtime_replay` rows in all
three repeats, adding non-counted protocol work without improving evidence
quality.

The strongest single trajectory was `rep03/full`.
`cost_vacate_order_transfer` reached validation and frozen. Validation was
strong at the protocol row level: `5/5` case wins, `14/15` pair wins, and
complete high-confidence runtime evidence. Frozen completed cleanly with no
pair failures and `3/4` case wins, `8/12` pair wins, but the frozen gate
recorded `FROZEN_FAIL_HIERARCHICAL_UNCERTAIN`, so it correctly did not promote.

## Branch Depth And Attribution

Replayable formal-candidate sequences show that full context supported deeper
same-branch/same-mechanism follow-up in two repeats:

- `rep01/full`: one branch repeated 4 times on
  `vacancy_creation_order_move`.
- `rep02/full`: one branch repeated 4 times on
  `split_preserving_cost_fill`.
- `rep03/full`: one branch repeated 2 times on
  `vacate_redundant_vehicle`, then a later candidate reached validation/frozen.

No-measurement also showed meaningful continuity:

- `rep02/no-measurement-diagnostics`: one branch repeated 4 times on
  `split_preserving_gap_fill`.
- `rep03/no-measurement-diagnostics`: one branch repeated 3 times on
  `subcategory_bucket_consolidate`.

Minimal mostly produced shorter branch streaks, plus one 3-repeat branch in
`rep03/minimal-research-context`. It did not produce validation/frozen reach.

All formal-candidate joins in the manifests use the conservative
`branch_code_sequence` fallback. This is acceptable for report-only audit
fingerprints, but it remains weaker than direct persisted `session_id`,
`request_id`, or `hypothesis_id` linkage in formal candidate rows.

## Accounting Caveats

Formal candidates, screening rows, and effective protocol rounds must not be
used interchangeably:

- `formal_candidates/index.jsonl` is a replayable patch-artifact subset.
- Validation and frozen rows count as protocol rows but are not new screening
  candidate artifacts.
- Verification-only consumed failures can count toward effective rounds without
  producing formal candidate artifacts.
- Fresh-runtime replay rows are non-counted extras. They inflated protocol row
  totals in the minimal arm and in `rep03/no-measurement-diagnostics`; they
  should stay out-of-band for Phase 5 accounting.

`rep03/full` illustrates the distinction: it completed 8 effective protocol
rows, with 6 screening rows, 1 validation row, 1 frozen row, and 5 replayable
formal candidate artifacts.

## Acceptance

Accepted as Phase 5 proposal-context ablation evidence:

- 9/9 cells exited 0 and were valid complete runs.
- All arms used the intended warehouse production protocol/split/seeds,
  `gpt-5.5`, 8 rounds, 30s uniform runtime cap, and
  `measurement_governance=on`.
- Proposal trajectory manifests and compares are report-only, non-mutating,
  and free of raw prompt/response/patch/Decision payload leakage.
- Context-arm fingerprints were unmixed and prompt manifests were fully loaded.
- Subagent read-only analyses independently checked prompt/context signal
  density and protocol/branch/runtime outcomes after reading the v3 blueprint.

Not accepted as a causal governance-value conclusion:

- Free-running LLM trajectories diverged.
- The comparisons are `observational_only=true`.
- No fixed trajectory replay or explicit control-pair key exists for these
  prompt-context arms.
- No arm promoted; the strongest candidate failed frozen.

## Phase 5 Implication

This run supports the next v0.4 design decision:

- Do not use `minimal-research-context` as the default compression strategy.
  It removes the branch/cross-branch research memory that appears necessary for
  useful research.
- Preserve a `no-measurement-diagnostics` style arm for isolating the value of
  measurement diagnostics while keeping branch/cross-branch research context
  constant.
- Keep full context as the current best warehouse research-efficiency baseline.
- Before a stronger governance claim, add or pre-register a trajectory-aware
  control: fixed proposal trace replay, explicit control-pair keys, or another
  design that distinguishes context-governance effects from free-running LLM
  trajectory divergence.

CVRP remains excluded from formal governance-value conclusions until its
measurement power improves; the latest 8-seed A/A check still measured MDE
`9.6` against `practical_delta_screen=2.0`.
