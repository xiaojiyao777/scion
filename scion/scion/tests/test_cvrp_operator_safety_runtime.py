from __future__ import annotations

from scion.tests.cvrp_solver_runtime_support import *

def test_invalid_operator_outputs_do_not_pollute_solution(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)
    (workspace / "operators" / "bad_type.py").write_text(
        "\n".join(
            [
                "class BadType:",
                "    def execute(self, solution, instance, rng):",
                "        return []",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (workspace / "operators" / "missing_customers.py").write_text(
        "\n".join(
            [
                "from scion.problems.cvrp.models import CvrpSolution",
                "",
                "class MissingCustomers:",
                "    def execute(self, solution, instance, rng):",
                "        return CvrpSolution(routes=((1, 2),))",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (workspace / "registry.yaml").write_text(
        "\n".join(
            [
                "operators:",
                "  - name: bad_type",
                "    file_path: operators/bad_type.py",
                "    class_name: BadType",
                "    weight: 2.0",
                "  - name: missing_customers",
                "    file_path: operators/missing_customers.py",
                "    class_name: MissingCustomers",
                "    weight: 1.0",
                "",
            ]
        ),
        encoding="utf-8",
    )

    raw = _run_solver(
        workspace,
        "data/operator_case.json",
        registry_path=str(workspace / "registry.yaml"),
    )

    assert raw["routes"] == [[1, 2, 3, 4, 5]]
    assert raw["objective"]["total_distance"] == 16.0
    assert raw["runtime"]["operator_loaded"] == 2
    assert raw["runtime"]["operator_accepted"] == 0
    assert raw["runtime"]["operator_skipped"] >= 2
    assert raw["runtime"]["operator_errors"] >= 2
    assert raw["runtime"]["operator_invalid_outputs"] >= 2
    assert {
        (event["operator"], event["status"])
        for event in raw["runtime"]["operator_events"]
    } >= {
        ("bad_type", "error"),
        ("missing_customers", "error"),
    }
    issue = runtime_audit_failure_from_raw(raw)
    assert issue is not None
    assert issue["error_category"] == "operator_runtime_error"

    adapter, instance, artifact = _artifact(raw, workspace, "data/operator_case.json")
    assert adapter.check_solution_consistency(artifact, instance).passed is True
    assert adapter.check_feasibility(artifact, instance).passed is True


def test_operator_exception_is_reported_in_run_result_runtime_audit(
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)
    (workspace / "operators" / "bad_attribute.py").write_text(
        "\n".join(
            [
                "class BadAttribute:",
                "    def execute(self, solution, instance, rng):",
                "        _ = instance.vehicle_capacity",
                "        return solution",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (workspace / "registry.yaml").write_text(
        "\n".join(
            [
                "operators:",
                "  - name: bad_attribute",
                "    file_path: operators/bad_attribute.py",
                "    class_name: BadAttribute",
                "    weight: 1.0",
                "",
            ]
        ),
        encoding="utf-8",
    )

    result = _runner().run_solver(
        workdir=str(workspace),
        instance_path="data/operator_case.json",
        seed=14,
        time_limit_sec=2,
        registry_path=str(workspace / "registry.yaml"),
    )

    assert result.success is True
    assert result.output is not None
    assert result.output.runtime["operator_errors"] == 1
    issue = runtime_audit_failure_from_result(result)
    assert issue is not None
    assert issue["error_category"] == "operator_runtime_error"
    assert "vehicle_capacity" in issue["operator_events"][0]["detail"]


def test_registry_path_escape_entry_is_not_loaded(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    _write_operator_case(workspace)
    escaped = tmp_path / "escaped_operator.py"
    escaped.write_text(
        "\n".join(
            [
                "from scion.problems.cvrp.models import CvrpSolution",
                "",
                "class EscapedOperator:",
                "    def execute(self, solution, instance, rng):",
                "        return CvrpSolution(routes=((1, 2, 3, 5, 4),))",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (workspace / "registry.yaml").write_text(
        "\n".join(
            [
                "operators:",
                "  - name: escaped_operator",
                "    file_path: ../escaped_operator.py",
                "    class_name: EscapedOperator",
                "    weight: 1.0",
                "",
            ]
        ),
        encoding="utf-8",
    )

    raw = _run_solver(
        workspace,
        "data/operator_case.json",
        registry_path=str(workspace / "registry.yaml"),
    )

    assert raw["routes"] == [[1, 2, 3, 4, 5]]
    assert raw["objective"]["total_distance"] == 16.0
    assert raw["runtime"]["operator_loaded"] == 0
    assert raw["runtime"]["operator_skipped"] == 1
    assert raw["runtime"]["operator_events"] == [
        {
            "operator": "escaped_operator",
            "status": "skipped",
            "detail": "operator path escapes workspace",
        }
    ]
