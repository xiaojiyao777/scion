# Scion 4R experiment analysis: v04-post-runtime-guidance-4r-gpt55-20260607T062920Z

Run root: `/home/clawd/research/scion-experiments/v04-post-runtime-guidance-4r-gpt55-20260607T062920Z-claw`

Report path: `/home/clawd/research/or-autoresearch-agent/scion/reports/experiments/v04-post-runtime-guidance-4r-gpt55-20260607T062920Z-analysis.md`

This report is based on direct artifact inspection of the run root, including campaign status files, SQLite state, agentic session indexes, per-session transcripts and scratch artifacts, LLM traces, raw metrics, workspace snapshots, and final retained code. It treats the v3 architecture blueprint and onboarding guide as the design baseline:

- `/home/clawd/research/or-autoresearch-agent/scion/design/scion-architecture-v3.md`
- `/home/clawd/research/or-autoresearch-agent/scion/docs/AGENT_ONBOARDING.md`

## 1. Run-level conclusion

The run completed and is valid, but it did not promote a new champion. The campaign reached the requested four effective rounds after eight proposal attempts. Two attempts were blocked before protocol by code-stage model repair failure, and two screened candidates appear to be formal-excluded or not effective in reconciled accounting despite being listed as screened steps. The final retained state is an active marginal branch, not a champion promotion.

| Field | Finding | Evidence |
|---|---:|---|
| Run complete | yes | `/run_status.json`, `/campaign/status.json` |
| Run validity | valid | `/run_status.json` |
| Wrapper exit | 0 | `/exit.txt` |
| Requested rounds | 4 | `/command.txt`, `/campaign/status.json` |
| Effective rounds completed | 4 | `/campaign/status.json`, `/campaign/campaign_summary.json` |
| Campaign steps / proposal attempts | 8 | `/campaign/campaign_summary.json` |
| Formal screened candidates | 4 | `/campaign/status.json`, reconciled accounting |
| Protocol-evaluated candidates | 4 by reconciled accounting; 6 screening experiment rows in DB / metrics | `/campaign/status.json`, `/campaign/scion.db`, `/campaign/metrics/*.json` |
| Proposal quality blocks | 4 recorded; 2 itemized as proposal_block steps | `/campaign/status.json`, `/campaign/campaign_summary.json`, agentic scratch artifacts |
| Model repair failures | 2 | `/campaign/status.json`, failed sessions `1b8d18d9...`, `48c73d42...` |
| Agentic sessions | 14 | `/campaign/agentic_sessions/agentic_session_index.json` |
| LLM trace count | 116 | `/campaign/agentic_sessions/agentic_session_trace_index.json`, `/campaign/llm_traces/*.json` |
| Model | `gpt-5.5` | `/command.txt`, all LLM traces |
| Champion version | 1 | `/campaign/status.json`, `/campaign/scion.db`, `/campaign/champions/champion_v1` |
| Promotion | no | champion table has no `promotion_experiment_id`; final `why_not_promoted` reasons in metrics/status |
| Stop reason | `max_rounds_exhausted` | `/campaign/status.json` |
| Formal readiness | false | reason `normal_campaign_completed_without_formal_final_evidence` in `/campaign/status.json` |

Command evidence in `/command.txt` shows the campaign ran with `SCION_MODEL=gpt-5.5`, `--rounds 4`, `--time-limit-sec 10`, `--agentic-session-timeout-sec 900`, `--disable-early-stop`, and `--agentic-proposal`. `/run.log` ends with `Campaign finished. experiments: 6 champion ver: 1 active branches: 1`.

### Accounting caveat

There is a real reporting ambiguity:

- `/campaign/status.json` and reconciled accounting say `effective_rounds_completed=4`, `formal_screened_candidates=4`, `quality_blocks=4`, `blocked_attempts=4`.
- `/campaign/campaign_summary.json` has 8 campaign steps and marks all 6 screening steps as `screened_experiment_effective=true`.
- The DB and metrics contain 6 screening experiment artifacts.

For run-level conclusion I treat the reconciled accounting in status as authoritative, but the step-level field is ambiguous. This should be fixed because a reviewer cannot map all four recorded quality/blocked counts to itemized block artifacts without inference.

## 2. v3 design baseline used for judgment

The v3 design boundary is the key acceptance criterion:

- LLM proposals, tool observations, branch notes, screening feedback, and cross-branch memory are tainted. They may influence proposal visibility and audit, but must not become free-text Decision inputs.
- Decision must read only deterministic, structured `DecisionFeatures`.
- Contract, Verification, and Protocol are deterministic evidence gates between tainted proposal generation and governance.
- CVRP/VRP-specific facts belong in problem-owned packages, adapters, providers, problem specs, or solver policies. They must not leak into Scion generic core.

This run mostly respected those boundaries. I found no evidence that Decision consumed LLM free text or cross-branch memory text. The retained code changes are in problem-owned policy modules under the experiment workspace, not in Scion generic core.

## 3. Branch-level analysis

### Branch `fd658eab-fab0-4ce2-8201-0e9aef306090`

Research direction: expand bounded local search with `interroute_2opt_segment_exchange`.

Hypothesis chain: the initial hypothesis claimed the baseline VNS had limited inter-route interior segment exchange, so adding short, strictly capacity-feasible, distance-improving segment swaps could reduce total distance without increasing fleet violations. The hypothesis targeted `/policies/baseline_modules/local_search.py`.

State/lifecycle: one screened attempt, then abandoned. DB branch state is `abandoned`, branch code status `quality_regression`, failure codes include `CANDIDATE_RUNTIME_FAILURE` and `SCREENING_RUNTIME_BUDGET_SATURATION`.

Evidence and result: metrics file `/campaign/metrics/1c080ebf-95a9-4700-ba8f-bbb847c52c39.json` has 16 pairs, 15 valid, 1 candidate timeout/failure, pair-level 1 win / 5 losses / 10 ties, runtime confidence high/sufficient, candidate runtime regression pressure. Protocol reasons include `SCREENING_FAIL_WIN_RATE` and `SCREENING_RUNTIME_BUDGET_SATURATION`.

Governance assessment: abandon was consistent with Scion branch governance. The branch explored a plausible new mechanism, but evidence showed runtime failure and quality regression. This is a useful failed branch rather than infra failure.

Learning from history/weak signal: the next branch moved from a broad local-search expansion to a narrower route-merge bridge, suggesting the campaign learned from runtime saturation and did not keep widening the same expensive move family.

### Branch `ade67163-1aba-4eaf-89e3-95cce434ee94`

Research direction: first a narrower local-search bridge (`route_merge_2opt_bridge`), then a repair tie-breaker (`capacity_slack_regret_repair`).

Hypothesis chain:

- `route_merge_2opt_bridge`: after runtime-heavy segment exchange failed, try a more bounded route merge/bridge that only considers short/low-load pairs and does not increase route count.
- `capacity_slack_regret_repair`: after all-tie/no-effect local-search evidence, move attention to destroy/repair tie-breaking with capacity slack and route-closure geometry.

State/lifecycle: first screened candidate continued exploration despite all ties. Second screened candidate abandoned and archived the lineage. DB branch has `abandoned`, code status `discarded`, best checkpoint classified as no-effect before final abandonment.

Evidence and result:

- `/campaign/metrics/8c909b17-f57c-4265-9aeb-9d5ee556de37.json`: 16 valid pairs, all ties, runtime confidence low because champion was cached/fresh champion required. Protocol reasons include `RUNTIME_TIE_FRESH_CHAMPION_REQUIRED` and `SCREENING_RUNTIME_BUDGET_SATURATION`.
- `/campaign/metrics/8cc59f7e-bacc-4619-855f-ffdd4c9e687c.json`: 16 valid pairs, 1 win / 3 losses / 12 ties at pair level, low cached runtime confidence, no stable positive signal. Protocol reasons include `SCREENING_FAIL_WIN_RATE`, `BRANCH_LIFECYCLE_ARCHIVE_LINEAGE`, `SCREENING_SOFT_ABANDON_LOSS_WITHOUT_WIN`, `SCREENING_SOFT_ABANDON_NON_POSITIVE_CI`, and `SCREENING_RUNTIME_BUDGET_SATURATION`.

Governance assessment: the continue after all-tie/no-effect and abandon after loss-skewed weak signal both match branch governance. The branch did not get promoted on empty or noisy evidence.

Learning from history/weak signal: this branch learned from fd658eab's runtime failure by narrowing local search. After no effect, it shifted mechanism surface to repair. That is legitimate branch-local learning, though the second change still failed to produce stable objective improvement.

### Branch `f5f5cbcd-5a90-4c56-86b0-dcfed912a3b1`

Research direction: route-count-aware repair scheduling under mechanism `route_limit_repair_bias`.

Hypothesis chain:

- First hypothesis: avoid rewarding repairs that inflate route count; use route-count then distance lexicographic gating/retry before VNS/SA.
- Refinement hypothesis: after weak-positive, tie-dominated signal, make it a late-activation lexicographic-distance intensifier only after route count is preserved.

State/lifecycle: two code-stage proposal blocks occurred on this branch, both caused by telemetry identity mismatch during model repair. Two screened candidates were evaluated and the branch ended as `parked_lineage`, not abandoned. DB branch shows retry count 2, failure codes `["PROPOSAL","PROPOSAL"]`, branch lifecycle policy blocks 1, best checkpoint `ab8578d4...`, evidence tier weak-positive but incomplete.

Evidence and result:

- Failed proposal block sessions: `1b8d18d9-59c5-4428-a496-091a78b93bb2` and `48c73d42-dec0-4329-a9eb-3da692441980`.
- `/campaign/metrics/366ea896-7f68-437c-82c7-022bab5036e0.json`: 16 valid pairs, 2 wins / 2 losses / 12 ties, low cached runtime confidence, continue explore.
- `/campaign/metrics/8bd78ef5-ae61-490e-8f9c-a354e7e2ef64.json`: 16 valid pairs, 3 wins / 3 losses / 10 ties, runtime evidence incomplete/exhausted, branch parked. Protocol reasons include `SCREENING_FAIL_WIN_RATE`, `BRANCH_LIFECYCLE_PARK_LINEAGE`, `SCREENING_RUNTIME_SATURATION_REROUTE`, `SCREENING_RUNTIME_EVIDENCE_INCOMPLETE_EXHAUSTED`, and `SCREENING_RUNTIME_BUDGET_SATURATION`.

Governance assessment: retrying after proposal blocks was appropriate because no protocol evidence existed yet. Continuing after weak mixed signal and later parking the lineage was also appropriate. The branch governance avoided both premature promotion and repeated same-lineage over-investment.

Learning from history/weak signal: this branch did learn from earlier runtime saturation by moving from local search into scheduler-level gating. It also learned from its own first weak result by narrowing activation. However, the repeated telemetry identity repair failure is framework/agent interaction cost, not a VRP research insight.

### Branch `79800905-3643-4919-91b2-19cd269f5dc3`

Research direction: construction-stage diversification through `savings_seed_diversification`.

Hypothesis chain: after local-search and scheduler/repair changes produced runtime pressure or weak mixed signals, move effect earlier into construction by generating deterministic Clarke-Wright savings seed variants and selecting the best feasible seed.

State/lifecycle: final active branch, status `explore`, code status `active_marginal`, best checkpoint `e9854f1c...`. It is retained but not promoted.

Evidence and result: `/campaign/metrics/beca6321-0883-4718-afdb-aa731dd0acad.json` has 16 valid pairs, 4 wins / 3 losses / 9 ties, case-level 1 win / 1 loss / 6 ties, median delta 0, CI `[0,10]`, runtime confidence low/incomplete. Protocol reasons include `SCREENING_FAIL_WIN_RATE`, `SCREENING_MARGINAL_SIGNAL_CONTINUE`, and `SCREENING_RUNTIME_BUDGET_SATURATION`.

Governance assessment: retaining as active marginal without promotion is consistent. Evidence is not strong enough for champion replacement, but it is the best live branch for another same-mechanism refine/tune/integrate action.

Learning from history/weak signal: this is the clearest learning step in the run. The campaign moved away from expensive post-construction local search and scheduler retries toward cheaper construction diversity. That matches the observed failure pattern.

## 4. Attempt-level timeline: all 8 proposal attempts

The campaign made 8 proposal attempts to complete 4 effective rounds. Each code-generating screened attempt passed contract, verification, and canary checks before protocol. Proposal blocks did not enter protocol and did not count toward effective/formal rounds.

| Attempt | Branch | Session / hypothesis | Kind | LLM sequence | Tools and traces | Candidate intent | Contract / verification / protocol | Decision / lifecycle | Counts? |
|---:|---|---|---|---|---|---|---|---|---|
| 1 | `fd658eab...` | hypothesis `e0dc1a90...`; code session `39a9b6a4...` | screening | hypothesis session `6eed833b...` then code session `39a9b6a4...`; model `gpt-5.5` | hypothesis: 4 tool_selection + target_intent + hypothesis; code: 6 tool_selection + code; transcript used context/problem/file/design/memory/schema/contract/smoke tools | add `interroute_2opt_segment_exchange` to `local_search.py` | contract passed, verification passed, canary passed; protocol failed on win/runtime | abandon; clean fork selected | effective yes; formal yes |
| 2 | `ade67163...` | hypothesis `9a152fee...`; code session `248826e0...` | screening | hypothesis session `4a576ee6...` then code session `248826e0...`; model `gpt-5.5` | hypothesis: 4 tool_selection + target_intent + hypothesis; code: 6 tool_selection + code | add `route_merge_2opt_bridge` to `local_search.py` | contract/verification/canary passed; protocol all ties/no effect, fresh champion required | continue explore; clean fork available | screening yes; likely not formal/effective in reconciled accounting |
| 3 | `ade67163...` | hypothesis `049bbf88...`; code session `c3b61158...` | screening | hypothesis session `8e73f152...` then code session `c3b61158...`; model `gpt-5.5` | hypothesis: 4 tool_selection + target_intent + hypothesis; code: 7 tool_selection + code | modify `capacity_slack_regret_repair` in `destroy_repair.py`, plus scheduler integration | contract/verification/canary passed; protocol failed on weak/lossy evidence | abandon/archive lineage | screening yes; likely not formal/effective in reconciled accounting |
| 4 | `f5f5cbcd...` | hypothesis `fc971dda...`; code session `1b8d18d9...` | proposal_block | hypothesis session `776585fe...` then code session `1b8d18d9...`; model `gpt-5.5` | hypothesis: 4 tool_selection + target_intent + hypothesis; code: 7 tool_selection + 2 code traces due repair | modify `route_limit_repair_bias` in `scheduler.py` | blocked before contract/protocol by code self-check; telemetry identity mismatch | retry same branch | no effective/formal count |
| 5 | `f5f5cbcd...` | hypothesis `fc971dda...`; code session `295e2bc5...` | screening | repair/fresh code attempt after block; model `gpt-5.5` | code: 10 tool_selection + code; inherited hypothesis ledger | route-count/distance gating in `scheduler.py` | contract/verification/canary passed; protocol mixed weak signal | continue explore; same branch eligible | effective yes; formal yes |
| 6 | `f5f5cbcd...` | hypothesis `b5d6037c...`; code session `48c73d42...` | proposal_block | repair-profile hypothesis `120bf410...` then code session `48c73d42...`; model `gpt-5.5` | hypothesis: 4 tool_selection + target_intent + hypothesis; code: 11 tool_selection + 2 code traces due repair | refine `route_limit_repair_bias` in `scheduler.py` | blocked before contract/protocol by same telemetry identity mismatch | retry same branch | no effective/formal count |
| 7 | `f5f5cbcd...` | hypothesis `b5d6037c...`; code session `2d0469e6...` | screening | retry/fresh code attempt; model `gpt-5.5` | code: 8 tool_selection + code; inherited repair hypothesis | late activation route-limit repair bias in `scheduler.py` | contract/verification/canary passed; protocol weak mixed/incomplete | continue then parked lineage | effective yes; formal yes |
| 8 | `79800905...` | hypothesis `4e24bd6b...`; code session `68e399fe...` | screening | hypothesis session `f268ae96...` then code session `68e399fe...`; model `gpt-5.5` | hypothesis: 4 tool_selection + target_intent + hypothesis; code: 10 tool_selection + code | modify `savings_seed_diversification` in `construction.py`, scheduler passes context/reserve | contract/verification/canary passed; protocol marginal | continue explore; active marginal retained | effective yes; formal yes |

## 5. Retry and proposal quality blocks

### What caused retry

The concrete retry events are not protocol-after-continue retries. They are pre-protocol proposal/code-stage retries caused by model repair failure:

- Session `1b8d18d9-59c5-4428-a496-091a78b93bb2`
- Session `48c73d42-dec0-4329-a9eb-3da692441980`

Both targeted branch `f5f5cbcd...` and mechanism `route_limit_repair_bias`. Both generated scheduler code that introduced or increased telemetry for undeclared mechanism identity `alns` while the approved/protected mechanism identity was `route_limit_repair_bias`. The agentic code self-check blocked these patches before contract, verification, protocol, or Decision.

Evidence:

- `/campaign/agentic_sessions/1b8d18d9-59c5-4428-a496-091a78b93bb2/output.json`
- `/campaign/agentic_sessions/1b8d18d9-59c5-4428-a496-091a78b93bb2/scratch/code_retry_failure_detail_0001.json`
- `/campaign/agentic_sessions/48c73d42-dec0-4329-a9eb-3da692441980/output.json`
- `/campaign/agentic_sessions/48c73d42-dec0-4329-a9eb-3da692441980/scratch/code_retry_failure_detail_0001.json`

The first failure artifact reports `code_stage_telemetry_identity_mismatch` and points to a generated `self.context.record_move(...)` site around `scheduler.py` line 178 using or increasing `alns`. The second reports the same class, with generated `record_move("alns", attempted=1, accepted=0)`-style calls around normalized scheduler lines 166/194; the session output also identifies offending generated lines around 173/180/186/212. Both sessions have two `code` LLM traces, which is consistent with model repair being attempted and then failing.

### Quality block reason and reasonableness

These two itemized quality blocks are reasonable. If Scion allowed a patch for mechanism `route_limit_repair_bias` to record new or increased telemetry as `alns`, then downstream audit and DecisionFeatures could attribute evidence to the wrong mechanism. Blocking preserves the v3 taint and deterministic evidence boundary.

There is still a framework usability problem:

- The baseline scheduler already contains legitimate `alns` telemetry.
- The code model copied or extended nearby telemetry twice.
- The model repair loop failed twice to fix the mechanism identity.

That points to a P1/P2 framework issue in code-stage guidance or repair, not a reason to relax the telemetry gate. Better fixes would be to make the allowed telemetry identities explicit in the code prompt, add a targeted repair instruction that rewrites generated telemetry to the protected mechanism only when semantically correct, or present a structured diff-level telemetry lint before asking the model for repair.

### Recorded quality block count mismatch

`/campaign/status.json` records `quality_blocks=4` and `blocked_attempts=4`, while `/campaign/campaign_summary.json` itemizes only two `proposal_block` steps. The two itemized blocks are the telemetry identity failures above. The other two recorded blocks are not separately reconstructable from per-session quality block artifacts. The strongest inference is that reconciled accounting includes two screened-but-not-effective/formal-excluded candidates or derived proposal-quality accounting events, but the evidence is insufficient to map each of the four recorded quality blocks to a concrete LLM output, missing field, or blocked artifact.

This is itself an audit gap. The quality block ledger should have one row per block with `attempt_id`, `session_id`, stage, rule, exact failing payload/check, and whether it consumed retry budget.

## 6. LLM call and agentic session audit

All LLM traces used model `gpt-5.5`. Trace index evidence is in `/campaign/agentic_sessions/agentic_session_trace_index.json` and `/campaign/llm_traces/*.json`.

| Request kind | Count | Prompt tokens | Completion tokens | Interpretation |
|---|---:|---:|---:|---|
| `hypothesis_target_intent` | 6 | 165358 | 1059 | choose target/mechanism intent for hypothesis |
| `hypothesis` | 6 | 221668 | 5454 | produce structured hypothesis |
| `tool_selection` | 94 | 1454342 | 3713 | choose next proposal tool; these are not actual tool executions |
| `code` | 10 | 304138 | 28082 | produce or repair code patch |

Total trace count: 116. The high `tool_selection` volume is a major cost signal. Most sessions spent four to eleven LLM calls just selecting tools.

### Agentic sessions and roles

| Session | Branch | Role in attempt | Request mix | Outcome |
|---|---|---|---|---|
| `6eed833b-3a81-4a16-bc37-996bab29f9cb` | `fd658eab...` | hypothesis for attempt 1 | 4 tool_selection, target_intent, hypothesis | hypothesis awaiting approval |
| `39a9b6a4-8ddf-4f72-85cf-f68080a5b758` | `fd658eab...` | code for attempt 1 | 6 tool_selection, code | completed; screened |
| `4a576ee6-3958-4d28-983a-0a764c33452b` | `ade67163...` | hypothesis for attempt 2 | 4 tool_selection, target_intent, hypothesis | hypothesis awaiting approval |
| `248826e0-84d9-43a1-b9b7-b71c019471b2` | `ade67163...` | code for attempt 2 | 6 tool_selection, code | completed; screened |
| `8e73f152-5546-48f5-a2bc-856fa0f773a6` | `ade67163...` | hypothesis for attempt 3 | 4 tool_selection, target_intent, hypothesis | hypothesis awaiting approval |
| `c3b61158-74d2-4979-a2a4-ca3f9223cd10` | `ade67163...` | code for attempt 3 | 7 tool_selection, code | completed; screened |
| `776585fe-6a28-4058-8ece-927ca2f45169` | `f5f5cbcd...` | hypothesis for attempt 4/5 | 4 tool_selection, target_intent, hypothesis | hypothesis awaiting approval |
| `1b8d18d9-59c5-4428-a496-091a78b93bb2` | `f5f5cbcd...` | code for attempt 4 | 7 tool_selection, 2 code | code_generation_failed; model_repair_failed |
| `295e2bc5-839c-48ca-a24a-c1b4244f0801` | `f5f5cbcd...` | retry code for attempt 5 | 10 tool_selection, code | completed; screened |
| `120bf410-15db-40eb-a544-c332186d492f` | `f5f5cbcd...` | repair-context hypothesis for attempt 6/7 | 4 tool_selection, target_intent, hypothesis | hypothesis awaiting approval |
| `48c73d42-dec0-4329-a9eb-3da692441980` | `f5f5cbcd...` | code for attempt 6 | 11 tool_selection, 2 code | code_generation_failed; model_repair_failed |
| `2d0469e6-306e-417c-b69b-845a1dd3066a` | `f5f5cbcd...` | retry code for attempt 7 | 8 tool_selection, code | completed; screened |
| `f268ae96-2177-4ecd-b038-09e12e177234` | `79800905...` | hypothesis for attempt 8 | 4 tool_selection, target_intent, hypothesis | hypothesis awaiting approval |
| `68e399fe-65c9-4e99-942d-0a9c4c44dab1` | `79800905...` | code for attempt 8 | 10 tool_selection, code | completed; screened and retained marginal |

### Tool selection versus actual tool execution

The 94 `tool_selection` traces are LLM choices, not actual tool executions. Actual proposal tool observations appear in each session transcript under `Proposal tool observation`.

Common tools and purposes:

- `context.list_surfaces`: enumerate allowed proposal surfaces.
- `context.read_problem`: read problem-owned specification/context.
- `context.list_algorithm_files`: list solver policy files.
- `context.read_active_solver_design`: read active solver design.
- `context.read_solver_call_graph`: inspect call graph and legal edit surfaces.
- `context.read_active_solver_map`: map active solver modules.
- `context.read_algorithm_file` / `context.read_algorithm_slice`: inspect concrete policy code.
- `context.read_operator_registry`: inspect available operators.
- `context.read_branch_state`: inspect branch-local state and lifecycle constraints.
- `memory.query`: retrieve tainted proposal-visible cross-branch memory.
- `feedback.query_screening`: retrieve safe screening feedback counts and summaries.
- `feedback.query_runtime`: retrieve screening-derived runtime feedback when available.
- `proposal.schema_preview`: preview proposal schema constraints.
- `proposal.target_permission_preview`: confirm allowed target file/mechanism.
- `proposal.contract_preview`: preview contract expectations.
- `proposal.algorithm_smoke`: run tainted runtime preview/smoke on proposed algorithm changes.

Tool result summary:

- Early sessions had no prior screening feedback; later sessions saw 1/1 through 5/5 screening summaries.
- `memory.query` returned tainted, proposal-safe information only. I found no evidence it entered DecisionFeatures.
- `proposal.algorithm_smoke` passed for completed code sessions. For successful `route_limit_repair_bias` sessions, smoke was diagnostic with `activation_not_observed_diagnostic` but `passed=true`, which was advisory and did not block.
- Code sessions often used inherited hypothesis ledger receipts instead of repeating full hypothesis payloads.

## 7. Final code audit

The final retained candidate is branch `79800905-3643-4919-91b2-19cd269f5dc3`. Comparing `/campaign/champions/champion_v1` with `/campaign/workspaces/79800905-3643-4919-91b2-19cd269f5dc3` shows meaningful retained source changes only in:

- `/campaign/workspaces/79800905-3643-4919-91b2-19cd269f5dc3/policies/baseline_modules/construction.py`
- `/campaign/workspaces/79800905-3643-4919-91b2-19cd269f5dc3/policies/baseline_modules/scheduler.py`

`construction.py` changes:

- `_clarke_wright_savings(instance, target_routes=None)` becomes `_clarke_wright_savings(instance, target_routes=None, context=None, reserve=0.0)`.
- Savings entries carry deterministic perturbation fields such as demand gap and radial gap.
- A helper path builds Clarke-Wright routes from a supplied savings ordering.
- Up to four deterministic seed variants are generated, with a guard that skips diversification on larger instances when no target route limit is active.
- The best feasible lower-cost seed is retained while respecting target-route constraints.
- Telemetry records `savings_seed_diversification` iteration/move/phase information.

`scheduler.py` changes:

- Scheduler passes `context=self.context` and `reserve=reserve` into `_clarke_wright_savings`.
- No Scion generic core files are modified by the retained candidate.
- Existing baseline `record_move("alns")` telemetry remains, but the retained savings patch did not introduce the route-limit telemetry identity failure seen in blocked attempts.

Hypothesis consistency: the final code matches the `savings_seed_diversification` hypothesis. It moves search pressure earlier into construction and uses deterministic variants to improve initial routes before later repair/local-search stages.

Boundary assessment: the retained changes are CVRP/problem-owned solver policy changes inside experiment workspace policy modules. I found no evidence that CVRP/VRP-specific facts were added to Scion generic core.

## 8. Contract, verification, protocol, and promotion results

All six screened candidates passed deterministic pre-protocol gates:

- `contract_result=passed`
- `verification_result=passed`
- `canary_result=passed`
- DB audit checks passed for syntax, interface, unit tests, regression tests, solution consistency, feasibility, objective, nondeterminism, and performance guard.

Screening results by metrics artifact:

| Metrics file | Mechanism | Pair result | Runtime evidence | Decision result | Direct no-promotion reason |
|---|---|---:|---|---|---|
| `1c080ebf-95a9-4700-ba8f-bbb847c52c39.json` | `interroute_2opt_segment_exchange` | 1 win / 5 loss / 10 tie; 1 candidate timeout | runtime confidence high/sufficient but regression/failure | abandon | candidate runtime failure and fail win rate |
| `8c909b17-f57c-4265-9aeb-9d5ee556de37.json` | `route_merge_2opt_bridge` | 0 win / 0 loss / 16 tie | low cached champion / fresh champion required | continue | no objective effect; no promotion evidence |
| `8cc59f7e-bacc-4619-855f-ffdd4c9e687c.json` | `capacity_slack_regret_repair` | 1 win / 3 loss / 12 tie | low cached / insufficient | abandon | fail win rate, soft abandon loss/no positive CI |
| `366ea896-7f68-437c-82c7-022bab5036e0.json` | `route_limit_repair_bias` | 2 win / 2 loss / 12 tie | low cached / fresh champion required | continue | weak mixed signal |
| `8bd78ef5-ae61-490e-8f9c-a354e7e2ef64.json` | `route_limit_repair_bias` | 3 win / 3 loss / 10 tie | low cached / incomplete exhausted | parked lineage | runtime saturation reroute and incomplete evidence |
| `beca6321-0883-4718-afdb-aa731dd0acad.json` | `savings_seed_diversification` | 4 win / 3 loss / 9 tie | low cached / incomplete | active marginal retained | marginal signal, insufficient for promotion |

No candidate was promoted because none produced stable, formal-ready superiority over champion. The final active branch has a marginal signal but median delta 0, mixed losses, and insufficient runtime/formal evidence. Champion version remained 1 with no `promotion_experiment_id`.

## 9. Decision and taint-boundary audit

SQLite table `experiment_events` contains Decision rows with `decision_features_json`. The fields I inspected are structured numeric/enumerated features such as branch id, stage, candidate status, win/loss/tie counts, win rate, median delta, confidence interval, runtime stats, retry count, failure codes, and branch lifecycle state. I did not find LLM proposal text, tool-observation free text, or cross-branch memory text in DecisionFeatures.

Cross-branch research observability evidence:

- `/campaign/campaign_summary.json` has `cross_branch_research_observability.policy=proposal_observability_only`.
- It also records `decision_input_policy=excluded_from_decision_features`.
- Step visibility audit fields include `proposal_visibility_only=true` and `decision_features_excluded=true`.

There is a status summary discrepancy: `/campaign/status.json` has a later compact `cross_branch_research_observability` view with less history, while `/campaign/campaign_summary.json` contains richer source counts and observability summaries. The richer campaign summary supports the intended v3 policy; the compact status view is less useful for audit.

## 10. Framework behavior versus research quality

### Agent research quality issues

- Several mechanisms were plausible but weak: local search extensions and repair/scheduler gates produced mostly ties, losses, or runtime pressure.
- The route-limit branch repeatedly generated code that polluted mechanism telemetry with `alns`. That is partly an agent code-quality failure.
- Some hypotheses reacted to previous evidence in reasonable ways, but none produced a robust improvement under screening.

### Framework mechanism issues

- Quality block accounting is not sufficiently itemized. `quality_blocks=4` cannot be fully reconstructed from concrete block artifacts.
- Step-level `screened_experiment_effective=true` conflicts with reconciled effective/formal counts.
- Tool-selection overhead is high: 94 tool-selection LLM calls versus 6 hypotheses and 10 code calls. This may be acceptable for traceability, but it is a significant context/cost load.
- Telemetry identity repair failed twice on a predictable pattern. The gate is correct, but the repair path needs stronger targeted guidance.
- Runtime evidence was repeatedly low/incomplete because of cached champion/fresh champion requirements and screening runtime saturation. That prevented promotion even when a branch had marginal wins.

### VRP problem difficulty

- The campaign struggled because many candidates were tie-dominated across seeds and instances.
- Small route/distance improvements were mixed with losses on other cases.
- Runtime pressure is real for local-search-heavy changes under a 10-second screening budget.
- The final construction diversification direction appears more promising because it is cheaper and earlier, but evidence is still marginal.

## 11. Recommendation to main session

Do not treat this run as a research success. Treat it as a valid completed 4R campaign that produced one marginal retained branch and several useful negative results, but no champion promotion.

Before moving to an 8R run, I recommend fixing P1/P2 framework observability and repair issues:

1. Add an itemized quality-block ledger keyed by attempt/session/stage/rule/failing artifact.
2. Reconcile step-level `screened_experiment_effective` with formal/effective accounting.
3. Improve code-stage telemetry identity repair for generated patches.
4. Reduce or batch tool-selection calls where the tool path is deterministic from session stage.
5. Make runtime evidence/fresh-champion gating easier to audit from one status artifact.

After those fixes, an 8R follow-up is reasonable, preferably seeded from the final active marginal branch `79800905...` and constrained to same-mechanism refinement of `savings_seed_diversification` or closely related construction-stage diversification. Running 8R immediately is possible, but likely to spend more budget on framework accounting/repair friction before producing formal evidence.

Evidence is strong for:

- run completion and model identity;
- 8 proposal attempts and 14 agentic sessions;
- two concrete code-stage retry/quality blocks;
- no champion promotion;
- retained final code boundary staying outside generic Scion core;
- Decision using structured DecisionFeatures rather than LLM free text.

Evidence is insufficient or ambiguous for:

- exact itemization of all four recorded `quality_blocks`;
- why two screened candidates are excluded from reconciled formal/effective counts while step fields mark them effective;
- full semantic attribution of every screening-runtime saturation code without a unified per-attempt audit table.
