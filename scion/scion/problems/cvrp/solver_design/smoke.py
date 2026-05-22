"""CVRP solver-design smoke and active-search effort interpretation."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from scion.core.models import HypothesisProposal, PatchProposal, patch_file_changes
from scion.core.paths import normalize_relative_patch_path

_LOW_EFFORT_MIN_CASES = 2
_LOW_EFFORT_MAX_ITERATIONS = 5
_LOW_EFFORT_MAX_ATTEMPTS = 30
_LOW_EFFORT_MAX_RUNTIME_RATIO = 0.35
_LOW_EFFORT_STOP_REASONS = frozenset(
    {
        "no_improvement",
        "early_exit",
        "construction_only",
        "no_search",
    }
)
_SMOKE_TIME_LIMIT_SEC = 3


def is_runtime_patch_path(path: str | None) -> bool:
    normalized = str(path or "").replace("\\", "/").lstrip("/")
    return normalized == "policies/baseline_algorithm.py" or (
        normalized.startswith("policies/baseline_modules/")
        and normalized.endswith(".py")
    )


def patch_claims_search_effort(
    patch: PatchProposal,
    hypothesis: HypothesisProposal | None,
) -> bool:
    paths = set(patch_paths(patch))
    if paths & {
        "policies/baseline_algorithm.py",
        "policies/baseline_modules/scheduler.py",
        "policies/baseline_modules/local_search.py",
        "policies/baseline_modules/destroy_repair.py",
        "policies/baseline_modules/acceptance.py",
    }:
        return True
    text_parts = []
    if hypothesis is not None:
        for name in (
            "hypothesis_text",
            "target_weakness",
            "expected_effect",
            "runtime_budget_strategy",
            "target_runtime_effect",
        ):
            value = getattr(hypothesis, name, None)
            if value:
                text_parts.append(str(value))
    text = " ".join(text_parts).lower()
    if not text:
        return False
    search_terms = (
        "alns",
        "vns",
        "search",
        "local",
        "move",
        "operator",
        "destroy",
        "repair",
        "acceptance",
        "anneal",
        "scheduler",
    )
    return any(term in text for term in search_terms)


def zero_effort_issue(
    *,
    patch: PatchProposal,
    hypothesis: HypothesisProposal | None,
    runs: Sequence[Mapping[str, Any]],
) -> str | None:
    if not patch_claims_search_effort(patch, hypothesis):
        return None
    successful = [
        run
        for run in runs
        if run.get("passed") is True and isinstance(run.get("runtime"), Mapping)
    ]
    if not successful:
        return None
    zero_effort = []
    for run in successful:
        runtime = run.get("runtime")
        if not isinstance(runtime, Mapping):
            continue
        iterations = nonnegative_int(runtime.get("solver_algorithm_search_iterations"))
        attempts = nonnegative_int(runtime.get("solver_algorithm_move_attempts"))
        if iterations == 0 and attempts == 0:
            zero_effort.append(run)
    if len(zero_effort) != len(successful):
        return None
    targets = ", ".join(patch_paths(patch))
    return (
        "solver_design smoke observed zero active search effort on all "
        f"{len(successful)} successful smoke case(s): "
        "solver_algorithm_search_iterations=0 and "
        "solver_algorithm_move_attempts=0. This candidate touches or claims "
        f"search-bearing solver code ({targets}) but behaves like a "
        "construction/wrapper-only path. Wire the changed mechanism into the "
        "active ALNS/VNS/search loop, record real iterations or moves, or "
        "retarget the hypothesis as a bounded construction-only algorithm "
        "with explicit telemetry."
    )


def low_effort_issue(
    *,
    patch: PatchProposal,
    hypothesis: HypothesisProposal | None,
    runs: Sequence[Mapping[str, Any]],
    micro_results: Sequence[Mapping[str, Any]],
) -> str | None:
    if not patch_claims_search_effort(patch, hypothesis):
        return None
    successful = [
        run
        for run in runs
        if run.get("passed") is True and isinstance(run.get("runtime"), Mapping)
    ]
    if len(successful) < _LOW_EFFORT_MIN_CASES:
        return None
    if any(result.get("comparison") == "win" for result in micro_results):
        return None

    micro_by_case_seed = {
        (str(result.get("case") or ""), nonnegative_int(result.get("seed"))): result
        for result in micro_results
    }
    low_effort: list[dict[str, Any]] = []
    for run in successful:
        runtime = run.get("runtime")
        if not isinstance(runtime, Mapping):
            continue
        iterations = nonnegative_int(runtime.get("solver_algorithm_search_iterations"))
        attempts = nonnegative_int(runtime.get("solver_algorithm_move_attempts"))
        stop_reason = runtime_stop_reason(runtime.get("solver_algorithm_stop_reason"))
        if iterations > _LOW_EFFORT_MAX_ITERATIONS:
            continue
        if attempts > _LOW_EFFORT_MAX_ATTEMPTS:
            continue
        if stop_reason not in _LOW_EFFORT_STOP_REASONS:
            continue
        if not runtime_underspent(run, micro_by_case_seed=micro_by_case_seed):
            continue
        low_effort.append(
            {
                "case": run.get("case"),
                "seed": run.get("seed"),
                "iterations": iterations,
                "attempts": attempts,
                "stop_reason": stop_reason,
            }
        )

    if len(low_effort) != len(successful):
        return None
    targets = ", ".join(patch_paths(patch))
    return (
        "solver_design smoke observed low active search effort on all "
        f"{len(successful)} successful smoke case(s): each run stopped with "
        f"{sorted(_LOW_EFFORT_STOP_REASONS)} after at most "
        f"{_LOW_EFFORT_MAX_ITERATIONS} search iteration(s) and "
        f"{_LOW_EFFORT_MAX_ATTEMPTS} move attempt(s), while using only a "
        "small fraction of the smoke/champion runtime and producing no "
        "smoke micro-benchmark win. This candidate touches or claims "
        f"search-bearing solver code ({targets}) but appears to truncate "
        "the active ALNS/VNS/search loop. Keep real search budget and "
        "telemetry, or retarget the hypothesis as a bounded "
        "construction/runtime-speed change that does not claim search "
        "improvement."
    )


def runtime_smoke_repair_guidance(
    audit_failure: Mapping[str, Any],
    *,
    runtime: Any,
    run_payload: Any,
) -> Sequence[str]:
    if audit_failure.get("error_category") != "solver_algorithm_runtime_error":
        return ()
    events = audit_failure.get("solver_algorithm_events")
    text = " ".join(
        str(part)
        for part in (
            audit_failure.get("detail"),
            audit_failure.get("error_category"),
            events,
            run_payload.get("detail") if isinstance(run_payload, Mapping) else None,
        )
        if part not in (None, "", [], {})
    )
    guidance = [
        "Failure occurred inside the candidate solver_design solve path during tainted algorithm smoke; repair the candidate algorithm code, not protocol or adapter files.",
        "Use the current CVRP object model: _Solution has .instance, .routes, .total_cost, .copy(), .rebuild_index(), .remove_empty_routes(), .is_feasible(), and .routes_as_tuples(); it does not expose ._instance.",
        "_Solution and _Route use __slots__; do not attach temporary private attributes such as solution._cache, solution._nn_lists, or route._memo. Keep temporary search state in local variables or helper arguments.",
        "_Solution.routes contains _Route objects. A _Route has .customers, .load, .cost, .insert(), .remove(), .can_insert(), .cost_of_insert(), .cost_of_remove(), and .recalculate(); do not treat routes as plain customer lists unless you explicitly use route.customers.",
        "CvrpInstance.distance(i, j), demand(i), route_load(route), and route_distance(route) use integer node/customer ids; keep depot/customer ids explicit and rebuild solution indexes after direct route edits.",
    ]
    if "_Solution' object has no attribute '_instance'" in text:
        guidance.insert(
            1,
            "Specific fix: replace solution._instance with solution.instance; only _Route carries the private _instance slot.",
        )
    if "int' object has no attribute 'distance'" in text or '".distance"' in text:
        guidance.insert(
            1,
            "Specific fix: do not call .distance on an int, route, or customer id; call instance.distance(prev_id, next_id).",
        )
    if "has no attribute '_nn_lists'" in text or "object has no attribute '_cache'" in text:
        guidance.insert(
            1,
            "Specific fix: remove the dynamic state attribute write; pass nearest-neighbor lists or caches as helper arguments because _Solution uses __slots__.",
        )
    if runtime in (None, {}, ""):
        guidance.append(
            "Runtime payload was missing or empty; first make solve(...) return a valid _Solution and context telemetry before adding new search breadth."
        )
    return tuple(guidance[:6])


def runtime_underspent(
    run: Mapping[str, Any],
    *,
    micro_by_case_seed: Mapping[tuple[str, int], Mapping[str, Any]],
) -> bool:
    elapsed = nonnegative_int((run.get("run") or {}).get("elapsed_ms"))
    runtime = run.get("runtime")
    solver_elapsed = 0
    if isinstance(runtime, Mapping):
        solver_elapsed = nonnegative_int(runtime.get("solver_algorithm_elapsed_ms"))
    candidate_elapsed = elapsed or solver_elapsed
    if candidate_elapsed <= 0:
        return False

    key = (str(run.get("case") or ""), nonnegative_int(run.get("seed")))
    micro = micro_by_case_seed.get(key)
    if isinstance(micro, Mapping):
        champion_elapsed = nonnegative_int(micro.get("champion_elapsed_ms"))
        if champion_elapsed > 0:
            return candidate_elapsed / champion_elapsed <= _LOW_EFFORT_MAX_RUNTIME_RATIO
    return candidate_elapsed <= int(
        _SMOKE_TIME_LIMIT_SEC * 1000 * _LOW_EFFORT_MAX_RUNTIME_RATIO
    )


def patch_paths(patch: PatchProposal) -> list[str]:
    paths: list[str] = []
    for change in patch_file_changes(patch):
        try:
            path = normalize_relative_patch_path(change.file_path)
        except ValueError:
            path = str(change.file_path or "")
        if path:
            paths.append(path)
    return paths


def runtime_stop_reason(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text or "unknown"


def nonnegative_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


__all__ = [
    "is_runtime_patch_path",
    "low_effort_issue",
    "patch_claims_search_effort",
    "runtime_smoke_repair_guidance",
    "zero_effort_issue",
]
