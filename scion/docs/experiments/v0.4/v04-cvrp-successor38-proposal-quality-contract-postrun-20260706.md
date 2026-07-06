# CVRP successor38 proposal-quality contract postrun

Date: 2026-07-06

Run root:
`/home/clawd/research/scion-experiments/v04-cvrp-successor38-proposal-quality-contract-cleanfork-server-retry-2r-gpt55-20260705T153833Z-claw`

## Status

- Wrapper/campaign status: complete.
- Campaign validity: valid.
- Campaign completeness: complete.
- Effective rounds completed: 2 / 2.
- Protocol metric rows: 2 screening rows, 0 validation rows, 0 frozen rows.
- Postrun acceptance: summaries, failures, inventory, manifests, research
  efficiency, and analysis brief rebuilt successfully.
- Postrun readiness: ready.
- Model calls were present and normal for this run:
  `hypothesis_target_intent=2`, `hypothesis=2`, `tool_selection=1`, `code=1`.

## Proposal-quality result

The CVRP-owned causal-path hypothesis-quality contract worked as intended.
The first live hypothesis, `slack_weighted_2opt_star_exchange`, was blocked
before code generation because it missed `material_difference` and structured
`branch_lesson_usage.clean_fork_diversity_claim` evidence. The retry constraint
explicitly required direct mechanism effect telemetry and CMT2/CMT4 protection
fields.

The accepted hypothesis stayed on `policies/baseline_modules/local_search.py`
and declared `radial_2opt_star_relink`. It supplied material-difference
evidence, mechanism-specific effect telemetry paths, and structured
`clean_fork_diversity_claim.protected_cases=["CMT2", "CMT4"]`.

Conclusion: successor38 is framework-positive for proposal-control and
candidate-shape feedback.

## Solver result

The accepted candidate is solver-negative.

Row 1 screened 32 pairs:

- Pair results: 1 win, 1 loss, 30 ties.
- Delta range: min `-1.0`, max `4.0`, median `0.0`.
- Case gate: 0 wins, 0 losses, 8 ties.
- CMT2 had one `-1.0` seed loss; CMT4 was all ties.

Row 2 screened 48 pairs:

- Pair results: 1 win, 0 losses, 47 ties.
- Delta range: min `0.0`, max `4.0`, median `0.0`.
- Case gate: 0 wins, 0 losses, 12 ties.
- CMT2 had one `+4.0` seed win; CMT4 was all ties.

Postrun aggregate across both rows:

- Champion promotions: 0.
- Screening pass rate: 0.0.
- Screening case wins/losses/ties: 0 / 0 / 20.
- Screening pair wins/losses/ties: 2 / 1 / 77.
- Measurement readiness: ready, but low-power; MDE at 80% power is `9.9`,
  with effect/MDE ratio `0.202`.

## Mechanism diagnosis

The branch card called the row weak-positive because of tiny pair-level
signals, but the mechanism evidence contract said `observed_no_effect`.

Direct mechanism telemetry confirms that interpretation:

- `radial_2opt_star_relink` phase runtime was observed on all screened pairs.
- Accepted moves for `radial_2opt_star_relink`: 0 in row 1 and 0 in row 2.
- Best delta for `radial_2opt_star_relink`: 0.0 in row 1 and 0.0 in row 2.
- Mechanism effect counters: 160 candidate-present direct-effect fields, 0
  positive, 160 zero.

The small pair wins are therefore not evidence that the declared mechanism
improved the solver. Downstream ALNS/VNS phases produced measurable movement;
the declared radial relink operator did not.

## Decision

Treat successor38 as:

- proposal-control positive;
- candidate-quality/solver negative;
- reviewed/default-avoid for unchanged `radial_2opt_star_relink`;
- not eligible for long-round expansion;
- not a reason to follow the branch's weak-positive lifecycle lane.

Next CVRP work should clean-fork to a materially different problem-owned causal
path with direct accepted-move/objective-effect evidence and CMT2/CMT4
protection. The issue exposed here is not another missing proposal field; it is
that a structurally compliant local-search hypothesis still produced an
active-no-effect candidate.
