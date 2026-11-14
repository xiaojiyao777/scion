# CVRP Direct Longitudinal R10 Terminal Analysis

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
- wrapper PID: `2848393` (terminal).

R10 completed all `8/8` requested typed experiments at
`2026-07-16T10:31:55Z`. Wrapper, campaign, postrun rebuild, and readiness all
exited zero. The campaign is `valid / complete / requested_rounds_completed`;
`current_run_analysis_ready=true`, `delegation_ready=true`, and the failure
report is empty. R10 is a fresh end-to-end wrapper/readiness acceptance and a
longer longitudinal adaptation trajectory. It is not needed to establish that
the agent can make substantive algorithm changes; R9 already did that.

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

## H3/C3 Screening and Validation Pass, Frozen Failure

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
returned `SCREENING_PASS`; Decision `queue_validate` committed. Fresh
validation completed `32/32` valid with zero failures, case `7/0/1`, pair
`26/4/2`, median `+37.75`, and CI `[6,199]`. Protocol returned
`VALIDATION_PASS_HIERARCHICAL`; Decision `queue_frozen` committed. Both
screening formal v3 artifacts use
`base_workspace_ref=champions/champion_v1`, complete identity, the same patch
digest, and a clean Branch.

Frozen evaluation completed its fresh target at `24/24` valid with zero
candidate, champion, or fleet failures. The result reversed the earlier
signal: case `4/4/0`, pair `11/13/0`, median `-19.5`, CI `[-350,98]`, and
hierarchical status `uncertain`. Protocol returned
`FROZEN_FAIL_HIERARCHICAL_UNCERTAIN`; Decision `abandon` committed and the
workspace was archived. This is real split instability, not a framework,
runtime, or evidence-integrity failure. Champion remains v1.

Mechanism evidence supports the causal removal: ejection attempts are zero and
initial-screening ALNS recovered to `1010/1665`. It does not support the new
cost-aware weighting claim. `SEGMENT_LENGTH=100`, while per-solve ALNS stayed
below 100, so weights were never updated and then reused in the same solve.
The mechanism also lacks runtime-density/weight telemetry, and configured
`SIGMA_ACCEPTED=13` exceeds `SIGMA_BETTER=9`. Treat the screening recovery as
ejection removal plus search-trajectory change; the cost-aware claim remains
unsupported even though validation quality was positive. Frozen throughput
also collapsed to only `52` aggregate ALNS iterations across 24 pairs; initial
VNS dominated the large-instance runtime.

## H4/C4 Screening Pass and Validation Classification Defect

After H3 was abandoned, Scheduler opened a fresh branch from champion v1. H4
targeted `policies/baseline_modules/local_search.py` and added a capacity-safe
granular CROSS exchange of contiguous segments of length one through three.
H4/C4 again used one provider attempt each, with no retry, and verified at hash
`454b6ab2...` over champion base `06820ecd...`.

Screening completed `32/32` valid with zero failures:

- case `6/1/1` and pair `21/7/4`;
- median `+3.75`, CI `[0,7.5]`;
- candidate/champion ALNS iterations `1226/1665`;
- Protocol `SCREENING_PASS`, Decision `queue_validate`.

Validation then completed `32/32` valid with zero failures and returned case
`4/0/4`, pair `20/5/7`, median `+11.75`, CI `[0,79.75]`. The case-level win
rate is `0.5`, below the preregistered `0.66`, so this evidence cannot pass
directly. It is nevertheless no-loss, nonnegative hierarchical uncertainty,
and the formal protocol already preregisters one validation expansion from
eight to twelve cases. The current gate incorrectly mapped every low-win-rate
hierarchical uncertain result to `VALIDATION_FAIL_NO_HIERARCHICAL_GAIN`, so
Decision abandoned H4 instead of using the existing one-time expansion.

The repair keeps the original case-level threshold and does not use pair-level
evidence to pass. It permits only an initial hierarchical-uncertain result with
zero case losses, at least one win, and enough remaining preregistered cases to
mathematically reach the original threshold to return the existing
`VALIDATION_EXPAND_HIERARCHICAL_UNCERTAIN`. An expanded result cannot use this
exception again. No gate, retry, budget, or reason code is added.

## Cross-Branch Research-Continuity Defect

R10 also exposes a direct context defect. H2 and H3 received respectively one
and two complete current-branch canonical screening records. After H3's branch
was abandoned, H4's new-branch Hypothesis trace had
`experiment_history=[]`, although the old branch durably owned four screening
records: H1, H2, H3 initial, and H3 expansion. H4 therefore did not see that H2
had already attempted candidate-list VNS plus CROSS and proposed another CROSS
family mechanism.

The cause is a branch-id filter applied after screening-only filtering in the
direct ContextManager. The repair projects the complete canonical screening
history from every branch in the same campaign, including terminal branches
after reopen. Each context-only record carries only `source_branch_id` and
`relation=current|sibling`. It does not expose terminal state, direction,
failure prose, validation/frozen rows, raw metric refs, or patch bodies. It
does not create a failed-hypothesis ledger, summary substitution, top-N,
budget, compression, or truncation.

## Repair Acceptance

Both R10-derived repairs are implemented and independently reviewed. The
context path now reads all campaign branches in stable order, merges durable
and live canonical screening evidence, and fails closed on duplicate ownership,
reserved provenance keys, unknown live owners under a complete campaign scope,
or malformed terminal evidence during reopen. The validation exception is
limited to the first no-loss hierarchical uncertainty whose preregistered
expansion can still reach the unchanged case win-rate threshold; expanded,
negative, tied, lossy, and unreachable evidence is not relaxed.

Focused affected tests pass `168`; the correctly rooted full Scion suite passes
`2053` with one existing skip in `465.36s`. Compileall and `git diff --check`
pass. No retry, semantic budget, truncation, top-N, compression, summary
substitution, blacklist, reason code, or new gate was introduced.

## Terminal Integrity

- eight evaluated experiments: five screening, two validation, one frozen;
- four H calls and four C calls, all successful, with no retry or replacement;
- all candidate/champion comparison rows valid and no solver failure;
- five formal v3 candidate artifacts pass apply-check and materialization;
- all artifacts use campaign-relative `champions/champion_v1` with complete
  replay identity;
- six Decision completion intents are committed;
- both research branches are abandoned, active slots are zero, and candidate
  staging, workspaces, and promotion journals are empty;
- champion v1 hash `06820ecd...` is unchanged and no promotion dossier exists;
- `formal_ready=false` only denotes normal completion without promoted final
  evidence; research-conclusion eligibility and current-run analysis are true.

## Next Experiment

Do not resume or mutate R10. The two framework repairs pass focused and
full-suite verification; launch a distinct fresh eight-round root from their
exact clean pushed commit. Do not force a surface, action, target, or algorithm
hypothesis. Keep `gpt-5.6-sol / direct_v3`, the single active branch, the
30-second scientific solver subprocess fallback, completion preflight, and
strict postrun/readiness. Add no retry, semantic budget, truncation, blacklist,
or telemetry gate.

The strongest next algorithm lead is elapsed-time simulated-annealing cooling:
H4 screening/validation averaged only `38.3/24.4` ALNS iterations per pair,
while the scheduler's temperature horizon assumes at least roughly `1200` per
solve. Annealing accepted about half of observed H4 iterations and embedded VNS
consumed most phase runtime. This lead is audit guidance only; the open control
must choose its own target. If a second branch is created, verify that its H
receives prior sibling screening records without hidden-stage leakage or
duplicate provider calls.
