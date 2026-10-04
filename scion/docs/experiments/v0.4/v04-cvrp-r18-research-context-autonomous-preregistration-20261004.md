# CVRP R18: public research context and exact-reference support

State: preregistered, not launched. October 4 user explicitly authorizes
coordinated subagents to implement the R17 follow-up, verify, commit/push, then
run fresh experiments. [R17 postrun](v04-cvrp-r17-quota-aware-autonomous-postrun-20261004.md)
is operator-only; its private validation findings are not research inputs.

## Intervention and falsifiable questions

Separate problem-declared public read-only dependency source from editable
algorithm source; provide bounded query correction feedback; strengthen optional
problem-owned real-entry and independent exact-reference probe examples.
The implementation must preserve exact current source, explicit public closure,
frozen edit protection and held-out exclusion. Invalid commands remain invalid
and charged, with no auto-repair, hidden retry or enlarged research budgets.
Examples support agent-authored tests, not a mandatory test style or new gate.

The research questions are whether actual H/C can use the declared support
source and recover from invalid queries, and whether probes exercise their
claimed real mechanism with correct independent reference values. These are
postrun research questions, not Contract/Verification/Protocol or Decision
inputs. The model may choose not to query or use an example. No per-mechanism
read requirement, novelty test, telemetry gate or host-selected solver edit.

## Frozen scientific design

Unchanged complete 100-file R12-A-fixed initial algorithm:
`/home/clawd/research/scion-experiments/v04-cvrp-r13-constructor-fixed-b0-20260926/input_snapshots/candidate`.
No R17 candidate is merged or reconstructed. The common constructor repair is
earlier operator-assisted engineering, not autonomous discovery. A fresh local
champion v1 does not imply promotion or superiority over B0-fixed/original B0.

[Research input](inputs/v04-cvrp-r18-research-context-autonomous-research-input.json)
preserves the complete preceding question and all five R4/R5/R6/R8/R13
observations, adding only screening/public-development context. All seventeen
ordered histories (R3–R3i, R7, R9, R11, R12, R14, R15, R16, R17) are loaded whole.
R17 adds all eleven screening rows / 166 pairs, not validation or operational
facts. No favorable-record selection, top-k or context truncation.
The prospective question has 11,345 characters before any provider projection.

[Protocol](inputs/v04-cvrp-r18-research-context-autonomous-protocol.yaml) equals
R17 except version/canary seed. Same R7 split: five initial cases × two seeds,
mandatory six-case × four-seed expansion, six validation cases × two, twelve
frozen cases × two. Validation is already operator-exposed, not independent
confirmation; frozen and retained evidence remain conditionally unopened.
Retained confirmation is separate. No case drop, changed threshold, extra
stage or budget widening. Dimension limits 60/90/120/180/240 seconds, canary10;
same algorithm fraction/reserve. Champion-first order remains an acknowledged
limitation, requiring independent counterbalanced confirmation of any claim.

[Seeds](inputs/v04-cvrp-r18-research-context-autonomous-seeds.yaml) are the first
nine primes above 200000, fixed before outcomes: screening
200003/200009/200017/200023; validation200029/200033; frozen200041/200063;
canary200087. K=1/max three branches, twelve evaluated stages, gpt-5.6-sol high,
H180/C300, SDK retry0/two charged typed redispatches, 600 physical calls and
172800-second outer guard. Unchanged R3i C limits: 12 turns, eight reads,
eight searches, four tests, no transcript character cap. Parameter search off.

## Verification, commit and launch conditions

Runtime base is `7e1fd7dc` plus the P14 repairs/tests/inputs to be frozen and
committed/pushed before dispatch. Record the actual revision below after tests.
Focused adversarial source/feedback/probe tests, the full framework suite,
public/formal closure, complete source comparison, prospective inputs and
actual safe H projection must pass before formal measurement.

Because shared context/query boundaries change, an independent
[Warehouse control](v04-r18-warehouse-research-context-control-20261004.md)
runs first on the same frozen runtime, two evaluated stages / 80 calls.
Audit its actual source delivery, corrections, H/C, safety and paired outcomes.
A framework defect blocks CVRP. An incomplete control remains incomplete;
do not silently extend or resume it, and do not present it as two-stage coverage.
No control outcomes enter CVRP H/C. One bounded inference health probe may
check service before both runs; credentials must never be printed or stored.

No tests, solvers, maintenance or runtime/input edits overlap either measurement.
Only status/analysis documentation may change. No terminal campaign resumes.
R17 and all earlier roots stay untouched. At CVRP startup compare all 100 initial
files, exact question/observations/history index and successful actual H calls.
Startup is not improved research or scientific success.

Output: `/home/clawd/research/scion-experiments/v04-cvrp-r18-research-context-autonomous-20261004`.
Tmux: `scion-r18-research-context-autonomous-20261004`.

## Planned direct CLI invocation

Not executed at preregistration. No generated launcher or prepared runtime.

```bash
set -Eeuo pipefail
cd /home/clawd/research/or-autoresearch-agent
test ! -e /home/clawd/research/scion-experiments/v04-cvrp-r18-research-context-autonomous-20261004
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
    --research-input /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r18-research-context-autonomous-research-input.json \
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
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r17-quota-aware-autonomous-20261003/research_history.jsonl \
    --code-research-limits /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r3i-long-run-code-research-limits.json \
    --protocol /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r18-research-context-autonomous-protocol.yaml \
    --split /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r7-autonomous-source-continuation-split.yaml \
    --seeds /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r18-research-context-autonomous-seeds.yaml \
    --time-limit-sec 60 --rounds 12 --provider-call-cap 600 \
    --provider-transient-retries 2 --outer-hardwall-sec 172800 \
    --campaign-dir /home/clawd/research/scion-experiments/v04-cvrp-r18-research-context-autonomous-20261004
```

## Actual verification and startup

Implementation and independent cross-review complete. Focused groups pass
132 source/context, 113 feedback/source and 51 reference/probe/provider tests
(overlapping, not additive); the five new input regressions pass. The optional
complete probe passes within the unchanged ten-second sandbox on both repository
source and the unchanged selected R12-A-fixed source copy.

Read-only preflight: all 100 initial files parse/check; all 25 formal/canary
instances load; public/formal closure passes. Seventeen whole history files
contain 176 raw records, yielding 153 safe H records plus five unchanged
observations (158 history-index entries). Exact question is 11,345 characters;
the H source index has 30 entries and C has 17 declared readonly dependencies.
`models.py` is available in both phases and absent from editable C source.
No output directory, provider call or solver call is created by this preflight.
Full suite passes **2622 tests / one skip in 446.02 s**. The first full run had
2620 pass and two old-schema test-fixture failures; only the prompt fixture was
aligned to include a nonempty readonly source, retaining all exact assertions.
Seventeen prompt/input tests and the complete second suite pass. Production code
was unchanged between full runs. Changed-file Ruff F/E9 and diff checks pass.
Git push and terminal Warehouse audit remain pending.
