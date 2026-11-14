# CVRP R20: exact R19 discovery versus B0-fixed

State: **completed NOT_CONFIRMED at validation**, October9 at03:05:39 Beijing
/October8 at19:05:39 UTC. All72 formal pairs valid; screening passes, validation
CI crosses zero. No frozen/retained or promotion. See the
[October9 postrun](v04-cvrp-r20-r19-final-b0-fixed-postrun-20261009.md).
Launched once October8 at23:36:28 Beijing /15:36:28 UTC, PID652580,
tmux `scion-r20-r19-final-b0-fixed-20261008`. Never resume or rerun this root;
startup and planned-command wording below is historical.
October8 user authorizes experiment inspection,
analysis/optimization and another experiment. The [R19 postrun](v04-cvrp-r19-reliable-probes-autonomous-postrun-20261008.md)
finds valid12/12 stages,320 pairs, seven candidates and a final expanded-screening
pass, but no remaining scheduled stage for validation. Do not resume R19.

## Question and intervention

Does the exact final A3 source discovered by Scion outperform B0-fixed on the
prespecified full funnel, without relying on champion-first order or six-seed
discovery selection? R19 compared it with R12-A-fixed. This new comparison is
not an independent repetition of that identical contrast and does not isolate
the latest ordinary-swap edit from its cumulative bundle.

Optimize measurement, not the selected algorithm: use the existing provider-free
fixed-candidate runner, equal fresh-copy isolation, balanced AB/BA order and
larger prospective seed samples. No new runtime, adapter, solver patch, generic
gate, model call, candidate synthesis, sibling merge or authority machinery.
Prior R19 Contract/Verification accepted this exact source; fixed-funnel scope
checks, paired canary, runtime audit, feasibility/objective checks and deterministic
Protocol/Decision stay unchanged. The driver does not invent a new H/C session
or rerun the original Contract/Verification pipeline.

## Exact source contrast

A = B0-fixed, the existing complete100-file R13 baseline snapshot:
`/home/clawd/research/scion-experiments/v04-cvrp-r13-constructor-fixed-b0-20260926/input_snapshots/baseline`.
It byte-equals R13's declared b0-fixed input; no original B0 edit.

B = R19 A3, selected solely by its final SCREENING_PASS/queue_validate result:
`/home/clawd/research/scion-experiments/v04-cvrp-r19-reliable-probes-autonomous-20261005/candidate_workspaces/candidate-560r6jum`.
All100 files are retained. Compared with R19 champion only local_search differs;
compared with B0-fixed the exact changed-file set is:

- `policies/baseline_modules/destroy_repair.py`
- `policies/baseline_modules/local_search.py`
- `policies/baseline_modules/scheduler.py`

Both arms retain the same independently engineered constructor repair. R13's
[design](v04-cvrp-r13-constructor-fixed-b0-preregistration-20260926.md) and
[postrun](v04-cvrp-r13-constructor-fixed-b0-postrun-20260927.md) establish this
common-repair lineage. Read-only byte comparison checks the ordinary whole
sources; no hash/identity record is introduced. The runner snapshots both once
and uses disposable per-arm copies. The original R19/R13 evidence is untouched.

## Prospective populations and gates

Reuse the unchanged [R7 main split](inputs/v04-cvrp-r7-autonomous-source-continuation-split.yaml)
and [pre-R3 retained split](inputs/v04-cvrp-r6-minus-2for1-b0-retained-split.yaml).
Already exposed validation is a development/completeness gate, not unseen data.
Frozen and retained are conditionally unopened: no later stage runs if a preceding
stage fails, is uncertain, or has incomplete comparison evidence.

[Protocol](inputs/v04-cvrp-r20-r19-final-b0-fixed-protocol.yaml) differs from R19
only in version, canary seed and seed counts: expanded screening6→8,
validation2→4 and frozen2→4. Initial design remains5cases×4seeds, but the fixed
runner starts directly at mandatory expanded screening. No twelve-stage campaign
cap can cut off a queued validation. All practical margins, CI, case-level score,
loss constraints, runtime/feasibility/fleet rules and solver limits are unchanged.
The algorithm wall-clock fraction/reserve is unchanged. More samples are fixed
in advance, not sequential additions to turn a negative result positive.

First21 primes above260000, selected before any R20 outcome and disjoint from
all checked-in preceding seed ledgers. [Main seeds](inputs/v04-cvrp-r20-r19-final-b0-fixed-seeds.yaml)
and [retained seeds](inputs/v04-cvrp-r20-r19-final-b0-fixed-retained-seeds.yaml):

| Stage | Cases | Seeds | Pairs |
|---|---:|---|---:|
|Expanded screening|6|260003,260009,260011,260017,260023,260047,260081,260089|48|
|Exposed validation|6|260111,260137,260171,260179|24|
|Frozen|12|260189,260191,260201,260207|48|
|Independent retained|12|260213,260231,260263,260269|48|
|Safety canary|1|260209|1|

Existing parity order balances each formal case across seeds:4AB/4BA screening,
2AB/2BA at each later stage. Each pair uses equal60/90/120/180/240-second
dimension limits, with canary10seconds, process guard30seconds and4096MiB.
Canary is the existing safety pair, not counterbalanced quality evidence.
No pooling with R19 or post-outcome extension/seed selection.

Maximum conditional work169 pairs/338 solver processes,40580 nominal and50720
guarded subject-seconds. Outer hardwall86400seconds (24h). This upper bound
includes all conditional stages and does not promise they will be reached.
No provider calls or provider health probe is needed. No simultaneous autonomous
run, tests, maintenance or input/runtime editing during measurement.

## Interpretation and stopping

Preserve NOT_CONFIRMED, incomplete and interruption terminals unchanged. A
screening-only success does not promote; only the existing full funnel may do
so. A PROMOTED_RETAINED result concerns **B0-fixed**, not unchanged original B0
and not isolated ordinary-swap causality. CVRP's original-B0 objective cannot be
silently relabeled complete. Report every pair/case, failures, scheduled/actual
order and source snapshots before choosing any subsequent research action.

Test reliability and real-path coverage are improved but not solved globally:
R19's small real-entry probes do not certify large formal-case accepted/retained
transitions. Family-level telemetry is insufficient for component attribution.
No extra quality gate is added to mask those limits. Future autonomous proposals
must use the actual delivered head, not assume sibling inheritance; later private
outcomes must not enter H/C. Any further run needs a separate fresh design.

## Verification and launch

Runtime remains6380a59e. This turn changes prospective inputs, their focused
regressions and analysis/status docs only. Eight new input tests verify unchanged
rules, prospective/disjoint seeds, complete resource matrix, per-case balanced
ordinals and public/formal closure. Combined R19/R20 input, fixed-driver and
paired-execution tests:61 passed in1.09seconds. Final read-only `--check`, source
parsing, no-overlap/fresh-output/disk checks and launch evidence follow below.
No Git action accompanied the launch. A subsequent October8 user request
authorizes committing/pushing this frozen inputs/tests/docs set. This does not
change launch provenance6380a59e, runtime, source snapshots or live measurement.

Read-only preparation returns PREPARED: all37 cases parse, all populations/seeds
are disjoint, exact three-file source difference and338-process/40580-nominal/
50720-guarded-second envelope match. Both100-file trees have48 Python files,
all AST-parse. Final A3 source equals its actually submitted exact patch applied
in memory to the delivered edit base. Ruff F/E9 and git diff --check pass.
All prior panes are dead and read-only process inspection finds no competing
campaign/solver/tests. About58.2GiB remains available. Runtime and scientific
inputs are frozen before launch; only lifecycle documentation may update.

Startup read-only audit: input.json is present, terminal.json absent, driver
alive. Both complete100-file private snapshots equal their declared sources.
Stored selected surface, three changed files and resource envelope match the
design. Actual safety-canary subprocess has seed260209 and time-limit10.
The subsequent live subprocess uses screening seed260003 and time-limit60;
the unchanged driver has therefore passed canary and entered expanded screening.
No completed formal metric exists yet.
Startup verifies execution, not comparative improvement; do not run tests or
alter runtime/scientific inputs while this process is live.

Output: `/home/clawd/research/scion-experiments/v04-cvrp-r20-r19-final-b0-fixed-20261008`.
Tmux: `scion-r20-r19-final-b0-fixed-20261008`.

## Frozen invocation

Execute once only after preflight. Appending `--check` performs read-only prep
with zero provider/solver calls and no output creation.

```bash
/usr/bin/env -i \
  PATH=/home/clawd/miniconda3/envs/claw/bin:/usr/bin:/bin \
  LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
  PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion:/home/clawd/research/or-autoresearch-agent:/home/clawd/.local/lib/python3.12/site-packages:/home/clawd/miniconda3/envs/claw/lib/python3.12/site-packages \
  OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  SCION_PROBLEM_DATA_ROOT=/home/clawd/research/scion-experiment-inputs/v04-cvrp-r6-minus-2for1-b0-20260921/data \
  /home/clawd/miniconda3/envs/claw/bin/python -S -B \
  /home/clawd/research/or-autoresearch-agent/scion/run_fixed_candidate_funnel.py \
  --label v04-cvrp-r20-r19-final-b0-fixed-20261008 \
  --baseline-source /home/clawd/research/scion-experiments/v04-cvrp-r13-constructor-fixed-b0-20260926/input_snapshots/baseline \
  --candidate-source /home/clawd/research/scion-experiments/v04-cvrp-r19-reliable-probes-autonomous-20261005/candidate_workspaces/candidate-560r6jum \
  --problem-spec /home/clawd/research/or-autoresearch-agent/scion/scion/problems/cvrp/problem-v1.yaml \
  --protocol /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r20-r19-final-b0-fixed-protocol.yaml \
  --split /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r7-autonomous-source-continuation-split.yaml \
  --seeds /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r20-r19-final-b0-fixed-seeds.yaml \
  --retained-split /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r6-minus-2for1-b0-retained-split.yaml \
  --retained-seeds /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r20-r19-final-b0-fixed-retained-seeds.yaml \
  --changed-file policies/baseline_modules/destroy_repair.py \
  --changed-file policies/baseline_modules/local_search.py \
  --changed-file policies/baseline_modules/scheduler.py \
  --selected-surface solver_design --time-limit-sec 60 --timeout-guard-sec 30 \
  --outer-hardwall-sec 86400 --memory-mb 4096 \
  --output-dir /home/clawd/research/scion-experiments/v04-cvrp-r20-r19-final-b0-fixed-20261008
```
