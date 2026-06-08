# Fresh 4R CVRP Verification Analysis

Experiment:
`/home/clawd/research/scion-experiments/v04-audit-provenance-replay-verify-4r-gpt55-20260607T202748Z-4r-gpt55-20260607T202748Z-claw/campaign`

Date analyzed: 2026-06-07

Required design references read:

- `scion/design/scion-architecture-v3.md`
- `scion/reports/architecture-audit-v0.4/remediation-status.md`

## Executive Conclusion

This fresh 4R run is valid as a framework verification gate. It completed the requested 4 effective screened rounds, produced 4/4 formal screening candidates, had 0 proposal-quality blocks, recorded 30 LLM traces all on `gpt-5.5`, and wrote complete tool-selection provenance plus complete formal candidate replay identity for all screened candidates.

I do not see a blocking framework defect that should prevent moving to an 8R run. The main remaining risks before 8R are not provenance/accounting failures; they are research-quality and signal-strength risks:

- The agent is doing real algorithm research, but the search is still in a narrow route-compression/repair neighborhood family.
- The only weak positive was `route_compaction_repair` create-new, with 1/12 case-level wins and median delta 0.0; the immediate branch refinement eliminated that weak signal.
- Runtime evidence was often low-confidence because of cached champion runtime, and two candidates excluded runtime aggregates from decision features.
- Screening remains highly tie-dominated, so 8R should check whether the agent diversifies mechanisms and whether fresh champion runtime is requested only as proposal/audit guidance, not as a promotion input shortcut.

## Run-Level Verification

Wrapper and campaign status:

- `WRAPPER_EXIT_STATUS=0`
- `CAMPAIGN_EXIT_STATUS=complete`
- `RUN_VALIDITY_STATUS=valid`
- `RUN_COMPLETE=True`
- `COMPLETED_REQUESTED_ROUNDS=True`
- `LAST_STOP_REASON=max_rounds_exhausted`
- start/end: `2026-06-07T20:27:49Z` to `2026-06-07T20:55:35Z`

Accounting reconciliation:

| Counter | Value |
|---|---:|
| requested_rounds | 4 |
| effective_rounds_completed | 4 |
| formal_screened_candidates | 4 |
| protocol_evaluated_candidates | 4 |
| protocol_stage_counts.screening | 4 |
| proposal_attempts_consumed | 4 |
| quality_blocks | 0 |
| telemetry_failed_experiments | 0 |
| scheduler_active_slot_blocked_attempts | 0 |
| validation/frozen candidates | 0 |

LLM accounting:

| Request kind | Calls | Prompt tokens | Output tokens |
|---|---:|---:|---:|
| hypothesis_target_intent | 4 | 110,570 | 742 |
| hypothesis | 5 | 177,614 | 4,583 |
| tool_selection | 17 | 228,118 | 737 |
| code | 4 | 109,413 | 10,409 |
| total | 30 | 625,715 | 16,471 |

Trace index:

- `agentic_session_trace_index.json`: 8 sessions, 30 traces.
- All traces used `gpt-5.5`.
- Completed code sessions all include `scion-tooling-audit-provenance.v1` with `deterministic_prefetch_plan_id`, `prefetch_tool_names`, `tool_selection_ledger_digest`, and `tool_selection_ledger_ref`.

Formal replay identity:

- 4/4 `candidate.patch.json` artifacts include top-level `replay_identity`.
- Each replay identity has complete `problem_spec_hash`, `split_manifest_hash`, `seed_ledger_hash`, `patch_digest`, `patch_hash`, `selected_surface`, `protocol_version`, and `raw_metrics_ref`.
- All four have `identity_status/status=complete` and empty missing-key lists.

## Candidate Analysis By Round

### Round 1: `9eea8eca`, `route_merge_local_search`

Basic identity:

| Field | Value |
|---|---|
| Branch | `9eea8eca-90f4-424e-9286-71bf55684b62` |
| Hypothesis | `d1c795a9-b07b-459c-a364-d9bf9d2ff380` |
| Action | `modify` |
| Target surface | `solver_design` |
| Target file | `policies/baseline_modules/local_search.py` |
| Patch artifact | `artifacts/formal_candidates/9eea8eca/screening-d1c795a9-b07b-459c-a364-d9bf9d2ff380-9bd6cb552c76f9ef/candidate.patch.json` |
| Raw metrics | `metrics/842f754b-c5c4-488e-8499-c810f12bc4b9.json` |

Hypothesis:

The agent identified that the VNS portfolio had relocate, swap, Or-opt, and tail exchange, but no whole-route compression neighborhood. It proposed `route_merge_local_search`: choose low-load routes, greedily reinsert every customer into other capacity-feasible routes, and commit only if route count/fleet violation improves or total distance improves without harming the protected lexicographic objective.

Implementation:

- Adds `_route_merge_local_search(solution, context, reserve)` to `local_search.py`.
- Registers it in `_default_vns_operators`.
- Copies the solution, empties a candidate source route, reinserts all customers into other feasible routes, checks feasibility and route-count non-regression, then atomically copies the candidate back.
- Records mechanism-specific telemetry: iteration, accepted move, delta, and phase runtime.

Contract, verification, canary, protocol, decision:

- Contract: passed.
- Verification: passed all configured checks. Unit/regression checks were skipped because no paths were configured; syntax, interface, solution consistency, feasibility, objective, nondeterminism, and perf guard passed.
- Canary: passed.
- Screening: 8 cases x 2 seeds = 16 valid pairs.
- Result: 0 case wins, 0 losses, 8 ties; 0 pair wins, 0 losses, 16 ties; median delta 0.0, CI [0.0, 0.0].
- Runtime: median ratio 1.00018, runtime regression rate 0.5, high/sufficient runtime evidence.
- Telemetry: activation observed; effect fields positive only in a few pairs but no objective effect at case level.
- Decision: `continue_explore`.
- Reason codes: `SCREENING_FAIL_WIN_RATE`, `SCREENING_NEUTRAL_SIGNAL_CONTINUE`, `SCREENING_RUNTIME_SATURATION_DIAGNOSTIC`, `SCREENING_RUNTIME_BUDGET_SATURATION`, `BOTH_RUNTIME_BUDGET_SATURATION`.
- Finalizer behavior: retained as `active_no_effect`; branch remained active, with guidance to clean fork or materially change mechanism family rather than repeat the same costly no-effect path.

Assessment:

The hypothesis was mechanically clear and correctly grounded in known local-search gaps. The code implemented the stated mechanism. The negative outcome was not a framework artifact: the mechanism activated but did not change objective outcomes. This is a useful failed experiment.

### Round 2: `850a66e3`, `route_compaction_repair` create-new

Basic identity:

| Field | Value |
|---|---|
| Branch | `850a66e3-1f25-4a28-93e3-83923fde5647` |
| Hypothesis | `171aac32-b8ca-442d-9261-f3c0dc797878` |
| Action | `create_new` |
| Target surface | `solver_design` |
| Target file | `policies/baseline_modules/route_compaction.py` plus `scheduler.py` integration |
| Patch artifact | `artifacts/formal_candidates/850a66e3/screening-171aac32-b8ca-442d-9261-f3c0dc797878-eccb00131cedcec1/candidate.patch.json` |
| Raw metrics | `metrics/3b326897-bca0-408d-8232-e438590673e6.json` |

Hypothesis:

After round 1 showed a tie-dominated, runtime-saturated local-search path, the agent clean-forked to a repair-stage route compaction mechanism. The proposed `route_compaction_repair` acts after ALNS repair and before optional VNS, trying to eliminate low-load routes by reinserting their customers into existing capacity-feasible routes. This was materially different from VNS-local route merge because it changed invocation phase and target file.

Implementation:

- Creates `route_compaction.py`.
- Implements `_route_compaction_repair(solution, max_routes, context, reserve, max_sources=3)`.
- Samples lowest-load source routes, tries full reinsertion into other routes, checks feasibility, route limit, and non-regression guard.
- Integrates it from `scheduler.py`.
- Records mechanism-specific runtime, iteration, move, delta, and improvement telemetry.

Contract, verification, canary, protocol, decision:

- Contract: passed.
- Verification: passed all configured checks.
- Canary: passed.
- Screening: create-new used 12 cases x 2 seeds = 24 valid pairs.
- Result: 1 case win, 0 losses, 11 ties; 4 pair wins, 1 pair loss, 19 ties; median delta 0.0, CI [0.0, 0.0].
- Case-level signal:
  - `P-n60-k10`: win on both seeds, total_distance deltas +7 and +6.
  - `P-n101-k4`: one win and one tie, pair deltas +9 and 0.
  - `A-n39-k5`: one win and one loss, pair deltas +1 and -3, net unstable.
- Runtime: median ratio 0.9978, but champion runtime was partly cached; runtime policy marked this as low-cached-confidence and proposal/audit guidance only.
- Telemetry: activation observed in 24/24 candidate pairs; effect fields positive in 10/24 pairs.
- Decision: `continue_explore`.
- Reason codes: `SCREENING_FAIL_WIN_RATE`, `SCREENING_WEAK_SIGNAL_CONTINUE`, `SCREENING_RUNTIME_BUDGET_SATURATION`, `CANDIDATE_RUNTIME_BUDGET_SATURATION`.
- Finalizer behavior: retained as best-quality checkpoint with `screening_weak_positive_retained`.

Assessment:

This was the best research result in the run. It was not strong enough for validation, but it gave actionable feedback: route compaction can create case-level positive signal on some P instances, while being tie-heavy and runtime-sensitive elsewhere. The branch-local history correctly preserved this as the branch's best checkpoint.

### Round 3: `850a66e3`, `route_compaction_repair` pressure/slack refinement

Basic identity:

| Field | Value |
|---|---|
| Branch | `850a66e3-1f25-4a28-93e3-83923fde5647` |
| Hypothesis | `3bc02ce6-4bca-4cdf-b41d-6bad58e4bf4b` |
| Action | `modify` |
| Target surface | `solver_design` |
| Target file | `policies/baseline_modules/route_compaction.py` |
| Patch artifact | `artifacts/formal_candidates/850a66e3/screening-3bc02ce6-4bca-4cdf-b41d-6bad58e4bf4b-1bfdf9d4af39fcde/candidate.patch.json` |
| Raw metrics | `metrics/c409711a-ad23-4206-9ac8-4cd9d83af36c.json` |

Hypothesis:

The agent used branch feedback from round 2: preserve the P-case weak positives, reduce broad slack activation, avoid A-n39-style regression, and reduce tie-dominated runtime. It proposed a pressure-and-slack gated compactor that activates only under route-limit pressure or when a cheap source-value prefilter predicts nonpositive cost growth.

Implementation:

- Modifies `route_compaction.py`.
- Adds `_source_compaction_growth` to estimate whether a low-load source route can be removed without positive insertion-growth.
- Tightens source screening and acceptance:
  - pressure if route count is at/above route limit,
  - otherwise require sufficient receiver slack and nonpositive estimated growth,
  - no copy-back unless route count drops and objective guard is respected.

Contract, verification, canary, protocol, decision:

- Contract: passed.
- Verification: passed all configured checks.
- Canary: passed.
- Screening: 8 cases x 2 seeds = 16 valid pairs.
- Result: 0 case wins, 0 losses, 8 ties; 0 pair wins, 0 losses, 16 ties; median delta 0.0, CI [0.0, 0.0].
- Runtime: aggregate runtime excluded because champion runtime evidence was low/cached; `fresh_champion_required=True`.
- Telemetry: activation observed in 16/16 pairs; route-compaction effect fields positive in 3/16 pairs, but no objective-level case effect.
- Decision: `continue_explore`.
- Reason codes: `RUNTIME_TIE_FRESH_CHAMPION_REQUIRED`, `SCREENING_RUNTIME_BUDGET_SATURATION`, `CANDIDATE_RUNTIME_BUDGET_SATURATION`.
- Finalizer behavior: current head discarded/no-effect, but branch retained prior weak-positive checkpoint.

Assessment:

This was a legitimate branch-local follow-up. It directly used the previous screening feedback and implemented the stated refinement. The outcome is scientifically useful: the gating reduced regressions but also removed the weak case-level upside. The branch state correctly distinguished the discarded current head from the retained best checkpoint.

### Round 4: `01006eff`, `cluster_slack_regret_repair`

Basic identity:

| Field | Value |
|---|---|
| Branch | `01006eff-4ebe-4e08-9fdc-b2eb41f71248` |
| Hypothesis | `7d51448a-69db-4564-99b2-dba8c62593c8` |
| Action | `modify` |
| Target surface | `solver_design` |
| Target files | `policies/baseline_modules/destroy_repair.py`, `scheduler.py` |
| Patch artifact | `artifacts/formal_candidates/01006eff/screening-7d51448a-69db-4564-99b2-dba8c62593c8-150350125baaaa2d/candidate.patch.json` |
| Raw metrics | `metrics/3bada848-c244-44a3-ab43-ce26f4dbe335.json` |

Hypothesis:

After route compaction remained weak/no-effect, the agent proposed changing ALNS repair ordering instead of post-hoc route merge. `cluster_slack_regret_repair` scores candidate insertions using regret, residual capacity slack, and spatial affinity to the destination route's nearest neighbors. The goal was lower total distance under stable fleet violation.

Implementation:

- Adds `_cluster_slack_regret_repair(solution, removed, rng, context=None, max_routes=None, reserve=0.0)` in `destroy_repair.py`.
- Adds `_route_affinity`.
- Wires the new repair option in `scheduler.py`.
- Falls back to `_regret_insertion` when time reserve is low or feasible insertion/new-route handling fails.
- Records mechanism-specific iteration, move, delta, and phase runtime.

Contract, verification, canary, protocol, decision:

- Contract: passed.
- Verification: passed all configured checks.
- Canary: passed.
- Screening: 8 cases x 2 seeds = 16 valid pairs.
- Result: 0 case wins, 1 case loss, 7 ties; 3 pair wins, 4 pair losses, 9 ties; median delta 0.0, CI [-3.5, 0.75].
- Case-level signal:
  - `B-n31-k5`: case-level positive, one win and one tie, aggregate delta +1.5.
  - `B-n52-k7`: case-level loss, two losses, aggregate delta -3.5.
  - `E-n101-k8` and `P-n101-k4` had mixed seed-level wins/losses, not stable case wins.
- Runtime: aggregate runtime excluded due low cached champion confidence and incomplete runtime evidence.
- Telemetry: activation observed in 16/16; improvement count positive in 14/16, but `solver_algorithm_phase_best_delta.cluster_slack_regret_repair` was positive in 0/16. This produced `TELEMETRY_EFFECT_ZERO_DIAGNOSTIC`.
- Decision: `abandon`.
- Reason codes: `SCREENING_FAIL_WIN_RATE`, `BRANCH_LIFECYCLE_ARCHIVE_LINEAGE`, `SCREENING_SOFT_ABANDON_LOSS_WITHOUT_WIN`, `TELEMETRY_EFFECT_ZERO_DIAGNOSTIC`, `SCREENING_RUNTIME_BUDGET_SATURATION`, `CANDIDATE_RUNTIME_BUDGET_SATURATION`.
- Finalizer behavior: soft lifecycle archive; branch code discarded; evidence retained.

Assessment:

This candidate was a reasonable clean-fork mechanism shift, but the implementation did not produce stable objective effect and created a clear negative case. The telemetry diagnostic is important: the mechanism was active and generated local improvement counters, but the phase best-delta field showed no observed best effect, so the apparent activity should not be treated as algorithmic improvement.

## LLM Call Analysis

### Session/Trace Inventory

| Session | Branch | Status | Trace composition | Role |
|---|---|---|---|---|
| `c5794902` | `9eea8eca` | partial hypothesis | 1 intent, 1 hypothesis | Round 1 hypothesis approval stage |
| `f499443a` | `9eea8eca` | completed | 7 tool-selection, 1 code | Round 1 code generation |
| `21cd038b` | `850a66e3` | partial hypothesis | 1 intent, 2 hypothesis | Round 2 hypothesis, including one retry |
| `7590aad2` | `850a66e3` | completed | 3 tool-selection, 1 code | Round 2 code generation |
| `ec3b825f` | `850a66e3` | partial hypothesis | 1 tool-selection, 1 intent, 1 hypothesis | Round 3 hypothesis with prefetch feedback |
| `7ebd1636` | `850a66e3` | completed | 3 tool-selection, 1 code | Round 3 code generation |
| `21202cfc` | `01006eff` | partial hypothesis | 1 intent, 1 hypothesis | Round 4 hypothesis |
| `c99af739` | `01006eff` | completed | 3 tool-selection, 1 code | Round 4 code generation |

### Round 1 LLM Calls: `route_merge_local_search`

1. `hypothesis_target_intent`, `20260607T202749...`
   - Purpose: select formal target intent.
   - Key context: solver_design surface, CVRP objective, active solver facts showing local search has relocate/swap/Or-opt/tail exchange but no whole-route route merge.
   - Result: `modify local_search.py`, mechanism `route_merge_local_search`, confidence 0.72.
   - Deterministic prefetch: not shown on this trace; hypothesis prompt already had exposed context receipts from static solver reads.

2. `hypothesis`, `20260607T202754...`
   - Purpose: generate formal hypothesis under selected target-intent binding.
   - Key context: same active solver facts, target action/file lock, expected telemetry templates, no prior experiment history on the branch.
   - Result: structured hypothesis with `mechanism_changes=[add route_merge_local_search]`.
   - Validity: mechanism was clear and matched target file.

3. `tool_selection`, `20260607T202814...`
   - Purpose: code-session diagnose. The planner chose `context.read_branch_state`.
   - Deterministic prefetch before call: `memory.query`.
   - Required-context guard: `stop_allowed=false`; missing `context.read_branch_state` and `context.read_surface`.
   - Assessment: valid anti-early-stop guard, not overhead.

4. `tool_selection`, `20260607T202820...`
   - Purpose: read solver_design surface preview.
   - Prefetch so far: `memory.query`, `context.read_branch_state`.
   - Required-context guard still `stop_allowed=false`; surface preview missing.
   - Assessment: valid.

5. `tool_selection`, `20260607T202823...`
   - Purpose: read `policies/baseline_algorithm.py`.
   - Prefetch so far: memory, branch state, surface.
   - Guard required target source before stop.
   - Assessment: valid, though the target was `local_search.py`; reading entrypoint helped integration understanding.

6. `tool_selection`, `20260607T202825...`
   - Purpose: inspect `scheduler.py` for VNS integration.
   - Assessment: valid because the new local-search operator needed call-path/registry integration.

7. `tool_selection`, `20260607T202827...`
   - Purpose: inspect `state.py`.
   - Assessment: valid because the patch manipulates solution routes and rebuilds/copies state.

8. `tool_selection`, `20260607T202830...`
   - Purpose: read full `local_search.py` target preview.
   - Assessment: valid.

9. `tool_selection`, `20260607T202834...`
   - Purpose: stop after required context was satisfied.
   - `stop_allowed=false`: false.
   - Assessment: no skipped-stop bug.

10. `code`, `20260607T202835...`
    - Purpose: generate patch.
    - Result: modify `local_search.py`, code added `route_merge_local_search`.
    - Patch normalization later composed duplicate file changes, but final patch replay identity was complete.

### Round 2 LLM Calls: `route_compaction_repair` create-new

1. `hypothesis_target_intent`, `20260607T203559...`
   - Purpose: select a materially different target after route-merge no-effect.
   - Key context: round 1 no-effect and runtime saturation; active solver facts.
   - Result: `create_new route_compaction.py`, mechanism `route_compaction_repair`, confidence 0.72.

2. `hypothesis`, `20260607T203604...`
   - Purpose: generate first formal hypothesis.
   - Result: included duplicate mechanism changes (`add` and `integrate`) and effect telemetry inconsistent with no-objective-changing/unchanged-incumbent claims.
   - Assessment: useful but not final; schema preview caught the contradiction.

3. `hypothesis`, `20260607T203624...`
   - Purpose: corrected hypothesis retry.
   - Key correction: removes fabricated effect claim for unchanged attempts; keeps activation/budget telemetry.
   - Result: final route compaction hypothesis.
   - Assessment: valid retry, not wasteful overhead.

4. `tool_selection`, `20260607T203645...`
   - Purpose: code-session read `local_search.py`.
   - Prefetch: `memory.query`, `feedback.query_screening`, `feedback.query_runtime`.
   - Guard: `stop_allowed=false`; required source context.
   - Assessment: slightly indirect because target was `route_compaction.py`, but local search was the failed sibling mechanism and relevant contrast.

5. `tool_selection`, `20260607T203651...`
   - Purpose: read branch state.
   - Assessment: valid; branch-local history/target constraints needed for code.

6. `tool_selection`, `20260607T203654...`
   - Purpose: stop after context satisfied.
   - Assessment: valid.

7. `code`, `20260607T203655...`
   - Purpose: create `route_compaction.py` and integrate it.
   - Result: create patch with scheduler integration; final artifact target files include `route_compaction.py` and `scheduler.py`.

### Round 3 LLM Calls: `route_compaction_repair` refinement

1. `tool_selection`, `20260607T204500...`
   - Purpose: pre-hypothesis diagnostic read of current branch `route_compaction.py`.
   - Prefetch: `memory.query`, `feedback.query_screening`, `feedback.query_runtime`.
   - Guard: `stop_allowed=false`; target source required.
   - Assessment: valid and important, because this was a branch-local refinement.

2. `hypothesis_target_intent`, `20260607T204504...`
   - Purpose: bind same-mechanism follow-up.
   - Result: `modify route_compaction.py`, mechanism `route_compaction_repair`, confidence 0.88.
   - Key context: weak-positive checkpoint plus A-n39 instability and runtime saturation.

3. `hypothesis`, `20260607T204508...`
   - Purpose: formal refinement hypothesis.
   - Result: pressure/slack gated compactor; target weakness explicitly names broad slack activation, A-n39 regression, and tie-dominated runtime.
   - Assessment: strong branch-local feedback use.

4. `tool_selection`, `20260607T204527...`
   - Purpose: code-session read `local_search.py`.
   - Prefetch: memory/screening/runtime feedback.
   - Assessment: marginally less direct than reading `route_compaction.py`; however inherited context already had route_compaction and branch state, and local_search remained relevant for sibling contrast and integration.

5. `tool_selection`, `20260607T204530...`
   - Purpose: read branch state.
   - Assessment: valid.

6. `tool_selection`, `20260607T204533...`
   - Purpose: stop after required context.
   - Assessment: valid.

7. `code`, `20260607T204535...`
   - Purpose: generate modification.
   - Result: implements `_source_compaction_growth` and stricter activation/acceptance.

### Round 4 LLM Calls: `cluster_slack_regret_repair`

1. `hypothesis_target_intent`, `20260607T205027...`
   - Purpose: select clean-fork material-difference target after route compaction no-effect/current-head discard.
   - Result: `modify destroy_repair.py`, mechanism `cluster_slack_regret_repair`, confidence 0.73.
   - Key context: prior route-compaction/local-search attempts; repair phase not yet tried.

2. `hypothesis`, `20260607T205049...`
   - Purpose: formal hypothesis.
   - Result: cluster/slack-biased regret repair, targeting total_distance while preserving fleet_violation.
   - Assessment: valid new mechanism family; grounded in known regret2/regret3 limitations.

3. `tool_selection`, `20260607T205108...`
   - Purpose: code-session read `local_search.py`.
   - Prefetch: memory/screening/runtime feedback.
   - Guard: `stop_allowed=false`; required source context.
   - Assessment: target was `destroy_repair.py`, so this read was indirect. It was still defensible as prior failed sibling context, but the report should track this as mild planner overhead compared with directly reading `destroy_repair.py`.

4. `tool_selection`, `20260607T205110...`
   - Purpose: read branch state.
   - Assessment: valid.

5. `tool_selection`, `20260607T205113...`
   - Purpose: stop after required context.
   - Assessment: valid.

6. `code`, `20260607T205114...`
   - Purpose: generate patch.
   - Result: modifies `destroy_repair.py` and scheduler integration; final artifact target files include both.

### Tool Selection Quality

Tool-selection behavior is acceptable for 8R:

- No tool-selection trace failed.
- All code sessions have deterministic prefetch provenance and a tool-selection ledger.
- `stop_allowed=false` appeared when required context was missing and successfully forced another tool call.
- Actual `STOP` calls happened only after required context was satisfied.
- No skipped stop or invalid planner stop was observed.

Observed inefficiencies:

- Round 1 used 7 tool-selection calls before code, including repeated/indirect reads.
- Rounds 3 and 4 code sessions read `local_search.py` first even when the target was `route_compaction.py` or `destroy_repair.py`; prior context made this tolerable, but 8R should monitor whether planner-selected source reads converge on the actual target file faster.
- Cache hit rate was low overall: 1.66%, with tool-selection hit rate 3.03%. This is cost/performance risk, not a correctness defect.

## Branch-Level Research Narrative

### Branch `9eea8eca`: VNS route merge

Hypothesis reasonableness:

- Reasonable. The solver facts showed local search lacked a whole-route absorption move.
- Mechanism was concrete and compatible with CVRP objectives.

Implementation fidelity:

- Good. The code implements exactly the route-elimination local search described.

Outcome and follow-up:

- No objective effect across 8 cases, all ties.
- Runtime saturation diagnostics appeared.
- Branch remains active_no_effect but with guidance to clean fork or materially change mechanism rather than repeat unchanged local search.

### Branch `850a66e3`: repair-stage route compaction

Hypothesis reasonableness:

- Stronger than round 1 because it moved from VNS to post-repair compaction based on failed local-search feedback.
- The create-new action was materially distinct and used a different activation path.

Implementation fidelity:

- Good. The code creates a repair-stage module and scheduler integration.

Follow-up quality:

- Round 2 produced a weak positive: 1/12 case wins, no losses, but median delta 0.
- Round 3 used exactly that feedback: preserve P-case gains, reduce A-n39 regression, reduce broad activation.
- The refinement removed all case-level signal, which is a negative result but a coherent follow-up.

Branch status:

- Best checkpoint retained: weak-positive route compaction.
- Current head discarded/no-effect.
- Runtime aggregate excluded/fresh champion required for the current head because champion runtime was cached and screening tied.

### Branch `01006eff`: destroy/repair cluster-slack regret

Hypothesis reasonableness:

- Reasonable clean fork. It moved to repair-ordering rather than route compaction and explicitly avoided prior mechanism families.
- The mechanism was plausible for total_distance improvements under stable fleet_violation.

Implementation fidelity:

- Mostly good. The code added the intended repair scoring and scheduler integration.
- However, the telemetry outcome showed a mismatch between local improvement counters and phase best-delta effect.

Outcome and follow-up:

- 0 case wins, 1 case loss, 7 ties.
- Soft-archived/abandoned with code discarded.
- This is the correct lifecycle response.

## Is The Agent Doing Effective Algorithm Research?

Yes, with caveats.

Evidence that the research loop is real:

- Hypotheses name mechanisms, objective targets, protected objectives, no-op conditions, runtime caps, and expected telemetry.
- Code changes implement the proposed mechanisms rather than only changing metadata or instrumentation.
- Branch-local feedback is visible and used. The round 3 refinement explicitly responds to round 2's P-case gains, A-n39 instability, and runtime saturation.
- Cross-branch differences are meaningful: VNS local search, repair-stage compaction, and destroy/repair regret ordering are distinct phases/families.
- Protocol feedback is interpreted at case level, not only by token or tool count.

Caveats:

- The search space is still narrow. All candidates are route compression or repair-ordering variants around the same CVRP bottleneck.
- The agent has not yet shown a sustained path from weak signal to stronger signal. The one weak-positive checkpoint was not improved by refinement.
- Runtime signal is being treated carefully, but runtime saturation is common and can mask objective mechanisms.
- Many cases tie exactly, so 8R must test whether the agent can escape tie-heavy local changes.

My judgment: the agent is doing valid early-stage algorithm research, but the algorithmic improvement signal is weak. The framework is ready for a longer 8R verification; the agent's search quality should be the main thing to audit there.

## v3 / Scion Boundary Check

Decision boundary:

- No evidence that Decision read LLM free text directly.
- Formal decisions are recorded via structured `decision_features_json`, numeric screening outcomes, gate booleans, reason-code arrays, runtime policy structures, and lifecycle reason codes.
- `hypothesis_text` and proposal artifacts are retained as tainted/proposal data, but decisions use structured fields.

Cross-branch and tainted text:

- Cross-branch history appears in branch cards and proposal/session context as proposal visibility/guidance.
- Material-difference and runtime-pressure records explicitly include `proposal_visibility_only=true` and `decision_features_excluded=true`.
- Runtime policy also marks `standalone_optimization_signal=false` and `decision_features_excluded=true` where appropriate.
- This matches the v3 rule: tainted text and cross-branch observations may guide proposal visibility, not deterministic promotion.

Problem boundary:

- CVRP-specific semantics appear in problem artifacts, adapter-rendered context, solver workspaces, metrics, and candidate files.
- The generic campaign/status structures use generic fields: `selected_surface`, `decision_features`, reason codes, protocol counts, replay identity, runtime policy.
- I did not see evidence in this run's artifacts that generic core decisions depend on CVRP-specific free text. CVRP terms such as `fleet_violation`, `total_distance`, case ids, and mechanism names occur in problem/candidate/metric surfaces where expected.

Replay and provenance boundary:

- Formal replay identity is complete in candidate artifacts and lineage audit payloads.
- Tool-selection provenance is audit-only and traceable.
- The remediation goals from `remediation-status.md` are satisfied for this fresh 4R: accounting, prompt/tool provenance, replay identity, and case-level naming are present and machine-readable.

## 8R Recommendation

Recommendation: proceed to 8R.

I do not find a blocking framework defect. The run validates the remediation targets:

- Valid completed run.
- 4/4 formal screened candidates.
- 0 quality blocks.
- 30/30 traces on `gpt-5.5`.
- Tool-selection provenance complete for completed sessions.
- Formal replay identity complete for all candidates.
- Contract, verification, and canary gates passed for all four formal candidates.
- Decision/finalizer behavior is consistent with structured evidence.
- Case-level gate aliases and concrete positive/negative case visibility are present.

Risks to watch in 8R:

1. Research diversity: require material movement beyond repeated route-compression variants if tie/no-effect persists.
2. Weak-signal handling: check whether retained weak-positive checkpoint guidance helps or traps the agent in low-value refinement.
3. Runtime evidence: watch `fresh_champion_required`, `runtime_aggregate_excluded`, and `low_cached_champion` counts; these should remain proposal/audit guidance unless fresh high-confidence runtime becomes available.
4. Planner efficiency: monitor indirect target-file reads and repeated tool-selection calls. Not a blocker now, but cost can grow in 8R.
5. Telemetry semantics: verify effect fields correspond to objective movement, especially after the `cluster_slack_regret_repair` effect-zero diagnostic.
6. v3 boundary drift: continue checking that cross-branch text remains `proposal_visibility_only` and `decision_features_excluded`, and that no CVRP semantics enter generic core decision schemas.

## Files And Tables Checked

Primary files:

- `scion/design/scion-architecture-v3.md`
- `scion/reports/architecture-audit-v0.4/remediation-status.md`
- `campaign/run_status.json`
- `campaign/exit.txt`
- `campaign/status.json`
- `campaign/campaign_summary.json`
- `campaign/agentic_sessions/agentic_session_trace_index.json`
- `campaign/agentic_sessions/agentic_session_index.json`
- 8 `agentic_sessions/*/{output.json,transcript.json}` files
- 30 `llm_traces/*.json` files
- 4 `artifacts/formal_candidates/*/screening-*/candidate.patch.json` files
- 4 `artifacts/formal_candidates/*/screening-*/candidate.diff` files
- `artifacts/formal_candidates/index.jsonl`
- 4 formal protocol metrics JSON files:
  - `metrics/842f754b-c5c4-488e-8499-c810f12bc4b9.json`
  - `metrics/3b326897-bca0-408d-8232-e438590673e6.json`
  - `metrics/c409711a-ad23-4206-9ac8-4cd9d83af36c.json`
  - `metrics/3bada848-c244-44a3-ab43-ce26f4dbe335.json`
- SQLite DB `scion.db` tables:
  - `experiment_events`
  - `hypotheses`
  - `branches`

Counts checked:

- 4 formal candidate artifacts.
- 4 formal candidate diffs.
- 4 raw formal screening metrics files.
- 4 DB screening experiment rows.
- 4 hypothesis DB rows.
- 8 agentic sessions.
- 30 LLM traces.
- 4 completed code sessions with tool-selection provenance.
- 4 complete replay identities.
