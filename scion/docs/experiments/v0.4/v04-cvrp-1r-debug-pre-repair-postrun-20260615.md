# CVRP 1R Behavior Debug Pre-Repair Postrun - 2026-06-15

## Purpose

This was a one-round CVRP behavior debug to inspect agent research behavior,
prompt/source visibility, branch-lesson use, and pre-Protocol proposal quality
before starting another long CVRP campaign.

The run started before the CVRP best-update solution-boundary repair, so it is
classified as pre-repair behavior evidence. It is not Protocol evidence and
must not be used as promotion, rejection, or mechanism-quality evidence.

## Artifacts

- WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-single-round-debug-cvrp-compact-1r-gpt55-20260615T172112Z-claw`
- Server sync:
  `/home/clawd/research/scion-experiments/v04-single-round-debug-cvrp-compact-1r-gpt55-20260615T172112Z-claw`
- Launch commit: `17fdeb8`
- Stop marker:
  `/home/clawd/research/scion-experiments/v04-single-round-debug-cvrp-compact-1r-gpt55-20260615T172112Z-claw/stopped_by_main.txt`
- Command:
  `/home/clawd/research/scion-experiments/v04-single-round-debug-cvrp-compact-1r-gpt55-20260615T172112Z-claw/command.txt`

Launch shape:

- One cell, `rounds=1`.
- Local WSL `gpt-5.5`.
- `measurement_governance=on`.
- `compact-measurement-diagnostics`.
- `time_limit_sec=30`.
- `SCION_STAGE_TRANSITION_DRAIN_LIMIT=0`.
- Foreground `timeout 2h` inside tmux session
  `scion_cvrp_1r_debug_172112`.

The main session stopped the run at `2026-06-15T17:53:07Z` after repeated
pre-Protocol failures on the now-fixed boundary bug. Wrapper exit was
`143/SIGTERM`.

## Outcome

Campaign validity:

- `run_validity.status=invalid`.
- `run_validity.reason=invalid_no_effective_rounds`.
- `run_validity.effective_rounds_completed=0`.
- `run_validity.protocol_metric_results=0`.
- `run_validity.stopped_reason=signal:SIGTERM`.

Counters:

- `proposal_attempts_total=5`.
- `agentic_sessions=10`.
- `screening_protocol_results=0`.
- `protocol_metric_results=0`.
- `formal_screened_candidates=0`.
- `verification_failure_consumed_candidates=0`.
- `quality_block_ledger=4`.
- LLM request kind counts:
  `code=17`, `hypothesis=5`, `hypothesis_target_intent=5`,
  `tool_selection=18`.

Artifacts:

- Agentic session output files: `10`.
- LLM trace files: `45`.
- Formal candidates: none.

## Failure Classification

This is a pre-Protocol code/self-check failure, not a Protocol negative result.
No candidate reached formal screening.

The repeated hard failure was:

```text
solver runtime audit reported solver_algorithm_errors=1:
solve failed: solution cannot be coerced to CvrpSolution
```

Read-only artifact audit found:

- Code-stage target/current source visibility was present.
- Source visibility was not the main blocker.
- Prompt context remained large and diluted by governance/rules/diagnostic
  material.
- The agent proposed multiple solver-design mechanisms, including
  `interroute_2opt_bridge`, `route_slack_regret_repair`,
  `operator_pair_diversity_scheduler`, and `route_compaction_postrepair`.
- Branch/cross-branch lesson structure was present, but the run did not reach a
  point where those lessons could be judged through Protocol evidence.

The root cause was a CVRP problem-owned runtime boundary bug:

- ALNS/VNS scheduler best-update instrumentation passed internal `_Solution`
  objects to `record_best_update()`.
- Runtime audit coercion accepted public `CvrpSolution`, mappings, or simple
  routes-like values, but internal `_Solution.routes` contains `_Route` objects.
- `_Route` is not directly iterable as a customer route, so coercion failed and
  the algorithm smoke failed closed.

## Repair

The blocker was repaired in commit `c3c15ca` and pushed as part of the current
branch:

- `scheduler.py` now records best updates with `best.routes_as_tuples()`.
- CVRP-owned `solution_ops._coerce_solution()` accepts bare routes-like
  iterables.
- Focused acceptance:
  `PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q scion/scion/tests/test_cvrp_solver_algorithm_runtime.py scion/scion/tests/test_cvrp_solver_vrp_smoke.py scion/scion/tests/test_cvrp_protocol_smoke.py`
  passed with `21 passed`.
- Scoped `py_compile` and `git diff --check` passed.

The later documentation-only commit `e667d6c` records the independent VRP
control evidence and is the current pushed branch tip at this report time.

## Interpretation

The run is valuable as behavior/debug evidence because it proves the pre-repair
path could spend multiple LLM attempts without producing a formal candidate.
It is not evidence that the proposed CVRP mechanisms are weak, and it is not
evidence that Scion cannot do CVRP research.

The run supports two v0.4 conclusions:

1. Source visibility alone is not sufficient. The code context had source, but
   the proposal loop was still blocked by an API boundary and heavy prompt
   context.
2. Effective-research validation must distinguish pre-Protocol self-check
   failures from Protocol screening/validation/frozen evidence.

## Next Gate

Rerun a small one-round CVRP behavior debug from the repaired commit before any
longer CVRP campaign. Acceptance for the rerun is not promotion; it is whether
the run can produce at least one formal candidate or a different, non-boundary
pre-Protocol failure that genuinely reflects agent code quality rather than the
fixed `_Solution`/`CvrpSolution` boundary.
