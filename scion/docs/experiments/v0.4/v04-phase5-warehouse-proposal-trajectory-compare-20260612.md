# v0.4 Warehouse Proposal Trajectory Compare

*Date: 2026-06-12*
*Branch: `codex/v04-evidence-repair-plan`*
*Status: valid report-only trajectory artifact; observational only*

## Summary

The warehouse ON/OFF shakedown now has a report-only proposal trajectory
comparison. This sits one level above fixed-candidate replay: it summarizes
agentic sessions, trace indexes, prompt-manifest block-family accounting, and
replayable formal-candidate joins without embedding raw prompts, raw responses,
patch bodies, raw metrics, validation/frozen detail, or Decision inputs.

The comparison confirms the current interpretation. Same-patch protocol
evaluation was not the source of the ON/OFF difference; fixed-candidate replay
produced identical screening outcomes. The remaining signal is proposal and
context trajectory distribution, and the artifact is explicitly
`observational_only=true`.

## Artifacts

Artifact root:

`/home/clawd/research/scion-experiments/v04-phase5-proposal-trajectory-warehouse-onoff-20260612T0550Z-claw`

- ON manifest:
  `on-proposal-trajectory-manifest.v1.json`
- Record-only manifest:
  `record-only-proposal-trajectory-manifest.v1.json`
- Comparison:
  `proposal-trajectory-comparison.v1.json`

Commands:

```bash
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion \
python -m scion.cli.main report proposal-trajectory-manifest \
  --campaign-dir /home/clawd/research/scion-experiments/v04-phase5-governance-warehouse-on-pilot-8r-gpt55-20260612T013119Z-claw/campaign \
  --observed-control-arm on \
  --output /home/clawd/research/scion-experiments/v04-phase5-proposal-trajectory-warehouse-onoff-20260612T0550Z-claw/on-proposal-trajectory-manifest.v1.json

PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion \
python -m scion.cli.main report proposal-trajectory-manifest \
  --campaign-dir /home/clawd/research/scion-experiments/v04-phase5-governance-warehouse-record_only-pilot-8r-gpt55-20260612T013119Z-claw/campaign \
  --observed-control-arm record_only \
  --output /home/clawd/research/scion-experiments/v04-phase5-proposal-trajectory-warehouse-onoff-20260612T0550Z-claw/record-only-proposal-trajectory-manifest.v1.json

PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion \
python -m scion.cli.main report proposal-trajectory-compare \
  --left /home/clawd/research/scion-experiments/v04-phase5-proposal-trajectory-warehouse-onoff-20260612T0550Z-claw/on-proposal-trajectory-manifest.v1.json \
  --right /home/clawd/research/scion-experiments/v04-phase5-proposal-trajectory-warehouse-onoff-20260612T0550Z-claw/record-only-proposal-trajectory-manifest.v1.json \
  --output /home/clawd/research/scion-experiments/v04-phase5-proposal-trajectory-warehouse-onoff-20260612T0550Z-claw/proposal-trajectory-comparison.v1.json
```

## Guardrails

Both manifests and the comparison set:

- `report_only=true`
- `decision_features_excluded=true`
- `comparison_is_decision_input=false`
- `campaign_state_mutated=false`
- `scheduler_state_mutated=false`
- `promotion_state_mutated=false`
- `raw_prompt_excluded=true`
- `raw_response_excluded=true`
- `patch_body_excluded=true`

An exact recursive key/value scan found no `code_content`, `prompt_text`,
`user_prompt`, `system_blocks`, `response`, `raw_measurement_diagnostics`,
`bks_gap`, `aa_rows`, `hypothesis_text`, or `rationale_text` leakage.

## Counts

| Arm | Sessions | Traces | Formal candidates | Replayable candidates | Prompt manifests loaded |
| --- | ---: | ---: | ---: | ---: | ---: |
| ON | 10 | 32 | 5 | 5 | 32 |
| Record-only | 10 | 32 | 5 | 5 | 32 |

Trace kind counts:

| Arm | Hypothesis | Tool selection | Code |
| --- | ---: | ---: | ---: |
| ON | 9 | 18 | 5 |
| Record-only | 10 | 17 | 5 |

Formal-candidate joins are session-level joins to replayable formal rows. ON
joined 4 sessions and record-only joined 6 sessions. Missing joins are expected
where multiple sessions share one branch or where a proposal did not produce a
formal candidate.

## Trajectory Differences

The selected surface distribution was the same: both arms had 8 vehicle-level
and 2 order-level proposal sessions. Mechanism and target distributions
diverged:

ON mechanisms:

- `subcategory_pack_upgrade`: 6
- `split_preserving_evacuate`: 2
- `split_safe_cost_merge`: 2

Record-only mechanisms:

- `subcategory_block_repack`: 4
- `safe_gap_fill`: 2
- `best_of_k_merge`: 2
- `compatible_repack_merge`: 2

Target-file distribution:

| Target | ON | Record-only |
| --- | ---: | ---: |
| `operators/merge_vehicles.py` | 2 | 4 |
| `operators/subcategory_pack_upgrade.py` | 6 | 0 |
| `operators/split_preserving_evacuate.py` | 2 | 0 |
| `operators/subcategory_consolidate.py` | 0 | 4 |
| `operators/move_order.py` | 0 | 2 |

Prompt block-family aggregate token shares show broad similarity but different
emphasis:

| Family | ON | Record-only | Delta |
| --- | ---: | ---: | ---: |
| feedback | 0.030602 | 0.021876 | -0.008726 |
| general | 0.335124 | 0.345742 | +0.010618 |
| governance | 0.036384 | 0.042851 | +0.006467 |
| research_signal | 0.145015 | 0.158782 | +0.013767 |
| source_context | 0.000743 | 0.000889 | +0.000146 |
| tool_observation | 0.066083 | 0.072970 | +0.006887 |
| tool_selection | 0.386105 | 0.356944 | -0.029161 |

## Interpretation

The artifact supports the same conclusion as the manual prompt/context analysis:
record-only is not all-governance-off. Measurement diagnostics are suppressed,
but objective opportunity, runtime feedback, cross-branch maps, branch memory,
source visibility, and general governance remain active. The current ON/OFF
label therefore mixes at least two questions:

- Does measurement diagnostics change proposal/context behavior?
- Does broader research context and branch memory change proposal behavior?

The next formal experiment should separate these effects. A useful v0.4 design
is a warehouse prompt/context ablation with at least:

- measurement diagnostics on/off with broader research context held constant;
- broader research context on/off with measurement diagnostics held constant;
- fixed-candidate replay after generation to confirm protocol evaluation is
not the source of any trajectory difference.

This report remains proposal/experiment-design evidence only. It must not be
used as campaign, Decision, validation, frozen, or promotion input.
