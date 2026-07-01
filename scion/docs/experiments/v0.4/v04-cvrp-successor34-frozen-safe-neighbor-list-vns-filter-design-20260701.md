# CVRP successor34 frozen-safe neighbor-list VNS filter design

Date: 2026-07-01

## Context

Successor33 completed valid/complete/postrun-ready. It was not a model,
proposal-quality, telemetry, or postrun failure.

The first candidate was negative at screening, but the second
`neighbor_list_vns_filter` candidate repaired the mechanism with
customer-adjacency filtering:

- screening: `20` wins / `6` losses / `6` ties, median delta `6.25`,
  CI `[1.5, 18.5]`;
- validation: `24` wins / `7` losses / `1` tie, median delta `7.75`,
  CI `[0.75, 96.5]`;
- mechanism activation, iteration, phase runtime, and objective-effect
  telemetry were positive in all screening pairs.

Frozen then abandoned the branch because six candidate-side large-instance
evaluations timed out. The failures were on `X-n401`, `X-n573`, `X-n641`, and
`X-n1001`, with candidate elapsed times beyond the formal time limits. Large
case quality was mixed: `X-n327`, `X-n401`, and `X-n641` had useful wins, while
`X-n139`, `X-n251`, `X-n573`, and timeout-heavy `X-n1001` blocked promotion.

Treat successor33 as validation-positive but frozen-unsafe. The next step is a
same-family safety repair, not an unchanged rerun and not a pivot away from the
mechanism before testing the frozen blocker.

## Rejected Alternatives

### A. Rerun unchanged successor33

Rejected. The frozen failures are deterministic enough to require design
change: six candidate-side timeouts on large X cases and loss-heavy
`X-n251/X-n573` behavior. A rerun would spend budget on a known promotion
blocker.

### B. Park neighbor-list VNS filter entirely

Rejected for now. Screening and validation produced the strongest CVRP
solver-positive evidence in the recent v0.4 sequence. The right interpretation
is not zero-effect; it is frozen-unsafe.

### C. Switch to a new local-search move family

Rejected for successor34. Successor33's positive signal came from filtering
existing neighborhoods, not from adding a move. A new move family would lose
the causal link to the validation-positive candidate and increase the chance of
another broad helper-heavy `local_search.py` patch.

## Recommended Direction

Mechanism id:
`frozen_safe_neighbor_list_vns_filter`

Mechanism family:
`bounded_local_search_variant`

Owner files:

- primary integration: `policies/baseline_modules/local_search.py`;
- preferred module boundary if multi-file edits are allowed:
  `policies/baseline_modules/local_search_neighbor_filter.py`;
- optional constants only if needed: `policies/baseline_modules/config.py`.

The mechanism should preserve the successor33 customer-adjacency candidate
filter for existing relocate, swap, Or-opt, two-opt intra, and two-opt-star
neighborhoods, but make it frozen-safe:

- derive a monotonic deadline or remaining-time guard from the solver context;
- check remaining budget before route-pair, customer-pair, and fallback scans;
- cap neighbor list size, fallback breadth, and accepted-improvement loops by
  instance size and remaining budget;
- use broad fallback only when enough budget remains, not after every failed
  filtered pass;
- skip expensive fallback scans on very large instances when the remaining
  budget is below a conservative threshold;
- keep all moves feasibility-preserving and improvement-only;
- avoid case ids, seeds, split names, BKS values, or frozen-case literals.

## Module Boundary

Do not keep growing `local_search.py` with ad hoc helper functions. The
successor33 second candidate grew that file from 313 to 443 lines. Successor34
should prefer a small problem-owned module for neighbor-filter policy if the
agent can add files:

- build customer-neighbor lists;
- answer whether a route insertion/swap/two-opt-star endpoint is eligible;
- expose a simple budget-aware fallback decision;
- return telemetry counters for filtered, fallback, skipped, and accepted
  attempts.

`local_search.py` should remain the operator integration layer. It should call
the neighbor-filter module at candidate enumeration points and record existing
context telemetry. This keeps the feature as a coherent module instead of
helper sprawl.

If the launcher forces a single file, the formal hypothesis must state why and
keep the change narrow enough to audit. A long local helper block should be a
quality concern for postrun interpretation even if the candidate compiles.

## Required Telemetry

Record under `frozen_safe_neighbor_list_vns_filter`:

- `record_iteration` for filtered VNS passes;
- `record_phase` for filtered VNS runtime;
- `record_move` with attempted, accepted, delta, and best-improved status;
- neighbor filter counters: filtered candidates, fallback candidates, skipped
  fallback scans, and budget-stop events;
- route count and feasibility through existing runtime fields;
- formal pair-level `total_distance` deltas;
- explicit frozen failure accounting if any candidate side times out.

## Acceptance Reading

The repair succeeds only if it preserves the successor33 validation signal and
removes the frozen runtime blocker.

Minimum useful evidence:

- screening and validation stay positive enough to justify frozen;
- frozen has no candidate-side timeout failures;
- frozen losses on `X-n251/X-n573` are reduced or explicitly explained by
  valid pair evidence;
- runtime regression is not hidden by budget saturation diagnostics;
- telemetry shows the guarded path ran and did not simply disable local search.

If the repair only removes timeouts by suppressing local search and the
objective effect returns to zero, park it as a safety-only/no-effect repair.

## Launch Recommendation

After updating problem-owned guidance, launch one server-local successor34 run
with:

- `--force-surface solver_design`
- `--force-action modify`
- `--force-target-file policies/baseline_modules/local_search.py`
- proposal-only target-intent binding to
  `frozen_safe_neighbor_list_vns_filter`
- no hard `required_mechanism_ids`, preserving prepared-successor arbitration

The server-local `claw` runner is acceptable for this single run. WSL remains
the high-resource path for concurrent or large batch follow-ups.

