# CVRP R8: exact final R7 candidate versus original B0

State: launched once at `2026-09-22T14:45:38.550230+00:00`, tmux
`scion-r8-r7-final-b0-20260922`, driver PID 117138, under the user's
experiment-analysis/optimization request. The frozen design below is unchanged.
The normal `input.json` points to both output-local source snapshots and the
declared original source directories; provider calls are zero. The driver has
passed its strict canary and entered expanded screening (real B-n34-k5 calls
observed). No terminal or completed formal-stage result yet at this launch
check. Do not infer improvement from startup or partial metrics.

## Question and source selection

Does R7's final complete branch-C candidate improve on original B0 under the
existing full fixed-candidate funnel, and, conditional on passing, retain that
effect on the still-unopened independent final block?

The [R7 postrun](v04-cvrp-r7-autonomous-source-continuation-postrun-20260922.md)
records a positive initial screen (case W/L/T 2/0/1, median +40, CI [0,608.5])
without expansion, validation, frozen evidence or promotion. tai100a improved
at both seeds with the changed ALNS code active. The large-case gain is not
attributable to those changes: both arms ran zero ALNS iterations and the
unchanged comparator varied strongly across repeats. These are reasons for one
prospective, counterbalanced check, not for declaring improvement or selecting
new thresholds. No additional candidate or mechanism is chosen after R8 starts.

Exact ordinary source inputs, used directly without a host-authored edit:

- Baseline: `/home/clawd/research/scion-experiments/v04-cvrp-r6-minus-2for1-b0-20260921/input_snapshots/baseline`,
  the complete original B0 preserved by R6.
- Candidate: `/home/clawd/research/scion-experiments/v04-cvrp-r7-autonomous-source-continuation-20260921/candidate_workspaces/candidate-3bsvzm8k`,
  the complete source actually evaluated in R7 step 13, branch
  `8485adcb-706a-4d81-a2fd-29cee75c0aa3`.

Both contain the same 100 ordinary files, ignoring generated caches. Exactly
`policies/baseline_modules/destroy_repair.py`, `local_search.py`, and
`scheduler.py` differ. The candidate retains the ordinary R6 starting bundle
plus R7 assignment-opportunity removal and bounded ejection repair, with the
randomized-regret arm removed from the active portfolio. Its unused helper and
import remain untouched so the full tree is exactly the evaluated one.

The fixed driver makes its normal read-only output-local snapshots and serial
disposable arm workspaces. It checks complete source equality/scope directly,
not a patch chain or authority digest. R7 is terminal and is not resumed; R8
neither restores its branch state nor backfills its pending comparison with
minus-2-for-1. B0 is a different comparator and this is a new estimand.

## Frozen science and exposure

- [Protocol](inputs/v04-cvrp-r8-r7-final-b0-protocol.yaml): R7 settings unchanged
  except version and canary seed.
- [Main split](inputs/v04-cvrp-r7-autonomous-source-continuation-split.yaml):
  reuse the exact R6/R7 6 screening / 6 validation / 12 frozen partition.
- [Main seeds](inputs/v04-cvrp-r8-r7-final-b0-seeds.yaml).
- [Retained split](inputs/v04-cvrp-r6-minus-2for1-b0-retained-split.yaml):
  reuse the exact pre-R3 reserved 12 cases, still unexecuted.
- [Retained seeds](inputs/v04-cvrp-r8-r7-final-b0-retained-seeds.yaml).

The six screening cases are outcome-known adaptive development, **not fresh
cases**. R6/R7 did not execute their validation or frozen partitions. The final
retained block is separate from those partitions and remains unopened. No
held-out outcomes enter candidate selection or another H/C context.

Seeds are the first eleven primes above 60,000, in the following stage order;
they are not outcome-selected and are disjoint from the R3–R7 declared ledgers.

| Stage | Cases | Seeds | Pairs |
|---|---:|---|---:|
| expanded screening | 6 | 60013,60017,60029,60037 | 24 |
| validation | 6 | 60041,60077 | 12 |
| frozen | 12 | 60083,60089 | 24 |
| independent retained | 12 | 60091,60101 | 24 |
| canary, safety only | 1 | 60103 | 1 |

The fixed driver goes directly to complete expanded screening after the strict
canary. The familiar canary is not effect evidence. All formal stages use the
existing explicit AB/BA parity schedule (12 AB and 12 BA pairs in expanded
screening), executing both arms independently. A is B0, B is the candidate.
Raw scheduled/actual order, objective, feasibility and bounded failures remain
in the normal metrics. Unlike R7's default champion-first path, this schedule
counterbalances order; it does not guarantee identical instantaneous host load.

Unchanged gates: complete pairs, feasibility, fleet protection, case-paired
median distance effects, screening practical delta 2.0, validation delta 1.0,
nonnegative bootstrap lower bound, net case score >= 0.25, loss rate <= 0.20.
No modification to `SCREENING_FAIL_CASE_QUALITY`, no telemetry/novelty gate,
and no retuning, automatic repeat or additional arm after observing results.
Validation, frozen and retained execute only after the preceding necessary
pass. Comparator/shared/bilateral failure is incomplete evidence, not a
candidate defeat. Historical negative Decisions remain unchanged.

This is provider-free: no H/C export, model call, synthetic proposal or repeated
proposal Contract/Verification. The candidate already passed those boundaries
in R7; the existing fixed driver checks inputs/scope, strict canary, Protocol,
Safe Features and deterministic Decision. Only `PROMOTED_RETAINED` supports
retained improvement of this exact bundle over B0 on the declared populations.
It cannot establish isolated component causality, global CVRP superiority or
the original eight-seed final matrix. A negative keeps CVRP/v0.4 open.

## Runtime, resources and checks

Main checkout `v0.4-dev`, HEAD `75ce0265`; runtime implementation is unchanged
from `e405bfd2`. R8 preparation changes documentation, three prospective YAML
inputs and an input test only. They are frozen before launch; no commit or
remote push is required to endow an ordinary source value with authority.
Do not modify runtime, inputs, sources or datasets while measurement is live.

Reuse the already checked read-only R6 data root. Subject limits are unchanged:
DIMENSION <=100/200/350/700/1001 gets 30/45/60/90/120 seconds, canary 10 seconds,
subprocess guard 30 seconds, memory 4096 MiB, single-threaded serial execution.
Maximum: 85 pairs, 170 subprocesses, 10,160 nominal / 15,260 guarded subject
seconds, outer hardwall 21,600 seconds. Screening plus canary needs at most 50
subprocesses and 2,660 nominal seconds; later work is conditional.

Before launch, run prospective-input and existing fixed-funnel tests, perform
the read-only `--check`, compare both ordinary source values, verify no live
solver/tests/cleanup, and ensure the fresh output and tmux session are absent.
No core/adapter/Protocol implementation changed, so no concurrent full-suite
or extra Warehouse solver control is needed; the P1b 2397-pass full suite and
existing Warehouse A/A wiring control remain implementation evidence.

Prelaunch checks completed: 27 fixed-funnel/R7/R8 tests passed (0.55 seconds
after formatting); targeted Ruff F/E9 and `git diff --check` passed. Read-only
`--check` returned `PREPARED`, parsed all 37 case inputs including canary, and
validated the exact three-file difference and the 170-subprocess maximum without
creating output or executing a solver. The prior R3, R4, R5, R6 and R7 seed
ledgers contain none of the eleven new seeds. Ordinary live checks found only
dead old experiment panes, no active solver or tests, and 64 GiB disk available.

Output: `/home/clawd/research/scion-experiments/v04-cvrp-r8-r7-final-b0-20260922`.
tmux: `scion-r8-r7-final-b0-20260922`. Run exactly once; do not restart terminal
state. Preserve all original R7 and R6 evidence.

## Frozen invocation

From the main checkout, with no credentials or provider configuration:

```bash
/usr/bin/env -i \
  PATH=/home/clawd/miniconda3/envs/claw/bin:/usr/bin:/bin \
  LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
  PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion:/home/clawd/.local/lib/python3.12/site-packages:/home/clawd/miniconda3/envs/claw/lib/python3.12/site-packages \
  OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  SCION_PROBLEM_DATA_ROOT=/home/clawd/research/scion-experiment-inputs/v04-cvrp-r6-minus-2for1-b0-20260921/data \
  /home/clawd/miniconda3/envs/claw/bin/python -S -B \
  /home/clawd/research/or-autoresearch-agent/scion/run_fixed_candidate_funnel.py \
  --label v04-cvrp-r8-r7-final-b0-20260922 \
  --baseline-source /home/clawd/research/scion-experiments/v04-cvrp-r6-minus-2for1-b0-20260921/input_snapshots/baseline \
  --candidate-source /home/clawd/research/scion-experiments/v04-cvrp-r7-autonomous-source-continuation-20260921/candidate_workspaces/candidate-3bsvzm8k \
  --problem-spec /home/clawd/research/scion-experiments/v04-cvrp-r6-minus-2for1-b0-20260921/input_snapshots/baseline/problem-v1.yaml \
  --protocol /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r8-r7-final-b0-protocol.yaml \
  --split /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r7-autonomous-source-continuation-split.yaml \
  --seeds /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r8-r7-final-b0-seeds.yaml \
  --retained-split /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r6-minus-2for1-b0-retained-split.yaml \
  --retained-seeds /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r8-r7-final-b0-retained-seeds.yaml \
  --changed-file policies/baseline_modules/destroy_repair.py \
  --changed-file policies/baseline_modules/local_search.py \
  --changed-file policies/baseline_modules/scheduler.py \
  --selected-surface solver_design --time-limit-sec 30 --timeout-guard-sec 30 \
  --outer-hardwall-sec 21600 --memory-mb 4096 \
  --output-dir /home/clawd/research/scion-experiments/v04-cvrp-r8-r7-final-b0-20260922
```

Appending `--check` is read-only preparation: no solver or provider call and no
output creation. Explicit imports avoid the server's older editable checkout.
Read `terminal.json` and its exact metric references after completion; while
live use ordinary progress and process checks without opening original SQLite.
