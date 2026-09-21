# CVRP R6 complete v2-minus-2-for-1 versus original B0

State: launched once at `2026-09-21T16:09:27Z`, running; no terminal result yet.

The prospective code/input record was committed as `e405bfd2` before any R6
solver execution. Launch used a clean checkout at that revision and tmux
`scion-r6-minus-2for1-b0-20260921`. This administrative status does not alter the
frozen design below. Runtime/source/configuration files remain unchanged.
Output: `/home/clawd/research/scion-experiments/v04-cvrp-r6-minus-2for1-b0-20260921`.
At `16:11:04Z`, the live child was executing screening case B-n34-k5 at seed
20021. This establishes progression past canary, not a valid-pair count or
effect estimate; terminal metrics were not yet available.

The [Warehouse control postrun](v04-p1b-warehouse-aa-control-postrun-20260921.md)
preserves both diagnostics: the first had two shared-infeasible pairs; a
prospectively documented public-fixture replacement produced 4/4 valid ties
and the expected negative Decision on the same runtime. R6 inputs were not
changed by either control outcome.

## Question and source values

Does the complete R5 minus-2-for-1 tree improve on the exact original R3i B0
on new cases and seeds, and, only after a complete main-funnel pass, retain
that effect on the still-unexecuted pre-R3 final block?

This provider-free fixed-candidate experiment exports no H or C, calls no
provider, and does not rerun Contract or Verification over invented proposals.
The existing fixed funnel performs source/scope checks, complete-pair canary,
Protocol, Safe Features and deterministic Decision. It starts as development
screening, not as a presumption that R5 promoted its comparator.

Input root:
`/home/clawd/research/scion-experiment-inputs/v04-cvrp-r6-minus-2for1-b0-20260921`.

- `baseline/` is byte-equal to R4's `input_snapshots/baseline`, the original B0.
- `candidate/` is byte-equal to R5's `input_snapshots/baseline`, the complete
  v2-minus-2-for-1 tree. No patch-chain reconstruction or new algorithm edit.
- R5's full-v2 snapshot is byte-equal to R4's candidate. Relative to full v2,
  R6's candidate differs only in `policies/baseline_modules/local_search.py`:
  the one default-registry `_exchange_2_for_1` entry is absent.
- Relative to B0, exactly `destroy_repair.py`, `local_search.py`, and
  `scheduler.py` under `policies/baseline_modules/` differ.

These checks concern ordinary source values, not identity, registration or
digest authority. R4/R5 terminal roots remain untouched. The fixed driver
makes its normal output-local read-only snapshots and disposable per-arm
workspaces.

## Prospective population

The exclusion basis is the R4 audit of R3–R3i's 68 metric artifacts (36 executed
formal cases and 24 seeds), the checked-in R3 formal split/ledger, and the exact
R4/R5 terminal and metric artifacts linked by current state. R4 and R5 executed
only the six R4 screening cases. The new main population excludes even R4's
unexecuted validation/frozen cases; its overlap with all 24 R4 main cases and
all 36 R3 formal cases is zero.

Selection uses only local CVRPLIB instance metadata, not solver outcomes:

1. Start from `/home/clawd/research/or-autoresearch-agent/vrp/cvrplib`.
   Keep A/B/E/F/M/P/X/tai instances with both .vrp and .sol files, DIMENSION
   30–1001, and, where the filename has -k, k / DIMENSION <= 0.15.
2. Exclude R3's 36 formal cases, all 24 R4 main cases, and the 12 pre-R3 final
   cases reserved for retained evaluation.
3. Split by DIMENSION into 30–100, 101–350 and 351–1001. Sort each stratum by
   (DIMENSION, canonical relative path). Eligible counts are 38, 25 and 14.
4. Take indices floor((i + 0.5) * N / 8), i = 0..7. Indices are
   2/7/11/16/21/26/30/35, 1/4/7/10/14/17/20/23, and 0/2/4/6/7/9/11/13.
5. Assign ordinals 0/4 to screening, 1/5 to validation, 2/3/6/7 to frozen,
   interleaving small/medium/large within each ordinal.

This documents outcome-unseen status relative to the R3–R5 lineage, not a
claim that no historical project ever evaluated any catalog instance.
The retained block is the original pre-R3 reserved 12-case block; R3i, R4
and R5 did not open it. No historical experiment-root scan was performed.

| Stage | Small | Medium | Large | Seeds | Pairs |
|---|---|---|---|---|---:|
| expanded screening | B-n34-k5, A-n54-k7 | tai100a, X-n190-k8 | X-n351-k40, X-n513-k21 | 20011,20021,20023,20029 | 24 |
| validation | B-n39-k5, A-n62-k8 | X-n106-k14, X-n228-k23 | tai385, X-n627-k43 | 20047,20051 | 12 |
| frozen | A-n44-k6, A-n48-k7, B-n66-k9, P-n76-k5 | X-n129-k18, tai150d, X-n275-k28, X-n327-k20 | X-n449-k29, X-n491-k59, X-n783-k48, X-n979-k58 | 20063,20071 | 24 |
| retained | original reserved block, unchanged | original reserved block, unchanged | original reserved block, unchanged | 20089,20101 | 24 |
| canary | reused controlled synthetic safety case | — | — | 20107 | 1 |

Seeds are the first eleven primes greater than 20,000, assigned in the table's
stage order. They are disjoint from R3–R5 ledgers. Canary is a non-estimand
execution check; its familiar case does not enter an effect aggregate.

Frozen files:

- [Protocol](inputs/v04-cvrp-r6-minus-2for1-b0-protocol.yaml)
- [main split](inputs/v04-cvrp-r6-minus-2for1-b0-split.yaml)
- [main seeds](inputs/v04-cvrp-r6-minus-2for1-b0-seeds.yaml)
- [retained split](inputs/v04-cvrp-r6-minus-2for1-b0-retained-split.yaml)
- [retained seeds](inputs/v04-cvrp-r6-minus-2for1-b0-retained-seeds.yaml)

Only input selection/version/canary and the dimension-correct tai100a time rule
differ from R4's Protocol configuration. Gates are unchanged: complete pairs,
feasibility, protected fleet_violation, practical distance delta 2.0 for
screening and 1.0 for validation, nonnegative bootstrap lower bound,
net case score >= 0.25 and loss rate <= 0.20. No weakening of
SCREENING_FAIL_CASE_QUALITY, no diagnostic-telemetry gate, no retry or retuning.

## Execution and claim limits

Conditional path: strict canary -> expanded screening -> validation -> frozen
promotion -> independent retained B0 comparison. A negative stage stops
progression without opening later outcomes. Comparator/shared/bilateral failure
is incomplete evidence, not a candidate defeat. A positive terminal requires
all intended pairs with zero failures; the ordinary driver owns these outcomes.

Both arms use DIMENSION-only 30/45/60/90/120-second limits (<=100/200/350/700/1001),
10-second canary, 30-second subprocess guard, 4096 MiB and serial execution.
The unchanged maximum is 85 pairs / 170 subprocesses / 10,160 nominal /
15,260 guarded subject-seconds. The 21,600-second outer alarm is specific to
this finite matrix, not a campaign-lifetime policy. Screening alone has
24 pairs plus canary, 50 subprocesses and 2,660 nominal subject-seconds.

Only PROMOTED_RETAINED supports improvement of this exact selected bundle over
B0 on this declared funnel. It does not prove isolated 2-for-1 causality,
global CVRP superiority, or complete the original eight-seed final matrix.
A negative remains a valid experiment and does not complete CVRP or v0.4.

Before launch: finish P1b full regression, freeze code and these inputs, verify
no active experiment, and run the independently preregistered
[Warehouse A/A wiring control](/home/clawd/research/scion-experiment-inputs/v04-p1b-warehouse-aa-control-20260921/PREREGISTRATION.md)
on the same runtime. That comment-only control executes the real Warehouse
solver without fabricated H/C; its expected scientific negative is diagnostic
only and cannot support a solver improvement. Its maximum is 16 subprocesses,
32 nominal and 272 guarded seconds, 2 seconds/arm, 15-second guard, 1024 MiB,
600-second outer guard. Its frozen configuration files live beside that record.

P1b full regression completed with 2397 passed, 1 skipped and no failures in
436.38 seconds. Targeted Ruff F/E9 and diff checks passed. R6's 36 instance/
reference copies match their catalog files, all 11 seeds are disjoint from
R3–R5 ledgers, and both external input roots are read-only.

Both --check commands returned PREPARED without solver calls or output creation.
Run each exactly once from an absent output root:

```bash
# Independent diagnostic control:
/usr/bin/env -i PATH=/home/clawd/miniconda3/envs/claw/bin:/usr/bin:/bin LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion:/home/clawd/.local/lib/python3.12/site-packages:/home/clawd/miniconda3/envs/claw/lib/python3.12/site-packages OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 /home/clawd/miniconda3/envs/claw/bin/python -S -B /home/clawd/research/or-autoresearch-agent/scion/run_fixed_candidate_funnel.py --label v04-p1b-warehouse-aa-control-20260921 --baseline-source /home/clawd/research/scion-experiment-inputs/v04-p1b-warehouse-aa-control-20260921/baseline --candidate-source /home/clawd/research/scion-experiment-inputs/v04-p1b-warehouse-aa-control-20260921/candidate --problem-spec /home/clawd/research/or-autoresearch-agent/scion/scion/problems/warehouse_delivery/problem-v1.yaml --protocol /home/clawd/research/scion-experiment-inputs/v04-p1b-warehouse-aa-control-20260921/protocol.yaml --split /home/clawd/research/scion-experiment-inputs/v04-p1b-warehouse-aa-control-20260921/split.yaml --seeds /home/clawd/research/scion-experiment-inputs/v04-p1b-warehouse-aa-control-20260921/seeds.yaml --retained-split /home/clawd/research/scion-experiment-inputs/v04-p1b-warehouse-aa-control-20260921/retained-split.yaml --retained-seeds /home/clawd/research/scion-experiment-inputs/v04-p1b-warehouse-aa-control-20260921/retained-seeds.yaml --changed-file operators/change_vehicle_type.py --selected-surface vehicle_level --time-limit-sec 2 --timeout-guard-sec 15 --outer-hardwall-sec 600 --memory-mb 1024 --output-dir /home/clawd/research/scion-experiments/v04-p1b-warehouse-aa-control-20260921

# R6 (after regression/control and ordinary read-only launch checks):
/usr/bin/env -i PATH=/home/clawd/miniconda3/envs/claw/bin:/usr/bin:/bin LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion:/home/clawd/.local/lib/python3.12/site-packages:/home/clawd/miniconda3/envs/claw/lib/python3.12/site-packages OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 SCION_PROBLEM_DATA_ROOT=/home/clawd/research/scion-experiment-inputs/v04-cvrp-r6-minus-2for1-b0-20260921/data /home/clawd/miniconda3/envs/claw/bin/python -S -B /home/clawd/research/or-autoresearch-agent/scion/run_fixed_candidate_funnel.py --label v04-cvrp-r6-minus-2for1-b0-20260921 --baseline-source /home/clawd/research/scion-experiment-inputs/v04-cvrp-r6-minus-2for1-b0-20260921/baseline --candidate-source /home/clawd/research/scion-experiment-inputs/v04-cvrp-r6-minus-2for1-b0-20260921/candidate --problem-spec /home/clawd/research/scion-experiment-inputs/v04-cvrp-r6-minus-2for1-b0-20260921/baseline/problem-v1.yaml --protocol /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r6-minus-2for1-b0-protocol.yaml --split /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r6-minus-2for1-b0-split.yaml --seeds /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r6-minus-2for1-b0-seeds.yaml --retained-split /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r6-minus-2for1-b0-retained-split.yaml --retained-seeds /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r6-minus-2for1-b0-retained-seeds.yaml --changed-file policies/baseline_modules/destroy_repair.py --changed-file policies/baseline_modules/local_search.py --changed-file policies/baseline_modules/scheduler.py --selected-surface solver_design --time-limit-sec 30 --timeout-guard-sec 30 --outer-hardwall-sec 21600 --memory-mb 4096 --output-dir /home/clawd/research/scion-experiments/v04-cvrp-r6-minus-2for1-b0-20260921
```

Appending --check is read-only preparation. Runtime imports explicitly select
this checkout, avoiding the older editable installation. No credentials are
needed or printed. tmux is only a process carrier. Read terminal.json and exact
metric references for scientific outcomes; do not infer a result from pane exit
status, interrupt/restart a negative run, or open the original SQLite databases.
