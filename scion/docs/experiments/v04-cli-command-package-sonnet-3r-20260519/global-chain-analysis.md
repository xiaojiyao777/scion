# v0.4 CLI Command Package Sonnet 3R - Global Chain Analysis

Analysis scope: read-only inspection of campaign artifacts, database rows, session indexes, compact transcripts, prompt manifests, and CLI entrypoint wiring. Raw prompt/transcript content was not reviewed beyond short structured fields and summaries.

Campaign path:

`/home/clawd/research/scion-experiments/v04-cli-command-package-sonnet-3r-20260519T073734Z/campaign`

## Campaign Facts

- Campaign id: `51935831-70bf-4188-989f-eea0098a1a6e`.
- Launch command: `python -m scion.cli.main run ... --rounds 3 --disable-early-stop --agentic-proposal --agentic-session-timeout-sec 600`.
- Model env: `SCION_MODEL=claude-sonnet-4-6`.
- `status.json`: `n_steps=3`, `n_experiments=0`, `total_rounds=3`, `stopped_reason=max_rounds_exhausted`.
- `campaign_summary.json`: `total_rounds=3`, `n_active_branches=0`, `champion_version=1`, `champion_weight_revision=0`, `budget_utilization=0.0`, `verification_failure_breakdown={}`.
- Frozen budget was untouched: `used=0`, `limit=2`, `remaining=2`.
- No balance/circuit stop: `balance_exhausted=false`, `circuit_breaker_tripped=false`.
- Final closure was non-formal: `final_evidence_refs.status=non_formal_final_evidence_closed`, because no formal final evidence package was produced.
- Coverage stayed inside the intended surface: `action_locus_coverage={"modify/solver_design": 3}`, `family_coverage={"solver_design": 3}`.

High-level result: the campaign ran three rounds, but no candidate escaped the agentic proposal/code-quality smoke layer into campaign-level experiment execution. Therefore `n_experiments=0` is expected from the stored artifacts.

## Artifact Map

Core artifacts:

- `status.json`: final state, including `n_steps=3`, `n_experiments=0`, and last result reason `agent_quality_blocked`.
- `campaign_summary.json`: three round step records with hypothesis previews, failure stages, primary failure summaries, and proposal session refs.
- `scion.db`: 1 branch, 3 hypotheses, 6 agentic proposal session events, 1 champion, 0 weight optimizations.
- `run.log`: three "agentic output rejected" lines, then campaign finish with `experiments: 0`.
- `agentic_sessions/agentic_session_index.json`: six session index entries, two per round.
- `agentic_sessions/<session>/output.json`: structured hypothesis/code-session results.
- `agentic_sessions/<session>/transcript.json`: compact transcript plus failure ledger.
- `agentic_sessions/<session>/scratch/api_visible_prompt_manifest_*.json`: 12 prompt manifest files total, with prompt hashes and section statuses, `raw_prompt_saved=false`.
- `llm_traces/`: 39 trace files: 27 tool-selection, 3 hypothesis, 9 code.
- `archive/`, `workspaces/`, `metrics/`: present but empty. This matches pre-experiment rejection.

Artifact validation:

- All six session index entries point to existing `output.json`, `transcript.json`, and referenced prompt manifests. Missing artifact count was 0 for all sessions.
- Prompt manifest refs were complete: one hypothesis manifest for each hypothesis-only session, three code manifests for each failed code session.
- API-visible manifests did not save raw prompts; they recorded prompt hashes, section names, section statuses, truncation/omission state, and observation ids.
- All six `output.json` artifacts had `self_check.schema_valid=true`.
- The three code sessions had `self_check.contract_preview_passed=true`; the three hypothesis-only sessions had no contract preview result because they intentionally stopped at approval handoff.

## DB/Event Chain

Database row counts:

| Table | Count | Interpretation |
|---|---:|---|
| `branches` | 1 | Single campaign branch. |
| `hypotheses` | 3 | One rejected hypothesis per campaign round. |
| `experiment_events` | 6 | Agentic proposal session events only, not formal experiment events. |
| `champions` | 1 | Initial champion only. |
| `weight_optimizations` | 0 | No promotion or tuning path reached. |

Branch:

- Branch `b717b08e-0f71-4709-b735-ba1325354870` ended `state=abandoned`.
- `failure_codes=["MAX_ROUNDS_EXHAUSTED"]`.
- `retry_count=0`, `pending_retry=0`, `blocked_rounds=0`, `consecutive_llm_retries=0`, `infra_block_count=0`.
- Champion hash stayed at the initial snapshot; no `current_code_hash` or `last_clean_code_hash` was recorded for a candidate branch.

Hypotheses:

| Round | Hypothesis id | Status | Target | Mechanism ids |
|---:|---|---|---|---|
| 1 | `8aa737d7-dda1-4f6b-840f-9aa442ca8e7b` | `rejected` | `policies/baseline_modules/destroy_repair.py` | `capacity_first_regret_repair`, `repair_selector_fleet_violation_check` |
| 2 | `2d50f03d-141a-4938-a5ff-3925ed23b97f` | `rejected` | `policies/baseline_modules/local_search.py` | `vns_cross_route_tail_swap`, `vns_local_search_neighborhoods` |
| 3 | `d6f7aed4-597a-4c46-8c21-28c00ce30d7e` | `rejected` | `policies/baseline_modules/scheduler.py` | `alns_phase_gate`, `adaptive_weight_reset_on_feasibility`, `sa_temperature_phase_switch` |

Event chain:

| Round | Event id | Session | DB stage | DB result summary |
|---:|---|---|---|---|
| 1 | `081d558c-967b-4323-a49d-950c05b81c72` | `ed28c780-ab4b-4a5a-9c0e-d852b3b1f1a2` | `agentic_proposal` | `partial_hypothesis_only`, failure category `contract_boundary_failure`, stage `hypothesis_awaiting_approval`, `contract_result=not_run` |
| 1 | `093ed4c7-333a-4d86-a614-1262d045ed66` | `926ff944-e771-4e13-967b-17a558e02ac7` | `agentic_proposal` | `failed`, `termination_reason=code_generation_failed`, `contract_result=passed`, `verification_result=not_run`, failure category `algorithm_smoke_failure` |
| 2 | `95a5513d-5964-4e91-be58-5e9952cec01f` | `fd357287-65c0-4bbc-8942-c89fc4453ab5` | `agentic_proposal` | `partial_hypothesis_only`, stage `hypothesis_awaiting_approval`, `contract_result=not_run` |
| 2 | `7640a17b-b686-4460-bc37-581033831671` | `3626e95a-ba9e-4c9d-a176-6af44266411e` | `agentic_proposal` | `failed`, `termination_reason=code_generation_failed`, `contract_result=passed`, `verification_result=not_run`, failure category `algorithm_smoke_failure` |
| 3 | `26d4dc47-0378-41e5-af12-8292b4dc3117` | `f54a32a8-7879-46a4-b714-d8720be03737` | `agentic_proposal` | `partial_hypothesis_only`, stage `hypothesis_awaiting_approval`, `contract_result=not_run` |
| 3 | `9c5469b0-f454-48bf-8ca1-6b115c0929a2` | `3c335532-a3d5-4952-a1d2-8f96a02df787` | `agentic_proposal` | `failed`, `termination_reason=code_generation_failed`, `contract_result=passed`, `verification_result=not_run`, failure category `algorithm_smoke_failure` |

There are no `event_kind='experiment'` rows, no `raw_metrics_ref`, no decisions, no screening metrics, and no verification-passed rows. The DB therefore supports the same conclusion as `status.json`: all activity ended before formal campaign experiments.

## Agentic Session Chain

Each round used two agentic sessions with the same idempotency key:

1. Hypothesis session: `partial_hypothesis_only`, stopped at `hypothesis_awaiting_approval`.
2. Code session: `failed`, stopped at `code_generation_failed` after proposal self-check smoke failures.

Session budget/config:

| Round | Phase | Session | Status | Termination | Tool calls | Preview calls | Observation chars | Prompt manifests | Failure ledger |
|---:|---|---|---|---|---:|---:|---:|---:|---|
| 1 | hypothesis | `ed28c780-ab4b-4a5a-9c0e-d852b3b1f1a2` | `partial_hypothesis_only` | `hypothesis_awaiting_approval` | 12 | 2 | 74459 | 1 | 1 entry, `contract_boundary_failure` |
| 1 | code | `926ff944-e771-4e13-967b-17a558e02ac7` | `failed` | `code_generation_failed` | 14 | 8 | 76153 | 3 | 2 entries, attempts 0 and 2, `algorithm_smoke_failure` |
| 2 | hypothesis | `fd357287-65c0-4bbc-8942-c89fc4453ab5` | `partial_hypothesis_only` | `hypothesis_awaiting_approval` | 12 | 2 | 74808 | 1 | 1 entry, `contract_boundary_failure` |
| 2 | code | `3626e95a-ba9e-4c9d-a176-6af44266411e` | `failed` | `code_generation_failed` | 14 | 8 | 77257 | 3 | 3 entries, attempts 0/1/2, `algorithm_smoke_failure` |
| 3 | hypothesis | `f54a32a8-7879-46a4-b714-d8720be03737` | `partial_hypothesis_only` | `hypothesis_awaiting_approval` | 13 | 2 | 84865 | 1 | 1 entry, `contract_boundary_failure` |
| 3 | code | `3c335532-a3d5-4952-a1d2-8f96a02df787` | `failed` | `code_generation_failed` | 15 | 8 | 86554 | 3 | 3 entries, attempts 0/1/2, `algorithm_smoke_failure` |

Tool loop config was consistent across sessions:

- `max_steps=30`
- `max_tool_calls=24`
- `max_code_tool_calls=6`
- `max_code_repair_attempts=2`
- `max_code_generation_timeout_retries=1`
- `max_wall_time_sec=600.0`
- `max_observation_chars=192000`
- `max_repeated_tool_calls=2`

Prompt manifests:

- Hypothesis calls used `phase=draft_hypothesis`, `call_kind=hypothesis`, one manifest per round.
- Code calls used `phase=draft_patch`, `call_kind=code`, three manifests per failed code session.
- All manifests had `raw_prompt_saved=false`.
- All manifests showed `agentic_tool_observations` as truncated. Later code retry manifests also listed `agentic_tool_observations` and `agentic_preview_feedback` as omitted while still preserving hashes/observation ids. This is sufficient for provenance hashes, but not enough to reconstruct exact prompts.

## Round Chain Map

| Round | Hypothesis trace | Code attempts | Failure reason | Artifact refs / DB evidence | Design interpretation |
|---:|---|---|---|---|---|
| 1 | Hypothesis `8aa737d7...`, target `destroy_repair.py`, mechanisms `capacity_first_regret_repair` and `repair_selector_fleet_violation_check`. | Code session `926ff944...`, three prompt manifests, two recorded smoke failures. | Final failure: `agent_quality_blocked` / `algorithm_smoke_failure`; runtime audit reported `solver_algorithm_errors=1` in candidate solve path. Short guidance explicitly points to `_Solution`/`_Route` object model misuse and says repair candidate algorithm code, not protocol or adapter files. | Summary step round 1; DB events `081d...` and `093e...`; session refs `ed28...` and `926...`; run.log first rejection line. | Correct fail-closed behavior. Contract preview passed in code session, but formal protocol/screening was never run. Failure is candidate code quality/object-model mismatch, not CLI or protocol failure. |
| 2 | Hypothesis `2d50f03d...`, target `local_search.py`, mechanisms `vns_cross_route_tail_swap` and `vns_local_search_neighborhoods`. | Code session `3626e95a...`, three prompt manifests, three smoke failures. | Final failure: telemetry guard found no activation evidence for `vns_cross_route_tail_swap`; missing runtime paths included `solver_algorithm_context_records.vns_cross_route_tail_swap_iterations` and `solver_algorithm_phase_runtime_ms.vns_cross_route_tail_swap`. | Summary step round 2; DB events `95a...` and `7640...`; session refs `fd357...` and `3626...`; run.log second rejection line. | Boundary is respected, but agent failed to make declared mechanism observable in smoke. This is a proposal-code/smoke mismatch. No decision or screening evidence exists. |
| 3 | Hypothesis `d6f7aed4...`, target `scheduler.py`, mechanisms `alns_phase_gate`, `adaptive_weight_reset_on_feasibility`, `sa_temperature_phase_switch`. | Code session `3c335532...`, three prompt manifests, three smoke failures. | Final failure: telemetry guard found no activation evidence for `adaptive_weight_reset_on_feasibility`; missing runtime paths included `solver_algorithm_context_records.adaptive_weight_reset_on_feasibility_iterations` and `solver_algorithm_phase_runtime_ms.adaptive_weight_reset_on_feasibility`. | Summary step round 3; DB events `26d...` and `9c54...`; session refs `f54a...` and `3c335...`; run.log third rejection line. | Same pattern as round 2: declared mechanism did not activate in smoke. The gate prevented unobservable mechanism claims from entering screening. |

Why `n_experiments=0`:

- All six DB events are `agentic_proposal_session`, not formal experiments.
- The three code sessions terminated with `code_generation_failed` under `agent_quality_blocked`.
- `archive/`, `workspaces/`, and `metrics/` are empty.
- `raw_metrics_ref` and all screening fields are absent/null.
- `status.last_result.reason=agent_quality_blocked`.
- `campaign_summary.steps[*].decision=null`, `contract_passed=false`, `verification_passed=false`, `code_archive_ref=null`.

This means the campaign never materialized an accepted candidate workspace for formal ContractGate/protocol/screening/decision. It only executed agentic proposal preview and algorithm smoke.

## Design Compliance

Boundary control:

- Worked. All hypotheses were `change_locus=solver_design`, `action=modify`, and targeted `policies/baseline_modules/*.py`.
- `selected_surface` in agentic outputs stayed `solver_design`.
- No candidate attempted to modify protocol, split, seeds, adapter, problem provider, runtime gate, or CLI code.
- The code-session failures told the agent to repair candidate algorithm code and not protocol/adapter files. This is aligned with v3 boundary intent.

Fail-closed behavior:

- Worked. A candidate with runtime errors or missing telemetry activation was blocked before screening.
- No frozen budget, validation budget, champion promotion, or weight optimization path was consumed.
- Empty `archive/`, `workspaces/`, and `metrics/` are consistent with pre-experiment rejection rather than partial protocol execution.

Auditability:

- Mostly worked. The chain can be reconstructed from `status.json`, `campaign_summary.json`, DB events, session index, session outputs, compact transcripts, prompt manifests, and `run.log`.
- Session artifacts include stable ids, idempotency keys, transcript digests, prompt hashes, and failure ledgers.
- `campaign_summary.steps[*].proposal_session_ref` gives a direct pointer from each round to the terminal code session.

Classification and over-interception:

- The three terminal round failures are correctly classified at the agentic code-quality/smoke layer, not as formal protocol or decision failures.
- The three hypothesis-only sessions are recorded as `contract_boundary_failure` with reason `hypothesis awaits ContractGate approval`. That is operationally a two-phase handoff, not a real failure. Treating it as a failure ledger entry is useful for closed-loop bookkeeping but confusing in global audits.
- `campaign_summary.steps[*].contract_passed=false` coexists with code-session `self_check.contract_preview_passed=true` and DB `contract_result=passed` for code events. The naming blurs formal ContractGate versus agentic contract preview.
- Rounds 2 and 3 are reasonable fail-closed telemetry blocks because declared mechanisms had no observed activation. Effect-evidence failures seen in intermediate ledgers remain a calibration risk for conditional mechanisms, but the terminal failures here were activation failures or runtime audit errors, not merely weak empirical uplift.

CLI modularization impact:

- The experiment used the modular CLI entrypoint: `python -m scion.cli.main run`.
- Current `scion/scion/cli/main.py` is a thin compatibility wrapper that imports `app` from `scion.cli.app`; `scion/scion/cli/app.py` registers command modules; `scion/scion/cli/commands/init_run.py` constructs `ExperimentProtocol`, `VerificationGate`, `WorkspaceMaterializer`, `ChampionState`, and `CampaignManager`.
- `run.log` shows the campaign started and finished normally through the CLI, and all expected campaign/session/DB artifacts were created.
- There is no evidence that CLI splitting changed the experiment chain or caused the failures. The failures are downstream candidate-quality/smoke failures inside agentic proposal, not command dispatch, option parsing, path resolution, protocol loading, or manager construction failures.

## Observability Gaps

- `experiment_events.hypothesis_id` is blank for all six agentic events, so DB-only round mapping requires joining by time/idempotency/session metadata rather than a direct foreign key.
- `experiment_events` stores `event_kind=agentic_proposal_session` for both hypothesis and code phases, but does not normalize a `phase` column (`hypothesis` vs `code`).
- Hypothesis-only sessions are logged as `contract_boundary_failure`; this makes the normal approval split look like a failure in session ledgers.
- `contract_passed` in `campaign_summary` is false even when the code-session contract preview passed. Formal contract and preview contract need distinct names in summaries.
- `transcript.json` has `termination_reason=null` while `output.json` and the session index contain the real termination reason. This weakens single-file auditability.
- Round 1 code session has three code manifests but only two failure ledger entries (`repair_attempt=0` and `repair_attempt=2`). The missing attempt-level ledger entry should be explainable from artifacts without reading raw traces.
- `failure_code` in `proposal_session_ref` is empty even when `primary_failure.code=algorithm_smoke_failure` is present.
- Failed code attempts do not leave an easy top-level per-attempt patch hash/file summary in `output.json`; the final `patch` field is null after failure. Auditing exact candidate edits requires going to lower-level traces.
- Prompt manifests preserve hashes and section metadata, but raw prompts are absent by design. That is acceptable for privacy/cost control, but insufficient to verify exact prompt content in a global chain audit.
- `archive/`, `workspaces/`, and `metrics/` are empty without a sentinel file explaining "not created because agent_quality_blocked"; this is inferable but not self-describing.

## Recommended Fixes

1. Add `round`, `phase`, and `hypothesis_id` to agentic rows in `experiment_events`.
2. Split normal two-phase hypothesis handoff from failures: use a status like `awaiting_contract_approval` instead of `contract_boundary_failure`.
3. Distinguish `contract_preview_passed` from `formal_contract_passed` in `campaign_summary` and DB columns.
4. Persist per-code-attempt summaries: attempt number, patch hash, touched files, contract preview result, smoke result code, and smoke artifact ref.
5. Mirror `termination_reason` from `output.json` into `transcript.json`.
6. Populate `proposal_session_ref.failure_code` from `primary_failure.code`.
7. Add a pre-experiment rejection counter to campaign summary: e.g. `agentic_hypothesis_handoffs`, `agentic_code_failures`, `agentic_smoke_failures`, and `formal_experiments`.
8. Create small sentinel metadata in empty `archive/`, `workspaces/`, or `metrics/` when no workspace was materialized due to pre-experiment blocking.
9. Review telemetry guard policy separately for conditional effect evidence. Activation evidence should remain fail-closed; effect evidence may need "warn then screen under quarantine" only when activation and safety checks pass.

