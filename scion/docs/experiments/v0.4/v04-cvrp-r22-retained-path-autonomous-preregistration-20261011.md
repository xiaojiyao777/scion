# CVRP R22: completed real-path improvement retained at solver return

State: **running; startup audited October11**. October11 user explicitly requests committing
the prior work first, then the next round focused on whether improvement survives
a completed real path into the final returned solution. Prior R21 analysis and
optional observer repair were committed as **693cd4a0**, not yet pushed at launch. R21 is terminal
and never resumed. This is fresh autonomous H/C research, not independent
confirmation of a selected R21 branch.

## Source, intervention and falsifiable question

Use the complete100-file source at
`/home/clawd/research/scion-experiments/v04-cvrp-r21-source-grounded-autonomous-20261009/champions/champion_v1`.
It is byte-equal to R21's starting R20 candidate/R19 A3; no R21 branch is selected,
merged or promoted. All twenty whole chronological history files are supplied,
adding every R21 screening record to the nineteen R21 input histories. Preserve
the five prior observations and the entire R21 question under explicit historical
delimiters. The new current frame overrides historical present-tense source and
sampling descriptions. No ranked subset, truncation, state restore or private
later-stage evidence is introduced.

Question: can autonomous research produce more reliable final-quality gains
while distinguishing real-path entry, completion, feasible accepted change and
benefit retained in the returned solution? The [R21 postrun](v04-cvrp-r21-source-grounded-autonomous-postrun-20261011.md)
records valid but unstable incremental effects, not a discovered general retention
bug. Do not presuppose that the solver loses improvements or that any particular
mechanism is the answer.

Two bounded interventions only:

1. Problem-owned research input emphasizes independent feasibility/objective
   checks at the changed transition and actual solver return, with honest
   reporting when completion/retention is not observed. All public R21 records,
   including losses, remain available whole. No source target, required
   neighborhood, mandatory test, phase schedule or new gate is prescribed.
2. An optional public example observes the real VNS boundary without changing
   its operators/guards, snapshots a live return before diagnostic overhead,
   records strict independently rescored feasible improvements, and checks that
   the final returned objective is no worse than the best observed improvement.
   It runs two public seeds on a synthetic40-customer matrix. This is a bounded
   no-loss demonstration, not production-size coverage or comparative benefit.
   Real live return does not imply exhaustive neighborhood closure. It does not
   attribute improvement to a particular inner kernel; the agent must choose
   suitable observations for its own claim. A later better solution may replace
   the earlier routes. A locally improving trial worse than the existing best
   may correctly be rejected.

The new example is inside the already optional public string, not another
collected candidate check. Mutation tests challenge counter-only claimed gains,
expired returns and a feasible final return that discards the observed gain.
The two existing collected public checks, solver, core, adapter, generic prompts,
Contract, Verification, Protocol and Decision implementations are unchanged.
No new Warehouse control is required for this problem-only test/input change.

## Scientific design and resources

[Research input](inputs/v04-cvrp-r22-retained-path-autonomous-research-input.json),
[Protocol](inputs/v04-cvrp-r22-retained-path-autonomous-protocol.yaml),
[seeds](inputs/v04-cvrp-r22-retained-path-autonomous-seeds.yaml).

Protocol is exactly R21 except version and canary seed. Initial5 cases×4 seeds,
required expanded6×8, conditional validation6×4 and frozen12×4. Same R7 split,
case populations, practical margins, case-level bootstrap/score/loss gates,
feasibility, fleet protection and equal dimension-band limits60/90/120/180/240s;
canary10s. Algorithm-local time fractions/reserves are unchanged.

Prospective seeds: first17 primes above280000, disjoint from prior checked-in
ledgers, chosen before outcomes:

| Stage | Seeds |
|---|---|
|Screening|280001,280009,280013,280031,280037,280061,280069,280097|
|Validation|280099,280103,280121,280129|
|Frozen|280139,280183,280187,280199|
|Canary|280207|

gpt-6.1-sol high; K=1/max three branches,12 evaluated stages,600 physical calls,
two charged typed redispatches, SDK retry0 and172800-second48-hour guard.
H180/C300-second transport ceilings; unchanged12-turn/8-read/8-search/4-test
Code limits, transcript characters unbounded, parameter search off. No silent
resource widening, terminal resumption or post-outcome sample extension.

Ordinary champion-first pairs are not counterbalanced. Known screening and
already-exposed validation are adaptive development, not globally unseen
confirmation. Frozen remains conditional. R22 compares cumulative candidates
with the local R19 A3 baseline (or an actual later champion), not original B0 or
B0-fixed. Do not pool different stages/candidates/comparators or infer isolated
causality from a cumulative bundle, more search or telemetry associations.

## Prospective acceptance and analysis

Separate three questions in the terminal report:

- **Research-path evidence:** does actual C faithfully implement H on its current
  complete source? Do self-authored probes observe the proposed path through its
  ordinary entry and real collaborators? Was computation completed before expiry,
  a feasible objective change independently checked, and a no-worse final return
  observed? Record absent coverage as absent; test names/counters are insufficient.
- **Complete-solver quality:** evaluate the complete declared case/seed matrix,
  losses, uncertainty and fixed-budget final objective using unchanged Protocol
  and Decision. A successful synthetic retention probe cannot promote a candidate
  or establish improved comparative quality.
- **Independent retention:** remains a separate later frozen-source/comparator
  experiment with prospective fresh seeds/order. This run cannot establish
  retained original-B0 superiority.

Optional observations never become hard gates, Safe Features or scheduling
preferences. Preserve all negative/uncertain results, provider failures and
incomplete stages. No host-selected algorithm fix is part of this experiment.

## Verification and execution boundary

Use Code Repair Or Feature Work reading profile for the public example/tests,
plus the operations runbook and exact R21 postrun/preregistration. Checkout
began at3cf85afe with the preceding seven-file set; it was committed first as
693cd4a0. R22 example/input/test/docs edits were separate uncommitted work at launch.
Production implementation remains6380a59e; record actual worktree provenance,
not an invented clean-launch claim.

Before launch: focused support/input/boundary tests, full optional example on an
isolated selected-source copy, whole100-file equality/48 Python parses, all25
declared cases and public/formal closure, twenty whole histories, exact provider
H question/observations/index and C public-example/source separation. No private
later-stage facts or operational quota errors enter H/C research input. Confirm
fresh root/session, disk, no concurrent experiment/test/solver, and one bounded
successful model health inference without exposing credentials.

Freeze all runtime, problem support and scientific inputs before dispatch. No
tests, maintenance or competing solvers during measurement; lifecycle docs only.
Verify startup source, saved inputs/resources, exact first H context and provider
success without injecting a forced read or changing the run.

Output:
`/home/clawd/research/scion-experiments/v04-cvrp-r22-retained-path-autonomous-20261011`.
Tmux: `scion-r22-retained-path-autonomous-20261011`.
Do not launch until all checks below pass; after launch the command is historical.

## Direct invocation used once

```bash
set -Eeuo pipefail
cd /home/clawd/research/or-autoresearch-agent
test ! -e /home/clawd/research/scion-experiments/v04-cvrp-r22-retained-path-autonomous-20261011
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
    --source-tree /home/clawd/research/scion-experiments/v04-cvrp-r21-source-grounded-autonomous-20261009/champions/champion_v1 \
    --research-input /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r22-retained-path-autonomous-research-input.json \
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
    --code-research-limits /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r3i-long-run-code-research-limits.json \
    --protocol /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r22-retained-path-autonomous-protocol.yaml \
    --split /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r7-autonomous-source-continuation-split.yaml \
    --seeds /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r22-retained-path-autonomous-seeds.yaml \
    --time-limit-sec 60 --rounds 12 --provider-call-cap 600 \
    --provider-transient-retries 2 --outer-hardwall-sec 172800 \
    --campaign-dir /home/clawd/research/scion-experiments/v04-cvrp-r22-retained-path-autonomous-20261011
```

## Verification and actual execution

Prelaunch verification completed October11. Focused support/diagnostic/dependency/
provider/Contract/public-solver regressions:122 passed in39.73seconds. R16/R19/
R20/R21/R22 input and research-input regressions:47 passed in1.46seconds. These
169 tests are focused coverage, not a new full-suite run. Targeted Ruff F/E9,
diff check and CLI help pass. The full optional public example passes in the
ordinary10-second isolated sandbox on both repository and selected R21 starting
source; the new retention example also passes alone on that selected source.
The expired-return mutation was corrected to expire the real nested context;
an input-test Path conversion and diagnostic result-field assertion were also
corrected. These were test/audit harness assumptions, not production defects.

Read-only checks verify byte equality of all100 selected-source files to the
R20 candidate,48 Python parses, all25 declared cases loaded, disjoint splits and
public/formal closure. Twenty whole histories contain212 normalized records;
the ordinary safe projection exposes189 plus five unchanged observations,
194 history index entries and30 source entries. Exact24,389-character current
question matches. No private-case sentinels appear. C exposes19 read-only bodies
(17 support plus two public tests), including the new optional example, and11
editable entries with no overlap. The artificial context-only diagnostic H was
never dispatched or supplied to research.

R21 status is terminal valid12/12 and its carrier is dead. Fresh root/session
are absent, no concurrent campaign/test/solver remains, and57.08GiB are free.
One gpt-6.1-sol high health inference succeeds at02:19:42.774931 UTC /10:19:42
Beijing in3.890seconds, one physical call with SDK retry0. No credential was
printed or saved. Runtime/support/scientific inputs were frozen before launch.

Launched once at02:20:35 UTC /10:20:35 Beijing on October11, tmux foreground
PID756593. Actual startup audit passes:100 initial champion files exactly match
the selected source; saved research input, Code limits and600-call/two-redispatch/
172800-second envelope match. First H succeeds at02:20:43.106147 UTC, attempt0,
gpt-6.1-sol with180-second request ceiling; trace
`llm_traces/20261011T022043106050_hypothesis_research_turn_2f4ba302.json`.
Its exact24,389-character question,194 history indexes and30 source indexes
match the independently assembled context (JSON-normalized tuples only).
All five observations and189 safe historical records remain indexed; private
case sentinels are absent. At startup audit three completed H traces succeed
with no errors, while status remains running first hypothesis/zero evaluated
stages. The status call counter is an earlier snapshot, not evidence of zero
physical calls. Carrier remains live. No runtime/support/input edit, tests,
maintenance or competing solver follows launch; lifecycle docs only. Startup
success is not evidence of retained gains, stable quality or promotion.

The subsequent October11 user request authorizes committing and pushing this
already frozen R22 set together with693cd4a0. The Git handoff uses Documentation
Maintenance and read-only diff/carrier checks; only lifecycle prose changes.
No runtime/support/scientific input, original artifact or running process is
changed, and no tests or experiments are rerun. Git records the resulting tip;
the uncommitted-at-launch provenance above remains historical fact.
