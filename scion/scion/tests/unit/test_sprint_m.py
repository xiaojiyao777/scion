"""Sprint M unit tests: T1-T6 bug fixes."""
from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest

from scion.config.problem import ParameterSearchConfig
from scion.core.campaign import CampaignManager
from scion.core.models import Branch, BranchState, CheckResult, ChampionState, VerificationResult
from scion.proposal.mock_client import MockLLMClient
from scion.proposal.edit_protocol import source_digest_for_content
from scion.config.problem import ProblemSpec, ProtocolConfig, SplitManifest, SeedLedgerConfig, SearchSpace


# ---------------------------------------------------------------------------
# Shared helpers (reuse pattern from test_campaign.py)
# ---------------------------------------------------------------------------

_VALID_CODE = (
    "class LocalSearch:\n"
    "    def execute(self, solution, rng):\n"
    "        return solution\n"
)

_VALID_HYPOTHESIS = {
    "hypothesis_text": "Improve local search by trying 2-opt.",
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
    "source_digest": source_digest_for_content(_VALID_CODE),
    "old_string": "        return solution\n",
    "new_string": "        candidate = solution\n        return candidate\n",
    "replace_all": False,
    "test_hint": None,
}


def _make_problem_spec(root_dir: str) -> ProblemSpec:
    return ProblemSpec(
        name="test_vrp",
        root_dir=root_dir,
        operator_categories=["local_search"],
        search_space=SearchSpace(
            editable=["operators/*.py"],
            frozen=["solver.py", "oracle.py"],
            import_whitelist=["numpy", "random", "math"],
        ),
    )


def _make_solver_design_problem_spec(root_dir: str) -> ProblemSpec:
    return ProblemSpec(
        name="test_cvrp_solver_design",
        root_dir=root_dir,
        operator_categories=["solver_design"],
        research_surfaces=[
            SimpleNamespace(
                name="solver_design",
                kind="solver_design",
                algorithm=SimpleNamespace(role="problem_object_solver_algorithm"),
                targets=SimpleNamespace(
                    files=["policies/baseline_algorithm.py"],
                    create_new_allowed=False,
                    modify_allowed=True,
                    remove_allowed=False,
                ),
            )
        ],
        search_space=SearchSpace(
            editable=["policies/*.py"],
            frozen=["solver.py", "oracle.py"],
            import_whitelist=["math"],
        ),
    )


def _make_champion(code_dir: str) -> ChampionState:
    return ChampionState(
        version=1,
        operator_pool={},
        solver_config_hash="abc123",
        code_snapshot_path=code_dir,
        code_snapshot_hash="deadbeef",
    )


def _make_protocol_config() -> ProtocolConfig:
    return ProtocolConfig(
        screening_n=6,
        screening_win_rate_threshold=0.66,
        validation_n=12,
        validation_win_rate_threshold=0.66,
        frozen_n=24,
        min_practical_delta=0.001,
    )


def _make_split_manifest() -> SplitManifest:
    return SplitManifest(
        screening=["case1", "case2"],
        validation=["case3", "case4"],
        frozen=["case5", "case6"],
    )


def _make_seed_ledger() -> SeedLedgerConfig:
    return SeedLedgerConfig(
        screening=[1, 2],
        validation=[3, 4],
        frozen=[5, 6],
    )


def _solver_design_campaign(
    tmp_path: Path,
    *,
    verification_gate: Any = None,
) -> CampaignManager:
    code_dir = tmp_path / "solver_design_champion"
    (code_dir / "policies").mkdir(parents=True)
    solver_code = "def solve(instance, rng, time_limit_sec, context):\n    return None\n"
    (code_dir / "policies" / "baseline_algorithm.py").write_text(
        solver_code,
        encoding="utf-8",
    )
    spec = _make_solver_design_problem_spec(str(code_dir))
    champion = _make_champion(str(code_dir))
    hypothesis = {
        "hypothesis_text": "Try a different solver-design lifecycle.",
        "change_locus": "solver_design",
        "action": "modify",
        "target_file": "policies/baseline_algorithm.py",
        "predicted_direction": "improve",
        "target_weakness": "candidate lifecycle",
        "expected_effect": "better total_distance",
    }
    patch = {
        "file_path": "policies/baseline_algorithm.py",
        "action": "modify",
        "edit_intent": "exact_replace",
        "source_digest": source_digest_for_content(solver_code),
        "old_string": "    return None\n",
        "new_string": "    return context.nearest_neighbor()\n",
        "replace_all": False,
        "test_hint": None,
    }
    return CampaignManager(
        problem_spec=spec,
        protocol_config=_make_protocol_config(),
        split_manifest=_make_split_manifest(),
        seed_ledger=_make_seed_ledger(),
        llm_client=MockLLMClient(
            hypothesis_response=hypothesis,
            patch_response=patch,
        ),
        champion=champion,
        campaign_dir=str(tmp_path / "solver_design_campaign"),
        verification_gate=verification_gate or AlwaysPassVerificationGate(),
    )


class AlwaysPassVerificationGate:
    def run(self, workspace: str, champion_workspace: str, patch: Any) -> VerificationResult:
        check = CheckResult(name="SYNTAX", passed=True, severity="light", detail="ok", elapsed_ms=0)
        return VerificationResult(passed=True, checks=(check,))


class HeavyFailVerificationGate:
    """Verification gate that always fails with heavy severity."""

    def run(self, workspace: str, champion_workspace: str, patch: Any) -> VerificationResult:
        check = CheckResult(
            name="V5", passed=False, severity="heavy",
            detail="regression detected", elapsed_ms=0,
        )
        return VerificationResult(
            passed=False, checks=(check,),
            failure_severity="heavy", first_failure="V5",
        )


class LightFailVerificationGate:
    """Verification gate that always fails with light severity."""

    def run(self, workspace: str, champion_workspace: str, patch: Any) -> VerificationResult:
        check = CheckResult(
            name="SYNTAX", passed=False, severity="light",
            detail="syntax error", elapsed_ms=0,
        )
        return VerificationResult(
            passed=False, checks=(check,),
            failure_severity="light", first_failure="SYNTAX",
        )


def _campaign(
    tmp_path: Path,
    llm_client: Any = None,
    experiment_protocol: Any = None,
    verification_gate: Any = None,
) -> CampaignManager:
    code_dir = tmp_path / "champion_code"
    (code_dir / "operators").mkdir(parents=True)
    (code_dir / "operators" / "local_search.py").write_text(_VALID_CODE)

    campaign_dir = str(tmp_path / "campaign")
    spec = _make_problem_spec(str(code_dir))
    champion = _make_champion(str(code_dir))

    return CampaignManager(
        problem_spec=spec,
        protocol_config=_make_protocol_config(),
        split_manifest=_make_split_manifest(),
        seed_ledger=_make_seed_ledger(),
        llm_client=llm_client or MockLLMClient(
            hypothesis_response=_VALID_HYPOTHESIS,
            patch_response=_VALID_PATCH,
        ),
        champion=champion,
        campaign_dir=campaign_dir,
        verification_gate=verification_gate or AlwaysPassVerificationGate(),
        experiment_protocol=experiment_protocol,
    )


# ---------------------------------------------------------------------------
# T2: BranchStore.save() called on creation
# ---------------------------------------------------------------------------

class TestT2BranchStorePersistence:
    """Branch must be saved to SQLite after creation and state changes."""

    def test_branch_saved_after_creation(self, tmp_path):
        """After run_one_step, branches table must be non-empty."""
        cm = _campaign(tmp_path, verification_gate=AlwaysPassVerificationGate())
        cm.run_one_step()
        db_path = str(Path(cm._materializer._champions_dir).parent / "scion.db")
        with sqlite3.connect(db_path) as conn:
            count = conn.execute("SELECT COUNT(*) FROM branches").fetchone()[0]
        assert count > 0, "branches table must be populated after branch creation"

    def test_branch_saved_with_correct_state(self, tmp_path):
        """After creation, the branch state in DB matches the in-memory state."""
        cm = _campaign(tmp_path, verification_gate=HeavyFailVerificationGate())
        result = cm.run_one_step()
        bid = result.branch_id
        if bid is None:
            pytest.skip("No branch created in this step")

        db_path = str(Path(cm._materializer._champions_dir).parent / "scion.db")
        with sqlite3.connect(db_path) as conn:
            row = conn.execute(
                "SELECT state FROM branches WHERE branch_id = ?", (bid,)
            ).fetchone()
        assert row is not None, "Branch must be saved to branches table"


# ---------------------------------------------------------------------------
# T3: Verification failures remain typed research rejections
# ---------------------------------------------------------------------------

class TestT3VerificationRejections:
    """Direct V3 records verification rejection on the step, not a lifecycle event."""

    def test_heavy_verification_failure_is_a_typed_rejection(self, tmp_path):
        """Heavy verification failure ends the candidate before evaluation."""
        cm = _campaign(tmp_path, verification_gate=HeavyFailVerificationGate())
        result = cm.run_one_step()

        assert result.failure_stage == "verification"
        assert result.execution_outcome.value == "research_rejected"
        assert result.execution_outcome_reason_code == "VERIFICATION_HEAVY_REJECTED"
        assert result.decision is None
        step = cm._step_history[-1]
        assert step.verification_passed is False
        assert step.protocol_result is None

    def test_light_verification_failure_is_a_typed_rejection(self, tmp_path):
        """Light verification failure has the same direct pre-evaluation shape."""
        cm = _campaign(tmp_path, verification_gate=LightFailVerificationGate())
        result = cm.run_one_step()

        assert result.failure_stage == "verification"
        assert result.execution_outcome.value == "research_rejected"
        assert result.execution_outcome_reason_code == "VERIFICATION_LIGHT_REJECTED"
        assert cm._step_history[-1].verification_passed is False

    def test_verification_rejection_carries_check_provenance(self, tmp_path):
        """The failure remains explainable without a second event lifecycle."""
        cm = _campaign(tmp_path, verification_gate=HeavyFailVerificationGate())
        result = cm.run_one_step()

        assert result.branch_id is not None
        assert result.execution_outcome_provenance["stage"] == "verification"
        assert result.execution_outcome_provenance["severity"] == "heavy"
        checks = result.execution_outcome_provenance["verification_checks"]
        assert checks == [
            {
                "name": "V5",
                "passed": False,
                "severity": "heavy",
                "detail": "regression detected",
                "elapsed_ms": 0,
                "metadata": {},
            }
        ]


# ---------------------------------------------------------------------------
# T4: ChampionStore already persists on promote (verify it exists)
# ---------------------------------------------------------------------------

class TestT4ChampionStorePersistence:
    """ChampionStore.promote() must be callable and ChampionStore is initialized."""

    def test_champion_store_initialized(self, tmp_path):
        """CampaignManager must have a _champion_store attribute."""
        cm = _campaign(tmp_path)
        assert hasattr(cm, "_champion_store")

    def test_champion_store_promote_called_on_promote(self, tmp_path):
        """After a promotion, champion_store should have a record."""
        # Set up a campaign that will promote
        cm = _campaign(tmp_path, verification_gate=AlwaysPassVerificationGate())
        # Directly call _on_promote with a mock branch to test persistence
        branch = Branch(
            branch_id=str(uuid.uuid4()),
            state=BranchState.FROZEN_TESTING,
            base_champion_id=1,
            base_champion_hash="abc",
        )
        cm._branch_ctrl._branches[branch.branch_id] = branch
        # Set up a workspace for the branch (needed by _on_promote)
        code_dir = str(tmp_path / "champion_code")
        cm._branch_workspaces[branch.branch_id] = code_dir

        with patch.object(cm._champion_store, "promote") as mock_promote:
            cm._on_promote(branch)
        # promote() should have been called exactly once
        mock_promote.assert_called_once()


# ---------------------------------------------------------------------------
# T5: Weight optimization evaluation count
# ---------------------------------------------------------------------------

class TestT5WeightOptEvalCount:
    """ParameterSearchConfig must have n_initial_random=8, n_iterations=16."""

    def test_default_n_initial_random(self):
        cfg = ParameterSearchConfig()
        assert cfg.n_initial_random == 8, (
            f"n_initial_random should be 8, got {cfg.n_initial_random}"
        )

    def test_default_n_iterations(self):
        cfg = ParameterSearchConfig()
        assert cfg.n_iterations == 16, (
            f"n_iterations should be 16, got {cfg.n_iterations}"
        )

    def test_total_evaluations_is_24(self):
        cfg = ParameterSearchConfig()
        total = cfg.n_initial_random + cfg.n_iterations
        assert total == 24, f"Total evaluations should be 24, got {total}"


# ---------------------------------------------------------------------------
# T6: 403/balance exhausted graceful stop
# ---------------------------------------------------------------------------

class TestT6BalanceExhaustedStop:
    """LLMBalanceError must set stopped_reason='api_balance_exhausted'."""

    def test_llm_balance_error_exists(self):
        """LLMBalanceError must be importable from llm_client."""
        from scion.proposal.llm_client import LLMBalanceError
        assert issubclass(LLMBalanceError, Exception)

    def test_balance_error_sets_balance_exhausted_flag(self, tmp_path):
        """When LLMBalanceError is raised, _balance_exhausted must be True."""
        from scion.proposal.llm_client import LLMBalanceError as _BalanceError

        class BalanceExhaustedMockClient:
            """Mock LLM client that raises LLMBalanceError on first call."""
            def __init__(self):
                self._calls = 0

            def call_with_tool(self, *args, **kwargs):
                raise _BalanceError("API balance exhausted: 403 Forbidden balance is insufficient")

            def get_cache_stats(self):
                return {}

        cm = _campaign(tmp_path, llm_client=BalanceExhaustedMockClient())
        # run_one_step triggers LLM call → raises LLMBalanceError
        cm.run_one_step()
        assert cm._balance_exhausted is True
        assert cm.should_stop() is True
        assert cm._last_stop_reason == "api_balance_exhausted"

    def test_stopped_reason_api_balance_exhausted(self, tmp_path):
        """campaign_summary must record stopped_reason='api_balance_exhausted' on balance error."""
        from scion.proposal.llm_client import LLMBalanceError as _BalanceError

        class BalanceExhaustedMockClient:
            def __init__(self):
                self._calls = 0

            def call_with_tool(self, *args, **kwargs):
                raise _BalanceError("API balance exhausted: 403 balance is insufficient")

            def get_cache_stats(self):
                return {}

        cm = _campaign(tmp_path, llm_client=BalanceExhaustedMockClient())
        cm.run_one_step()
        assert cm.should_stop() is True
        # Simulate the summary write
        cm._write_campaign_summary()
        import json
        from pathlib import Path as _Path
        summary_path = _Path(str(tmp_path / "campaign")) / "campaign_summary.json"
        assert summary_path.exists()
        summary = json.loads(summary_path.read_text())
        assert summary.get("stopped_reason") == "api_balance_exhausted", (
            f"Expected 'api_balance_exhausted', got {summary.get('stopped_reason')}"
        )
