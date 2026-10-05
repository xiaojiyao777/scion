# CVRP R18: public research context and exact-reference support

State: **completed / valid**, 12/12 screening stages, 176/176 valid pairs,
no promotion. Launched once on October 4 at 12:04:15 Beijing / 04:04:15 UTC;
terminal status October 4 21:56:58 Beijing / 13:56:58 UTC. The startup and
interim sections below are dated historical snapshots; terminal findings follow.
October 4 user explicitly authorizes
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

Frozen at preregistration, subsequently executed once as recorded below.
No generated launcher or prepared runtime.

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
Runtime and inputs committed/pushed as `1596347c` before provider dispatch.
Warehouse started once at 11:39:12 Beijing (03:39:12 UTC), after a successful
single bounded inference health check. It completed at 12:00:17 Beijing:
2/2 valid tie stages, 48 successful calls, one C research rejection, no observed
execution/scientific blocker. Independent source/context and feedback audits
pass. Three repeated new-file read errors, three rejected readonly edits and
three import-preflight rejections remain visible research limitations; no causal
efficiency or algorithm-quality claim. See the full control report. Its outcomes
are operator-only and are not appended to the frozen CVRP research input.

CVRP subsequently launched once at **12:04:15 Beijing / 04:04:15 UTC**, PID 480652,
on the same `1596347c` runtime and inputs. All subsequent checkout changes are
status/analysis docs only. Before launch no live tests/solvers were present;
the completed Warehouse carrier was dead. The direct CLI remains running in
the named tmux session; do not restart or resume a later terminal campaign.

Startup audit compares all 100 initial files byte-for-byte with the selected
complete R12-A-fixed source. Actual first H succeeds (04:04:17–04:04:21 UTC),
with exact 11,345-character question, 158 history-index entries (153 safe records
and five observations), 30 source entries including 17 declared readonly
dependencies. Resource envelope is exactly 600 calls / 172800 seconds / two
charged transient redispatches. No Warehouse control output or private R17
validation detail is added. Startup has zero evaluated stages and is not an
algorithm-quality or research-efficiency result.

## Read-only interim analysis — October 4, 21:05 Beijing

This is an in-flight observation, not a terminal postrun or an amendment to the
frozen design. The latest user request authorizes inspection/analysis only.
Checkout is clean at pushed `484433ea`; differences from runtime `1596347c` are
documentation only. No provider, test, solver, resume, runtime/input edit or Git
commit/push was performed by this analysis. The original campaign and SQLite
were not modified/opened. The live process snapshot shows the campaign's solver
as the only busy solver; this does not establish continuous historical absence
of competing load. Champion-first ordering and missing matched calibration remain
limitations; no causal speedup claim is made from budget-exhausting runtimes.

### Live scope and completed Protocol evidence

`status.json` at `2026-10-04T13:05:49.818255+00:00` reports running, ten of twelve
evaluated stages, all screening, seven distinct H/C candidates. Round 11 is A3's
expanded screen: 21/24 valid pairs complete, pair 22 running. No terminal summary
exists yet. The ten complete metric files contain **142/142 valid pairs**; do
not add unfinished round-11 pairs to that completed-stage population. No
research rejection, formal pair failure, promotion, validation or frozen stage.
The initial local champion remains v1, unchanged R12-A-fixed.

There are 77 physical traces: H35 successful; C42 dispatches, 41 successful and
one 300-second timeout. Its charged redispatch has exactly the same context,
system blocks and user prompt and succeeds. No quota exhaustion; 523/600 calls
remain. Admitted-call counts must not be described as all-successful calls.

Each row compares that complete branch candidate against the same local
champion. Delta is champion minus candidate total distance: positive is better.
Initial populations are five cases/two seeds; expanded populations six/four.
W/L/T counts cases, not individual pairs. These are separate estimands, not a
continuous improvement curve. Recorded decisions are preserved, not rejudged.

| Stage | Candidate mechanism | Population | Case W/L/T | Median delta [CI] | Recorded result |
| --- | --- | --- | --- | --- | --- |
| 1 | A1: VNS/ALNS interleaving | Initial | 1/2/2 | 0 [-28,1804] | Fail |
| 2 | B1: exact two-route windows | Initial | 1/1/3 | 0 [-12.5,65] | Fail |
| 3 | C1: exact 2-opt delta + don't-look | Initial | 3/0/2 | +3 [0,544] | Expand |
| 4 | Same C1 | Expanded | 2/1/3 | 0 [-261.25,26.75] | Fail |
| 5 | A2: synchronized ALNS batches | Initial | 2/1/2 | 0 [-112.5,1623.5] | Expand |
| 6 | Same A2 | Expanded | 1/3/2 | -0.5 [-14.5,135.75] | Fail |
| 7 | B2: replace windows with ejection chain | Initial | 1/2/2 | 0 [-40.5,15] | Fail |
| 8 | C2: retain exact delta, remove don't-look | Initial | 2/0/3 | 0 [0,82.5] | Expand |
| 9 | Same C2 | Expanded | 1/1/4 | 0 [-1.5,91] | Fail |
| 10 | A3: route-shape scheduling guard | Initial | 1/0/4 | 0 [0,1712.5] | Expand; round 11 pending |

All 284 completed solver sides report valid solutions, zero fleet violation and
no algorithm errors. Every raw distance difference, per-case median and overall
median agrees with the recorded aggregate. Case/seed rosters and 60/90/180-second
limits match the frozen populations. These checks do not independently rerun
feasibility or the Decision engine. Expansion is additional evidence collection,
not a screening pass or promotion.

### H/C source delivery and research behavior

All 264 visible editable C source values match their selected branch bases;
all 714 public readonly values and 84 public-test values match frozen problem
runtime source. Public tests intentionally come from that runtime, including the
new optional example, not the older selected algorithm snapshot. H's 35 visible
source values match their branch sources with only the renderer's one appended
newline. The champion and all three current heads retain complete 100-file trees,
matching their own recorded changes; A changes scheduler only, B scheduler plus
local_search, C local_search only. No sibling merge or stale-source mismatch was
found. The four superseded candidate trees are no longer present: changed source
is retained in history/traces, but their full stage-source attribution is
`UNIDENTIFIABLE` in this audit. Current A3/B2/C2 heads are `FULL_SOURCE_IDENTIFIED`.
No runnable historical tree or new provenance artifact was manufactured.

H performs eleven source reads, eleven history reads, six frontier reviews and
seven finalizations, with no failed H query. Continuations explicitly distinguish
their inherited branch changes from unmerged siblings and respond to negative
screening evidence. C has one failed directory-path search; the typed
`omit_path_or_use_exact_listed_file` correction is followed by a successful exact
file read. Two edit failures (`duplicate_file_path`, `selector_not_found`) also
recover. Public dependencies are delivered, but this CVRP sample has no explicit
dependency-file query; delivery is not proof that the repair caused better
research. Do not infer causal efficiency improvement from a cross-run call count.

The eleven development test calls all pass the five standard checks. Optional
probe outcomes are four passed, three failed then revised, two inconclusive and
two omitted. This separates standard check success from self-probe success:

- A1 and A2 submit module-level scripts without collected `test_*` functions and
  receive `inconclusive`, not `passed`. The pytest runner maps non-test-failure
  exits to inconclusive; absent collection is consistent with these sources,
  but a raw exit code is not retained in C feedback. A1 calls the real entry;
  A2 replaces construction, budget, VNS and destroy/repair collaborators. Neither
  recorded outcome establishes its proposed scheduler mechanism.
- B1's passed test is named `matches_bruteforce`, but contains no brute-force
  enumeration or independent optimum. It checks a strict improvement, feasibility
  and independently summed route cost; the second test checks mocked wiring.
  B2 submits only standard tests, with no self-authored mechanism probe.
- C1 initially attempts to assign an instance method on slotted `_Solution` and
  receives a bounded AttributeError at probe line 64. Its corrected class-level
  observation test and C2's later test pass an independent full-rescore reference
  over all 120 starts of a five-customer asymmetric synthetic model, comparing
  every accepted transition and final route/cost. This is real bounded exactness
  evidence, not production throughput or general equivalence under time cutoff.
- A3's first two failures are erroneous numerical expectations: for time limit
  1, reserve is 0.05 and handoff is **0.335**, not 0.321; for limit 10, reserve is
  0.3 and handoff is **3.21**, not 3.35. Both failure lines reach C. C rewrites
  scheduler code after each failure rather than first establishing that the
  expected value is correct. Its final probe passes but still mocks construction,
  ordinary operators, full VNS and budget; it proves dispatch for supplied route
  shapes, not real-entry/real-construction integration or timed search benefit.

### Mechanism evidence and remaining limits

- **A1 is partial relative to H.** H says no fixed fraction and a completed first
  sweep; C imposes a 30% reserve and may stop before that sweep completes, then
  reserves half of each remaining slice through a budget-method wrapper. A2
  recognizes and replaces this inherited design with one incumbent-synchronized
  batch implementation. This is substantive autonomous correction, not just text.
- **A2/A3 code is a real scheduler change, but repeated batches are unobserved on
  the large cases.** In A2's expanded screen X351 runs 1/1/1/4 ALNS iterations;
  X513 runs one each. No large-case `vns_batch` phase is recorded. Iteration counts
  include failed/incomplete trials: X513's four trials all fail to improve best.
  The +271.5 X351 case median hides seed deltas +2337/+2784/-2405/-1794. The
  headline batch mechanism therefore has much weaker activation evidence than a
  simple reserved-time single perturbation; initial two-seed gains are unstable.
- **B's new intensifiers do not reach the targeted large-case bottleneck.** B1
  records six window invocations and zero improvements, none on X351/X513. B2
  records six invocations and four improvements, again none on those large cases.
  Its historical `vns_boundary_window` label now represents the replacement
  ejection-chain routine, not DP success. Its smaller-case activation still fails
  whole-candidate quality. Placing more work after unfinished initial VNS does
  not establish useful large-case activation.
- **C's kernel correctness lead does not establish solver improvement.** C1's
  expanded screen has 308 fewer ALNS iterations and X351 median -522.5. C2 removes
  the stale filtering policy; expanded X351 improves +182 but tai100 loses -3 and
  four cases tie, leaving overall median zero and a failed gate. Both versions
  still execute zero ALNS iterations on X351/X513. More efficient arithmetic alone
  has not demonstrated escape from the initial-search budget bottleneck.
- **A3 is a local lead, not a generic solution.** Its initial X351 deltas are
  +2116/+1309 (median +1712.5), with one best-improving ALNS trial each. X513 is
  restored to the canonical path, zero ALNS and exact ties; the other three cases
  tie. Source chooses `cross_work / within_work >= 12` and explicitly motivates
  it by the observed 40-route and 21-route regimes. This is adaptive public-screen
  fitting, not private-data leakage or a forbidden mechanism; generalization is
  unproven. Round 11 must complete before interpreting the expanded population.

### Separate verdicts and next action

**Framework correctness:** no observed source-delivery, query-feedback or
completed Protocol arithmetic blocker on the exercised paths; one bounded
transport timeout recovers correctly. This is an in-flight, limited verdict,
not certification of every framework boundary.

**Research effectiveness:** real source-grounded algorithm edits and stronger
tiny exact-reference tests exist, but no completed candidate has passed expanded
screening. Main remaining limits are test-oracle arithmetic, mocked/uncollected
scheduler probes, activation depth and seed/generalization stability. More calls
or weaker gates are not supported remedies.

Keep runtime/inputs frozen and inspect the normal terminal output when available;
do not restart or resume. A later authorized repair could expose bounded
no-tests-collected feedback, clarify pytest collection and independent expected
value calculation, and support optional real construction/dispatch probes over
multiple public route shapes. Keep these as research aids, not mandatory style,
new gates or host-chosen solver mechanisms. No new experiment is launched here.

### Exact ordinary evidence references

All paths below are relative to the single output root declared above:
`status.json`, `research_history.jsonl`, `llm_traces/`, the three status-linked
`candidate_workspaces/` heads and `champions/champion_v1`.
The complete metric files in stage order are:

1. `metrics/e95f3359-c65f-4b12-b1ae-7266f0dc7e2c.json`
2. `metrics/6b8645d5-1e4a-4bbd-a9ef-ab5d96ea028b.json`
3. `metrics/1b97f74e-0019-4fdf-b55d-697d53240a27.json`
4. `metrics/9781fb47-3294-4d2b-94fe-4304b5c5c2a5.json`
5. `metrics/67dffbc5-4c1e-4f2a-99fe-f63e87513f19.json`
6. `metrics/071e253d-78d5-44ae-b7f6-94b9340ad573.json`
7. `metrics/c5045928-7fb7-46cb-ac7a-1c29b7947fa4.json`
8. `metrics/0f58c56f-5592-41c5-a1a0-24de4658da69.json`
9. `metrics/adffacb9-5814-4479-8f48-5b7794892620.json`
10. `metrics/b4eaf028-7885-4bd7-8700-a2ba72980ab9.json`

Representative trace references: recovered timeout
`20261004T045427645654_code_research_turn_6043d1e0.json` and redispatch
`20261004T045817822577_code_research_turn_b441af77.json`; C1 corrected exact probe
`20261004T053845261742_code_research_turn_f2094567.json`; C2 exact probe
`20261004T094915385382_code_research_turn_fa5613c6.json`; A3 erroneous expected
values in `20261004T113400811137_code_research_turn_84b53447.json` and
`20261004T113541030591_code_research_turn_bc081b4b.json`, final mocked probe in
`20261004T113722713450_code_research_turn_55a307e0.json` with passed feedback in
`20261004T113735734960_code_research_turn_b3b0ab40.json`.

[Live ordinary status](/home/clawd/research/scion-experiments/v04-cvrp-r18-research-context-autonomous-20261004/status.json)
is the next operational pointer; use corresponding terminal/metric evidence
when available. Frozen/retained confirmation and any original-B0 superiority
remain open.

## Terminal analysis October 5

The October 5 request authorizes terminal analysis, research-support optimization
and a fresh experiment, emphasizing test reliability, actual execution paths and
stable gains. It does not authorize resuming R18 or another Git commit/push.
Entry at pushed `484433ea` preserves the three preceding analysis/status edits.
All carriers are dead; R18 exit0 is operational evidence only. Ordinary
[status](/home/clawd/research/scion-experiments/v04-cvrp-r18-research-context-autonomous-20261004/status.json)
and [summary](/home/clawd/research/scion-experiments/v04-cvrp-r18-research-context-autonomous-20261004/campaign_summary.json)
establish `completed / requested_rounds_completed / valid` at
`2026-10-04T13:56:58.582475+00:00` (21:56:58 Beijing).

All twelve evaluated stages are screening: eight distinct cumulative candidates,
176/176 valid pairs, all 352 solver sides feasible with fleet_violation0 and
empty error lists. Every new candidate passes Contract, Verification and canary;
expansion reuses the same candidate rather than rerunning those checks. No
research rejection, interrupted stage, validation, frozen or promotion. The
local champion remains unchanged R12-A-fixed v1. There are 89 physical
dispatches: H40 successful, C49 including one recovered 300-second timeout;
511 of600 calls remain. No quota or global-cap exhaustion.

The first ten stages and seven candidates are analyzed above. The remaining two
stages change the provisional interpretation as follows; positive distance
delta means champion minus candidate, not an isolated component contribution.

| Stage and candidate | Valid pairs | Case W/L/T | Case median and CI | Decision |
| --- | --- | --- | --- | --- |
| 11 A3 route-shape scheduler expansion | 24 | 1/2/3 | 0 [-255.5,0.25] | SCREENING_FAIL_CASE_QUALITY |
| 12 B3 displacement chain initial | 10 | 2/1/2 | 0 [-12.5,25] | SCREENING_EXPAND_INITIAL_QUALITY |

A3's [expanded metric](/home/clawd/research/scion-experiments/v04-cvrp-r18-research-context-autonomous-20261004/metrics/5992dc1a-4299-4add-8b3d-d3bf2aac2bc0.json)
has case medians B34=0, tai100=-9.5, X351=-501.5, A54=+0.5, X190=0,
X513=0. X351 expanded seed deltas are +3791,+1537,-2714,-2540; candidate
ALNS counts are 1,1,2,4. Only the first two seeds improve best during ALNS.
Thus the earlier two-seed X351 +1712.5 signal does not survive wider sampling.
The first two seed values also differ across separate timed stages; do not treat
expansion as adding observations to an unchanged deterministic initial sample.
All X513 expansion pairs still have zero ALNS and exact terminal ties. Avoiding
the prior X513 regression is not sufficient for stable positive quality.

B3's [initial metric](/home/clawd/research/scion-experiments/v04-cvrp-r18-research-context-autonomous-20261004/metrics/f411566b-eda3-4f31-8a8a-38a3f50d6051.json)
has B34=0, tai100=-12.5 (seeds +28,-53), X351=+25 (+1,+49),
X190=+15 (-46,+76), X513=0. Expansion is requested but not executed before
the twelve-stage terminal stop. Six boundary-window invocations and four
improvements occur on the smaller/tai/X190 cases; none occurs on X351/X513.
Those counters do not prove a displacement chain completed, and the X351 signal
cannot be assigned to an uninvoked helper.

### Final mechanism and revision failure

The last H correctly identifies that its inherited helper only makes immediately
feasible relocations, not capacity-displacing chains. B3 adds a carried-customer
beam search, but its materializer removes the ejected resident in step one and
then requires that resident to remain in the previous destination at step two.
Inspection of the actual final source shows that a genuine multi-step displacement
therefore returns None; non-ejecting one-step relocation is still possible.
This is a source-derived mechanism defect, not a failed formal feasibility check.
Host public checks can pass because that transition is not exercised.

Actual C notices the defect: after its first draft passes host checks without a
falsifier, it tries three corrections selecting the new materializer text. All
three return `selector_not_found`, because each revise replaces the entire draft
against the original session base, and read_source also returns that base.
The final ready retains draft1. The existing interface needs a clearer statement
of replacement semantics, not automatic patch composition or host algorithm repair.
Exact traces are the seven C records from `20261004T132159281285` through
`20261004T132335338294` in this campaign's `llm_traces`; the first failed repair
is `20261004T132234976214_code_research_turn_43931289.json`.

### Integrity audit and limits

All twelve raw metric populations, valid distance differences, case medians and
aggregate medians reconcile with recorded results. All89 traces are accounted
for. Independent branch-history comparison checks 299 visible editable C values,
833 readonly values, 98 public-test values across49 C contexts and40 visible H
source values. Public tests are compared with the frozen `1596347c` runtime, not
with the newer research-support edits. Champion and surviving A3/B3/C2 heads each
contain100 exact source files matching their initial tree plus recorded changes.
Five superseded full stage trees no longer survive; changed source remains in
history, but full historical-stage attribution is limited. No runnable historical
candidate is reconstructed and no original SQLite or terminal evidence is changed.

R18 is valid negative discovery, not evidence that Scion has solved CVRP. Research
issues are now more specific than generic query efficiency: incorrect expected
values, uncollected or mock-only probes, missing real accepted-transition checks,
failed draft correction, and unstable case/seed gains. Champion-first order,
adaptive known screening cases and absent matched calibration still prevent
retained/causal performance claims. More seed coverage cannot fix those limitations.

The authorized next rung is [fresh R19](v04-cvrp-r19-reliable-probes-autonomous-preregistration-20261005.md):
optional independent arithmetic and real multishape entry examples, bounded
no-tests feedback, explicit draft-base semantics, and prospective four-/six-seed
screening. Preserve all thresholds, per-solve limits, held-out boundaries and
the unchanged complete starting algorithm. Do not repair B3 on the host or resume R18.
