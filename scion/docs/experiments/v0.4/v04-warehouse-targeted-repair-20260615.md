# Warehouse Targeted Repair Acceptance - 2026-06-15

## Purpose

Accept a targeted v0.4 repair after the repaired warehouse short `4R` compact
debug showed valid Protocol execution but insufficient research quality:

- only `1/4` branch-lesson usages satisfied semantic projection;
- no-effect nearby `subcategory_pack_upgrade.py` variants consumed counted
  attempts before a clean fork;
- one no-effect budget-exhausting runtime-tie path still generated a
  fresh-runtime replay row;
- prompt truncation remained unresolved.

This repair is intentionally narrow. It does not launch a new campaign and does
not claim warehouse longrun readiness.

## V3 Boundary

The repair preserves the v3 boundary. Branch lessons, runtime replay pressure,
prompt context, and diagnostic metadata remain proposal/report material. They
are not added to `DecisionFeatures`, and no warehouse-specific decision
constant is introduced.

## Accepted Code Changes

Changed files:

- `scion/scion/core/explore_step/branch_lesson_usage.py`
- `scion/scion/core/branch_step_runner.py`
- `scion/scion/tests/unit/core/test_branch_lesson_usage.py`
- `scion/scion/tests/unit/core/test_branch_step_runner_scheduler_metadata.py`
- `scion/scion/tests/unit/core/test_decision_finalizer_lifecycle.py`

Behavior changes:

- Strict branch-lesson requirements now hard pre-code block for
  `clean_fork_new_branch` and `sibling_nearby_attempt` when
  `branch_lesson_usage` is missing, metadata-only, linkage-unrecognized, or
  semantically mismatched.
- `same_branch_refinement` remains non-hard-blocking.
- Fresh-runtime replay drain no longer materializes bare
  `fresh_runtime_required` / `RUNTIME_TIE_FRESH_CHAMPION_REQUIRED` into a
  replay unless there is pair-win/no-loss evidence or an actionable loss
  diagnostic.
- Existing pending replay markers can still close normally. Pair-win/no-loss
  and actionable loss diagnostic paths remain eligible.
- No prompt renderer change was accepted in this patch. Prompt overhead and
  `compact_research_signals` truncation remain the next diagnostic item.

## Main-Thread Verification

Commands run from `/home/clawd/research/or-autoresearch-agent`:

```bash
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q \
  scion/scion/tests/unit/core/test_branch_lesson_usage.py \
  scion/scion/tests/unit/core/test_branch_step_runner_scheduler_metadata.py \
  scion/scion/tests/unit/core/test_decision_finalizer_lifecycle.py \
  scion/scion/tests/unit/core/test_retry_round_accounting_campaign_loop.py \
  scion/scion/tests/test_protocol_stats_gates.py \
  scion/scion/tests/unit/core/test_cross_branch_observability.py
```

Result: `149 passed`.

```bash
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q \
  scion/scion/tests/unit/test_hypothesis_context_profiles.py \
  scion/scion/tests/test_proposal_validation.py \
  scion/scion/tests/test_proposal_trajectory_artifacts.py \
  scion/scion/tests/unit/test_cross_branch_research.py
```

Result: `79 passed`.

```bash
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q \
  scion/scion/tests/test_scheduler.py \
  scion/scion/tests/unit/test_branch_prompt_projection.py \
  scion/scion/tests/unit/test_agentic_session_hypothesis_preview_retry.py
```

Result: `76 passed`.

Additional checks:

```bash
python -m py_compile \
  scion/scion/core/branch_step_runner.py \
  scion/scion/core/explore_step/branch_lesson_usage.py

git diff --check -- \
  scion/scion/core/branch_step_runner.py \
  scion/scion/core/explore_step/branch_lesson_usage.py \
  scion/scion/tests/unit/core/test_branch_lesson_usage.py \
  scion/scion/tests/unit/core/test_branch_step_runner_scheduler_metadata.py \
  scion/scion/tests/unit/core/test_decision_finalizer_lifecycle.py
```

Result: both clean.

## Residual Risk

- Stricter branch-lesson enforcement may increase proposal blocks when strict
  lesson records are generated from noisy context. Non-actionable sibling
  records remain filtered.
- Fresh-runtime replay eligibility now depends on structured pair/loss or
  actionable diagnostic signals. Legacy summaries with only bare
  fresh-runtime reason codes will be demoted.
- Prompt truncation remains unresolved. The next safe patch should reduce or
  reorder hypothesis/tool-selection scaffolding so compact research signals are
  not the first casualty of prompt budgets.

## Next Gate

After CVRP solver-heavy work clears enough capacity, run another short compact
warehouse debug, preferably `4-6R`, before any full `3 x 24R` longrun.
Acceptance should require no pre-Protocol failures, no no-effect fresh-runtime
replay row, semantic branch-lesson satisfaction for strict clean forks, and no
more than one extra no-effect same-mechanism follow-up before parking or
forking.
