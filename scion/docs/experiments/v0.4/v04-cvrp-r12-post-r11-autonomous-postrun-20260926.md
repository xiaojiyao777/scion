# CVRP R12: small screening pass, repeated shared validation failure

## Scope and terminal result

R12 stopped with `execution_blocked_infra` /
`EVALUATION_CHAMPION_EVIDENCE_BLOCKED` at validation. The final status was
written at `2026-09-24T18:01:02.790088+00:00`; tmux is dead, exit 20.
This category does not identify a provider/server outage: both intended
algorithms failed in the same problem-owned constructor. The invocation is
terminal and must not resume. No promotion or frozen execution occurred.

- [Frozen design](v04-cvrp-r12-post-r11-autonomous-preregistration-20260924.md)
- [Status](/home/clawd/research/scion-experiments/v04-cvrp-r12-post-r11-autonomous-20260924/status.json)
- [Summary / ordinary step refs](/home/clawd/research/scion-experiments/v04-cvrp-r12-post-r11-autonomous-20260924/campaign_summary.json)
- [Safe research history](/home/clawd/research/scion-experiments/v04-cvrp-r12-post-r11-autonomous-20260924/research_history.jsonl)
- [A expanded screening](/home/clawd/research/scion-experiments/v04-cvrp-r12-post-r11-autonomous-20260924/metrics/182c2070-66b6-407b-997e-bf4a8269d8bf.json)
- [Validation, operator-only](/home/clawd/research/scion-experiments/v04-cvrp-r12-post-r11-autonomous-20260924/metrics/4d029e0f-ec63-4525-b960-3b99bdc48e24.json)

Started September 24 at 11:48:32 UTC from R11's complete B tree. There were
11 scheduled steps: six distinct evaluated candidates, three expansions,
one Patch Contract rejection, and one blocked validation. All 108 screening
pairs are valid. Validation attempted 12 pairs, with ten valid and two
shared failures: 120 attempted / 118 valid overall. The summary's nine
`formal_screened_candidates` are nine stages, not nine distinct candidates.

Runtime was unchanged from `e405bfd2`, HEAD `841de42b`, with the declared
uncommitted documentation/input/test work. No concurrent tests, cleanup or
other solver was identified; continuous host-load evidence is unavailable.
Autonomous ordering was champion-first, not counterbalanced. Local effects
are relative to R11 B, never original B0. Clock-sensitive gains remain limited.

## Framework, creative sessions and source fidelity

All 62 physical provider calls succeeded at attempt index zero: 37 H research
turns and 25 C turns. No retries, finalizer call or global-cap exhaustion.
H actions: 15 source reads, nine history reads, six frontier reviews and seven
exports. C actions: nine revisions, eight tests, one source read, seven ready
exports. Seven exported patches include one rejected before evaluation.

Every actual H context retains the exact R12 question and complete indexed
102-record prior history / four prior observations. The ordinary new history
contains ten rows, including the Contract rejection but no failed validation
row or private constructor diagnostics. Availability does not prove attention
to all prior evidence. All 131 visible source entries across 25 C contexts
equal the appropriate pre-attempt branch source values; indexed non-visible
peers are not misrepresented as inline content.

The initial 100-file champion equals R11 B byte-for-byte, excluding caches.
All three final complete 100-file trees match their accepted ordinary changes
and untouched files. No patch reconstruction is used as the next input:

| Branch | Complete source under R12 `candidate_workspaces/` | Last result |
|---|---|---|
| A `6665d76d…` | `candidate-32jstm92` | Expanded pass, validation blocked |
| B `cfecdaab…` | `candidate-1f4mk6ez` | Initial fail at step 6 |
| C `68b6b775…` | `candidate-220r5o28` | Expanded uncertain at step 8 |

Step 5's H targeted scheduler.py, but its exported primary patch targeted
local_search.py and placed scheduler.py in additional changes. Contract
correctly rejected the primary-target mismatch. This is not a prohibition
on multi-file research. The rejected patch did not become A's executable head;
the next accepted A change continued from its last verified source.

For every valid pair, both algorithms were loaded and active, error count was
zero, solution validity held and fleet violation was zero. All raw distance
differences and per-case medians were recomputed. Existing Protocol/Decision
results are preserved, including the absence of a validation Decision.

## Actual H/C changes and observed screening

Positive effect means local champion distance minus candidate distance.
Interpretation below is analysis, not another quality gate.

| Step / branch | Actual implementation | Case W/L/T; median [CI] |
|---|---|---|
| 1 / A | Best predicted SWAP* over the existing bounded shortlist, then exact rescore; faithful | 0/2/1; -11 [-119.5,0] |
| 2–3 / B | Route-pair ranking by high-removal-saving customer exchange opportunity; faithful but nontrivial up-front cost | Initial 2/0/1; expanded 3/1/2, +0.5 [-2,22] |
| 4 / C | 2-for-1 free-reinsertion fallback after unsuccessful 1-for-1 SWAP*; faithful | 0/2/1; -25 [-51.5,0] |
| 5 / A | Phase-selective multi-file SWAP* patch rejected for primary-target mismatch | No Protocol |
| 6 / B | Skip SWAP* on active-frontier VNS, retain full-scope calls; faithful | 1/1/1; 0 [-45.5,10.5] |
| 7–8 / C | Remove 2-for-1 fallback; inspect two active-frontier route pairs after exhaustive exact opportunity ranking | Initial 2/0/1; expanded 3/1/2, +1.25 [-3.25,50.5] |
| 9–10 / A | Lazy neighbor-updated marginal-saving worst removal; retains A's earlier best-improvement SWAP* | Initial 2/0/1; expanded 3/0/3, +2.25 [0,11.25], pass |

C's final implementation does not realize the H's cheap high-saving shortlist
for ranking: `customer_pair_limit=None` enumerates all customer pairs before
the two-route-pair selection. Its intended small final shortlist therefore
does not bound the up-front scan. This is an implementation-fidelity/cost
limitation, not missing source or a new Contract restriction.

A's lazy worst removal uses a heap with neighbor version updates and preserves
randomized rank selection. It changes destroy semantics as well as cost;
greater throughput is not isolated evidence of the intended benefit. Its final
complete source differs from R12's champion only in local_search.py and
destroy_repair.py; inherited scheduler.py is unchanged. No sibling merge.

### Final A expanded result

Seeds are 110017,110023,110039,110051 in order. All 24 pairs valid.

| Case | Four distance effects | Median |
|---|---|---:|
| B-n34-k5 | 0,0,0,0 | 0 |
| tai100a | 17,53,19,-6 | 18 |
| X-n351-k40 | -109,-75,84,99 | 4.5 |
| A-n54-k7 | 0,0,2,0 | 0 |
| X-n190-k8 | 0,-44,0,3 | 0 |
| X-n513-k21 | 28,8,8,8 | 8 |

The aggregate just clears the unchanged practical screen threshold of 2.0.
Mixed signs on X-n351 and tai100a caution against stable component attribution.
Both large cases still run zero ALNS in both arms; their changes cannot be
credited to lazy worst removal. The inherited SWAP* / initial-VNS / clock
interaction is part of the complete bundle. Do not pool this contrast with B0
comparisons or use it to claim retained improvement.

## Validation failure and independent repair boundary

X-n627-k43 fails at both seeds 110059/110063 in both intended algorithms:
`unable to pack customer 624 into 43 routes`, construction.py:135, followed by
nearest-neighbor fallback. Each has an algorithm error and exception stop.
This repeats R10's problem-owned greedy capacity-packing failure. Each arm
stops in about 9.4–10.3 seconds of its 180-second limit; budget widening cannot
repair the greedy dead end. Runtime audit correctly blocks incomplete evidence.

The five valid case medians are 0, -25.5, -84.5, +0.5, -327. They are an
incomplete subset, not a replacement validation verdict. Resolving the crash
does not guarantee a positive validation outcome. Frozen and the separate
pre-R3 retained block remain unopened. This report is operator-only and must
not enter Scion H/C research input.

On September 26 the user explicitly authorized an independent GPT-6-Astra
constructor-repair subagent, parallel experiment design, and a fresh launch
only after checks pass. This is a separately labeled engineering intervention,
not autonomous Scion research or a repair of terminal R12. Preserve original
B0, all R10/R12 sources, metrics and negative/incomplete outcomes unchanged.
Apply the same minimal construction repair to new ordinary complete copies
of B0 and selected R12 A. A comparison then estimates performance beyond a
common repair, against **B0-fixed**, not unchanged B0. Never silently transfer
that claim to the original retained-B0 objective.

The next provider-free comparison uses equal existing budgets, counterbalanced
order, fresh seeds and unchanged complete-pair/scientific gates. Known screening
and exposed validation are development gates; neither becomes unseen again.
Independent confirmation remains conditional on untouched frozen/retained
populations. No failed case is removed and no historical evidence is backfilled.
