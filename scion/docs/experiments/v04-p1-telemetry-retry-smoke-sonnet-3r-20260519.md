# v0.4 P1 Telemetry Retry Smoke, Sonnet 3R, 2026-05-19

Campaign path:

`/home/clawd/research/scion-experiments/v04-p1-telemetry-retry-smoke-sonnet-3r-20260519T020242Z/campaign`

Analysis scope: read-only artifact inspection of `output.json`, `transcript.json`, `llm_traces`, prompt manifests, and champion snapshot files. No code was changed for this analysis.

## 1. Experiment Overview

This 3-round smoke run did not get any candidate into screening.

- Campaign id: `9b0b567c-3bdc-4206-ac33-e0772fbb846f`.
- Rounds: 3.
- Champion stayed at version 1.
- Stop reason: `max_rounds_exhausted`.
- Budget was not exhausted and circuit breaker did not trip.
- `budget_utilization` remained `0.0`, consistent with all branches failing before protocol screening.
- `verification_failure_breakdown` was empty because no candidate reached verification/screening.
- All three code sessions failed at proposal self-check, specifically `agent_quality_blocked` / `algorithm_smoke_failure`.

High-level result:

1. Semantic retry prompt injection for hypothesis novelty rejection was not exercised in this run. There are no `hypothesis_semantic_retry` prompt manifests and no API-visible prompt contains `## Hypothesis Semantic Retry Feedback`.
2. Code retry feedback did enter API-visible prompts. Failed code attempts 2/3 start with `## Previous Attempt Failed` and include telemetry guard details.
3. CVRP novelty provider still has a false negative for the exact cross-route Or-Opt/segment-chain duplicate shape from round 2.
4. Telemetry guard protected-objective no-regression did not appear over-strict in this run. Failures were activation/effect evidence failures.
5. Activation failures were mostly candidate/code-path issues; effect evidence for conditional mechanisms remains a guard-calibration risk.

## 2. Session and Round Details

### Round 1: `adaptive_destroy_escalation`

Sessions:

- Hypothesis session: `ccbdc7d5-667c-40d0-a7a5-ac7f01d32ecb`
- Code session: `d140e837-7fc0-4366-8cd6-6836bd271b4a`

Hypothesis output:

- `change_locus`: `solver_design`
- `action`: `modify`
- `target_file`: `policies/baseline_modules/scheduler.py`
- `mechanism_changes`: `adaptive_destroy_escalation`
- Claim: fixed destroy-ratio/static segment length cannot adapt destruction intensity after stagnation; add a scheduler-level escalation/decay mechanism.
- Expected telemetry used generic activation/effect paths plus declared mechanism id in `mechanism_changes`.

Hypothesis tools and context:

- Required context was reasonable: `context.list_surfaces`, `context.read_problem`, `context.list_algorithm_files`, `context.read_active_solver_design`, `context.read_solver_call_graph`.
- Planner read `destroy_repair.py`, `local_search.py`, and `acceptance.py`; later grounding read `scheduler.py`.
- Schema and target permission previews passed.
- No semantic novelty retry occurred.

Reasonableness:

- Targeting `scheduler.py` is plausible for destroy-intensity scheduling.
- The hypothesis prose overstates part of the existing baseline by saying the pool only uses fixed weights; the active snapshot shows adaptive operator weights. The actual destroy count/ratio is still fixed, so this is a noisy premise rather than a complete duplicate.

Code output:

- Three code calls were made.
- All three returned a complete replacement for `policies/baseline_modules/scheduler.py`.
- No `additional_changes`.
- The final code records:
  - `context.record_iteration("adaptive_destroy_escalation", 1)`
  - `context.record_move("adaptive_destroy_escalation", ...)`
  - `context.record_phase("adaptive_destroy_escalation", elapsed)`
- The mechanism is wired into the ALNS loop and uses escalation after `_STAGNATION_SEGMENTS`.

Failure point:

- All smoke attempts failed on effect evidence:
  - `TELEMETRY_MECHANISM_EFFECT_NOT_OBSERVED`
  - Missing paths: `solver_algorithm_phase_improvement_counts.adaptive_destroy_escalation`, `solver_algorithm_phase_best_delta.adaptive_destroy_escalation`
- This means the candidate was active enough to reach code smoke but did not produce mechanism-specific improving evidence.

Assessment:

- This looks primarily like candidate quality / smoke-evidence mismatch, not a framework boundary bug.
- It still exposes a calibration question: requiring positive mechanism effect before screening can block conditional mechanisms whose activation is observable but whose improvement depends on smoke instance opportunity.

### Round 2: `cross_route_oropt`

Sessions:

- Hypothesis session: `2cd49c67-3a46-4975-8327-2306aed6bde1`
- Code session: `9bca0868-b9a0-42b9-8f32-ab58e61dcfe9`

Hypothesis output:

- `change_locus`: `solver_design`
- `action`: `create_new`
- `target_file`: `policies/baseline_modules/local_search.py`
- `mechanism_changes`: `cross_route_oropt`
- Claim: VNS has intra-route 2-opt, relocate, Or-Opt 1/2/3, swap, and 2-opt*, but lacks cross-route segment exchange/Or-Opt for chains of 2-3 customers between routes.

Hypothesis tools and context:

- Required solver-design context was present.
- Planner read `local_search.py`, `destroy_repair.py`, and `acceptance.py`.
- The API-visible prompt also included the active solver snapshot/call graph. It explicitly listed:
  - `_or_opt_1`, `_or_opt_2`, `_or_opt_3`
  - `VNS neighborhoods include intra and cross-route moves`
- The champion `local_search.py` confirms `_or_opt(solution, seg_len, ...)` skips same-route destinations and relocates length 1/2/3 segments across routes.

Novelty provider assessment:

- This hypothesis should have been rejected before code generation.
- The current CVRP provider facts are capable of seeing active cross-route Or-Opt 2/3 from the snapshot.
- The false negative comes from text classification: the hypothesis says it will be called after the existing Or-Opt-3 pass, and helper logic treats that as describing an existing Or-Opt improvement rather than as a contradiction/duplicate, even though the same text also says the cross-route segment exchange operator is missing.
- Because no novelty rejection occurred, semantic retry prompt injection was not exercised.

Code output:

- Three code calls were made.
- Attempt 1 passed contract preview, failed algorithm smoke on missing activation for `cross_route_oropt`.
- Attempt 2 failed static contract preview on complexity: uncapped `while restart` loops.
- Attempt 3 passed contract preview, failed algorithm smoke again on missing activation.
- Final code replaced `local_search.py`, added `_cross_route_oropt`, and appended it to `_default_vns_operators()`.
- Final code records `context.record_phase("cross_route_oropt", ...)` and `context.record_iteration("cross_route_oropt", 1)` only when `_cross_route_oropt` is actually reached.

Failure point:

- `TELEMETRY_MECHANISM_ACTIVATION_NOT_OBSERVED`
- Missing paths:
  - `solver_algorithm_context_records.cross_route_oropt_iterations`
  - `solver_algorithm_phase_runtime_ms.cross_route_oropt`

Assessment:

- The framework gave enough active-path context to show the current operator list and scheduler call path.
- The code agent still placed the new operator at the tail and did not make activation robust on smoke cases.
- More importantly, the round should not have reached code. This is a novelty-provider false negative, not merely a weak candidate.

### Round 3: `proximity_cluster_repair`

Sessions:

- Hypothesis session: `a0744345-bdb6-4109-9694-2bac2d74909a`
- Code session: `60a9d66b-4cf1-4f79-becd-d0f21f5cf553`

Hypothesis output:

- `change_locus`: `solver_design`
- `action`: `modify`
- `target_file`: `policies/baseline_modules/destroy_repair.py`
- `mechanism_changes`: `proximity_cluster_repair`
- Claim: existing removal heuristics are customer-oriented; repair insertion is greedy/regret rather than proximity-cluster guided.
- Expected telemetry was mechanism-specific:
  - Activation: `solver_algorithm_context_records.proximity_cluster_repair_iterations`, `solver_algorithm_phase_runtime_ms.proximity_cluster_repair`
  - Effect: `solver_algorithm_phase_improvement_counts.proximity_cluster_repair`, `solver_algorithm_phase_best_delta.proximity_cluster_repair`

Hypothesis tools and context:

- Required solver-design context was present.
- Planner read `destroy_repair.py`, `local_search.py`, and `acceptance.py`.
- Schema and target permission previews passed.
- No semantic retry occurred.

Novelty provider assessment:

- Non-rejection is reasonable here.
- The active solver has Shaw related removal, but the proposal targets a repair/insertion ordering mechanism, not a related-removal destroy operator.
- The provider should not collapse all proximity/cluster language into a Shaw-removal duplicate.

Code output:

- Three code calls were made.
- Final primary change modified `destroy_repair.py`.
- Final `additional_changes` modified `scheduler.py` to import `_proximity_cluster_repair` and add a context-aware wrapper to the `repair_ops` list.
- Final `destroy_repair.py` records `context.record_iteration("proximity_cluster_repair", ...)`.
- Final code does not record `context.record_phase("proximity_cluster_repair", ...)`.
- Effect telemetry is recorded only when scheduler sees a best improvement from the proximity repair operator.

Failure point:

- Attempts alternated between missing activation fields.
- Final failure:
  - `TELEMETRY_ACTIVATION_NOT_OBSERVED`
  - Missing field: `solver_algorithm_phase_runtime_ms.proximity_cluster_repair`

Assessment:

- The code-stage prompt was clear enough: it included exact context telemetry helpers and the expected mechanism fields.
- The agent wired the mechanism into the active repair pool, but did not emit phase runtime.
- This is mostly candidate implementation failure. A static telemetry preview could catch it earlier and give a narrower repair instruction.

## 3. API-Visible Prompt Findings

Hypothesis semantic retry:

- Not validated by this run.
- All hypothesis sessions have only `api_visible_prompt_manifest_0001_hypothesis.json`.
- No prompt manifest has `call_kind=hypothesis_semantic_retry`.
- No hypothesis LLM trace contains:
  - `## Hypothesis Semantic Retry Feedback`
  - `agentic_hypothesis_semantic_rejections`
  - `Mechanism novelty gate rejected`

Code retry feedback:

- Validated.
- Code attempts after preview/smoke failures include `## Previous Attempt Failed` at the top of `user_prompt`.
- The prompt text includes the telemetry guard code, category, mechanism/field, and repair guidance.
- Manifests for code retries include `prior_code_failure` with `omitted=false`.
- Some `agentic_preview_feedback` sections were omitted because of prompt budget, but the concise failure summary still entered the prompt.

## 4. Design-Conforming Behavior

The v3 boundary rules mostly held:

- `proposal/mechanism_novelty.py` is a generic dispatch point; CVRP mechanism semantics are in the problem package and reached through the adapter hook.
- The campaign champion adapter exposes `mechanism_novelty_provider()`.
- All hypotheses kept `change_locus=solver_design`; no component policy became a replacement research surface.
- CVRP problem summary, object model, active solver snapshot, and telemetry field names came from problem/adapter context.
- Code prompts prohibited adapter/runtime edits and kept changes within branch-owned solver modules.
- Telemetry guard failed candidates before screening and provided structured repair guidance.
- Protected-objective no-regression did not generate false failures in this run.

## 5. Why Screening Count Stayed at 0

No branch passed proposal self-check:

1. Round 1 failed algorithm smoke on missing mechanism effect evidence.
2. Round 2 should have been novelty-rejected first; after the false negative it failed code smoke on missing mechanism activation.
3. Round 3 failed code smoke on missing mechanism activation, specifically phase runtime.

Therefore no candidate branch reached protocol screening, no screening feedback rows were produced, and later hypothesis prompts only saw agent-quality failure history.

## 6. Framework Issues to Fix

### P0

1. Fix the CVRP novelty-provider false negative for cross-route Or-Opt segment-chain proposals.
   - The exact round-2 hypothesis should reject as `premise_contradicted` or `duplicate_mechanism`.
   - Do not let "after the existing Or-Opt-3 pass" suppress a missing/duplicate claim when the same text says cross-route segment exchange/Or-Opt 2-3 is absent.
   - Add a regression test using the round-2 hypothesis text and active snapshot evidence.

2. Add an end-to-end semantic retry regression for this duplicate shape.
   - First hypothesis is rejected by `MechanismNoveltyGate`.
   - Next prompt manifest has `call_kind=hypothesis_semantic_retry`.
   - API-visible prompt contains `## Hypothesis Semantic Retry Feedback` and the structured rejection payload.

### P1

1. Add a static telemetry-contract preview for declared mechanism fields.
   - If expected activation includes `solver_algorithm_phase_runtime_ms.<id>`, require an active-path `context.record_phase("<id>", positive_elapsed)` pattern or equivalent.
   - If expected activation includes `solver_algorithm_context_records.<id>_iterations`, require `context.record_iteration("<id>", positive_count)`.
   - This would have caught round 3 before repeated algorithm smoke attempts.

2. Improve activation feedback from algorithm smoke.
   - Distinguish "record call missing" from "record call present but active path not reached".
   - Round 2 likely had record calls but the new operator was not reached during smoke.

3. Calibrate mechanism effect gating.
   - Round 1's effect failure is useful quality feedback, but requiring positive phase-best movement for every conditional mechanism before screening can starve exploration.
   - Consider allowing screening when activation/search effort/protected-objective no-regression are present but smoke effect is absent, or only hard-block effect absence when smoke has a known improvement opportunity.

4. Keep concise preview feedback unomitted in retry prompts.
   - `prior_code_failure` was visible, but some `agentic_preview_feedback` sections were omitted due budget.
   - A compact, always-visible preview-feedback digest would make repair attempts more reliable.

### P2

1. Normalize or reject `create_new` on existing solver module files.
   - Round 2 used `action=create_new` for existing `policies/baseline_modules/local_search.py`, and code output used `action=create`.
   - For branch-owned existing modules this should probably be `modify`, or the prompt should explain that `create_new` means adding a new mechanism inside an existing file.

2. Improve hypothesis prompt quality feedback truncation.
   - Later hypothesis prompts showed agent-quality failures, but key telemetry fields were truncated in the branch history prose.
   - Exact field names should remain visible.

3. Add campaign-level counters for semantic retry opportunities.
   - Report `semantic_retries_attempted`, `mechanism_novelty_rejections`, and `semantic_retry_prompt_visible`.
   - This would make it obvious when a smoke run did not exercise the intended path.

## 7. Recommendation on Running 6 More Rounds

Do not run 6 more rounds immediately.

Run order should be:

1. Fix P0 novelty-provider false negative and add the end-to-end semantic retry prompt regression.
2. Add at least the P1 static telemetry-contract preview for activation fields.
3. Run another 3-round smoke to confirm at least one of:
   - a novelty duplicate is rejected and retried with API-visible semantic feedback, or
   - a non-duplicate candidate passes algorithm smoke and reaches screening.

Only after that should a 6-round run be useful. With the current behavior, a longer run is likely to spend additional rounds on duplicate or telemetry-incomplete candidates and still produce little or no screening evidence.
