# CVRP R14: autonomous research after the common-repair R13 screen

Terminal update: completed normally at `2026-09-27T08:44:52.323359+00:00`,
12 screening stages / ten evaluated candidates, 108 valid pairs, no promotion
or later stage. One Code attempt abandoned after opaque preflight rejections;
120/600 provider calls, all successful. See the [postrun](v04-cvrp-r14-post-r13-autonomous-postrun-20260927.md).
The launch record below is historical. R14 must not resume.

State: launched once at `2026-09-27T02:19:53Z`, driver PID 267274, tmux
`scion-r14-post-r13-autonomous-20260927`. The September 27 user request authorizes
checking the completed experiment, analysis/optimization and a fresh launch.
[R13 postrun](v04-cvrp-r13-constructor-fixed-b0-postrun-20260927.md) is terminal
NOT_CONFIRMED; it must not resume. No commit/push is requested this turn.

Startup: version 1 / weight revision 0, zero evaluated stages; all 100 initial
champion files exactly equal the selected candidate. The first actual H call
succeeded on gpt-5.6-sol (attempt index zero), with the exact question and
five-observation / 112-history indexes. This proves startup/input availability,
not complete evidence attention or algorithm improvement. Runtime/source/data/
scientific inputs are frozen; only launch-status documentation changes.

## Complete source and falsifiable question

Use R13's exact complete candidate snapshot:
`/home/clawd/research/scion-experiments/v04-cvrp-r13-constructor-fixed-b0-20260926/input_snapshots/candidate`.
It is the 100-file R12-A-fixed tree: autonomous R12 A plus the previously
authorized independent constructor repair. No new host performance patch,
sibling merge, removal of code, or patch-chain reconstruction is made.
Operator-assisted repair is acknowledged; it is not an H/C discovery.
Fresh local champion version 1 does not confer promotion or B0 superiority.

R13's six-case expanded result versus B0-fixed is W/L/T 4/1/1, median +91.5,
CI [-36,296.75], uncertain, with 24 valid pairs. Three cases win all four seeds,
one has small gains and X-n190 is unstable/negative. Two large cases still
have zero candidate ALNS; X-n190 spends 57.786–64.337 seconds in embedded VNS
and completes only 2–4 iterations. These whole-bundle facts suggest further
source-grounded quality/stability research; they do not identify a causal fix.

Question: can H/C improve the complete repaired algorithm under the same
budgets, preserving feasibility/fleet protection? The host provides observations,
not a required mechanism, target, phase schedule, read action or activity gate.
Local outcomes compare with R12-A-fixed or a later local champion, not B0-fixed
or unchanged original B0. Do not pool their effect estimates.

## Safe input and ordinary history

The [research input](inputs/v04-cvrp-r14-post-r13-autonomous-research-input.json)
preserves R4/R5/R6/R8 observations unchanged, then adds a fifth R13 observation
with the uncertain Decision, all case medians/sign patterns and no later-stage
facts. The question contains every R13 seed effect, phase counts/ranges and
source-grounded first-trial/100-iteration-update/inactive-threshold facts.
R12 A's screening pass and B/C adverse or uncertain screens remain distinct.

Append all ten ordinary R12 history rows to R12's twelve ordered history inputs:
R3–R3i, R7, R9, R11, R12. Thirteen files contain 135 raw records / 5,203,408
bytes. The unchanged projection exposes 112 scientific/Contract records to H,
excluding the same 23 operational rows. This includes all R12 screens and its
primary-target rejection, without success selection, history compression,
clipping or restoration of branch/provider state. H controls what it reads.

No private validation case, failure, failed seed, result or constructor-specific
regression recipe enters H/C context. The complete repaired source is visible,
with its engineering origin explicitly acknowledged; operator postruns and
engineering diagnostic artifacts are not proposal inputs.

## Prospective science

[Protocol](inputs/v04-cvrp-r14-post-r13-autonomous-protocol.yaml) retains every
R12/R13 scientific field except version and fresh canary seed. Equal formal
dimension limits remain 60/90/120/180/240 seconds, canary 10; algorithm 0.80
fraction and reserve unchanged. Preserve complete pairs, runtime audit,
feasibility/fleet, practical effect, case quality, CI and deterministic Decision.
No host ranking, novelty or telemetry gate.

Use the unchanged [R7 split](inputs/v04-cvrp-r7-autonomous-source-continuation-split.yaml):
initial screening 3 cases × 2 seeds; expanded 6 × 4 required before a pass;
validation 6 × 2 and frozen 12 × 2 conditionally reuse the exact candidate.
Validation was exposed in R10/R12 and used for engineering diagnosis, so it is
a development/completeness gate, not independent confirmation. R13 did not
reopen it. Frozen and the separate pre-R3 retained block remain unopened.
R14 does not execute the independent retained block. New seeds do not make
known cases unseen, and successful constructor diagnostics do not guarantee
formal validation completeness or good effects.

First nine primes above 130,000, selected before execution:
[seed ledger](inputs/v04-cvrp-r14-post-r13-autonomous-seeds.yaml).

| Stage | Seeds |
|---|---|
| screening | 130003,130021,130027,130043 |
| validation | 130051,130057 |
| frozen | 130069,130073 |
| safety canary | 130079 |

All nine are disjoint from previous checked-in ledgers. Existing autonomous
champion-first arm order is unchanged, not counterbalanced; disclose that
limitation and require an independent counterbalanced confirmation for any
later original/comparator claim. No retrospective sample extension or case drop.

## Resources and prelaunch verification

Checkout `v0.4-dev`, HEAD `964a9622`, with this new docs/input/test-only work
uncommitted. No algorithm, generic runtime, adapter, Protocol implementation or
control-boundary change; no new shared-core full suite or Warehouse run required.

Fresh K=1, existing maximum-three-branch scheduler, 12 formal evaluated stages,
verified provisional source continuation/rollback and exact held-out reuse.
Model `gpt-5.6-sol`, reasoning high; H/default timeout 180 s, C 300 s;
SDK retries zero, up to two charged typed-transient redispatches, 600 physical
provider calls and outer guard 172,800 s (48 hours). Existing R3i C limits:
12 turns, eight reads, eight searches, four tests, no transcript-character cap.
Parameter search remains disabled. These explicit resource guards are not
algorithm-quality gates and no previous cap exhaustion is alleged.

Before launch: focused source-continuation/history/redteam/session/fixed-funnel/
input tests; exact source and ordinary safe history projection; all 25 data
inputs; CLI/resource/session/expansion configuration; targeted Ruff and diff
checks. Provider catalog/credential check must not print secrets. Verify no
competing solver/test/cleanup, sufficient disk and fresh output/tmux, then
freeze source/runtime/data/scientific inputs and launch exactly once.

Prelaunch evidence: 225 focused tests passed in 3.07 seconds (source
continuation, CLI source selection, ordinary/safe history, research input,
context/code redteams, C sessions, fixed funnel and R7–R14 inputs).
Read-only preparation parsed all 25 cases and all Python source in the complete
100-file input, validated source/fresh output, parameter-search disablement,
expansion/resource/session limits and exact H projection: 135 raw / 112 visible
records, five observations and the unchanged current question. No solver,
provider dispatch or output directory was created by preparation. Ruff F/E9,
formatting, CLI help and diff checks pass. Older panes are dead; no competing
solver/test/cleanup was found and 62 GiB is available. The final credential/model
catalog check passed without secret output; output/session were absent before
the single launch. No tests or solvers were run alongside formal measurement.

Output: `/home/clawd/research/scion-experiments/v04-cvrp-r14-post-r13-autonomous-20260927`.
Tmux: `scion-r14-post-r13-autonomous-20260927`.

## Frozen invocation (executed once after checks)

```bash
set -Eeuo pipefail
cd /home/clawd/research/or-autoresearch-agent
test ! -e /home/clawd/research/scion-experiments/v04-cvrp-r14-post-r13-autonomous-20260927
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
    --research-input /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r14-post-r13-autonomous-research-input.json \
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
    --code-research-limits /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r3i-long-run-code-research-limits.json \
    --protocol /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r14-post-r13-autonomous-protocol.yaml \
    --split /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r7-autonomous-source-continuation-split.yaml \
    --seeds /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r14-post-r13-autonomous-seeds.yaml \
    --time-limit-sec 60 --rounds 12 --provider-call-cap 600 \
    --provider-transient-retries 2 --outer-hardwall-sec 172800 \
    --campaign-dir /home/clawd/research/scion-experiments/v04-cvrp-r14-post-r13-autonomous-20260927
```

After launch verify the complete initial snapshot, actual H's exact question,
five-observation / 112-history indexes and at least one real successful call.
Do not force a read or treat provider success as algorithm evidence.
Only launch-status documentation may change during formal measurement.
After terminal completion analyze H/C, complete source fidelity and paired
evidence. Preserve any negative/incomplete result and never resume the terminal
campaign or open its original SQLite database.
