# R14 postrun: valid non-promotion, development-feedback and attribution gaps

Profile: Experiment Analysis. Read the entry pack, experiment index, R14
preregistration, operations/runbook/postrun handoff, ordinary status/summary,
all 120 provider traces, 12 linked metrics, safe history, relevant source and
development-check implementation. No original SQLite, solver rerun, provider
call, runtime edit or new experiment. Documentation is the only changed output.

## Terminal and scientific result

Started `2026-09-27T02:19:53Z`; final status
`2026-09-27T08:44:52.323359+00:00`, `completed` /
`requested_rounds_completed`. Twelve evaluated screening stages, ten distinct
evaluated candidates, eleven H/C attempts and one Code-session abandonment.
All 108 paired observations are valid, intended-algorithm active, feasible,
fleet-protected and error-free; objective differences match recorded deltas.
No validation/frozen, promotion or retained evidence. Comparator is local
R12-A-fixed, not B0-fixed or unchanged original B0. Autonomous champion-first
order remains a limitation. No known operator contamination was introduced.

- [Status](/home/clawd/research/scion-experiments/v04-cvrp-r14-post-r13-autonomous-20260927/status.json).
- [Summary and exact metric references](/home/clawd/research/scion-experiments/v04-cvrp-r14-post-r13-autonomous-20260927/campaign_summary.json).
- [Frozen design](v04-cvrp-r14-post-r13-autonomous-preregistration-20260927.md).

| Step / branch | Candidate research | Case-median delta / CI | Result |
|---|---|---|---|
| 1–2 / A | portfolio-scale pair-weight updates | initial +59.5 [0,180]; expanded 0 [0,27.25] | uncertain, 2/0/4 |
| 3–4 / B | nearest-neighbor SWAP* shortlist | initial +0.5 [0,12]; expanded 0 [-0.25,12.25] | failed case quality, 2/1/3 |
| 5 / C | generalized-savings ensemble | 0 [-93,19] | failed |
| 6 / A | opportunity-directed SWAP* generation | 0 [-215.5,17] | failed |
| 7 / B | reuse neighbor graph across VNS calls | 0 [-1.5,85] | failed |
| 8 / C | exact streaming top-k SWAP* shortlist | 0 [-29,0] | failed |
| 9 / A | balanced first-trial pair sequence | -3.5 [-435.5,0] | failed |
| 10 / B | per-call embedded-VNS time quantum | -60.5 [-77.5,0] | failed |
| 11 / C | pre-polish repair beam | 0 [-7.5,144.5] | failed |
| 12 / A | fleet-conditioned ejection insertion | no formal metric | Code abandoned |
| 13 / B | frozen-root one-hop VNS frontier | -10 [-89,0] | failed |

These are cumulative-branch versus champion effects, not isolated effects of
each newly named change. Initial and expanded screens also rerun observations;
their results must not be pooled into an independent confirmation.

## What is working

All 120 physical calls succeed at attempt index zero: H 66, C turns 53,
C finalizer one. Only 120/600 calls were used; no global cap or 48-hour guard
exhaustion. H performs 26 source reads, 17 history reads, ten history-frontier
reviews, one source search and twelve finalize actions (not twelve distinct
accepted hypotheses). C performs 23 revise, 15 test, eleven ready, three read
and one search actions. A ready action can itself be rejected in an open session.

All 66 H contexts have the exact question, 112-record history index and five
observations. All 302 visible C source values match their actual branch-current
source. All three final complete trees contain 100 files and exactly match
their accepted ordinary history changes, with rejected Code absent:

- A: `candidate_workspaces/candidate-clvfxx_u`.
- B: `candidate_workspaces/candidate-e3349x3e`.
- C: `candidate_workspaces/candidate-whdcgxwx`.

Source continuation, history access and negative-result feedback therefore work
in this run. A failed scientific screen retaining a verified provisional head
is intentional research continuity, not an accidental promotion or rollback bug.

## Confirmed gap 1: preflight failure gives C no actionable reason

Step 12 spends all four test calls on `preflight_rejected`, each with empty
checks/counts (zero tests executed). It also encounters duplicate-file and
selector errors, which do have explicit feedback. Its ready action receives
`latest_draft_not_passing`; after another revision and the twelve-turn bound,
the finalizer abandons. The scheduler correctly continues with a fresh H;
this is not a campaign-wide budget failure.

Read-only parsing of the exact provider-visible draft and the existing static
checks identifies:

- Draft 2 scheduler: C9 rejects `__import__` / dynamic import use.
- Draft 3 scheduler: C8 rejects non-whitelisted `inspect`.
- Draft 4 passes these two static checks but was never development-tested;
  no claim is made that it passes all necessary checks.

The safety boundaries are justified and should remain. The feedback gap is
in `scion/core/code_development.py`: failed safety preflight and several
exceptions collapse to `DevelopmentCheckRun(outcome="preflight_rejected")`
with no check/file/reason. `scion/verification/development.py` similarly reduces
the safety checker to bool. C cannot see the actionable C8/C9 distinctions.
Return bounded, safe typed failure location/reason while preserving rejection;
do not expose private cases, raw exceptions or weaken import/security rules.

The generic finalizer wording still refers to confirming a "frozen ready"
candidate. In this attempt the latest draft was genuinely untested, so the
abandonment is not evidence that a passing draft needed a redundant closure.

## Confirmed gap 2: hypothesis interpretation and cumulative source diverge

Step 13 proposes one-hop frontier closure as a better alternative to the failed
wall-clock quantum. C implements the frontier change in local_search.py, but
the inherited scheduler still computes `polish_allowance`, raises
`embedded_vns_reserve` and passes it into VNS. Thus the result tests **one-hop
frontier plus retained quantum**, not an isolated replacement restoring full
descent. This is an experimental reasoning/claim gap, not a Contract violation:
H named a local-search edit and the runtime correctly retained verified source.

Exact source:
[scheduler](/home/clawd/research/scion-experiments/v04-cvrp-r14-post-r13-autonomous-20260927/candidate_workspaces/candidate-e3349x3e/policies/baseline_modules/scheduler.py:392),
[frontier](/home/clawd/research/scion-experiments/v04-cvrp-r14-post-r13-autonomous-20260927/candidate_workspaces/candidate-e3349x3e/policies/baseline_modules/local_search.py:9).
H/C should reason explicitly about retained versus removed preceding changes
and the actual comparator. This must not become automatic host rollback,
mechanism selection, compulsory ablation or a new promotion gate.

## Attribution and screening-design limitations

All 28 X-n351 pairs run zero ALNS in both arms. A's first patch changes only
pair-weight selection/update logic, yet its initial X-n351 case delta is +180.
That difference cannot be credited to the changed ALNS logic. Later stages
also show large variable deltas on paths with no ALNS. Timing-sensitive
bundle effects require care; source costs alone do not prove the main hot path.

Several H texts focus on the known X-n190 bottleneck, but the unchanged initial
screen contains B-n34, tai100a and X-n351. X-n190 is evaluated only in the two
expanded screens, before the later quantum/beam/one-hop proposals. Those later
proposals' claimed X-n190 improvements were therefore not directly tested by
their own formal metrics. Keep their recorded negative Decisions; any future
coverage adjustment needs a prospective problem-owned design, not a case drop,
post-outcome expansion or generic host-selected target.

## Verdict and next action

R14 is a valid no-promotion result, with usable negative evidence, not proof
that Scion cannot research or that CVRP has improved. Persistent complete-source
research works; actionable development feedback and experimental attribution
remain deficient. Prioritize bounded C preflight diagnostics and focused
regressions before spending another campaign on opaque rejections. Separately
address cumulative-source reasoning and hypothesis/population alignment in a
prospective design. Do not widen budgets or weaken scientific gates by default.
No implementation or new run is authorized by this status/diagnosis response.
