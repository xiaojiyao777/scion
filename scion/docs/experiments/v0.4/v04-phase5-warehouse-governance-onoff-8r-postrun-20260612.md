# v0.4 Warehouse Measurement-Governance ON/OFF 8R Shakedown Postrun

*Date: 2026-06-12*
*Branch: `codex/v04-evidence-repair-plan`*
*Launch commit: `f604e81`*
*Status: valid shakedown; not a causal governance-value conclusion*

## Summary

The first warehouse measurement-governance ON/OFF shakedown completed cleanly.
Both arms were valid and complete, both consumed the requested eight effective
protocol rounds, and both reached the full screening -> validation -> frozen ->
promotion path to champion v2.

This validates the mechanics of the new `measurement_governance` switch and
shows that the repaired warehouse evidence path can still promote. It does not
prove that measurement-aware governance is better than record-only governance.
The ON and record-only arms generated different LLM trajectories and promoted
different `operators/merge_vehicles.py` patches, so the terminal difference
cannot be attributed causally to the governance switch.

## Runs

Common launch controls:

- Problem: `scion/problems/warehouse_delivery/problem.yaml`
- Protocol: `scion/problems/warehouse_delivery/protocol_prod.yaml`
- Split: `scion/problems/warehouse_delivery/split_manifest_prod.yaml`
- Seeds: `scion/problems/warehouse_delivery/seed_ledger.yaml`
- Model: local `gpt-5.5`
- Rounds: `8`
- Runtime CLI cap: `--time-limit-sec 30`
- Agentic timeout: `--agentic-session-timeout-sec 900`
- Other controls: `--disable-early-stop --agentic-proposal`

ON arm:

`/home/clawd/research/scion-experiments/v04-phase5-governance-warehouse-on-pilot-8r-gpt55-20260612T013119Z-claw`

- `--measurement-governance on`
- Wrapper exit status: `0`
- Ended at: `2026-06-12T02:22:45Z`
- Campaign status: `valid`, `complete`

Record-only/OFF arm:

`/home/clawd/research/scion-experiments/v04-phase5-governance-warehouse-record_only-pilot-8r-gpt55-20260612T013119Z-claw`

- `--measurement-governance record-only`
- Wrapper exit status: `0`
- Ended at: `2026-06-12T02:23:30Z`
- Campaign status: `valid`, `complete`

The arms matched on the outer experiment configuration: commit, problem,
protocol, split, seed ledger, round budget, model, runtime CLI cap, and agentic
timeout. The formal replay identity also matched: problem spec hash
`138b08aa...`, split manifest hash `c1d77b2...`, seed ledger hash
`85a89469...`, and protocol version `3.1-prod`.

## Counters

Both arms finished with the same top-level evidence shape:

| Arm | Effective rounds | Screening rows | Validation rows | Frozen rows | Champion |
| --- | ---: | ---: | ---: | ---: | ---: |
| ON | 8/8 | 6 | 1 | 1 | v2 |
| Record-only | 8/8 | 6 | 1 | 1 | v2 |

Both arms had:

- `formal_screened_candidates=6`
- `effective_protocol_rounds=8`
- `screening_protocol_results=6`
- `validation_protocol_results=1`
- `frozen_protocol_results=1`
- `last_stop_reason=max_rounds_exhausted`

The LLM paths had already diverged: both arms wrote 32 LLM traces, but ON had
`9` hypothesis, `18` tool-selection, and `5` code traces, while record-only had
`10` hypothesis, `17` tool-selection, and `5` code traces.

## Promoted Candidates

ON promoted:

- Candidate: `6c37eca6-58ad-4f31-9cc9-42993b43473b`
- Branch: `1cb5c4cd-e4f6-4e99-ad92-1765021fad4a`
- Mechanism: `split_safe_cost_merge`
- Target: `operators/merge_vehicles.py`
- Screening initial: cases `3/0/3`, pairs `7/0/5`, median `950`,
  CI `[0, 9775]`, expanded.
- Screening expanded: cases `8/0/6`, pairs `19/0/9`, median `950`,
  CI `[400, 4500]`, queued validation.
- Validation: cases `5/0/0`, median `33800`, CI `[23100, 39100]`.
- Frozen: cases `4/0/0`, median `33600`, CI `[24600, 40800]`.

Record-only promoted:

- Candidate: `def632bf-3bfb-480d-83b9-1d4548ff23ca`
- Branch: `bead7684-c1f7-4fc3-bf68-fd33582c3f0b`
- Mechanism: `best_of_k_merge`
- Target: `operators/merge_vehicles.py`
- Screening initial: cases `3/0/3`, pairs `7/0/5`, median `950`,
  CI `[0, 8525]`, expanded.
- Screening expanded: cases `7/0/7`, pairs `17/0/11`, median `950`,
  CI `[275, 4800]`, queued validation with
  `SCREENING_EXPAND_EXHAUSTED_BORDERLINE`.
- Validation: cases `5/0/0`, median `16500`, CI `[14000, 22500]`.
- Frozen: cases `4/0/0`, median `18350`, CI `[11000, 25900]`.

Both winners targeted `operators/merge_vehicles.py`, and both replaced random
merge behavior with bounded, compatibility-aware merge logic. The patches were
not identical, so the run should be treated as a successful shakedown and a
source of follow-up candidate ideas, not as a paired candidate-level
governance ablation.

## Runtime Interpretation

The protocol evidence did not run each warehouse solver call for 300s. The
problem default still declares `solver.time_limit_sec: 300`, but both run
commands passed `--time-limit-sec 30`, and protocol metrics report
`time_limit_policy.resolved_unique_sec=[30]`.

The observed 300s path came from asynchronous weight optimization, not from the
counted protocol evidence. Both arms reported weight optimization as cancelled
at final wait with zero completed evaluations and no `weight_optimizations`
rows in SQLite. It did not contribute promotion evidence.

Validation and frozen runtime evidence used fresh champion rows with cache hits
`0` and high runtime confidence. Screening expansion could contain cached
champion runtime rows, so screening runtime should be read as audit/proposal
guidance rather than standalone speed evidence.

## Governance Switch And Context

The switch took effect:

- ON status reported `measurement_governance="on"`.
- Record-only status reported `measurement_governance="record_only"`.
- ON promoted hypothesis prompts contained `problem_measurement_diagnostics`
  at about `1658` tokens.
- Record-only promoted hypothesis prompts did not contain
  `problem_measurement_diagnostics`.

Record-only is not a complete "no governance signal" arm. It still exposes
objective opportunity, runtime feedback, cross-branch research map, branch
memory, and general rule/governance blocks. This matches the implemented
record-only contract, but it means future claims must distinguish
"measurement diagnostics off" from "all governance/research shaping off."

Prompt density on promoted hypothesis manifests:

| Arm | Governance rules | Measurement diagnostics | Problem opportunity | Champion/source | Cross-branch history | Branch memory |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| ON | 10.6% | 2.1% | 0.9% | 21.6% | 19.5% | 7.1% |
| Record-only | 13.0% | 0.0% | 1.0% | 23.0% | 23.7% | 7.0% |

Code-phase manifests preserved direct research-object visibility in both arms:
`current_champion_research_code` was about `16970` tokens and
`approved_target_file_current_content` about `2665` tokens. No evidence showed
code-phase compression hiding champion, current branch, or target source.

Decision boundary checks held. SQLite `decision_features_json` contained
structured protocol metrics and enums, with no raw A/A rows, raw BKS/gap
details, LLM text, prompt ratios, or raw cross-branch material.

## Branch Research Trajectory

Both arms improved on the Phase 4 warehouse no-promotion outcome by reaching
validation, frozen evidence, and promotion. They did not yet prove the stronger
v3 research ideal of a branch direction becoming better through multiple
hypothesis edits before promotion.

ON branch shape:

- `subcategory_pack_upgrade`: `create_new -> modify -> modify`, stale/no
  effect.
- `split_preserving_evacuate`: clean fork, abandoned on runtime/regression
  evidence.
- `split_safe_cost_merge`: first hypothesis on a fresh branch, then protocol
  depth through screening expansion, validation, frozen, and promotion.

Record-only branch shape:

- `subcategory_block_repack`: `create_new -> modify`, stale/no effect.
- `safe_gap_fill`: abandoned on runtime/saturation evidence.
- `best_of_k_merge`: first hypothesis on a fresh branch, then protocol depth
  through screening expansion, validation, frozen, and promotion.
- `compatible_repack_merge`: post-promotion branch abandoned.

Branch-level conclusion:

- Protocol depth recovered: promoted candidates were not one-row accidents.
- Hypothesis depth for the promoted branch did not recover: both promoted
  candidates were first hypotheses on their branches.
- Same-mechanism follow-up exists elsewhere, but it did not produce the
  promoted candidate.
- `parent_hypothesis_id` was empty, so same-branch ancestry is inferable from
  branch IDs and scheduler records but not explicitly durable enough for
  robust audits.

## Findings

1. The measurement-governance switch is operationally usable.
2. Warehouse production saferoot remains promotion-capable after the v0.4
   measurement/readiness/context repairs.
3. This shakedown is not a valid causal ON/OFF conclusion because candidate
   generation diverged.
4. Record-only suppresses measurement diagnostics, but still includes other
   research-shaping governance signals.
5. The code phase preserved source visibility; context compression did not hide
   the research object code in the inspected promoted sessions.
6. Branch experience is proposal-visible and Decision-excluded, but durable
   parent lineage is weak.
7. The record-only winner used a borderline expanded screening path with
   `SCREENING_EXPAND_EXHAUSTED_BORDERLINE`; this path needs explicit review
   before formal governance experiments.
8. ON reported a fresh-runtime replay pressure inconsistency: summary said no
   replayable pressure candidate, while detail indicated a materializable
   pressure candidate that the scheduler did not replay. This did not affect
   the winner, but it is a replay-closure debt.

## Required Follow-Up

Before treating governance ON/OFF as evidence of Scion value:

- Run a fixed-candidate replay or fixed-order comparison where the same patches
  are evaluated under ON and record-only.
- Decide whether record-only means "measurement diagnostics off" or "all
  governance opportunity signals off"; if the latter, add a stricter ablation
  mode.
- Add manifest assertions: ON must include measurement diagnostics;
  record-only must suppress them; both arms must preserve full champion and
  target-source visibility in code phase.
- Add `measurement_governance` to `campaign_summary.json`, not only status and
  launch metadata.
- Review `SCREENING_EXPAND_EXHAUSTED_BORDERLINE` semantics and whether it is
  allowed to queue validation.
- Repair or clarify fresh-runtime replay drain closure when pressure candidates
  are materializable but scheduler selection does not replay them.
- Add durable parent hypothesis lineage for same-branch follow-up.
- Track branch-level acceptance metrics: promoted-branch hypothesis depth,
  protocol depth, same-mechanism follow-up rate, lesson reuse satisfaction,
  explicit parent lineage rate, and terminal lifecycle reason coverage.

## Evidence Reviewed

Three read-only subagent audits inspected:

- Protocol, DB, metrics, formal candidate artifacts, promotion dossiers, and
  runtime/weight-opt paths.
- Prompt manifests, self-check previews, LLM traces, promoted candidate diffs,
  and `DecisionFeatures` contents.
- Branch records, hypothesis records, experiment events, lifecycle transitions,
  lesson usage, and Phase 4 warehouse trajectory comparison.

Main evidence paths:

- `campaign/status.json`
- `campaign/campaign_summary.json`
- `campaign/scion.db`
- `campaign/artifacts/formal_candidates/index.jsonl`
- `campaign/artifacts/promotions/champion_v2_promotion_dossier.json`
- Promoted ON metrics: `40199ae6...`, `b89d7a5e...`, `c58d5ec8...`
- Promoted record-only metrics: `ed6321db...`, `e39c5d9f...`,
  `0532c940...`
