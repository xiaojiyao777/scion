# CVRP Direct Causal-Feedback R6 Postrun

*Terminal audit: 2026-07-15*

## Disposition

R6 is a complete and valid two-round screening campaign. It demonstrates that
the direct V3 loop can make two substantive cumulative algorithm changes and
that H2 can use lossless R1 objective and mechanism evidence to change research
direction. Its round-2 cumulative candidate passed screening and is queued for
validation, but the effect is statistically uncertain and has a material search
allocation risk. It is not promotion evidence.

- root:
  `/home/clawd/research/scion-experiments/v04-cvrp-direct-causal-feedback-r6-2r-gpt56sol-20260715T153632Z-claw`;
- runtime commit: clean detached
  `56ba4851c92ef8e925a5d5e368d988a138c80286`;
- model/runtime/requested rounds: `gpt-5.6-sol`, `direct_v3`, `2`;
- scientific solver limit: `30` seconds per subprocess;
- elapsed lifecycle: `2026-07-15 15:37:50Z` to `16:30:24Z`;
- wrapper/campaign/postrun exit: `0/0/0`;
- completeness/validity: `complete / valid`, requested rounds complete;
- H/C/provider attempts: `2/2/4`, all successful, retry/replacement=`0`;
- formal screening pairs: `64/64` valid, failed=`0`;
- final branch: `ready_validate`, champion v1 unchanged;
- exact cumulative code hash:
  `0d9c2ce5cd62dd88c4666fcfed7a6ef14001a07caf171a6af346c74c4706535a`;
- prepared/pre/post data identity: 81 files, digest
  `ca7e470ec8d1f3569a690d10df5a170c4994108c71fecf5aa1a7a76b42630743`;
- postrun readiness: 28 `ok`, 3 optional problem-owned checks `skipped`,
  no required or optional failure.

There was no forced surface, action, or target; no Scion prompt/session/tool/
file/item/token budget or truncation; no automatic retry; and no additional
gate. Campaign `formal_readiness=false` only means that validation/frozen
evidence is not yet closed. It does not invalidate this complete screening
campaign.

## Round 1: Route-Cap-Aware Regret Repair

H1 selected `destroy_repair.py`. C1 used the restored serial same-file typed
edit path to change both `destroy_repair.py` and `scheduler.py`: regret-2/3
received `max_routes`, prioritized customers with few feasible placements,
penalized opening a route near the cap, and added small distance-scaled noise.
Contract, Verification, and Canary passed.

- case W/L/T: `0/4/4`;
- pair W/L/T: `9/16/7`;
- total-distance case median: `-3.25`, CI `[-9.25, 0]`;
- fleet-violation case deltas: all `0`;
- gate/Decision: `SCREENING_FAIL_WIN_RATE / continue_explore`;
- statistical status: `uncertain`;
- fresh runtime: 32 pairs, median ratio `1.0021`, median delta `+72.5 ms`,
  regression rate `0.5625`.

The intended intermediate mechanism moved: route-limit rejection fell from
champion `98` to candidate `32`, including regret-2/3 falling from `46` to `0`.
But repair errors rose from `0` to `5`, and final solution quality did not
improve. CMT2 and CMT4 had medians `-14.5` and `-13`; E-n101-k14 was `+8.5`.
This is useful negative causal evidence, not a framework rejection.

## H2 Used R1 Evidence

The H2 provider request contained exactly one canonical R1 history record:
all eight case rows, all 32 pair rows, case aggregate and CI, fresh runtime
facts, and the problem-owned route-limit/repair-error comparison. It also
contained the complete verified current `destroy_repair.py` and `scheduler.py`
sources. There was no duplicate history row or summary replacement.

H2 explicitly cited route-limit `-66`, median `-3.25`, and the CMT2/CMT4
losses. It then moved from further repair tuning to a materially different
local-search mechanism. This is direct evidence that the compact causal packet
and current-source continuation affected the next research decision.

## Round 2: Cumulative Swap-Star Candidate

H2 selected `local_search.py`. C2 used two ordered `exact_replace` edits on the
same file, registering and implementing a capacity-feasible inter-route
swap-star neighborhood. It tests a bounded customer-pair set, removes one
customer from each route, reinserts them at independently best positions, and
accepts strict distance improvements while preserving capacity and coverage.
Contract, Verification, and Canary passed.

The evaluated candidate is cumulative: R1 repair changes plus R2 swap-star.
The experiment does not isolate swap-star's incremental effect.

- case W/L/T: `5/1/2`;
- pair W/L/T: `20/11/1`;
- total-distance case median: `+3.5`, CI `[-11, 12]`;
- fleet-violation case deltas: all `0`;
- gate/Decision: `SCREENING_PASS / queue_validate`;
- statistical status: `uncertain`, below the `9.9` MDE context;
- strongest case medians: E `+17.5`, A `+12`, CMT2 `+4.5`;
- remaining weakness: CMT4 `-11`, X-n110-k13 `-55`.

The pair delta sum was `-131` (mean `-4.09375`) despite the positive
case-median gate. This is not a contradiction: Protocol's declared statistical
unit is the case and its median is formed from case aggregates. It does show
that the positive signal is heterogeneous and requires validation.

Round-2 comparative runtime fields are not interpretable because all 32
champion results were cache hits; `runtime_pairs=0` and runtime status is
`insufficient`. Descriptive candidate telemetry nevertheless shows an
important tradeoff:

- ALNS iterations fell from `1857` to `789` (`-57.5%`);
- ALNS-core time fell from `125959` to `53362 ms`;
- initial VNS time rose from `25639` to `75078 ms`;
- embedded VNS time rose from `778603` to `798764 ms`.

The fixed solver limit keeps total elapsed time similar while the new
neighborhood consumes a much larger share of search. Validation needs fresh
champion runtime before any runtime-regression conclusion.

The existing mechanism packet only owns ALNS repair diagnostics. It contains
no swap-star invocation/acceptance counter. Therefore R6 proves that the code
path was installed and the cumulative candidate produced a screening signal;
it does not directly prove swap-star activation or attribute the gain to it.

## Formal Artifact Defect

R6 exposed a framework integrity defect independent of its valid live
workspace:

- R1's v2 formal artifact correctly describes the two R1 files;
- R2's v2 artifact still declares `champions/champion_v1` as base but stores
  only the R2 `local_search.py` patch;
- it binds that incremental patch to the cumulative branch code hash
  `0d9c2ce5...`, omitting inherited R1 changes in `destroy_repair.py` and
  `scheduler.py`;
- replaying champion plus only the R2 artifact produces
  `0cc21753d1929398cf98b318e47039181b6884a3093330ec34dd8a062c47e13a`,
  not the declared cumulative hash;
- the old postrun check only ran `git apply --check`, so it did not detect the
  missing cumulative closure.

The original R6 root remains read-only evidence. Its R2 artifact must not be
used alone for fixed-candidate replay. Exact validation must copy the complete
campaign workspace, whose recomputed hash is `0d9c2ce5...`.

The repair introduces formal-candidate artifact v3:

- `patch` remains the current proposal attempt;
- `replay_materialization` is the complete champion-to-current full-file
  closure;
- proposal and cumulative digests are distinct;
- file attribution distinguishes current proposal, inherited verified state,
  and runtime activation;
- recorder and fixed replay validate base identity, per-file content, closure
  digest, candidate identity, and final code hash;
- postrun materializes v3 in a temporary workspace and fails closed on any
  mismatch;
- v1/v2 readers remain compatible.

The accompanying boundary tests cover consecutive edits to the same file,
create/delete, complete reversion to champion with an empty closure,
`registry.yaml` activation, and closure/content/base/final-hash tampering.

## Feedback Semantics Repair

The same audit removed misleading feedback fields and duplicate truth:

- a problem-owned mechanism envelope is no longer reinterpreted as the legacy
  mechanism shape or given invented `unknown` activation/effect fields;
- CVRP marks the packet as ALNS repair runtime diagnostics with hypothesis
  attribution `unbound`;
- canonical history includes Protocol outcome/reason codes and explicitly says
  the evaluated candidate is cumulative versus champion, not an isolated
  current-step effect;
- case median/CI/win-rate and pair win-rate scopes are explicit;
- pair median is not computed across possibly heterogeneous decisive metrics;
- formal Protocol pair counts are the only pair-rate owner and are reconciled
  fail-closed with the retained lossless pair rows;
- canonical history identity no longer hashes display-schema fields, so a
  schema upgrade does not duplicate the same durable R1 observation.

No case or pair row is truncated, ranked, summarized away, or moved into a
Decision feature.

## Repair Verification

The final formal-artifact/resume/postrun slice passes `21` tests, the complete
unit suite passes `707`, and the standard suite run from the repository root passes
`1926` with `1` skipped. The three apparent failures from an earlier full
invocation were reproduced as a wrong-working-directory invocation: their
repository-relative fixtures resolved through an extra `scion/` component and
all pass under the standard root command. Final review also reproduced a crash
window where an existing index could omit a newly written metadata artifact;
postrun now always compares disk metadata with indexed references, and the
partial-index fault-injection regression passes. Resume preparation quarantines
the prior index so current-run counts start at zero; postrun now binds those
metadata refs through the declared snapshot index without counting them as
current validation artifacts. Missing inherited metadata and metadata absent
from both live and snapshot indexes fail closed, while legitimate omitted rows
remain non-artifacts. The inherited index is accepted only at the launcher's
fixed quarantine path with the manifest-declared size and SHA-256, preventing a
tampered snapshot from disguising a current-run orphan.

## Next Experiment

Run one distinct eval-only continuation by copying the complete R6 campaign.
It must make no new H/C provider call and must evaluate the exact cumulative
candidate on the validation split with fresh champion runtime. Check the
current invocation's proposal-transition and trace deltas rather than treating
copied cumulative H/C counters as new calls.

Only after that validation is terminal should a separate clean generative run
continue longitudinal assessment. Use four requested rounds first; expand to
eight only if four rounds still leave evidence-use or adaptation questions
unresolved. Additional rounds are new scientific observations, not retries or
a semantic termination budget.
