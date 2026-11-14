# CVRP Successor27 Route-Pair Overlap Postrun - 2026-07-01

## Status

Successor27 produced valid weak-positive solver evidence, but not promotion
evidence.

- Run root:
  `/home/clawd/research/scion-experiments/v04-cvrp-successor27-non-seed-clean-fork-server-2r-gpt55-20260630T151408Z-claw`
- Runner: server-local `claw`
- Model: local `gpt-5.5`
- Wrapper status: `finished`
- Wrapper exit status: `0`
- Run completeness: `complete`
- Run validity: `valid`
- Stop reason: `max_rounds_exhausted`
- Effective protocol rounds: `2`
- Protocol metric results: `2`
- Screening protocol results: `2`
- Proposal attempts total: `2`
- Proposal quality blocks: `0`
- Verification consumed candidates: `2`
- Postrun readiness: ready

The run is not an infrastructure, model, proposal-quality, telemetry, or
postrun-readiness failure. The campaign made four LLM calls, all to local
`gpt-5.5`: `hypothesis_target_intent`, `hypothesis`, `tool_selection`, and
`code`.

## Mechanism

The agent selected `route_pair_overlap_removal`, a destroy/repair mechanism
owned by `policies/baseline_modules/destroy_repair.py` with scheduler
registration/telemetry. The operator scores pairs of existing routes by
geographic overlap, removes a bounded set of interleaved or boundary customers,
and relies on existing repair to reinsert them.

This is materially different from the parked construction seed, scheduler
destroy-size, insertion-cost lookahead, and reviewed destroy/repair paths. It is
also not a seed selector.

## Result Summary

- Research-efficiency interpretation:
  `protocol_effects_below_mde_or_inconclusive`
- MDE at 80% power: `9.9`
- Protocol rows: `2`
- Positive rows: `2`
- Rows at or above MDE: `0`
- Max median delta: `2.5`
- Max effect/MDE ratio: `0.252525`
- Champion promotions: `0`
- Decisions: `expand_screening`, then `continue_explore`

Row 1, `route_pair_overlap_removal`:

- Median delta: `0.75`
- CI: `[-4.5, 12.5]`
- Effect/MDE ratio: `0.075758`
- Win rate: `0.5`
- Key case medians: `A-n64=14.5`, `B-n63=4.0`, `CMT2=-3.0`,
  `CMT4=-10.0`, `E-n101-k14=1.5`, `M-n200=0.0`, `P-n65=-4.5`,
  `X-n110=12.5`

Row 2, expanded `route_pair_overlap_removal`:

- Median delta: `2.5`
- CI: `[-7.75, 7.0]`
- Effect/MDE ratio: `0.252525`
- Win rate: `0.5`
- Key positive case medians: `A-n64=14.5`, `A-n80=10.0`, `B-n63=4.0`,
  `CMT3=6.0`, `E-n101-k14=1.5`, `E-n101-k8=3.5`, `X-n110=12.5`
- Key negative case medians: `B-n67=-8.0`, `CMT4=-16.0`,
  `P-n101=-14.0`, `P-n65=-4.5`, `P-n76=-7.5`

## Interpretation

The correct next action is a CMT2/CMT4/P-protected same-mechanism follow-up.

Do not expand unchanged `route_pair_overlap_removal`: the expanded row stayed
well below MDE and retained a negative CI lower bound. Another unchanged
expansion would mostly spend budget confirming low-SNR marginal evidence.

Do not immediately discard the mechanism for an unrelated non-seed clean fork:
successor27 is the strongest recent CVRP solver signal. Both rows were
positive, activation and objective effect were observed, and the positive cases
are not only tiny ties.

The follow-up should keep the route-pair-overlap causal path while reducing the
loss mode:

- bound removal more conservatively;
- skip or downweight route pairs with low spare capacity, route-count risk, or
  high imbalance;
- require stronger overlap before perturbing a route pair;
- preserve route-pair selection, removed-count, and objective-effect telemetry;
- keep CMT2 and CMT4 in formal coverage when available;
- do not hardcode case ids, BKS values, seeds, or split membership.

## Follow-Up

- Update problem-owned CVRP guidance and adapter diagnostics so the top
  opportunity is `route_pair_overlap_removal_protected_followup`.
- Add `route_pair_overlap_removal` to the destroy/repair mechanism-family
  aliases so postrun review treats it as destroy/repair evidence.
- Default-reject unchanged route-pair-overlap expansion without protection.
- Launch successor28 as a two-round server-local run only after targeted
  guidance and adapter tests pass.
