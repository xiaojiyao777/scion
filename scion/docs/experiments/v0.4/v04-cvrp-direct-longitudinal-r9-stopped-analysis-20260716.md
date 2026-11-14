# CVRP Direct Longitudinal R9 Stopped Analysis

*Date: 2026-07-16*
*Disposition: terminal fresh-root evidence; continued only through a distinct diagnostic copied root*

## Identity

- root:
  `/home/clawd/research/scion-experiments/v04-cvrp-direct-longitudinal-r9-4r-gpt56sol-4r-gpt56sol-20260716T034629Z-claw`;
- clean detached runtime:
  `/home/clawd/research/or-autoresearch-agent-v04-direct-runtime-db971c57`;
- exact pushed commit:
  `db971c57b7ed5f7ac79c88f151b182b11e2bb816`;
- model/runtime: `gpt-5.6-sol / direct_v3`;
- requested/effective typed rounds: `4/1`;
- provider activity: exactly `2H/2C`, all four calls successful, retry and
  replacement zero, provider-managed output, and no Scion transport ceiling;
- wrapper/postrun exits: `0/0`;
- status: `valid_but_incomplete / incomplete`;
- stop: `execution_research_rejected`;
- champion: v1, unchanged.

The fresh-root run started at `2026-07-16T03:46:52Z` and ended at
`2026-07-16T04:19:56Z`. Guarded readiness and the wrapper-owned completion
preflight passed. Postrun acceptance is ready with no required or optional
failure. The second candidate never reached Protocol and is excluded from
algorithm conclusions.

## Evaluated Round 1

H1 independently selected `destroy_repair.py` and proposed a substantive
related-customer regret-2 pair-insertion repair, with scheduler registration.
The implementation evaluates both pair orientations over existing route edges
and permitted new-route placement, then selects a pair by regret against its
second-best placement. The new operator was really selected and executed; it
was not a telemetry-only or helper change.

Formal screening was complete and valid:

- attempted/valid/failed pairs: `32/32/0`;
- candidate/champion failures: `0/0`;
- candidate loaded/active/valid: `32/32/32`;
- fleet violation: zero in all 32 candidate rows;
- case W/L/T: `3/2/3`, win rate `0.375`;
- pair W/L/T: `9/11/12`, win rate `0.28125`;
- total-distance case median/CI: `0 / [-5.5,4.0]`;
- Protocol: `fail / SCREENING_FAIL_WIN_RATE`;
- Decision: `continue_explore`;
- runtime median ratio/delta: `0.9998729 / -3 ms` with high-confidence fresh
  evidence.

The positive cases were A-n64-k9, E-n101-k14, and P-n65-k10. B-n63-k10 and
CMT2 regressed; M-n200-k17 was all ties and X-n110-k13 had three ties and one
loss. This is a valid negative algorithm result, not a framework or runtime
failure.

Mechanism diagnostics are association-only and excluded from Decision. They
reported candidate/champion iterations `1567/1671` and route-limit rejections
`93/85`. The new repair was selected `384` times, accepted `259`, associated
with `15` best updates and `37` route-limit rejections, with zero repair error.
The data prove activation but not that this operator caused the final
objective difference.

Two implementation risks remain relevant to later hypotheses:

- deadline or no-placement fallback calls the old single-customer regret-2
  repair without `context`, `reserve`, or `max_routes`;
- equal-delta sorting places route index `-1` before existing routes, so a new
  route wins that tie.

Neither invalidated the complete Protocol result, but both can waste the
scientific runtime and may contribute to route-limit rejection.

## Rejected Round 2

H2 received R1's full objective, pair, case, mechanism, Protocol, and outer
Decision evidence. It explicitly used the lower iteration count and higher
route-limit count, then changed direction from repair to a general cross-route
2-opt local-search neighborhood. This confirms that the repaired canonical
feedback projection now carries `decision=continue_explore` and that the agent
attempted a materially different algorithm mechanism.

C2 did not implement the hypothesis. Its typed edits only:

- added `_cross_route_two_opt` to the default VNS list without defining it;
- removed the `_two_opt_star` function header while leaving the name in the
  same list.

The remaining old body became unreachable code inside the preceding function.
Syntax therefore passed, but V1b correctly found `_cross_route_two_opt` and
`_two_opt_star` undefined in `local_search.py`. Verification returned
`research_rejected / VERIFICATION_LIGHT_REJECTED / V1b_undefined_names` in
milliseconds. No formal candidate, Protocol, Decision, or algorithm-quality
claim exists for H2.

Both Code traces used about 4096 output tokens while Scion recorded no output
parameter or transport ceiling. A prior complete R8 Code response exceeded
4096 tokens and the next R9 continuation Code response is complete at 3184,
so the current artifacts do not establish a strict provider cap or truncation.

## Transaction and Reporting Acceptance

R9 is the live acceptance test for the R8 transactional repair:

- the H1 decision-completion intent is `committed` and uniquely binds the
  experiment, Decision, H, Branch, and completed verified-candidate marker;
- the H2 rejected staging tree exists only in `archive/round_2_`;
- the durable workspace hash, Branch current hash, Branch last-clean hash,
  verified code hash, and executable snapshot hash are all
  `4a9771a9a0d75083f620ab21f5a2d8b961e94e9d5ff71a0a8d04641f642b5d54`;
- `candidate_workspaces/` and `promotion_journals/` are empty;
- accounting separates one evaluated formal round from one
  `research_rejected` attempt;
- postrun summary reports one Decision, one V1b failure, Contract intercept
  rate `0.0`, and Verification intercept rate `0.5`.

No R8-style durable-workspace pollution, decision split-brain, or typed-report
false negative remains. The previously accepted recovery P2s are unchanged.

## Invocation Stop and Continuation

Stopping on H2 is the current normative v0.4 rule: any non-`EVALUATED` outcome
terminates the current invocation. Automatically generating proposals until
four formal results exist would be unsafe without a proposal cap and would
recreate an unbounded retry-shaped loop. No such retry, cap, budget, or heavier
gate is added.

The Branch is nevertheless clean, `EXPLORE`, schedulable, and has no execution
hold. The addendum permits an explicit later operator invocation. R9 is
therefore continued only through the distinct diagnostic copied root:

`/home/clawd/research/scion-experiments/v04-cvrp-direct-longitudinal-r9-cont1-3r-gpt56sol-20260716T042653Z-claw`

That continuation requests three new typed Protocol rounds from the exact H1
clean branch. It is not a fresh formal-root control and must not be reported as
one.

## Diagnostic Continuation Terminal Evidence

The distinct continuation root is terminal and read-only:

`/home/clawd/research/scion-experiments/v04-cvrp-direct-longitudinal-r9-cont1-3r-gpt56sol-20260716T042653Z-claw`

It started at `2026-07-16T04:27:49Z` and completed campaign execution at
`2026-07-16T05:35:23Z`. The current invocation completed its requested `3/3`
typed screening rounds and stopped with `requested_rounds_completed`. Campaign
status is `valid / complete`, research conclusions are eligible, and all 96
new formal pairs are valid. The cumulative campaign contains exactly `5H/5C`:
R9 H1/C1, rejected pre-formal H2/C2, and continuation H3/C3 through H5/C5.
Every provider call was a single successful attempt; there was no retry or
replacement.

The cumulative canonical screening history is unique at rounds 1 through 4.
All four Decision completion intents are `committed`; the H3, H4, and H5
verified markers are `completed`; Branch current, last-clean, verified, and
executable identities agree after every round. Candidate staging and promotion
journal directories are empty. The continuation therefore accepts the R8/R9
transactional repair across three consecutive evaluated candidates.

The four-round longitudinal trajectory is:

| Round | Cumulative candidate mechanism | Case W/L/T | Pair W/L/T | Median / CI | Candidate/champion ALNS iterations |
| --- | --- | ---: | ---: | ---: | ---: |
| R1 | related-customer regret-2 pair repair | `3/2/3` | `9/11/12` | `0 / [-5.5,4]` | `1567/1671` |
| R2 | bounded two-customer ejection chain | `2/4/2` | `10/15/7` | `-1.5 / [-8,5.5]` | `422/1678` |
| R3 | granular three-route cyclic exchange replacing the ejection chain | `2/3/3` | `8/15/9` | `0 / [-14.25,0.5]` | `839/1678` |
| R4 | promise-gated embedded VNS plus cheap intra-route polish | `2/3/3` | `10/15/7` | `0 / [-21.25,1.25]` | `8809/1678` |

All four Protocol results failed only `SCREENING_FAIL_WIN_RATE` and produced
`continue_explore`. Champion v1 was never changed. R3 and R4 reused cached
champion solutions, so their aggregate runtime evidence is correctly marked
insufficient; their per-pair candidate telemetry remains available for
proposal feedback. These are cumulative Branch candidates versus champion,
not isolated A/B estimates of the latest incremental patch.

## Longitudinal Algorithm Findings

H3 was substantive and active, not a helper-only change. Its ejection chain
accepted 1,111 moves across 32 pairs, but candidate ALNS iterations collapsed
to `422` versus `1678` for champion. Static review found that the distinct-third-
route delta omitted the source-route removal delta. This usually conservatively
misses useful moves, but rounded distances also make its direct-delta telemetry
non-exact. Per-call check and accepted-move limits were repeatedly reset by the
outer VNS, so the neighborhood occupied most embedded-VNS time.

H4 consumed that negative objective and throughput evidence. It removed the H3
ejection implementation, replaced its default VNS slot with a granular atomic
three-route cycle, and restored ALNS iterations to `839`. Independent review
found no customer-coverage, capacity, route-count, delta, rollback, or deadline
correctness defect. Its per-call bounds were still reset by VNS improvement,
however, so embedded VNS continued to dominate the solve. Mechanism telemetry
also combined cyclic exchange and its follow-up relocate/two-opt descent.

H5 then changed level from a local neighborhood to scheduler policy. It ran a
cheap intra-route polish on each repaired candidate and gated full VNS by
promise, cadence, and a solver-internal runtime-share target. This restored
actual destroy/repair ALNS iterations to `8809`, about `5.25x` champion, and
reduced cumulative embedded-VNS time from H4's `743691 ms` to `241859 ms`.
Quality nevertheless remained negative: CMT2 was `0/4`, CMT4 was `1/3`, and
the final pair result was `10/15/7`. More diversification alone did not recover
the intensification lost by suppressing full VNS.

The generic runtime field `solver_algorithm_search_iterations` is a cross-phase
activity counter and includes accepted polish moves; H5 recorded `19060` there.
This does not pollute agent feedback. The problem-owned canonical mechanism
projection explicitly reads `solver_algorithm_alns_iteration_trace` and exposes
the correct `8809/1678` counts; the generic counter does not appear in the
provider-visible compact feedback.

The evidence therefore rejects the earlier broad claim that heavy Scion gates
are the primary obstacle. V1b stopped one genuinely incomplete C2 in
milliseconds, while three later substantial candidates passed all gates and
completed `32/32` valid pairs. Scion now demonstrably carries full objective,
case, pair, mechanism, Protocol, and Decision feedback into materially different
algorithm proposals. The remaining research obstacle is the solver's
intensification/diversification design and the precision of problem-owned
mechanism attribution, not an inability to reach or edit the algorithm.

## Postrun Resolver Defect

The campaign command and postrun report rebuild exited `0`, but the outer
wrapper returned effective status `64` because the required
`formal_candidate_diff_integrity` readiness check failed. Resume had correctly
reanchored the in-memory champion to the copied campaign, while the formal-
candidate base helper re-read the stale source-campaign path from SQLite
history. Public-reference redaction converted that external absolute path to
`artifact:champion_v1#bb7f8d39a7f6`; postrun replay then incorrectly treated
the opaque public id as a campaign-relative filesystem path.

This does not invalidate the 96 solver pairs or completed Protocol/Decision
transactions, but it is a real framework replay defect rather than an expected
fresh-root rejection. The implemented repair:

- makes the producer reuse the already verified campaign-local champion;
- supports existing opaque v3 base refs only when champion id, local path,
  editable identity manifest, full snapshot hash, and every file digest agree;
- keeps v1/v2 or malformed opaque refs fail-closed;
- also fails closed on a missing/mismatched local snapshot, nested campaign
  without a safe local snapshot, or escaping/looping symlink.

A read-only rebuild with the repaired code exits `0` and restores
`formal_candidate_diff_integrity=ok`: all three new candidates use
`apply_check`, materialize successfully, and report zero formal failures. The
campaign tree digest is unchanged before and after at
`02b2b2171598e1166ce2fe4728de326e73b51753f24a4a5efb755a5fe4d6315d`.
The rebuilt aggregate still has `current_run_analysis_ready=false` only because
the historical `run_status.json` and `exit.txt` correctly preserve the original
wrapper `64` and postrun-failure markers; `delegation_ready=true`. Rewriting
those terminal wrapper facts to fabricate an all-green historical root would
be incorrect.

Verification covers `58` focused resolver/workspace tests, `105` related
formal-screening tests across the two implementation passes, and the correctly
rooted standard suite at `2040 passed, 1 skipped in 479.74s`. `compileall`,
`git diff --check`, and two independent fail-closed reviews pass.

Do not launch a fresh eight-round root until the repair is committed and
pushed. The fresh root is the end-to-end wrapper/readiness acceptance plus a
reproducibility and longer-adaptation experiment; it is not needed to prove
that substantive algorithm editing and longitudinal feedback are working.
