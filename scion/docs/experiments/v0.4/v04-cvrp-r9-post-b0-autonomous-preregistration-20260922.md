# CVRP R9: autonomous complete-source research after R8 nonconfirmation

State: completed normally at `2026-09-23T04:02:58.157595+00:00` after the
requested 12 screening stages / eight distinct H/C candidates. All 144 formal
pairs were valid; no promotion or held-out stage. See the
[postrun](v04-cvrp-r9-post-b0-autonomous-postrun-20260923.md) for the expanded
negative/uncertain results, source fidelity and unresolved budget consumption.
R9 is terminal and must not resume. Launched once at
`2026-09-22T23:22:20.486583+00:00`, tmux
`scion-r9-post-b0-autonomous-20260922`, driver PID 126943, under the user's
analysis/optimization request. The [R8 postrun](v04-cvrp-r8-r7-final-b0-postrun-20260922.md)
closes the negative fixed B0 comparison. R9 is a new autonomous campaign, not
an R8 rerun or resumption of terminal R7/R8 state. The design below is frozen.

At the initial live check, version 1 / weight revision 0 and zero evaluated
rounds were recorded. All 100 ordinary files in `champions/champion_v1` match
the selected R8 source. The first two real `gpt-5.6-sol` H calls succeeded
(`read_source`, then `read_history`); their actual contexts contain the current
R8 nonconfirmation question and all four prior observations / 78 scientific
history records in the existing index. This is startup evidence, not a formal
result, proof of comprehensive history attention or an improvement claim.

## Source and question

Start from the ordinary complete
[R8 candidate snapshot](/home/clawd/research/scion-experiments/v04-cvrp-r8-r7-final-b0-20260922/input_snapshots/candidate):
100 ordinary files, directly equal to R7 step 13's evaluated branch-C tree.
Keep its executable bundle and unused helpers intact; no host-authored solver
patch precedes launch. The fresh CLI copies the source into its initial champion
snapshot, with version 1, weight revision 0, fresh branches and provider counts.
This source is a research baseline, not a confirmed improvement over B0.

Question: can autonomous H/C improve that complete algorithm under the declared
solver limits while preserving feasibility and fleet protection? The ordinary
current question explicitly states R8's 24 valid pairs, case W/L/T 1/1/4,
median 0, CI [-159.5,71.75] and `NOT_CONFIRMED`. H remains free to select a
mechanism and C its implementation. No target, schedule, patch, action, mandatory
history read, novelty requirement or activity gate is prescribed.

## Evidence available to H

The [research input](inputs/v04-cvrp-r9-post-b0-autonomous-research-input.json)
preserves all three R4/R5/R6 observations byte-for-value and appends R8 as a
distinct fourth observation. R8 includes all six case medians and seed sign
patterns, verified counterbalancing, zero-ALNS/initial-search facts for both
large cases and the few ALNS iterations/embedded-search runtime on X-n190-k8.
These are problem-owned observations, not component-causal conclusions.
No filenames, source targets, held-out outcomes or synthetic H/C enter them.

Load the existing R3, R3b, R3c, R3d, R3e, R3f, R3g, R3h, R3i and R7 JSONL files
in that order, using the exact paths in the invocation below. Together they
contain 101 records / 3,463,467 bytes; the unchanged projection exposes 78
scientific records and excludes 23 operational rows. R7 includes its Contract
rejection and full screening history, not just its final positive initial
screen. R8 has no H/C ledger; its fixed comparison is conveyed through the
ordinary observation instead of fabricating a history step.

History is lossless and ordered within the existing input/projection semantics,
not ranked, clipped or selected by outcome. It is H-only and restores no campaign
state. The current research question remains directly visible in H context;
detailed prior records are available through the existing bounded read actions.
Availability does not guarantee attention, and no new attention gate is added.

## Prospective science

- [Protocol](inputs/v04-cvrp-r9-post-b0-autonomous-protocol.yaml).
- [Split](inputs/v04-cvrp-r7-autonomous-source-continuation-split.yaml), reused
  unchanged: six known adaptive screening cases, six still-unexecuted validation
  cases and twelve still-unexecuted frozen cases.
- [Seeds](inputs/v04-cvrp-r9-post-b0-autonomous-seeds.yaml): first nine primes
  above 80,000. Screening 80021/80039/80051/80071; validation 80077/80107;
  frozen 80111/80141; familiar safety-only canary 80147.

The seeds are distinct from the R3–R8 declared ledgers. Reusing screening cases
is explicitly adaptive development, not new-case independent evidence. R8
never opened validation/frozen; the separate pre-R3 retained block is outside
R9 and remains unopened. No later-stage outcome reaches H/C.

All R7/R8 scientific gates, complete-pair requirements, protected fleet objective,
case-median effects and dimension-only 30/45/60/90/120-second limits are unchanged.
Canary is 10 seconds. Autonomous screening starts at 3 cases x 2 seeds, then
requires 6 x 4 expanded screening, 6 x 2 validation and 12 x 2 frozen evidence
with exact candidate reuse before promotion. Screening practical delta is 2.0,
validation 1.0, CI lower bound nonnegative, net case score >= 0.25 and case loss
rate <= 0.20. Preserve initial-quality expansion and `SCREENING_FAIL_CASE_QUALITY`.

R9 uses the existing autonomous Protocol's champion-first order, not R8's
explicit fixed-driver AB/BA schedule. Its paired development evidence is
limited accordingly. No framework measurement implementation is changed in
this slice. A local promotion compares with the selected starting source or a
later local champion, not original B0; retained superiority still requires a
separate prospective exact-candidate B0 comparison. Do not pool contrasts.

Target: 12 formally evaluated stages, not 12 provider calls or guaranteed
promotions. K=1, the existing maximum-three-branch scheduler, complete verified
provisional branch heads, rollback on Contract/Verification failure and exact
held-out reuse remain unchanged. Parameter search stays explicitly disabled.

## Runtime and resource bounds

Main checkout `v0.4-dev`, preparation HEAD `39b03166`; runtime implementation
unchanged from `e405bfd2`. This slice changes only analysis/status documents,
three prospective inputs and one focused test. Record any uncommitted diff
honestly; freeze runtime, source, data and scientific inputs before launch.
Do not make Git clean state a scientific gate or mutate files during measurement.

Provider: `gpt-5.6-sol`, reasoning high, through the existing local proxy.
H/default timeout 180 seconds, C turn/finalization 300 seconds, SDK retries zero.
The existing R3i code-research limits allow 12 turns, 8 reads, 8 searches and
4 tests, with no total transcript-character ceiling. Invocation envelope:
600 physical dispatches, at most two charged redispatches per typed transient
frozen request, outer guard 172,800 seconds. These are declared resource bounds,
not new algorithm-quality or global campaign-lifetime rules.

Use the unchanged R6 read-only data root named in the split. Before launch:
validate new inputs and ordered H-only projection, source/fresh-output selection,
all 24 formal case paths and ordinary CLI expansion settings. Run focused
continuation/history/CLI/fixed-funnel/input tests without a live campaign. No
core, adapter, gate or runtime change requires another full suite or Warehouse
control. The previous 2397-pass P1b suite remains implementation evidence.

Prelaunch validation: 138 focused continuation, source-CLI, research-input,
history/redteam, fixed-funnel and R7/R8/R9 input tests passed in 2.25 seconds.
Targeted Ruff F/E9 and `git diff --check` passed. Read-only preparation parsed
all 24 formal cases plus canary, validated fresh output/source selection,
disabled parameter search, expansion configuration, limits and all four
problem-owned observation projections. It loaded 101 raw / 78 H-visible history
records without a solver/provider call or output creation. A catalog check
found `gpt-5.6-sol`; actual generation remains to be observed after launch.

Check the provider catalog without printing credentials; catalog presence is
not evidence of successful generation. Verify no solver, cleanup or tests are
active and that both fresh output and tmux session are absent. Start once, then
freeze inputs and avoid overlapping tests, maintenance or another solver.

Output:
`/home/clawd/research/scion-experiments/v04-cvrp-r9-post-b0-autonomous-20260922`.
tmux: `scion-r9-post-b0-autonomous-20260922`. Terminal campaigns are never
resumed or restarted. Preserve all R7/R8 raw evidence unchanged.

## Frozen invocation

Run once from the main checkout after the preceding checks. The credential is
retrieved at runtime and is never printed or written into experiment artifacts.

```bash
set -Eeuo pipefail
cd /home/clawd/research/or-autoresearch-agent
test ! -e /home/clawd/research/scion-experiments/v04-cvrp-r9-post-b0-autonomous-20260922
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
    --source-tree /home/clawd/research/scion-experiments/v04-cvrp-r8-r7-final-b0-20260922/input_snapshots/candidate \
    --research-input /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r9-post-b0-autonomous-research-input.json \
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
    --code-research-limits /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r3i-long-run-code-research-limits.json \
    --protocol /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r9-post-b0-autonomous-protocol.yaml \
    --split /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r7-autonomous-source-continuation-split.yaml \
    --seeds /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r9-post-b0-autonomous-seeds.yaml \
    --time-limit-sec 30 --rounds 12 --provider-call-cap 600 \
    --provider-transient-retries 2 --outer-hardwall-sec 172800 \
    --campaign-dir /home/clawd/research/scion-experiments/v04-cvrp-r9-post-b0-autonomous-20260922
```

After launch, inspect ordinary status/summary and the exact H/C/metric references.
Verify the first actual H context contains the current R8 question and the full
four-observation/78-record index. Do not require particular read actions or
infer improvement from a successful provider call. Analyze the final actual
H/C, complete sources, paired outcomes and terminal Decision before selecting
another rung. Do not open the original SQLite database.
