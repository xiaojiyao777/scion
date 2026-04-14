# Scion v0.2 — Refined Delivery Plan

*Date: 2026-04-09*  
*Based on code review + existing v0.2 design/task manifest*  
*Branch: `v0.2-dev`*

---

## 0. Purpose

This note refines the existing v0.2 design into a more executable landing plan.

It does **not** replace:
- `scion-v0.2-design.md`
- `scion-v0.2-task-manifest.md`

Instead, it locks a few implementation decisions that became clear only after re-reading the actual v0.1 codebase.

---

## 1. Code-review corrections (important)

### 1.1 Already implemented in v0.1

The following are **already present** and should NOT be re-designed in v0.2:

- `ObjectiveBreakdown`
- `PairwiseCaseFeedback`
- `CaseAggregateFeedback`
- `ScreeningPatternSummary`
- `ProtocolResult.case_feedback / pattern_summary`
- `compare_with_breakdown()` in `protocol/evaluation.py`
- screening-time case aggregation + pattern summary generation in `protocol/experiment.py`
- case feedback rendering in `proposal/context_manager.py`

Implication:
- T09/T10 are **incremental refinements**, not foundational data-layer tasks.

### 1.2 Already present but underused

- `runtime/pool_manager.py` already supports:
  - candidate pool construction
  - registry export
  - weight normalization

Implication:
- T13 should **extend / reuse PoolManager**, not create a parallel `registry_writer.py` unless a strong reason appears.

### 1.3 Confirmed missing in v0.1

These are real v0.2 gaps:

- `PYTHONHASHSEED` not fixed in subprocess runner
- V5 diagnostics too shallow
- `campaign_summary.json` too thin
- failed candidate code not archived in a usable way
- hypothesis family tracking absent
- strategy-shift guidance absent
- parameter layer entirely absent
- weight optimization lineage absent

---

## 2. Design decisions to lock now

### D1. v0.2 should be delivered in two layers

#### v0.2-MVP (core differentiator)
Goal: prove the parameter layer works on top of a cleaner foundation.

Includes:
- T01, T02, T03, T04
- T12, T13, T14, T16, T17, T18

#### v0.2-Full (research-efficiency polish)
Goal: improve outer-loop exploration quality and benchmark rigor.

Includes:
- T05, T06, T07, T08, T09, T10, T11, T15

Reason:
- parameter-layer search is the architectural differentiator of v0.2
- outer-loop efficiency matters, but it should not block the first end-to-end v0.2 close loop

---

### D2. T13 should reuse PoolManager

Current design says:
- new file: `parameter/registry_writer.py`

Refined decision:
- prefer extending `runtime/pool_manager.py` with:
  - `read_weights(registry_path)`
  - `update_weights(registry_path, weights)`

Reason:
- registry semantics already live in PoolManager
- avoids duplicated YAML write logic
- reduces inconsistency risk

If separation is still preferred, `registry_writer.py` must wrap PoolManager helpers rather than duplicate them.

---

### D3. T14 should reuse existing `compute_delta()` semantics

Current design text uses:
```python
score = -(splits * 100_000 + total_cost)
```

Refined decision:
- evaluator should reuse `protocol.evaluation.compute_delta()` semantics
- aggregate score should be median delta over `(case, seed)` pairs

Reason:
- this matches existing screening/validation practical-significance logic
- avoids introducing a second scoring convention for the same lexicographic objective

Recommended interface:
```python
def evaluate_weights(...) -> float:
    # returns median_delta under current lexicographic scoring rules
```

---

### D4. Parameter search default cases should come from screening split

Current design leaves:
```python
eval_cases: Tuple[str, ...] = ()
```

Refined decision:
- empty `eval_cases` means: use screening cases from `SplitManifest`
- this fallback should be implemented centrally, not repeated in CLI / optimizer

Reason:
- makes config ergonomic
- keeps parameter search aligned with existing fast evaluation stage

---

### D5. Weight optimization must never mutate the current champion snapshot in-place during search

Refined decision:
- each optimization run should use an evaluation workspace copied from the promoted champion snapshot
- only the final accepted best weights are written back to the new champion snapshot

Reason:
- champion snapshot should remain a trustworthy artifact
- avoids half-written registry state if optimizer crashes

Suggested flow:
```text
promoted workspace -> create champion snapshot
                 -> clone eval workspace for optimization
                 -> run search in eval workspace
                 -> if improved, write best weights into champion snapshot registry.yaml
```

---

### D6. T15 should be staged, not all-or-nothing

Refined decision:

#### T15a — MVP optimizer
- random initialization
- local perturbation around best-so-far
- log-space sampling

#### T15b — Bayesian optimizer
- GP/acquisition-based implementation
- only after T15a proves the end-to-end pipeline works

Reason:
- isolates modeling risk from plumbing risk
- makes T16/T17/T18 land faster

---

## 3. Refined implementation order

The original task manifest is structurally sound, but the best landing order is:

### Milestone A — Foundation cleanup
- T01 deterministic env
- T02 V5 diagnostics
- T03 summary schema
- T04 failed-code archiving

Deliverable:
- rerun one short campaign and measure real V5 failure pattern

### Milestone B — Parameter-layer MVP
- T12 parameter config + models
- T13 registry weight read/write (via PoolManager)
- T14 evaluator using `compute_delta()`
- T15a random/local optimizer
- T16 promote hook
- T17 minimal lineage + CLI

Deliverable:
- first successful `promote -> optimize weights -> persist result` close loop

### Milestone C — End-to-end proof
- T18 full campaign + A/B comparison

Deliverable:
- one experimental note comparing:
  - baseline promoted structure
  - optimized-weight promoted structure

### Milestone D — Research-efficiency upgrades
- T05 frozen expansion
- T07 family tracking
- T08 strategy guidance
- T09 clearer case feedback wording
- T10 champion baseline hints
- T11 screening rebalance
- T06 observability polish
- T15b Bayesian optimizer

Deliverable:
- stronger search diversity + stronger experiment reports

---

## 4. Task-level refinements

### T01 — Deterministic env

Keep current scope exactly as-is.

Minimal implementation:
```python
_ENV_PASSTHROUGH = {"PATH", "PYTHONPATH"}
_ENV_FIXED = {"PYTHONHASHSEED": "0"}
```

Acceptance:
- `_build_clean_env()` contains fixed hash seed
- V5 false positives measurably drop in rerun

---

### T02 — V5 diagnostics

Current code only returns:
- `run1={...} run2={...}`

Refined minimum scope:
1. save `run1` and `run2` full JSON outputs
2. include `diff_keys`
3. archive candidate operator files
4. return structured detail string / JSON blob

Defer from MVP:
- deep trace of operator selection
- sophisticated failure classification if it slows delivery

---

### T03 + T04 — treat as one artifact track

These two tasks should be implemented together.

Refined artifact policy:
- `campaign_summary.json` stores references, not large blobs
- prefer `code_archive_ref` over inline `code_content`

Recommended new summary fields per step:
- `protocol_result`
- `case_feedback_summary`
- `verification_detail`
- `code_archive_ref`
- `cache_stats`

---

### T07 — Family tracking

Keep it rule-based for v0.2.

Acceptance must include backtest on the known v0.1 hypotheses:
- the 7 subcategory-consolidation variants should collapse into one family or at most two tightly-related families

Do NOT use embeddings in v0.2.

---

### T08 — Strategy guidance

Injection point should be in `ContextManager.build_hypothesis_context()` as a separate block, not hidden inside raw experiment history.

Suggested prompt block order:
1. experiment history
2. strategy guidance
3. blacklist
4. sibling branches

Reason:
- keeps guidance explicit and easier to test

---

### T09

Only improve wording clarity.
No data-model redesign needed.

---

### T10

Good P2 task.
Keep minimal:
- one champion baseline objective per case
- no per-seed baseline expansion

---

### T12

Add a dedicated config model instead of stuffing raw dicts into `ProblemSpec`.

Recommended shape:
```python
class ParameterSearchConfig(BaseModel):
    enabled: bool = True
    trigger: Literal["on_promote"] = "on_promote"
    target: Literal["operator_weights"] = "operator_weights"
    strategy: Literal["random_local", "bayesian"] = "random_local"
    n_initial_random: int = 8
    n_iterations: int = 8
    n_eval_seeds: int = 2
    weight_bounds: Tuple[float, float] = (0.05, 5.0)
    eval_cases: List[str] = []
```

Notes:
- default strategy should be `random_local` for first landing
- default iterations/seeds should be smaller than current design draft

---

### T13

Implementation should operate on `registry.yaml` as the single source of truth.

Required helpers:
- read current operators + weights
- update weight field only
- preserve file path / category / class name untouched

---

### T14

Refined evaluator contract:
```python
def evaluate_weights(...) -> float:
    """Return median_delta under the existing lexicographic scoring rule."""
```

Implementation notes:
- reuse runner + split manifest + seed ledger
- use a dedicated temporary evaluation workspace
- do not mutate champion snapshot during search

---

### T15

Refined split:

#### T15a (MVP)
- random samples in log-space
- local perturb around best point
- deterministic seed for optimizer itself

#### T15b (upgrade)
- proper BO if dependency choice is settled

Dependency decision still required:
- `skopt`
- `sklearn.gaussian_process` + custom acquisition
- or stay with random/local for v0.2

---

### T16

Current `_on_promote()` in `core/campaign.py` is the correct hook.

But it needs one more rule:
- after optimized weights are accepted, reload operator-pool metadata from the new registry rather than copying stale in-memory `operator_pool`

Reason:
- current `ChampionState.operator_pool` can lag behind actual snapshot contents

---

### T17

Split into two sub-goals:

#### T17a — minimal lineage
- new `weight_optimizations` table
- write/read helpers

#### T17b — CLI/reporting
- `scion optimize-weights`
- `scion inspect --weights`
- report rendering

CLI is useful, but should not block landing the core promote-hook path.

---

### T18

Refined acceptance for the first end-to-end run:
1. one branch gets promoted
2. post-promote weight optimization runs automatically
3. optimization result is persisted
4. optimized registry can be inspected later
5. frozen holdout comparison table can be exported

Do not require Bayesian optimization for the first successful T18.

---

## 5. Practical delivery recommendation for tonight

Tonight's goal should be to lock the following, not to over-design every edge case:

1. **Scope split**: v0.2-MVP vs v0.2-Full
2. **T13 decision**: reuse PoolManager
3. **T14 scoring**: reuse `compute_delta()` semantics
4. **T15 strategy**: ship random/local first, BO second
5. **T16 rule**: optimize in eval workspace, then write back final weights

If these five are locked, the rest of the implementation can move quickly.

---

## 6. Recommended next coding order

If implementation starts immediately after review:

```text
1. T01 + T02 + T03/T04   (1 sprint)
2. rerun short campaign   (measure V5 + artifact quality)
3. T12 + T13 + T14       (parameter plumbing)
4. T15a + T16 + T17a     (close loop)
5. T18                   (first v0.2 MVP proof)
6. T05/T07/T08/...       (full polish)
```

This is the fastest path to a believable v0.2 result.

---

## 7. Bottom line

The existing v0.2 design is directionally correct.

The real refinement is not a conceptual rewrite. It is:
- reduce duplicate implementation paths
- land the parameter layer earlier
- separate MVP from full research polish
- reuse existing v0.1 infrastructure aggressively

That is the highest-ROI way to make v0.2 real.
