# CVRP successor51 bounded route-arc LNS rebuild postrun - 2026-07-09

## Scope

Run root:
`/home/clawd/research/scion-experiments/v04-cvrp-successor51-repaired-slot-cleanfork-server-claw-2r-gpt55-2r-gpt55-20260708T135236Z-claw`

Successor51 was launched from committed repair `7dfbd1b0` after successor50
closed scheduler-level material-difference contract repair as an invalid
solver slot. The run used the server-local `claw` environment, local
`gpt-5.5`, `--rounds 2`, `--completion-preflight`, full proposal context,
`--force-surface solver_design`, and no forced target mechanism or file.

## Run Status

- Wrapper status: finished, exit status `0`.
- Campaign status: complete; requested rounds `2`, effective rounds `2`.
- Postrun acceptance: ready.
- Stop reason: `max_rounds_exhausted`.
- Model calls: six successful `gpt-5.5` calls.
- Request kinds: two `hypothesis_target_intent`, two `hypothesis`, one
  `tool_selection`, one `code`.
- Proposal attempts: three total, with one proposal-quality block.
- Candidate intents: two algorithm-quality candidates and one repair/infra
  attempt.

The run is valid experiment evidence. It is not a model outage, completion
preflight, verification, or postrun-acceptance failure.

## LLM Call Audit

1. The first target-intent call selected `bounded_edge_path_relinking` as a
   new `policies/baseline_modules/edge_path_relinking.py` mechanism.
2. The first formal hypothesis for that mechanism was blocked before code
   generation by `cvrp_solver_design_causal_path_contract`: it missed
   `branch_lesson_usage.clean_fork_diversity_claim` and
   `algorithmic_intervention_sufficiency`.
3. The second target-intent call selected `bounded_route_arc_lns_rebuild` as a
   new `policies/baseline_modules/route_arc_lns.py` mechanism.
4. The second formal hypothesis passed the contract with explicit
   `material_difference`, CMT2/CMT4 branch-lesson usage, and final-objective
   telemetry intent.
5. Tool selection returned `stop`; no external tool was requested.
6. The code call created `route_arc_lns.py` and wired it into
   `scheduler.py` after repair and before embedded VNS.

Prompt manifests showed no section truncation. The code prompt's visible
manifest recorded `32` full sections, `10` summaries, `7` dedicated
projections, `5` omitted sections, and `0` truncated sections. Required source
dependencies for `destroy_repair.py`, `local_search.py`, and `scheduler.py`
were fully visible; `route_arc_lns.py` was a new-file placeholder. Prepared
research obligations and active subject code constraints were included. This
does not look like context starvation.

## Candidate Audit

The accepted patch was a real solver mechanism, not a hook wrapper:

- new file: `policies/baseline_modules/route_arc_lns.py`;
- wiring: `scheduler.py` imports `_bounded_route_arc_lns_rebuild` and calls it
  after repair, before embedded VNS and acceptance;
- mechanism: rank high-cost directed route arcs, select nearby customers,
  remove at most a bounded neighborhood, repair with regret-style insertion
  into existing routes, and accept only feasible strict total-distance
  improvement;
- telemetry: records `bounded_route_arc_lns_rebuild` iterations, move attempts,
  accepted moves, delta, and phase runtime.

The implementation is structurally conservative: `_MAX_ARC_CHOICES=4`,
`_MAX_ARC_CANDIDATES_PER_ROUTE=2`, `_MAX_REMOVED=12`, no new route creation,
strict no-op on infeasible or non-improving trials, and strict route-count
guarding. This helped it pass canary/contract/verification, but limited the
chance of large final objective movement.

## Measurement Result

Measurement readiness was `ready`, with MDE at power 80 equal to `9.9`; the
readiness artifact remains proposal/report-only and excluded from
`DecisionFeatures`.

Protocol rows:

| Round | Pairs | Case W/L/T | Pair W/L/T | Median | CI | Decision |
|---|---:|---:|---:|---:|---|---|
| 2 | 48 | 5/4/3 | 22/19/7 | 0.0 | [-6.25, 5.0] | expand_screening |
| 3 | 64 | 6/4/6 | 30/25/9 | 1.0 | [-1.0, 5.0] | continue_explore |

Postrun effect-vs-MDE summary:

- max median delta: `1.0`;
- max effect-to-MDE ratio: `0.10101`;
- rows at or above MDE: `0`;
- rows with CI high below MDE: `2`;
- interpretation: `all_available_ci_high_below_mde`;
- champion promotions: `0`.

## Case Pattern

The expanded row has real positive pockets:

- `A-n64-k9`: W/L/T `4/0/0`, median `+29.0`.
- `E-n101-k8`: `3/1/0`, median `+5.0`.
- `M-n151-k12`: `3/1/0`, median `+6.5`.
- `X-n110-k13`: `2/2/0`, median `+56.5`.

The protected and loss-prone cases block continuation:

- `CMT2`: `1/2/1`, median `-8.0`.
- `CMT4`: `1/3/0`, median `-33.5`.
- `B-n67-k10`: `0/4/0`, median `-5.5`.
- `P-n101-k4`: `1/3/0`, median `-7.0`.

Fleet violation medians remained `0.0` in these case summaries, so this is not
a feasibility collapse. It is final total-distance degradation on protected
and structured instances.

## Telemetry Interpretation

Mechanism activation was strong:

- round 2 observed nonzero `bounded_route_arc_lns_rebuild` phase runtime in
  `48/48` candidate pairs;
- round 3 observed nonzero phase runtime in `64/64` candidate pairs;
- round 3 phase weighted runtime was `34970 ms`;
- local mechanism effect was marked positive, with accepted moves and positive
  phase deltas present in almost all pairs.

The failure mode is therefore not inactive mechanism suppression. The gap is
attribution: local route-arc LNS deltas did not preserve enough final
candidate-vs-champion total-distance advantage after downstream VNS and
acceptance, and the protected CMT cases were objective-negative.

## Decision

Treat successor51 as valid, active, below-MDE, and protected-case unsafe.

Do not:

- run a long experiment on unchanged `bounded_route_arc_lns_rebuild`;
- tune thresholds such as max removed, max arc choices, or acceptance guard as
  a same-mechanism optimization slot;
- count phase-local positive telemetry as final solver effect;
- treat the `continue_explore` lifecycle row as promotion-grade evidence.

The successor50 repair itself is upheld: the first weak hypothesis was blocked
before code generation, `counts_toward_max_rounds=false`, and the retry
produced a genuine solver mechanism rather than another contract/hook repair.

## Next TASK Implication

Record `bounded_route_arc_lns_rebuild` as reviewed/default-avoid for unchanged
same-line follow-up. The next CVRP solver slot should be a materially
different CVRP-owned clean fork, with:

- exact `material_difference.changed_dimensions`, `contrast`, and `evidence`;
- `branch_lesson_usage.clean_fork_diversity_claim` with explicit CMT2/CMT4
  entries;
- final or post-downstream total-distance attribution, not only phase-local
  delta;
- CMT2/CMT4 priority-case coverage retained;
- no scheduler-level metadata gate, hook wrapper, config-only activation, or
  telemetry-only wrapper.

A short same-mechanism diagnostic would only be justified if the explicit goal
is to explain why phase-positive route-arc LNS deltas do not translate into
final best-solution advantage on CMT2/CMT4. It should not be treated as an
optimization or long-run candidate.
