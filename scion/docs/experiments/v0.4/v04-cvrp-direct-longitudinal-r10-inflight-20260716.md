# CVRP Direct Longitudinal R10 Inflight

## Launch Identity

- root:
  `/home/clawd/research/scion-experiments/v04-cvrp-direct-longitudinal-r10-8r-gpt56sol-20260716T063211Z-claw`;
- clean detached runtime:
  `/home/clawd/research/or-autoresearch-agent-v04-direct-runtime-c936cde4`;
- exact pushed code commit:
  `c936cde41d746c9cbfcd308bae84ba54d85c7f4a`;
- model/runtime: `gpt-5.6-sol / direct_v3`;
- requested rounds: `8`;
- scientific solver subprocess fallback: `30s`;
- no resume, force controls, retry, semantic budget, or truncation;
- completion preflight: authenticated, HTTP `200`, nonempty response;
- wrapper PID: `2848393`.

R10 is a fresh end-to-end wrapper/readiness acceptance and a longer
longitudinal adaptation trajectory. It is not needed to establish that the
agent can make substantive algorithm changes; R9 already did that.

## H1/C1 Terminal

H1 targeted `policies/baseline_modules/destroy_repair.py` and added a bounded
route-pair ejection-chain repair, with scheduler registration and deadline
propagation in `scheduler.py`. H1 and C1 each used one successful provider
attempt; there was no retry or replacement. The candidate was verified at
hash `cd8f6bb6...` and completed all `32/32` formal pairs with zero candidate
or champion failure.

The formal result was strongly negative:

- pair outcome: `1W / 21L / 10T`;
- case outcome: `0W / 5L / 3T`;
- case median: `-14.25`;
- case CI: `[-48.75, 0]`;
- case win rate: `0`;
- candidate/champion ALNS iterations: `69 / 1665`;
- ejection-chain attempts/accepted: `30 / 0`;
- Protocol: `fail / SCREENING_FAIL_WIN_RATE`;
- Decision: `continue_explore`, transaction committed.

The implementation was substantive and genuinely activated, but its algorithm
was defective. A depth-two, branch-32 recursive search was executed for every
pending customer, while the branch limit applied only after full enumeration
and sorting. When the deadline reserve was reached, the implementation created
one singleton route per remaining customer instead of using the promised
regret-3 fallback. Observed ejection activations consumed roughly `21–23s` in
one ALNS iteration and ended at `route_limit`. Static review found no customer
uniqueness, capacity, rollback, or trial-delta P0; this is a search-complexity
and fallback-policy P1 in the candidate algorithm, not a Scion gate failure.

The repaired formal-artifact path is accepted live:

- schema: `scion.formal_candidate_patch_artifact.v3`;
- `base_workspace_ref=champions/champion_v1`, campaign-relative and non-opaque;
- replay identity: `complete`, not degraded;
- base identity: `06820ec...`;
- formal current/replay/verified/executable identity: `cd8f6b...`;
- candidate staging and promotion journals: empty after Decision completion.

## H2/C2 In Flight

H2 directly cites H1's `30/30` route-limit activations and the `1665 -> 69`
throughput collapse. It changed direction to
`policies/baseline_modules/local_search.py`, proposing candidate-list-driven
incremental inter-route VNS plus bounded 2-for-1/1-for-2 CROSS exchange. H2 and
C2 again each used one successful provider attempt, with no retry. Verification
committed current/last-clean/verified/executable identity `65f379...` over H1
base `cd8f6b...`; formal evaluation is pending.

The main audit question is whether H2 fixes the causal bottleneck or merely
adds a faster local-search mechanism while retaining H1's expensive ejection
repair in the cumulative candidate. Do not infer recovery from the hypothesis
text alone; require runtime activation, throughput, objective, Protocol, and
Decision evidence.

## Monitoring Rules

- poll no more frequently than about three minutes;
- do not signal, mutate, resume, or start another generative root;
- distinguish requested observation count `8` from retries or semantic
  budgets;
- audit each terminal round before attributing a causal improvement;
- require fresh-root wrapper/postrun readiness at campaign terminal state.
