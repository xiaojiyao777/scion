# CVRP Baseline-Strength Phase C Postrun

*Date: 2026-06-15*
*Branch: `codex/v04-evidence-repair-plan`*
*Accepted run commit: `d0bd95f`*
*Postrun sync/status commit: `a70b160`*
*Model: local `gpt-5.5`*

## Purpose

Phase C is the long-run follow-up to the CVRP baseline-strength contrast. It
tests whether the repaired v0.4 framework can carry CVRP research beyond the
Phase B screening-only result, especially on the copied ALNS-only research
surface where Phase A measured a lower A/A MDE and Phase B produced a final-row
validation-ready signal.

The v3 boundary still governs interpretation. MDE, BKS/gap/headroom,
ALNS/VNS telemetry, branch trajectories, and prompt/context analysis are
postrun research diagnostics only. Promotion decisions remain limited to
Contract, Verification, Protocol, safe feature extraction, and deterministic
Decision over `DecisionFeatures`.

## Inputs

- Phase C run root:
  `/home/clawd/research/scion-experiments/v04-cvrp-baseline-strength-phaseC-longrun-20260614T174532Z`
- Accepted postrun root:
  `/home/clawd/research/scion-experiments/v04-cvrp-baseline-strength-phaseC-longrun-20260614T174532Z/postrun_acceptance`
- Accepted cells: corrected WSL-only six-cell matrix,
  `rep01/rep02/rep03 x alns_vns/alns_only`.
- Protocol shape: Phase A 8-case/8-seed split, repaired Phase C staged gate,
  `measurement_governance=on`,
  `proposal_context_ablation=compact-measurement-diagnostics`, 16 effective
  rounds, and `SCION_STAGE_TRANSITION_DRAIN_LIMIT=4`.
- Phase A MDE anchors:
  - ALNS+VNS: `9.6` raw `total_distance`
  - ALNS-only: `4.65` raw `total_distance`

The early mixed server/WSL launch and the canary-only WSL cells are excluded
from accepted evidence. The accepted rerun used WSL-native `config_wsl/`,
`/home/xjy-ubuntu/research/or-autoresearch-agent/vrp` as the safe data root,
and WSL conda Python.

## Acceptance

All six corrected WSL cells completed with `validity=valid` and
`effective_rounds=16`. Each accepted cell had recorded formal artifacts and
CVRPLIB metrics, not canary-only evidence.

`launch_env_validation.csv` reports `ok=false` only because the postrun checker
still expected the initial portable launcher commit `354a941`, while the
accepted all-WSL rerun launched from `d0bd95f` after postrun tooling and WSL
rerun preparation. This is a provenance/checker expectation drift to document,
not an evidence-invalidating failure: config paths, WSL Python, protocol/split/
seed files, measurement governance, context arm, rounds, drain limit, and
formal CVRPLIB metrics match the corrected Phase C design.

## Formal Outcome

Arm totals from `postrun_acceptance/sql/arm_aggregates.csv`:

| arm | cells | effective rounds | screening rows | validation rows | frozen rows | promoted cells | rows >= arm MDE | max effect/MDE |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| ALNS+VNS | 3 | 48 | 45 | 3 | 0 | 0 | 0 | 0.677 |
| ALNS-only | 3 | 48 | 42 | 4 | 4 | 0 | 6 | 10.968 |

Per-cell reach from `postrun_acceptance/sql/reach_drain.csv`:

| repeat | arm | validation rows | frozen rows | promote decisions | champion version |
| --- | --- | ---: | ---: | ---: | ---: |
| rep01 | ALNS-only | 2 | 2 | 0 | 1 |
| rep02 | ALNS-only | 1 | 2 | 0 | 1 |
| rep03 | ALNS-only | 1 | 0 | 0 | 1 |
| rep01 | ALNS+VNS | 1 | 0 | 0 | 1 |
| rep02 | ALNS+VNS | 2 | 0 | 0 | 1 |
| rep03 | ALNS+VNS | 0 | 0 | 0 | 1 |

No champion promotion occurred. Each accepted cell retained a single champion
version (`1`), `promote_decisions_total=0`, and the per-cell summaries report
`champion_promotions=0`.

## MDE Interpretation

The ALNS-only arm produced measurable intermediate signals relative to its own
Phase A MDE:

- rep01 ALNS-only queued frozen at validation with `median_delta=51.0`,
  `CI=[14.25, 319.5]`, and `effect_to_mde=10.968`, then failed at frozen with
  `median_delta=4.0` and `effect_to_mde=0.860`.
- rep02 ALNS-only queued frozen at validation with `median_delta=20.75`,
  `CI=[13.0, 272.5]`, and `effect_to_mde=4.462`, then failed at frozen with
  `median_delta=0.0` and `effect_to_mde=0.0`.
- rep03 ALNS-only reached validation once but did not reach frozen.

The canonical ALNS+VNS arm did not produce a row above its own MDE. Its best
validation row was rep02 with `median_delta=6.5` and `effect_to_mde=0.677`,
below the ALNS+VNS MDE of `9.6`.

Therefore the main formal outcome is not "the gate blocked everything". The
repaired protocol can reach validation and frozen, especially under the weaker
ALNS-only research surface. The failure is downstream: the strongest ALNS-only
signals did not generalize through frozen, and canonical ALNS+VNS signals
remained below measured power.

## Validation-to-Frozen Runtime Check

The two ALNS-only validation positives are not identical to a generic "agent
cannot research VRP" failure. They show a size split:

- validation cases were `30/45/60s` protocol buckets and produced complete
  paired evidence. The strongest ALNS-only validation rows improved median
  BKS-gap from about `5.21%` for champion evidence to `4.48%-4.63%` for
  candidate evidence.
- frozen cases are all X-family holdouts with `60/90/120s` protocol buckets.
  In the two ALNS-only frozen rows, `X-n573-k30`, `X-n641-k35`, and
  `X-n1001-k43` produced `0` valid paired comparisons across `18` attempted
  pairs; all were timeout/shared-process failures. `X-n401-k29` also had a
  `1/3` seed timeout in each frozen row.
- the failed 501+ bucket was therefore not measured as "no improvement"; it was
  not measured by the current runner/protocol combination.

A no-LLM ALNS-only champion runtime smoke was run after closeout at
`/home/clawd/research/scion-experiments/v04-cvrp-runtime-budget-smoke-20260615`.
It replayed `X-n401-k29` and `X-n573-k30`, seed `61`, at current and 2x nominal
budgets:

| case | nominal budget | wall elapsed | distance | BKS gap | ALNS iterations | best delta | stop |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| X-n401-k29 | 90s | 115.9s | 68673 | 3.81% | 2 | 0 | time_limit |
| X-n401-k29 | 180s | 171.4s | 68673 | 3.81% | 6 | 0 | completed |
| X-n573-k30 | 120s | 188.5s | 52495 | 3.60% | 1 | 0 | time_limit |
| X-n573-k30 | 240s | 211.4s | 52495 | 3.60% | 2 | 0 | completed |

This smoke shows two distinct issues. First, the Phase C runner's fixed grace
killed large-X solver calls before the baseline could emit even a no-improvement
result, so frozen evidence completeness was invalid for X501+. Second, 2x
nominal budget did not improve these sampled baseline results; the large-X
search loop has very low best-update density, so simply running another long
LLM campaign is not justified without a targeted runtime curve and mechanism
redesign.

## Branch Behavior

The run is not a pure one-off search. Every cell produced at least depth-2
branch chains. ALNS+VNS showed the deepest same-mechanism chains:

- rep01 ALNS+VNS: max depth 5, max same-mechanism chain 5.
- rep02 ALNS+VNS: max depth 5, max same-mechanism chain 5.
- rep01 ALNS-only: max depth 3, max same-mechanism chain 3.
- Other cells were mostly depth 2.

This partially satisfies the Phase 4 effective-research requirement for
within-branch continuation. It does not yet prove mature branch research.
Mechanism family remains concentrated in `solver_design`. A later report-only
trajectory projection narrowed the immediate evidence gap: across the six
accepted cells, structured `branch_lesson_usage` was recoverable for `125/128`
agentic sessions, with pooled counts `avoided=205`, `contrasted=175`,
`preserved_same_branch=53`, `borrowed=15`, and
`rejected_weak_positive=56`. This means the remaining problem is not simply
"no structured branch lessons were emitted." The unresolved research question
is whether those lessons changed later mechanism choices in a useful way; Phase
C still does not prove that.

## Prompt and Context

`compact-measurement-diagnostics` improved signal density compared with the
earlier full measurement block, but it did not make the prompts small. Sampled
Phase C manifests show:

- hypothesis prompts still around 120k-180k visible characters, with later
  branch-aware samples around 179k characters;
- code prompts around 121k characters in the sampled code session;
- the target/current source was preserved in code phase, including full current
  source visibility for `policies/baseline_modules/local_search.py`;
- source visibility risk is currently lower than research-signal overload
  risk.

The remaining issue is composition. Later hypothesis prompts can contain a
large `cross_branch_research_map` and a truncated
`branch_lesson_usage_context`, while compact measurement/opportunity signals
are bounded to much smaller sections. Across the six accepted cells,
`prompt_context.csv` records 76 compact-research truncations and 62
branch-lesson truncations. Code-stage source visibility held in the inspected
sample, but the agent still receives a large amount of framework, rule, editing,
and interface material around the actual research intent.

## Interpretation

Phase C is valid and useful evidence, but it does not close the CVRP effective
research gate.

Supported conclusions:

- The staged CVRP gate repair and 16-round design improved reach beyond Phase B.
- The ALNS-only copied research surface is more measurable than canonical
  ALNS+VNS: it reached validation in all three repeats and frozen in two.
- The framework no longer simply dies at screening; validation/frozen paths are
  exercised under formal protocol.
- Fresh-runtime replay is not the main blocker in this run: stage-transition
  drain did not execute because no eligible pending validation/frozen work
  remained at stop. Large-X timeout/evidence completeness is a separate blocker
  for frozen interpretation.

Unsupported conclusions:

- Scion has not yet shown a formal CVRP promotion in Phase C.
- Phase C does not prove effective improvement against the canonical ALNS+VNS
  baseline.
- Phase C does not prove branch lessons are being effectively used. New
  report-only projection shows most sessions emitted structured lesson-use
  objects, but the campaign still failed to turn them into robust VRP
  mechanisms.
- More rounds alone are not justified as the next step until the validation to
  frozen collapse, large-X runtime evidence, and prompt/lesson use are
  explained.

## Next Work

Before another long CVRP campaign, the next v0.4 work should be targeted:

1. Inspect the two ALNS-only candidates that crossed MDE at validation and
   collapsed at frozen. Compare patch intent, case-level behavior, holdout
   composition, runtime-incomplete rows, and whether the positive signal was
   size/family overfit.
2. Treat report-only lesson-use accounting as a completed diagnostic guardrail,
   not a new framework-repair theme. The main bottleneck is now VRP mechanism
   research quality: the agent must convert branch lessons into better
   large-X-aware mechanism follow-up.
3. Run a small no-LLM runtime curve before any new LLM campaign: current/2x/4x
   budgets on `X-n401`, `X-n573`, `X-n641`, and `X-n1001` across the frozen
   seeds, with objective, timeout, BKS gap, ALNS iteration count, and
   best-update trace. This is problem-owned measurement work, not a Decision
   feature. Tooling for this is now available through
   `scion/tools/cvrp_runtime_curve.py`, and CVRP solver-design runtime emits
   optional bounded best-update trace/summary telemetry for new replays.
4. Tighten hypothesis-context composition so branch lessons, same-mechanism
   continuation state, per-case opportunity summaries, and mechanism rankings
   survive without long generic rule payloads. Preserve full target/current
   source in code phase.
5. Treat ALNS-only as a useful diagnostic research surface, not a canonical
   baseline replacement.
6. Keep CVRP out of formal governance-value claims until it either promotes or
   produces a clearly accepted research insight above its measurement floor.
