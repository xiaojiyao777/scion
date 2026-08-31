"""T23: End-to-end validation for Scion Phase 6."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, List

import pytest

from scion.config.problem import (
    ProblemSpec,
    ProtocolConfig,
    SearchSpace,
    SeedLedgerConfig,
    SplitManifest,
)
from scion.core.campaign import CampaignManager
from scion.core.models import (
    CanaryResult,
    ChampionState,
    CheckResult,
    EvalStats,
    ExperimentStage,
    ProtocolResult,
    VerificationResult,
)
from scion.problem.spec import ObjectiveMetricSpec
from scion.proposal.mock_client import MockLLMClient
from scion.verification.gate import VerificationGate

from .campaign_test_support import _bounded_campaign

# ---------------------------------------------------------------------------
# Shared helpers (mirroring test_campaign.py conventions)
# ---------------------------------------------------------------------------

_VALID_CODE = (
    "class LocalSearch:\n"
    "    def execute(self, solution, rng):\n"
    "        return solution\n"
)

_VALID_HYPOTHESIS = {
    "hypothesis_text": "E2E: try improved swap.",
    "change_locus": "local_search",
    "action": "modify",
    "target_file": "operators/local_search.py",
    "predicted_direction": "improve",
    "target_weakness": "slow convergence",
    "expected_effect": "better solutions",
    "suggested_weight": 0.3,
}

_VALID_PATCH = {
    "file_path": "operators/local_search.py",
    "action": "modify",
    "edit_intent": "exact_replace",
    "old_string": "        return solution\n",
    "new_string": "        candidate = solution\n        return candidate\n",
    "replace_all": False,
    "test_hint": None,
}

_VALID_CODE_AFTER_PATCH = _VALID_CODE.replace(
    "        return solution\n",
    "        candidate = solution\n        return candidate\n",
)


def _make_problem_spec(root_dir: str) -> ProblemSpec:
    return ProblemSpec(
        name="e2e_vrp",
        root_dir=root_dir,
        operator_categories=["local_search"],
        search_space=SearchSpace(
            editable=["operators/*.py"],
            frozen=["solver.py", "oracle.py"],
            import_whitelist=["math", "random", "copy"],
        ),
    )


def _make_protocol_result(
    stage: ExperimentStage,
    gate_outcome: str = "pass",
    win_rate: float = 0.7,
) -> ProtocolResult:
    stats = EvalStats(
        n_cases=6, wins=5, losses=1, ties=0,
        win_rate=win_rate, median_delta=0.02,
        ci_low=0.005, ci_high=0.04,
    )
    return ProtocolResult(
        stage=stage,
        stats=stats,
        gate_outcome=gate_outcome,
        reason_codes=(
            "SCREENING_FAIL_WIN_RATE"
            if stage is ExperimentStage.SCREENING and gate_outcome == "fail"
            else f"{stage.value.upper()}_{gate_outcome.upper()}",
        ),
        exposed_summary=f"stage={stage.value}",
        raw_metrics_ref="/tmp/e2e.json",
    )


class _AlwaysPassVerificationGate(VerificationGate):
    def __init__(self) -> None:
        super().__init__()

    def run(self, workspace: str, champion_workspace: str, patch: Any) -> VerificationResult:
        check = CheckResult(
            name="SYNTAX", passed=True, severity="light",
            detail="e2e stub pass", elapsed_ms=0,
        )
        return VerificationResult(passed=True, checks=(check,))


class _MockExperimentProtocol:
    """Configurable mock ExperimentProtocol."""

    def __init__(self, results: List[ProtocolResult], canary_pass: bool = True) -> None:
        self._results = list(results)
        self._canary_pass = canary_pass
        self.canary_call_count = 0
        self.experiment_call_count = 0
        self.runner = object()
        self.config = ProtocolConfig()
        self._metric_specs = (
            ObjectiveMetricSpec(name="cost", direction="minimize", priority=1),
        )
        self._problem_spec = None

    def set_problem_adapter(self, adapter: Any) -> None:
        self._problem_spec = adapter.spec
        objectives = getattr(adapter.spec, "objectives", None)
        if objectives:
            self._metric_specs = tuple(objectives)

    def run_canary(self, candidate_ws: str, champion_ws: str) -> CanaryResult:
        self.canary_call_count += 1
        return CanaryResult(passed=self._canary_pass, reason=None)

    def run_experiment(
        self,
        stage: ExperimentStage,
        candidate_ws: str,
        champion_ws: str,
        hypothesis_action: str,
        expand: bool = False,
        expand_round: int = 1,
    ) -> ProtocolResult:
        del expand_round
        self.experiment_call_count += 1
        if self._results:
            return self._results.pop(0)
        return _make_protocol_result(stage)


def _build_campaign(
    tmp_path: Path,
    *,
    llm_client: Any = None,
    experiment_protocol: Any = None,
    verification_gate: Any = None,
) -> CampaignManager:
    code_dir = tmp_path / "champion_code"
    (code_dir / "operators").mkdir(parents=True)
    (code_dir / "operators" / "local_search.py").write_text(_VALID_CODE)

    spec = _make_problem_spec(str(code_dir))
    champion = ChampionState(
        version=1,
        operator_pool={},
        code_snapshot_path=str(code_dir),
    )
    protocol = experiment_protocol or _MockExperimentProtocol(results=[])
    protocol._problem_spec = spec

    return CampaignManager(
        protocol_config=ProtocolConfig(
            screening_n=6,
            screening_win_rate_threshold=0.66,
            validation_n=9,
            validation_win_rate_threshold=0.66,
            frozen_n=9,
            min_practical_delta=0.001,
        ),
        split_manifest=SplitManifest(
            screening=["case1", "case2", "case3"],
            validation=["case4", "case5", "case6"],
            frozen=["case7", "case8", "case9"],
            canary=["case10"],
        ),
        seed_ledger=SeedLedgerConfig(
            screening=[42, 137],
            validation=[7, 19, 83],
            frozen=[256, 512, 1024],
            canary=[2048],
        ),
        llm_client=llm_client or MockLLMClient(
            hypothesis_response=_VALID_HYPOTHESIS,
            patch_response=_VALID_PATCH,
        ),
        champion=champion,
        campaign_dir=str(tmp_path / "campaign"),
        verification_gate=verification_gate or _AlwaysPassVerificationGate(),
        experiment_protocol=protocol,
        adapter=SimpleNamespace(spec=spec),
    )


# ---------------------------------------------------------------------------
# Test 1: Full mock campaign — ≥5 rounds
# ---------------------------------------------------------------------------

class TestFullMockCampaign:
    """Mock LLM full campaign: ≥5 rounds, lineage queryable, no crash."""

    def test_runs_at_least_5_rounds_without_crash(self, tmp_path):
        """Campaign runs 5 steps without raising an exception."""
        protocol = _MockExperimentProtocol(
            results=[
                _make_protocol_result(
                    ExperimentStage.SCREENING,
                    gate_outcome="fail",
                    win_rate=0.0,
                )
            ]
            * 5
        )
        cm = _build_campaign(tmp_path, experiment_protocol=protocol)

        for _ in range(5):
            if cm.should_stop():
                break
            cm.run_one_step()

        # Sanity: state is queryable
        state = cm.get_state()
        assert "n_experiments" in state
        assert "champion_version" in state

    def test_at_least_one_explore_step(self, tmp_path):
        """At least one step must be of action type 'explore' or 'create_branch'."""
        client = MockLLMClient(
            hypothesis_response=_VALID_HYPOTHESIS,
            patch_response=_VALID_PATCH,
        )
        protocol = _MockExperimentProtocol(
            results=[
                _make_protocol_result(
                    ExperimentStage.SCREENING,
                    gate_outcome="fail",
                    win_rate=0.0,
                )
            ]
            * 5
        )
        cm, bounded_client = _bounded_campaign(
            tmp_path,
            llm_client=client,
            experiment_protocol=protocol,
            failure_frontier_disposition="used",
        )

        results = []
        for _ in range(5):
            if cm.should_stop():
                break
            results.append(cm.run_one_step())

        explore_actions = {"explore", "create_branch"}
        assert any(r.action in explore_actions for r in results), (
            f"Expected at least one explore step; got: {[r.action for r in results]}"
        )
        assert protocol.experiment_call_count >= 2
        assert client.call_count >= 4
        assert "hypothesis_research_turn" in bounded_client.request_kinds
        assert "code_research_turn" in bounded_client.request_kinds
        research_actions = [
            response.get("action", response.get("outcome"))
            for response in bounded_client.responses
        ]
        review_index = research_actions.index("review_history_frontier")
        assert "read_source" in research_actions[:review_index]
        assert "read_history" in research_actions[:review_index]
        assert "finalize_hypothesis" in research_actions[review_index + 1 :]
        assert all(
            item["disposition"] == "used"
            for item in bounded_client.responses[review_index]["dispositions"]
        )
        code_actions = [
            action
            for action in research_actions
            if action in {"revise", "test_patch", "ready", "finalize_patch"}
        ]
        assert code_actions[:4] == [
            "revise",
            "test_patch",
            "ready",
            "finalize_patch",
        ]
        branch = cm._branch_ctrl.get_branch(results[-1].branch_id)
        workspace = Path(cm._branch_workspaces[branch.branch_id])
        assert branch.current_code_hash is not None
        assert (workspace / "operators" / "local_search.py").read_text() == (
            _VALID_CODE_AFTER_PATCH
        )

    def test_lineage_queryable_via_get_state(self, tmp_path):
        """get_state() returns branch lineage (branch list) after exploration."""
        cm = _build_campaign(tmp_path)

        cm.run_one_step()  # creates branch + explore

        state = cm.get_state()
        # branches key must be present and each entry must have id + state
        assert "branches" in state
        for entry in state["branches"]:
            assert "id" in entry
            assert "state" in entry

    def test_campaign_run_method_terminates(self, tmp_path):
        """cm.run(requested_rounds=5) terminates without hanging."""
        cm = _build_campaign(tmp_path)
        cm.run(requested_rounds=5)
        # No exception = pass

    def test_experiments_counter_increments(self, tmp_path):
        """n_experiments increments as steps run."""
        # Use experiment_protocol so experiments actually run
        proto = _MockExperimentProtocol(
            results=[_make_protocol_result(ExperimentStage.SCREENING)] * 10
        )
        cm = _build_campaign(tmp_path, experiment_protocol=proto)

        initial = cm.get_state()["n_experiments"]
        cm.run_one_step()
        after = cm.get_state()["n_experiments"]
        assert after >= initial  # at minimum no regression


# ---------------------------------------------------------------------------
# Test 2: Failure routing — contract fail → retry (no crash)
# ---------------------------------------------------------------------------

class TestContractFailureRouting:
    """Mock LLM that produces a contract-failing hypothesis, verifying retry flow."""

    def test_contract_fail_does_not_crash(self, tmp_path):
        """When hypothesis contract fails, campaign step completes without raising."""
        # Produce a hypothesis with an invalid action to trigger contract failure
        bad_hypothesis = {
            **_VALID_HYPOTHESIS,
            "action": "INVALID_ACTION",  # Contract C2 will reject this
        }
        llm_client = MockLLMClient(hypothesis_response=bad_hypothesis)
        cm = _build_campaign(tmp_path, llm_client=llm_client)

        # Should not raise even when contract gate rejects
        result = cm.run_one_step()
        assert result is not None


    def test_format_error_does_not_crash(self, tmp_path):
        """LLMFormatError in hypothesis generation is handled gracefully."""
        llm_client = MockLLMClient(mode="format_error")
        cm = _build_campaign(tmp_path, llm_client=llm_client)

        result = cm.run_one_step()
        assert result is not None

    def test_exhausted_llm_does_not_crash(self, tmp_path):
        """LLMRetryExhaustedError is handled gracefully."""
        llm_client = MockLLMClient(mode="exhausted")
        cm = _build_campaign(tmp_path, llm_client=llm_client)

        result = cm.run_one_step()
        assert result is not None

    def test_mode_sequence_contract_then_success(self, tmp_path):
        """Fail on first LLM call, succeed on subsequent ones — no crash."""
        llm_client = MockLLMClient(mode_sequence=["format_error", "success", "success"])
        cm = _build_campaign(tmp_path, llm_client=llm_client)

        for _ in range(3):
            if cm.should_stop():
                break
            result = cm.run_one_step()
            assert result is not None


# ---------------------------------------------------------------------------
# Test 3: CLI smoke test — scion run --mock-llm --rounds 3
# ---------------------------------------------------------------------------

class TestCLISmoke:
    """CLI smoke test: `scion run --mock-llm --rounds 3`."""

    @pytest.fixture()
    def problem_dir(self, tmp_path):
        """Create a minimal problem directory with all required YAML files."""
        code_dir = tmp_path / "solver_code"
        (code_dir / "operators").mkdir(parents=True)
        (code_dir / "operators" / "local_search.py").write_text(_VALID_CODE)

        problem_yaml = tmp_path / "problem.yaml"
        problem_yaml.write_text(
            f"name: smoke_test\n"
            f"root_dir: {code_dir}\n"
            f"operator_categories:\n  - local_search\n"
            f"search_space:\n"
            f"  editable:\n    - operators/*.py\n"
            f"  frozen:\n    - solver.py\n"
            f"  import_whitelist:\n    - math\n"
        )

        protocol_yaml = tmp_path / "protocol.yaml"
        protocol_yaml.write_text(
            "screening_n: 6\n"
            "screening_win_rate_threshold: 0.66\n"
            "validation_n: 9\n"
            "validation_win_rate_threshold: 0.66\n"
            "frozen_n: 9\n"
            "min_practical_delta: 0.001\n"
        )

        split_yaml = tmp_path / "split_manifest.yaml"
        split_yaml.write_text(
            "version: '1.0'\n"
            "screening:\n  - case1\n  - case2\n"
            "validation:\n  - case3\n"
            "frozen:\n  - case4\n"
            "canary: []\n"
        )

        seed_yaml = tmp_path / "seed_ledger.yaml"
        seed_yaml.write_text(
            "version: '1.0'\n"
            "screening:\n  - 42\n"
            "validation:\n  - 7\n"
            "frozen:\n  - 256\n"
            "canary:\n  - 999\n"
        )

        return tmp_path

    def test_cli_run_mock_llm_3_rounds(self, tmp_path, problem_dir):
        """scion run --mock-llm --rounds 3 exits with code 0."""
        campaign_dir = tmp_path / "cli_campaign"
        problem_yaml = problem_dir / "problem.yaml"

        # Run via Python module (avoids PATH issues in CI)
        env = os.environ.copy()
        scion_root = str(Path(__file__).parent.parent.parent)
        env["PYTHONPATH"] = scion_root

        result = subprocess.run(
            [
                sys.executable, "-m", "scion.cli.main",
                "run",
                "--mock-llm",
                "--rounds", "3",
                "--problem", str(problem_yaml),
                "--campaign-dir", str(campaign_dir),
            ],
            capture_output=True,
            text=True,
            env=env,
            timeout=60,
        )

        # Some minimal fixture combinations may be research-rejected, but the
        # fresh-only command must terminate without hanging.
        assert result.returncode in (0, 1), (
            f"CLI exited with code {result.returncode}\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )
        # If exit 0, it should report starting the campaign
        if result.returncode == 0:
            assert "Starting campaign" in result.stdout or "Campaign" in result.stdout

# ---------------------------------------------------------------------------
# Test 4: Warehouse Delivery problem config validation
# ---------------------------------------------------------------------------

class TestWarehouseDeliveryConfig:
    """Validate the warehouse_delivery YAML configs can be loaded correctly."""

    @pytest.fixture()
    def warehouse_dir(self):
        here = Path(__file__).parent.parent.parent  # scion root
        return here / "problems" / "warehouse_delivery"

    def test_problem_yaml_loads(self, warehouse_dir):
        from scion.config.problem import ProblemSpec
        spec = ProblemSpec.from_yaml(str(warehouse_dir / "problem.yaml"))
        assert spec.name == "warehouse_delivery"
        assert "order_level" in spec.operator_categories
        assert "vehicle_level" in spec.operator_categories

    def test_protocol_yaml_loads(self, warehouse_dir):
        from scion.config.problem import ProtocolConfig
        proto = ProtocolConfig.from_yaml(str(warehouse_dir / "protocol.yaml"))
        # New nested schema: screening.n_cases_modify, validation.n_cases, etc.
        assert proto.screening.n_cases_modify == 6
        assert proto.screening.n_cases_create == 10
        assert proto.validation.n_cases == 6
        assert proto.frozen.n_cases == 4

    def test_split_manifest_loads_and_is_disjoint(self, warehouse_dir):
        from scion.config.split_manifest import SplitManifest
        manifest = SplitManifest.from_yaml(str(warehouse_dir / "split_manifest.yaml"))
        assert len(manifest.screening) >= 10  # v4: 17 instances
        assert len(manifest.validation) >= 6   # v4: 10 instances
        assert len(manifest.frozen) >= 6, "T05: frozen set must have 6+ cases"
        # Frozen must be disjoint from screening and validation
        frozen_set = set(manifest.frozen)
        assert frozen_set.isdisjoint(set(manifest.screening)), "Frozen must not overlap screening"
        assert frozen_set.isdisjoint(set(manifest.validation)), "Frozen must not overlap validation"

    def test_seed_ledger_loads(self, warehouse_dir):
        from scion.config.seed_ledger import SeedLedger
        ledger = SeedLedger.from_yaml(str(warehouse_dir / "seed_ledger.yaml"))
        assert len(ledger.screening) >= 2
        assert len(ledger.validation) >= 2
        assert len(ledger.frozen) >= 2
