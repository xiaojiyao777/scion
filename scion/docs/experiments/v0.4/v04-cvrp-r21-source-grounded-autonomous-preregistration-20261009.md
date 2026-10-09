# CVRP R21: source-grounded autonomous continuation

State: **running**, launched once October9 at20:49:38 Beijing /12:49:38 UTC,
PID696534, tmux `scion-r21-source-grounded-autonomous-20261009`. Planned-command
wording below is now historical; do not launch again. October9 authorizes experiment inspection,
analysis/optimization and a fresh run. [R20 postrun](v04-cvrp-r20-r19-final-b0-fixed-postrun-20261009.md)
records valid72/72 pairs, screening pass but incomplete validation stability
evidence, no promotion. R20 and R19 remain terminal, never resumed.

## Intervention and falsifiable question

Can autonomous H/C improve the complete discovered A3 source, using correct
inheritance and stronger interpretation of independent-reference and real-entry
tests, while producing a stable full-case/seed pattern? No host-selected solver
mechanism, sibling merge, mandatory test style or new quality gate.

Select the **complete100-file R20 candidate snapshot**, byte-equal to R19 A3:
`/home/clawd/research/scion-experiments/v04-cvrp-r20-r19-final-b0-fixed-20261008/input_snapshots/candidate`.
This is a local development baseline, not a claim of promotion/retention and not
a restoration of old branch/provider state. A new ordinary campaign starts at
champion:v1. It includes earlier research, the common constructor repair and
the cumulative R19 A-branch insertion cache, supplemental exchanges and ordinary
swap indexing; it does not silently inherit B/C sibling mechanisms.

No production code, solver, generic prompt, Contract, Verification, Protocol gate,
adapter or Decision implementation changes. Optimize the problem-owned research
input and complete-source continuity. A new explicit current frame precedes the
**entire unchanged R19 question**, delimited as historical (its old present-tense
source/design descriptions no longer apply). Preserve all five observations
exactly. Append public source/testing facts and all48 R20 screening deltas,
including its negative pair, with the correct comparator. R20's private
validation/terminal facts, later-stage cases/seeds/paths and control results
must not enter H/C. No artificial positive terminal observation is fabricated.

Load all nineteen declared history files whole in chronological order: the same
eighteen R19 inputs plus all twelve safe R19 screening records. R20 has no H/C
history and no fabricated history file. No ranking, truncation, summary substitute
or selective record load. An inheritance claim in old prose is not source
evidence. Distinguish helper correctness, real entry, completed transition,
acceptance and retention; deadline-only probes do not establish large-path
completion. H/C retain algorithm and test choice. A negative/uncertain scientific
result is not a framework bug or authorization for a host recipe.

## Prospective design and limits

[Research input](inputs/v04-cvrp-r21-source-grounded-autonomous-research-input.json),
[Protocol](inputs/v04-cvrp-r21-source-grounded-autonomous-protocol.yaml), and
[seeds](inputs/v04-cvrp-r21-source-grounded-autonomous-seeds.yaml).
Protocol is exactly R20 except version and canary seed: initial5×4,
mandatory expanded6×8, conditional validation6×4 and frozen12×4. The autonomous
driver, unlike the R20 fixed funnel, starts at initial screening. This retains
R20's prospective denser sampling rather than restoring R19's6/2/2 counts.
All case populations, practical margins, CI/case-score/loss gates, feasibility,
fleet protection and dimension limits60/90/120/180/240seconds remain unchanged.
Canary10seconds and algorithm time fractions/reserves stay fixed.

Seeds are the first17 primes above270000, chosen before outcomes and disjoint
from all checked-in prior ledgers:

| Stage | Seeds |
|---|---|
|Screening|270001,270029,270031,270037,270059,270071,270073,270097|
|Validation|270121,270131,270133,270143|
|Frozen|270157,270163,270167,270191|
|Canary|270209|

Same R7 main split. No new retained data opens in this autonomous campaign.
Validation is already exposed development evidence; no claim of unseen
generalization. Frozen remains conditional. No posthoc extra seeds or gate
relaxation. Bootstrap aggregation is case-level; more seeds do not fix case
heterogeneity or the absence of prospectively calibrated MDE/power.

K=1/max three branches,12 evaluated stages, gpt-6.1-sol high,600 physical calls,
two charged typed redispatches, SDK retry0,172800-second48-hour outer guard.
H180/C300 timeouts; unchanged R3i C limits12 turns/8 reads/8 searches/4 tests,
uncapped transcript characters, parameter search off. Longer dense evaluations
may hit the existing guard or stop with queued validation; preserve incompleteness
instead of resuming/expanding the cap.

R21 uses ordinary champion-first autonomous pairs, not R20's counterbalanced
fixed funnel. It compares against A3 (and a later actual champion if promoted),
not B0-fixed or R12-A-fixed. Do not pool these different contrasts or claim an
isolated effect of source continuation versus question/sampling changes.
Promising exact source needs a separate counterbalanced independent retained
test; original-B0 superiority is still a distinct unmet objective.

## Verification and launch boundary

Runtime remains6380a59e, checkout starts clean at3d2123e3. This turn changes only
new experiment inputs, focused tests and documentation. No shared change means
no new Warehouse control is needed; the prior complete P16 control remains
evidence for this unchanged implementation.

Before launch: input regressions, whole-source equality/AST parse, all25
main/canary case resolution/load and public/formal closure, whole history
normalization, actual H question/observations/history/source projection and C
read-only/editable separation. Check fresh root/session, disk and no live
measurements/tests. One bounded provider health inference is allowed; no secret
printing/storage or hidden retries. Freeze runtime/scientific inputs before
dispatch; no concurrent tests, maintenance or other solvers during measurement.
Only lifecycle docs may change afterward.

At startup verify all100 initial source files, the exact question, five safe
observations,182 H history entries and30 source entries, resource envelope and
first successful actual H trace. A failed provider call may consume only the
existing explicit allowance; do not create a second run to conceal it.
Startup establishes execution, not research quality or scientific improvement.

Output: `/home/clawd/research/scion-experiments/v04-cvrp-r21-source-grounded-autonomous-20261009`.
Tmux: `scion-r21-source-grounded-autonomous-20261009`.
No Git commit/push accompanied launch. The subsequent October9 user request
authorizes committing/pushing this frozen analysis/input/test/doc set; it does
not change launch provenance, runtime, source snapshots or scientific inputs.

## Planned direct invocation

Execute once after verification; after launch this command is historical.

```bash
set -Eeuo pipefail
cd /home/clawd/research/or-autoresearch-agent
test ! -e /home/clawd/research/scion-experiments/v04-cvrp-r21-source-grounded-autonomous-20261009
proxy_key_value=$(curl -fsS --connect-timeout 5 --max-time 15 http://127.0.0.1:8080/auth/status | jq -er '.proxy_api_key | select(type == "string" and length > 0)')
curl -fsS --connect-timeout 5 --max-time 15 -H "Authorization: Bearer $proxy_key_value" http://127.0.0.1:8080/v1/models | jq -e 'any(.data[]?; .id == "gpt-6.1-sol")' >/dev/null
exec env \
  PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
  PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion \
  OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  SCION_PROBLEM_DATA_ROOT=/home/clawd/research/scion-experiment-inputs/v04-cvrp-r6-minus-2for1-b0-20260921/data \
  SCION_MODEL=gpt-6.1-sol SCION_REASONING_EFFORT=high \
  SCION_BASE_URL=http://127.0.0.1:8080 SCION_API_KEY="$proxy_key_value" \
  SCION_LLM_TIMEOUT_SEC=180 SCION_LLM_HYPOTHESIS_RESEARCH_TURN_TIMEOUT_SEC=180 \
  SCION_LLM_CODE_RESEARCH_TURN_TIMEOUT_SEC=300 SCION_LLM_CODE_RESEARCH_FINALIZE_TIMEOUT_SEC=300 \
  /home/clawd/miniconda3/envs/claw/bin/python -B -m scion.cli.main run \
    --problem /home/clawd/research/or-autoresearch-agent/scion/scion/problems/cvrp/problem-v1.yaml \
    --source-tree /home/clawd/research/scion-experiments/v04-cvrp-r20-r19-final-b0-fixed-20261008/input_snapshots/candidate \
    --research-input /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r21-source-grounded-autonomous-research-input.json \
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
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r18-research-context-autonomous-20261004/research_history.jsonl \
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r19-reliable-probes-autonomous-20261005/research_history.jsonl \
    --code-research-limits /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r3i-long-run-code-research-limits.json \
    --protocol /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r21-source-grounded-autonomous-protocol.yaml \
    --split /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r7-autonomous-source-continuation-split.yaml \
    --seeds /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r21-source-grounded-autonomous-seeds.yaml \
    --time-limit-sec 60 --rounds 12 --provider-call-cap 600 \
    --provider-transient-retries 2 --outer-hardwall-sec 172800 \
    --campaign-dir /home/clawd/research/scion-experiments/v04-cvrp-r21-source-grounded-autonomous-20261009
```

## Verification and actual execution

Input regressions:33 passed in1.46seconds, including six new R21 tests.
Whole-history chronology/public-dependency/query-boundary regressions:138 passed
in1.92seconds. These171 tests are focused coverage, not a newly run full suite.
Production implementation remains unchanged from6380a59e. Ruff F/E9, diff and
CLI help checks pass.

Read-only preparation verifies100 complete source files/48 AST-parsed Python
files, all25 main/canary cases resolved and loaded, public/formal closure and
fresh output. Nineteen whole files contain200 raw/normalized records; the
existing H projection exposes177 safe records plus five unchanged observations,
182 indexed histories and30 source entries. Exact18,949-character question and
observations match; private-case/result sentinels are absent. C has17 read-only
support bodies plus two public tests,5 visible editable bodies and6 editable
index-only entries, with no editable/read-only collision. The context-only
diagnostic hypothesis is never dispatched or supplied to the research agent.

Initial audit assertions were corrected to distinguish raw versus safe-history
counts, support files versus public tests, and the existing renderer's one fence
newline; these were diagnostic assumptions, not runtime defects. R19's historical
directory has10 additional October6 bytecode cache files; all100 ordinary files
exactly match the cache-free selected R20 snapshot. No old directory was changed.
No live campaign/solver/tests are found;57.7GiB free. Scientific inputs are frozen
after verification. One bounded gpt-6.1-sol high health inference succeeds
October9 at20:48:54 Beijing /12:48:54 UTC,3.77seconds, SDK retry0. No key is
printed or saved. Launched once at20:49:38 Beijing /12:49:38 UTC, PID696534.
Status records running round1 hypothesis research, zero evaluated stages. Actual
startup audit passes: all100 initial champion files exactly equal the selected
R20 source; stored research input, C limits and600-call/two-redispatch/172800-second
envelope match. First actual H succeeds at attempt0 on gpt-6.1-sol with180-second
policy; trace `llm_traces/20261009T124947473560_hypothesis_research_turn_e2ea6efc.json`.
Its exact18,949-character question,182 history indexes and30 source indexes match
the independently assembled context (JSON-normalized tuple representation only).
All five prior observations remain indexed, with177 safe history records; private
case/result sentinels are absent. At startup audit four H calls are recorded and
no formal stage is complete. Carrier remains live PID696534. No tests or runtime/
input edits follow launch; only lifecycle documentation. Successful startup is
not evidence of new research quality, gain stability or promotion.
