# 8R CVRP Verification Analysis

Experiment:
`/home/clawd/research/scion-experiments/v04-audit-provenance-replay-verify-8r-gpt55-20260607T210441Z-8r-gpt55-20260607T210441Z-claw/campaign`

Date analyzed: 2026-06-07

Required design references read:

- `scion/design/scion-architecture-v3.md`
- `scion/reports/architecture-audit-v0.4/remediation-status.md`
- `scion/reports/experiments/v04-audit-provenance-replay-verify-4r-gpt55-20260607T202748Z-analysis.md`

## Executive Conclusion

This run is valid partial evidence, not an 8R acceptance run. It requested 8 effective screened rounds but completed only 5 formal screening candidates, then stopped as `valid_partial_interrupted` with `last_stop_reason=scheduler_active_slot_blocked`. The blocking condition is framework-level scheduler/lifecycle behavior, not an algorithm candidate failure: three active branches occupied the active-slot cap, and the final scheduler audit reported `decision_origin_lifecycle_marker_missing` for all three candidate active branches during new-branch reclaim.

I would not continue to 8R/12R without fixing or explicitly bypass-testing this scheduler active-slot release/reclaim path. The completed 5 candidates are useful for research-quality and provenance analysis, but they are not sufficient for the requested 8R verification gate because final evidence packaging is missing, 3 requested screened rounds never ran, and the stop condition is a scheduler resource-governance defect.

Research-quality verdict: the agent is doing real algorithm research in the narrow sense that hypotheses are mechanism-specific, code changes implement the stated mechanisms, telemetry shows activation, and branch follow-up used prior feedback. The algorithmic signal is weak: no candidate reached validation, one scheduler branch produced only marginal/weak pair-level and mixed case-level evidence, and all other mechanisms were no-effect or regression. Runtime/tool-token reductions should not be treated as success; runtime evidence was explicitly excluded from decision features for all 5 candidates and low/cached for 4/5.

Architecture-boundary verdict: the run is consistent with Scion v3 boundaries. LLM outputs remained proposal/patch artifacts; Decision evidence used structured features, reason codes, and protocol metrics. Cross-branch research observability is marked proposal-only and excluded from decision features. I found no sign that CVRP semantics polluted generic core in the artifacts inspected; CVRP-specific content stayed in problem/solver artifacts, traces, metrics, and candidate code.

## Run-Level Accounting

Wrapper and campaign status:

| Field | Value |
|---|---:|
| `WRAPPER_EXIT_STATUS` | 0 |
| `CAMPAIGN_EXIT_STATUS` | incomplete |
| `RUN_VALIDITY_STATUS` | `valid_partial_interrupted` |
| `RUN_COMPLETE` | false |
| `COMPLETED_REQUESTED_ROUNDS` | false |
| `LAST_STOP_REASON` | `scheduler_active_slot_blocked` |
| Started | `2026-06-07T21:04:41Z` |
| Ended | `2026-06-07T21:38:55Z` |

Counter reconciliation:

| Counter | Value |
|---|---:|
| `requested_rounds` | 8 |
| `effective_rounds_completed` | 5 |
| `formal_screened_candidates` | 5 |
| `protocol_evaluated_candidates` | 5 |
| `protocol_stage_counts.screening` | 5 |
| `protocol_stage_counts.validation` | 0 |
| `protocol_stage_counts.frozen` | 0 |
| `proposal_attempts_consumed` | 5 |
| `proposal_attempts_total` | 8 |
| `quality_blocks` | 0 |
| `scheduler_active_slot_blocked_attempts` | 3 |
| `active_slot_blocked_attempt_limit` | 3 |

Integrity:

- `lineage_integrity.status=complete`, `recorded_outcome_count=5`, no degraded outcomes.
- `evidence_integrity.status=complete`.
- `formal_readiness.formal_ready=false`, missing `final_evidence_refs.package`.
- `cross_branch_research_observability.policy=proposal_observability_only`, `decision_input_policy=excluded_from_decision_features`.
- 5/5 formal candidate patch artifacts have top-level `replay_identity.status=complete`, with complete `problem_spec_hash`, `split_manifest_hash`, `seed_ledger_hash`, `patch_digest`, `patch_hash`, `selected_surface`, `protocol_version`, and `raw_metrics_ref`.

LLM trace accounting:

| Request kind | Calls | Prompt tokens | Output tokens | Model |
|---|---:|---:|---:|---|
| `hypothesis_target_intent` | 5 | 139,413 | 895 | `gpt-5.5` |
| `hypothesis` | 8 | 304,795 | 7,221 | `gpt-5.5` |
| `tool_selection` | 22 | 279,264 | 987 | `gpt-5.5` |
| `code` | 5 | 136,633 | 13,733 | `gpt-5.5` |
| total | 40 | 860,105 | 22,836 | `gpt-5.5` |

Runtime evidence policy:

- 5/5 candidate decisions marked runtime as not a standalone optimization signal and excluded runtime from decision features.
- 4/5 had `runtime_signal_role=audit_or_proposal_guidance_only`.
- 3/5 excluded aggregate runtime stats due low cached champion evidence.
- `fresh_champion_required_count=0`; the framework did not force a fresh runtime rerun despite low/cached runtime evidence in most rounds.

## Candidate Analysis By Round

### Round 1: `b4aa5b76`, `route_merge_vns`

Identity:

| Field | Value |
|---|---|
| Branch | `b4aa5b76-2959-48b1-8819-b177c6c10b65` |
| Hypothesis | `341d1a1d-0cf1-4ff6-afb0-200d4c9b85f8` |
| Candidate | `8ba792383798b14e` |
| Action | `modify` |
| Surface | `solver_design` |
| Target file | `policies/baseline_modules/local_search.py` |
| Raw metrics | `metrics/225ba97f-796a-4e4d-b22a-c2eca272e5e4.json` |

Hypothesis:

Add a bounded VNS whole-route absorption operator. The agent argued that the existing VNS portfolio had local distance moves but no explicit route elimination/absorption neighborhood after ALNS repair. The mechanism targeted `fleet_violation` protection first and `total_distance` second.

Code change:

- Registers `_route_merge_vns` in `_default_vns_operators`.
- Adds `_route_merge_vns(solution, context, reserve)`.
- Sorts small/low-load source routes, tries to fully reinsert each source route's customers into other capacity-feasible routes, computes insertion delta, and accepts only complete route elimination with positive cost delta.
- Adds `_insert_delta`.
- Records `route_merge_vns` iteration, move, delta, and phase runtime telemetry.

Gate and protocol behavior:

- Contract: passed.
- Verification: passed.
- Canary: passed.
- Screening: 8 cases, 16 valid pairs.
- Pair/case result: 0 pair wins, 0 pair losses, 16 pair ties; 0 case wins, 0 case losses, 8 case ties.
- Median delta 0.0, CI [0.0, 0.0].
- Runtime evidence high/sufficient, median runtime ratio about 1.00024.
- Telemetry: activation observed in all 16 candidate pairs; `route_merge_vns` phase runtime positive in all 16, phase delta positive in only 3 pairs. No screening objective effect.
- Decision: `continue_explore`.
- Reason codes: `SCREENING_FAIL_WIN_RATE`, `SCREENING_NEUTRAL_SIGNAL_CONTINUE`, `SCREENING_RUNTIME_SATURATION_DIAGNOSTIC`, `SCREENING_RUNTIME_BUDGET_SATURATION`, `BOTH_RUNTIME_BUDGET_SATURATION`.
- Finalizer/lifecycle: retained as `active_no_effect`, active slot remained occupied; allowed next action was clean fork.

Assessment:

This is a real, mechanism-clear algorithm experiment. The code implements the hypothesis, and telemetry proves it ran. The negative result is also real: all objective comparisons tied. The main framework issue starts here only indirectly: this no-effect branch still retained an active slot instead of being parked/released after low-value evidence.

### Round 2: `9237ff13`, `slack_biased_regret_repair`

Identity:

| Field | Value |
|---|---|
| Branch | `9237ff13-4669-4327-b2cf-310c3364f96a` |
| Hypothesis | `5bf701ec-a59a-44be-a25a-4f5558f6a116` |
| Candidate | `377ae7c5504137cc` |
| Action | `modify` |
| Surface | `solver_design` |
| Target files | `policies/baseline_modules/destroy_repair.py`, `policies/baseline_modules/scheduler.py` |
| Raw metrics | `metrics/f8c4c937-575b-4e52-b5fe-d1cb064bb28c.json` |

Hypothesis:

Move improvement pressure earlier into ALNS repair instead of adding another VNS pass. Modify regret-2/3 insertion so near ties prefer lower residual capacity slack waste and lower insertion distance, while preserving fleet feasibility.

Code change:

- Extends `_regret2_insertion`, `_regret3_insertion`, and `_regret_insertion` to accept `context`.
- Adds `slack_biased_regret_repair` iteration/phase telemetry.
- Adds `_slack_biased_insert`, considering up to six near-tie insertion choices by slack and cost.
- Wires repair ops through scheduler lambdas that pass `self.context`.

Gate and protocol behavior:

- Contract: passed.
- Verification: passed.
- Canary: passed.
- Screening: 8 cases, 16 valid pairs.
- Pair/case result: 1 pair win, 3 pair losses, 12 pair ties; 0 case wins, 0 case losses, 8 case ties by gate count.
- Case-level negative signals were recorded for `B-n52-k7.vrp` (delta -2.5) and `E-n101-k8.vrp` (delta -2.0). Pair deltas also included one `P-n101-k4` win and two losses on `E-n101`/`P-n101`.
- Median delta 0.0, CI [-2.5, 0.0].
- Runtime aggregate excluded: champion runtime was fully cached, confidence `low_cached_champion`, runtime pairs 0 for aggregate.
- Telemetry: activation observed; branch evidence summary says pair-level positive signal, but objective effect remained zero at case gate level.
- Decision: `abandon`.
- Reason codes: `SCREENING_FAIL_WIN_RATE`, `BRANCH_LIFECYCLE_ARCHIVE_LINEAGE`, `SCREENING_SOFT_ABANDON_NON_POSITIVE_CI`, `SCREENING_RUNTIME_BUDGET_SATURATION`, `CANDIDATE_RUNTIME_BUDGET_SATURATION`.
- Finalizer/lifecycle: branch was soft lifecycle archived; branch code discarded; evidence retained.

Assessment:

The clean-fork hypothesis was reasonable and materially different from round 1. It used prior feedback correctly: avoid no-effect high-cost VNS by changing repair scoring. The implementation matched the hypothesis. The result is a useful failed experiment: there were pair-level perturbations, but no case-level win and a non-positive CI, so abandoning was appropriate.

### Round 3: `8b8ce21b`, first `phase_budgeted_alns_vns`

Identity:

| Field | Value |
|---|---|
| Branch | `8b8ce21b-ca6f-4433-8a76-2bd67989a1b3` |
| Hypothesis | `9735ab6e-9a40-4373-966a-f3ad92aafa49` |
| Candidate | `5bcd6d5efd210b8c` |
| Action | `modify` |
| Surface | `solver_design` |
| Target file | `policies/baseline_modules/scheduler.py` |
| Raw metrics | `metrics/29967725-d4cd-462f-b28d-833f35b37fa4.json` |

Hypothesis:

Recent experiments were tie-heavy and runtime-saturated. Instead of another neighborhood, change scheduler/runtime policy: run ALNS first, gate VNS after accepted/improving ALNS candidates or sparse checkpoints, and skip VNS near reserve.

Code change:

- Removes unconditional embedded VNS inside candidate construction.
- Adds `phase_budgeted_alns_vns` iteration and phase telemetry.
- Adds `accepted_since_vns`, `vns_checkpoint`, and gated VNS invocation on `current`.
- Records accepted/no-effect VNS moves, feasibility/max-route rollback, and best-improved deltas.

Gate and protocol behavior:

- Contract: passed.
- Verification: passed.
- Canary: passed.
- Screening: 8 cases, 16 valid pairs.
- Pair/case result: 4 pair wins, 3 pair losses, 9 pair ties; 1 case win, 1 case loss, 6 case ties.
- Case signals: strong `E-n101-k8` pair wins (+8, +25) and `P-n101-k4` seed win (+10), but losses on `A-n32-k5` (-43, -12) and `B-n31-k5` (-4).
- Median delta 0.0, CI [-2.0, 5.0].
- Runtime aggregate excluded due low cached champion confidence.
- Decision: `continue_explore`.
- Reason codes: `SCREENING_FAIL_WIN_RATE`, `SCREENING_MARGINAL_SIGNAL_CONTINUE`, `SCREENING_RUNTIME_BUDGET_SATURATION`, `CANDIDATE_RUNTIME_BUDGET_SATURATION`.
- Finalizer/lifecycle: retained as `active_marginal`, establishing the branch-local follow-up path.

Assessment:

This is the best evidence that the agent can make a meaningful mechanism shift: it changed scheduler policy rather than adding another local move, and it generated mixed but real objective movement. It was not strong enough for validation because losses balanced the wins and the gate still failed. The evidence supported a same-branch follow-up.

### Round 4: `8b8ce21b`, candidate-selective `phase_budgeted_alns_vns`

Identity:

| Field | Value |
|---|---|
| Branch | `8b8ce21b-ca6f-4433-8a76-2bd67989a1b3` |
| Hypothesis | `984155ce-034b-4725-99af-f8e169d779ab` |
| Candidate | `1bde89d921efbb93` |
| Action | `modify` |
| Surface | `solver_design` |
| Target file | `policies/baseline_modules/scheduler.py` |
| Raw metrics | `metrics/32a08f1e-f906-4208-b4d4-81c8f8edbc07.json` |

Hypothesis:

Use branch-local feedback from round 3: the first scheduler variant produced mixed gains/losses and runtime pressure. Refine the same mechanism by running VNS only on accepted candidates worth intensification, adding accepted-streak trigger and no-effect backoff.

Code change:

- Adds `accepted_streak`, `vns_no_effect`, `vns_backoff`, and `vns_streak_trigger`.
- Tracks `accepted_better` versus merely accepted moves.
- Gates VNS by best improvement, cheaper-than-current moves, accepted streak, sparse checkpoint, remaining-time margin, and no-effect backoff.
- Resets VNS no-effect/backoff by segment.
- Records `phase_budgeted_alns_vns` telemetry.

Gate and protocol behavior:

- Contract: passed.
- Verification: passed.
- Canary: passed.
- Screening: 8 cases, 16 valid pairs.
- Pair/case result: 3 pair wins, 3 pair losses, 10 pair ties; 0 case wins, 0 case losses, 8 case ties.
- Case-level branch card records positive cases `B-n52-k7.vrp` (+1.0), `E-n101-k8.vrp` (+3.0), `P-n101-k4.vrp` (+7.0), and negative cases `A-n32-k5.vrp` (-21.5), `B-n31-k5.vrp` (-2.0), `P-n40-k5.vrp` (-4.5), each with one seed win/loss and one tie.
- Median delta 0.0, CI [-4.5, 3.0].
- Runtime aggregate excluded due low cached champion confidence and incomplete runtime evidence.
- Telemetry: activation observed; pair-level positive signal; no stable objective effect at case gate.
- Decision: `continue_explore`.
- Reason codes: `SCREENING_FAIL_WIN_RATE`, `SCREENING_ACTIVE_PAIR_WINS_BUT_CASE_FAIL`, `SCREENING_RUNTIME_SATURATION_DIAGNOSTIC`, `SCREENING_RUNTIME_EVIDENCE_INCOMPLETE_PRESSURE`, `SCREENING_RUNTIME_BUDGET_SATURATION`, `CANDIDATE_RUNTIME_BUDGET_SATURATION`.
- Finalizer/lifecycle: retained as `active_weak_positive`; follow-up recommended, but active slot remained occupied.

Assessment:

This is a legitimate branch-local refinement. It was based on historical feedback and remained in the same mechanism family. It reduced the earlier decisive `A-n32` damage but also lost the stable case win; the result is weak positive only as pair-level/mixed case-level evidence. It should not be promoted. It is enough to justify further controlled refinement if the scheduler can continue, but not enough to count as an algorithmic success.

### Round 5: `981a9e0a`, `route_pool_recombine`

Identity:

| Field | Value |
|---|---|
| Branch | `981a9e0a-252d-450d-a6b2-b2ab02a8b757` |
| Hypothesis | `14be99e6-9f14-45ca-91c8-a40fed194837` |
| Candidate | `13a10dbc57179c2b` |
| Action | `create_new` |
| Surface | `solver_design` |
| Target files | `policies/baseline_modules/route_pool.py`, `policies/baseline_modules/scheduler.py` |
| Raw metrics | `metrics/704d4fb0-b20d-4c92-9349-e96ca0febe41.json` |

Hypothesis:

After local-search, repair, and scheduler variants were tie-heavy, introduce a distinct route-set recombination family. Build route pools from incumbent/current/best/accepted candidates, greedily cover customers with high-quality whole routes, fill uncovered customers by regret insertion, and accept only feasible route-limit-preserving total-distance improvements.

Code change:

- Adds new `route_pool.py`.
- Implements `_route_pool_recombine`, `_pool_routes`, `_recompose`, `_insert_uncovered`, and `_insertion_choices`.
- Collects feasible route fragments, scores by cost/demand and edge cost, recomposes route sets under route limits, and rejects infeasible or non-improving recombinations.
- Integrates route-pool recombination after construction and at segment boundaries in scheduler.
- Records `route_pool_recombine` iteration/move/phase telemetry.

Gate and protocol behavior:

- Contract: passed.
- Verification: passed.
- Canary: passed.
- Screening: create-new candidate used 12 cases, 24 valid pairs.
- Pair/case result: 0 pair wins, 0 pair losses, 24 pair ties; 0 case wins, 0 case losses, 12 case ties.
- Median delta 0.0, CI [0.0, 0.0].
- Runtime evidence low cached champion but sufficient; runtime ratio median about 0.9989. Runtime remained proposal/audit guidance only.
- Telemetry: activation observed in 24/24 pairs; `route_pool_recombine` phase improvement count and best delta positive in 3/24 pairs, but no protocol-level objective improvement.
- Decision: `continue_explore`.
- Reason codes: `SCREENING_FAIL_WIN_RATE`, `SCREENING_NEUTRAL_SIGNAL_CONTINUE`, `SCREENING_RUNTIME_SATURATION_DIAGNOSTIC`, `SCREENING_RUNTIME_EVIDENCE_INCOMPLETE_PRESSURE`, `SCREENING_RUNTIME_BUDGET_SATURATION`, `CANDIDATE_RUNTIME_BUDGET_SATURATION`.
- Finalizer/lifecycle: retained as `active_no_effect`; active slot remained occupied.

Assessment:

This was the most diverse mechanism family in the run and a reasonable clean fork from prior failures. The implementation is real and guarded, but screening showed no objective effect. Internal telemetry suggests recombination sometimes improved an intermediate candidate, yet those local effects did not survive to champion comparison. This is useful partial evidence against this first route-pool implementation, not evidence of solver improvement.

## LLM Call Analysis By Session

The run used 10 agentic sessions: 5 hypothesis-only sessions and 5 code sessions. All traces used `gpt-5.5`.

### `b4aa5b76` round 1

Hypothesis session `ad2b1db6-746f-4c19-be13-8083df3a462b`:

- `hypothesis_target_intent`: 23,977 prompt / 176 output tokens. Selected `modify`, `local_search.py`, `route_merge_vns`; intent was to add a local-search route absorption neighborhood.
- `hypothesis`: 29,423 prompt / 868 output tokens. Produced the full bounded whole-route absorption hypothesis with target/protected objectives and telemetry expectations.
- Schema retry: 0. Stop skipped: false.

Code session `a1012da7-9b59-41db-b114-950da0832046`:

- Tool-selection calls: 6. Tools selected in order: `context.read_branch_state`, `context.read_surface`, `context.read_algorithm_file` for `baseline_algorithm.py`, `scheduler.py`, `state.py`, then stop.
- Deterministic prefetch plan: `9f3852733fe0389f`; prefetch included `memory.query`, branch state, surface, and algorithm file context.
- Code call: 28,477 prompt / 1,955 output tokens. Produced exact replacements in `local_search.py`.
- Assessment: context was sufficient and targeted. There was one slightly wasteful read path because it did not read `local_search.py` via tool selection in the visible list, but code still had `target_file_code` evidence. No schema retry, no skipped stop, no invalid planner overhead.

### `9237ff13` round 2

Hypothesis session `04a6754d-ebaa-49fc-9961-139ae7917468`:

- `hypothesis_target_intent`: 26,692 / 206 tokens. Selected `destroy_repair.py`, mechanism `slack_biased_regret_repair`.
- `hypothesis`: first attempt 35,409 / 886 tokens, then retry 38,730 / 857 tokens.
- Schema retry count: 1. This appears to be preview/schema repair overhead, not a quality block.
- Key context: prior route-merge VNS was no-effect and runtime saturated; target shifted to repair phase.

Code session `8396d75c-922e-4825-b524-8267693a840c`:

- Tool-selection calls: 3. Read `local_search.py`, read branch state, stop.
- Deterministic prefetch plan: `5165d957e9f24fbc`; prefetch included `memory.query`, `feedback.query_screening`, `feedback.query_runtime`, and `context.read_algorithm_file`.
- Code call: 26,882 / 2,271 tokens. Modified `destroy_repair.py` and `scheduler.py`.
- Assessment: the code session could have read `destroy_repair.py` explicitly before code, but deterministic prefetch already included relevant feedback/runtime and the final code used the correct file. No code retry, no skipped stop.

### `8b8ce21b` round 3

Hypothesis session `ada44600-c5f4-455f-a4a6-60ca327f5ef5`:

- `hypothesis_target_intent`: 28,984 / 161 tokens. Selected `scheduler.py`, `phase_budgeted_alns_vns`.
- `hypothesis`: first attempt 36,937 / 938 tokens, retry 39,949 / 827 tokens.
- Schema retry count: 1.
- Key context: route-merge and repair variants were high-cost or mixed; change runtime scheduling rather than mechanism neighborhood.

Code session `ab1fb19e-a894-4396-b988-aa0d87e62ea2`:

- Tool-selection calls: 3. Read `local_search.py`, read `destroy_repair.py`, stop.
- Deterministic prefetch plan: `c90f2132d3020110`; prefetch included memory and screening/runtime feedback.
- Code call: 27,613 / 3,421 tokens. Modified `scheduler.py`.
- Assessment: code implemented the selected scheduling mechanism. Planner did not explicitly select `scheduler.py` as a read in this session, which is an avoidable context-selection inefficiency, but the code call still generated a coherent scheduler diff. No code retry, no skipped stop.

### `8b8ce21b` round 4

Hypothesis session `7c5e2b87-54b4-4b11-a8a5-f28b22ac596b`:

- `hypothesis_target_intent`: 30,412 / 175 tokens. Stayed on `scheduler.py`, same mechanism.
- `hypothesis`: first attempt 41,780 / 986 tokens, retry 44,806 / 847 tokens.
- Schema retry count: 1.
- Key context: branch-local feedback from round 3, mixed gains/losses and budget saturation; same-mechanism trigger/backoff refinement.

Code session `e21ba977-922e-4825-b524-8267693a840c`:

- Tool-selection calls: 4. Read `local_search.py`, `destroy_repair.py`, branch state, stop.
- Deterministic prefetch plan: `1a9eb6ae1da66593`; prefetch included memory and screening/runtime feedback.
- Code call: 28,332 / 2,663 tokens. Modified scheduler trigger/backoff logic.
- Assessment: this is the cleanest branch-local follow-up in the run. Tool selection still over-read local_search/destroy_repair relative to scheduler, but branch-state and feedback were appropriate. No code retry, no skipped stop.

### `981a9e0a` round 5

Hypothesis session `b5820912-d1cf-4201-8742-7edf639e6d67`:

- `hypothesis_target_intent`: 29,348 / 177 tokens. Selected `create_new`, `route_pool.py`, mechanism `route_pool_recombine`.
- `hypothesis`: 37,761 / 1,012 tokens. Proposed route-set recombination as a distinct mechanism family.
- Schema retry: 0.
- Key context: all prior variants were tie-heavy; need mechanism diversity beyond scheduler/destroy/local VNS.

Code session `ba79fe23-93f2-4e50-a238-21641ef81197`:

- Tool-selection calls: 6. Read `local_search.py`, `destroy_repair.py`, `scheduler.py`, branch state, surface target preview for `route_pool.py`, then stop.
- Deterministic prefetch plan: `0659a37befd1b39f`; prefetch included memory, screening/runtime feedback, algorithm files, branch state, and target surface.
- Code call: 25,329 / 3,423 tokens. Created `route_pool.py` and integrated it in `scheduler.py`.
- Assessment: context was sufficient and well matched for a new module plus integration. No schema/code retry, no skipped stop.

### Planner Overhead Summary

- Hypothesis preview/schema retries: 3 sessions had 1 retry each; none became quality blocks.
- Tool-selection calls: 22 for 5 code calls. The first and route-pool code sessions used 6 tool-selection calls; two scheduler sessions used 3-4. This is nontrivial planner overhead but traceable and bounded.
- Skipped stop: none observed.
- Invalid planner overhead: no invalid tool-selection outputs found; each code session ended with an explicit stop trace.
- Deterministic prefetch: present for all tool-selection code sessions with manifest/provenance digests. Prefetch consistently included memory and, after round 1, screening/runtime feedback.

## Branch-Level Research Narrative

### `b4aa5b76`: route absorption VNS

The branch hypothesis was reasonable: whole-route absorption is a plausible gap in a VNS portfolio dominated by customer-local moves. The implementation matched the hypothesis and telemetry showed activation. The result was all ties with runtime saturation, so the branch became no-effect. It should have been cheap to park or release after the no-effect evidence. Instead, it remained in an active slot through stop.

### `9237ff13`: repair-phase slack bias

This clean fork was a rational response to `b4aa5b76`: move the same high-level goal earlier into ALNS repair and avoid another VNS route-merge pass. The code implemented the hypothesis. Feedback was negative enough to abandon: 0 case wins, loss signals, and non-positive CI. This branch did not contribute to the final active-slot block because it was abandoned.

### `8b8ce21b`: scheduler/runtime gating

This is the strongest research thread. Round 3 produced mixed but real total-distance movement. Round 4 used that branch-local evidence and refined the same mechanism with candidate-selective VNS and no-effect backoff. The follow-up is historically grounded and mechanically coherent. However, it did not convert mixed pair-level signal into a stable case-level win, and runtime evidence remained low/cached. Keeping it active for further refinement is defensible, but only if active-slot governance can park weaker branches.

### `981a9e0a`: route-pool recombination

This branch was a materially different mechanism family and avoided repeating scheduler/destroy/local VNS changes. The implementation was substantial and guarded. Telemetry showed activation and internal route-pool effects in 3/24 pairs, but the protocol result was all ties. It is useful no-effect evidence for this first route-pool design. Keeping it active after all-tie screening contributed to scheduler blockage.

### Cross-Branch Differences

The agent did not merely repeat one idea:

- `route_merge_vns`: local-search route absorption.
- `slack_biased_regret_repair`: repair scoring.
- `phase_budgeted_alns_vns`: scheduler/runtime gating and then same-mechanism refinement.
- `route_pool_recombine`: solution recombination.

The branch diversity is good enough for partial research-quality evidence. The main limitation is not mechanism duplication; it is that weak/no-effect branches stayed active and exhausted scheduler slots before 8R completion.

## Is The Agent Doing Effective Algorithm Research?

Yes, but only partially and with weak algorithmic results.

Positive evidence:

- Hypotheses identify concrete mechanisms, target files, protected objectives, no-op conditions, runtime strategies, and expected telemetry.
- Code changes are real and mostly aligned with hypotheses.
- Contract/verification/canary passed for all five candidates.
- Telemetry showed mechanisms actually activated.
- Branch-local refinement happened in `8b8ce21b` and used prior feedback.
- Cross-branch diversity emerged after failures.

Negative or limiting evidence:

- No candidate reached validation.
- Most objective evidence is tie-dominated.
- The only promising branch had mixed pair-level gains/losses and no stable gate-level success after refinement.
- Runtime evidence was low/cached for most rounds and explicitly excluded from decision features.
- The system produced 860k prompt tokens for 5 screened candidates, including 22 tool-selection calls and 3 schema retries; traceability is good, but research efficiency is not yet strong.
- Scheduler active-slot behavior prevented the research loop from completing the requested horizon.

The right interpretation is: the agent is capable of mechanism-grounded search, but the completed 5 rounds do not establish algorithm improvement, and the framework stopped before it could test whether further diversification or refinement would help.

## Partial Stop Impact

This is not sufficient as 8R acceptance:

- Requested 8 effective screened candidates; completed 5.
- `formal_readiness` is false due missing final evidence package.
- `run_complete=false`, `completed_requested_rounds=false`.
- The stop reason was not benign max-round exhaustion; it was scheduler active-slot blockage.

What the 5/8 evidence supports:

- Tool-selection manifest/provenance works over 40 traces.
- Formal replay identity works for 5/5 screened candidate artifacts.
- Accounting distinguishes effective screened candidates from proposal/scheduler attempts.
- Contract/verification/canary/protocol path can process real code changes.
- Agent research quality is plausible but not strong.
- Runtime evidence guardrails mostly behaved correctly by excluding low/cached runtime from decision features.

What it does not support:

- 8R campaign acceptance.
- Any conclusion about validation/frozen promotion behavior.
- Any conclusion that active-slot scheduling is robust in longer campaigns.
- Any algorithmic improvement claim for CVRP.

Recommendation:

1. Fix scheduler active-slot release/reclaim or lifecycle-origin marker propagation first.
2. Rerun 8R from a clean campaign after the fix.
3. If the scheduler fix is small and targeted, run a focused scheduler/lifecycle regression before rerun: create three active retained branches with no-effect/weak-positive states, verify a new clean fork can reclaim or park an eligible active slot without terminating the campaign.

## v3 / Scion Boundary Check

Decision boundary:

- Decision artifacts read structured `decision_features_json`, reason codes, gate outputs, runtime policy, and protocol metrics.
- LLM hypothesis text exists in DB/artifacts but is tainted proposal evidence, not promotion input.
- Runtime policy explicitly records `decision_features_excluded=true` for runtime as a standalone optimization signal.
- Cross-branch research observability is explicitly proposal-only and excluded from decision features.

Cross-branch / tainted text:

- Branch cards and history are visible for proposal guidance.
- `cross_branch_research_observability` reports `policy=proposal_observability_only`.
- No evidence shows cross-branch free text being used as Decision input.

Problem boundary:

- CVRP semantics remain in candidate solver files, metrics, hypotheses, and problem artifacts.
- Generic campaign accounting, lineage integrity, and decision reason-code surfaces remain problem-generic.
- The observed scheduler defect is generic resource/lifecycle governance, not CVRP-specific contamination.

Conclusion: the run is v3-consistent on taint/decision boundaries. The blocker is scheduler lifecycle semantics, not a v3 boundary violation.

## Blocking Framework Defects And Recommendations

### Blocker: active-slot reclaim/release can terminate partial campaigns

Evidence:

- Stop: `scheduler_active_slot_blocked`.
- Attempts: `scheduler_active_slot_blocked_attempts=3`, equal to limit.
- Active slots: used 3/3, branches `b4aa5b76`, `8b8ce21b`, `981a9e0a`.
- Last scheduler result: `reason=max_active_branches reached`.
- Scheduler audit metadata: `active_slot_hard_cap_blocked`, `pre_finalizer_scheduler_action=at_capacity`.
- Reclaim metadata: `mode=new_branch_reclaim`, `blocked_reason=decision_origin_lifecycle_marker_missing`, `marker_missing_branch_ids` includes all three active branches.

Impact:

- The run ended at 5/8 despite no quality blocks and no infra/model failures.
- Low/no-effect active branches were not released or parked in time.
- This blocks credible 8R/12R runs because longer runs are more likely to accumulate retained active branches.

Recommended fix:

- Ensure finalizer/lifecycle outcomes that retain no-effect or weak-positive checkpoints also write the marker required by active-slot reclaim.
- Define deterministic reclaim eligibility for active no-effect branches with low-value evidence and for weak-positive branches whose follow-up is not selected.
- Add a regression that asserts the scheduler can either select a valid same-branch follow-up, park/reclaim an eligible active branch, or create a clean fork without hitting the active-slot blocked attempt limit.
- Surface marker absence as a status/integrity warning before it becomes a campaign-stopping condition.

### Non-blocking: tool-selection/context inefficiency

Evidence:

- 22 tool-selection calls for 5 code calls.
- Some code sessions over-read adjacent files or did not visibly select the final target file before code, relying on prefetch/target evidence.
- 3 hypothesis sessions required schema preview retry.

Recommendation:

- Keep provenance as is, but consider a deterministic target-file prefetch for code sessions to reduce planner calls.
- Treat schema retry counts as overhead metrics in future reports.

### Non-blocking: runtime evidence remains low/cached in most rounds

Evidence:

- 4/5 candidates had low cached champion runtime confidence.
- 3/5 excluded runtime aggregate.
- Runtime was excluded from decision features in 5/5.

Recommendation:

- This is acceptable for decision safety but weak for research feedback.
- If runtime saturation keeps guiding proposals, add a policy that either requests fresh champion runtime for repeated runtime-pressure branches or suppresses runtime-saturation guidance after low/cached evidence.

## Final Verdict

The 8R experiment should be classified as a useful partial framework/research audit and a failed 8R acceptance run. Provenance, replay identity, structured accounting, and v3 taint boundaries look good. Algorithm research is real but weak. The blocking issue for continuing to 8R/12R is scheduler active-slot lifecycle/reclaim behavior, specifically the missing decision-origin lifecycle markers that prevented reclaim and caused `scheduler_active_slot_blocked`.

Fix scheduler/lifecycle reclaim first, then rerun 8R. Do not treat this 5/8 run as a completed 8R verification gate.
