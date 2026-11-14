# CVRP Direct Longitudinal R7 Stopped Analysis

Date: 2026-07-15

Branch: `v0.4-dev`

Runtime commit: `3dc0aee4d2b65375e1c4728e82c935bc73856c95`

Model/runtime: `gpt-5.6-sol / direct_v3`

## Scope and identity

R7 was prepared as a fresh four-round generative campaign after the shared
CVRP deadline and later-stage evidence-acquisition repairs:

- root:
  `/home/clawd/research/scion-experiments/v04-cvrp-direct-longitudinal-r7-4r-gpt56sol-20260715T232619Z-claw`;
- campaign: `<root>/campaign`;
- runtime checkout:
  `/home/clawd/research/or-autoresearch-agent-v04-direct-runtime-3dc0aee4`;
- requested rounds: `4`;
- no resume source, force control, automatic retry, or semantic budget;
- launcher fallback solver limit: `30s`, with formal per-case overrides;
- data identity: 81 files, digest
  `ca7e470ec8d1f3569a690d10df5a170c4994108c71fecf5aa1a7a76b42630743`.

Completion preflight authenticated successfully, returned HTTP 200 with
non-empty content, and resolved the requested model. The wrapper launched
once. Provider accounting before the stop was exactly one successful H call
and one successful C call with no replacement or retry.

## Round-one proposal

The hypothesis was substantive and correctly targeted the active scheduler.
It proposed replacing independent destroy and repair adaptive weights with one
weight for each destroy-repair Cartesian pair. The intended mechanism was to
learn interaction compatibility rather than crediting both marginals with the
same outcome.

The generated patch changed the main scheduler path to `pair_weights` and
`pair_idx`, but its indentation-sensitive `replace_all` edit reached only the
deeply indented `destroy_empty` branch. Three sibling rejection paths retained
the deleted names `destroy_weights`, `repair_weights`, `d_idx`, and `r_idx`:

- `repair_error`;
- `infeasible`;
- `route_limit`.

When one of those paths executed, the active solver raised
`NameError: name 'destroy_weights' is not defined` and emitted the fixed
nearest-neighbor fallback. This is a candidate patch-completeness defect, not
a `_DeadlineContext`, proxy, runner, or infrastructure failure.

## Formal screening evidence

The screening matrix completed before the later persistence exception:

- attempted pairs: `32/32`;
- valid objective pairs: `22`;
- candidate failures: `10`;
- champion failures: `0`;
- pair feedback W/L/T, including candidate failures as Protocol-defined
  synthetic losses: `10/17/5`;
- valid-only pair W/L/T: `10/7/5`;
- case-level gate W/L/T: `0/4/4`;
- median/CI: `+1 / [-0.5,3]`;
- Protocol: `fail / SCREENING_FAIL_WIN_RATE`;
- Decision: `abandon / CANDIDATE_RUNTIME_FAILURE`;
- champion v1 unchanged; no promotion.

Failures were concentrated on A-n64-k9 (`1/4`), B-n63-k10 (`2/4`), CMT2
(`4/4`), and P-n65-k10 (`3/4`). The other cases completed without candidate
runtime failure. On valid rows the pair-weight mechanism was mixed: the
available `10/7/5` result is useful diagnostic evidence, but the selectively
missing rows make it ineligible for promotion or a clean algorithm-quality
claim.

The repaired common deadline held. Formal limits resolved to 30 or 45 seconds;
there were no champion timeout or watchdog failures. Candidate algorithm stop
reasons were 22 `time_limit` and 10 `exception`, with the latter caused by the
stale names above. This does not reproduce the R6 frozen shared-deadline defect.

## Terminal orchestration failure

After screening and the correct abandon decision, Scion failed while
persisting the canonical screening record:

```text
ValueError: screening valid-pair count conflicts with pair feedback
```

Protocol intentionally uses two related counts:

- `valid_pairs` counts only pairs with valid objective comparisons;
- candidate-only failures count in `candidate_failed_pairs` and are retained
  as synthetic loss rows in screening `pair_feedback`.

Champion/shared/missing-output invalid rows do not enter `pair_feedback`.
Therefore the correct projection invariant is:

```text
len(pair_feedback) == valid_pairs + candidate_failed_pairs
```

R7 was internally consistent at `32 == 22 + 10`. The canonical context layer
incorrectly required `32 == 22`, raised after the scientific result existed,
and prevented the campaign loop from recording an effective completed round
or starting round two.

The wrapper exited `1`; postrun reporting rebuilt successfully but readiness
failed only on the non-zero wrapper status. The postrun inventory classifies
the root as `valid_but_incomplete`, with one screened experiment and zero
effective rounds. The root is terminal and read-only. It must not be resumed,
retried, or represented as a four-round campaign result.

## Repairs before R8

Two narrow repairs are required and implemented in the source worktree:

1. A stdlib `symtable`-based `V1b_undefined_names` check runs after syntax and
   before interface verification over the complete primary and additional
   candidate modules. Replaying the R7 scheduler rejects exactly `d_idx`,
   `destroy_weights`, `r_idx`, and `repair_weights`. It neither executes the
   candidate nor adds solver work, retry, or a semantic budget.
2. Canonical screening projection now validates
   `valid_pairs + candidate_failed_pairs == len(pair_feedback)` while retaining
   the exact W/L/T reconciliation. Tests preserve the existing distinction:
   candidate-only failures enter feedback as losses; champion/shared and
   missing-output rows do not.

R8 must be a distinct fresh four-round root from the exact clean pushed repair
commit. It must not resume or copy R7 campaign state. Expansion to eight rounds
remains conditional on the terminal four-round evidence, not an automatic
retry or stop rule.
