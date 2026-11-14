# CVRP Direct Causal-Feedback R5 Postrun

*Terminal audit: 2026-07-15*

## Disposition

R5 is a complete, auditable research-rejected terminal root, not a two-round
algorithm experiment. The wrapper and postrun tooling completed normally, but
the first Code proposal failed Patch Contract before Workspace, Verification,
Protocol, or solver execution. R5 must not be resumed, retried, or reused.

- root:
  `/home/clawd/research/scion-experiments/v04-cvrp-direct-causal-feedback-r5-2r-gpt56sol-20260715T141236Z-claw`;
- runtime commit: clean detached `3fb2f9a7`;
- model/requested rounds/solver limit: `gpt-5.6-sol`, `2`, `30` seconds;
- wrapper exit: `0`;
- campaign completeness/validity: `incomplete` /
  `invalid_research_rejected_only`;
- last stop: `execution_research_rejected`;
- H/C/provider attempts: `1/1/2`;
- provider retry or replacement attempt: `0`;
- evaluated rounds/candidates/solver pairs: `0/0/0`;
- champion: version 1, unchanged.

The single live completion preflight was healthy: authenticated, HTTP 200, and
non-empty. Force surface/action/target were empty. The provider request policy
used provider-managed output with no output-token parameter or transport
ceiling. No Scion prompt/session/tool/file/item/token budget, truncation,
automatic retry, or scheduler/gate steering was present.

## Proposal And Failure

H1 independently selected `solver_design` and
`policies/baseline_modules/destroy_repair.py`. It proposed a substantive
route-cap-aware bounded ejection-chain repair: when direct insertion fails,
eject a resident customer, insert the pending customer, and reinsert the
resident into another route before falling back to a new route.

C1 returned a schema-valid but incomplete two-file patch:

- `destroy_repair.py` added `_route_distance` to the import and declared
  `_MAX_EJECTION_CHAIN_CHECKS = 5000`;
- `scheduler.py` imported `_ejection_chain_insertion`;
- it did not define `_ejection_chain_insertion`;
- it did not add the new operator to `repair_ops`.

Patch Contract passed 18 of 19 checks. C9e correctly rejected the candidate
because scheduler imported a symbol absent from the fully materialized
candidate `destroy_repair.py`. Host materialization was correct: C9e observed
the new constant/import and the scheduler edit, but no function export.
Verification, Protocol, Decision, and the solver were correctly skipped. This
is neither algorithm-quality evidence nor a gate artifact.

## Root-Cause Audit

Three independent read-only audits converged on the same result:

- H/C source visibility was complete and source digests matched the champion;
- C received all 11 unique active solver files, including full current
  `destroy_repair.py` (7,304 chars), `scheduler.py` (25,113 chars), and
  `state.py` (5,456 chars);
- Code input was 22,460 tokens / 95,351 provider-visible chars;
- output was a complete successful tool response: 1,508 output tokens,
  including 1,010 reasoning tokens, with no output ceiling or truncation;
- lineage and four durable transitions were complete: H started/generated and
  C started/generated, with no hidden attempt.

The immediate cause was a model coding omission. A new framework instruction
at `3fb2f9a7` materially amplified it by requiring exactly one change object per
file. This hypothesis required two non-contiguous edits in each of two files:
target import plus function definition, and scheduler import plus registration.
With one object per file, the model had to emit two large full-file rewrites or
large spanning replacements; it instead returned only the first scaffold edit
for each file.

The existing host normalizer already safely supports ordered same-file
`exact_replace` composition. The repair therefore restores that typed
expression instead of adding a retry, repair call, gate, budget, or truncation:

- provider tool, PATCH schema, and parser guidance consistently allow multiple
  ordered `exact_replace` objects for one existing path;
- each edit binds to the original visible source digest;
- host composition is deterministic and recorded as ordinary
  `typed_edit_normalization` with
  `composed_serial_exact_replace_changes`;
- wrong order and stale digest fail closed;
- create/delete/full-file mixtures fail closed;
- C9e remains unchanged.

The repair passes `115` affected tests and the full suite:
`1905 passed, 1 skipped in 495.65s`. Compileall and `git diff --check` pass;
independent final review reports P0/P1/P2=`0/0/0`.

## Context And Next Experiment

R5 ended before Protocol, so there is no round-1 causal packet and no H2. It
does not validate compact causal feedback or semantic source deduplication.

The 11-file SourceLedger remains unchanged for the next run. A separate design
audit found that a safe forward+reverse+entrypoint+conditional dependency
closure expands back to all 11 active modules. A smaller set would require a
new problem-owned mechanism whitelist and would violate the current complete
SourceLedger contract; it is not a valid implicit noise reduction.

After the serial-edit repair is committed and pushed, prepare and launch a
distinct fresh R6 root. Start with two requested formal rounds because H2 is the
first observation needed for the causal-feedback acceptance. If evaluated
results show that two rounds cannot establish longitudinal use or adaptation,
use distinct clean 4- or 8-round experiments; do not reinterpret extra rounds
as retry, a semantic budget, or permission to resume this root.

## Postrun Integrity

- postrun readiness: 28 `ok`, 3 `skipped`, no required or optional failure;
- research conclusion eligibility: `ineligible_zero_evaluated`;
- evidence and lineage status: complete, warnings empty;
- proposal trajectory: two attempts, four valid transitions, no invalid or
  unrecovered row;
- launch manifest secret check: clean; key value absent from persisted command
  and manifest;
- postrun families: analysis brief, failure report, inventory, trajectory
  manifest, summary, rebuild manifest, and readiness all present.
