# v0.4 Warehouse Direct Control R2 at `436b6e12`

- Date: 2026-07-14
- Model: `gpt-5.6-sol`
- Requested rounds: `2`
- Runtime mode: `direct_v3`
- Run root:
  `/home/clawd/research/scion-experiments/v04-warehouse-direct-control-r2-2r-gpt56sol-20260714T120937Z-claw`

## Verdict

This control reached two complete executable screening evaluations. Both
candidates were substantive algorithm implementations, both passed Contract,
Verification, and Canary, and the second proposal correctly consumed the first
round's experiment evidence and verified branch source. The simplified runtime
has therefore crossed the earlier “can only make small edits” boundary.

Neither algorithm improved the solver. Round 1 made many locally accepted
consolidation moves without changing the primary split metric and did not
improve cost reliably. Round 2 attempted a broader three-vehicle repartition,
but was quality-negative and much slower. The champion remained version 1 and
there was no promotion.

The campaign itself completed normally and is valid for algorithm conclusions.
The outer wrapper's effective exit was `64` because the original postrun reader
misclassified two identity-less duplicate decision rows as non-evaluated. That
is a postrun false negative, not an experiment failure.

## Execution Evidence

- guarded readiness: `static_ready=true`,
  `guarded_wrapper_launch_ready=true`, no blockers;
- completion preflight: authenticated HTTP 200 with non-empty response;
- durable provider calls: H=`2`, C=`2`, total=`4`;
- automatic retries or replacement attempts: `0`;
- effective Protocol rounds: `2/2`;
- execution outcomes: evaluated=`2`, all other typed outcomes=`0`;
- run validity: `valid`;
- one branch for both rounds:
  `79428226-855b-4e0d-9d0c-dfc092e2f417`;
- campaign wrapper exit: `0`; original root wrapper effective exit: `64` due
  only to the postrun readiness false negative.

No Scion prompt/session/tool/file/item/token budget or truncation was active.
The protocol's 30-second per-solver-run limit is a scientific execution fact,
not an agent context or proposal budget.

## Round 1: Subcategory Consolidation

The agent created `operators/subcategory_consolidation.py`: a bounded
best-improvement ejection/repacking operator intended to empty fragments of one
subcategory, resize affected vehicles, and accept lexicographic improvements.
This was a real new search mechanism rather than metadata or a cosmetic edit.

- Contract / Verification / Canary: pass / pass / pass;
- valid screening pairs: `20/20`;
- `subcategory_splits` delta: `0` on all ten cases;
- case W/L/T: `1/1/8`, win rate `0.10`;
- pair W/L/T: `7/8/5`;
- total-cost median delta: `+50`, CI `[-325, 250]`;
- runtime median ratio: `0.9254`, delta `-194 ms`;
- Decision: `continue_explore / SCREENING_FAIL_WIN_RATE`.

Candidate telemetry recorded hundreds of locally accepted moves and a large
negative sum of local cost deltas, yet the complete solver trajectory did not
improve. The central research problem is therefore no longer simply operator
activation: accepted local improvements can perturb later search and operator
selection without producing a better final solution.

## Round 2: Cost-Neutral Repack

The same branch consumed round 1's canonical screening result. Its C
SourceLedger contained the verified round-1 operator with
`owner=branch_helper`, `provenance=branch_history_current`, full current source,
and the expected digest. The agent then created
`operators/cost_neutral_repack.py`, a bounded three-vehicle repartition intended
to reach fleet substitutions that pairwise merging cannot.

- Contract / Verification / Canary: pass / pass / pass;
- valid screening pairs: `20/20`;
- `subcategory_splits` delta: `0` on all ten cases;
- case W/L/T: `0/3/7`, win rate `0.00`;
- pair W/L/T: `5/9/6`;
- total-cost median delta: `-150`, CI `[-2500, 400]`;
- runtime median ratio: `2.2983`, delta `+3373 ms`;
- runtime regression rate: `0.85`, maximum elapsed `30115 ms`;
- Decision: `continue_explore / RUNTIME_REGRESSION`.

The negative verdict is not merely an over-heavy runtime gate. The candidate
also lost three cases, won none, and had more losing than winning seed pairs.
Its expensive per-call search likely displaced useful champion operators and
starved the remaining search schedule.

## Experiment-Proven Framework Findings

### 1. Formal launcher consumed the wrong configuration copy

The previous repair simplified
`scion/scion/problems/warehouse_delivery/problem-v1.yaml`, but the formal
launcher and warehouse prompt bridge prefer
`scion/problems/warehouse_delivery/problem-v1.yaml`. The latter still contained
old provider-visible requests for activation/effect counters, telemetry guards,
top-k/max-candidate policies, validation-transfer analysis, and runtime-budget
strategy. Round 2's actual C trace proves those instructions were still sent,
and the generated code followed them.

The operational top-level spec remains the launch owner. Its resolved semantics
are now aligned with the package mirror, and a full semantic-parity regression
prevents silent divergence. This is deliberately a
single-runtime-owner decision, not a launcher migration performed during an
experiment repair.

### 2. Postrun correlated rows by schema, not row identity

The database contains two exact `explore_evaluation_outcome=evaluated` rows and
identity-bearing experiment/scheduler decision rows for both hypotheses. It
also contains two standalone `event_kind=decision` projections with branch ID
only and NULL campaign/hypothesis/stage. The original inventory SQL saw that
the table had identity columns, then treated those two identity-less rows as
failed correlations.

The repair has two parts:

- future `record_decision` rows persist campaign, hypothesis, and stage;
- postrun correlates only decision rows with complete identity, while counting
  legacy identity-less projections separately as
  `decision_rows_without_correlation_identity`.

Explicit non-evaluated decision outcomes still fail closed. Rebuilding the
inventory from this root now reports consistency=`consistent`, non-evaluated
decision rows=`0`, identity-less diagnostic rows=`2`, and the
`execution_outcome_integrity` check passes. Strict current-run readiness still
fails only on the immutable historical wrapper/postrun-failed markers; the root
must not be rewritten or rerun.

### 3. H6 key format was underspecified

Both generated operators constructed amount-limit keys as shipping method plus
country with a pipe separator. The warehouse oracle actually uses
`f"{destination_country},{ship_method}"`. The screening fixtures did not expose
the mismatch strongly enough for Verification to reject it. The exact key
format is now part of the concise problem/operator interface so future code can
implement the real feasibility rule without additional governance text.

## Research Interpretation

Scion can now generate, execute, and iteratively adapt substantial algorithmic
operators. The remaining warehouse bottleneck is scientific: a local operator
must improve the final search trajectory, not merely find locally acceptable
moves. The next investigation should examine operator selection weight,
opportunity cost, seeded trajectory divergence, and cheap attribution of final
objective effects. It should not reintroduce mandatory telemetry dialects or a
heavier pre-evaluation gate.

Do not start the CVRP control from `436b6e12`. First land the configuration
owner/parity, lineage correlation, and H6 interface repairs, run the complete
suite, and prepare a fresh clean runtime root. The next formal experiment must
then confirm that the provider-visible warehouse context is actually the
repaired context before CVRP is used as the second problem-family control.
