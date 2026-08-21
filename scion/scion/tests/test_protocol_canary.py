"""Focused tests split from test_protocol.py."""

from .protocol_test_support import *  # noqa: F401,F403


def test_run_canary_pass(tmp_path):
    """Canary calls cand first, then champ. 2 cases × 1 seed = 4 calls."""
    runner = MagicMock()
    runner.run_solver.side_effect = [
        _make_run_result(2, 900, feasible=True),  # cand case_a seed1
        _make_run_result(2, 1000, feasible=True),  # champ case_a seed1
        _make_run_result(2, 900, feasible=True),  # cand case_b seed1
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
        success=False,
        exit_code=1,
        stdout="",
        stderr="crash",
        elapsed_ms=50,
        error_category="crash",
    )
    proto = _make_protocol(runner, tmp_path)
    result = proto.run_canary("/cand", "/champ")
    assert not result.passed
    assert result.details["candidate_outcome"]["output_present"] is False
    assert "output_path" not in result.details["candidate_outcome"]


def test_complete_pair_canary_runs_champion_after_candidate_failure(tmp_path):
    runner = MagicMock()
    runner.run_solver.side_effect = [
        RunResult(
            success=False,
            exit_code=1,
            stdout="",
            stderr="candidate crash",
            elapsed_ms=50,
            error_category="crash",
        ),
        _make_run_result(2, 1000, feasible=True),
    ]
    proto = _make_protocol(runner, tmp_path)

    result = proto.run_canary("/cand", "/champ", require_complete_pairs=True)

    assert result.passed is False
    assert runner.run_solver.call_count == 2
    assert result.details["pair_failure_scope"] == "candidate"
    assert result.details["candidate_failed_pairs"] == 1
    assert result.details["champion_failed_pairs"] == 0


def test_complete_pair_canary_success_records_comparator_observed(tmp_path):
    runner = MagicMock()
    runner.run_solver.return_value = _make_run_result(2, 900, feasible=True)
    proto = _make_protocol(runner, tmp_path)

    result = proto.run_canary("/cand", "/champ", require_complete_pairs=True)

    assert result.passed is True
    assert result.details["complete_pairs_required"] is True
    assert result.details["champion_status"] == "passed"


def test_complete_pair_canary_rejects_champion_failure(tmp_path):
    runner = MagicMock()
    runner.run_solver.side_effect = [
        _make_run_result(2, 900, feasible=True),
        RunResult(
            success=False,
            exit_code=1,
            stdout="",
            stderr="champion crash",
            elapsed_ms=50,
            error_category="crash",
        ),
    ]
    proto = _make_protocol(runner, tmp_path)

    result = proto.run_canary("/cand", "/champ", require_complete_pairs=True)

    assert result.passed is False
    assert result.failure_category == "incomplete_evidence"
    assert result.reason_codes == ("CANARY_CHAMPION_FAILURE",)
    assert result.details["pair_failure_scope"] == "champion"


def test_complete_pair_canary_distinguishes_shared_and_bilateral_failures(tmp_path):
    for categories, stderrs, expected in [
        (("crash", "crash"), ("same", "same"), "shared"),
        (("timeout", "crash"), ("same", "same"), "bilateral"),
        (("crash", "crash"), ("left", "right"), "bilateral"),
    ]:
        runner = MagicMock()
        runner.run_solver.side_effect = [
            RunResult(
                success=False,
                exit_code=1,
                stdout="",
                stderr=stderr,
                elapsed_ms=50,
                error_category=category,
            )
            for category, stderr in zip(categories, stderrs)
        ]
        proto = _make_protocol(runner, tmp_path)

        result = proto.run_canary("/cand", "/champ", require_complete_pairs=True)

        assert result.passed is False
        assert result.details["pair_failure_scope"] == expected
        assert result.details["shared_failed_pairs"] == int(expected == "shared")
        assert result.details["bilateral_failed_pairs"] == int(expected == "bilateral")
        assert result.details["candidate_failed_pairs"] == int(expected == "bilateral")
        assert result.details["champion_failed_pairs"] == 1


def test_complete_pair_canary_applies_selected_surface_audit_to_both_arms(tmp_path):
    runner = MagicMock()
    runner.run_solver.return_value = _make_run_result(
        1,
        900,
        feasible=True,
        runtime={"dispatch_loaded": True, "dispatch_errors": 1},
    )
    problem_spec = _surface_problem_spec()
    problem_spec.research_surfaces[0].evidence.runtime_field_roles = {
        "diagnostic": ["dispatch_errors"]
    }
    proto = _make_protocol(
        runner,
        tmp_path,
        problem_spec=problem_spec,
    )

    result = proto.run_canary(
        "/cand",
        "/champ",
        selected_surface="dispatch_policy",
        require_complete_pairs=True,
    )

    assert result.passed is False
    assert result.failure_category == "incomplete_evidence"
    assert result.details["pair_failure_scope"] == "shared"


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


def test_run_canary_selected_surface_runtime_fields_are_diagnostic(tmp_path):
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

    assert result.passed is True
    assert "runtime audit failed" not in (result.reason or "")
    assert runner.run_solver.call_count == 4
