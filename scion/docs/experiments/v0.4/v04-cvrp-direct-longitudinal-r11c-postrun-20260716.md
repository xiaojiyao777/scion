# CVRP Direct Longitudinal R11c Terminal Audit

## Disposition

R11c is terminal, read-only, and scientifically usable but incomplete. It is
not an infrastructure failure and it is not evidence that the validation gate
should be weakened. It completed four of eight requested formal observations,
then a fifth scheduled research attempt failed light Verification and the
current campaign loop treated the typed `research_rejected` outcome as an
invocation-wide stop.

The strongest algorithm result is H2/SWAP*: it was genuinely active and
positive on most validation families, but it caused a stable severe regression
on `tai150a` by consuming the initial-VNS interval and starving ALNS. The
candidate therefore should not be promoted unchanged. The useful research
lesson is “promising mechanism requiring targeted allocation redesign,” not
“validation was too strict.”

R11c must not be resumed, backfilled, or rewritten. Its evidence is the main
fixture for the post-R11c runtime, attribution, candidate-ancestry, and research
rejection lifecycle work.

## Identity and terminal accounting

- run root:
  `/home/clawd/research/scion-experiments/v04-cvrp-direct-longitudinal-r11c-8r-gpt56sol-8r-gpt56sol-20260716T132422Z-claw`;
- wrapper PID: `2892669`;
- started: `2026-07-16T13:24:24Z`;
- finished: `2026-07-16T15:29:03Z`;
- clean detached runtime:
  `/home/clawd/research/or-autoresearch-agent-v04-direct-runtime-56bc445d`;
- exact pushed code:
  `56bc445d07b19587ecb8e4b763ab448c4ceb9115`;
- model/runtime: `gpt-5.6-sol / direct_v3`;
- requested formal observations: `8`;
- scientific solver subprocess fallback: `30s`;
- fresh root: no resume, force surface/action/target, provider retry, semantic
  budget, output truncation, or automatic extension.

Wrapper and campaign exited zero. The authoritative terminal state is
`valid_but_incomplete`, `completed_requested_rounds=false`, and
`last_stop=execution_research_rejected`. The campaign scheduled five attempts:

| Round | Attempt | Formal stage | Outcome |
|---:|---|---|---|
| 1 | H1 route elimination | screening | evaluated |
| 2 | exact H1/C1 reuse | expanded screening | evaluated |
| 3 | H2 SWAP* on cumulative branch | screening | evaluated |
| 4 | exact H2 candidate reuse | validation | evaluated / abandon |
| 5 | H3 joint operator weights | pre-Protocol Verification | research rejected |

Formal accounting is screening `3`, validation `1`, frozen `0`; outcomes are
evaluated `4` and research-rejected `1`. Rounds 6–8 were never scheduled.
Champion remains v1 and no promotion occurred.

All 144 formal candidate/champion pairs were valid, with zero solver failure,
`solution_valid=true`, and zero fleet violation. The run contains three H calls
and three C calls, each exactly once and successful at the provider/transport
layer. There was no provider retry or response truncation.

## Postrun and readiness

Postrun rebuild, reports, and strict readiness all exited zero. The direct-v3
readiness artifact has 31 required checks with no failures and reports
`current_run_analysis_ready=true` and `delegation_ready=true`. These fields mean
that the retained evidence can be audited; they do not mean that eight
observations completed or that any candidate is accepted.

The terminal audit found three projection defects that readiness does not yet
detect:

1. the analysis brief reports Protocol accounting, measurement effect, and
   research continuity as unavailable/zero and phase 4 reports source
   visibility/prompt density unavailable, despite four metrics, three formal
   artifacts, six traces, campaign state, and trajectory source evidence;
2. `campaign/status.json.last_execution_outcome` remains the older evaluated
   result while `last_result` and `campaign_summary.json` correctly identify
   round 5 as research rejected;
3. event-level H2 replay identity combines the incremental proposal patch
   digest with the cumulative code hash and declares itself complete without a
   formal-candidate reference.

Postrun “handoff exists” readiness therefore passes, but semantic projection
completeness is not yet covered.

## Context volume and sibling isolation

Provider-visible H context grew without any budget or truncation:

| Hypothesis | Visible characters | Input tokens |
|---|---:|---:|
| H1 | 90,896 | 20,593 |
| H2 | 214,078 | 46,971 |
| H3 | 261,889 | 57,066 |

C prompts remained about 99–102k characters / 23–24k input tokens. The H
growth comes primarily from repeating complete screening pair/case trees for
each observation. It is a schema/ownership problem, not a reason to add top-k,
summaries, token budgets, or truncation.

After H2 validation abandoned the old branch, H3 used new clean branch
`cf8935b5-...` from champion hash `06820e...`. It had no inherited H1/H2 code
and no current branch overlay before evaluation. Its sibling history contained
exactly the three old-branch screening observations. Recursive inspection found
no validation/frozen result, terminal state, raw ref, patch body, failure prose,
or current-code projection. The safe sibling boundary therefore passed.

## H1: inactive route elimination

H1 combined route elimination with `regret3_existing`. Initial screening was
32/32 valid:

- case `4W/2L/2T`;
- pair `15W/10L/7T`;
- median delta `+0.25`, CI `[-5.75, 3.25]`;
- Decision: expand screening.

Expanded screening was 48/48 valid:

- case `3W/3L/6T`;
- pair `19W/22L/7T`;
- median `0`, CI `[-3.25, 4.25]`;
- gate fail / Decision `continue_explore`.

The intended mechanism never produced a candidate. Route elimination paired
with `regret3_existing` was selected 511 times in initial screening and 530
times in expansion; every selection ended `destroy_empty`, with zero repair
invocation, acceptance, or best update. In the inherited H2 candidate it added
another 320 empty selections in screening and 179 in validation, for 1,540 dead
selections across the campaign.

This is structurally predictable. Seven of the eight initial cases have total
demand above `(k-1) * capacity`, so reducing the route count from `k` to `k-1`
is impossible by the capacity lower bound. Only `M-n200` was theoretically
eligible, and it still produced no removal. The proposal context did not expose
total demand, capacity, minimum-route slack, or even a useful size bucket.

H1 did not test successful route elimination. Its observed differences mainly
reflect scheduler/RNG/search-allocation changes from adding a dead operator
pair. Calling the 511 selected names “repair attempts” would be false; repair
invocation was zero.

## H2: active SWAP* with a real starvation failure

H2 added SWAP* under `local_search.py`. It was strongly active:

- screening: 4,280 attempts, 3,061 accepted, delta sum 16,432;
- validation: 3,459 attempts, 2,695 accepted, delta sum 29,586.

Screening was 32/32 valid with case `5W/3L`, pair `20W/12L`, median `+4.25`,
and CI `[-10, 12.25]`; Decision queued validation.

Validation was 32/32 valid:

- Protocol case classification `5W/1L/2T`, win rate `0.625` below the
  preregistered `0.66` threshold;
- pair `22W/7L/3T`, median `+7`, CI `[0, 241]`;
- Decision: `VALIDATION_FAIL_WIN_RATE / abandon`.

Case medians were A `+2.5` (2W/2L, Protocol tie), P `+20`, tai75 `0` (tie),
tai150a `-56`, tai150b `+6`, X120 `+283.5`, X129 `+8`, and X190 `+241`.
The only losing family, tai150a, was not noise: all four seed deltas were
negative (`-22`, `-210`, `-90`, `-21`). Candidate initial VNS consumed about
46.3–46.4 seconds on each pair and left zero ALNS iterations; champion initial
VNS used about 25–29 seconds and still completed one to three ALNS iterations.
SWAP* therefore created a stable large-case starvation mode.

The candidate is also scientifically cumulative. Its formal artifact correctly
lists inherited H1 files `destroy_repair.py` and `scheduler.py`, the H2 proposal
file `local_search.py`, and `incremental_effect_isolated=false`. H2 tested
H1+SWAP*, not SWAP* alone. The artifact is honest and materializable; the branch
continuation policy is the defect.

## Search allocation

VNS dominated every candidate cohort while the next agent received only ALNS
repair diagnostics:

| Cohort | Candidate ALNS share | Candidate VNS share | Candidate ALNS throughput |
|---|---:|---:|---:|
| H1 screening | 17.17% | 82.61% | 2.739 iterations/s |
| H1 expansion | 15.28% | 84.56% | 1.796 iterations/s |
| H2 screening | 8.72% | 91.05% | 1.546 iterations/s |
| H2 validation | 4.70% | 95.05% | 0.693 iterations/s |

H2 validation splits VNS into 37.29% initial and 57.76% embedded. Every
candidate pair hit the runtime budget. The raw runtime already contains phase
time, move attempts/acceptance/delta, ALNS trace, and SWAP* activity; none of
the phase/VNS/SWAP/allocation evidence was visible to H3.

This supports a problem-owned, proposal-only SearchAllocationEvidence packet
and a current pure-ALNS control. It does not support deleting VNS or changing a
gate before the matched evidence exists.

## H3 rejection and premature campaign stop

H3 reasonably proposed replacing independent destroy/repair marginals with 12
joint pair weights. C used the complete current champion scheduler and changed
pair creation, selection, scoring, and one update path, but left six later
references to the removed `destroy_weights`/`repair_weights` variables. Syntax
passed; `V1b_undefined_names` correctly rejected the incomplete closure before
Protocol. The failed scheduler is retained only in the round-5 archive and the
branch workspace rolled back to the clean champion.

The gate did its job. The orchestration defect is that a structured,
successfully finalized `research_rejected` attempt terminates the entire
campaign. One rejected H/C must not be retried or silently patched, but it also
must not reduce the requested formal observation count. The next attempt should
use a new attempt ID and new H ID on the exact clean base; provider format,
infra, resource, interrupt, replay-conflict, or scheduler-nonprogress outcomes
remain fail-closed stops.

## Expansion transaction and replay

The R11b prospective-count repair passed R11c:

- all four Decision completion intents committed;
- H1 source stayed explore/count 0 through the expanded Protocol;
- the completed expanded Decision atomically committed explore/count 1;
- no source-owner mismatch, duplicate execution outcome, or recovery anomaly
  occurred;
- the next H reset its new creative attempt count as designed.

All three formal artifacts contain complete base/problem/split/seed/code
identity, and validation correctly reused screening verification only after a
current-hash match. The event projection remains wrong for H2: the artifact
separates cumulative `formal_patch_digest=45010b...` from incremental
`proposal_patch_digest=8895c0...`, while screening/validation events place the
incremental digest beside cumulative code hash `09a39f...` and declare replay
complete. Events need both digests plus a formal-candidate reference; complete
must mean reconstructible from the declared base.

## Runner interchange leakage baseline

At the terminal audit snapshot, `/tmp` contained 252
`scion_run_*.json` files totaling 419,331,485 bytes, all with modification times
after the R11c launch. These are parsed solver interchange files, not formal
metrics. They support the accepted runner-owned lifetime fix; they were not
deleted during the terminal audit. After the ownership repair passed focused
and full-suite verification, a separate cleanup confirmed zero live file
owners and removed all 252 files; the residual count is zero. No R11c formal
metric or durable V8 artifact was removed.

## Accepted work order

1. keep R11c terminal/read-only and use it as the regression fixture;
2. implement runner-owned solver interchange cleanup with self-contained
   `SolverOutput` and no `RunResult.output_path`;
3. add problem-owned, gate-excluded SearchAllocationEvidence, including phase,
   operator lifecycle, joint destroy-repair pairs, and capacity/min-route
   feasibility features;
4. make finalized pre-Protocol research rejection an attempt-terminal but
   scheduler-forward typed outcome, with no same-H/C retry and crash-safe
   completion ownership;
5. implement clean/provisional candidate disposition so rejected code never
   contaminates a mechanism pivot;
6. fix replay event identity, normalized reversible screening/rejection ledger,
   status finalization, and postrun projection completeness;
7. run the current four-profile no-LLM characterization, then order-balanced
   canonical/pure-ALNS direct-v3 campaigns and canonical transplant replay;
8. retain the validation gate and record H2 as promising but non-promotable
   until a targeted redesign survives the failing family.

No step adds an LLM retry, semantic budget, rejection cap, top-k, compression,
truncation, forced research target, or Decision/gate dependency on the new
proposal evidence.
