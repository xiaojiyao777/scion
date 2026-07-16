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

## H2/C2 Terminal

H2 directly cites H1's `30/30` route-limit activations and the `1665 -> 69`
throughput collapse. It changed direction to
`policies/baseline_modules/local_search.py`, proposing candidate-list-driven
incremental inter-route VNS plus bounded 2-for-1/1-for-2 CROSS exchange. H2 and
C2 again each used one successful provider attempt, with no retry. Verification
committed current/last-clean/verified/executable identity `65f379...` over H1
base `cd8f6b...`.

H2 completed `32/32` valid formal pairs with zero candidate/champion/fleet
failure, but remained strongly negative:

- pair outcome: `2W / 26L / 4T`;
- case outcome: `0W / 7L / 1T`;
- case median: `-7.25`;
- case CI: `[-50.5, -2.0]`;
- candidate/champion ALNS iterations: `62 / 1665`;
- inherited ejection attempts/accepted/route-limit: `31 / 0 / 31`;
- inherited ejection runtime: `718244ms`;
- Protocol: `fail / SCREENING_FAIL_WIN_RATE`;
- Decision: `continue_explore`, transaction committed.

The code-correct CROSS/VNS path did not solve the causal bottleneck. H1's
`destroy_repair.py` and `scheduler.py` remained unchanged and active. Candidate
lists were rebuilt per VNS call and filtered only after broad route-position
enumeration; unrestricted fallback scans also repeated after later stalls.
CROSS lacked neighborhood-specific telemetry and could not be credited
independently. H2's formal artifact again uses
`base_workspace_ref=champions/champion_v1`; last-clean/current/replay/verified/
executable identity is `65f379...`, and transactional staging/journals are
empty.

## H3/C3 Screening Pass, Validation In Flight

H3 directly targets the causal failure in `scheduler.py`: remove ejection-chain
from the active repair portfolio and make repair selection cost-aware through
feasible-outcome reward density, runtime measurement, smoothed weights, and a
minimum exploration floor for greedy/regret operators. H3/C3 are single-attempt
and verified at current/last-clean/verified/executable identity `12ec5b...`
over H2 base `65f379...`.

Initial screening completed `32/32` valid with case `4/3/1`, pair `17/13/2`,
median `+1.75`, and CI `[-2.5,19.5]`. Protocol expanded the divergent,
low-signal trajectory rather than passing it immediately. The independent
expansion then completed `48/48` additional valid pairs with zero failures and
returned `SCREENING_PASS`; Decision `queue_validate` committed. Validation is
now live with a fresh 32-pair target. Both screening formal v3 artifacts use
`base_workspace_ref=champions/champion_v1`, complete identity, the same patch
digest, and a clean Branch.

Mechanism evidence supports the causal removal: ejection attempts are zero and
initial-screening ALNS recovered to `1010/1665`. It does not support the new
cost-aware weighting claim. `SEGMENT_LENGTH=100`, while per-solve ALNS stayed
below 100, so weights were never updated and then reused in the same solve.
The mechanism also lacks runtime-density/weight telemetry, and configured
`SIGMA_ACCEPTED=13` exceeds `SIGMA_BETTER=9`. Treat the screening recovery as
ejection removal plus search-trajectory change; require validation before any
promotion conclusion.

## Monitoring Rules

- poll no more frequently than about three minutes;
- do not signal, mutate, resume, or start another generative root;
- distinguish requested observation count `8` from retries or semantic
  budgets;
- audit each terminal round before attributing a causal improvement;
- require fresh-root wrapper/postrun readiness at campaign terminal state.
