"""Focused tests split from test_protocol.py."""

from .protocol_test_support import *  # noqa: F401,F403

def test_run_canary_pass(tmp_path):
    """Canary calls cand first, then champ. 2 cases × 1 seed = 4 calls."""
    runner = MagicMock()
    runner.run_solver.side_effect = [
        _make_run_result(2, 900, feasible=True),   # cand case_a seed1
        _make_run_result(2, 1000, feasible=True),  # champ case_a seed1
        _make_run_result(2, 900, feasible=True),   # cand case_b seed1
        _make_run_result(2, 1000, feasible=True),  # champ case_b seed1
    ]
    proto = _make_protocol(runner, tmp_path)
    result = proto.run_canary("/cand", "/champ")
    assert result.passed


def test_run_canary_fail_infeasible(tmp_path):
    """Candidate infeasible while champion feasible → veto."""
    runner = MagicMock()
    runner.run_solver.side_effect = [
        _make_run_result(2, 900, feasible=False),  # cand case_a infeasible
        _make_run_result(2, 1000, feasible=True),  # champ case_a feasible
    ]
    proto = _make_protocol(runner, tmp_path)
    result = proto.run_canary("/cand", "/champ")
    assert not result.passed


def test_run_canary_fail_solver_crash(tmp_path):
    runner = MagicMock()
    runner.run_solver.return_value = RunResult(
        success=False, exit_code=1, stdout="", stderr="crash",
        elapsed_ms=50, error_category="crash",
    )
    proto = _make_protocol(runner, tmp_path)
    result = proto.run_canary("/cand", "/champ")
    assert not result.passed


def test_run_canary_fail_candidate_operator_runtime_error(tmp_path):
    runner = MagicMock()
    runner.run_solver.side_effect = [
        _make_run_result(
            2,
            900,
            feasible=True,
            runtime={
                "operator_errors": 1,
                "operator_events": [
                    {"operator": "bad_op", "status": "error", "detail": "boom"}
                ],
            },
        ),
        _make_run_result(2, 1000, feasible=True),
    ]
    proto = _make_protocol(runner, tmp_path)

    result = proto.run_canary("/cand", "/champ")

    assert not result.passed
    assert "runtime audit failed" in (result.reason or "")


def test_run_canary_selected_surface_runtime_fields_fail_closed(tmp_path):
    runner = MagicMock()
    runner.run_solver.return_value = _make_run_result(
        1,
        900,
        feasible=True,
        runtime={"dispatch_loaded": True},
    )
    proto = _make_protocol(
        runner,
        tmp_path,
        problem_spec=_surface_problem_spec(),
    )

    result = proto.run_canary(
        "/cand",
        "/champ",
        selected_surface="dispatch_policy",
    )

    assert result.passed is False
    assert "runtime audit failed" in (result.reason or "")
    assert "dispatch_errors" in (result.reason or "")
