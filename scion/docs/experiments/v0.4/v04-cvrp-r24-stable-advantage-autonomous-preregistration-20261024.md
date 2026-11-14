# CVRP R24: stable final advantage from complete C3

State: **completed valid12/12; no promotion**. See the
[October26 terminal analysis](v04-cvrp-r24-stable-advantage-autonomous-postrun-20261026.md).
The startup record below is historical. October24 user explicitly authorizes
next optimization, experiment design and launch based on the
[R23 terminal analysis](v04-cvrp-r23-r22-final-local-fixed-postrun-20261024.md).
R22/R23 are terminal and never resumed. This is fresh autonomous H/C research,
not another unchanged-C3 resampling or independent original-B0 confirmation.

## Source and bounded intervention

The complete100-file source is R23's read-only candidate:
`/home/clawd/research/scion-experiments/v04-cvrp-r23-r22-final-local-fixed-20261018/input_snapshots/candidate`.
It is exact complete R22 C3, including inherited source and the cumulative
short-string local-search work. No host algorithm edit, sibling merge or patch
reconstruction. Existing CLI source selection makes C3 the new local champion.
Improvement over it is not automatically improvement over R23 A/R19 A3 or B0.

R23 repeated three positive case medians but remained3/2/1 with+33.5
[-3.25,145]. All96 arms retained their own recorded gains, yet seven initially
positive relative leads became final losses because A improved more. A production
best-return bug is not established. The falsifiable question is whether autonomous
research on this complete source can produce more stable final-distance gains
under equal budgets while preserving correctness, including adverse cases.

Only research support/input changes:

- Carry the prior optional public explanation distinguishing own retention from
  relative lead; its executable AST and two collected candidate checks are
  unchanged. This is problem-owned support, not a new gate.
- Prepend a current-source/research frame to the entire unchanged R22 question;
  preserve all five observations. Supply all21 whole chronological histories
  (the20 R22 inputs plus complete R22 history), all R22 safe screening records
  and complete R22-final/R23 public screening matrices including every loss.
- Ask about whole-solver opportunity costs, real changed-path completion,
  independently checked objective/feasibility and stable final quality.
  H/C choose algorithms and optional tests. No required target, neighborhood,
  phase schedule, telemetry activity, shorter search or mandatory test style.

No shared core, adapter, generic prompt, production solver, Contract,
Verification, Protocol or Decision edit. No new Warehouse control is needed.
Private later-stage facts and operational failures are not added to H/C input.
R23 is provider-free and has no research-history file to fabricate.

## Scientific design and resource bounds

[Research input](inputs/v04-cvrp-r24-stable-advantage-autonomous-research-input.json),
[Protocol](inputs/v04-cvrp-r24-stable-advantage-autonomous-protocol.yaml),
[seed ledger](inputs/v04-cvrp-r24-stable-advantage-autonomous-seeds.yaml).

Protocol is exactly R22 except version and canary seed. Same R7 split,
initial5 cases×4 seeds; mandatory expanded6×8; conditional validation6×4 and
frozen12×4. Same feasibility/fleet, margins, bootstrap/net-case/loss-rate gates,
zero equivalence band and dimension-band per-solve limits60/90/120/180/240s,
canary10s. No outcome-dependent dropping, sample extension or relaxed threshold.

Prospective seeds are the first17 primes above300000, disjoint from prior
checked-in ledgers and chosen before outcomes:

|Stage|Seeds|
|---|---|
|Screening|300007,300017,300023,300043,300073,300089,300109,300119|
|Validation|300137,300149,300151,300163|
|Frozen|300187,300191,300193,300221|
|Canary|300229|

Use gpt-6.1-sol high, K=1/max three branches,12 evaluated stages,600 physical
provider calls, two charged typed redispatches, SDK retry0 and172800-second
48-hour outer guard. H180/C300-second transport ceilings; inherited12-turn/
8-read/8-search/4-test Code limits, no transcript-character lifetime cap;
parameter search disabled. No budget widening or terminal resumption.

Autonomous pairs are champion-first, not counterbalanced. Known screening and
already-exposed validation populations are adaptive development; fresh seeds
do not make them globally unseen. Conditional frozen evidence remains separate.
Compare complete candidates with C3 or the actual local promoted champion;
do not pool unlike candidates, populations or comparators. A later warranted
fixed confirmation must use a separately frozen complete source and prospective
balanced pairs against preserved R23 A; original-B0 retention is distinct again.

## Prospective analysis

Separate framework execution from research effectiveness. Audit actual H
source grounding, C fidelity, unforced real collaborators, optional tests and
whether any claimed completed beneficial transition reaches a no-worse final
return. Missing kernel evidence remains missing, not a new candidate veto.
Independently check the paired initial/final identity within pairs; medians
are not additive. The inherited initial checkpoint follows initial local search.
Phase time and iteration counts are descriptive, not causal or quality gates.

Judge final complete-solver quality using every declared pair, uncertainty and
unchanged deterministic Decision. A passing synthetic no-loss test cannot
establish relative advantage. Preserve adverse cases, failures and incomplete
stages. Startup/provider success is not quality, promotion or task closure.

## Prelaunch and execution boundary

Reading profile: Experiment Analysis; mandatory handoff, operations runbook,
postrun handoff and exact R23 analysis/R22 design, plus responsible CLI/context,
input and optional-support regression code. Entry HEAD/local origin ref
`a4476ecc`, branch`v0.4-dev`, with the preceding six-file R23 analysis/support
change set uncommitted. R24 inputs/tests/docs are additional uncommitted changes.
No commit/push is requested. Record this actual provenance, not a clean launch.

Before launch verify source equality/48 Python parses, all25 declared cases,
public/formal closure, unchanged gates/resources, fresh seeds, all21 histories,
exact H question/observations/history index and C editable/public separation.
Run focused regressions and the optional example on an isolated selected-source
copy. Check no concurrent experiment/test/solver, sufficient disk, fresh
directory/session and one bounded successful model inference without secrets.
Freeze runtime, support and scientific inputs before dispatch.

Output:
`/home/clawd/research/scion-experiments/v04-cvrp-r24-stable-advantage-autonomous-20261024`.
Tmux: `scion-r24-stable-advantage-autonomous-20261024`.
After launch only read-only startup checks and lifecycle documentation; no tests,
competing solvers, maintenance or runtime/input edits during measurement.
Check actual initial champion, saved resources/input and first H success/context.

## Direct invocation used once (historical; do not rerun)

```bash
set -Eeuo pipefail
cd /home/clawd/research/or-autoresearch-agent
test ! -e /home/clawd/research/scion-experiments/v04-cvrp-r24-stable-advantage-autonomous-20261024
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
    --source-tree /home/clawd/research/scion-experiments/v04-cvrp-r23-r22-final-local-fixed-20261018/input_snapshots/candidate \
    --research-input /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r24-stable-advantage-autonomous-research-input.json \
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
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r21-source-grounded-autonomous-20261009/research_history.jsonl \
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r22-retained-path-autonomous-20261011/research_history.jsonl \
    --code-research-limits /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r3i-long-run-code-research-limits.json \
    --protocol /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r24-stable-advantage-autonomous-protocol.yaml \
    --split /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r7-autonomous-source-continuation-split.yaml \
    --seeds /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r24-stable-advantage-autonomous-seeds.yaml \
    --time-limit-sec 60 --rounds 12 --provider-call-cap 600 \
    --provider-transient-retries 2 --outer-hardwall-sec 172800 \
    --campaign-dir /home/clawd/research/scion-experiments/v04-cvrp-r24-stable-advantage-autonomous-20261024
```

## Verification and actual execution

Prelaunch checks completed October24.148 focused input/support/diagnostic/
dependency/Contract regressions pass in37.86seconds. The new input test's
initial source-discovery import locator was corrected before this passing run;
no production defect or change. Targeted Ruff F/E9, diff check and CLI help
pass; no new full-suite claim. The entire optional example passes against an
isolated selected-C3 copy in the existing10-second development sandbox.

All100 selected files exactly equal complete R22 C3 and are read-only;48 Python
files parse. All25 declared cases parse; public/formal closure passes. The21
whole histories load224 normalized records; ordinary safe projection preserves
201 records plus five observations,206 history indexes and30 source indexes.
The exact32,048-character question is unchanged in H projection. C has19
read-only bodies (17 support plus two public tests) and11 editable bodies, each
matching its correct problem-support/selected-source owner, with no overlap.
All private-case sentinels are absent. The context-only diagnostic H is never
dispatched or injected into research. Both48-cell R22-final and R23 input
matrices independently match their original metrics, including adverse cells.

One gpt-6.1-sol high health inference succeeds at05:05:15.305898 UTC /13:05:15
Beijing in3.077seconds, one physical call, SDK retry0; model listing passes.
No credential is printed or saved. Entry has about66GiB free and no active
formal experiment; the requested root/session are absent. All runtime/support/
scientific inputs are now frozen before dispatch. Launch audit follows below.

Launched once at05:06:25.942539 UTC /13:06:25 Beijing on October24, tmux
foreground PID1252392. Carrier is live. The initial champion's100 files exactly
equal the selected C3 snapshot; saved research input, Code limits and600-call/
two-redispatch/172800-second envelope match. Process environment confirms
gpt-6.1-sol high, H180/C300-second ceilings and single-thread numerical settings;
only explicitly named non-secret fields were inspected for reporting.

First H succeeds at05:06:34.462497 UTC /13:06:34 Beijing, attempt0, trace
`llm_traces/20261024T050634462285_hypothesis_research_turn_2d250a65.json`.
Its exact32,048-character question,206 history indexes and30 source indexes
match the independently assembled context;201 safe records and five observations
remain indexed, private-case sentinels absent. Initial read-only audit passed
the adapter object instead of its spec to the dependency-prefix helper; this
changed only the audit's expected dependency edges. Using the helper's actual
spec argument resolves the comparison exactly. No running source/input or
artifact was changed, and no corrective action was injected into H/C.

At the startup audit all nine completed H traces succeed, zero errors; status
is running first hypothesis with zero evaluated stages. Snapshot provider-call
counters can lag actual trace completion. No runtime/support/input edit, tests,
maintenance or competing solver follows launch; only read-only audit and these
lifecycle docs. Startup success is not stable gain, promotion or task closure.
At that startup handoff the11-file combined analysis/support/R24 worktree
remained uncommitted; no Git publication had been requested.

The subsequent October24 user request authorizes committing and pushing this
already frozen set. Documentation Maintenance profile and read-only Git/diff/
carrier checks match the handoff; R24 remains live, status at first Code
research/zero evaluated stages. Only lifecycle prose is changed for this Git
handoff; no runtime/support/scientific input, original artifact or process is
changed, and no tests/provider/solver are rerun. Git records the publication
result; the uncommitted-at-launch provenance above is preserved.
