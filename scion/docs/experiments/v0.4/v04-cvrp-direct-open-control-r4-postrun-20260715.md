# CVRP Direct Open Control R4 Postrun Audit

Date: 2026-07-15

Status: complete, valid, terminal negative algorithm evidence

## Identity and Completion

- run root:
  `/home/clawd/research/scion-experiments/v04-cvrp-direct-open-control-r4-2r-gpt56sol-20260714T234816Z-claw`;
- clean runtime: detached `ff14318c`;
- model: `gpt-5.6-sol`;
- wrapper exit: `0`;
- completed rounds: `2/2`;
- provider calls: H=`2`, C=`2`, four unique successful attempts;
- retry/failure lanes: `0`;
- protocol candidates: `2`, both evaluated at screening;
- formal pairs: `64/64` valid, no candidate/champion/solver failure.

Prepared, pre-campaign, and post-campaign data identity all contain 81 files and
the same digest:

`ca7e470ec8d1f3569a690d10df5a170c4994108c71fecf5aa1a7a76b42630743`

Missing cases, missing companions, and unsafe files are zero. Secret scans are
clean; the key value was process-only. Postrun readiness reports 28 `ok`, 3
`skipped`, no required or optional failures, complete lineage, and no degraded
outcome. It is analysis/delegation ready, report-only, and not a promotion
authority.

## Agent and Framework Behavior

Both H calls used the call-local `change_locus.enum=["solver_design"]` and
returned the exact locus. Both autonomously targeted
`policies/baseline_modules/destroy_repair.py`; scheduler changes only connected
the new repair operators to the ALNS loop. Contract, Verification, and Canary
passed in both rounds.

All four provider calls were provider-managed with no output-token parameter or
transport ceiling. There was no forced target, target-intent, successor hint,
mechanism ranking/denylist, candidate cap, retry/backoff, truncation, semantic
budget, token budget, or output budget. H/C timeouts were unused transport
protection. This run therefore tests open algorithm behavior rather than a
governance-constrained workaround.

## Round 1

The first candidate added route-cap-aware regret ordering, passed `max_routes`
into repair, and used bounded single-customer ejection and relocation when a
customer could not be directly inserted.

| Evidence | Result |
|---|---:|
| case W/L/T | 1/2/5 |
| pair W/L/T | 13/14/5 |
| case win rate | 12.5% |
| median total-distance delta | 0.0 |
| CI | [-9.0, 1.5] |
| statistical status | uncertain |
| gate | `SCREENING_FAIL_WIN_RATE` |

The result does not support improvement. The route-cap path removed route-limit
rejections but converted part of the failure surface into repair errors and did
not improve final distance consistently.

## Round 2

The second H received the complete aggregate, eight case summaries, 32 pair
outcomes, and current branch code. It correctly cited the first-round median,
13/14 pair balance, and CMT2/CMT4 regressions. It removed the global
capacity-pressure term and added a separate adaptive pair-insertion repair.

| Evidence | Result |
|---|---:|
| case W/L/T | 0/3/5 |
| pair W/L/T | 9/17/6 |
| case win rate | 0% |
| median total-distance delta | -4.0 |
| CI | [-10.25, -0.5] |
| statistical status | negative |
| gate | `SCREENING_FAIL_WIN_RATE` |

The negative result is algorithmic, not infrastructural. The pair repair was
selected for 441 of 1,748 ALNS iterations, accepted 328 times, and participated
in 28 best updates, so it was active. Its average iteration was about 856 ms
versus roughly 336--409 ms for the other repairs. Total ALNS-core time increased
about 45% and search iterations fell.

The implementation also does not match its central claim. It adds two pending
customers to one or two existing routes but never ejects or relocates an
incumbent customer. If the anchor customer is individually blocked by capacity,
adding another customer cannot make it feasible. The operator changes ordering
and scoring while adding computation; blocked-customer rescue still depends on
the older ejection path. Do not promote or retry this candidate.

## Gate Assessment

The win-rate gate is not the blocker. Round 1 wins only one of eight cases; its
non-tie pair win rate is also below half. Round 2 wins no case and has a CI
fully below zero. Both failures would remain negative under a less ceremonial
reading of the raw evidence. Champion remains v1; validation and frozen stages
were correctly not entered.

## Remediation Priorities

P0: none.

P1: project existing CVRP ALNS iteration trace into compact, problem-owned,
proposal-only mechanism evidence. Include per-repair attempt, acceptance,
best-update, and elapsed-time summaries plus route-limit and repair-error
comparisons. Raw evidence already exists, but the generic summary currently
emits `mechanism_evidence={}`, zero generic operator counters, and
`opportunity_status=unknown`. This weakens the next H's causal attribution.

P1: encourage single-variable mechanism isolation. Round 2 simultaneously
removed capacity-pressure ordering and added pair repair, so comparison against
the original champion cannot attribute the negative result to one change.
This is guidance and feedback quality, not a new hard gate.

P2:

- eliminate redundant second-round source projection: the H2 prompt grew from
  about 87k to 170k characters because it carried branch-current code alongside
  the full champion source; do not replace this with a budget or truncation;
- state in the patch tool that one file path should have one composed change
  object; the second C emitted two scheduler changes that host normalization
  merged transparently;
- repair trajectory-manifest action/surface/target values emitted as `unknown`;
- expose negative statistical status and CI alongside the win-rate reason code;
- preserve the rule that cached-champion runtime is insufficient for strict
  relative-runtime conclusions.

Do not launch another control until the compact causal feedback path is repaired
and independently validated. Do not resume R4 or reuse either rejected candidate.
