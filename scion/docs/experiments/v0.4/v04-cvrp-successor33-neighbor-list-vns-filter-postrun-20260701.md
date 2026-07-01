# CVRP successor33 neighbor-list VNS filter postrun

Date: 2026-07-01

Run root:
`/home/clawd/research/scion-experiments/v04-cvrp-successor33-neighbor-list-vns-filter-server-2r-gpt55-20260701T160210Z-claw`

Runner: server-local `claw`

Model: local `gpt-5.5`

Runner commit: `b579797d`

## Question

Can `neighbor_list_vns_filter` improve CVRP `total_distance` by filtering or
ordering candidate enumeration inside existing VNS neighborhoods, while keeping
move families, acceptance policy, destroy/repair policy, construction seeds,
scheduler q policy, operator credit, embedded-VNS runtime allocation, and
generic core unchanged?

## Validity

- Root `run_status.json`: `run_validity_status=valid`,
  `run_completeness_status=complete`, `completed_requested_rounds=true`,
  `campaign_exit_status=complete`, `last_stop_reason=max_rounds_exhausted`,
  `postrun_acceptance_status=ready`.
- Campaign status: `effective_rounds_completed=2`,
  `formal_screened_candidates=2`, `protocol_evaluated_candidates=4`,
  `proposal_attempts_total=3`, `proposal_quality_blocks=0`.
- Completion preflight was healthy with local `gpt-5.5`, HTTP 200, and
  authenticated chat completion.
- Postrun acceptance passed; current-run analysis and delegation artifacts are
  ready.

## Mechanism binding

Both live target-intent and formal hypothesis traces stayed on:

- `change_locus=solver_design`
- `target_file=policies/baseline_modules/local_search.py`
- `mechanism_id=neighbor_list_vns_filter`
- `mechanism_family=bounded_local_search_variant`

The first candidate used a nearest-route/customer filter over existing
relocate, swap, Or-opt, and two-opt-star neighborhoods. The second candidate
kept the same mechanism id but changed to customer-adjacency filtering. This
was a same-mechanism repair inside existing VNS neighborhoods, not a new move
family or a scheduler/destroy-repair/seed/acceptance change.

Only `policies/baseline_modules/local_search.py` differed in the successful
second candidate archive. The candidate file grew to 443 lines from the current
313-line baseline, so any production follow-up should split neighbor-list
policy into a coherent problem-owned module instead of adding more helper
growth to `local_search.py`.

## Objective results

| Candidate | Stage | Decision | Pair result | Case result | Median delta | CI | Failures |
|---|---|---|---|---|---:|---|---|
| nearest-route/customer filter | screening | abandon | 9 wins / 16 losses / 7 ties | 1 win / 5 losses / 2 ties | `-2.0` | `[-14.5, 3.0]` | 0 |
| customer-adjacency filter | screening | queue_validate | 20 wins / 6 losses / 6 ties | 6 wins / 0 losses / 2 ties | `6.25` | `[1.5, 18.5]` | 0 |
| customer-adjacency filter | validation | queue_frozen | 24 wins / 7 losses / 1 tie | not summarized in row | `7.75` | `[0.75, 96.5]` | 0 |
| customer-adjacency filter | frozen | abandon | 9 wins / 12 losses / 3 ties | not summarized in row | `20.5` | `[-19.0, 113.0]` | 6 candidate timeouts |

Use the protocol row medians above for decision interpretation. Raw pair-count
medians differ in the frozen row because six candidate-side timeouts are
counted as runtime failures and losses by the campaign decision path.

## Screening and validation signal

The second candidate produced the first strong CVRP solver signal in the recent
v0.4 sequence:

- screening passed with `20/6/6` pair W/L/T and no case-level losses;
- validation passed with `24/7/1` pair W/L/T and no failed pairs;
- validation runtime was not a regression: `runtime_ratio_median=0.9831`,
  `runtime_delta_median_ms=-513.5`, `runtime_regression_rate=0.1875`.

Mechanism telemetry was active and effect-bearing in all screening pairs:

- `neighbor_list_vns_filter` activation/status observed in `32/32`;
- `neighbor_list_vns_filter_iterations` present and positive in `32/32`;
- phase runtime positive in `32/32`;
- improvement counts and best-delta fields positive in `32/32`.

The mechanism is therefore not inactive, missing telemetry, or merely
runtime-moving. It showed real screening and validation objective effect.

## Frozen blocker

Frozen failed because the candidate side timed out on large X cases:

| Case | Seed | Candidate status | Exit code | Elapsed ms | Time limit | Runtime ratio | Delta |
|---|---:|---|---:|---:|---:|---:|---:|
| `X-n401-k29` | 61 | timeout | -9 | 105223 | 90 | 1.4244 | -1.0 |
| `X-n573-k30` | 61 | timeout | -9 | 135179 | 120 | 1.1192 | -1.0 |
| `X-n573-k30` | 67 | timeout | -9 | 135180 | 120 | 1.0152 | -1.0 |
| `X-n641-k35` | 61 | timeout | -9 | 135094 | 120 | 1.0970 | -1.0 |
| `X-n1001-k43` | 61 | timeout | -9 | 135165 | 120 | 1.0307 | -1.0 |
| `X-n1001-k43` | 89 | timeout | -9 | 135121 | 120 | 1.0044 | -1.0 |

Frozen case behavior was mixed:

- `X-n327-k20` won all three seeds with median `+41`.
- `X-n641-k35` won two seeds but timed out on seed 61, median `+221`.
- `X-n401-k29` won two seeds but timed out on seed 61, median `+99`.
- `X-n251-k28` lost all three seeds, median `-106`.
- `X-n573-k30` lost all three seeds, with two timeouts and one objective loss.
- `X-n139-k10` lost two seeds and tied one, median `-2`.
- `X-n1001-k43` had one win and two candidate timeouts.

The frozen decision reason was `CANDIDATE_RUNTIME_FAILURE`. Champion promotion
remained `no_promotion_signal_observed` despite one frozen protocol median
above MDE because the final frozen row had failed pairs and loss-heavy large
case behavior.

## Interpretation

Do not park the entire neighbor-list VNS direction as zero-effect or
default-avoid. The second candidate produced a real positive signal through
screening and validation, with active mechanism telemetry and no model,
proposal, or postrun failure.

Do not rerun the same implementation unchanged either. The frozen layer proved
that the candidate is not large-instance safe. The next useful experiment is a
design-first same-family repair: preserve the customer-adjacency filtering
signal while adding strict large-instance deadline guards, fallback limits, and
module boundaries.

Successor33 is therefore `validation-positive but frozen-unsafe`, not a v0.4
closeout result. It is strong enough to justify a successor34 repair, but not
strong enough for promotion or v0.4 closure.

## Next design boundary

Successor34 should target `frozen_safe_neighbor_list_vns_filter`:

- same bounded-local-search family and existing VNS neighborhoods;
- customer-adjacency filter preserved as the starting causal path;
- no new move family, destroy/repair policy, construction seed policy,
  scheduler q policy, acceptance policy, operator credit, or runtime allocation;
- explicit large-instance guards for X-scale cases without hardcoding case ids,
  BKS values, seeds, or split membership;
- deadline/remaining-time checks before and inside filtered VNS scans;
- bounded fallback to broader search only while enough budget remains;
- direct telemetry for skipped/guarded/fallback behavior and objective effect;
- prefer a coherent problem-owned neighbor-filter module over adding more
  helpers to `local_search.py`.

