# CVRP R17: explicit quota stop and fresh autonomous research

State: running, launched once at 2026-10-03T13:40:12Z, tmux PID 460131.
October 3 follow-up approves the proposed
quota fix and fresh run. No Git commit or push is requested in this turn.
R16 remains terminal and immutable; this is not a resume.

## Intervention and limits

Recognize explicit HTTP 429 quota exhaustion by known code/type
(insufficient_quota or usage_limit_reached), or the exact usage-limit message,
including the R16 local-proxy wrapper. Use the existing LLMBalanceError /
RESOURCE_EXHAUSTED / PROVIDER_BALANCE_EXHAUSTED terminal path after the charged,
traced dispatch. Structured SDK bodies take precedence over formatted text.
Ordinary rate throttling, typed timeout/transport/provider faults and the narrow
synthetic 401 retain bounded redispatch. Real authentication remains terminal.
No new timers, outage counters, recovery state, scheduler rule or history gate.
The fix prevents the observed initial quota 429 from triggering another 43 hours
of futile attempts; it does not promise recognition of every unknown outage.

No solver, prompt, Contract, Verification, Protocol or Decision implementation
changes. Safe research-input additions describe complete R16 screening and
public source/probe scope, not validation outcomes or provider failures as
algorithm evidence. No mechanism or mandatory research action is prescribed.

## Frozen scientific design

Same complete 100-file R12-A-fixed source as R14–R16:
`/home/clawd/research/scion-experiments/v04-cvrp-r13-constructor-fixed-b0-20260926/input_snapshots/candidate`.
No R16 source selection/merge or host algorithm optimization. Earlier common
constructor repair is operator-assisted engineering. Fresh champion v1 is not
a promoted or independently retained improvement over B0-fixed/original B0.

[Research input](inputs/v04-cvrp-r17-quota-aware-autonomous-research-input.json)
keeps the full preceding question and five R4/R5/R6/R8/R13 observations, appending
R16 screening/public-development facts. All sixteen ordered histories
(R3–R3i, R7, R9, R11, R12, R14, R15, R16) are loaded whole. R16 contributes all
six safe rows / 74 screening pairs, not its private validation or operational
rejections. Read-only loading verifies 165 raw / 142 H-visible rows,
6,982,454 bytes; the exact 10,347-character question and all five projected
observations reach the ordinary H context without truncation or selection.

[Protocol](inputs/v04-cvrp-r17-quota-aware-autonomous-protocol.yaml) equals R16
except version/canary seed. Same R7 split: five initial cases × two seeds;
six expanded cases × four seeds, expansion mandatory. Six-case validation ×
two is already operator-exposed, not independent confirmation; twelve frozen
cases × two remain conditionally unopened. Retained confirmation is separate.
No case drop or threshold relaxation. Dimension limits 60/90/120/180/240
seconds, canary 10; same algorithm fraction/reserve. Champion-first timing
requires subsequent independent counterbalanced confirmation. Do not pool
adaptive discovery with an independent effect estimate.

[Seeds](inputs/v04-cvrp-r17-quota-aware-autonomous-seeds.yaml), selected before
outcomes: first nine primes above 180000. Screening 180001/180007/180023/180043;
validation 180053/180071; frozen 180073/180077; canary 180097.

K=1, max three branches, twelve evaluated stages, gpt-5.6-sol high,
H180/C300, SDK retry0, at most two charged typed redispatches.
600 physical calls, 172800-second outer guard; R3i C limits
12 turns/eight reads/eight searches/four tests, no transcript character cap.
Parameter search disabled. No global or local budget widening.

## Prelaunch and interpretation

Full suite, focused quota-to-campaign tests, input/closure/source checks and
an independent [Warehouse control](v04-r17-warehouse-quota-control-20261003.md)
must finish on the same frozen runtime before CVRP. The control has a two-stage
target and unchanged 80-call cap. A framework defect blocks CVRP. An incomplete
control is not a completed two-stage control; any decision to proceed must
explicitly state actual exercised coverage and limitations before launch.
Quota-stop correctness is established by injected regression tests, not by
intentionally exhausting a live account. One bounded provider inference probe
will check restored service; a model catalog alone is insufficient.

Runtime base: `505dce03` plus the uncommitted, frozen quota repair in
proposal/llm/transport and errors, tests and prospective inputs. No other
runtime changes. Git commit is not required to freeze the ordinary checkout.
No concurrent tests, solvers or maintenance during either formal run. Preserve
all old roots. After startup compare every initial source file and verify actual
H question/history counts and successful provider calls. Startup is not quality
success. Postrun must distinguish engineering correctness, reasoning/test claim
fidelity, complete paired science and retained improvement.

Output: `/home/clawd/research/scion-experiments/v04-cvrp-r17-quota-aware-autonomous-20261003`.
Tmux: `scion-r17-quota-aware-autonomous-20261003`.

## Frozen invocation (executed once)

Read-only preflight passes: 100 unchanged initial source files; all 25 case
inputs parse; complete public/formal closure, strict expansion, resource,
production and Verification composition. No campaign output/provider/solver
is created by these checks. Ten R16/R17 input tests and 163 quota/provider/client
tests pass; Ruff F/E9, new-test formatting and diff checks pass.
At 13:21 UTC one separate bounded gpt-5.6-sol high inference probe returns the
expected structured value with SDK retry0 / 60-second timeout. Credentials
are never printed or stored. This checks service recovery, not future capacity
or scientific quality. Full suite: **2554 passed, 1 skipped in 434.47 s**.
Warehouse completes both requested stages at 13:35:48 UTC: two complete valid
ties with deterministic negative Decisions, 70/80 successful calls, two research
rejections, correct 406-file source and accepted-head continuation. Its full
terminal audit finds no framework blocker; repeated query errors remain a
research-efficiency limitation. This permits the preregistered CVRP launch,
not an improved-reasoning or quality claim. The final absent-output/session,
no-overlap and unchanged runtime checks pass; CVRP launches once at 13:40:12 UTC.
All runtime/inputs remain frozen and uncommitted; only status docs change.

```bash
set -Eeuo pipefail
cd /home/clawd/research/or-autoresearch-agent
test ! -e /home/clawd/research/scion-experiments/v04-cvrp-r17-quota-aware-autonomous-20261003
proxy_key_value=$(curl -fsS --connect-timeout 5 --max-time 15 http://127.0.0.1:8080/auth/status | jq -er '.proxy_api_key | select(type == "string" and length > 0)')
curl -fsS --connect-timeout 5 --max-time 15 -H "Authorization: Bearer $proxy_key_value" http://127.0.0.1:8080/v1/models | jq -e 'any(.data[]?; .id == "gpt-5.6-sol")' >/dev/null
exec env \
  PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
  PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion \
  OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  SCION_PROBLEM_DATA_ROOT=/home/clawd/research/scion-experiment-inputs/v04-cvrp-r6-minus-2for1-b0-20260921/data \
  SCION_MODEL=gpt-5.6-sol SCION_REASONING_EFFORT=high \
  SCION_BASE_URL=http://127.0.0.1:8080 SCION_API_KEY="$proxy_key_value" \
  SCION_LLM_TIMEOUT_SEC=180 SCION_LLM_HYPOTHESIS_RESEARCH_TURN_TIMEOUT_SEC=180 \
  SCION_LLM_CODE_RESEARCH_TURN_TIMEOUT_SEC=300 SCION_LLM_CODE_RESEARCH_FINALIZE_TIMEOUT_SEC=300 \
  /home/clawd/miniconda3/envs/claw/bin/python -B -m scion.cli.main run \
    --problem /home/clawd/research/or-autoresearch-agent/scion/scion/problems/cvrp/problem-v1.yaml \
    --source-tree /home/clawd/research/scion-experiments/v04-cvrp-r13-constructor-fixed-b0-20260926/input_snapshots/candidate \
    --research-input /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r17-quota-aware-autonomous-research-input.json \
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r3-normal-k1-sol-20260828-r1/research_history.jsonl \
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r3b-normal-k1-sol-20260829-r1/research_history.jsonl \
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r3c-normal-k1-sol-20260830-r1/research_history.jsonl \
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r3d-normal-k1-sol-20260830-r1/research_history.jsonl \
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r3e-normal-k1-sol-20260830-r1/research_history.jsonl \
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r3f-normal-k1-sol-20260831-r1/research_history.jsonl \
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r3g-normal-k1-sol-20260901-r1/research_history.jsonl \
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r3h-normal-k1-sol-20260902-r1/research_history.jsonl \
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r3i-normal-k1-sol-20260903-r1/research_history.jsonl \
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r7-autonomous-source-continuation-20260921/research_history.jsonl \
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r9-post-b0-autonomous-20260922/research_history.jsonl \
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r11-wide-budget-autonomous-20260923/research_history.jsonl \
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r12-post-r11-autonomous-20260924/research_history.jsonl \
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r14-post-r13-autonomous-20260927/research_history.jsonl \
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r15-feedback-repair-autonomous-20260927/research_history.jsonl \
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r16-probe-diagnostics-autonomous-20260928/research_history.jsonl \
    --code-research-limits /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r3i-long-run-code-research-limits.json \
    --protocol /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r17-quota-aware-autonomous-protocol.yaml \
    --split /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r7-autonomous-source-continuation-split.yaml \
    --seeds /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r17-quota-aware-autonomous-seeds.yaml \
    --time-limit-sec 60 --rounds 12 --provider-call-cap 600 \
    --provider-transient-retries 2 --outer-hardwall-sec 172800 \
    --campaign-dir /home/clawd/research/scion-experiments/v04-cvrp-r17-quota-aware-autonomous-20261003
```

## Actual startup verification

At 13:41 UTC the ordinary
[status](/home/clawd/research/scion-experiments/v04-cvrp-r17-quota-aware-autonomous-20261003/status.json)
is running in initial H research, champion v1 / weight revision0, no formal
result yet. All 100 champion files exactly equal the declared R12-A-fixed
source, and the recorded research input equals the prospective input.
The [first actual H trace](/home/clawd/research/scion-experiments/v04-cvrp-r17-quota-aware-autonomous-20261003/llm_traces/20261003T134020495241_hypothesis_research_turn_3a67f004.json)
succeeds at attempt index0 on gpt-5.6-sol. Its exact 10,347-character question
matches; indexed wrappers contain 142 safe history rows and five observations,
with all 147 entries in the H research index. Four dispatch traces already exist.
This verifies startup/input fidelity, not scientific success or improved reasoning.
Runtime/inputs stay frozen; no concurrent tests/solvers/maintenance and no Git
commit/push in this turn. Inspect only this exact root for later results.
