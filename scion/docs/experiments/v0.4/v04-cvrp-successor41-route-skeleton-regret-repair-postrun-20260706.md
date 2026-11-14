# CVRP successor41 route skeleton regret repair postrun

Date: 2026-07-06

## Scope

Successor41 tested `route_skeleton_regret_repair` as a proposal-only
target-intent-bound clean fork at the ALNS repair boundary. The intended
mechanism compared the normal repaired candidate against one bounded
route-skeleton-biased regret repair candidate before embedded VNS or polish.

Run root:
`/home/clawd/research/scion-experiments/v04-cvrp-successor41-route-skeleton-regret-repair-server-claw-2r-gpt55-20260706T053608Z-claw`

The run used local `gpt-5.5` through the server-local `claw` environment,
completed the requested two rounds, exited with wrapper status `0`, and was
postrun-acceptance ready. Completion preflight passed. A prior launch attempt
without the `claw` Python failed during dependency preflight because that
interpreter lacked `numpy`; it is not solver evidence.

## Campaign Outcome

- Status: valid, complete, postrun-ready.
- Stop reason: `max_rounds_exhausted`.
- Proposal attempts: 5.
- Proposal quality blocks: 3.
- Formal screened candidates: 2.
- Protocol metric results: 2.
- Promotions: 0.

The quality blocks were contract/shape failures, not model availability
failures. Target-intent binding stayed on `route_skeleton_regret_repair`.
Postrun readiness reported source visibility and research context checks as
actionable; target/source content needed for code generation was visible.

## Formal Results

Candidate 1 metric:
`campaign/metrics/a102f12b-a46b-4e85-af1f-74e8239341c0.json`

- Pair W/L/T: 6 / 19 / 7.
- Median delta: `-6.0`.
- A-n64-k9: 2 / 2 / 0, median `-3.0`.
- B-n63-k10: 1 / 3 / 0, median `-11.0`.
- E-n101-k14: 1 / 3 / 0, median `-4.5`.
- P-n65-k10: 1 / 2 / 1, median `-1.0`.
- CMT2: 0 / 4 / 0, median `-19.0`.
- CMT4: 1 / 3 / 0, median `-13.0`.
- M-n200-k17: 0 / 0 / 4, median `0.0`.
- X-n110-k13: 0 / 2 / 2, median `-6.0`.

Candidate 2 metric:
`campaign/metrics/90b61e31-fbf5-4bfc-a542-7abbe54bcfed.json`

- Pair W/L/T: 13 / 14 / 5.
- Median delta: `0.0`.
- Case-level lifecycle tier: `marginal`.
- Case winners: A-n64-k9 median `+15.0`, B-n63-k10 median `+10.0`.
- Case losses: P-n65-k10 median `-7.0`, CMT4 median `-16.0`.
- CMT2 was mixed but median positive: 2 / 2 / 0, median `+5.0`.
- X had one large positive seed but median `0.0`.

The second candidate improved materially over the first, but still failed
promotion due win-rate and marginal-signal gates. It is not a long-run
candidate.

## LLM And Context Findings

The run had 17 LLM traces:

- 5 `hypothesis_target_intent`
- 6 `hypothesis`
- 4 `tool_selection`
- 2 `code`

The important finding is negative for the prior blocker hypothesis: there is
no evidence that harmful prompt truncation caused the poor solver result.
General/preflight sections were sometimes compacted, but the active target
source, prepared successor focus, research obligations, measurement
diagnostics, feedback, and code-phase source requirements were visible. The
code prompt for the retained second candidate had full visible source for
`scheduler.py`, `destroy_repair.py`, and `local_search.py`.

The quality blocks came from structured-contract adherence:

- one hypothesis missed accepted `material_difference` /
  `branch_lesson_usage.clean_fork_diversity_claim` shape;
- one retry removed `expected_telemetry.effect` too aggressively after C11
  feedback;
- one second-round hypothesis again missed accepted `material_difference`
  shape.

These blocks are useful fail-closed behavior. They should not be bypassed.

## Code Findings

The retained second candidate implemented the mechanism in
`policies/baseline_modules/scheduler.py` only. It added a copied post-destroy
candidate, built a skeleton-biased repair, selected it only when feasible,
route-count compliant, and lower distance before VNS, and recorded telemetry
under `route_skeleton_regret_repair`.

However, the implementation shape is not acceptable as a production direction:

- `scheduler.py` grew from 568 to 714 lines in the experiment workspace.
- The skeleton behavior was added as multiple private methods inside
  `scheduler.py`, increasing helper sprawl.
- The mechanism remained close to a dual-candidate repair selector, despite
  the hypothesis contrasting it against prior repair-selector evidence.
- Detailed prepared telemetry fields were incomplete: default/skeleton repair
  distances, selected label, feasibility, route count, bounded effort, and
  per-decision counters were not emitted as direct structured fields.
- The implementation can select a better pre-VNS repair candidate while still
  changing downstream ALNS/VNS trajectory negatively, especially on P and CMT4.
- The replacement candidate still feeds subsequent adaptive repair-weight
  scoring through the originally selected repair operator, which muddies
  operator-credit attribution.

## Interpretation

Successor41 is not an infra/model failure. It is valid solver evidence.

The mechanism activated and produced direct pre-VNS objective movement, but
that movement was not reliably preserved into final paired objective results.
The first candidate was broadly negative. The second candidate showed a real
small-instance signal on A/B and a mixed-positive CMT2 signal, but P and CMT4
losses blocked promotion and make long-run expansion inappropriate.

## Next Action

Do not long-run successor41 and do not rerun the unchanged scheduler helper
implementation.

One same-mechanism diagnostic follow-up is defensible only if it is designed
first as successor41b:

- keep mechanism id `route_skeleton_regret_repair`;
- move nontrivial skeleton repair behavior into a coherent CVRP-owned module,
  with scheduler limited to a narrow boundary call;
- explicitly record default distance, skeleton distance, selected label,
  feasibility, route count, bounded effort, attempted/accepted counts, and
  pre-VNS delta;
- fix attempted/best-improved telemetry semantics;
- avoid contaminating adaptive repair-operator credit when the skeleton
  candidate replaces the default repair;
- add P/CMT4 protection by structure, not by hardcoded case id, and no-op on
  marginal or unstable skeleton rewires.

If that design cannot explain why P and CMT4 losses should be repaired, park
`route_skeleton_regret_repair` for v0.4 and clean-fork to a different
problem-owned causal path.
