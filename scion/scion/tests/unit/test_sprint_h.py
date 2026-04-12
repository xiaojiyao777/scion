"""Sprint H unit tests: H3 registry class_name sync, H4 V5 stderr propagation."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from scion.config.problem import ProblemSpec, SearchSpace
from scion.core.models import (
    HypothesisProposal,
    OperatorConfig,
    PatchProposal,
    RunResult,
)
from scion.runtime.pool_manager import PoolManager
from scion.verification.state_mutation import check_state_mutation


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_spec(canary: str) -> ProblemSpec:
    ss = SearchSpace(
        editable=["operators/*.py"],
        frozen=["solver.py"],
        import_whitelist=["copy", "random", "collections"],
    )
    return ProblemSpec(
        name="test",
        root_dir="/tmp",
        canary_case_path=canary,
        operator_categories=["order_level"],
        search_space=ss,
    )


def _op(name: str, file_path: str, class_name: str, weight: float = 0.5) -> OperatorConfig:
    return OperatorConfig(
        name=name,
        file_path=file_path,
        category="order_level",
        weight=weight,
        class_name=class_name,
    )


def _make_hypothesis(action: str, target_file: str = "operators/foo.py") -> HypothesisProposal:
    return HypothesisProposal(
        hypothesis_text="test",
        change_locus="order_level",
        action=action,  # type: ignore[arg-type]
        target_file=target_file,
        suggested_weight=0.3,
    )


# ---------------------------------------------------------------------------
# H3: Registry class_name sync
# ---------------------------------------------------------------------------

class TestRegistryClassNameSync:
    def test_modify_updates_class_name(self, tmp_path):
        """modify action: class_name in registry is updated when LLM renames the class."""
        # Create workspace with renamed class
        ops_dir = tmp_path / "operators"
        ops_dir.mkdir()
        (ops_dir / "foo.py").write_text(
            "from operators.base import Operator\n\n"
            "class FooFixed(Operator):\n"
            "    def execute(self, solution, rng):\n"
            "        return solution\n"
        )

        champion_pool = {"foo": _op("foo", "operators/foo.py", "Foo")}
        pm = PoolManager(champion_pool)

        hypothesis = _make_hypothesis("modify", target_file="operators/foo.py")
        patch = PatchProposal(
            file_path="operators/foo.py",
            action="modify",
            code_content="class FooFixed(Operator): pass",
        )

        candidate_pool = pm.build_candidate_pool(
            champion_pool, hypothesis, patch, workspace=str(tmp_path)
        )

        assert "foo" in candidate_pool
        assert candidate_pool["foo"].class_name == "FooFixed", (
            f"Expected FooFixed, got {candidate_pool['foo'].class_name}"
        )

    def test_modify_keeps_old_class_name_when_no_workspace(self):
        """modify without workspace: falls back to old class_name (backward compat)."""
        champion_pool = {"foo": _op("foo", "operators/foo.py", "Foo")}
        pm = PoolManager(champion_pool)

        hypothesis = _make_hypothesis("modify", target_file="operators/foo.py")
        patch = PatchProposal(
            file_path="operators/foo.py",
            action="modify",
            code_content="class FooFixed(Operator): pass",
        )

        candidate_pool = pm.build_candidate_pool(champion_pool, hypothesis, patch)
        assert candidate_pool["foo"].class_name == "Foo"

    def test_create_new_uses_actual_class_name(self, tmp_path):
        """create_new action: class_name is extracted from actual file, not guessed."""
        ops_dir = tmp_path / "operators"
        ops_dir.mkdir()
        (ops_dir / "my_op.py").write_text(
            "from operators.base import Operator\n\n"
            "class MyOperatorV2(Operator):\n"
            "    def execute(self, solution, rng):\n"
            "        return solution\n"
        )

        champion_pool = {"swap": _op("swap", "operators/swap.py", "Swap")}
        pm = PoolManager(champion_pool)

        hypothesis = HypothesisProposal(
            hypothesis_text="test",
            change_locus="order_level",
            action="create_new",
            suggested_weight=0.3,
        )
        patch = PatchProposal(
            file_path="operators/my_op.py",
            action="create",
            code_content="class MyOperatorV2(Operator): pass",
        )

        candidate_pool = pm.build_candidate_pool(
            champion_pool, hypothesis, patch, workspace=str(tmp_path)
        )

        assert "my_op" in candidate_pool
        assert candidate_pool["my_op"].class_name == "MyOperatorV2", (
            f"Expected MyOperatorV2, got {candidate_pool['my_op'].class_name}"
        )

    def test_export_registry_contains_updated_class_name(self, tmp_path):
        """Full flow: export_registry writes the scanned class_name to YAML."""
        ops_dir = tmp_path / "operators"
        ops_dir.mkdir()
        (ops_dir / "foo.py").write_text(
            "class FooFixed:\n"
            "    def execute(self, solution, rng): return solution\n"
        )

        champion_pool = {"foo": _op("foo", "operators/foo.py", "Foo")}
        pm = PoolManager(champion_pool)

        hypothesis = _make_hypothesis("modify", target_file="operators/foo.py")
        patch = PatchProposal(
            file_path="operators/foo.py",
            action="modify",
            code_content="class FooFixed: pass",
        )

        candidate_pool = pm.build_candidate_pool(
            champion_pool, hypothesis, patch, workspace=str(tmp_path)
        )
        reg_path = pm.export_registry(candidate_pool, str(tmp_path))

        import yaml
        with open(reg_path) as f:
            data = yaml.safe_load(f)

        op_entries = {op["name"]: op for op in data["operators"]}
        assert op_entries["foo"]["class_name"] == "FooFixed"


# ---------------------------------------------------------------------------
# H4: V5 includes stderr on failure
# ---------------------------------------------------------------------------

class TestV5IncludesStderrOnFailure:
    def test_stderr_included_in_detail_on_solver_failure(self, tmp_path):
        """V5: when solver fails, result.detail must contain stderr content."""
        canary = str(tmp_path / "small.json")
        Path(canary).write_text("{}")
        spec = _make_spec(canary=canary)

        runner = MagicMock()
        runner.run_solver.return_value = RunResult(
            success=False,
            exit_code=1,
            stdout="",
            stderr="AttributeError: module 'operators.foo' has no attribute 'FooOld'",
            elapsed_ms=100,
            output=None,
            output_path=None,
            error_category="crash",
        )

        result = check_state_mutation(spec, runner, str(tmp_path))

        assert result.passed is False
        assert "AttributeError" in result.detail, (
            f"Expected AttributeError in detail, got: {result.detail!r}"
        )

    def test_solver_success_still_passes(self, tmp_path):
        """V5: consistent solution output still passes."""
        canary = str(tmp_path / "small.json")
        Path(canary).write_text("{}")
        spec = _make_spec(canary=canary)

        # Write a minimal valid solver output
        output_path = str(tmp_path / "out.json")
        output_data = {
            "vehicles": {"V1": {"vehicle_id": "V1", "vehicle_type": "HQ40",
                                "region": "Dongguan", "order_ids": ["O1"]}},
            "assignment": {"O1": "V1"},
            "objective": {"subcategory_splits": 0, "total_cost": 3300, "solve_time_ms": 50},
            "feasible": True,
        }
        Path(output_path).write_text(json.dumps(output_data))

        runner = MagicMock()
        runner.run_solver.return_value = RunResult(
            success=True,
            exit_code=0,
            stdout="",
            stderr="",
            elapsed_ms=100,
            output=None,
            output_path=output_path,
            error_category=None,
        )

        result = check_state_mutation(spec, runner, str(tmp_path))
        assert result.passed is True
