from __future__ import annotations

from types import SimpleNamespace

from scion.runtime.telemetry_guard import build_telemetry_guard_summary


def _problem_spec() -> SimpleNamespace:
    return SimpleNamespace(
        research_surfaces=[
            SimpleNamespace(
                name="solver",
                evidence=SimpleNamespace(
                    required_runtime_fields=[
                        "solver_search_iterations",
                        "solver_phase_runtime_ms",
                    ],
                    stage_budget_runtime_fields=["solver_phase_runtime_ms"],
                ),
            )
        ]
    )


def test_telemetry_guard_flags_stage_budget_starvation() -> None:
    summary = build_telemetry_guard_summary(
        candidate_runtimes=[
            {
                "solver_search_iterations": 4,
                "solver_phase_runtime_ms": {"search": 0},
            }
        ],
        champion_runtimes=[
            {
                "solver_search_iterations": 7,
                "solver_phase_runtime_ms": {"search": 25},
            }
        ],
        problem_spec=_problem_spec(),
        selected_surface="solver",
        expected_telemetry={"budget": ["solver_phase_runtime_ms"]},
    )

    assert summary["passed"] is False
    assert summary["failures"][0]["code"] == "TELEMETRY_BUDGET_STARVED"
    assert summary["fields"]["solver_phase_runtime_ms"]["champion_positive"] == 1
