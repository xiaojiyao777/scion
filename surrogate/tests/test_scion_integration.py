"""Real integration tests: warehouse_delivery with actual solver.

These tests use the real surrogate solver, real ContractGate, real Runner,
and real ExperimentProtocol — everything except the LLM (which is mocked
with warehouse_delivery-compatible responses).

Catches config mismatches (import_whitelist, registry.yaml, etc.) that
unit tests with synthetic specs cannot detect.

Requires: surrogate/ directory with solver.py, operators/, data/, registry.yaml
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Optional

import pytest

from scion.config.problem import ProblemSpec, ProtocolConfig, SplitManifest, SeedLedgerConfig
from scion.core.campaign import CampaignManager
from scion.core.models import ChampionState, Decision, ExperimentStage
from scion.core.termination import TerminationConfig
from scion.proposal.mock_client import MockLLMClient
from scion.protocol.experiment import ExperimentProtocol, SplitManager, SeedLedger
from scion.runtime.subprocess_runner import LocalSubprocessRunner
from scion.runtime.workspace import WorkspaceMaterializer


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCION_ROOT = _REPO_ROOT / "scion"
_PROBLEM_DIR = _SCION_ROOT / "problems" / "warehouse_delivery"
_SURROGATE_DIR = _REPO_ROOT / "surrogate"


def _surrogate_available() -> bool:
    """Check if the surrogate solver directory exists with all required files."""
    required = [
        _SURROGATE_DIR / "solver.py",
        _SURROGATE_DIR / "oracle.py",
        _SURROGATE_DIR / "registry.yaml",
        _SURROGATE_DIR / "operators" / "move_order.py",
        _SURROGATE_DIR / "data" / "instance_small_1.json",
    ]
    return all(p.exists() for p in required)


skip_no_surrogate = pytest.mark.skipif(
    not _surrogate_available(),
    reason="surrogate solver not available (run from full repo)",
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def problem_spec() -> ProblemSpec:
    return ProblemSpec.from_yaml(str(_PROBLEM_DIR / "problem.yaml"))


@pytest.fixture
def protocol_config() -> ProtocolConfig:
    return ProtocolConfig.from_yaml(str(_PROBLEM_DIR / "protocol.yaml"))


@pytest.fixture
def split_manifest() -> SplitManifest:
    return SplitManifest.from_yaml(str(_PROBLEM_DIR / "split_manifest.yaml"))


@pytest.fixture
def seed_ledger() -> SeedLedgerConfig:
    return SeedLedgerConfig.from_yaml(str(_PROBLEM_DIR / "seed_ledger.yaml"))


def _read_operator(name: str) -> str:
    """Read the real source code of an operator from surrogate/operators/."""
    return (_SURROGATE_DIR / "operators" / name).read_text()


def _make_mock_llm(
    *,
    target_file: str = "operators/move_order.py",
    change_locus: str = "order_level",
    code_modifier=None,
) -> MockLLMClient:
    """Create a MockLLMClient with warehouse_delivery-compatible responses.

    Args:
        target_file: Operator file to "modify".
        change_locus: Must be in problem.yaml operator_categories.
        code_modifier: Optional callable (str) -> str to transform the code.
                       Default: adds a comment (no behavioral change).
    """
    original_code = _read_operator(Path(target_file).name)

    if code_modifier is not None:
        modified_code = code_modifier(original_code)
    else:
        # Default: trivial change (add comment) — no behavioral difference
        modified_code = original_code.replace(
            "class MoveOrder(Operator):",
            "class MoveOrder(Operator):  # integration-test-modified",
        )

    hypothesis = {
        "hypothesis_text": "Integration test: modify operator.",
        "change_locus": change_locus,
        "action": "modify",
        "target_file": target_file,
        "predicted_direction": "improve",
        "target_weakness": "Integration test.",
        "expected_effect": "Integration test.",
        "suggested_weight": 0.3,
    }
    patch = {
        "file_path": target_file,
        "action": "modify",
        "code_content": modified_code,
        "test_hint": "Integration test.",
    }
    return MockLLMClient(mode="success", hypothesis_response=hypothesis, patch_response=patch)


def _build_real_campaign(
    tmp_path: Path,
    problem_spec: ProblemSpec,
    protocol_config: ProtocolConfig,
    split_manifest: SplitManifest,
    seed_ledger: SeedLedgerConfig,
    llm_client: MockLLMClient,
    *,
    max_experiments: int = 50,
    time_limit_sec: int = 30,
) -> CampaignManager:
    """Build a CampaignManager wired to real solver + ExperimentProtocol."""
    campaign_dir = str(tmp_path / "campaign")
    Path(campaign_dir).mkdir(parents=True, exist_ok=True)

    materializer = WorkspaceMaterializer(
        campaign_dir,
        frozen_patterns=frozenset(problem_spec.search_space.frozen)
        if problem_spec.search_space.frozen else None,
    )
    code_hash = materializer.compute_code_hash(problem_spec.root_dir)
    champion = ChampionState(
        version=1,
        operator_pool={},
        solver_config_hash="initial",
        code_snapshot_path=problem_spec.root_dir,
        code_snapshot_hash=code_hash,
    )

    runner = LocalSubprocessRunner()
    split_mgr = SplitManager(split_manifest)
    seed_mgr = SeedLedger(seed_ledger)
    experiment_protocol = ExperimentProtocol(
        protocol_config=protocol_config,
        split_manager=split_mgr,
        seed_ledger=seed_mgr,
        runner=runner,
        time_limit_sec=time_limit_sec,
        metrics_dir=str(tmp_path / "metrics"),
    )

    return CampaignManager(
        problem_spec=problem_spec,
        protocol_config=protocol_config,
        split_manifest=split_manifest,
        seed_ledger=seed_ledger,
        llm_client=llm_client,
        champion=champion,
        campaign_dir=campaign_dir,
        experiment_protocol=experiment_protocol,
        termination_config=TerminationConfig(
            max_experiments=max_experiments,
            stagnation_limit=50,
        ),
    )


# ===========================================================================
# Test 1: Solver subprocess runs successfully on all instances
# ===========================================================================

@skip_no_surrogate
@pytest.mark.integration
class TestSolverSubprocess:
    """Verify LocalSubprocessRunner can execute real solver.py."""

    def test_solver_runs_on_small_instance(self):
        runner = LocalSubprocessRunner()
        result = runner.run_solver(
            workdir=str(_SURROGATE_DIR),
            instance_path="data/instance_small_1.json",
            seed=42,
            time_limit_sec=30,
            registry_path=str(_SURROGATE_DIR / "registry.yaml"),
        )
        assert result.success, f"Solver failed: exit={result.exit_code}, stderr={result.stderr[:300]}"
        assert result.output is not None
        assert result.output.feasible is True
        assert result.output.objective is not None

    @pytest.mark.parametrize("instance", [
        "data/instance_small_1.json",
        "data/instance_small_2.json",
        "data/instance_medium_1.json",
    ])
    def test_solver_runs_on_screening_instances(self, instance):
        """Solver must succeed on all screening split instances."""
        runner = LocalSubprocessRunner()
        result = runner.run_solver(
            workdir=str(_SURROGATE_DIR),
            instance_path=instance,
            seed=42,
            time_limit_sec=60,
            registry_path=str(_SURROGATE_DIR / "registry.yaml"),
        )
        assert result.success, (
            f"Solver failed on {instance}: exit={result.exit_code}, "
            f"stderr={result.stderr[:300]}"
        )

    def test_solver_output_has_required_fields(self):
        runner = LocalSubprocessRunner()
        result = runner.run_solver(
            workdir=str(_SURROGATE_DIR),
            instance_path="data/instance_small_1.json",
            seed=42,
            time_limit_sec=30,
            registry_path=str(_SURROGATE_DIR / "registry.yaml"),
        )
        assert result.output is not None
        # SolverOutput must have the fields ExperimentProtocol expects
        assert hasattr(result.output, "feasible")
        assert hasattr(result.output, "objective")
        assert hasattr(result.output, "vehicles")
        assert hasattr(result.output, "assignment")


# ===========================================================================
# Test 2: ContractGate accepts real operator code
# ===========================================================================

@skip_no_surrogate
@pytest.mark.integration
class TestContractGateRealCode:
    """Verify ContractGate passes real warehouse_delivery operator code."""

    def test_real_move_order_passes_contract(self, problem_spec):
        from scion.contract.gate import ContractGate
        from scion.core.models import HypothesisProposal, PatchProposal

        gate = ContractGate(problem_spec)
        real_code = _read_operator("move_order.py")

        # Hypothesis check
        hypothesis = HypothesisProposal(
            hypothesis_text="Test real code.",
            change_locus="order_level",
            action="modify",
            target_file="operators/move_order.py",
            predicted_direction="improve",
            target_weakness="test",
            expected_effect="test",
        )
        h_result = gate.validate_hypothesis(hypothesis, [], [])
        assert h_result.passed, f"Hypothesis contract failed: {h_result.failure_reason}"

        # Patch check
        patch = PatchProposal(
            file_path="operators/move_order.py",
            action="modify",
            code_content=real_code,
        )
        p_result = gate.validate_patch(patch)
        assert p_result.passed, (
            f"Patch contract failed: {p_result.failure_reason}\n"
            f"Checks: {[(c.name, c.passed, c.detail) for c in p_result.checks]}"
        )

    @pytest.mark.parametrize("operator_file,locus", [
        ("move_order.py", "order_level"),
        ("swap_orders.py", "order_level"),
        ("merge_vehicles.py", "vehicle_level"),
        ("split_vehicle.py", "vehicle_level"),
        ("change_vehicle_type.py", "vehicle_level"),
        ("destroy_rebuild.py", "order_level"),
    ])
    def test_all_operators_pass_contract(self, problem_spec, operator_file, locus):
        """Every existing operator's code must pass the ContractGate."""
        from scion.contract.gate import ContractGate
        from scion.core.models import PatchProposal

        gate = ContractGate(problem_spec)
        code = _read_operator(operator_file)

        patch = PatchProposal(
            file_path=f"operators/{operator_file}",
            action="modify",
            code_content=code,
        )
        result = gate.validate_patch(patch)
        assert result.passed, (
            f"Contract failed for {operator_file}: {result.failure_reason}\n"
            f"Checks: {[(c.name, c.passed, c.detail) for c in result.checks]}"
        )


# ===========================================================================
# Test 3: Full pipeline — 1 round with real solver
# ===========================================================================

@skip_no_surrogate
@pytest.mark.integration
@pytest.mark.slow
class TestFullPipelineRealSolver:
    """End-to-end: MockLLM + real ContractGate + real solver + real ExperimentProtocol."""

    def test_one_round_completes(
        self, tmp_path, problem_spec, protocol_config, split_manifest, seed_ledger,
    ):
        """A single campaign round must complete without error."""
        llm_client = _make_mock_llm()
        cm = _build_real_campaign(
            tmp_path, problem_spec, protocol_config, split_manifest, seed_ledger,
            llm_client, max_experiments=5, time_limit_sec=30,
        )

        result = cm.run_one_step()
        assert result is not None
        assert result.action in ("explore", "create_branch")
        assert not result.stopped

    def test_one_round_produces_screening_metrics(
        self, tmp_path, problem_spec, protocol_config, split_manifest, seed_ledger,
    ):
        """Metrics JSON must be produced with valid screening pairs."""
        llm_client = _make_mock_llm()
        cm = _build_real_campaign(
            tmp_path, problem_spec, protocol_config, split_manifest, seed_ledger,
            llm_client, max_experiments=5, time_limit_sec=30,
        )

        cm.run_one_step()

        metrics_dir = tmp_path / "metrics"
        metrics_files = list(metrics_dir.glob("*.json"))
        assert len(metrics_files) >= 1, "No metrics files produced"

        data = json.loads(metrics_files[0].read_text())
        assert data["stage"] == "screening"
        assert len(data["pairs"]) > 0, "No evaluation pairs in metrics"

        # Each pair must have required fields
        for pair in data["pairs"]:
            assert "case" in pair
            assert "seed" in pair
            assert "comparison" in pair
            assert "delta" in pair

    def test_trivial_patch_produces_all_ties(
        self, tmp_path, problem_spec, protocol_config, split_manifest, seed_ledger,
    ):
        """A comment-only patch must produce all ties (same solver behavior)."""
        llm_client = _make_mock_llm()  # default: comment-only change
        cm = _build_real_campaign(
            tmp_path, problem_spec, protocol_config, split_manifest, seed_ledger,
            llm_client, max_experiments=5, time_limit_sec=30,
        )

        cm.run_one_step()

        metrics_dir = tmp_path / "metrics"
        metrics_files = list(metrics_dir.glob("*.json"))
        assert len(metrics_files) >= 1

        data = json.loads(metrics_files[0].read_text())
        comparisons = [p["comparison"] for p in data["pairs"]]
        assert all(c == "tie" for c in comparisons), (
            f"Expected all ties for trivial patch, got: {comparisons}"
        )

    def test_three_rounds_no_promotion(
        self, tmp_path, problem_spec, protocol_config, split_manifest, seed_ledger,
    ):
        """3 rounds with trivial patch: no promotion, champion stays at v1."""
        llm_client = _make_mock_llm()
        cm = _build_real_campaign(
            tmp_path, problem_spec, protocol_config, split_manifest, seed_ledger,
            llm_client, max_experiments=10, time_limit_sec=30,
        )

        cm.run(max_rounds=3)

        state = cm.get_state()
        assert state["champion_version"] == 1, "Trivial patch should not promote"
        assert state["n_experiments"] >= 1


# ===========================================================================
# Test 4: Config consistency — whitelist covers all operator imports
# ===========================================================================

@skip_no_surrogate
@pytest.mark.integration
class TestConfigConsistency:
    """Verify problem.yaml config is consistent with actual operator code."""

    def test_import_whitelist_covers_all_operators(self, problem_spec):
        """Every import used by existing operators must be in the whitelist."""
        import ast

        whitelist = set(problem_spec.search_space.import_whitelist)
        operators_dir = Path(problem_spec.root_dir) / "operators"

        violations = []
        for py_file in sorted(operators_dir.glob("*.py")):
            if py_file.name in ("__init__.py", "base.py"):
                continue
            tree = ast.parse(py_file.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        top = alias.name.split(".")[0]
                        if top not in whitelist:
                            violations.append((py_file.name, top))
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        top = node.module.split(".")[0]
                        if top not in whitelist:
                            violations.append((py_file.name, top))

        assert not violations, (
            f"Operators use imports not in whitelist:\n"
            + "\n".join(f"  {f}: import {m}" for f, m in violations)
        )

    def test_registry_yaml_exists(self, problem_spec):
        """registry.yaml must exist in root_dir for solver to work with runner."""
        registry = Path(problem_spec.root_dir) / "registry.yaml"
        assert registry.exists(), (
            f"registry.yaml not found in {problem_spec.root_dir}. "
            f"Runner passes --registry to solver, which will crash without it."
        )

    def test_all_instances_exist(self, split_manifest, problem_spec):
        """All instance files referenced in split_manifest must exist."""
        root = Path(problem_spec.root_dir)
        all_cases = split_manifest.screening + split_manifest.validation + split_manifest.frozen
        missing = [c for c in all_cases if not (root / c).exists()]
        assert not missing, f"Missing instance files: {missing}"
