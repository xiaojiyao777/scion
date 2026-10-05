# R19 fresh Warehouse control with GPT-6.1 Sol

State: **completed / valid, 2/2 evaluated stages**, terminal October5 at16:36:07
Beijing /08:36:07 UTC. Started once at15:42:59 Beijing /07:42:59 UTC,
PID537412. October5 user approves proceeding with
gpt-6.1-sol after bounded connectivity tests. This replaces the missing complete
control evidence, not the original terminal record. The
[earlier control](v04-r19-warehouse-reliable-probes-control-20261005.md) remains
invalid_no_evaluated_outcome, 0/2 stages at80 calls; never resume or overwrite it.
No new Git commit/push, proxy restart, runtime repair or budget increase.

## Prospective design

Runtime remains pushed484433ea plus the unchanged, uncommitted P15 production
changes tested by2659 passing tests / one skip. Complete initial source remains
repository surrogate; no host algorithm edit or prior Warehouse candidate reuse.
Use the same frozen runtime for this control and subsequent CVRP R19.

Changes from the original control are model gpt-6.1-sol (still high), a fresh
output directory, and the first five primes above240000: screening240007/240011,
validation240017, frozen240041, canary240043. New
[protocol](inputs/v04-r19-warehouse-reliable-probes-sol61-control-protocol.yaml)
and [seeds](inputs/v04-r19-warehouse-reliable-probes-sol61-control-seeds.yaml)
are frozen before dispatch. Reuse the unchanged
[split](inputs/v04-r19-warehouse-reliable-probes-control-split.yaml), including
its historical descriptive version label. All populations and scientific gates
are unchanged: initial small_6, expansion small_6/small_1; validation small_3,
frozen small_4, canary small_5. Public small_2 remains excluded.

Two evaluated stages, two-second solver limits, K=1/max three branches,
H180/C300-second transport ceilings, SDK retry0/two charged typed redispatches,
80 physical calls,7200-second outer guard, unchanged R3i C limits, no forced
surface/action/target and no mutable resume. Negative scientific quality or ties
are acceptable; incomplete control is not silently relabeled complete.

Model compatibility: official
[GPT-6.1 Sol documentation](https://developers.openai.com/api/docs/models/gpt-6.1-sol)
supports high and requires Responses for tool calling. Scion's existing local
OpenAI-compatible client is translated by the proxy into /codex/responses;
two actual tool probes at15:32–15:33 Beijing both return the expected JSON in
4.313/3.628 seconds. Egress logs confirm the actual requested/upstream model
and high setting; these ordinary diagnostics are not scientific evidence.
Old gpt-5.6-sol also succeeds in a contemporaneous probe, so these tests do not
prove model-specific outage or lasting service stability. No change to proxy,
SDK, global model defaults, tools or prompts is made for the model switch.

## Acceptance and limits

Complete the two evaluated stages and audit actual H/C, source values,
Contract/Verification/canary, complete paired Protocol and deterministic Decision.
Inspect readonly protection, safe query/probe feedback, collected tests and draft
corrections where naturally exercised; do not force a bad action to manufacture
coverage. Unexercised paths retain regression-only coverage. A real execution or
boundary defect blocks CVRP; service failure preserves an invalid/incomplete run.
No maintenance, tests, other solver or runtime/input edits during measurement.

This is an engineering/research-interface control, not retained improvement or
a controlled comparison of model quality. Model and seed changes prevent causal
attribution to P15 alone. No control result, algorithm or repair recipe enters
CVRP H/C. After a complete audited control, CVRP uses gpt-6.1-sol high with its
already prepared source, histories, seeds, gates and resource envelope.

Output: `/home/clawd/research/scion-experiments/v04-r19-warehouse-reliable-probes-sol61-control-20261005`.
Tmux: `scion-r19-warehouse-reliable-probes-sol61-control-20261005`.

## Planned direct invocation

```bash
set -Eeuo pipefail
cd /home/clawd/research/or-autoresearch-agent
test ! -e /home/clawd/research/scion-experiments/v04-r19-warehouse-reliable-probes-sol61-control-20261005
proxy_key_value=$(curl -fsS --connect-timeout 5 --max-time 15 http://127.0.0.1:8080/auth/status | jq -er '.proxy_api_key | select(type == "string" and length > 0)')
curl -fsS --connect-timeout 5 --max-time 15 -H "Authorization: Bearer $proxy_key_value" http://127.0.0.1:8080/v1/models | jq -e 'any(.data[]?; .id == "gpt-6.1-sol")' >/dev/null
exec env \
  PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
  PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion \
  OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  SCION_PROBLEM_DATA_ROOT=/home/clawd/research/or-autoresearch-agent/surrogate \
  SCION_MODEL=gpt-6.1-sol SCION_REASONING_EFFORT=high \
  SCION_BASE_URL=http://127.0.0.1:8080 SCION_API_KEY="$proxy_key_value" \
  SCION_LLM_TIMEOUT_SEC=180 SCION_LLM_HYPOTHESIS_RESEARCH_TURN_TIMEOUT_SEC=180 \
  SCION_LLM_CODE_RESEARCH_TURN_TIMEOUT_SEC=300 SCION_LLM_CODE_RESEARCH_FINALIZE_TIMEOUT_SEC=300 \
  /home/clawd/miniconda3/envs/claw/bin/python -B -m scion.cli.main run \
    --problem /home/clawd/research/or-autoresearch-agent/scion/problems/warehouse_delivery/problem-v1.yaml \
    --source-tree /home/clawd/research/or-autoresearch-agent/surrogate \
    --code-research-limits /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r3i-long-run-code-research-limits.json \
    --protocol /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-r19-warehouse-reliable-probes-sol61-control-protocol.yaml \
    --split /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-r19-warehouse-reliable-probes-control-split.yaml \
    --seeds /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-r19-warehouse-reliable-probes-sol61-control-seeds.yaml \
    --time-limit-sec 2 --rounds 2 --provider-call-cap 80 \
    --provider-transient-retries 2 --outer-hardwall-sec 7200 \
    --campaign-dir /home/clawd/research/scion-experiments/v04-r19-warehouse-reliable-probes-sol61-control-20261005
```

## Verification and execution

Prelaunch:22 R16–R19 input regressions pass in1.13 seconds; Ruff F/E9 and
git diff --check pass. New seeds are disjoint from every checked-in ledger;
effective Protocol equals the original control except canary seed/version.
Read-only preparation checks406 Warehouse files/40 Python parses/five cases,
100 selected CVRP files/48 Python parses/25 cases, public/formal closure and
both fresh outputs. All18 histories load188 raw rows; provider projection retains
165 safe rows plus five observations, with the unchanged13,556-character question.
Actual client/CreativeLayer both select gpt-6.1-sol high and H180/C300.
No solver, provider or campaign output is created by preparation.

A separate single bounded tool inference succeeds at15:42:01 Beijing
(07:42:01 UTC),4.536 seconds, no SDK retry. Process checks find no live campaign,
pytest, fixed-funnel or solver subprocess. Freeze runtime and all scientific
inputs now; only status/analysis docs may change during measurement. Original
control artifacts and executed inputs are not touched. No new full-suite rerun
is needed for these input/model-only amendments; the prior2659-test verification
covers the unchanged production code.

The direct invocation starts once at15:42:59 Beijing, PID537412, with the new
output and unchanged80-call envelope. Startup is not a completed control or
scientific benefit. Await terminal evidence before CVRP dispatch.

Startup audit: all406 non-cache champion files equal the selected initial tree.
The first two actual H requests succeed at attempt0 on gpt-6.1-sol (180-second
request policy), reading ordinary source entries. This confirms the formal
research path uses the intended model, beyond the short connectivity probes.

## Interim audit at15:59 Beijing (not terminal)

The first18 completed physical dispatches all succeed on gpt-6.1-sol; no overload,
quota event or transport retry is observed in this prefix. One H plus12 C turns
and the allowed final choice consume16 calls in the first attempt; the next two
H reads have also completed. Counters in status update at phase/step boundaries,
so the completed trace prefix is not confused with a live call-admission total.

First H proposes a bounded subcategory-aware beam repacker in DestroyRebuild.
Four complete draft replacements preserve that mechanism, but every requested
test stops at C8_import_whitelist before executing public tests or the optional
falsifier. Each draft imports oracle, which is not in this problem's declared
import whitelist. Removing allowed collections/dataclasses imports or changing
from-import to import does not solve that restriction. A search for
import_whitelist returns no matches in the source corpus. Typed feedback names
the failed check/file, not the offending module or full allowed-import list.
This preserves the gate but leaves a concrete research-efficiency/context limit;
reading a public readonly file does not grant candidate import permission.

The first ready receives latest_draft_not_passing, then the model explicitly
abandons at15:58:47: CODE_RESEARCH_ABANDONED, no exported/verified candidate or
formal round. The scheduler correctly begins a fresh H on the clean base, without
changing the80-call limit. The control remains running at0/2 evaluated stages.
This is not a valid negative Protocol result or completed live support validation.
The proposed collected tests/reference enumeration were never executed; no
live pytest_no_tests_collected path or successful draft correction is established.

All visible bodies in the first five C contexts match the original base under
the existing outer-whitespace normalization: five editable values,45 readonly
values and10 public-test values. The remaining25 indexed editable entries are
not yet visible, rather than truncated bodies. Frozen dependencies stay outside
the editable set. Production diff remains unchanged from the launch-time value.
Original SQLite is not opened: current CLI inspect/report initializes its normal
registry/WAL, so this read-only audit uses existing JSON/traces/source directly.

Continue this live control under its original envelope. CVRP remains unlaunched;
the model switch has live H/C transport evidence but not a completed control.
Do not repair or relax imports mid-run, resume a terminal root, or infer retained
algorithm improvement from these operational observations.

## Terminal audit (October5, after measurement)

[Status](/home/clawd/research/scion-experiments/v04-r19-warehouse-reliable-probes-sol61-control-20261005/status.json)
and [summary](/home/clawd/research/scion-experiments/v04-r19-warehouse-reliable-probes-sol61-control-20261005/campaign_summary.json)
record completed/valid, requested_rounds_completed, two evaluated screening
stages from four attempts. Pane exit0 is only carrier evidence. No cap exhaustion,
validation, frozen or promotion; champion remains v1. All78 physical calls use
gpt-6.1-sol:77 succeed, one H502 overload recovers at attempt1. Two calls remain.
This demonstrates operational recovery, not a model-capacity or retirement cause.

Attempts1/3 abandon after repeated C8 failures in DestroyRebuild/MergeVehicles.
The import rule remains enforced, but ordinary import_whitelist context is
discarded by the final research-core renderer and target guidance filters its
interface line. Feedback names the check/file, not the rejected import position.
This is an actionable context-composition/feedback gap, not provider failure.

Attempt2 replaces DestroyRebuild with bounded atomic-group beam repacking;
attempt4 replaces MoveOrder with whole-subcategory-block relocation and resizing.
The accepted sources use local feasibility/objective computations rather than
prohibited oracle imports. Both modify real execute methods; this alone does
not establish their activation on the formal case. Both pass development D1–D4,
their final optional falsifiers, formal Verification and canary. MoveOrder's
earlier public test failure leads to a deliberate corrected draft that passes.
Failed drafts never become ready. No live no-tests-collected event is observed.

Each formal screen covers only small_6/seed240007 and ties on both objectives:

| Candidate | Candidate/champion elapsed | Decision | Evidence |
|---|---|---|---|
| DestroyRebuild | 715/385 ms (+85.7%) | continue_explore / SCREENING_FAIL_WIN_RATE | [pair](/home/clawd/research/scion-experiments/v04-r19-warehouse-reliable-probes-sol61-control-20261005/metrics/9855c45a-4b04-4723-8bd7-7a56249ea285.json) |
| MoveOrder | 524/376 ms (+39.4%) | continue_explore / SCREENING_FAIL_WIN_RATE | [pair](/home/clawd/research/scion-experiments/v04-r19-warehouse-reliable-probes-sol61-control-20261005/metrics/b77a8bf8-cbb7-4e4f-80c5-b603109c47d7.json) |

Both pairs are complete/valid, no runtime failures or candidate-attributable
infeasibility. Runtime estimates are single-pair observations, not stable ratios.
Telemetry establishes registry resolution only, not completed mechanism
transitions. Optional forced-weight integration probes cannot prove ordinary
production activation. No retained improvement or P15 causal benefit is shown.

All48 editable,432 read-only and96 public-test visible bodies across48 C contexts
match their clean champion bases under existing outer-whitespace normalization.
Both surviving complete candidate trees differ only in the corresponding
operator and registry.yaml; no additions/deletions/frozen-source changes. Two
ordinary history rows match the two formal screens. Original SQLite and run
artifacts remain untouched; no solver/provider rerun or evidence backfill.

The subsequent user approval permits fixing this shared research-support gap.
The [fresh import-feedback control](v04-r19-warehouse-import-feedback-control-20261005.md)
must validate that new runtime before prospective CVRP R19; this completed
control proves only its own frozen P15 runtime. No resume or retrospective input edit.
