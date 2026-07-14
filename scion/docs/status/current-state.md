# Scion v0.4 Current State

*Last updated: 2026-07-14*

This is the operational resume point. Read `scion/TASK.md` first and use
`scion/design/scion-architecture-v3.md` as the architecture tie-breaker.

No experiment is running. The latest formal warehouse campaign completed two
evaluated rounds and proved that the direct runtime can perform substantial,
iterative algorithm development. Neither candidate improved the solver. Before
CVRP, three experiment-proven framework defects are being repaired: the formal
launcher consumed a stale problem-spec copy, postrun falsely rejected
identity-less duplicate decision rows, and the exact warehouse H6 key format
was absent from provider context.

## Current Decision

Commit `436b6e12` is pushed on `v0.4-dev`. It is the source commit for the
completed R2 warehouse control, not the next runtime baseline.

Do not launch CVRP or another formal warehouse run from `436b6e12`. First land
and fully test the narrow spec-owner/parity, lineage-correlation, and H6 prompt
repair. Then prepare a fresh detached clean worktree and run a two-round
warehouse confirmation whose actual H/C trace proves the corrected context is
visible. CVRP follows only after that confirmation.

Do not resume successor55, create successor56, reuse an old warehouse root, or
bypass `git_runtime_worktree_clean`.

## Latest Formal Control

Run root:

`/home/clawd/research/scion-experiments/v04-warehouse-direct-control-r2-2r-gpt56sol-20260714T120937Z-claw`

Runtime facts:

- model: `gpt-5.6-sol`;
- prepared/runtime commit: `436b6e12`;
- guarded readiness: passed with no blocker;
- preflight: authenticated HTTP 200, non-empty response;
- requested/evaluated rounds: `2/2`;
- durable provider calls: H=`2`, C=`2`, total=`4`;
- retries or replacement attempts: `0`;
- branch count: one active research branch across both rounds;
- both candidates: Contract pass, Verification pass, Canary pass, `20/20`
  valid screening pairs;
- campaign validity: `valid`;
- campaign wrapper exit: `0`;
- original outer wrapper effective exit: `64` only because postrun produced a
  false `execution_outcome_integrity` failure.

The run used no Scion prompt/session/tool/file/item/token budget, semantic
termination budget, or truncation. The protocol's 30-second solver time limit
remains a scientific subprocess fact.

## Algorithm Results

### Round 1

The agent created a 373-line `subcategory_consolidation.py` implementing a
bounded best-improvement subcategory ejection/repacking search.

- case W/L/T: `1/1/8`, win rate `0.10`;
- pair W/L/T: `7/8/5`;
- subcategory-split delta: always `0`;
- total-cost median delta: `+50`, CI `[-325, 250]`;
- runtime median ratio: `0.9254`, delta `-194 ms`;
- Decision: `continue_explore / SCREENING_FAIL_WIN_RATE`.

The operator reported many accepted local moves and large summed local cost
reductions, but the final solver output did not improve. Local acceptance is
not causal evidence of better global search.

### Round 2

The same branch received round 1's canonical experiment result and verified
current source. The agent created a 320-line `cost_neutral_repack.py`
implementing bounded three-vehicle repartition.

- C SourceLedger carried the round-1 operator as
  `branch_history_current/full_current` with its digest;
- case W/L/T: `0/3/7`, win rate `0.00`;
- pair W/L/T: `5/9/6`;
- subcategory-split delta: always `0`;
- total-cost median delta: `-150`, CI `[-2500, 400]`;
- runtime median ratio: `2.2983`, delta `+3373 ms`;
- runtime regression rate: `0.85`, max elapsed `30115 ms`;
- Decision: `continue_explore / RUNTIME_REGRESSION`.

This was not a promising algorithm blocked only by a heavy runtime gate. It
also won no case and lost more seed pairs than it won. The likely scientific
bottleneck is operator opportunity cost and whole-search trajectory impact:
expensive locally improving operators can starve useful existing operators or
change the seeded trajectory adversely.

## Experiment-Proven Framework Defects

### Operational problem-spec drift

The previous repair edited
`scion/scion/problems/warehouse_delivery/problem-v1.yaml`, but both the formal
launcher and warehouse prompt bridge prefer
`scion/problems/warehouse_delivery/problem-v1.yaml`. The actual round-2 C trace
still contained activation/effect counter requests, telemetry-guard language,
validation-transfer analysis, top-k/max-candidate rules, and runtime-budget
strategy. The generated code followed that noise.

The repair keeps the top-level spec as the operational launch owner, aligns its
resolved semantics with the package mirror, and adds full semantic parity
coverage. Changing the launch owner and every prompt-bridge path is out
of scope for this experiment repair.

### Postrun decision correlation false negative

The R2 database has two exact evaluated outcome rows and identity-complete
experiment/scheduler decisions. `LineageRegistry.record_decision` also wrote two
duplicate branch-only decision projections with NULL campaign/hypothesis/stage.
The original SQL checked only whether identity columns existed in the table and
therefore treated those legacy rows as failed outcome correlations.

The repair persists full identity on future decision projections. Postrun now:

- fails any decision row that explicitly carries a non-evaluated outcome;
- requires an evaluated correlation only for decision rows with complete
  campaign/branch/hypothesis identity;
- counts legacy incomplete projections separately as
  `decision_rows_without_correlation_identity`.

The rebuilt R2 inventory reports evaluated=`2`, consistency=`consistent`,
non-evaluated decision rows=`0`, and identity-less diagnostic rows=`2`.
`execution_outcome_integrity` passes. Strict current-run readiness still fails
only on immutable historical outer-wrapper/postrun-failed markers, so the old
root remains evidence rather than a reusable runtime.

### H6 source contract

Both generated candidates used `ship_method + "|" + destination_country` for
amount-limit lookup. The oracle uses
`f"{destination_country},{ship_method}"`. Screening data did not expose the
mismatch strongly enough to fail Verification. The exact key format is now
included once in the concise problem/operator interface.

## Repair Validation Status

Completed so far:

- focused problem-guidance and problem-bridge regression: `13 passed`;
- complete affected lineage/postrun/launcher shard: `206 passed`;
- final collection/full Scion suite: `1853` tests collected,
  `1852 passed, 1 skipped` in `492.99s`;
- compileall and `git diff --check`: passed;
- a read-only current-source postrun check against the R2 root confirms
  `execution_outcome_integrity=ok` and only the immutable wrapper-marker checks
  remain failed.

Still required before commit/runtime preparation:

- focused diff review and exclusion check.

## Worktree State

- branch: `v0.4-dev`;
- `436b6e12` has been committed and pushed;
- the source worktree contains the new, uncommitted framework repair plus this
  report and operating-doc updates;
- `scion/docs/v0.4-measurement-readiness.md` is a pre-existing user-owned
  tracked change and must remain excluded;
- unrelated untracked historical/future documents must remain excluded;
- the source worktree must not host a formal run.

## Resume Actions

1. Complete the final read-only audit and exclusion review; the affected shard,
   full suite, compileall, and diff checks already pass.
2. Stage only the spec/parity, lineage/postrun, H6 interface, R2
   report, `TASK.md`, and this current-state file after explicit authorization.
   Preserve all excluded user/history files.
3. Commit and push the reviewed repair after authorization.
4. Create a fresh detached clean worktree at that exact commit. Prepare a new
   warehouse root and require guarded-wrapper readiness with no separate live
   probe.
5. Before launch, inspect the prepared provider context and prove that old
   telemetry-counter, telemetry-guard, validation-transfer, top-k/
   max-candidate, and runtime-budget strategy text is absent.
6. After explicit operator approval, launch one two-round warehouse
   confirmation. Poll observationally at about three-minute intervals and
   never schedule a retry.
7. Run one clean, open, non-target-bound CVRP control only after the repaired
   warehouse confirmation is executable and the outer wrapper is green.

## Runner Notes

Server `claw`:

- repo: `/home/clawd/research/or-autoresearch-agent`;
- Python: `/home/clawd/miniconda3/envs/claw/bin/python`;
- use for focused tests and one formal run at a time.

WSL `scion` is reserved for large/concurrent validation after a fresh
connectivity and preflight check.

## Pointers

- Active task: `scion/TASK.md`
- V3 architecture: `scion/design/scion-architecture-v3.md`
- v0.4 direct-runtime addendum:
  `scion/design/scion-architecture-v3-v0.4-direct-runtime-addendum.md`
- Main audit:
  `scion/reports/v04-v3-runtime-and-research-effectiveness-audit-20260712.md`
- Successor55 characterization:
  `scion/docs/experiments/v0.4/v04-cvrp-successor55-bounded-elite-solution-pool-postrun-20260712.md`
- Warehouse R1 control:
  `scion/docs/experiments/v0.4/v04-warehouse-direct-control-b1464171-postrun-20260713.md`
- Warehouse R2 control:
  `scion/docs/experiments/v0.4/v04-warehouse-direct-control-r2-436b6e12-postrun-20260714.md`
