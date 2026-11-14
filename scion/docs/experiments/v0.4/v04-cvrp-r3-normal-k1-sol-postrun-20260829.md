# CVRP R3 normal K1 continuous-research postrun

Date: 2026-08-29 UTC

Preregistration:
[`v04-cvrp-r3-normal-k1-sol-preregistration-20260828.md`](v04-cvrp-r3-normal-k1-sol-preregistration-20260828.md)

Experiment root:
`/home/clawd/research/scion-experiments/v04-cvrp-r3-normal-k1-sol-20260828-r1`

## Outcome

The preregistered campaign finished normally with exit code zero and is
classified `VALID_16_STAGE_NO_PROMOTION`.

- status: `completed`, `requested_rounds_completed`, validity `valid`;
- scheduled research calls: 21;
- formal evaluated stages: 16 of 16, all screening;
- research rejections: 5;
- provider dispatches: 114 of 272, with every proposal attempt closed;
- active branches used: three;
- validation/frozen/promotion: `0/0/0`;
- terminal champion: unchanged `v1`.

The ordinary artifacts agree on the terminal counts: 16 metric files, 21
SQLite events (`16` experiments plus `5` research rejections), 21 ordered
research-history rows and 114 LLM traces. No interrupted or unknown execution
outcome occurred.

This is valid negative CVRP research evidence. It does not satisfy the R3
acceptance condition and does not authorize retained-B0 evaluation.

## Research trajectory

Provider/solver-free trajectory reconstruction reports:

- 16 formal and 16 distinct H episodes from 114 charged calls
  (`0.14035` distinct formal H per call);
- 12 observed distinct H+patch pairs and no exact H or H+patch replay;
- maximum branch depth five;
- Contract: 15 pass, one fail across 16 formal episodes;
- Verification/code-readiness path: 11 pass, four fail across the 15
  Contract-admitted episodes;
- screening Decisions: five `expand_screening`, ten `continue_explore`, one
  `abandon` after a Protocol pass with candidate-runtime failure;
- complete pair accounting: 832 attempted, 827 valid, five failed;
- all five failed pairs were candidate-only process timeouts; invalid-output,
  infeasibility and protected-objective regressions were zero.

The campaign therefore demonstrated sustained proposal production, branch
continuity, exact-candidate expanded-screen reuse and deterministic safety
decisions. Its limiting factor was algorithm quality and runtime robustness,
not proposal yield or infrastructure.

## Closest positive candidate

Rounds 15-16 evaluated the same exact cumulative candidate from
`candidate-yic4dmhh`, digest
`e99a91bbe7e72050be29a815d0985cc231d680a354b827c47578cd967713f954`.
Its incremental local-search delta implementation produced the strongest
observed CVRP result:

- initial screen: 32/32 valid, case W/L/T `5/2/1`, median distance delta
  `+17`, CI `[-1, 109]`, then exact-candidate expansion;
- expanded screen: Protocol quality pass, case W/L/T `7/2/3`, pair W/L/T
  `56/19/21`, median `+3.75`, CI `[0, 31.75]`;
- search allocation changed materially: ALNS iterations `11926` versus `1965`
  and best updates `258` versus `155` for candidate versus champion.

It nevertheless produced five repeatable candidate-only hard timeouts on
`X-n716-k35` (seeds 11, 29, 73, 97 and 103), each at the 120-second solver
limit plus the 15-second subprocess guard while the champion completed. The
Decision layer correctly overrode `SCREENING_PASS` with
`CANDIDATE_RUNTIME_FAILURE`, abandoned the candidate and did not enter
validation. A positive quality screen with incomplete runtime safety is not a
promotion.

## History continuity

Within-campaign history was explicitly used in several rounds. Selected H
episodes read and cited ordinary current/sibling evidence eight times. In
particular:

- round 6 used the expanded round-5 throughput loss to move from another
  local-search mechanism to cheap stagnation feedback;
- round 11 used the expanded round-10 joint-arm failure to abandon more
  scheduler complexity and propose constant-time local-search deltas;
- rounds 13 and 15 used the immediately preceding rejection/expanded result to
  simplify the mechanism and then attack the measured VNS throughput cost.

This establishes attributable uptake and that Scion can make a later H depend
on an earlier research branch. It does not establish history benefit or
reliable continuous research control.

After round 16 exposed a Protocol quality pass plus five candidate-only hard
timeouts, rounds 17-21 completed no successful history read. Rounds 17-20 did
not invoke a history tool. Round 21 issued one narrow literal search, received
zero matches, then finalized H. The visible index already contained the latest
runtime failure, code abandonment, schema rejection, quality failure and Patch
Contract rejection. All five selected bases declared no nearest prior.

The present optional-history rule therefore prevents host mechanism steering,
but also permits silent disregard of the immediate failure frontier. The next
runtime change must retain agent choice while requiring an explicit,
agent-authored disposition of the latest live-campaign failures.

## Final stage

Round 21 changed simulated-annealing cooling to add stagnation-triggered
reheating. The exact candidate was stable at runtime: 32/32 pairs valid, no
runtime failure or protected regression. It failed quality decisively:

- case W/L/T `0/0/8`;
- pair W/L/T `2/2/28`;
- median `0`, CI `[0, 0]`, statistical status `tie`;
- candidate/champion ALNS iterations `775/787`, accepted `638/653`, best
  updates `47/47`;
- runtime median `+3 ms`, ratio `1.000064`, regression rate `0.5625`.

More importantly, all 32 candidate traces reconstruct zero reheat triggers;
maximum continuous stagnation was 81 iterations against a trigger of 100. The
hypothesis premise was also inconsistent with the configured cooling horizon:
at 100 iterations the natural temperature remains above the proposed cap, so
the first possible `max(current, cap)` is a no-op. Problem-owned mechanism
evidence correctly remained `exact_mechanism_activation=false` and
`unavailable_current_source`.

The code-research session's own custom falsifier returned `failed`, while the
D1-D4 host checks passed. The session ignored the separate falsifier result,
allowed `ready`, and spent a full formal screen on a mechanism that its own
research test had not supported. This is a framework control defect, not an
algorithm result to reinterpret.

## Lineage gaps

The terminal summary retains the selected six-field research basis, but all 16
ordinary SQLite experiment rows have
`selected_hypothesis_research_basis_json=NULL`, and the research-history writer
drops the same field. Ordinary evaluated SQLite rows also leave their
`execution_outcome` columns null even though status, summary and history
classify them as `evaluated/EVALUATION_COMPLETED`.

The R3 database and JSONL are append-only evidence and will not be rewritten.
Future runs must persist the attempt-local selected basis and evaluated outcome
at the original write point. Any R3 reconciliation remains a separate ordinary
postrun projection with the original nulls explicitly preserved as facts.

## Next falsifiable rung

Before another provider/solver campaign:

1. make a failed custom falsifier a session-local, exact-patch readiness veto;
2. require an agent-authored disposition of the latest live-campaign failure
   frontier, without host ranking, mechanism choice or mandatory citation;
3. persist selected-H basis and evaluated execution outcome through the normal
   append-only lineage/history path;
4. require proposed mechanism activation to be tested or explicitly reported
   unavailable before an expensive formal screen, while keeping those
   diagnostics out of Safe Features and Decision;
5. add large-instance deadline falsification to performance-changing CVRP code
   research before a new frozen campaign.

R4 remains blocked because R3 produced no promotion. The next experiment must
be freshly preregistered after these framework changes and their provider- and
solver-free regressions pass.

## Subsequent repair disposition (2026-08-29)

The frozen R3 root, artifacts, Decisions and
`VALID_16_STAGE_NO_PROMOTION` classification remain unchanged. In particular,
its historical SQLite and JSONL null fields were not rewritten. The following
runtime changes apply only to future campaigns:

- a failed self-authored falsifier permanently vetoes the same complete
  executable patch value for that C session; test hints and patch-list ordering
  cannot reopen it;
- explicit failures at the latest ordinary live round of `current` and
  `sibling` independently require an agent-authored used/rejected disposition.
  External and older history remain optional, and the host neither ranks refs
  nor selects mechanisms;
- attempt-local selected-H basis and typed evaluated/rejected/infra outcomes
  now share the ordinary StepRecord, SQLite, summary and research-history write
  path. Validation/frozen evidence remains excluded from H-only history;
- candidate/workspace disposition failure is an exact-once typed
  `BLOCKED_INFRA` fact that preserves either the interrupted outcome or the
  completed Protocol plus unapplied Decision and selected basis;
- accepted-chain reconcile cleanup failure preserves the exact replay-head
  basis and interrupted fact without deleting an accepted head, while a
  promotion already committed at the champion boundary remains promoted;
- CVRP development guidance requires an agent-authored exact-path activation
  falsifier plus a separate public synthetic 719-customer deadline check. These
  diagnostics remain outside Safe Features and Decision.

The final provider-free repository regression passed `2259` tests with one
declared skip in 435.67 seconds. The fresh R3b question and inputs were then
frozen; R3b is a new campaign, not a continuation or repair of R3.
