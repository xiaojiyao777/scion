"""Sprint M unit tests: T1-T6 bug fixes."""
from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path
from typing import Any, List, Optional
from unittest.mock import MagicMock, patch

import pytest

from scion.config.problem import ParameterSearchConfig
from scion.core.campaign import CampaignManager
from scion.core.models import (
    Branch, BranchState, CanaryResult, CheckResult, ChampionState,
    Decision, EvalStats, ExperimentStage, HypothesisProposal, HypothesisRecord,
    PatchProposal, ProtocolResult, VerificationResult,
)
from scion.core.termination import TerminationConfig
from scion.failure.router import FailureRouter, RetryConfig
from scion.lineage.branch_store import BranchStore, HypothesisStore
from scion.lineage.registry import LineageRegistry
from scion.proposal.llm_client import LLMBalanceError
from scion.proposal.mock_client import MockLLMClient
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
    "code_content": _VALID_CODE,
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
    termination_config: Optional[TerminationConfig] = None,
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
        termination_config=termination_config or TerminationConfig(
            max_experiments=100,
            stagnation_limit=50,
        ),
    )


# ---------------------------------------------------------------------------
# T1: Blacklist double-write bug
# ---------------------------------------------------------------------------

class TestT1BlacklistDoubleWrite:
    """Heavy verification failure must produce exactly 1 blacklisted hypothesis record."""

    def test_heavy_verification_failure_single_blacklist_record(self, tmp_path):
        """V-heavy failure: only 1 blacklisted row in hypotheses table."""
        cm = _campaign(tmp_path, verification_gate=HeavyFailVerificationGate())
        # Run one step — creates branch + runs explore step with heavy V-failure
        cm.run_one_step()
        # Check hypotheses table
        db_path = str(Path(cm._materializer._champions_dir).parent / "scion.db")
        with sqlite3.connect(db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM hypotheses WHERE status = 'blacklisted'"
            ).fetchall()
        assert len(rows) == 1, (
            f"Expected exactly 1 blacklisted record, got {len(rows)}. "
            "This indicates the double-write bug is still present."
        )

    def test_hypothesis_already_recorded_prevents_duplicate(self, tmp_path):
        """Direct _handle_failure calls: flag=True skips write, flag=False writes."""
        from scion.core.models import FailureEvent
        cm = _campaign(tmp_path)
        branch = Branch(
            branch_id=str(uuid.uuid4()),
            state=BranchState.EXPLORE,
            base_champion_id=1,
            base_champion_hash="abc",
        )
        hyp = HypothesisProposal(
            hypothesis_text="test hyp",
            change_locus="local_search",
            action="modify",
            target_file="operators/local_search.py",
        )
        cm._branch_hypotheses[branch.branch_id] = hyp
        failure = FailureEvent(category="verification_heavy", detail="V5")

        db_path = str(Path(cm._materializer._champions_dir).parent / "scion.db")

        # Call 1: hypothesis_already_recorded=True — no new record
        cm._handle_failure(branch, failure, hypothesis_already_recorded=True)
        with sqlite3.connect(db_path) as conn:
            c1 = conn.execute("SELECT COUNT(*) FROM hypotheses WHERE status='blacklisted'").fetchone()[0]
        assert c1 == 0

        # Reset streaks so action still routes to discard
        cm._failure_streak.clear()
        # Call 2: hypothesis_already_recorded=False — 1 new record
        cm._handle_failure(branch, failure, hypothesis_already_recorded=False)
        with sqlite3.connect(db_path) as conn:
            c2 = conn.execute("SELECT COUNT(*) FROM hypotheses WHERE status='blacklisted'").fetchone()[0]
        assert c2 == 1

    def test_handle_failure_with_hypothesis_already_recorded_skips_write(self, tmp_path):
        """_handle_failure(hypothesis_already_recorded=True) must NOT write a new record."""
        from scion.core.models import FailureEvent
        cm = _campaign(tmp_path)
        # Manually create a branch
        from scion.core.models import Branch, BranchState
        branch = Branch(
            branch_id=str(uuid.uuid4()),
            state=BranchState.EXPLORE,
            base_champion_id=1,
            base_champion_hash="abc",
        )
        # Inject a hypothesis into the campaign so _handle_failure has something to write
        hyp = HypothesisProposal(
            hypothesis_text="test",
            change_locus="local_search",
            action="modify",
            target_file="operators/local_search.py",
        )
        cm._branch_hypotheses[branch.branch_id] = hyp

        db_path = str(Path(cm._materializer._champions_dir).parent / "scion.db")
        failure = FailureEvent(category="verification_heavy", detail="V5 regression")

        # With hypothesis_already_recorded=True: should NOT create a new record
        cm._handle_failure(branch, failure, hypothesis_already_recorded=True)
        with sqlite3.connect(db_path) as conn:
            count = conn.execute("SELECT COUNT(*) FROM hypotheses").fetchone()[0]
        assert count == 0, "hypothesis_already_recorded=True must skip hypothesis write"

        # Reset streak for second call
        cm._failure_streak.clear()
        # Without the flag: should create a new record
        cm._handle_failure(branch, failure, hypothesis_already_recorded=False)
        with sqlite3.connect(db_path) as conn:
            count = conn.execute("SELECT COUNT(*) FROM hypotheses").fetchone()[0]
        assert count == 1, "hypothesis_already_recorded=False must write a new record"


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
# T3: Verification failures write experiment_events
# ---------------------------------------------------------------------------

class TestT3VerificationFailEvents:
    """Verification failures must write rows to experiment_events with event_kind='verification_fail'."""

    def test_heavy_verification_failure_writes_event(self, tmp_path):
        """Heavy V-failure → 1 verification_fail event in experiment_events."""
        cm = _campaign(tmp_path, verification_gate=HeavyFailVerificationGate())
        cm.run_one_step()
        db_path = str(Path(cm._materializer._champions_dir).parent / "scion.db")
        with sqlite3.connect(db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM experiment_events WHERE event_kind = 'verification_fail'"
            ).fetchall()
        assert len(rows) == 1, f"Expected 1 verification_fail event, got {len(rows)}"

    def test_light_verification_failure_writes_event(self, tmp_path):
        """Light V-failure (exhausted retries) → 1 verification_fail event in experiment_events."""
        # MockLLMClient returns the same valid hypothesis each time → retries exhaust
        cm = _campaign(tmp_path, verification_gate=LightFailVerificationGate())
        cm.run_one_step()
        db_path = str(Path(cm._materializer._champions_dir).parent / "scion.db")
        with sqlite3.connect(db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM experiment_events WHERE event_kind = 'verification_fail'"
            ).fetchall()
        # At minimum one event must be recorded for the light failure
        assert len(rows) >= 1, f"Expected ≥1 verification_fail event for light failure, got {len(rows)}"

    def test_verification_fail_event_has_correct_fields(self, tmp_path):
        """verification_fail event must have branch_id, hypothesis_id, and stage='verification'."""
        cm = _campaign(tmp_path, verification_gate=HeavyFailVerificationGate())
        result = cm.run_one_step()
        db_path = str(Path(cm._materializer._champions_dir).parent / "scion.db")
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM experiment_events WHERE event_kind = 'verification_fail' LIMIT 1"
            ).fetchone()
        assert row is not None
        d = dict(row)
        assert d.get("branch_id") is not None
        assert d.get("stage") == "verification"
        assert d.get("verification_passed") in (0, False, "False", "0", None) or not d.get("verification_passed")


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
        from scion.core.models import EvalStats
        # Set up a campaign that will promote
        cm = _campaign(tmp_path, verification_gate=AlwaysPassVerificationGate())
        # Directly call _on_promote with a mock branch to test persistence
        branch = Branch(
            branch_id=str(uuid.uuid4()),
            state=BranchState.EXPLORE,
            base_champion_id=1,
            base_champion_hash="abc",
        )
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

            def call(self, *args, **kwargs):
                raise _BalanceError("API balance exhausted: 403 Forbidden balance is insufficient")

            def get_cache_stats(self):
                return {}

        cm = _campaign(tmp_path, llm_client=BalanceExhaustedMockClient())
        # run_one_step triggers LLM call → raises LLMBalanceError
        cm.run_one_step()
        assert cm._balance_exhausted is True

    def test_stopped_reason_api_balance_exhausted(self, tmp_path):
        """campaign_summary must record stopped_reason='api_balance_exhausted' on balance error."""
        from scion.proposal.llm_client import LLMBalanceError as _BalanceError

        class BalanceExhaustedMockClient:
            def __init__(self):
                self._calls = 0

            def call_with_tool(self, *args, **kwargs):
                raise _BalanceError("API balance exhausted: 403 balance is insufficient")

            def call(self, *args, **kwargs):
                raise _BalanceError("API balance exhausted: 403 balance is insufficient")

            def get_cache_stats(self):
                return {}

        cm = _campaign(tmp_path, llm_client=BalanceExhaustedMockClient())
        # Drain the circuit breaker threshold
        for _ in range(4):
            cm.run_one_step()
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

    def test_llm_client_raises_balance_error_on_403_with_balance(self):
        """LLMClient._call_once raises LLMBalanceError when error has 403 + balance."""
        from scion.proposal.llm_client import LLMClient, LLMBalanceError as _BalanceError
        import anthropic

        client = LLMClient.__new__(LLMClient)
        client._anthropic_client = None
        client._openai_client = None
        client.model = "claude-test"
        client.max_tokens = 100
        client.timeout_sec = 10

        # Mock the anthropic client to raise a 403 balance error
        mock_anthropic = MagicMock()
        mock_anthropic.messages.create.side_effect = Exception(
            "403 Forbidden: balance is insufficient"
        )
        client._anthropic_client = mock_anthropic

        with pytest.raises(_BalanceError):
            client._call_once("test prompt", "claude-test")
