# CVRP Successor50 Material-Difference Contract Repair Postrun

Date: 2026-07-08

## Status

Successor50 completed valid/complete/postrun-ready, but it is not solver
evidence and should not be long-run or continued as an optimization branch.

Root:
`/home/clawd/research/scion-experiments/v04-cvrp-successor50-repaired-context-material-cleanfork-server-claw-2r-gpt55-20260708T121805Z-claw`

Launch facts:

- Commit: `0dd21bfc`
- Runner: server-local conda `claw`
- Model: local `gpt-5.5`
- Command shape: `--rounds 2 --completion-preflight --force-surface solver_design --proposal-context-ablation full --agentic-proposal`
- Wrapper exit: `0`
- Campaign status: `complete`
- Run validity: `valid`
- Completed requested rounds: `true`
- Stop reason: `max_rounds_exhausted`
- Postrun readiness: `ready`

Campaign accounting:

- Requested rounds: 2
- Effective rounds completed: 2
- Proposal attempts: 3
- Proposal quality blocks: 1
- Formal screened candidates: 2
- Protocol evaluated candidates: 2
- LLM traces: 6, all `gpt-5.5`, all `ok`
- Candidate intent counts: `repair_or_infra_candidate=3`,
  `algorithm_quality_candidate=0`

## Per-Call Trace Audit

The trace audit found normal model calls. The failure mode was research
direction drift into repair/infra work, not local model unavailability.

| Time | Stage | Result |
| --- | --- | --- |
| 12:18:09 | `hypothesis_target_intent` | Selected `bounded_route_path_relinking`, target `policies/baseline_modules/route_path_relinking.py`, `create_new`. The target-intent preflight was rejected by default-avoid route/path risk, so it did not bind the formal hypothesis. |
| 12:18:31 | `hypothesis` | Drifted to `depot_anchor_rotation`, target `policies/baseline_modules/depot_anchor_rotation.py`. This was a real solver idea, but it was blocked before code generation by `cvrp_solver_design_causal_path_contract` for missing exact `branch_lesson_usage.clean_fork_diversity_claim` shape and `algorithmic_intervention_sufficiency`. |
| 12:19:06 | `hypothesis_target_intent` | Retry selected `material_difference_contract_repair`, target `policies/baseline_modules/scheduler.py`, `modify`. |
| 12:19:22 | `hypothesis` | Accepted the same `material_difference_contract_repair` idea. The hypothesis explicitly proposed a scheduler-level metadata/hook gate and stated the champion route search would remain unchanged when no hook is present. |
| 12:19:46 | `tool_selection` | Returned `intent=stop`; no extra tool work. |
| 12:19:48 | `code` | Modified `scheduler.py` to add a material-difference metadata gate and telemetry records. Static checks and screening ran. |

Prompt visibility was mostly healthy. All six current-run traces had prompt
manifests. The material-difference requirement was visible in hypothesis
target-intent and hypothesis prompts. One hypothesis retry trace had
`hypothesis_target_intent_preflight` truncated, but the accepted scheduler
contract hypothesis had full material-difference visibility and full target
source visibility. The observed failure is therefore not explained by a
missing model call or fatal prompt truncation.

## Candidate

The screened candidate was a CVRP-owned scheduler contract wrapper:

- add `_MATERIAL_DIFFERENCE_CONTRACT_PHASE`;
- add required metadata keys for experimental scheduler hooks;
- call `_material_difference_contract_allows()` before the normal initial
  solution path;
- record `material_difference_contract_repair` context/phase telemetry;
- return `False` when no compliant `experimental_scheduler_hook` exists.

With no hook present, the champion route search path is unchanged. The
candidate does not generate or select a new route state, does not accept or
reject a candidate route move, and does not provide a direct final objective
mechanism effect. It is repair-or-infra work, not a CVRP solver mechanism.

This stayed inside the CVRP problem package and did not move CVRP semantics
into generic Scion core or `DecisionFeatures`, but it consumed a solver-design
experiment slot with a non-solver candidate.

## Screening Evidence

Postrun summary:

- Total experiments: 2
- Champion promotions: 0
- Screening case W/L/T: `0/0/20`
- Screening pair W/L/T: `3/2/75`
- Screening gate win rate: `0.0`
- Measurement readiness: ready, `n_pairs=96`, MDE `9.9`, low power

Screening rows:

| Row | Pairs | Case W/L/T | Pair W/L/T | Median delta | CI | Mechanism effect |
| --- | ---: | --- | --- | ---: | --- | --- |
| 1 | 32 | `0/0/8` | `3/1/28` | `0.0` | `[0.0, 0.0]` | activation/context observed; runtime positive in 1/32 pairs; best-delta and improvement counts positive in 0/32 pairs |
| 2 | 48 | `0/0/12` | `0/1/47` | `0.0` | `[0.0, 0.0]` | activation/context observed; runtime positive in 0/48 pairs; best-delta and improvement counts positive in 0/48 pairs |

Research-efficiency diagnostics classified both rows below MDE with
`max_median_delta=0.0`, `max_effect_to_mde_ratio=0.0`, and interpretation
`all_available_ci_high_below_mde`.

## Diagnosis

The repaired solver-design causal-path contract worked at the first important
failure point: it blocked the under-specified `depot_anchor_rotation`
hypothesis before code generation. That blocked hypothesis had a plausible
algorithmic direction, but it did not satisfy the exact clean-fork diversity
and algorithmic-intervention schema.

The retry then followed the wrong target. The live CVRP guidance still carried
an outdated instruction to repair the context/contract before another solver
line. In the retry profile, the model interpreted the quality feedback as a
request to implement a scheduler-level contract gate rather than to redraft the
solver hypothesis itself. This is why all three candidate intents were counted
as repair/infra rather than algorithm-quality candidates.

This explains the zero-effect metrics. The accepted patch records that a gate
was checked, but it leaves the solver trajectory unchanged and never produces
candidate route states. There is no solver improvement to measure.

## Decision

Treat successor50 as:

- framework/guidance-negative for solver-slot routing;
- solver-negative for `material_difference_contract_repair`;
- reviewed/default-avoid evidence that contract repair, metadata preflight,
  telemetry-only wrapper, hook gate, and no-op hook validation must not occupy
  a materially different CVRP solver clean-fork slot.

Do not long-run, threshold-tune, telemetry-tune, or continue this line. The
next CVRP slot must return to a materially different CVRP-owned solver
mechanism with candidate route-state generation or selection, attempted/
accepted/rejected/budget observations, final `total_distance` attribution, and
CMT2/CMT4 protected-case evidence.

## Follow-Up Repair

The current checkout closes the successor50 failure mode in CVRP-owned code:

- `scion/problems/cvrp/research_guidance.py` now marks
  `material_difference_contract_repair` as reviewed/default-avoid
  repair-or-infra work and removes the stale "repair context/contract before
  another solver line" instruction.
- `scion/problems/cvrp/proposal_quality/hypothesis_contract.py` now blocks the
  exact `material_difference_contract_repair` mechanism and the generalized
  solver-slot anti-pattern: `*_contract_repair`, scheduler-level metadata
  gates, metadata preflights, telemetry-only wrappers, hook gates, and no-op
  hook validation.
- Prepared-manifest tests verify successor50 reviewed evidence is visible to
  future CVRP runs.
- Hypothesis-quality tests verify repair/infra candidates cannot pass as CVRP
  solver mechanisms.

Boundary verification:

- `python -m pytest scion/tests/test_cvrp_adapter_core.py scion/tests/unit/test_cvrp_research_guidance_provider.py scion/tests/test_cvrp_agentic_launcher.py`
- `python -m pytest scion/tests/unit/test_v3_problem_boundary_no_cvrp_terms_in_generic_layers.py`
