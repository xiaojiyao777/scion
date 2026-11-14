# Warehouse No-Hard-Truncation Short Debug 4R Postrun - 2026-06-16

## Scope

This postrun analyzes the completed WSL run
`scion_wh_nohardtrunc_short4r_155951`.

- WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-postrepair-nohardtrunc-short-debug-4r-20260616T155951Z`
- Server sync root:
  `/home/clawd/research/scion-experiments/v04-warehouse-postrepair-nohardtrunc-short-debug-4r-20260616T155951Z`
- Campaign root:
  `rep01/on_compact/campaign`
- Model: `gpt-5.5`
- Context profile: `compact-measurement-diagnostics`
- Measurement governance: `on`
- Requested effective rounds: `4`

The v3 boundary remains the interpretation anchor: proposal prompts, branch
lessons, cross-branch maps, and LLM traces are tainted proposal material.
Protocol rows, verification results, canary results, and deterministic
DecisionFeatures remain the decision boundary.

## Verdict

Launch/env validity: valid. The wrapper exited `0`, `exit_code.txt` is `0`,
`run_status.json` reports `status=finished`, `run_validity_status=valid`,
`run_completeness_status=complete`, and `completed_requested_rounds=true`.
The run started at `2026-06-16T16:00:59Z` and ended at
`2026-06-16T16:11:25Z`.

Prompt-rendering field validity: accepted with one non-fatal timeout caveat.
All 21 LLM traces are `gpt-5.5`; all trace-index entries have `ok=true`.
No auth, credential, API-key, 401/403 failure, or missing-credentials failure
was found. One first-hypothesis provider call hit `llm_tool_timeout` and was
retried; the wrapper completed successfully.

Research quality: not accepted as an improvement/recovery claim. The run
produced 3 screening protocol rows, all failed the screening gate by win rate.
One candidate branch survived only as `active_marginal`; there were no
validation or frozen rows and no promotion.

## Artifact Reconciliation

Root-level wrapper artifacts:

- `exit_code.txt`: `0`
- `status.txt`: final `status=finished`, `exit_code=0`
- `rep01/on_compact/run.log`: campaign startup, one tool timeout retry, then
  `Campaign finished. experiments: 3`
- `rep01/on_compact/campaign/run_status.json`: complete/valid wrapper audit
- `rep01/on_compact/campaign/status.json`: final campaign accounting snapshot
- `rep01/on_compact/campaign/campaign_summary.json`: detailed postrun summary
- `rep01/on_compact/campaign/scion.db`: SQLite lineage store
- `rep01/on_compact/campaign/agentic_sessions/agentic_session_trace_index.json`
- `prompt_context.csv`: not present; prompt audit used manifests and traces

SQLite counts:

- branches: `3`
- hypotheses: `5`
- experiment_events: `22`
- champions: `1`
- weight_optimizations: `0`

Formal candidate artifacts:

- `artifacts/formal_candidates/index.jsonl`: `5` entries, all with complete
  replay identity and no missing replay keys.
- Campaign accounting reports `formal_screened_candidates=3` and
  `protocol_metric_results=3`. The run's reconciliation explicitly flags the
  2-entry difference as formal-candidate index entries outside the current
  screening-row counter scope.

## LLM And Prompt Checks

Trace index:

- sessions: `9`
- traces: `21`
- request kinds: `8` hypothesis, `8` tool_selection, `5` code
- model counts: `{"gpt-5.5": 21}`
- provider counts: `{"openai_compatible": 21}`

Hypothesis prompt manifests:

- All `api_visible_prompt_manifest_*_hypothesis*.json` files report
  `prompt_section_truncation_count=0`, `truncated_sections=[]`, and visibility
  ledger `truncated=0`.
- `compact_research_signals`, `branch_lesson_usage_context`, and
  `cross_branch_research_map` are included whenever present.
- In the actual provider-facing trace prompts, those three sections contain no
  `<truncated agentic context>`, no `... [truncated]`, no `[truncated]`, no
  synthetic ellipsis, no `required_response`, and no session metadata markers.
- Later branch lessons are visible. Early hypothesis traces carry
  `lesson:dfbea3c5229eab39`; later traces carry multiple lesson ids, including
  the final hypothesis trace with `lesson:552a64749ded17ce`,
  `lesson:790a8e4fcda50384`, `lesson:97d91b324ee8f24b`, and
  `lesson:fae7944881d616f5`.
- Cross-branch map evidence summaries are visible with compact
  activation/effect/outcome/runtime status counts.

Code-stage manifests:

- All code manifests report `prompt_section_truncation_count=0` and visibility
  ledger `truncated=0`.
- Existing-target code calls show full literal current target source and source
  digest visibility for `operators/split_vehicle.py` and
  `operators/merge_vehicles.py`.
- Create-new calls for `operators/consolidate_subcategory.py` and
  `operators/absorb_residual_vehicle.py` correctly show
  `create_new_target_no_current_source`; champion/reference surface code remains
  visible.
- All code traces include current champion research code, approved target
  current-content context or create-new placeholder, and reference surface files.

## Campaign Accounting

Final campaign counters:

- `total_rounds=5`
- `effective_rounds_completed=4`
- `proposal_attempts=5`
- `proposal_attempts_total=5`
- `proposal_quality_blocks=1`
- `verification_consumed_candidates=4`
- `verification_failure_consumed_candidates=1`
- `protocol_metric_results=3`
- `protocol_metric_stage_counts`: screening `3`, validation `0`, frozen `0`
- `fresh_runtime_replay_protocol_results=0`
- `fresh_champion_required_count=0`
- `stage_transition_drain`: one skip, `not_selected_no_pending`

The extra `total_rounds` beyond the requested `4` is the non-counted proposal
quality block. The requested effective budget was consumed by 3 screening rows
and 1 verification-only failure.

## Protocol Rows And Attempts

1. Round 1, branch `50a981b0`, `create_new/vehicle_level`,
   `operators/consolidate_subcategory.py`.
   Contract, verification, and canary passed. Screening failed:
   case win rate `0.2`, median delta `-50.0`, CI `[-2325.0, 400.0]`.
   Decision: abandon, with `SCREENING_FAIL_WIN_RATE` and soft-abandon negative
   delta lifecycle reasons.

2. Round 2, branch `f7af5503`, `modify/order_level`,
   `operators/move_order.py`.
   Non-counted proposal quality block before code/protocol:
   `branch_lesson_usage_semantic_mismatch`.

3. Round 3, branch `f7af5503`, `remove/vehicle_level`,
   `operators/split_vehicle.py`.
   Contract passed, verification failed with `V5_solution_consistency`.
   This consumed an effective round but produced no protocol row.

4. Round 4, branch `f7af5503`, `modify/vehicle_level`,
   `operators/merge_vehicles.py`.
   Contract, verification, and canary passed. Screening failed:
   case win rate `0.0`, median delta `-625.0`, CI `[-5625.0, 0.0]`.
   Decision: abandon, with loss/no-positive-CI/negative-delta soft-abandon
   reasons.

5. Round 5, branch `2d6004f0`, `create_new/vehicle_level`,
   `operators/absorb_residual_vehicle.py`.
   Contract, verification, and canary passed. Screening failed by win rate but
   retained marginal signal: case win rate `0.2`, median delta `50.0`, CI
   `[-175.0, 1100.0]`. Decision: `continue_explore` with
   `SCREENING_MARGINAL_SIGNAL_CONTINUE`.

## Branch Behavior

Active branch:

- `2d6004f0-969f-443a-829a-860119d2e887`
- mechanism: `residual_vehicle_absorption`
- status: `explore`
- branch code status: `active_marginal`
- best/last valid checkpoint: `9e11f6d1-7387-4353-bc24-9fa6726216f3`
- generic evidence: wins `2`, losses `0`, ties `8`, median delta `50.0`
- case-level positive cases include `instance_prod_scr_micro03.json`,
  `instance_prod_scr_s02.json`, `instance_prod_scr_ms03.json`,
  `instance_prod_scr_m03.json`, and `instance_prod_scr_ml02.json`
- not promoted because `SCREENING_FAIL_WIN_RATE`; retained only as marginal
  follow-up material

Abandoned branches:

- `50a981b0`: `consolidate_subcategory`, regression screening result
  `wins=2/losses=3/ties=5`, median delta `-50.0`
- `f7af5503`: same-subcategory / split-removal / compatible-pair-merge family,
  with one proposal quality block, one V5 verification failure, and one
  regression screening result `wins=0/losses=2/ties=4`, median delta `-625.0`

Cross-branch observability:

- branch lesson records: `8`
- branch lesson usage requirements: `4`
- satisfied: `3`
- present but not semantic: `1`
- semantic-mismatch block count: `1`
- cross-branch map seen count: `4`
- active research shape: `deep_focused`

## Fresh Runtime Replay

No fresh-runtime replay ran or was required:

- `fresh_champion_required_count=0`
- `fresh_runtime_replay_protocol_results=0`
- active branch runtime confidence is `low_cached_champion`
- the active branch runtime aggregate was excluded because champion runtime
  evidence was cached/low-confidence

This is acceptable for the prompt-rendering field check, but it means the
active marginal branch has weak runtime evidence and should not be treated as a
validated research result.

## Failure Modes

Observed:

- one LLM provider hard timeout on the first hypothesis call, retried
  successfully;
- one proposal quality block:
  `agent_quality_blocked:branch_lesson_usage_semantic_mismatch`;
- one verification-heavy failure: `V5_solution_consistency`;
- two screening regressions abandoned;
- one marginal screening signal retained for exploration only.

Not observed:

- auth/API credential failure;
- code-generation failure;
- `old_string_not_found`;
- `stale_source`;
- validation/frozen leakage;
- prompt section truncation in the required research-signal sections.

## Commands Used

Representative commands:

```bash
ssh -i /home/clawd/.ssh/id_ed25519_codex_wsl -p 2222 -o BatchMode=yes \
  xjy-ubuntu@127.0.0.1 '...tmux/status/artifact checks...'

rsync -az --delete \
  -e 'ssh -i /home/clawd/.ssh/id_ed25519_codex_wsl -p 2222 -o BatchMode=yes' \
  xjy-ubuntu@127.0.0.1:/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-postrepair-nohardtrunc-short-debug-4r-20260616T155951Z/ \
  /home/clawd/research/scion-experiments/v04-warehouse-postrepair-nohardtrunc-short-debug-4r-20260616T155951Z/

jq . rep01/on_compact/campaign/run_status.json
jq . rep01/on_compact/campaign/status.json
jq . rep01/on_compact/campaign/campaign_summary.json
sqlite3 rep01/on_compact/campaign/scion.db '.tables'
sqlite3 rep01/on_compact/campaign/scion.db 'select ... from experiment_events'
rg -n -i 'auth|unauthorized|invalid api|missing credential|timeout|old_string_not_found|stale_source|error' ...
python - <<'PY'
# JSON checks over trace index, LLM traces, manifests, prompt sections, and formal candidate index
PY
```

## Residual Risks

- This was a short 4R field check. It validates the live no-hard-truncation
  prompt/context path, not warehouse continuous-improvement recovery.
- `prompt_context.csv` was absent, so provider-visible prompt validation relies
  on trace prompt text plus `api_visible_prompt_manifest_*` ledgers.
- Formal candidate artifact count is `5` while protocol rows are `3`; the run
  reconciles this as extra index entries outside the current screening-row
  counter scope, not as missing protocol evidence.
- The active branch is marginal and runtime aggregate evidence is excluded due
  to low/cached champion runtime confidence.
- Some ordinary clipped snippets appear in generic tool-observation summaries,
  but the repaired research-signal sections under test have no ellipsis or
  truncation markers.
