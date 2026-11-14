# v0.4 Warehouse Proposal Context Ablation Shakedown

*Date: 2026-06-12*
*Branch: `codex/v04-evidence-repair-plan`*
*Executor commit: `2a88e86`*
*Status: valid 3-arm shakedown; trajectory attribution repaired; observational only*

## Summary

The first warehouse proposal-context ablation shakedown completed cleanly. All
three free-running arms used `measurement_governance=on`, warehouse production
protocol/split/seeds, local `gpt-5.5`, `--rounds 4`, and a uniform
`--time-limit-sec 30`.

The ablation switch behaved as intended:

- `full` kept measurement diagnostics and broader research context.
- `no-measurement-diagnostics` removed prompt-visible
  `problem_measurement_diagnostics` while preserving broader research context.
- `minimal-research-context` preserved compact measurement diagnostics while
  hiding broader branch/cross-branch/research history blocks.

The run is useful shakedown evidence, not a governance-value conclusion. LLM
trajectories diverged, no arm promoted, and the proposal trajectory comparison
artifacts are explicitly report-only and observational-only.

## Artifacts

Clean run root:

`/home/clawd/research/scion-experiments/v04-phase5-proposal-context-ablation-warehouse-3arm-20260612T072730Z-claw`

Failed environment probe/run root, excluded from analysis except as launch
hygiene evidence:

`/home/clawd/research/scion-experiments/v04-phase5-proposal-context-ablation-warehouse-3arm-20260612T072456Z-claw`

The failed attempt inherited an invalid `SCION_API_KEY` and produced LLM 401
errors before it was stopped. The clean run used a live proxy probe with
`SCION_BASE_URL=http://127.0.0.1:8080`, `SCION_MODEL=gpt-5.5`, and a corrected
proxy key.

Generated report artifacts:

- `full-proposal-trajectory-manifest.v1.json`
- `no-measurement-diagnostics-proposal-trajectory-manifest.v1.json`
- `minimal-research-context-proposal-trajectory-manifest.v1.json`
- `full-vs-no-measurement-diagnostics-comparison.v1.json`
- `full-vs-minimal-research-context-comparison.v1.json`

Follow-up report-attribution repair validation regenerated the manifests and
comparisons against the same source campaigns under:

`/tmp/scion-proposal-context-ablation-report-fix`

Launch shape:

```bash
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion \
SCION_MODEL=gpt-5.5 \
SCION_BASE_URL=http://127.0.0.1:8080 \
SCION_API_KEY=<proxy-key> \
python -m scion.cli.main run \
  --campaign-dir <run-root>/<arm>/campaign \
  --problem /home/clawd/research/or-autoresearch-agent/scion/problems/warehouse_delivery/problem.yaml \
  --protocol /home/clawd/research/or-autoresearch-agent/scion/problems/warehouse_delivery/protocol_prod.yaml \
  --split /home/clawd/research/or-autoresearch-agent/scion/problems/warehouse_delivery/split_manifest_prod.yaml \
  --seeds /home/clawd/research/or-autoresearch-agent/scion/problems/warehouse_delivery/seed_ledger.yaml \
  --rounds 4 \
  --time-limit-sec 30 \
  --measurement-governance on \
  --proposal-context-ablation <full|no-measurement-diagnostics|minimal-research-context> \
  --disable-early-stop \
  --agentic-proposal \
  --agentic-session-timeout-sec 900
```

## Run Results

| Arm | Exit | Duration sec | Status | Steps | Formal candidates | Last result |
| --- | ---: | ---: | --- | ---: | ---: | --- |
| `full` | 0 | 743 | `max_rounds_exhausted` | 4 | 3 | heavy verification failed before protocol row |
| `no-measurement-diagnostics` | 0 | 1168 | `max_rounds_exhausted` | 5 | 4 | fresh-runtime replay closure, parked lineage |
| `minimal-research-context` | 0 | 930 | `max_rounds_exhausted` | 5 | 4 | fresh-runtime replay closure, parked lineage |

No arm promoted beyond champion v1. The two non-full arms both triggered a
non-counted `fresh_runtime_replay` after a runtime tie, so they show
`n_steps=5` even though the requested research budget was four rounds.

Compact campaign-summary counters:

| Arm | Proposals | Counted experiments | Screened experiments | Runtime diagnostics | Fresh champion required | Runtime aggregate excluded | Low cached runtime | Input tokens | Output tokens |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `full` | 4 | 3 | 3 | 0 | 0 | 0 | 1 | 313184 | 18492 |
| `no-measurement-diagnostics` | 4 | 4 | 5 | 1 | 1 | 1 | 2 | 324496 | 21644 |
| `minimal-research-context` | 4 | 4 | 5 | 0 | 1 | 2 | 3 | 268610 | 15793 |

`minimal-research-context` reduced input tokens by about 14% relative to
`full`, but did not reduce LLM call count (`23` calls per arm) and did not
prevent runtime-tie/fresh-replay pressure.

## Prompt Context Check

First-hypothesis prompt manifest samples showed the intended visibility:

| Arm | `proposal_context_ablation` | Measurement diagnostics | Cross-branch map |
| --- | --- | --- | --- |
| `full` | `full` | present | present |
| `no-measurement-diagnostics` | `no-measurement-diagnostics` | absent | present |
| `minimal-research-context` | `minimal-research-context` | present | absent |

Across all four hypothesis manifests per arm:

- `no-measurement-diagnostics`: all four had no
  `problem_measurement_diagnostics`.
- `minimal-research-context`: all four retained
  `problem_measurement_diagnostics` and had no `cross_branch_research_map`.

Prompt block-family aggregate token shares:

| Family | `full` | `no-measurement-diagnostics` | `minimal-research-context` |
| --- | ---: | ---: | ---: |
| feedback | 0.018423 | 0.035908 | 0.002238 |
| general | 0.398922 | 0.386550 | 0.447925 |
| governance | 0.046389 | 0.045830 | 0.047692 |
| research_signal | 0.154850 | 0.144698 | 0.042491 |
| source_context | 0.001232 | 0.000688 | 0.000843 |
| tool_observation | 0.086872 | 0.075957 | 0.092563 |
| tool_selection | 0.293392 | 0.310429 | 0.366319 |

The minimal arm materially reduced research-signal bulk, but the remaining
prompt is still dominated by general/tool-selection material. That supports the
audit concern that context signal density needs continued treatment, while also
confirming code/source visibility was not the target of this ablation.

## Trajectory Artifacts

Proposal trajectory manifest counts:

| Arm | Sessions | Traces | Formal candidates | Replayable candidates | Prompt manifests loaded |
| --- | ---: | ---: | ---: | ---: | ---: |
| `full` | 8 | 23 | 3 | 3 | 23 |
| `no-measurement-diagnostics` | 8 | 23 | 4 | 4 | 23 |
| `minimal-research-context` | 8 | 23 | 4 | 4 | 23 |

Both comparisons set:

- `observational_only=true`
- `llm_deterministic_replay=false`
- `report_only=true`
- `comparison_is_decision_input=false`
- `decision_features_excluded=true`
- `raw_prompt_excluded=true`
- `raw_response_excluded=true`
- `patch_body_excluded=true`
- `campaign_state_mutated=false`
- `scheduler_state_mutated=false`
- `promotion_state_mutated=false`

Trajectory distributions diverged materially:

| Arm | Mechanisms | Selected surfaces | Target files |
| --- | --- | --- | --- |
| `full` | 4 mechanisms, 2 sessions each | 4 order-level, 4 vehicle-level | 4 target files, 2 sessions each |
| `no-measurement-diagnostics` | `subcategory_consolidation_repack` 6, `split_neutral_cost_compaction` 2 | 2 order-level, 6 vehicle-level | 2 target files |
| `minimal-research-context` | `consolidate_subcategory` 4, `repack_split_subcategory` 4 | 8 vehicle-level | 2 target files |

The original trajectory artifacts exposed a report-attribution gap: the formal
candidate rows were present and replayable, but the session-to-candidate join
heuristic did not understand the common agentic shape where a hypothesis-only
session is followed by a separate code-bearing session. A follow-up repair adds
a conservative `branch_code_sequence` fallback. Exact session/request/
hypothesis matches still win; the fallback only fires when the number of
code-bearing sessions on a branch equals the number of replayable formal
candidate rows for that branch. Hypothesis-only sessions remain unjoined.

Regenerated trajectory manifest coverage on the same source campaigns:

| Arm | Formal candidates | Joined sessions | Missing session joins | Join basis | Context arm known/unknown traces |
| --- | ---: | ---: | ---: | --- | --- |
| `full` | 3 | 3 | 5 | `branch_code_sequence`: 3 | `full`: 8 / 15 unknown |
| `no-measurement-diagnostics` | 4 | 4 | 4 | `branch_code_sequence`: 4 | `no-measurement-diagnostics`: 8 / 15 unknown |
| `minimal-research-context` | 4 | 4 | 4 | `branch_code_sequence`: 4 | `minimal-research-context`: 8 / 15 unknown |

The remaining missing session joins are hypothesis-only sessions or sessions
without a formal candidate. The unknown context-arm traces are tool-selection
and code calls whose prompt manifests do not carry hypothesis-context
metadata; all eight hypothesis-context traces per arm carry the expected
ablation value.

The `branch_code_sequence` join is a fallback, not a replacement for stable
join keys. It depends on the within-branch order of code-bearing sessions
matching the append order of replayable formal candidate rows. That order held
for this shakedown. Future campaigns should persist direct `session_id`,
`request_id`, or `hypothesis_id` linkage in formal candidate rows when
available.

`campaign_summary.json` and `status.json` still record
`measurement_governance=on` while `proposal_context_ablation` /
`context_ablation_arm` are `null`. The repaired trajectory manifest and
comparison now expose a top-level `context_arm_fingerprint`; a future campaign
summary field would still make arm identity easier to inspect without loading
report artifacts.

A coarse forbidden-token scan of the generated trajectory manifest/comparison
artifacts found no raw prompt, raw response, code body, raw measurement
diagnostics, BKS/gap, A/A rows, hypothesis text, or rationale text leakage
beyond guardrail field names such as `raw_response_excluded`.

## Interpretation

The shakedown validates the proposal-visible ablation control:

- CLI and runtime wiring work in a real warehouse campaign.
- Prompt manifests record the selected ablation mode.
- Measurement diagnostics can be removed independently from broader research
  context.
- Broader research context can be hidden while compact measurement diagnostics
  remain visible.
- Report-only trajectory artifacts preserve v3 guardrails.

It also exposes three v0.4 issues that should be handled before formal
governance-value claims:

1. Runtime-tie/fresh-replay pressure still appears in warehouse despite all
   three arms using `measurement_governance=on`. This confirms the audit point
   that runtime semantics and anytime/budget behavior can distort research
   loop accounting.
2. Context compression helps token volume but does not automatically improve
   research quality. `minimal-research-context` produced narrower vehicle-level
   exploration and no promotion in this short run.
3. The original proposal trajectory report needed stronger
   session-to-formal-candidate attribution. The follow-up report repair closes
   the shakedown blocker with a conservative code-session sequence fallback,
   but direct persistence of session/request ids in formal candidate rows would
   still be a stronger long-term attribution source.

## Independent Check

Read-only subagent Kepler independently inspected the run root after first
reading the v3 architecture blueprint. Its conclusion matched the main-thread
check:

- all three arms exited valid/complete with exit code `0`;
- prompt manifests show the intended `proposal_context_ablation` behavior;
- no promotion artifacts were present and champion version remained v1;
- proposal trajectory comparisons are correctly marked `report_only` and
  `observational_only`;
- generated report artifacts did not expose raw prompt/response/code or raw
  measurement material;
- formal repeat analysis should first fix or pre-register the missing
  top-level context-arm fingerprint and weak session-to-formal-candidate join.

The subsequent main-thread repair addressed those two report-layer blockers in
trajectory artifacts. Plato performed a follow-up read-only review and accepted
the v3 boundary, report-only guardrails, and conservative fallback shape. Its
main caveat is the same order assumption above. The result remains posthoc and
observational-only.

## Next Gate

This run is accepted as a shakedown. The immediate report-layer blockers are
repaired for trajectory artifacts: regenerated manifests expose top-level
context-arm fingerprints and join every replayable formal candidate to the
corresponding code-bearing session. The next gate is a warehouse 3-arm repeat
matrix with the same arms, longer round budget, and fixed-candidate replay
after generation. CVRP should remain a context/source/DecisionFeatures smoke
target only until measurement power improves.
