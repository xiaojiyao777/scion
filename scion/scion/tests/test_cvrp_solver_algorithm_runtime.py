from __future__ import annotations

from scion.problems.cvrp.policies.baseline_modules import scheduler as baseline_scheduler
from scion.problems.cvrp.policies.baseline_modules.state import _Route, _Solution
from scion.problems.cvrp.solver_runtime.algorithm_runtime import (
    SolverAlgorithmContext,
    _record_solver_algorithm_event,
    solver_algorithm_defaults,
    typed_events_from_legacy_record_move,
)
from scion.tests.cvrp_solver_runtime_support import *
from scion.runtime.audit import (
    format_runtime_audit_failure,
    runtime_audit_failure_from_runtime,
)


def _actionability_summary() -> dict[str, object]:
    return {
        "schema": "scion.cvrp.solver_actionability.v1",
        "attempted": True,
        "move_attempts": 1,
        "accepted_moves": 0,
        "no_accepted_moves": True,
        "candidate_emitted_no_measurable_objective_effect": True,
        "runtime_budget_hit": False,
        "phases": {},
    }


def test_solver_algorithm_audit_preserves_every_event() -> None:
    audit: dict[str, object] = {"solver_algorithm_path": "fixture.py"}

    for index in range(25):
        _record_solver_algorithm_event(audit, "ok", f"event-{index}")

    events = audit["solver_algorithm_events"]
    assert isinstance(events, list)
    assert len(events) == 25
    assert events[-1]["detail"] == "event-24"


def test_legacy_record_move_compat_never_claims_direct_effect() -> None:
    events = typed_events_from_legacy_record_move(
        "elite_pool_admission",
        attempted=1,
        accepted=1,
        delta=17.0,
        best_improved=True,
    )

    assert [event.lane for event in events] == ["attempt", "associated_outcome"]
    assert all(event.lane != "direct_effect" for event in events)
    assert events[1].attribution_scope == "legacy_record_move_ambiguous"
    assert events[1].before_ref is None
    assert events[1].after_ref is None
    assert set(events[1].missing_refs) == {"before_ref", "after_ref"}


def test_typed_state_transition_does_not_increment_legacy_accepted_moves() -> None:
    instance = _line_instance(3)
    audit, context = _runtime_context_for_instance(instance)
    context.record_move(
        "legacy_elite_pool_admission",
        attempted=1,
        accepted=1,
        delta=17.0,
        best_improved=True,
    )

    assert "typed_telemetry_events" not in audit
    legacy_accepted = audit["solver_algorithm_accepted_moves"]

    context.record_telemetry_event(
        "state_transition",
        "elite_solution_pool",
        attribution_scope="pool_anchor_selection",
        attribution_confidence=1.0,
        before_ref="anchor:old",
        after_ref="anchor:new",
        missing_refs=(),
        evidence_ref="runtime.pool_anchor_transition.17",
    )

    assert legacy_accepted == 1
    assert audit["solver_algorithm_accepted_moves"] == legacy_accepted
    summary = audit["typed_telemetry_summary"]
    assert summary["lane_counts"]["state_transition"] == 1
    assert summary["lane_counts"]["direct_effect"] == 0


def test_solver_design_surface_declares_active_algorithm_runtime_fields(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)

    raw = _run_solver(
        workspace,
        "data/operator_case.json",
        selected_surface="solver_design",
    )
    runtime = raw["runtime"]
    spec_v1 = load_problem_spec_v1_from_yaml(workspace / "problem-v1.yaml")
    legacy_spec = legacy_problem_spec_from_v1(spec_v1)
    surface = next(
        surface
        for surface in spec_v1.research_surfaces or []
        if surface.name == "solver_design"
    )
    required_fields = tuple(surface.evidence.required_runtime_fields)
    optional_fields = tuple(surface.evidence.optional_runtime_fields)

    assert "solver_algorithm_loaded" in required_fields
    assert "solver_algorithm_active" in required_fields
    assert "solver_algorithm_phase_runtime_ms" in required_fields
    assert "solver_algorithm_actionability_summary" in required_fields
    assert "solver_algorithm_best_update_trace" not in required_fields
    assert "solver_algorithm_best_update_summary" not in required_fields
    assert "solver_algorithm_alns_iteration_trace" not in required_fields
    assert "solver_algorithm_best_update_trace" in optional_fields
    assert "solver_algorithm_best_update_summary" in optional_fields
    assert "solver_algorithm_alns_iteration_trace" in optional_fields
    assert set(required_fields).issubset(runtime)
    assert runtime["solver_algorithm_path"] == "policies/baseline_algorithm.py"
    assert runtime["solver_algorithm_loaded"] is True
    assert runtime["solver_algorithm_active"] is True
    assert runtime["solver_algorithm_errors"] == 0
    assert runtime["solver_algorithm_solution_valid"] is True
    assert runtime["solver_algorithm_solution_routes"] >= 1
    assert runtime["solver_algorithm_total_distance"] > 0
    assert runtime["solver_algorithm_stop_reason"] != "inactive"
    assert raw["feasible"] is True
    assert runtime_audit_failure_from_raw(
        raw,
        problem_spec=legacy_spec,
        selected_surface="solver_design",
    ) is None


def test_solver_design_default_solver_variant_stays_alns_vns(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)

    raw = _run_solver(
        workspace,
        "data/operator_case.json",
        selected_surface="solver_design",
    )
    runtime = raw["runtime"]
    phase_runtime = runtime["solver_algorithm_phase_runtime_ms"]

    assert raw["feasible"] is True
    assert runtime["solver_algorithm_active"] is True
    assert runtime["solver_algorithm_errors"] == 0
    assert runtime["solver_algorithm_solution_valid"] is True
    assert "alns_core" in phase_runtime
    assert "route_first_heuristic" not in phase_runtime
    assert runtime["solver_algorithm_search_iterations"] > 0


def test_solver_design_route_first_variant_runs_with_telemetry(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)
    config_path = workspace / "policies" / "baseline_modules" / "config.py"
    config_text = config_path.read_text(encoding="utf-8")
    assert 'SOLVER_VARIANT = "alns_vns"' in config_text
    config_path.write_text(
        config_text.replace(
            'SOLVER_VARIANT = "alns_vns"',
            'SOLVER_VARIANT = "route_first_heuristic"',
        ),
        encoding="utf-8",
    )

    raw = _run_solver(
        workspace,
        "data/operator_case.json",
        selected_surface="solver_design",
    )
    runtime = raw["runtime"]
    context_records = runtime["solver_algorithm_context_records"]

    assert raw["feasible"] is True
    assert runtime["solver_algorithm_active"] is True
    assert runtime["solver_algorithm_errors"] == 0
    assert runtime["solver_algorithm_solution_valid"] is True
    assert runtime["solver_algorithm_fleet_violation"] == 0
    assert runtime["solver_algorithm_stop_reason"] in {"completed", "time_limit"}
    assert "route_first_heuristic" in runtime["solver_algorithm_phase_runtime_ms"]
    assert context_records["route_first_heuristic_iterations"] >= 1
    assert runtime["solver_algorithm_move_attempts"] >= 1


def test_solver_design_baseline_algorithm_exception_fails_selected_surface(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)
    (workspace / "policies" / "baseline_algorithm.py").write_text(
        "\n".join(
            [
                "def solve(instance, rng, time_limit_sec, context):",
                "    raise RuntimeError('baseline body failed')",
                "",
            ]
        ),
        encoding="utf-8",
    )

    raw = _run_solver(
        workspace,
        "data/operator_case.json",
        selected_surface="solver_design",
    )
    runtime = raw["runtime"]
    spec_v1 = load_problem_spec_v1_from_yaml(workspace / "problem-v1.yaml")
    legacy_spec = legacy_problem_spec_from_v1(spec_v1)
    issue = runtime_audit_failure_from_raw(
        raw,
        problem_spec=legacy_spec,
        selected_surface="solver_design",
    )

    assert runtime["solver_algorithm_path"] == "policies/baseline_algorithm.py"
    assert runtime["solver_algorithm_loaded"] is True
    assert runtime["solver_algorithm_active"] is False
    assert runtime["solver_algorithm_errors"] == 1
    assert runtime["solver_algorithm_stop_reason"] == "exception"
    assert "baseline body failed" in json.dumps(runtime["solver_algorithm_events"])
    assert issue is not None
    assert issue["error_category"] == "solver_algorithm_runtime_error"
    assert issue["solver_algorithm_errors"] == 1
    assert "baseline body failed" in format_runtime_audit_failure(issue)


def test_solver_design_runtime_audit_rejects_inactive_surface_without_error_counter() -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(CVRP_DIR / "problem-v1.yaml")
    legacy_spec = legacy_problem_spec_from_v1(spec_v1)
    issue = runtime_audit_failure_from_runtime(
        {
            "solver_algorithm_loaded": True,
            "solver_algorithm_active": False,
            "solver_algorithm_errors": 0,
            "solver_algorithm_elapsed_ms": 20,
            "solver_algorithm_phase_runtime_ms": {"construction": 3},
            "solver_algorithm_solution_valid": True,
            "solver_algorithm_solution_routes": 1,
            "solver_algorithm_objective": {"total_distance": 1.0},
            "solver_algorithm_total_distance": 1.0,
            "solver_algorithm_fleet_violation": 0,
            "solver_algorithm_search_iterations": 1,
            "solver_algorithm_move_attempts": 1,
            "solver_algorithm_accepted_moves": 0,
            "solver_algorithm_improving_moves": 0,
            "solver_algorithm_neutral_accepted_moves": 0,
            "solver_algorithm_best_improving_moves": 0,
            "solver_algorithm_best_delta": 0,
            "solver_algorithm_phase_delta_sum": {"construction": 0},
            "solver_algorithm_phase_best_delta": {"construction": 0},
            "solver_algorithm_phase_improvement_counts": {"construction": 0},
            "solver_algorithm_actionability_summary": _actionability_summary(),
            "solver_algorithm_stop_reason": "inactive",
        },
        problem_spec=legacy_spec,
        selected_surface="solver_design",
    )

    assert issue is not None
    assert issue["error_category"] == "surface_runtime_contract_error"
    assert "solver_algorithm_active" in issue["failed_runtime_fields"]


def test_solver_design_runtime_audit_rejects_surface_fallback_event() -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(CVRP_DIR / "problem-v1.yaml")
    legacy_spec = legacy_problem_spec_from_v1(spec_v1)
    issue = runtime_audit_failure_from_runtime(
        {
            "solver_algorithm_loaded": True,
            "solver_algorithm_active": True,
            "solver_algorithm_errors": 0,
            "solver_algorithm_elapsed_ms": 20,
            "solver_algorithm_phase_runtime_ms": {"construction": 3},
            "solver_algorithm_solution_valid": True,
            "solver_algorithm_solution_routes": 1,
            "solver_algorithm_objective": {"total_distance": 1.0},
            "solver_algorithm_total_distance": 1.0,
            "solver_algorithm_fleet_violation": 0,
            "solver_algorithm_search_iterations": 1,
            "solver_algorithm_move_attempts": 1,
            "solver_algorithm_accepted_moves": 0,
            "solver_algorithm_improving_moves": 0,
            "solver_algorithm_neutral_accepted_moves": 0,
            "solver_algorithm_best_improving_moves": 0,
            "solver_algorithm_best_delta": 0,
            "solver_algorithm_phase_delta_sum": {"construction": 0},
            "solver_algorithm_phase_best_delta": {"construction": 0},
            "solver_algorithm_phase_improvement_counts": {"construction": 0},
            "solver_algorithm_actionability_summary": _actionability_summary(),
            "solver_algorithm_stop_reason": "completed",
            "solver_algorithm_events": [
                {
                    "status": "warning",
                    "detail": "active algorithm failed; emitted fallback",
                }
            ],
        },
        problem_spec=legacy_spec,
        selected_surface="solver_design",
    )

    assert issue is not None
    assert issue["error_category"] == "surface_runtime_fallback"
    assert "fallback" in format_runtime_audit_failure(issue)


def test_solver_design_runtime_audit_rejects_inconsistent_phase_runtime() -> None:
    spec_v1 = load_problem_spec_v1_from_yaml(CVRP_DIR / "problem-v1.yaml")
    legacy_spec = legacy_problem_spec_from_v1(spec_v1)
    issue = runtime_audit_failure_from_runtime(
        {
            "solver_algorithm_errors": 0,
            "solver_algorithm_elapsed_ms": 1000,
            "solver_algorithm_phase_runtime_ms": {
                "search": 500,
                "bad_phase": 100000,
            },
        },
        problem_spec=legacy_spec,
        selected_surface="solver_design",
    )

    assert issue is not None
    assert issue["error_category"] == "solver_algorithm_runtime_telemetry_error"
    assert issue["runtime_phase"] == "bad_phase"
    assert "phase runtime fields must record per-phase elapsed delta" in (
        format_runtime_audit_failure(issue)
    )


def test_active_baseline_algorithm_ignores_deleted_legacy_policy_hooks(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)
    (workspace / "policies" / "baseline_algorithm.py").write_text(
        "\n".join(
            [
                "def solve(instance, rng, time_limit_sec, context):",
                "    solution = context.nearest_neighbor()",
                "    context.record_phase('candidate_construct', 1)",
                "    context.record_iteration('candidate_probe', 1)",
                "    context.record_move('candidate_probe', attempted=1, accepted=0)",
                "    context.set_stop_reason('candidate_completed')",
                "    return solution",
                "",
            ]
        ),
        encoding="utf-8",
    )
    legacy_files = {
        "solver_algorithm.py": "def solve(*args, **kwargs):\n    raise RuntimeError('legacy solver hook should not run')\n",
        "search_policy.py": "def baseline_time_fraction(*args, **kwargs):\n    raise RuntimeError('legacy search policy should not run')\n",
        "construction_policy.py": "def construction_mode(*args, **kwargs):\n    raise RuntimeError('legacy construction policy should not run')\n",
        "main_search_strategy.py": "def main_search_plan(*args, **kwargs):\n    raise RuntimeError('legacy main search should not run')\n",
    }
    for name, body in legacy_files.items():
        (workspace / "policies" / name).write_text(body, encoding="utf-8")

    raw = _run_solver(
        workspace,
        "data/operator_case.json",
        selected_surface="solver_design",
    )
    runtime = raw["runtime"]
    spec_v1 = load_problem_spec_v1_from_yaml(workspace / "problem-v1.yaml")
    legacy_spec = legacy_problem_spec_from_v1(spec_v1)

    assert runtime["solver_algorithm_path"] == "policies/baseline_algorithm.py"
    assert runtime["solver_algorithm_loaded"] is True
    assert runtime["solver_algorithm_active"] is True
    assert runtime["solver_algorithm_errors"] == 0
    assert runtime["solver_algorithm_stop_reason"] == "candidate_completed"
    assert runtime["solver_algorithm_search_iterations"] == 1
    assert runtime["solver_algorithm_move_attempts"] == 1
    assert runtime["solver_algorithm_solution_valid"] is True
    assert "candidate_construct" in runtime["solver_algorithm_phase_runtime_ms"]
    rendered_runtime = json.dumps(runtime)
    assert "legacy solver hook should not run" not in rendered_runtime
    assert "legacy search policy should not run" not in rendered_runtime
    assert "legacy construction policy should not run" not in rendered_runtime
    assert "legacy main search should not run" not in rendered_runtime
    assert runtime_audit_failure_from_raw(
        raw,
        problem_spec=legacy_spec,
        selected_surface="solver_design",
    ) is None


def test_solver_design_context_exposes_objective_and_budget_helpers(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)
    (workspace / "policies" / "baseline_algorithm.py").write_text(
        "\n".join(
            [
                "def solve(instance, rng, time_limit_sec, context):",
                "    solution = context.nearest_neighbor()",
                "    objective = context.objective(solution)",
                "    assert context.objective_key(solution) == (objective[0], objective[1])",
                "    assert context.is_valid(solution)",
                "    assert context.remaining_time() >= 0.0",
                "    assert context.remaining_time_ms() >= 0",
                "    context.record_solution_progress(",
                "        initial_route_count=2,",
                "        final_route_count=1,",
                "        initial_total_distance=10.0,",
                "        final_total_distance=8.0,",
                "        budget_hit=True,",
                "    )",
                "    context.record_iteration('objective_probe', 1)",
                "    context.record_move('objective_probe', attempted=1, accepted=0)",
                "    return context.make_solution(solution.routes)",
                "",
            ]
        ),
        encoding="utf-8",
    )

    raw = _run_solver(
        workspace,
        "data/operator_case.json",
        selected_surface="solver_design",
    )
    runtime = raw["runtime"]

    assert runtime["solver_algorithm_active"] is True
    assert runtime["solver_algorithm_errors"] == 0
    assert runtime["solver_algorithm_search_iterations"] == 1
    assert runtime["solver_algorithm_move_attempts"] == 1
    assert runtime["solver_algorithm_accepted_moves"] == 0
    assert runtime["solver_algorithm_neutral_accepted_moves"] == 0
    assert runtime["solver_algorithm_improving_moves"] == 0
    assert runtime["solver_algorithm_runtime_budget_hit"] is True
    assert runtime["solver_algorithm_phase_move_attempts"]["objective_probe"] == 1
    assert runtime["solver_algorithm_phase_accepted_moves"]["objective_probe"] == 0
    assert runtime["solver_algorithm_phase_improvement_counts"]["objective_probe"] == 0
    summary = runtime["solver_algorithm_actionability_summary"]
    assert summary["schema"] == "scion.cvrp.solver_actionability.v1"
    assert summary["candidate_emitted_no_measurable_objective_effect"] is True
    assert summary["runtime_budget_hit"] is True
    assert summary["route_count_delta_final_minus_initial"] == -1
    assert summary["total_distance_improvement_from_initial"] == 2.0
    assert summary["phases"]["objective_probe"]["status"] == "attempted_no_acceptance"
    assert runtime["solver_algorithm_best_update_trace"] == []
    best_update_summary = runtime["solver_algorithm_best_update_summary"]
    assert best_update_summary["schema"] == "scion.cvrp.best_update_summary.v1"
    assert best_update_summary["best_update_count"] == 0
    assert summary["best_update_summary"]["best_update_count"] == 0
    assert runtime["solver_algorithm_solution_valid"] is True


def test_solver_design_best_update_trace_is_complete_and_summarized(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)
    (workspace / "policies" / "baseline_algorithm.py").write_text(
        "\n".join(
            [
                "def solve(instance, rng, time_limit_sec, context):",
                "    solution = context.nearest_neighbor()",
                "    for iteration in range(1, 41):",
                "        context.record_iteration('alns', 1)",
                "        context.record_best_update(",
                "            solution,",
                "            phase='alns',",
                "            iteration=iteration,",
                "            delta_from_previous_best=1.5,",
                "            destroy_operator='shaw',",
                "            repair_operator='regret2',",
                "        )",
                "        context.record_move(",
                "            'alns',",
                "            attempted=1,",
                "            accepted=1,",
                "            delta=1.5,",
                "            best_improved=True,",
                "        )",
                "    return solution",
                "",
            ]
        ),
        encoding="utf-8",
    )

    raw = _run_solver(
        workspace,
        "data/operator_case.json",
        selected_surface="solver_design",
    )
    runtime = raw["runtime"]

    trace = runtime["solver_algorithm_best_update_trace"]
    summary = runtime["solver_algorithm_best_update_summary"]
    assert runtime["solver_algorithm_active"] is True
    assert runtime["solver_algorithm_errors"] == 0
    assert runtime["solver_algorithm_best_improving_moves"] == 40
    assert runtime["solver_algorithm_phase_improvement_counts"]["alns"] == 40
    assert len(trace) == 40
    assert trace[0]["phase"] == "alns"
    assert trace[0]["iteration"] == 1
    assert trace[-1]["iteration"] == 40
    assert trace[0]["delta_from_previous_best"] == 1.5
    assert trace[0]["destroy_operator"] == "shaw"
    assert trace[0]["repair_operator"] == "regret2"
    assert trace[0]["operator_pair"] == "shaw+regret2"
    assert trace[0]["route_count"] >= 1
    assert trace[0]["total_distance"] > 0
    assert trace[0]["objective"]["total_distance"] == trace[0]["total_distance"]
    assert summary["schema"] == "scion.cvrp.best_update_summary.v1"
    assert summary["best_update_count"] == 40
    assert summary["first_iteration"] == 1
    assert summary["last_iteration"] == 40
    assert summary["first_elapsed_ms"] is not None
    assert summary["last_elapsed_ms"] is not None
    assert summary["update_density_per_1000_iterations"] == 1000.0
    assert summary["phase_counts"] == {"alns": 40}
    assert summary["operator_pair_counts"] == {"shaw+regret2": 40}
    actionability = runtime["solver_algorithm_actionability_summary"]
    assert actionability["best_update_summary"]["best_update_count"] == 40


def test_solver_design_alns_iteration_trace_is_complete(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)
    (workspace / "policies" / "baseline_algorithm.py").write_text(
        "\n".join(
            [
                "def solve(instance, rng, time_limit_sec, context):",
                "    solution = context.nearest_neighbor()",
                "    for iteration in range(1, 41):",
                "        context.record_iteration('alns', 1)",
                "        context.record_alns_iteration(",
                "            iteration=iteration,",
                "            elapsed_ms_before=iteration,",
                "            remaining_ms_before=1000 - iteration,",
                "            q=3,",
                "            destroy_operator='shaw',",
                "            repair_operator='regret3',",
                "            candidate_after_repair_distance=120.0,",
                "            candidate_after_polish_distance=118.0,",
                "            accepted=(iteration % 2 == 0),",
                "            acceptance_reason='new_best' if iteration % 2 == 0 else 'rejected',",
                "            best_improved=(iteration % 2 == 0),",
                "            elapsed_ms_after=iteration + 1,",
                "            remaining_ms_after=999 - iteration,",
                "        )",
                "    return solution",
                "",
            ]
        ),
        encoding="utf-8",
    )

    raw = _run_solver(
        workspace,
        "data/operator_case.json",
        selected_surface="solver_design",
    )
    runtime = raw["runtime"]

    trace = runtime["solver_algorithm_alns_iteration_trace"]
    assert runtime["solver_algorithm_active"] is True
    assert runtime["solver_algorithm_errors"] == 0
    assert runtime["solver_algorithm_search_iterations"] == 40
    assert len(trace) == 40
    assert trace[0]["iteration"] == 1
    assert trace[-1]["iteration"] == 40
    assert trace[0]["q"] == 3
    assert trace[0]["destroy_operator"] == "shaw"
    assert trace[0]["repair_operator"] == "regret3"
    assert trace[0]["candidate_after_repair_distance"] == 120.0
    assert trace[0]["candidate_after_polish_distance"] == 118.0
    assert trace[1]["accepted"] is True
    assert trace[1]["acceptance_reason"] == "new_best"
    assert trace[1]["best_improved"] is True


def test_baseline_scheduler_best_update_records_public_routes_not_internal_solution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instance = CvrpInstance(
        name="scheduler_best_update_boundary",
        capacity=99,
        depot=0,
        nodes=(
            CvrpNode(id=0, x=0, y=0, demand=0),
            CvrpNode(id=1, x=0, y=1, demand=1),
            CvrpNode(id=2, x=0, y=2, demand=1),
            CvrpNode(id=3, x=100, y=0, demand=1),
        ),
        allowed_routes=1,
        use_integer_cost=True,
    )

    def improve_to_ordered_route(candidate: _Solution, q: int, rng: object) -> list[int]:
        candidate.routes = [_Route(candidate.instance, [1, 2, 3])]
        candidate.rebuild_index()
        return [3]

    def repair_noop(candidate: _Solution, removed: list[int], rng: object) -> None:
        return None

    for name in (
        "_random_removal",
        "_worst_removal",
        "_shaw_removal",
        "_route_removal",
    ):
        monkeypatch.setattr(baseline_scheduler, name, improve_to_ordered_route)
    for name in ("_greedy_insertion", "_regret2_insertion", "_regret3_insertion"):
        monkeypatch.setattr(baseline_scheduler, name, repair_noop)

    audit = solver_algorithm_defaults("policies/baseline_algorithm.py")
    runtime_context = SolverAlgorithmContext(
        instance=instance,
        instance_path="unit/scheduler_best_update_boundary.json",
        seed=1,
        rng=random.Random(1),
        time_limit_sec=1.0,
        start_time=time.perf_counter(),
        adapter=CvrpAdapter(_Spec()),  # type: ignore[arg-type]
        audit=audit,
    )

    class _OneIterationRng:
        def random(self) -> float:
            return 0.0

        def uniform(self, low: float, high: float) -> float:
            return low

    class _BoundaryContext:
        def __init__(self, wrapped: SolverAlgorithmContext) -> None:
            self._wrapped = wrapped
            self.iterations = 0
            self.best_update_payloads: list[object] = []

        def elapsed_ms(self) -> int:
            return self._wrapped.elapsed_ms()

        def remaining_time(self) -> float:
            return 1.0 if self.iterations == 0 else 0.0

        def record_phase(self, name: str, elapsed_ms: int | float) -> None:
            self._wrapped.record_phase(name, elapsed_ms)

        def record_iteration(self, phase: str = "search", count: int = 1) -> None:
            self.iterations += count
            self._wrapped.record_iteration(phase, count)

        def record_best_update(self, solution: object, **kwargs: object) -> None:
            assert not isinstance(solution, _Solution)
            self.best_update_payloads.append(solution)
            self._wrapped.record_best_update(solution, **kwargs)

        def record_move(self, phase: str, **kwargs: object) -> None:
            self._wrapped.record_move(phase, **kwargs)

        def record_solution_progress(self, **kwargs: object) -> None:
            self._wrapped.record_solution_progress(**kwargs)

    context = _BoundaryContext(runtime_context)
    solver = baseline_scheduler._ALNSVNSSolver(
        time_limit=1.0,
        destroy_ratio=(0.1, 0.1),
        segment_length=10,
        reaction_factor=0.2,
        vns_max_no_improve=1,
        use_vns=False,
        cw_threshold=99,
        vns_threshold=99,
        alns_threshold=99,
        max_destroy_customers=1,
        max_routes=1,
        context=context,
    )

    initial_solution = _Solution(instance, [_Route(instance, [1, 3, 2])])
    monkeypatch.setattr(
        solver,
        "_initial_solution",
        lambda current_instance, reserve: initial_solution,
    )

    best = solver.solve(instance, _OneIterationRng())

    assert context.best_update_payloads == [((1, 2, 3),)]
    assert best.routes_as_tuples() == ((1, 2, 3),)
    assert audit["solver_algorithm_best_update_summary"]["best_update_count"] == 1
    assert audit["solver_algorithm_best_update_trace"][0]["route_count"] == 1


def _line_instance(customer_count: int) -> CvrpInstance:
    return CvrpInstance(
        name=f"line_{customer_count}",
        capacity=customer_count + 1,
        depot=0,
        nodes=tuple(
            [CvrpNode(id=0, x=0, y=0, demand=0)]
            + [
                CvrpNode(id=customer, x=customer, y=0, demand=1)
                for customer in range(1, customer_count + 1)
            ]
        ),
        allowed_routes=1,
        use_integer_cost=True,
    )


def _runtime_context_for_instance(
    instance: CvrpInstance,
) -> tuple[dict[str, object], SolverAlgorithmContext]:
    audit = solver_algorithm_defaults("policies/baseline_algorithm.py")
    context = SolverAlgorithmContext(
        instance=instance,
        instance_path=f"unit/{instance.name}.json",
        seed=1,
        rng=random.Random(1),
        time_limit_sec=1.0,
        start_time=time.perf_counter(),
        adapter=CvrpAdapter(_Spec()),  # type: ignore[arg-type]
        audit=audit,
    )
    return audit, context


def _scheduler_with_thresholds(
    context: SolverAlgorithmContext,
    *,
    use_vns: bool,
    vns_threshold: int,
    alns_threshold: int,
) -> baseline_scheduler._ALNSVNSSolver:
    return baseline_scheduler._ALNSVNSSolver(
        time_limit=1.0,
        destroy_ratio=(0.1, 0.1),
        segment_length=10,
        reaction_factor=0.2,
        vns_max_no_improve=1,
        use_vns=use_vns,
        cw_threshold=0,
        vns_threshold=vns_threshold,
        alns_threshold=alns_threshold,
        max_destroy_customers=1,
        max_routes=1,
        context=context,
    )


def test_size70_two_opt_fallback_activates_when_full_vns_is_skipped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instance = _line_instance(70)
    bad_initial = _Solution(
        instance,
        [_Route(instance, [1, 3, 2] + list(range(4, 71)))],
    )
    monkeypatch.setattr(
        baseline_scheduler,
        "_sweep_construction",
        lambda current_instance: bad_initial.copy(),
    )
    audit, context = _runtime_context_for_instance(instance)
    solver = _scheduler_with_thresholds(
        context,
        use_vns=True,
        vns_threshold=69,
        alns_threshold=69,
    )

    best = solver.solve(instance, random.Random(1))

    phase = "size70_two_opt_initial"
    assert best.routes_as_tuples()[0][:4] == (1, 2, 3, 4)
    assert best.stop_reason == "alns_threshold"
    assert phase in audit["solver_algorithm_phase_runtime_ms"]
    assert "vns_initial" not in audit["solver_algorithm_phase_runtime_ms"]
    assert audit["solver_algorithm_phase_accepted_moves"][phase] >= 1
    assert audit["solver_algorithm_phase_best_delta"][phase] > 0.0
    assert audit["solver_algorithm_best_delta"] > 0.0
    assert audit["solver_algorithm_best_update_summary"]["best_update_count"] == 1
    assert audit["solver_algorithm_best_update_summary"]["phase_counts"][phase] == 1
    assert audit["solver_algorithm_best_update_trace"][0]["phase"] == phase
    assert audit["solver_algorithm_best_update_trace"][0]["operator"] == "two_opt_intra"
    assert audit["solver_algorithm_best_update_trace"][0]["delta_from_previous_best"] > 0.0


def test_below_size70_keeps_existing_vns_initial_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instance = _line_instance(69)
    initial = _Solution(
        instance,
        [_Route(instance, [1, 3, 2] + list(range(4, 70)))],
    )
    vns_calls: list[int] = []

    def fake_vns(solution, operators, max_no_improve, context, reserve):
        vns_calls.append(len(operators))
        # A claimed improvement without an objective change is not direct effect.
        return True

    def fail_two_opt(*args, **kwargs):
        raise AssertionError("below-size70 path must keep full VNS behavior")

    monkeypatch.setattr(
        baseline_scheduler,
        "_sweep_construction",
        lambda current_instance: initial.copy(),
    )
    monkeypatch.setattr(baseline_scheduler, "_vns", fake_vns)
    monkeypatch.setattr(baseline_scheduler, "_two_opt_intra_polish", fail_two_opt)
    audit, context = _runtime_context_for_instance(instance)
    solver = _scheduler_with_thresholds(
        context,
        use_vns=True,
        vns_threshold=69,
        alns_threshold=68,
    )

    best = solver.solve(instance, random.Random(1))

    assert vns_calls == [7]
    assert best.routes_as_tuples()[0][:4] == (1, 3, 2, 4)
    assert "vns_initial" in audit["solver_algorithm_phase_runtime_ms"]
    assert "size70_two_opt_initial" not in audit["solver_algorithm_phase_runtime_ms"]
    assert audit["solver_algorithm_accepted_moves"] == 0
    assert [
        event["lane"] for event in audit["typed_telemetry_events"]
    ] == ["attempt"]
    assert audit["typed_telemetry_summary"]["lane_counts"]["direct_effect"] == 0


def test_initial_vns_records_direct_effect_only_for_local_objective_improvement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instance = _line_instance(4)
    initial = _Solution(instance, [_Route(instance, [1, 3, 2, 4])])

    def improving_vns(solution, operators, max_no_improve, context, reserve):
        del operators, max_no_improve, context, reserve
        solution.routes[0].customers = [1, 2, 3, 4]
        solution.rebuild_index()
        return True

    monkeypatch.setattr(
        baseline_scheduler,
        "_sweep_construction",
        lambda current_instance: initial.copy(),
    )
    monkeypatch.setattr(baseline_scheduler, "_vns", improving_vns)
    audit, context = _runtime_context_for_instance(instance)
    solver = _scheduler_with_thresholds(
        context,
        use_vns=True,
        vns_threshold=4,
        alns_threshold=0,
    )

    best = solver.solve(instance, random.Random(1))

    assert best.routes_as_tuples() == ((1, 2, 3, 4),)
    assert audit["solver_algorithm_move_attempts"] == 0
    assert audit["solver_algorithm_accepted_moves"] == 0
    events = audit["typed_telemetry_events"]
    assert [event["lane"] for event in events] == ["attempt", "direct_effect"]
    effect = events[1]
    assert effect["mechanism_id"] == "vns_initial"
    assert effect["attribution_scope"] == (
        "initial_vns_before_after_objective_boundary"
    )
    assert effect["before_ref"].startswith(
        "objective_snapshot:vns_initial_before:total_distance="
    )
    assert effect["after_ref"].startswith(
        "objective_snapshot:vns_initial_after:total_distance="
    )
    probes = audit["solver_algorithm_objective_probes"]
    before_probe = next(item for item in probes if item["name"] == "vns_initial_before")
    after_probe = next(item for item in probes if item["name"] == "vns_initial_after")
    assert before_probe["total_distance"] > after_probe["total_distance"]
    assert audit["typed_telemetry_summary"]["lane_counts"] == {
        "attempt": 1,
        "state_transition": 0,
        "direct_effect": 1,
        "associated_outcome": 0,
    }
