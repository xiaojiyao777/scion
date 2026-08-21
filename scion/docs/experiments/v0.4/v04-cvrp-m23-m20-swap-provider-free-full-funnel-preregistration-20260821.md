# CVRP M23 M20 `_swap` provider-free full-funnel preregistration and result

**State:** `completed / NOT_CONFIRMED`

**Label:** `v04-cvrp-m23-m20-swap-provider-free-full-funnel-20260821`

**External input:**
`/home/clawd/research/scion-experiment-inputs/v04-cvrp-m23-m20-swap-provider-free-full-funnel-20260821`

**Preserved output:**
`/home/clawd/research/scion-experiments/v04-cvrp-m23-m20-swap-provider-free-full-funnel-20260821`

## Observed terminal result

The authorized one-shot completed at `expanded_screening` with terminal type
`NOT_CONFIRMED`. The strict canary passed. Expanded screening completed all
24 declared pairs with 24 valid pairs and zero candidate, champion, shared or
bilateral failures. The aggregate result was two wins, zero losses and four
ties: `X-n439-k37` had paired-effect median `+27.0`, `X-n502-k39` had
`+106.5`, and the other four cases tied. Overall median delta was `0.0`, the
interval was `[0.0, 66.75]`, and win rate was `1/3`.

Protocol returned `unclear`; deterministic Decision returned
`continue_explore` with
`SCREENING_EXPAND_EXHAUSTED_CASE_LEVEL_UNCERTAIN`. Median runtime ratio was
`1.0002066`, median runtime delta was `+8.5 ms`, and there were no protected-
objective regressions. The terminal counters were 50 solver subprocesses,
2,420 nominal subject-seconds and 3,170 guarded subject-seconds, all within the
frozen envelope. Validation, frozen evaluation, promotion and retained
comparison were not run. The output root above remains preserved, the one-shot
is consumed, and there is no retry, resume or repair of this estimand.

## Scientific question and scope

Does the exact M20 directed `_swap` candidate retain its positive initial-screen
signal when the already-materialized code is evaluated, without another Agent
proposal, through complete-pair expanded screening, validation, frozen,
deterministic promotion and a separately declared retained comparison?

This is one provider-free fixed-candidate estimand. It is not another M20
attempt and does not generate or select an H, C, patch, mechanism, target or
replacement candidate. The existing
[`run_fixed_candidate_funnel.py`](../../../run_fixed_candidate_funnel.py) is the
only live entry. Contract and Verification are zero because the input candidate
is the exact already-verified M20 source; Protocol, Safe Features and
deterministic Decision retain their normal authority over the new paired
evidence.

M20's original run and its positive initial screen remain recorded in the
[`M20 preregistration`](v04-cvrp-m20-mechanism-frontier-continuation-preregistration-20260820.md).
This new run does not repair, resume or complete that historical campaign. It
uses a new label, immutable external inputs and a fresh output directory.

## Exact ordinary source inputs

The external input root contains three ordinary read-only directories:

- `baseline/`: an ordinary 98-file materialization of the CVRP problem package
  at the M20 carrier `ce6c2c26`;
- `candidate/`: an ordinary 98-file copy of the historical M20 verified
  provisional source;
- `data/`: the 30 external formal CVRP `.vrp`/`.sol` files used by the tracked
  screening, validation, frozen and retained populations.

Direct full-file byte comparison, without a digest or identity wrapper, must
show exactly one changed path:
`policies/baseline_modules/local_search.py`. The input directories are
scientific values, not signed, registered, leased or accepted objects. The
driver copies baseline and candidate once into private read-only
`output/input_snapshots/` before any solver dispatch and thereafter evaluates
only those private snapshots. It never writes the external input root.

The five tracked experiment inputs are:

- [`v04-cvrp-m23-m20-swap-full-funnel-protocol.yaml`](inputs/v04-cvrp-m23-m20-swap-full-funnel-protocol.yaml);
- [`v04-cvrp-m23-m20-swap-full-funnel-split.yaml`](inputs/v04-cvrp-m23-m20-swap-full-funnel-split.yaml);
- [`v04-cvrp-m23-m20-swap-full-funnel-seeds.yaml`](inputs/v04-cvrp-m23-m20-swap-full-funnel-seeds.yaml);
- [`v04-cvrp-m23-m20-swap-full-funnel-retained-split.yaml`](inputs/v04-cvrp-m23-m20-swap-full-funnel-retained-split.yaml);
- [`v04-cvrp-m23-m20-swap-full-funnel-retained-seeds.yaml`](inputs/v04-cvrp-m23-m20-swap-full-funnel-retained-seeds.yaml).

They are ordinary tracked configuration, not authorization manifests. Their
safe data root is the external `data/` directory above. The tiny canary is
`data/tiny_canary.json` already present in both ordinary source trees; it is not
part of the 30-file external formal-data copy. No formal case data is copied
into the repository or candidate source.

## Frozen population

The complete population is fixed before this exact candidate is run:

| Step | Cases | Seeds | Pairs | Subject subprocesses |
|---|---|---|---:|---:|
| strict canary | `data/tiny_canary.json` | `6419` | 1 | 2 |
| expanded screening | `A-n39-k5`, `P-n23-k8`, `X-n439-k37`, `A-n63-k10`, `P-n70-k10`, `X-n502-k39` | `6858`, `9488`, `8155`, `5774` | 24 | 48 |
| validation | `A-n48-k7`, `P-n55-k15`, `X-n313-k71` | `6241`, `8615` | 6 | 12 |
| frozen | `A-n62-k8`, `P-n55-k8`, `X-n393-k38` | `8498`, `7903` | 6 | 12 |
| retained against the original baseline | `X-n162-k11`, `X-n204-k19`, `X-n561-k42` | `4741`, `3617` | 6 | 12 |
| **Maximum** | 16 case uses across five steps | 11 distinct seeds | **43** | **86** |

The expanded-screening cases are the union of M21's reserved validation and
frozen cases, crossed with the union of their four reserved seeds. Validation
and frozen preserve M20's respective reserved case/seed sets. Retained uses
M22's reserved validation set. The source records are the
[`M21 preregistration`](v04-cvrp-m21-strict-expansion-continuation-preregistration-20260820.md)
and
[`M22 preregistration`](v04-cvrp-m22-post-infra-continuation-preregistration-20260820.md).

Every case and seed was declared before this M23 run, and none of the 43
declared case-seed pairs has been executed against the exact M20 candidate.
Individual cases, including the tiny canary with a different seed, may have
appeared in earlier work. This is an outcome-unseen boundary for the exact
paired estimand only. It is not an independent population: the M20 candidate
was selected after its positive development result, later reservations belong
to the same adaptive research lineage, and M23 combines and assigns those
reservations after observing prior campaign outcomes. The run therefore cannot
claim independent discovery, an unbiased mechanism estimate or global CVRP
generalization.

## Protocol and progression

The main chain is fixed as:

```text
strict complete-pair canary
  -> expanded screening (6 cases x 4 seeds)
  -> validation (3 x 2)
  -> frozen (3 x 2)
  -> deterministic PROMOTE
  -> one output-local read-only promoted_candidate snapshot
  -> retained comparison against the original baseline (3 x 2)
```

No threshold, order, case, seed, source or time limit may change after launch.
The driver records an ordinary per-subject solver failure and finishes the
current formal stage's full declared pair matrix before stopping. Candidate-only
failure remains candidate evidence and reaches deterministic Decision after
that stage. Champion-only, shared or bilateral failure produces
`completed_incomplete / INCOMPLETE_COMPARATOR_EVIDENCE`; at a main-chain stage
Decision is skipped and no later stage runs. Strict canary incompleteness stops
before Protocol. Retained comparator incompleteness stops at `retained` after
the already-complete frozen promotion and is not reported as
`PROMOTED_NOT_RETAINED`.

Protocol may run at most four times: expanded screening, validation, frozen and
retained. Safe Feature extraction and Decision may run at most three times:
expanded screening, validation and frozen. Retained evidence is interpreted by
the fixed driver and cannot reopen or alter the prior promotion Decision.

## Frozen resource envelope

Execution is serial with concurrency one. Provider, H, C, patch, Hypothesis
Contract, Patch Contract and Verification counts are all exactly zero.

| Resource | Maximum |
|---|---:|
| solver subprocesses | 86 |
| nominal subject seconds | 4,280 |
| per-subprocess timeout guard | 15 seconds |
| guarded subject seconds | 5,570 |
| outer hardwall | 7,200 seconds |
| subprocess memory | 4,096 MB |
| concurrent solver subprocesses | 1 |
| Protocol calls | 4 |
| Safe Feature / Decision calls | 3 each |

The nominal arithmetic is fixed by the tracked time-limit rules:

- canary: `2 * 10 = 20` subject-seconds;
- expanded screening: `2 * 4 * (30 + 30 + 90 + 30 + 30 + 90) = 2,400`;
- validation: `2 * 2 * (30 + 30 + 60) = 480`;
- frozen: `2 * 2 * (30 + 30 + 90) = 600`;
- retained: `2 * 2 * (45 + 60 + 90) = 780`;
- total: `4,280`, with `86 * 15 = 1,290` guard seconds and guarded total
  `5,570`.

Any dispatch that would exceed the declared solver, nominal or guarded limit
fails closed. The outer hardwall covers source snapshotting, every scientific
stage and the promotion copy. The single atomic `terminal.json` write occurs
after the guarded execution block, including when the block terminates by
hardwall or signal.

## Terminal and claim boundary

The sole positive terminal is `completed / PROMOTED_RETAINED`. It requires all
43 pairs and all 86 subject subprocesses, complete comparator evidence at every
step, the expected deterministic Decision at each main-chain stage, successful
promotion, a passing retained comparison with zero failed pairs, and exact
final resource counters.

Every other terminal is non-positive:

- canary or a complete Protocol/Decision quality failure is
  `completed / NOT_CONFIRMED` at that step;
- comparator-incomplete evidence is
  `completed_incomplete / INCOMPLETE_COMPARATOR_EVIDENCE` at canary, a
  main-chain stage or retained as applicable;
- a complete frozen promotion followed by a complete failing retained gate is
  `completed / PROMOTED_NOT_RETAINED`;
- outer hardwall or signal is typed `interrupted`;
- resource exhaustion, unavailable source, promoted-copy mismatch,
  positive-matrix mismatch or another typed scientific failure is `failed`;
- an unexpected exception is `failed / UNHANDLED_EXCEPTION`;
- preparation or output-location failure occurs before live execution and
  supplies no solver evidence.

Only `PROMOTED_RETAINED` supports the narrow claim that this exact M20 source
passed every aggregate stage gate against the ordinary `ce6c2c26` baseline and
retained on the separate declared population. Even that result does not prove
independent discovery, isolated family causality, global generalization,
production readiness or v0.4 completion. Negative and incomplete terminals are
preserved as evidence and do not authorize a changed population, threshold,
candidate or source.

## Preparation, standing authorization and source cleanliness

The user's 2026-08-21 instruction grants standing authorization for exactly one
live invocation under this label after all of the following are true:

1. the committed checkout contains the already-reviewed fixed-funnel driver,
   and one clean preparation commit contains the five YAML inputs and this
   preregistration;
2. the tracked worktree and index are clean;
3. the direct `297ec595..HEAD` diff under `scion/scion` and
   `scion/run_fixed_candidate_funnel.py` has been read and accepted as the exact
   production/driver change;
4. both external 98-file source trees and the external data root are read-only,
   the direct byte comparison has exactly the one declared `local_search.py`
   difference, every config/case/solution loads, and the provider-/solver-free
   `--check` returns `PREPARED` with the frozen resource envelope;
5. the live output path does not exist.

No additional launch confirmation is required after those conditions pass.
A failed preflight performs no live work and blocks launch until a clean prep
commit passes again. Once the fresh output is created and live execution starts,
the one-shot is consumed: there is no retry, resume, repair, replacement,
alternate candidate, source substitution, population/seed addition or automatic
next rung.

Repository cleanliness is intentionally limited to the ordinary tracked
worktree/index checks and direct Git diff above. Git revision is an ordinary
source reference. This design adds no source acceptance, mirror, hash gate,
receipt, identity, lease, signing, registration, nonce, refreeze or closure
lifecycle.

## Frozen preflight and live command

The direct Git diff is human review material, not a generated authorization
artifact:

```bash
set -euo pipefail
cd /home/clawd/research/or-autoresearch-agent

git diff --quiet
git diff --cached --quiet
git diff --check 297ec595..HEAD -- \
  scion/scion scion/run_fixed_candidate_funnel.py
git diff 297ec595..HEAD -- \
  scion/scion scion/run_fixed_candidate_funnel.py
```

After that direct review, use the same frozen argument vector first with
`--check` and then exactly once without it:

```bash
set -euo pipefail

REPO=/home/clawd/research/or-autoresearch-agent
SCION_ROOT="$REPO/scion"
CONFIG_ROOT="$SCION_ROOT/docs/experiments/v0.4/inputs"
CONFIG_REL=scion/docs/experiments/v0.4/inputs
LABEL=v04-cvrp-m23-m20-swap-provider-free-full-funnel-20260821
INPUT_ROOT="/home/clawd/research/scion-experiment-inputs/$LABEL"
OUTPUT="/home/clawd/research/scion-experiments/$LABEL"
PY=/home/clawd/miniconda3/envs/claw/bin/python
BASELINE="$INPUT_ROOT/baseline"
CANDIDATE="$INPUT_ROOT/candidate"
CHANGED_FILE=policies/baseline_modules/local_search.py

cd "$REPO"
git diff --quiet
git diff --cached --quiet
git ls-files --error-unmatch \
  scion/docs/experiments/v0.4/v04-cvrp-m23-m20-swap-provider-free-full-funnel-preregistration-20260821.md \
  "$CONFIG_REL/v04-cvrp-m23-m20-swap-full-funnel-protocol.yaml" \
  "$CONFIG_REL/v04-cvrp-m23-m20-swap-full-funnel-split.yaml" \
  "$CONFIG_REL/v04-cvrp-m23-m20-swap-full-funnel-seeds.yaml" \
  "$CONFIG_REL/v04-cvrp-m23-m20-swap-full-funnel-retained-split.yaml" \
  "$CONFIG_REL/v04-cvrp-m23-m20-swap-full-funnel-retained-seeds.yaml" \
  >/dev/null
test ! -e "$OUTPUT"
test -d "$BASELINE" && test ! -L "$BASELINE"
test -d "$CANDIDATE" && test ! -L "$CANDIDATE"
test -d "$INPUT_ROOT/data" && test ! -L "$INPUT_ROOT/data"
test "$(find "$BASELINE" -type f | wc -l)" -eq 98
test "$(find "$CANDIDATE" -type f | wc -l)" -eq 98
test "$(find "$INPUT_ROOT/data" -type f | wc -l)" -eq 30
test "$(find "$INPUT_ROOT/data" -type f -name '*.vrp' | wc -l)" -eq 15
test "$(find "$INPUT_ROOT/data" -type f -name '*.sol' | wc -l)" -eq 15
test -z "$(find "$INPUT_ROOT" -perm /222 -print -quit)"
test -z "$(find "$INPUT_ROOT" -type l -print -quit)"

CHANGED=()
while IFS= read -r -d '' BASE_FILE; do
  RELATIVE="${BASE_FILE#"$BASELINE"/}"
  test -f "$CANDIDATE/$RELATIVE"
  if ! cmp -s "$BASE_FILE" "$CANDIDATE/$RELATIVE"; then
    CHANGED+=("$RELATIVE")
  fi
done < <(find "$BASELINE" -type f -print0 | sort -z)
test "${#CHANGED[@]}" -eq 1
test "${CHANGED[0]}" = "$CHANGED_FILE"

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
DRIVER_ARGS=(
  "$SCION_ROOT/run_fixed_candidate_funnel.py"
  --label "$LABEL"
  --baseline-source "$BASELINE"
  --candidate-source "$CANDIDATE"
  --problem-spec "$BASELINE/problem-v1.yaml"
  --protocol "$CONFIG_ROOT/v04-cvrp-m23-m20-swap-full-funnel-protocol.yaml"
  --split "$CONFIG_ROOT/v04-cvrp-m23-m20-swap-full-funnel-split.yaml"
  --seeds "$CONFIG_ROOT/v04-cvrp-m23-m20-swap-full-funnel-seeds.yaml"
  --retained-split "$CONFIG_ROOT/v04-cvrp-m23-m20-swap-full-funnel-retained-split.yaml"
  --retained-seeds "$CONFIG_ROOT/v04-cvrp-m23-m20-swap-full-funnel-retained-seeds.yaml"
  --changed-file "$CHANGED_FILE"
  --selected-surface solver_design
  --time-limit-sec 30
  --timeout-guard-sec 15
  --outer-hardwall-sec 7200
  --memory-mb 4096
  --output-dir "$OUTPUT"
)

# Provider-/solver-free preparation. It creates no output directory.
/usr/bin/env -i "${COMMON_ENV[@]}" "$PY" -S -B \
  "${DRIVER_ARGS[@]}" --check
test ! -e "$OUTPUT"

# Standing authorization permits this line exactly once after PREPARED passes.
/usr/bin/env -i "${COMMON_ENV[@]}" "$PY" -S -B \
  "${DRIVER_ARGS[@]}"
```

The live output must contain one ordinary `input.json`, private source
snapshots, Protocol metrics, an optional `promoted_candidate/` only after a
frozen `PROMOTE`, and one `terminal.json`. These files are scientific evidence,
not a second authority ledger. Monitoring is read-only and never launches,
retries or mutates the run.
