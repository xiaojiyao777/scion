# R19 Warehouse import-feedback control

State: **completed / valid, 2/2 evaluated stages**, terminal October5 at18:41:23
Beijing /10:41:23 UTC; pane exit0. Started once at18:26:58 Beijing /10:26:58 UTC,
PID543472. October5 user approves continuing after the
completed Sol control and remaining research-support findings. Model remains
gpt-6.1-sol high; no old-model fallback, proxy restart, budget increase or Git
commit/push. This is a fresh control of changed shared context/feedback, not
resumption or relabeling of either previous R19 control.

## Intervention and estimand

Runtime is pushed484433ea plus uncommitted P15 and the scoped P16 follow-up:

- The existing C8 effective absolute-import roots (problem declarations, safe
  stdlib and declared runtime dependencies) have one shared implementation.
  Complete target guidance exposes those same roots through direct and bounded
  C rendering. Read-only visibility does not authorize import or modification.
- Failed C8 checks optionally expose the earliest rejected statement's one-based
  source_line in the current draft. It is a bounded integer tied to an editable
  submitted file, never raw checker text, a private path or a test exception.
  Relative-import file/symbol checks and all accept/reject rules are unchanged.
- Optional generic testing guidance distinguishes forced-weight/altered-guard
  wiring from ordinary activation, and entry counts from completed transitions,
  acceptance and improvement. This adds no mandatory test/telemetry requirement.

Questions: does actual C receive the rules; do naturally occurring C8 failures
locate the submitted statement and support deliberate correction; do source,
readonly, development-test and formal boundaries remain intact? No forced bad
action, target or algorithm. Unexercised paths retain regression-only coverage.
Negative/tied science is acceptable; incomplete runs remain incomplete. No
claim of causal feedback efficiency or model quality from different seeds/drafts.

## Frozen prospective design

Initial complete source is repository surrogate, not a previous candidate.
Reuse the unchanged [split](inputs/v04-r19-warehouse-reliable-probes-control-split.yaml):
initial small_6, required expansion small_6/small_1; validation small_3,
frozen small_4, canary small_5; public small_2 excluded. New
[protocol](inputs/v04-r19-warehouse-import-feedback-control-protocol.yaml) changes
only version/canary seed from the preceding control. The
[ledger](inputs/v04-r19-warehouse-import-feedback-control-seeds.yaml) uses the
first five primes above250000: screening250007/250013, validation250027,
frozen250031, canary250037, fixed before dispatch/outcomes.

Two evaluated stages, two-second solver limits, K1/max three branches, H180/C300,
SDK retry0/two charged typed transient redispatches,80 physical calls,7200-second
outer guard and unchanged R3i12-turn/8-read/8-search/4-test C limits. Transcript
unlimited; parameter search off. No algorithm, Contract acceptance, Verification,
Protocol, Decision, population or threshold change.

Finish focused/full regression, source/data/public-formal closure and bounded
provider health checks before launch. No tests/maintenance/other solver or
runtime/input edits during measurement. Audit completed H/C, exact sources,
canary, complete paired Protocol and recorded Decision. A real execution or
boundary defect blocks prospective CVRP R19. Two negative valid screens alone
do not block it. No control outcome/recipe is sent to CVRP H/C. CVRP remains
unlaunched, with unchanged prepared source/history/scientific inputs and caps.

Output: `/home/clawd/research/scion-experiments/v04-r19-warehouse-import-feedback-control-20261005`.
Tmux: `scion-r19-warehouse-import-feedback-control-20261005`.

## Direct invocation (after verification)

```bash
set -Eeuo pipefail
cd /home/clawd/research/or-autoresearch-agent
test ! -e /home/clawd/research/scion-experiments/v04-r19-warehouse-import-feedback-control-20261005
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
    --protocol /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-r19-warehouse-import-feedback-control-protocol.yaml \
    --split /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-r19-warehouse-reliable-probes-control-split.yaml \
    --seeds /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-r19-warehouse-import-feedback-control-seeds.yaml \
    --time-limit-sec 2 --rounds 2 --provider-call-cap 80 \
    --provider-transient-retries 2 --outer-hardwall-sec 7200 \
    --campaign-dir /home/clawd/research/scion-experiments/v04-r19-warehouse-import-feedback-control-20261005
```

## Prelaunch verification

Full regression:2678 passed / one skip in451.05 seconds. Focused feedback,
security, context and session group:197 passed;42 context/import checks overlap.
After adding prospective input assertions,24 R16–R19 input tests pass in1.17
seconds. Ruff F/E9 (excluding existing F403/F405) and git diff --check pass.

Read-only preparation validates406 Warehouse files/40 Python parses/five cases,
100 selected CVRP files/48 Python parses/25 cases, public/formal closure and
fresh absent outputs. CVRP retains18 histories,188 raw/165 safe records and five
observations (170 history-index entries), exact13,556-character question,30 H
sources and17 readonly C sources. Warehouse has17 H sources and9 readonly C
sources. Actual C rendering includes the new effective import rules. Preparation
creates no campaign or solver/provider execution. An initial audit assertion
used the wrong research_question shape; checking its current_question field
confirms exact equality without changing runtime or inputs.

One separate bounded tool inference succeeds at18:25:59 Beijing /10:25:59 UTC,
gpt-6.1-sol high,3.524 seconds, no SDK retry. No live campaign, test or solver
process remains at launch preparation. Freeze runtime and scientific inputs now;
only status/analysis documentation may change during measurement. Preserve all
prior terminal roots and never infer scientific benefit from startup.

## Actual launch and startup audit

The exact documented CLI starts once at18:26:58 Beijing, PID543472, in the
new tmux session and output. [Live status](/home/clawd/research/scion-experiments/v04-r19-warehouse-import-feedback-control-20261005/status.json)
records running/pending,0/2 evaluated stages at startup. All406 non-cache
champion files are byte-equal to the initial surrogate. The stored resource
envelope is80 calls/two charged retries/7200 seconds; stored C limits match the
preregistered12 turns/eight reads/eight searches/four tests/unlimited transcript.
The first two actual H calls succeed at attempt0 on gpt-6.1-sol with180-second
request policy. Production diff still equals its prelaunch value. This verifies
startup, not successful C8 correction, completed control or scientific gain.
CVRP remains unlaunched; finish and audit this control before its dispatch.

## Terminal audit — October6

The [terminal status](/home/clawd/research/scion-experiments/v04-r19-warehouse-import-feedback-control-20261005/status.json)
and [step summary](/home/clawd/research/scion-experiments/v04-r19-warehouse-import-feedback-control-20261005/campaign_summary.json)
record completed/valid2/2, two exported H/C candidates, no research rejection,
and no validation, frozen or promotion. All42 physical calls succeed at attempt0
on gpt-6.1-sol:23 H and19 C, with38/80 calls unused. No service failure or cap
exhaustion. Runtime/inputs were subsequently committed and pushed as6380a59e
without changing their launch-time values. October6 entry finds that checkout
clean and all experiment carriers dead. Original artifacts/SQLite stay untouched.

Actual C sees the effective import policy in all19 rendered requests. Each first
draft nevertheless imports oracle, which is read-only but not an allowed runtime
import. C8 feedback correctly identifies line9 in DestroyRebuild and line17 in
MergeVehicles. Each session deliberately replaces its complete draft, removes
the forbidden import, and passes D1/D1b/D2/D3/D4 plus its collected final probe
at draft2 before ready. There are no observed tool-error results. These are two
live correction examples, not a causal efficiency estimate or complete coverage
of every feedback path. No pytest-no-tests event occurred.

The accepted DestroyRebuild implements the bounded subcategory-aware beam and
local feasibility/objective checks; real VNS still applies the unchanged fixed
oracle after operator execution. Its public synthetic probes check an actual
joint consolidation, lexicographic priority, locked bins, amount restrictions,
repeatability and the order-count bound. MergeVehicles implements the bounded
biased pair sampler, exact split/cost ranking, feasible type enumeration and
whole-group movement. It also implements local checks rather than importing the
fixed oracle. Its probe compares those checks with the real oracle and exercises
real solve using unchanged default weights: a recorded improving merge survives
to the final feasible solution. The fixture is small and chooses seed/iteration
settings; this does not prove production-population activation or stable gains.

H2 incorrectly describes the earlier beam as inherited. Both actual step bases
are champion:v1 on separate branches: candidate2 retains original DestroyRebuild,
not candidate1's beam. Source delivery is correct; cross-branch attribution is a
remaining model-reasoning limitation. Neither patch modifies frozen oracle or
test files. Candidate-local semantic duplication remains research maintenance
debt, not a replacement for host Verification/Protocol.

| Candidate | Formal quality | Candidate/champion time | Recorded Decision |
|---|---|---|---|
| DestroyRebuild beam | Both objectives tie |2080/470 ms|CONTINUE_EXPLORE, SCREENING_FAIL_WIN_RATE|
| MergeVehicles pair search | Both objectives tie |390/480 ms|CONTINUE_EXPLORE, SCREENING_FAIL_WIN_RATE|

Each row has one complete valid pair on small_6/seed250007, equal2-second limits,
passed Contract/Verification/canary and no pair failures. The beam has a recorded
candidate budget-saturation warning; the second row's lower elapsed time is only
a single-pair observation. Neither supports stable benefit. Exact metrics:
[beam](/home/clawd/research/scion-experiments/v04-r19-warehouse-import-feedback-control-20261005/metrics/cb8ecdf3-8207-483a-9eeb-406f6330588c.json),
[merge](/home/clawd/research/scion-experiments/v04-r19-warehouse-import-feedback-control-20261005/metrics/88ef6738-45f1-47a1-9d6e-7d15f9528c13.json).
Registry-resolution telemetry alone does not show formal-case transitions.

Read-only source audit matches all406 non-cache champion files to the original
surrogate;27 visible editable,171 readonly,38 public-test and29 H-visible source
bodies match their declared base. Another87 editable entries are index-only,
not delivered source bodies. Both surviving complete406-file candidate trees
differ only in their respective operator and registry.yaml, and the final code
equals the accepted draft. Complete paired metrics and recorded Decisions agree.
No execution/boundary defect was found in exercised paths. This satisfies the
preregistered shared-runtime control for CVRP launch, not retained improvement.
Do not transfer Warehouse outcomes or repair recipes into CVRP H/C.
