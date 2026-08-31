"""Sprint M unit tests: T1-T6 bug fixes."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from scion.config.problem import (
    ParameterSearchConfig,
    ProblemSpec,
    ProtocolConfig,
    SearchSpace,
    SeedLedgerConfig,
    SplitManifest,
)
from scion.core.campaign import CampaignManager
from scion.core.models import (
    ChampionState,
    CheckResult,
    VerificationResult,
)
from scion.proposal.mock_client import MockLLMClient
from scion.problem.spec import ObjectiveMetricSpec
from scion.verification.gate import VerificationGate

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
        code_snapshot_path=code_dir,
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


class AlwaysPassVerificationGate(VerificationGate):
    def run(self, workspace: str, champion_workspace: str, patch: Any, **kwargs) -> VerificationResult:
        check = CheckResult(name="SYNTAX", passed=True, severity="light", detail="ok", elapsed_ms=0)
        return VerificationResult(passed=True, checks=(check,))


class HeavyFailVerificationGate(VerificationGate):
    """Verification gate that always fails with heavy severity."""

    def run(self, workspace: str, champion_workspace: str, patch: Any, **kwargs) -> VerificationResult:
        check = CheckResult(
            name="V5", passed=False, severity="heavy",
            detail="regression detected", elapsed_ms=0,
        )
        return VerificationResult(
            passed=False, checks=(check,),
            failure_severity="heavy", first_failure="V5",
        )


class LightFailVerificationGate(VerificationGate):
    """Verification gate that always fails with light severity."""

    def run(self, workspace: str, champion_workspace: str, patch: Any, **kwargs) -> VerificationResult:
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
    protocol = experiment_protocol
    if protocol is None:
        protocol = SimpleNamespace(
            runner=object(),
            config=_make_protocol_config(),
            _metric_specs=(
                ObjectiveMetricSpec(
                    name="cost", direction="minimize", priority=1
                ),
            ),
            _problem_spec=spec,
        )

        def bind_problem_adapter(adapter: Any) -> None:
            protocol._problem_spec = adapter.spec
            declared = getattr(adapter.spec, "objectives", None)
            if declared:
                protocol._metric_specs = tuple(declared)

        protocol.set_problem_adapter = bind_problem_adapter

    return CampaignManager(
        protocol_config=_make_protocol_config(),
        split_manifest=_make_split_manifest().model_copy(
            update={"canary": ["canary-case"]}
        ),
        seed_ledger=_make_seed_ledger().model_copy(update={"canary": [7]}),
        llm_client=llm_client or MockLLMClient(
            hypothesis_response=_VALID_HYPOTHESIS,
            patch_response=_VALID_PATCH,
        ),
        champion=champion,
        campaign_dir=campaign_dir,
        verification_gate=verification_gate or AlwaysPassVerificationGate(),
        experiment_protocol=protocol,
        adapter=SimpleNamespace(spec=spec),
    )


# ---------------------------------------------------------------------------
# T3: Verification failures remain typed research rejections
# ---------------------------------------------------------------------------

class TestT3VerificationRejections:
    """Direct V3 keeps one typed outcome for each verification rejection."""

    def test_heavy_verification_failure_is_a_typed_rejection(self, tmp_path):
        """Heavy verification failure ends the candidate before evaluation."""
        cm = _campaign(tmp_path, verification_gate=HeavyFailVerificationGate())
        result = cm.run_one_step()

        assert result.failure_stage == "verification"
        assert result.execution_outcome.outcome.value == "research_rejected"
        assert result.execution_outcome.reason_code == "VERIFICATION_HEAVY_REJECTED"
        assert result.decision is None
        step = cm._step_history[-1]
        assert step.verification_passed is False
        assert step.protocol_result is None
        outcomes = cm._registry.query_execution_outcomes(
            branch_id=result.branch_id
        )
        assert len(outcomes) == 1
        assert outcomes[0]["outcome"] == "research_rejected"
        assert outcomes[0]["reason_code"] == "VERIFICATION_HEAVY_REJECTED"

    def test_light_verification_failure_is_a_typed_rejection(self, tmp_path):
        """Light verification failure has the same direct pre-evaluation shape."""
        cm = _campaign(tmp_path, verification_gate=LightFailVerificationGate())
        result = cm.run_one_step()

        assert result.failure_stage == "verification"
        assert result.execution_outcome.outcome.value == "research_rejected"
        assert result.execution_outcome.reason_code == "VERIFICATION_LIGHT_REJECTED"
        assert cm._step_history[-1].verification_passed is False

    def test_verification_rejection_carries_check_provenance(self, tmp_path):
        """The typed failure remains explainable from its check provenance."""
        cm = _campaign(tmp_path, verification_gate=HeavyFailVerificationGate())
        result = cm.run_one_step()

        assert result.branch_id is not None
        assert result.execution_outcome.provenance["stage"] == "verification"
        assert result.execution_outcome.provenance["severity"] == "heavy"
        checks = result.execution_outcome.provenance["verification_checks"]
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
    """LLMBalanceError must set run_result.stop_reason consistently."""

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

        cm = _campaign(tmp_path, llm_client=BalanceExhaustedMockClient())
        # run_one_step triggers LLM call → raises LLMBalanceError
        cm.run_one_step()
        assert cm._balance_exhausted is True
        assert cm.should_stop() is True
        assert cm._last_stop_reason == "api_balance_exhausted"

    def test_stopped_reason_api_balance_exhausted(self, tmp_path):
        """Terminal summary records the typed balance-exhausted stop reason."""
        from scion.proposal.llm_client import LLMBalanceError as _BalanceError

        class BalanceExhaustedMockClient:
            def __init__(self):
                self._calls = 0

            def call_with_tool(self, *args, **kwargs):
                raise _BalanceError("API balance exhausted: 403 balance is insufficient")

        cm = _campaign(tmp_path, llm_client=BalanceExhaustedMockClient())
        cm.run_one_step()
        assert cm.should_stop() is True
        cm.finalize_requested_stop()
        import json
        from pathlib import Path as _Path
        summary_path = _Path(str(tmp_path / "campaign")) / "campaign_summary.json"
        assert summary_path.exists()
        summary = json.loads(summary_path.read_text())
        stop_reason = summary.get("run_result", {}).get("stop_reason")
        assert stop_reason == "api_balance_exhausted", (
            f"Expected 'api_balance_exhausted', got {stop_reason}"
        )
