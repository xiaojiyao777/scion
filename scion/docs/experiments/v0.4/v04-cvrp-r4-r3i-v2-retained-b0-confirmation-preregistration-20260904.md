# CVRP R4 R3i-v2 retained-B0 confirmation preregistration

**State:** prepared, checked, not launched

**Label:** `v04-cvrp-r4-r3i-v2-retained-b0-confirmation-20260904`

**External input:**
`/home/clawd/research/scion-experiment-inputs/v04-cvrp-r4-r3i-v2-retained-b0-confirmation-20260904`

**Reserved output:**
`/home/clawd/research/scion-experiments/v04-cvrp-r4-r3i-v2-retained-b0-confirmation-20260904`

## Question and fixed estimand

Does the exact cumulative R3i `champion_v2` source retain a positive feasible
CVRP distance effect when compared directly with the exact B0 source from
which R3i started, on fresh case-seed pairs and finally on the outcome-blind
final case block reserved before R3?

This is a provider-free fixed-candidate comparison. It does not ask H or C for
a proposal, change or select code, or infer an isolated effect for any one of
the four changes accumulated in `champion_v2`. The candidate-level estimand is
the complete three-file bundle. The exact ordinary sources are:

- B0: `/home/clawd/research/or-autoresearch-agent-r3i-dev/scion/scion/problems/cvrp`;
- candidate: `/home/clawd/research/scion-experiments/v04-cvrp-r3i-normal-k1-sol-20260903-r1/champions/champion_v2`.

The external input root contains ordinary read-only `baseline/`, `candidate/`
and `data/` copies. Direct byte comparison must report exactly these changed
paths and no others:

- `policies/baseline_modules/destroy_repair.py`;
- `policies/baseline_modules/local_search.py`;
- `policies/baseline_modules/scheduler.py`.

These are ordinary scientific inputs. There is no digest, source identity,
signature, registration, lease, receipt or trust lifecycle. The fixed driver
copies the two source trees once into its private output-local snapshots if a
live run is later started.

## Outcome-unseen population construction

The audit read all 68 non-SQLite metric files from R3 through R3i. Their union
contains 288 executed formal case-seed pairs: all 36 cases and 24 seeds in the
R3 formal screening, validation and frozen ledgers. Every case in the R4
effect matrices below is outside that 36-case union, so effect-population
overlap is zero at both the case and case-seed levels. All R4 main-funnel
seeds are also outside the 24-seed union.

The controlled synthetic canary is intentionally reused as a non-estimand
execution and safety smoke check. It uses the previously unseen seed `10091`,
is excluded from every quality aggregate and scientific effect claim, and
therefore does not weaken the outcome-unseen effect population.

The 24 main-funnel cases were selected without solver outcomes. Starting from
the local CVRPLIB catalog, the deterministic rule is:

1. retain families `A`, `B`, `E`, `F`, `M`, `P`, `X` and `tai` with both a
   `.vrp` instance and `.sol` reference, dimension 30 through 1001;
2. exclude the 36 R3 formal cases and the 12 pre-R3 reserved final cases;
3. for names carrying `-k`, require `k / dimension <= 0.15` to avoid making a
   construction-edge stress test the confirmation estimand;
4. split into small 30-100, medium 101-350 and large 351-1001, then sort each
   stratum by `(dimension, canonical relative path)`;
5. from a stratum of size `N`, take the eight distinct zero-based indices
   `floor((i + 0.5) * N / 8)` for `i=0..7`. The eligible stratum sizes are
   46, 33 and 22, giving indices `2,8,14,20,25,31,37,43`,
   `2,6,10,14,18,22,26,30`, and `1,4,6,9,12,15,17,20`;
6. assign ordinals 0 and 4 to screening, 1 and 5 to validation, and
   2, 3, 6 and 7 to frozen. Thus every main stage is size-stratified without
   looking at B0 or candidate results.

The main-funnel seeds are the first nine primes above 10,000, assigned in
stage order: four screening seeds, two validation seeds, two frozen seeds and
one canary seed. The retained seeds are the first two entries of the final
ledger frozen before R3, `157` and `163`. Using this fixed prefix bounds the
run while preserving outcome blindness; it is a moderate confirmation rather
than the full original eight-seed final matrix.

## Frozen population

| Step | Small cases | Medium cases | Large cases | Seeds | Pairs |
|---|---|---|---|---|---:|
| canary | synthetic controlled canary | - | - | `10091` | 1 |
| expanded screening | `A-n34-k5`, `A-n53-k7` | `tai100b`, `X-n186-k15` | `X-n367-k17`, `X-n573-k30` | `10007,10009,10037,10039` | 24 |
| validation | `A-n39-k5`, `A-n61-k9` | `X-n110-k13`, `X-n214-k11` | `X-n393-k38`, `X-n685-k75` | `10061,10067` | 12 |
| frozen | `A-n45-k6`, `B-n50-k7`, `B-n68-k9`, `tai75a` | `X-n134-k13`, `X-n153-k22`, `X-n270-k35`, `X-n322-k28` | `X-n429-k61`, `X-n480-k70`, `X-n766-k71`, `X-n957-k87` | `10069,10079` | 24 |
| retained B0 | `A-n64-k9`, `B-n63-k10`, `P-n70-k10`, `tai75c` | `X-n139-k10`, `X-n261-k13`, `tai150b`, `X-n308-k13` | `X-n561-k42`, `X-n701-k44`, `X-n1001-k43`, `X-n856-k95` | `157,163` | 24 |
| **maximum** |  |  |  | 11 distinct seeds | **85** |

The retained case list is exactly the 12-case outcome-blind final block in
`scion/scion/problems/cvrp/formal/manifests/final.json`, in its original order.
It was fixed before R3 and excluded from the R3-R3i Protocol splits and
proposal context. The first three screening cases contain one case per size
stratum and form the initial screen; Protocol may only add the other three
cases and two seeds as the declared expansion.

The tracked scientific inputs are:

- [`v04-cvrp-r4-r3i-v2-retained-b0-confirmation-protocol.yaml`](inputs/v04-cvrp-r4-r3i-v2-retained-b0-confirmation-protocol.yaml);
- [`v04-cvrp-r4-r3i-v2-retained-b0-confirmation-split.yaml`](inputs/v04-cvrp-r4-r3i-v2-retained-b0-confirmation-split.yaml);
- [`v04-cvrp-r4-r3i-v2-retained-b0-confirmation-seeds.yaml`](inputs/v04-cvrp-r4-r3i-v2-retained-b0-confirmation-seeds.yaml);
- [`v04-cvrp-r4-r3i-v2-retained-b0-confirmation-retained-split.yaml`](inputs/v04-cvrp-r4-r3i-v2-retained-b0-confirmation-retained-split.yaml);
- [`v04-cvrp-r4-r3i-v2-retained-b0-confirmation-retained-seeds.yaml`](inputs/v04-cvrp-r4-r3i-v2-retained-b0-confirmation-retained-seeds.yaml).

## Protocol, resources and claim boundary

The conditional path is strict canary, expanded screening, validation, frozen
promotion, then retained comparison of the copied promoted candidate directly
against B0. The existing case-level Protocol gates are unchanged: complete
paired evidence, the lexicographically protected `fleet_violation` objective,
practical distance thresholds, nonnegative bootstrap lower bound, minimum net
case score and maximum loss rate. The driver also requires zero failed pairs
for a positive retained terminal. These are scientific gates, not operational
permission gates.

The maximum matrix has 85 case-seed pairs and 170 serial solver subprocesses.
Dimension-only limits are 10 seconds for canary, then 30/45/60/90/120 seconds
for dimensions at most 100/200/350/700/1001. Exact nominal arithmetic is:

- canary: `20` subject-seconds;
- expanded screening: `2 arms * 4 seeds * 330 = 2,640`;
- validation: `2 arms * 2 seeds * 345 = 1,380`;
- frozen: `2 arms * 2 seeds * 750 = 3,000`;
- retained: `2 arms * 2 seeds * 780 = 3,120`;
- total nominal subject time: `10,160` seconds;
- 30-second per-process guard: `5,100` seconds;
- guarded subject envelope: `15,260` seconds;
- outer hardwall: `21,600` seconds; memory: `4,096 MiB`; concurrency: one.

Provider, H, C, patch generation, Contract and Verification counts are zero.
The only positive terminal is `completed / PROMOTED_RETAINED`. It supports the
narrow claim that the exact cumulative R3i v2 bundle retained an improvement
over its exact starting B0 on this declared funnel and the two-seed prefix of
the reserved final block. It does not isolate the 2-for-1 change, estimate an
individual mechanism effect, complete the original eight-seed final matrix,
or establish global CVRP or production superiority.

## Checked command and unexecuted live command

Preparation uses the same argument vector as a later live run. `--check`
performs source-difference, research-surface, population, path, parser and
resource validation and creates no output directory or solver process.

```bash
set -euo pipefail

REPO=/home/clawd/research/or-autoresearch-agent
SCION_ROOT="$REPO/scion"
CONFIG_ROOT="$SCION_ROOT/docs/experiments/v0.4/inputs"
LABEL=v04-cvrp-r4-r3i-v2-retained-b0-confirmation-20260904
INPUT_ROOT="/home/clawd/research/scion-experiment-inputs/$LABEL"
OUTPUT="/home/clawd/research/scion-experiments/$LABEL"
PY=/home/clawd/miniconda3/envs/claw/bin/python

COMMON_ENV=(
  HOME=/home/clawd
  PATH=/usr/bin:/bin
  LANG=C.UTF-8
  LC_ALL=C.UTF-8
  PYTHONDONTWRITEBYTECODE=1
  PYTHONUNBUFFERED=1
  PYTHONPATH="$SCION_ROOT:/home/clawd/.local/lib/python3.12/site-packages:/home/clawd/miniconda3/envs/claw/lib/python3.12/site-packages"
  SCION_PROBLEM_DATA_ROOT="$INPUT_ROOT/data"
  OMP_NUM_THREADS=1
  OPENBLAS_NUM_THREADS=1
  MKL_NUM_THREADS=1
  NUMEXPR_NUM_THREADS=1
)
ARGS=(
  "$SCION_ROOT/run_fixed_candidate_funnel.py"
  --label "$LABEL"
  --baseline-source "$INPUT_ROOT/baseline"
  --candidate-source "$INPUT_ROOT/candidate"
  --problem-spec "$INPUT_ROOT/baseline/problem-v1.yaml"
  --protocol "$CONFIG_ROOT/v04-cvrp-r4-r3i-v2-retained-b0-confirmation-protocol.yaml"
  --split "$CONFIG_ROOT/v04-cvrp-r4-r3i-v2-retained-b0-confirmation-split.yaml"
  --seeds "$CONFIG_ROOT/v04-cvrp-r4-r3i-v2-retained-b0-confirmation-seeds.yaml"
  --retained-split "$CONFIG_ROOT/v04-cvrp-r4-r3i-v2-retained-b0-confirmation-retained-split.yaml"
  --retained-seeds "$CONFIG_ROOT/v04-cvrp-r4-r3i-v2-retained-b0-confirmation-retained-seeds.yaml"
  --changed-file policies/baseline_modules/destroy_repair.py
  --changed-file policies/baseline_modules/local_search.py
  --changed-file policies/baseline_modules/scheduler.py
  --selected-surface solver_design
  --time-limit-sec 30
  --timeout-guard-sec 30
  --outer-hardwall-sec 21600
  --memory-mb 4096
  --output-dir "$OUTPUT"
)

/usr/bin/env -i "${COMMON_ENV[@]}" "$PY" -S -B "${ARGS[@]}" --check
test ! -e "$OUTPUT"

# Prepared but deliberately not run in this task:
# /usr/bin/env -i "${COMMON_ENV[@]}" "$PY" -S -B "${ARGS[@]}"
```

Monitoring a later run is read-only. No retry, population change or source
substitution belongs to this fixed estimand.
