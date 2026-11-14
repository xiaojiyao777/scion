# Warehouse Abort Behavior Analysis

Date: 2026-06-15

Subject:
`/home/clawd/research/scion-experiments/v04-phase4-warehouse-longrun-compact-on-3x24r-20260615T163700Z`

Purpose: explain why the clean warehouse 3x24R longrun produced no protocol
rows and was aborted. This is a behavior/patch lifecycle analysis, not a
warehouse mechanism-quality conclusion.

## Result

The clean warehouse run entered the adapter-backed production path, but no
candidate crossed Verification. Protocol never started, so
`protocol_metric_results=0` is expected.

Main failure chain:

1. Candidate patches passed or nearly passed Contract.
2. Verification failed with `V3_unit_tests` because the active WSL campaign
   environment could not import `pytest` (`No module named pytest`).
3. The fix stage correctly recognized some failures as `wrong_owner`, but had
   no usable no-op / abort-repair exit.
4. The model represented "do not edit" as empty or whole-file `exact_replace`,
   which triggered `patch_edit_protocol` errors.
5. Repeated `verification_light` failures blocked branches and consumed the
   run without protocol rows.

This means the run cannot support any claim about warehouse's ability or
inability to improve under v0.4.

## Counts

| cell | proposal attempts | unique hypotheses | LLM request kinds | verification failures | protocol rows |
| --- | ---: | ---: | --- | ---: | ---: |
| `rep01/on_compact` | `7` consumed, `8` total | `7` | `hypothesis=16`, `tool_selection=28`, `code=9`, `fix=7`; trace index `session_count=15`, `trace_count=53`; `llm_traces=60` | `7`, all `V3_unit_tests`; `failure_categories={verification:7}` | `0` |
| `rep02/on_compact` | `2` consumed, `3` total | status `2`; DB has `3` rows with one in-flight/unconsumed | `hypothesis=6`, `tool_selection=10`, `code=4`, `fix=3`; trace index `session_count=6`, `trace_count=20`; `llm_traces=23` | `2`, all `V3_unit_tests`; `failure_categories={verification:2}` | `0` |

Notes:

- `rep01` SQLite is malformed after abort, so counts come from `status.json`,
  `campaign_summary.json`, trace indexes, and logs.
- `rep02` SQLite is readable and confirms `verification_fail=2`,
  `scheduler_result=2`, and `agentic_proposal_session=6`.

## Failure Examples

`rep01` round 1 created `operators/subcategory_consolidate.py` after a
complexity-bound retry. Verification then failed on `No module named pytest`.
The fix response diagnosed `wrong_owner` but returned an empty
`exact_replace`, producing `patch_edit_protocol exact_replace_empty_old_string`.

`rep01` round 2 modified `operators/merge_vehicles.py`; source and digest were
visible, Contract passed, and Verification again failed on missing `pytest`.
The fix response again emitted an empty `exact_replace`.

`rep01` round 3 removed `operators/split_vehicle.py`. After Verification failed
for the same missing-`pytest` reason, the fix response targeted a deleted or
empty file state with a whole-file no-op replace, producing
`existing_file_whole_file_exact_replace_rejected`.

These examples show that source visibility and target grounding were not the
primary failure. The failure was verification environment first, then fix-stage
no-op representation.

## Diagnosis

Ordered causes:

1. Verification environment/preflight failure: campaign environment lacked
   `pytest`, so all consumed candidates failed before Protocol.
2. Patch schema / format obeying failure: fix stage lacked a legal
   `no_patch` / `abort_repair` path for infra or wrong-owner failures.
3. Operator file state edge case: delete/remove left file state that made no-op
   exact replacement especially brittle.
4. Context signal density: the model recognized `wrong_owner` but still tried
   to satisfy patch schema; the "do not edit for infra" instruction was not hard
   enough.
5. Source visibility / target grounding: not primary; target files and source
   digests were visible in the inspected modify/remove cases.
6. Warehouse mechanism quality: cannot be judged because Protocol rows are
   absent.

## Next Steps

Do not rerun the full warehouse longrun yet.

Required repair/debug sequence:

1. Add or enforce verifier startup preflight so missing `pytest` or equivalent
   verification dependencies fail fast before proposal budget is consumed.
2. Add a legal fix-stage no-op / abort-repair path for infra or wrong-owner
   verification failures; do not require the model to encode "no change" as an
   empty `exact_replace`.
3. Run a one-candidate warehouse lifecycle debug to confirm Contract ->
   Verification -> Protocol reaches `protocol_metric_results>0`.
4. Run a short 3-5R compact debug to verify `verification_light` loops and
   no-op patch errors are gone.
5. Only then rerun a warehouse longrun.

These repairs stay within the v3 boundary. They are core verification/patch
protocol robustness and problem-surface runtime setup issues; warehouse
objective semantics still belong in problem-owned protocol/report/proposal
context, not `DecisionFeatures`.

## Reproduction

```bash
ROOT=/home/clawd/research/scion-experiments/v04-phase4-warehouse-longrun-compact-on-3x24r-20260615T163700Z

jq '.accounting_reconciliation, .research_accounting, .llm_request_kind_counts, .verification_failure_breakdown, .protocol_metric_stage_counts' \
  "$ROOT/rep01/on_compact/campaign/status.json"

jq '.accounting_reconciliation, .research_accounting, .llm_request_kind_counts, .verification_failure_breakdown, .protocol_metric_stage_counts' \
  "$ROOT/rep02/on_compact/campaign/status.json"

sqlite3 "$ROOT/rep02/on_compact/campaign/scion.db" \
  "select event_type, count(*) from experiment_events group by event_type;"

rg -n "patch_edit_protocol|verification_light|V3_unit_tests|No module named pytest|infra_suspected" \
  "$ROOT/rep01/on_compact/campaign/run.log" \
  "$ROOT/rep01/on_compact/campaign/campaign_summary.json" \
  "$ROOT/rep02/on_compact/campaign/campaign_summary.json"
```
