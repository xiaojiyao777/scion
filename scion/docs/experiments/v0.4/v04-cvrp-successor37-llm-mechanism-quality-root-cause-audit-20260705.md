# CVRP successor37 LLM and mechanism-quality root-cause audit

Date: 2026-07-05

Run root:
`/home/clawd/research/scion-experiments/v04-cvrp-successor37-cleanfork-material-causal-path-server-2r-gpt55-20260705T133809Z-claw`

## Conclusion

Successor37 was not blocked by infrastructure, model availability, or an
over-strict gate. The run completed valid/complete/postrun-ready with two
effective screening rows and 11 successful `gpt-5.5` LLM calls. The failure is
proposal-control and candidate-quality:

- target-intent selected weak causal paths before material-difference and
  CMT2/CMT4 commitments became hard constraints;
- hypothesis responses self-certified novelty rather than proving it against
  source and reviewed evidence;
- tool-selection did not perform mechanism-neighborhood or claim/source
  consistency checks;
- code generation was allowed to implement supported patches even when novelty
  or causal effect was only diagnostic;
- postrun feedback changed the target owner after the route-angle failure, but
  did not enforce direct mechanism effect or CMT2/CMT4 protection.

Do not long-run successor37, do not repeat `route_angle_aware_2opt_star`, and
do not repeat unchanged `edge_frequency_penalty_repair`. A protected
edge-frequency follow-up is also not the next default action because the direct
mechanism effect was zero and CMT2/CMT4 lost all seeds. The next step is a
proposal-control/candidate-quality repair plus a materially different
CVRP-owned causal path.

## LLM Call Audit

All trace files are under:
`/home/clawd/research/scion-experiments/v04-cvrp-successor37-cleanfork-material-causal-path-server-2r-gpt55-20260705T133809Z-claw/campaign/llm_traces/`

| Trace | Type | Output | Quality issue |
|---|---|---|---|
| `20260705T133814852802_hypothesis_target_intent_d04719dc37_fe10862a.json` | `hypothesis_target_intent` | selected `policies/baseline_modules/local_search.py` / `route_angle_aware_2opt_star` | chose a near `_two_opt_star` route-tail exchange path; material-difference and opportunity commitments were not hard-visible. |
| `20260705T133821198184_hypothesis_8f4b0e8e65_29cb88da.json` | `hypothesis` | formalized `route_angle_aware_2opt_star` | `material_difference` was model self-report; CMT2/CMT4 appeared only as named protected cases, not a protection mechanism. |
| `20260705T133906132268_tool_selection_3834935536_9a24e7a7.json` | `tool_selection` | `context.read_branch_state` | gathered branch state, but not source-level novelty evidence. |
| `20260705T133908107108_tool_selection_c0836d51cc_229e1d06.json` | `tool_selection` | `context.read_surface(target_preview)` | read compact target preview only. |
| `20260705T133910264627_tool_selection_7a41426d3e_a593e9d4.json` | `tool_selection` | `context.read_algorithm_file(policies/baseline_algorithm.py)` | read the algorithm entrypoint, not the target `local_search.py`; did not compare against `_two_opt_star`. |
| `20260705T133915003032_tool_selection_306a791101_178cde8d.json` | `tool_selection` | `stop` | stopped before a mechanism-neighborhood audit. |
| `20260705T133916957222_code_fd71ac8f14_01ea1f81.json` | `code` | patched `local_search.py` | inserted `_route_angle_aware_2opt_star` before `_two_opt_star`; code stage treated duplicate/uncertain benefit as diagnostic, not a blocker. |
| `20260705T141441504856_hypothesis_target_intent_7ab695c06e_3820c133.json` | `hypothesis_target_intent` | selected `policies/baseline_modules/destroy_repair.py` / `edge_frequency_penalty_repair` | changed owner after failure, but did not carry a hard direct-effect or CMT2/CMT4 commitment. |
| `20260705T141449874896_hypothesis_a4505a08f3_d700b660.json` | `hypothesis` | formalized `edge_frequency_penalty_repair` | claimed incumbent/best trajectory edge memory, but no code-level contract required that state to exist. |
| `20260705T141517220053_tool_selection_8d1de4891e_c6c5d766.json` | `tool_selection` | `stop` | stopped without further target-file or scheduler-interface checks. |
| `20260705T141519575958_code_1ad2a85aef_87c5673f.json` | `code` | patched `destroy_repair.py` and `scheduler.py` | implemented current-partial-solution edge counts, not true incumbent/best trajectory memory; added repair helpers and scheduler wiring. |

Important prompt-manifest finding: the postrun trajectory manifest reports large
research-signal context, but prompt manifests showed
`material_difference_requirement_visible=false` and empty opportunity evidence
commitments. The history was present as narrative pressure, not as a hard
proposal contract.

## Candidate Mechanism Audit

`route_angle_aware_2opt_star`:

- Candidate diff:
  `/home/clawd/research/scion-experiments/v04-cvrp-successor37-cleanfork-material-causal-path-server-2r-gpt55-20260705T133809Z-claw/campaign/artifacts/formal_candidates/76221086/screening-aa0b0583-bc73-4efc-b3e8-3a0d1b9fcfad-dd8a89971e6e39f4/candidate.diff`
- Decision: `abandon`.
- Screening: median `-4.25`, CI `[-8.0, 0.0]`, effect/MDE `-0.429293`.
- Pair W/L/T: `8/15/9`; case win rate `0.125`.
- CMT2 median `-13.5`; CMT4 median `-9.0`.
- It had local direct effect telemetry, but the final objective row was
  negative. The mechanism is a search-order/basin perturbation before the
  existing `_two_opt_star`, not a robust new final-quality path.

`edge_frequency_penalty_repair`:

- Candidate diff:
  `/home/clawd/research/scion-experiments/v04-cvrp-successor37-cleanfork-material-causal-path-server-2r-gpt55-20260705T133809Z-claw/campaign/artifacts/formal_candidates/19b6473b/screening-de963c51-8163-44e8-a287-6d3346b35a21-c7aad5a2eb70ae90/candidate.diff`
- Decision: `expand_screening`, but with `TELEMETRY_EFFECT_ZERO_DIAGNOSTIC`.
- Screening: median `2.5`, CI `[-7.5, 19.5]`, effect/MDE `0.252525`.
- Pair W/L/T: `13/14/5`; case win rate `0.5`.
- CMT2 median `-7.5`, four losses; CMT4 median `-15.0`, four losses.
- Direct effect telemetry: candidate present `60`, positive `0`, zero `60`.
- The weak aggregate positive is not directly attributable to the new repair
  mechanism. It is more consistent with downstream ALNS/VNS absorption plus
  noise or search-path drift.

## Gate and Measurement Judgment

The gate is not the main bottleneck in successor37. Measurement readiness was
`ready`, but `signal_to_noise_tier=low_power`, `mde_at_power_80=9.9`, and
`noise_band_p90_abs=45.5`. That means small positives are hard to promote, but
the best row was only `2.5 / 9.9 = 0.252525` of MDE, had CI crossing negative,
direct effect zero, and all CMT2/CMT4 seeds lost. This is not a near-threshold
promotion case.

The promotion failure is expected:

- `champion_promotions=0`
- `screening_pass_rate=0.0`
- `rows_at_or_above_mde=0`
- total case W/L/T `5/5/6`
- total pair W/L/T `21/29/14`

## Design Follow-Up

Add or preserve these proposal-control rules before launching the next long or
large experiment:

1. Target-intent must emit a structured causal-path contract: exact mechanism,
   nearest reviewed mechanisms, difference dimensions, protected-case plan, and
   direct-effect measurement plan.
2. Hypothesis quality must fail closed on exact reviewed/default-avoid
   mechanisms. The current repair adds this for the two successor37 mechanisms.
3. Pre-code quality should compare the hypothesis claim against target source:
   code should not implement a patch when the claimed trajectory memory,
   protected-case guard, or direct-effect mechanism is absent.
4. Code generation should be allowed to reject `duplicate`, `contradicted`, or
   direct-effect-missing proposals rather than always emitting a patch.
5. Repair/local-search mechanisms need micro-effect evidence before formal
   screening: same-state before/after objective deltas for the declared
   mechanism, plus CMT2/CMT4 caveat or protection evidence.

This repair remains problem-owned. Do not put CVRP case semantics in generic
core or DecisionFeatures.
