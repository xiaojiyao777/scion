# CVRP R3f adaptive-history K1 postrun

Date: 2026-09-01 UTC

Preregistration:
[`v04-cvrp-r3f-adaptive-history-k1-sol-preregistration-20260831.md`](v04-cvrp-r3f-adaptive-history-k1-sol-preregistration-20260831.md)

Experiment root:
`/home/clawd/research/scion-experiments/v04-cvrp-r3f-normal-k1-sol-20260831-r1`

## Outcome

R3f completed normally and is classified
`VALID_20_STAGE_HORIZON_CENSORED`.

- terminal status: `completed`, stop reason `requested_rounds_completed`,
  run validity `valid`;
- requested/evaluated stages: `20/20`;
- scheduled calls: 23, comprising 20 evaluated stages and three typed
  research rejections;
- Protocol stages: 19 screening, one prospective validation and zero frozen;
- provider dispatches: 145 of 340, across 16 closed proposal attempts;
- execution outcomes: 20 evaluated, three research-rejected, and zero
  blocked-infrastructure, resource-exhausted, interrupted or unknown;
- active branches: three;
- terminal champion: unchanged `v1`; no promotion occurred.

The named tmux pane is dead with exit status zero and its capture says
`Campaign finished`, 20 experiments, champion 1 and three active branches.
That is consistent operational evidence, but terminal scientific truth comes
from the ordinary status, summary, metric and history artifacts.

R3f is valid negative research evidence. It reached prospective validation,
but the exact candidate failed both runtime completeness and the declared
quality requirement. It did not authorize frozen testing, promotion or
retained-B0 evaluation.

## Campaign accounting

The 23 scheduled calls comprise:

- 19 evaluated screening events;
- one evaluated validation event;
- two `PATCH_PROPOSAL_INVALID` rejections;
- one `CODE_RESEARCH_ABANDONED` rejection.

The 16 proposal attempts admitted 145 physical provider calls: 73 hypothesis
research turns, 58 code-research turns and 14 code-research finalizations.
The terminal research history contains 22 rows because the prospective
validation event is deliberately excluded from H-only history.

Screening Decisions in the 22 history rows are seven `expand_screening`, nine
`continue_explore`, two `abandon` and one `queue_validate`, plus the three
research rejections with no scientific Decision. These counts agree across
the terminal summary and ordered history trajectory.

## Prospective held-out validation

One cumulative exact branch reached the held-out validation split. Its current
step added a bounded pre-polish tournament in `scheduler.py`; the evaluated
cumulative candidate contained accepted changes in both
`destroy_repair.py` and `scheduler.py`.

Its exact progression was:

1. Initial screening completed 32/32 valid pairs across eight cases. Case
   W/L/T was `5/1/2`, pair W/L/T was `17/5/10`, and median total-distance
   improvement was `+5.25` with CI `[0,14.5]`. Decision was
   `expand_screening`.
2. Expanded screening completed 96/96 valid pairs across 12 cases. Case W/L/T
   was `6/1/5`, pair W/L/T was `45/17/34`, and median improvement was `+3`
   with CI `[0,9.5]`. Protocol returned `SCREENING_PASS`; Decision was
   `queue_validate`.
3. Prospective validation attempted all 96 declared pairs but obtained 94
   valid and two candidate-only timeout failures. The champion had zero
   failures. Both timeouts occurred on `X-n401-k29.vrp`, seeds 53 and 71;
   candidate processes exited `-9` after approximately 105.058 and 105.117
   seconds under the 90-second subject limit plus subprocess allowance.
   Candidate-only invalid output, candidate-attributable infeasibility,
   shared failure and bilateral failure were all zero.

The validation metric is durably finalized, but its paired evidence is not
complete. The 94 valid pairs descriptively give case W/L/T `6/2/4` and median
improvement `+1` with CI `[0,4.5]`; those numbers cannot turn missing
candidate outcomes into a complete held-out estimate. The observed case win
rate was `0.50`, below the validation threshold `0.66`; even assigning the two
missing pairs the most favorable possible outcomes cannot create an additional
case win because the other six `X-n401-k29` seeds were ties. Protocol returned
`INCOMPLETE_EVIDENCE` and `CANDIDATE_RUNTIME_FAILURE`, and Decision abandoned
the candidate. This is candidate-attributable negative algorithm/runtime
evidence, not a root-level infrastructure failure and not a validation pass.
No frozen stage followed.

The validation input and result never enter `research_history.jsonl`. R3g may
load the ordinary R3f history file, but its H cannot see this held-out row.

## Final exact-relocate horizon censor

The final scheduled call, number 23, and evaluated stage 20 independently
proposed an exact incremental evaluator for the existing inter-route
`_relocate` neighborhood in `local_search.py`. The cumulative branch candidate
contained accepted changes in `scheduler.py` and `local_search.py`; the result
therefore is not isolated causal evidence for `_relocate` alone.

Its initial screen completed 32/32 valid pairs with zero failures. Case W/L/T
was `2/1/5`, pair W/L/T was `9/5/18`, median improvement was `0`, CI was
`[0,25]`, and Decision was `expand_screening`. The branch ended in
`explore_expand` only because that initial screen was the twentieth evaluated
stage. There is no expanded-screen metric or event for this candidate and no
validation, frozen test or promotion.

This is a clean formal-horizon censor, not an interruption, screen pass,
screen failure or runtime failure. R3g must not resume or reconstruct the
candidate. Only the ordinary completed initial-screen history row may be
loaded in its frozen order.

## History continuity

R3f's terminal `research_history.jsonl` is frozen at 22 strict `cvrp` rows:
19 evaluated screening rows and three research-rejected rows. It contains no
validation or frozen evidence.

The eligible R3g external input is the following exact ordered concatenation:

1. R3: 21 rows;
2. R3b: one row;
3. R3c: two rows;
4. R3d: one row;
5. R3e: one row;
6. R3f: 22 rows.

The production loader reads `[21,1,2,1,1,22] = 48` strict `cvrp` records,
totalling 1,575,667 bytes. With the eight common ordinary observations, their
external ranges are R3 `history-0009..0029`, R3b `history-0030`, R3c
`history-0031..0032`, R3d `history-0033`, R3e `history-0034`, and R3f
`history-0035..0056`.

R3f's candidate source, branch workspace, SQLite state, status, metric files,
provider responses and live/dead process state are not R3g inputs. In
particular, neither the held-out validation result nor an executable
exact-relocate candidate is reconstructed from history.

## Carrier disposition

R3f used the preregistered single local tmux carrier for more than a day and
finished with pane exit status zero. This establishes that the carrier worked
for this run; it does not establish a lifetime guarantee. The retained dead
pane is operational residue only and may be removed after this postrun audit.

The carrier is not a service, deployment, distribution, scheduler or build.
It creates no scientific authority, object identity, lease, issuance,
registration, signature, receipt or repeated closure. Its state never enters
H, Protocol, Safe Features or Decision.

## Scientific conclusions

R3f narrows the useful search frontier without identifying a promoted
mechanism:

- the adaptive embedded-VNS scheduling candidate was a strong negative. It
  lost six of eight initial-screen cases with two ties, median improvement
  `-20`, CI `[-54,-5.25]`, while candidate ALNS iterations collapsed from 784
  to 32 relative to the champion. Do not invest another rung in that scheduling
  direction;
- exact inter-route evaluation remains a promising efficiency family, but the
  observations are cumulative-candidate, association-only evidence and are
  confounded by the deadline failure exposed later in the same campaign. The
  final exact-relocate initial screen is horizon-censored and cannot be called
  a pass;
- the pre-polish tournament reached validation but failed candidate runtime
  completeness and the declared quality threshold, while the later initial-VNS
  budget direction did not establish a reason for further investment. Neither
  direction receives a fixed replay or host priority in R3g;
- V3 cumulative-depth semantics remain unchanged. Accepted branch changes are
  not rolled back merely to isolate a later hypothesis. Every later result must
  therefore be reported against the exact cumulative candidate and described
  as association, not as an isolated current-step causal effect.

The next campaign may preserve the broad exact inter-route design starting
point, but Scion must independently select and generate any proposal through
the ordinary H/C path.

## Next falsifiable rung

Before another provider or solver campaign:

1. poll the existing monotonic deadline inside nested destroy/repair loops and
   discard a partially mutated candidate when the exit reserve is reached;
2. preserve the ordinary before-source packet needed for exact-candidate
   mechanism evidence after a transient candidate workspace is cleaned up;
3. clear stale stage and child-process progress fields at each new Protocol
   stage and subprocess launch;
4. pass the exact provider-free regression on the final combined launch tree;
5. preregister R3g as a fresh B0 campaign with exactly the 48 eligible H-only
   rows and a fresh output root.

These repairs do not revise R3f's artifacts or Decision. They add no host
mechanism selection, held-out exposure, identity/lease/signature/receipt/hash
lifecycle or repeated finalization authority.
