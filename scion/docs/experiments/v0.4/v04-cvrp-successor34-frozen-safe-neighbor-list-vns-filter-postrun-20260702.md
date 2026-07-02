# CVRP successor34 frozen-safe neighbor-list VNS filter postrun

Date: 2026-07-02

Run root:
`/home/clawd/research/scion-experiments/v04-cvrp-successor34-frozen-safe-neighbor-list-vns-filter-server-2r-gpt55-20260701T192249Z-claw`

Runner: server-local `claw`

Model: local `gpt-5.5`

Runner commit: `fe7a1a14`

## Question

Can `frozen_safe_neighbor_list_vns_filter` preserve successor33's
customer-adjacency VNS filtering signal while removing the frozen timeout
blocker?

## Validity

- Root status: `finished`, `valid`, `complete`,
  `completed_requested_rounds=true`, `campaign_exit_status=complete`,
  `last_stop_reason=max_rounds_exhausted`, `postrun_acceptance_status=ready`.
- Campaign status: `finished`, wrapper exit `0`, no wrapper signal.
- Completion preflight and postrun acceptance succeeded.
- Live target-intent and formal hypotheses stayed on
  `frozen_safe_neighbor_list_vns_filter` in
  `policies/baseline_modules/local_search.py`.

## Result

Successor34 is valid evidence, but not promotion-grade solver evidence.

| Row | Decision | Case W/L/T | Pair W/L/T | Median delta | CI | Main reason |
|---|---|---:|---:|---:|---|---|
| 1 | `continue_explore` | `2/2/4` | not used for gate | `0.0` | `[-3.0, 0.25]` | `SCREENING_FAIL_WIN_RATE`, `SCREENING_MARGINAL_SIGNAL_CONTINUE` |
| 2 | `expand_screening` | `3/1/4` | not used for gate | `0.25` | `[0.0, 3.25]` | `SCREENING_EXPAND_LOW_SNR_TRAJECTORY_DIVERGENT` |

The best row stayed far below the current CVRP screening MDE `9.9`
(`effect_to_mde_ratio=0.025253`).

Case-level row-2 deltas:

- `A-n64-k9`: win, median `+11.5`, `4/0/0`.
- `B-n63-k10`: win, median `+5.5`, `2/1/1`.
- `E-n101-k14`: win, median `+0.5`, `2/1/1`.
- `CMT2`: loss, median `-11.0`, `1/3/0`.
- `CMT4`: tie, median `0.0`, `0/0/4`.
- `M-n200-k17`: tie, median `0.0`, `0/0/4`.
- `P-n65-k10`: mixed, median `+1.0`, `2/2/0`.
- `X-n110-k13`: mostly tie, median `0.0`, `1/0/3`.

## Candidate Reading

The retained candidate added neighbor lists, filtered existing cross-route VNS
operators, and bounded each filtered operator with a checked-candidate cap. It
emitted phase runtime and move telemetry under
`frozen_safe_neighbor_list_vns_filter`, so this is not missing activation or a
model-call failure.

The repair did remove successor33's frozen timeout blocker, but it also lost
most of successor33's validation signal. The remaining gains are low-SNR and
case-fragile, with CMT2 still negative across three of four seeds.

## Decision

Park unchanged `frozen_safe_neighbor_list_vns_filter` for v0.4. Treat it as
reviewed weak-positive below MDE:

- not zero-effect, because A/B/E show objective movement;
- not promotion-grade, because the aggregate effect is tiny versus MDE;
- not a good immediate same-mechanism follow-up, because CMT2 remains a stable
  negative protected case.

The next CVRP slot should be a non-seed clean fork with a different causal
path: `capacity_tightness_removal` in
`policies/baseline_modules/destroy_repair.py`.
