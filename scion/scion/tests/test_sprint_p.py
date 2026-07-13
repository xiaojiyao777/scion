"""Tests for Sprint P: campaign journal, weight-opt feedback, solution consistency, canary."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from scion.config.problem import ProblemSpec, SearchSpace
from scion.core.canary import CanarySetVersion
from scion.core.models import RunResult
from scion.verification.state_mutation import check_state_mutation


# ---------------------------------------------------------------------------
# W11: Solution consistency diagnosis
# ---------------------------------------------------------------------------

class TestSolutionConsistencyDiagnosis:
    def test_legacy_oracle_consistency_hook_can_reject(self, tmp_path) -> None:
        _write_warehouse_oracle(tmp_path)
        canary = tmp_path / "small.json"
        canary.write_text("{}", encoding="utf-8")
        spec = _make_spec(tmp_path, str(canary))
        output = {
            "solution": {
                "assignment": {"o1": "v1"},
                "vehicles": {
                    "v1": {"order_ids": ["o1"]},
                    "v2": {"order_ids": ["o1"]},
                },
            }
        }

        result = check_state_mutation(spec, _runner_for_output(tmp_path, output), str(tmp_path))

        assert result.passed is False
        assert "[CANDIDATE]" in result.detail
        assert "multiple vehicles" in result.detail

    def test_legacy_oracle_consistency_hook_can_pass(self, tmp_path) -> None:
        _write_warehouse_oracle(tmp_path)
        canary = tmp_path / "small.json"
        canary.write_text("{}", encoding="utf-8")
        spec = _make_spec(tmp_path, str(canary))
        output = {
            "solution": {
                "assignment": {"o1": "v1", "o2": "v1"},
                "vehicles": {"v1": {"order_ids": ["o1", "o2"]}},
            }
        }

        result = check_state_mutation(spec, _runner_for_output(tmp_path, output), str(tmp_path))

        assert result.passed is True
        assert "oracle solution consistency ok" in result.detail

    def test_missing_legacy_oracle_hook_is_skipped(self, tmp_path) -> None:
        canary = tmp_path / "small.json"
        canary.write_text("{}", encoding="utf-8")
        spec = _make_spec(tmp_path, str(canary))

        result = check_state_mutation(spec, _runner_for_output(tmp_path, {}), str(tmp_path))

        assert result.passed is True
        assert "skipped" in result.detail


# ---------------------------------------------------------------------------
# W12: Canary versioning
# ---------------------------------------------------------------------------

class TestCanaryVersioning:
    def test_initial_version(self) -> None:
        v = CanarySetVersion(version="v1", cases=["/data/c1.json", "/data/c2.json"])
        assert len(v.cases) == 2
        assert v.accumulated_candidates == []

    def test_accumulate_candidate(self) -> None:
        v = CanarySetVersion(version="v1", cases=["/data/c1.json"])
        v.add_candidate("/data/c3.json", "known_failure")
        assert len(v.accumulated_candidates) == 1
        assert v.cases == ["/data/c1.json"]

    def test_no_duplicate_candidates(self) -> None:
        v = CanarySetVersion(version="v1", cases=[])
        v.add_candidate("/data/c3.json", "reason1")
        v.add_candidate("/data/c3.json", "reason1")
        assert len(v.accumulated_candidates) == 1

    def test_export_next_version(self) -> None:
        v = CanarySetVersion(version="v1", cases=["/data/c1.json"])
        v.add_candidate("/data/c3.json", "known_failure")
        v2 = v.export_next_version("v2")
        assert v2.version == "v2"
        assert "/data/c1.json" in v2.cases
        assert "/data/c3.json" in v2.cases
        assert v2.accumulated_candidates == []

    def test_export_no_duplicate_existing(self) -> None:
        v = CanarySetVersion(version="v1", cases=["/data/c1.json"])
        v.add_candidate("/data/c1.json", "already_exists")
        v2 = v.export_next_version("v2")
        assert v2.cases.count("/data/c1.json") == 1


def _make_spec(root: Path, canary: str) -> ProblemSpec:
    return ProblemSpec(
        name="test",
        root_dir=str(root),
        canary_case_path=canary,
        operator_categories=["local_search"],
        search_space=SearchSpace(
            editable=["operators/*.py"],
            frozen=["solver.py"],
            import_whitelist=["random", "math"],
        ),
    )


def _runner_for_output(root: Path, output: dict) -> SimpleNamespace:
    output_path = root / "solver-output.json"
    output_path.write_text(json.dumps(output), encoding="utf-8")

    def run_solver(workdir, instance_path, seed, time_limit_sec, registry_path):
        return RunResult(
            success=True,
            exit_code=0,
            stdout="",
            stderr="",
            elapsed_ms=100,
            output=None,
            output_path=str(output_path),
            error_category=None,
        )

    return SimpleNamespace(run_solver=run_solver)


def _write_warehouse_oracle(root: Path) -> None:
    (root / "oracle.py").write_text(
        """
def check_solver_output_consistency(raw, canary):
    solution = raw.get("solution", raw)
    assignment = solution.get("assignment", {})
    vehicles = solution.get("vehicles", {})
    seen = {}
    for vehicle_id, vehicle in vehicles.items():
        for order_id in vehicle.get("order_ids", []):
            if order_id in seen:
                return {
                    "passed": False,
                    "diagnosis": "CANDIDATE",
                    "reasons": [
                        f"order {order_id} in multiple vehicles: "
                        f"{seen[order_id]} and {vehicle_id}"
                    ],
                }
            seen[order_id] = vehicle_id
    for order_id, vehicle_id in assignment.items():
        if seen.get(order_id) != vehicle_id:
            return {
                "passed": False,
                "diagnosis": "CANDIDATE",
                "reasons": [f"order {order_id} assignment mismatch"],
            }
    return {"passed": True}
""".lstrip(),
        encoding="utf-8",
    )
