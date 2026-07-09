# CVRP successor54 protected budgeted trajectory selector postrun - 2026-07-09

## Scope

Run root:
`/home/clawd/research/scion-experiments/v04-cvrp-successor54-post-successor53-gate-repair-protected-race-server-claw-2r-gpt55-20260709T033540Z-claw`

Successor54 was launched from committed gate-wording repair `d7a1370c` after
successor53 showed a brittle CVRP-owned causal-path contract around
attempt/reject/budget wording. The run used the server-local `claw`
environment, local `gpt-5.5`, `--rounds 2`, `--completion-preflight`, full
proposal context, `--force-surface solver_design`, and no forced mechanism or
target file.

## Run Status

- Wrapper status: finished, exit status `0`.
- Campaign status: complete; requested rounds `2`, effective rounds `2`.
- Postrun acceptance: ready.
- Stop reason: `max_rounds_exhausted`.
- Run validity: valid.
- Model calls: eleven successful `gpt-5.5` calls.
- Request kinds: three `hypothesis_target_intent`, three `hypothesis`, three
  `tool_selection`, and two `code`.
- Proposal attempts: three total, with one proposal-quality block.
- Candidate intents: two algorithm-quality candidates and one repair/infra
  attempt.
- Champion promotions: `0`.

This is valid experiment evidence. It is not a model outage, completion
preflight failure, verification failure, postrun-acceptance failure, or generic
DecisionFeatures boundary issue.

## LLM Call Audit

| Step | Trace | Request | Result |
|---:|---|---|---|
| 1 | `20260709T033544261698_hypothesis_target_intent_f7f23d0e72_8550e4e6.json` | target intent | Selected `protected_budgeted_trajectory_race_selector` in `scheduler.py`, with RNG isolation, canonical baseline, post-downstream attribution, and CMT2/CMT4 protection. |
| 2 | `20260709T033556863275_hypothesis_ca0e967915_7f8b798c.json` | hypothesis | Blocked pre-code by `cvrp_solver_design_causal_path_contract`; missing `branch_lesson_usage.clean_fork_diversity_claim`. |
| 3 | `20260709T033625716767_hypothesis_target_intent_20b1a04d57_0f829b52.json` | target intent | Retried as `protected_budgeted_trajectory_selector` in `scheduler.py`. |
| 4 | `20260709T033638483002_hypothesis_33df52689d_7bb114b9.json` | hypothesis | Passed with exact `clean_fork_diversity_claim.protected_cases=[CMT2,CMT4]` and final-attribution telemetry. |
| 5 | `20260709T033706444915_tool_selection_9b98d74a7a_258551d1.json` | tool selection | Stopped; no extra tool call. |
| 6 | `20260709T033709454380_code_2bad95ca06_a3b92057.json` | code | Implemented `protected_budgeted_trajectory_selector`; modified only `policies/baseline_modules/scheduler.py`. |
| 7 | `20260709T041251013212_hypothesis_target_intent_bac6eb4e8e_3e3f62c5.json` | target intent | Selected `protected_budgeted_trajectory_selector_v2`, still a protected race repair. |
| 8 | `20260709T041258293016_hypothesis_4c62ee4d29_7a3e288b.json` | hypothesis | Passed with CMT2/CMT4 protected-case plan and baseline-vs-alternate post-polish objective guard. |
| 9 | `20260709T041322726352_tool_selection_0ee5a42373_6d9a9f99.json` | tool selection | Read full `policies/baseline_modules/scheduler.py` with `max_chars=96000`. |
| 10 | `20260709T041325542421_tool_selection_9a0f6189ac_718442a4.json` | tool selection | Stopped; no further tool call. |
| 11 | `20260709T041327478111_code_5ee2708240_20549a9d.json` | code | Implemented `protected_budgeted_trajectory_selector_v2`; modified only `scheduler.py`. |

The successor53 gate repair worked. The first block was the intended
CMT2/CMT4 clean-fork schema block, not another
`algorithmic_intervention_sufficiency` loop. Both accepted hypotheses reached
code generation with the protected-case schema present.

The run still shows prepared-context conservatism: all target-intent calls
selected the protected successor52 race repair in `scheduler.py`. That was
allowed by the prepared question, but it means successor54 is same-line
protected repair evidence rather than a materially different clean fork.

## Candidate Audit

Both candidates stayed inside the CVRP solver subject boundary: only
`policies/baseline_modules/scheduler.py` was changed, and no generic core,
protocol, promotion, or DecisionFeatures code received CVRP semantics.

`protected_budgeted_trajectory_selector` added `_prepare_candidate_trajectory`
and related selector helpers. It promised post-downstream selection, but the
candidate diff selected an alternate after repair-local distance comparison and
then ran downstream only on the selected candidate. That leaves the successor52
failure mode partly intact: a repair-local winner can still become the final
trajectory before its downstream behavior is known.

`protected_budgeted_trajectory_selector_v2` moved closer to the intended
contract. It lets the baseline follow the existing repair/polish path, lets one
alternate follow a bounded downstream path, then replaces the candidate only if
the alternate post-polish objective beats the baseline. The remaining design
gaps are:

- alternate RNG uses `random.Random(rng.random())`, which consumes the main RNG
  and is not strict non-winner RNG isolation;
- alternate downstream VNS can consume substantial runtime and change the
  later ALNS/VNS budget trajectory;
- the implementation is still inline scheduler growth rather than a separate
  bounded mechanism module.

These gaps do not require an immediate solver-code patch because the candidate
was not promoted into the main checkout. They are evidence for parking the
same race-selector line.

## Measurement Result

Measurement readiness was `ready`, with MDE at power 80 equal to `9.9`; the
readiness and research-efficiency artifacts are report-only and excluded from
DecisionFeatures.

| Mechanism | Pairs | Pair W/L/T | Median | CI | Decision |
|---|---:|---:|---:|---|---|
| `protected_budgeted_trajectory_selector` | 32 | 3/6/23 | 0.0 | [-0.25, 0.0] | abandon |
| `protected_budgeted_trajectory_selector_v2` | 32 | 14/9/9 | 1.25 | [-2.0, 6.0] | expand_screening |

Postrun effect-vs-MDE summary:

- max median delta: `1.25`;
- max effect-to-MDE ratio: `0.126263`;
- rows at or above MDE: `0`;
- rows with CI high below MDE: `2`;
- interpretation: `all_available_ci_high_below_mde`;
- champion promotions: `0`.

## Case Pattern

First selector:

- `CMT2`: median `-7.5`, deltas `[-32, 0, 0, -15]`.
- `CMT4`: median `0.0`, all ties.
- `P-n65-k10`: median `-0.5`.
- `X-n110-k13`: median `0.0`, with one `+70` seed and three ties.

Second selector:

- `A-n64-k9`: median `+18.5`.
- `B-n63-k10`: median `+2.0`.
- `CMT2`: median `+0.5`.
- `CMT4`: median `-2.0`, mixed `2/2/0`.
- `P-n65-k10`: median `+6.0`.
- `X-n110-k13`: median `-6.0`, with losses `-12` and `-46`.

The v2 candidate partly repaired CMT2 relative to successor52 and the first
selector, but the aggregate effect remained small, CMT4 stayed negative, and
X-n110 regressed.

## Telemetry Interpretation

Mechanism activation was observed for both candidates. The first selector had
low selector-phase runtime (`806 ms` weighted) and stayed no-positive at the
aggregate objective gate. The v2 selector activated in all 32 candidate pairs,
with `431866 ms` weighted selector runtime and positive primary mechanism
effect recorded, but that local/phase signal still did not convert into
promotion-grade final candidate-vs-champion total-distance evidence.

The failure mode is not context starvation or inactive telemetry. It is that
the protected race repair still creates trajectory and budget effects whose
final objective benefit is too small and too case-unstable for v0.4
continuation.

## Decision

Treat successor54 as valid, gate-positive, and solver-below-MDE.

Do not:

- promote or long-run `protected_budgeted_trajectory_selector`;
- promote or long-run `protected_budgeted_trajectory_selector_v2`;
- continue same-mechanism threshold, cadence, or budget-share tuning;
- treat v2's weak-positive row as enough to offset CMT4/X-n110 regressions;
- merge either candidate implementation into the main solver subject.

Record both mechanisms as reviewed/default-avoid. The next CVRP solver slot
should be a materially different CVRP-owned clean fork, designed before code
generation, with a bounded module boundary rather than more inline scheduler
helper growth. It should keep final total-distance attribution, feasibility,
route count, accepted/rejected/budget evidence, and CMT2/CMT4 protection
visible before code work starts.
