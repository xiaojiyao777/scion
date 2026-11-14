# CVRP Successor49 Repaired Context Route-Pool Repeat Postrun

Date: 2026-07-08

## Status

Successor49 completed valid/complete/postrun-ready, but it is solver-negative
and should not be long-run.

Root:
`/home/clawd/research/scion-experiments/v04-cvrp-successor49-repaired-context-open-cleanfork-server-claw-2r-gpt55-2r-gpt55-20260708T094104Z-claw`

Launch facts:

- Commit: `bd664202`
- Runner: server-local conda `claw`
- Model: local `gpt-5.5`
- Command: `--rounds 2 --force-surface solver_design --proposal-context-ablation full --agentic-proposal`
- Wrapper exit: `0`
- Campaign status: `complete`
- Run validity: `valid`
- Completed requested rounds: `true`
- Stop reason: `max_rounds_exhausted`
- Postrun readiness exit: `0`

Campaign accounting:

- Requested rounds: 2
- Effective rounds completed: 2
- Proposal attempts: 3
- Proposal quality blocks: 1
- Formal screened candidates: 2
- Protocol evaluated candidates: 2
- LLM traces: 6, all `gpt-5.5`, all `ok`

## Per-Call Trace Audit

The trace audit found no model-call failure and no evidence that prompt
truncation caused the repeated weak mechanism.

| Time | Stage | Result |
| --- | --- | --- |
| 09:41:07 | `hypothesis_target_intent` | Selected `bounded_route_pool_set_partition_recombination`, with target `policies/baseline_modules/route_pool_recombination.py`. |
| 09:41:13 | `hypothesis` | Blocked before code generation by `cvrp_solver_design_causal_path_contract`; missing `branch_lesson_usage.clean_fork_diversity_claim` and `algorithmic_intervention_sufficiency`. |
| 09:41:34 | `hypothesis_target_intent` | Retried target intent, still selected route-pool recombination but now as a create-new CVRP-owned module path. |
| 09:41:50 | `hypothesis` | Passed after adding clean-fork diversity, CMT2/CMT4 protected-case plan, mechanism telemetry, and algorithmic-intervention language. |
| 09:42:27 | `tool_selection` | Returned `intent=stop`; no extra tool work. |
| 09:42:28 | `code` | Created `route_pool_recombination.py` and minimal scheduler wiring. Static contract and smoke reached screening. |

Prompt manifests showed `material_difference_requirement_visible=true` for the
hypothesis target-intent and hypothesis calls. All six API-visible prompt
manifests had zero truncated sections.

## Candidate

The accepted candidate was a bounded whole-route set-partition recombination:

- build a small route pool from complete feasible routes already seen in the
  current run;
- solve a bounded exact-cover route-set selection problem;
- accept only if route count, feasibility, and final `total_distance` improve;
- record mechanism telemetry under
  `bounded_route_pool_set_partition_recombination`.

This preserved CVRP-owned boundaries: the generated solver code lived under
`policies/baseline_modules/route_pool_recombination.py`, with minimal scheduler
wiring. No CVRP/VRP semantics moved into generic Scion core.

## Screening Evidence

Postrun summary:

- Total experiments: 2
- Champion promotions: 0
- Screening case W/L/T: `0/0/28`
- Screening pair W/L/T: `7/0/105`
- Screening gate win rate: `0.0`
- Measurement readiness: ready, `n_pairs=96`, MDE `9.9`, low power

Screening rows:

| Row | Pairs | Case W/L/T | Pair W/L/T | Median delta | CI | Mechanism effect |
| --- | ---: | --- | --- | ---: | --- | --- |
| 1 | 48 | `0/0/12` | `3/0/45` | `0.0` | `[0.0, 0.0]` | route-pool runtime observed in 35/48 pairs; positive direct best-delta/improvement in 1/48 pairs |
| 2 | 64 | `0/0/16` | `4/0/60` | `0.0` | `[0.0, 0.0]` | route-pool runtime observed in 46/64 pairs; positive direct best-delta/improvement in 0/64 pairs |

The active branch was retained as weak-positive from pair-level ties/wins, but
the mechanism evidence classified the outcome as `telemetry_effect_zero` /
observed no effect. This is not promotion-grade evidence.

## Diagnosis

The repaired CVRP context/contract worked at the first failure point: the first
hypothesis was blocked before code generation because it did not provide the
required clean-fork diversity and algorithmic-intervention sufficiency.

The remaining problem was not context truncation. The retry still converged on
the same route-pool mechanism because the successor48/49 route-pool line had
not yet been fully closed in live CVRP guidance and the hypothesis contract.
The candidate itself was too conservative: a whole-route exact cover over only
same-run initial/current/best routes rarely creates a strictly better final
route set, so activation is visible but final objective effect remains zero.

## Decision

Treat successor49 as:

- framework-positive for the repaired CVRP solver-design contract;
- solver-negative for `bounded_route_pool_set_partition_recombination`;
- evidence that successor48/49 route-pool recombination must be
  reviewed/default-avoid, not tuned or long-run.

Do not launch a long-run, threshold-tuning, beam-width tuning, pool-size tuning,
or telemetry-hygiene-only follow-up for this mechanism. The next CVRP solver
slot must be a materially different CVRP-owned clean fork with direct accepted
move or final objective-effect evidence and CMT2/CMT4 protection.

## Follow-Up Repair

The current checkout closes this route-pool line in CVRP-owned code:

- `scion/problems/cvrp/proposal_quality/hypothesis_contract.py` now includes
  `bounded_route_pool_set_partition_recombination` in reviewed/default-avoid
  mechanisms.
- `scion/problems/cvrp/research_guidance.py` now publishes successor48/49
  reviewed evidence rather than live target-intent guidance for route-pool
  recombination.
- Tests cover the reviewed/default-avoid block and prepared manifest payload.

Boundary verification:

- `python -m pytest scion/tests/test_cvrp_adapter_core.py scion/tests/unit/test_cvrp_research_guidance_provider.py scion/tests/test_cvrp_agentic_launcher.py`
- `python -m pytest scion/tests/unit/test_v3_problem_boundary_no_cvrp_terms_in_generic_layers.py`
