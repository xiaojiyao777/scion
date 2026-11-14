"""Tests for T20: CampaignManager — full pipeline with MockLLMClient."""
# ruff: noqa: F401
from __future__ import annotations

import json
import os
import sqlite3
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from scion.config.problem import (
    ProblemSpec,
    ProtocolConfig,
    SearchSpace,
    SeedLedgerConfig,
    SplitManifest,
)
from scion.core.campaign import CampaignManager, StepResult
from scion.core.code_research_limits import CodeResearchLimits
from scion.core.models import (
    Branch,
    BranchState,
    CanaryResult,
    ChampionState,
    CheckResult,
    Decision,
    EvalStats,
    ExperimentStage,
    ProtocolResult,
    VerificationResult,
)
from scion.problem.spec import ObjectiveMetricSpec
from scion.proposal.mock_client import MockLLMClient
from scion.verification.development import DevelopmentCheckRun
from scion.verification.gate import VerificationGate

from .protocol_adapter_test_support import protocol_test_adapter

# ---------------------------------------------------------------------------
# Fixtures / helpers
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

_VALID_CODE_AFTER_PATCH = _VALID_CODE.replace(
    "        return solution\n",
    "        candidate = solution\n        return candidate\n",
)

_VALID_PATCH_REPAIR = {
    "file_path": "operators/local_search.py",
    "action": "modify",
    "edit_intent": "exact_replace",
    "old_string": "        return candidate\n",
    "new_string": "        return candidate\n",
    "replace_all": False,
    "test_hint": None,
}


def _schema_requests_patch(schema: dict[str, Any]) -> bool:
    """Return true for current or legacy patch proposal schemas."""
    required = set(schema.get("required", []))
    properties = set((schema.get("properties") or {}).keys())
    return (
        "code_content" in required
        or {"file_path", "action"}.issubset(properties)
    )


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


def _make_protocol_result(
    stage: ExperimentStage,
    gate_outcome: str = "pass",
    win_rate: float = 0.7,
    median_delta: float = 0.01,
    ci_low: float = 0.005,
    ci_high: float = 0.02,
) -> ProtocolResult:
    stats = EvalStats(
        n_cases=10, wins=7, losses=2, ties=1,
        win_rate=win_rate, median_delta=median_delta,
        ci_low=ci_low, ci_high=ci_high,
    )
    return ProtocolResult(
        stage=stage,
        stats=stats,
        gate_outcome=gate_outcome,
        reason_codes=(_protocol_reason_code(stage, gate_outcome),),
        exposed_summary=f"stage={stage.value} outcome={gate_outcome}",
        raw_metrics_ref="/tmp/test.json",
    )


def _protocol_reason_code(stage: ExperimentStage, gate_outcome: str) -> str:
    return {
        (ExperimentStage.SCREENING, "pass"): "SCREENING_PASS",
        (ExperimentStage.SCREENING, "fail"): "SCREENING_FAIL_WIN_RATE",
        (ExperimentStage.SCREENING, "unclear"): "SCREENING_INCONCLUSIVE_HIGH_WIN_NEGATIVE_EFFECT",
        (ExperimentStage.SCREENING, "expand"): "SCREENING_EXPAND",
        (ExperimentStage.SCREENING, "continue"): "SCREENING_FAIL_WIN_RATE",
        (ExperimentStage.VALIDATION, "pass"): "VALIDATION_PASS",
        (ExperimentStage.VALIDATION, "fail"): "VALIDATION_FAIL_WIN_RATE",
        (ExperimentStage.VALIDATION, "unclear"): "RUNTIME_TIE_FRESH_CHAMPION_REQUIRED",
        (ExperimentStage.VALIDATION, "expand"): "VALIDATION_EXPAND",
        (ExperimentStage.VALIDATION, "continue"): "RUNTIME_TIE_FRESH_CHAMPION_REQUIRED",
        (ExperimentStage.FROZEN, "pass"): "FROZEN_PASS",
        (ExperimentStage.FROZEN, "fail"): "FROZEN_FAIL_UNCLEAR",
        (ExperimentStage.FROZEN, "unclear"): "RUNTIME_TIE_FRESH_CHAMPION_REQUIRED",
        (ExperimentStage.FROZEN, "expand"): "FROZEN_FAIL_UNCLEAR",
        (ExperimentStage.FROZEN, "continue"): "RUNTIME_TIE_FRESH_CHAMPION_REQUIRED",
    }[(stage, gate_outcome)]


class MockExperimentProtocol:
    """Configurable mock ExperimentProtocol for campaign tests."""

    def __init__(
        self,
        results: list[ProtocolResult],
        canary_pass: bool = True,
    ) -> None:
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
        proposal_subject: dict[str, Any] | None = None,
    ) -> ProtocolResult:
        del proposal_subject
        self.experiment_call_count += 1
        if self._results:
            return self._results.pop(0)
        # Default: return a screening pass
        return _make_protocol_result(stage)


class AlwaysPassVerificationGate(VerificationGate):
    """Verification gate stub that always passes."""

    def __init__(self) -> None:
        super().__init__()

    def run(self, workspace: str, champion_workspace: str, patch: Any) -> VerificationResult:
        check = CheckResult(
            name="SYNTAX", passed=True, severity="light", detail="stub pass", elapsed_ms=0
        )
        return VerificationResult(passed=True, checks=(check,))


class AlwaysFailVerificationGate(VerificationGate):
    """Verification gate stub that always fails (light)."""

    def __init__(self) -> None:
        super().__init__()

    def run(self, workspace: str, champion_workspace: str, patch: Any) -> VerificationResult:
        check = CheckResult(
            name="SYNTAX", passed=False, severity="light",
            detail="stub fail", elapsed_ms=0,
        )
        return VerificationResult(
            passed=False, checks=(check,),
            failure_severity="light", first_failure="SYNTAX",
        )


class _DeterministicBoundedResearchClient:
    """Adapt direct H/C fixtures to the real bounded K1 tool protocol.

    Campaign lifecycle tests still own their direct response sequences.  This
    adapter only supplies the deterministic read/review/test/ready actions that
    a bounded research session requires around those responses. Depending on
    the test, it either reads/cites or explicitly rejects every latest frontier
    ref rather than bypassing the production guard.
    """

    def __init__(
        self,
        direct_client: Any,
        *,
        failure_frontier_disposition: str = "rejected",
    ) -> None:
        if failure_frontier_disposition not in {"rejected", "used"}:
            raise ValueError("failure frontier disposition must be rejected or used")
        self.direct_client = direct_client
        self.failure_frontier_disposition = failure_frontier_disposition
        self.model = getattr(
            direct_client,
            "model",
            "deterministic-bounded-campaign-research",
        )
        self.request_kinds: list[str] = []
        self.responses: list[dict[str, Any]] = []

    def call_with_tool(
        self,
        prompt: str,
        tool: dict[str, Any],
        model: str | None = None,
        system_blocks: list[dict[str, Any]] | None = None,
        request_kind: str | None = None,
    ) -> dict[str, Any]:
        if request_kind is None:
            raise AssertionError("bounded campaign request_kind is required")
        self.request_kinds.append(request_kind)
        response = self._bounded_response(
            prompt,
            tool,
            model=model,
            system_blocks=system_blocks,
            request_kind=request_kind,
        )
        self.responses.append(deepcopy(response))
        return response

    def _bounded_response(
        self,
        prompt: str,
        tool: dict[str, Any],
        *,
        model: str | None,
        system_blocks: list[dict[str, Any]] | None,
        request_kind: str,
    ) -> dict[str, Any]:
        blocks = system_blocks or []
        if request_kind == "hypothesis_research_turn":
            state = _bounded_research_state(
                blocks,
                heading="## Bounded Hypothesis Research State\n",
            )
            visible_sources = state["visible_sources"]
            if not visible_sources:
                source = next(
                    item for item in state["source_index"] if item["available"]
                )
                return {"action": "read_source", "ref": source["ref"]}
            frontier = state["failure_frontier"]
            if frontier["required"] and not frontier["reviewed"]:
                if self.failure_frontier_disposition == "used":
                    visible_history_refs = {
                        item["ref"] for item in state["visible_history"]
                    }
                    unread_ref = next(
                        (
                            ref
                            for ref in frontier["refs"]
                            if ref not in visible_history_refs
                        ),
                        None,
                    )
                    if unread_ref is not None:
                        return {"action": "read_history", "ref": unread_ref}
                return {
                    "action": "review_history_frontier",
                    "dispositions": [
                        (
                            {"ref": ref, "disposition": "used"}
                            if self.failure_frontier_disposition == "used"
                            else {
                                "ref": ref,
                                "disposition": "rejected",
                                "reason": (
                                    "Not used by this deterministic lifecycle fixture."
                                ),
                            }
                        )
                        for ref in frontier["refs"]
                    ],
                }
            hypothesis_schema = _bounded_action_schema(
                tool,
                "finalize_hypothesis",
            )["properties"]["hypothesis"]
            hypothesis = self._direct_response(
                prompt,
                hypothesis_schema,
                model=model,
                system_blocks=blocks,
                request_kind="hypothesis",
            )
            return {
                "action": "finalize_hypothesis",
                "hypothesis": hypothesis,
                "research_basis": {
                    "read_refs": [
                        *(item["ref"] for item in visible_sources),
                        *(item["ref"] for item in state["visible_history"]),
                    ],
                    "nearest_prior_refs": [
                        item["ref"] for item in state["visible_history"]
                    ],
                    "material_delta": (
                        "Exercise the fixture-selected mechanism as a fresh H."
                    ),
                    "alternatives_considered": [
                        "Keep the current fixture mechanism unchanged."
                    ],
                    "observable_prediction": (
                        "The configured campaign lifecycle outcome will differ."
                    ),
                    "falsification_condition": (
                        "Reject if the configured verification or Protocol check fails."
                    ),
                },
            }
        if request_kind == "code_research_turn":
            state = _bounded_research_state(
                blocks,
                heading="## Bounded Code Research State\n",
            )
            turn_index = state["turn_index"]
            if turn_index == 0:
                patch_schema = _bounded_action_schema(tool, "revise")["properties"][
                    "patch"
                ]
                patch = self._direct_response(
                    prompt,
                    patch_schema,
                    model=model,
                    system_blocks=blocks,
                    request_kind="code",
                )
                return {"action": "revise", "patch": patch}
            if turn_index == 1:
                return {"action": "test_patch"}
            if turn_index == 2:
                return {"action": "ready"}
            raise AssertionError(f"unexpected bounded code turn: {turn_index}")
        if request_kind == "code_research_finalize":
            return {"outcome": "finalize_patch"}
        raise AssertionError(f"unexpected request kind: {request_kind}")

    def _direct_response(
        self,
        prompt: str,
        schema: dict[str, Any],
        *,
        model: str | None,
        system_blocks: list[dict[str, Any]],
        request_kind: str,
    ) -> dict[str, Any]:
        return self.direct_client.call_with_tool(
            prompt,
            {
                "name": f"fixture_{request_kind}",
                "input_schema": deepcopy(schema),
            },
            model,
            system_blocks=system_blocks,
            request_kind=request_kind,
        )


class _PassingBoundedDevelopmentEvaluator:
    """Keep legacy campaign fixtures focused on their outer verification gate."""

    def evaluate(self, **_kwargs: Any) -> DevelopmentCheckRun:
        return DevelopmentCheckRun(outcome="passed")


def _bounded_research_state(
    system_blocks: list[dict[str, Any]],
    *,
    heading: str,
) -> dict[str, Any]:
    for block in reversed(system_blocks):
        text = block.get("text")
        if isinstance(text, str) and text.startswith(heading):
            value = json.loads(text.removeprefix(heading))
            if isinstance(value, dict):
                return value
    raise AssertionError(f"missing bounded research state: {heading.strip()}")


def _bounded_action_schema(
    tool: dict[str, Any],
    action: str,
) -> dict[str, Any]:
    for schema in tool["input_schema"]["oneOf"]:
        action_schema = schema.get("properties", {}).get("action", {})
        if action in action_schema.get("enum", []):
            return schema
    raise AssertionError(f"bounded action is unavailable: {action}")


def _bounded_campaign(
    tmp_path: Path,
    *,
    llm_client: Any | None = None,
    failure_frontier_disposition: str = "rejected",
    **kwargs: Any,
) -> tuple[CampaignManager, _DeterministicBoundedResearchClient]:
    """Create a K1 campaign using real bounded H/C session state machines."""

    direct_client = llm_client or MockLLMClient(
        hypothesis_response=_VALID_HYPOTHESIS,
        patch_response=_VALID_PATCH,
    )
    bounded_client = _DeterministicBoundedResearchClient(
        direct_client,
        failure_frontier_disposition=failure_frontier_disposition,
    )
    cm = _campaign(
        tmp_path,
        llm_client=bounded_client,
        code_research_limits=CodeResearchLimits(
            max_turns=(4 if failure_frontier_disposition == "used" else 3)
        ),
        **kwargs,
    )
    evaluator = _PassingBoundedDevelopmentEvaluator()
    cm._code_development_evaluator = evaluator
    cm._proposal_pipeline.code_development_evaluator = evaluator
    return cm, bounded_client


def _campaign(
    tmp_path: Path,
    llm_client: Any = None,
    experiment_protocol: Any = None,
    verification_gate: Any = None,
    resource_envelope: Any = None,
    code_research_limits: Any = None,
    research_history: Any = (),
) -> CampaignManager:
    # Create minimal champion code directory
    code_dir = tmp_path / "champion_code"
    (code_dir / "operators").mkdir(parents=True)
    (code_dir / "operators" / "local_search.py").write_text(_VALID_CODE)
    (code_dir / "solver.py").write_text(_VALID_CODE)

    campaign_dir = str(tmp_path / "campaign")
    spec = _make_problem_spec(str(code_dir))
    champion = _make_champion(str(code_dir))
    protocol = experiment_protocol or MockExperimentProtocol(results=[])
    if not getattr(protocol, "_metric_specs", None):
        protocol._metric_specs = (
            ObjectiveMetricSpec(name="cost", direction="minimize", priority=1),
        )
    spec = spec.model_copy(
        update={"objectives": tuple(protocol._metric_specs)}
    )
    protocol._problem_spec = spec
    adapter = protocol_test_adapter(
        protocol._metric_specs,
        problem_spec=spec,
    )

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
        adapter=adapter,
        research_history=research_history,
        resource_envelope=resource_envelope,
        code_research_limits=code_research_limits,
    )


# ---------------------------------------------------------------------------
# Basic campaign structure tests
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# CONTINUE_EXPLORE path
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# Full successful path: EXPLORE → QUEUE_VALIDATE → VALIDATING → QUEUE_FROZEN → PROMOTE
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# Contract failure routing
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# Screening fail → ABANDON (win_rate very low)
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# Canary failure
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# Stale branch reconciliation
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# Verification gate failure
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# run() loop integration
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# T03+T04: archive_workspace returns path + campaign_summary.json
# ---------------------------------------------------------------------------





# ---------------------------------------------------------------------------
# T16 — promotion weight optimization hook
# ---------------------------------------------------------------------------

def _promote_protocol():
    """Return a protocol that produces screening→validation→frozen pass."""
    return MockExperimentProtocol(results=[
        _make_protocol_result(ExperimentStage.SCREENING, gate_outcome="pass"),
        _make_protocol_result(ExperimentStage.VALIDATION, gate_outcome="pass",
                              win_rate=0.7, ci_low=0.005, ci_high=0.02),
        _make_protocol_result(ExperimentStage.FROZEN, gate_outcome="pass",
                              win_rate=0.7, ci_low=0.005, ci_high=0.02),
    ])


def _run_to_promote(cm):
    """Drive campaign manager through three steps to reach PROMOTE."""
    cm.run_one_step()
    cm.run_one_step()
    result = cm.run_one_step()
    assert result.decision == Decision.PROMOTE
    return result


def _setup_for_promotion(tmp_path, with_registry=False):
    """Create a campaign and frozen branch ready for the normal promote path.

    Returns (cm, branch, ws_path).
    """
    import yaml as _yaml

    ws = tmp_path / "branch_ws"
    ws.mkdir(parents=True)
    (ws / "operators").mkdir(exist_ok=True)
    (ws / "operators" / "local_search.py").write_text(_VALID_CODE)

    if with_registry:
        ops = [
            {"name": "swap", "file_path": "operators/swap.py",
             "category": "order_level", "weight": 0.6, "class_name": "Swap"},
            {"name": "move", "file_path": "operators/move.py",
             "category": "order_level", "weight": 0.4, "class_name": "Move"},
        ]
        (ws / "registry.yaml").write_text(_yaml.dump({"operators": ops}))

    cm = _campaign(tmp_path)
    branch = cm._branch_ctrl.create_branch(cm._champion)
    branch.state = BranchState.FROZEN_TESTING
    cm._branch_workspaces[branch.branch_id] = str(ws)
    return cm, branch, str(ws)


def _promote_frozen_branch(cm, branch):
    """Drive the same direct promotion used by DecisionFinalizer."""
    cm._require_promotable_branch(branch)
    cm._promote_branch(branch)




# ---------------------------------------------------------------------------
# T20: Code-failure degraded recovery (pending hypothesis retry)
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# T1: Eval steps use the branch's ordinary hypothesis value
# ---------------------------------------------------------------------------


__all__ = [
    name
    for name in globals()
    if not (name.startswith("__") and name.endswith("__"))
]
