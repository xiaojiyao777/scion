from __future__ import annotations

import json
import shutil
from dataclasses import fields, replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from scion.config.problem import SeedLedgerConfig, SplitManifest
from scion.core.models import (
    Branch,
    BranchState,
    CaseAggregateFeedback,
    ChampionState,
    DecisionFeatures,
    EvalStats,
    ExperimentStage,
    HypothesisProposal,
    OperatorConfig,
    PatchProposal,
    ProtocolResult,
    RunResult,
    StepRecord,
)
from scion.problem.spec import ProblemSpecV1
from scion.problem.bridge import (
    legacy_problem_spec_from_v1,
    load_problem_spec_v1_from_yaml,
)
from scion.problems.cvrp.adapter import CvrpAdapter
from scion.problems.cvrp.solver_design_provider import CvrpSolverDesignProvider
from scion.proposal import agentic_session as agentic_session_module
from scion.proposal.agentic_session import (
    AGENTIC_SESSION_SCHEMA_VERSION,
    AgenticProposalRequest,
    AgenticProposalPhase,
    AgenticProposalSession,
    AgenticProposalSessionState,
    AgenticProposalStatus,
    AgenticSessionStore,
    AgenticTerminationReason,
    AgenticToolLoopConfig,
    FileAgenticSessionArtifactStore,
    compute_agentic_idempotency_key,
    resume_from_artifact,
    validate_agentic_session_artifact,
    _compact_algorithm_smoke_observation,
    _compact_contract_preview_observation,
    _compact_feedback_observation_for_budget,
    _algorithm_smoke_failure_detail,
    _latest_preview_failure_detail,
    _code_observation_prompt_payload,
    _code_prompt_observations,
    _json_size,
    _observation_prompt_payload,
    _research_diagnosis_from_observations,
    _self_check_from_previews,
)
from scion.proposal.engine import CreativeLayer
from scion.proposal.llm_client import LLMRetryExhaustedError
from scion.proposal.tools import (
    ContextExposurePolicy,
    HoldoutExposure,
    ProposalExposureLevel,
    ProposalObservation,
    ProposalTaint,
    ProposalToolContext,
    ProposalToolFailureCode,
    ProposalToolPermission,
    ProposalToolRegistry,
    _resolve_smoke_instance_path,
    _solver_run_failure_detail,
)

_COMPACT_FEEDBACK_TOOL_NAMES = {
    "memory.query",
    "feedback.query_screening",
    "feedback.query_runtime",
}
_SCION_PACKAGE_ROOT = Path(__file__).resolve().parents[2]
_CVRP_ROOT = _SCION_PACKAGE_ROOT / "problems" / "cvrp"


def _solver_design_low_effort_issue(**kwargs):
    return CvrpSolverDesignProvider().low_effort_issue(**kwargs)


class FakeCreative:
    def __init__(
        self,
        *,
        hypothesis: HypothesisProposal | None = None,
        patch: PatchProposal | None = None,
    ) -> None:
        self.hypothesis = hypothesis or _hyp()
        self.patch = patch or PatchProposal(**_valid_policy_patch_payload())
        self.hypothesis_contexts: list[dict] = []
        self.code_contexts: list[dict] = []

    def generate_hypothesis(self, context):
        self.hypothesis_contexts.append(dict(context))
        return self.hypothesis

    def generate_code(self, context):
        self.code_contexts.append(dict(context))
        return self.patch


class SequentialPatchCreative(FakeCreative):
    def __init__(self, patches: list[PatchProposal], **kwargs) -> None:
        super().__init__(**kwargs)
        self.patches = list(patches)

    def generate_code(self, context):
        self.code_contexts.append(dict(context))
        if not self.patches:
            return self.patch
        return self.patches.pop(0)


class TimeoutThenPatchCreative(FakeCreative):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._timed_out = False

    def generate_code(self, context):
        self.code_contexts.append(dict(context))
        if not self._timed_out:
            self._timed_out = True
            raise LLMRetryExhaustedError(
                "Tool call failed after 3 attempt(s). Last error: Request timed out"
            )
        return self.patch


class PlanningCreative(FakeCreative):
    def __init__(self, plans: list[dict], **kwargs) -> None:
        super().__init__(**kwargs)
        self.plans = list(plans)
        self.planner_contexts: list[dict] = []

    def select_tool(self, context):
        self.planner_contexts.append(dict(context))
        if not self.plans:
            return {"stop": True}
        return self.plans.pop(0)


class ToolSelectionClient:
    def __init__(self, selections: list[dict]) -> None:
        self.selections = list(selections)
        self.prompts: list[str] = []
        self.tool_names: list[str] = []

    def call_with_tool(self, prompt, tool, model=None, system_blocks=None):
        self.prompts.append(prompt)
        self.tool_names.append(tool["name"])
        if tool["name"] == "plan_proposal_tool_call":
            if not self.selections:
                return {"intent": "stop"}
            return self.selections.pop(0)
        if tool["name"] == "generate_hypothesis":
            return _valid_hypothesis_payload()
        if tool["name"] == "generate_patch":
            return _valid_policy_patch_payload()
        raise AssertionError(f"unexpected tool request: {tool['name']}")


class CapturingToolClient:
    def __init__(self) -> None:
        self.prompts: list[str] = []
        self.system_blocks: list[list[dict]] = []
        self.tool_names: list[str] = []

    def call_with_tool(self, prompt, tool, model=None, system_blocks=None):
        self.prompts.append(prompt)
        self.system_blocks.append(list(system_blocks or []))
        self.tool_names.append(tool["name"])
        if tool["name"] == "generate_hypothesis":
            return _valid_hypothesis_payload()
        if tool["name"] == "generate_patch":
            return _valid_policy_patch_payload()
        raise AssertionError(f"unexpected tool request: {tool['name']}")


class _EmptyToolInput(BaseModel):
    pass


class LargeObservationTool:
    permission = ProposalToolPermission.READ_PUBLIC_CONTEXT
    read_only = True
    concurrency_safe = True
    max_result_chars = 200000

    def __init__(
        self,
        name: str,
        *,
        payload_chars: int,
        is_error: bool = False,
    ) -> None:
        self.name = name
        self.payload_chars = payload_chars
        self.is_error = is_error
        self.input_schema = _EmptyToolInput

    def call(
        self,
        args: BaseModel,
        context: ProposalToolContext,
    ) -> ProposalObservation:
        return ProposalObservation(
            observation_id=f"{self.name}-obs",
            session_id=context.session_id,
            tool_name=self.name,
            tool_call_id="",
            observation_type="huge_error" if self.is_error else "huge_payload",
            summary="Returned deliberately large test observation.",
            structured_payload={"payload": "x" * self.payload_chars},
            taint=ProposalTaint.PROPOSAL,
            exposure_level=ProposalExposureLevel.PUBLIC_SPEC,
            is_error=self.is_error,
            failure_code=(
                ProposalToolFailureCode.RUNTIME_EXCEPTION if self.is_error else None
            ),
        )


class HangingContractPreviewTool:
    name = "proposal.contract_preview"
    permission = ProposalToolPermission.CONTRACT_PREVIEW
    read_only = True
    concurrency_safe = True
    max_result_chars = 1000
    input_schema = _EmptyToolInput

    def call(
        self,
        args: BaseModel,
        context: ProposalToolContext,
    ) -> ProposalObservation:
        while True:
            pass


def _problem_spec(root: Path) -> ProblemSpecV1:
    return ProblemSpecV1(
        spec_version="problem-v1",
        id="toy_routing",
        display_name="Toy Routing",
        root_dir=str(root),
        description="Synthetic routing problem for proposal-tool tests.",
        search_space={
            "editable": ["operators/*.py", "policies/*.py"],
            "frozen": ["solver.py"],
            "import_whitelist": ["math"],
        },
        operator_interface={
            "base_class_import": "toy.operators.base:ToyOperator",
            "execute_signature": "execute(self, solution, rng) -> Solution",
            "categories": [{"name": "route_local", "description": "local moves"}],
        },
        objectives=[
            {
                "name": "distance",
                "direction": "minimize",
                "priority": 1,
                "tie_tolerance": 0.0,
            },
            {
                "name": "route_count",
                "direction": "minimize",
                "priority": 2,
                "tie_tolerance": 0.0,
            },
        ],
        objective_policy={"mode": "lexicographic"},
        runtime_failure_guidance=[
            {
                "failure_categories": ["no_accepted_moves"],
                "applies_to_surface_kinds": ["operator"],
                "min_category_fraction": 0.5,
                "min_count": 1,
                "recommended_surfaces": ["search_policy"],
                "discouraged_surfaces": ["route_local"],
                "guidance": "Use the declared budget surface when local moves do not accept.",
            }
        ],
        research_surfaces=[
            {
                "name": "route_local",
                "kind": "operator",
                "description": "Local operator surface.",
                "targets": {"files": ["operators/*.py"]},
                "interface": {"required_functions": ["execute"]},
            },
            {
                "name": "search_policy",
                "kind": "policy",
                "description": "Controls search budget.",
                "algorithm": {
                    "role": "search_budget_policy",
                    "invocation_point": "before_main_search",
                    "description": "Chooses bounded time and iteration budgets.",
                },
                "targets": {
                    "files": ["policies/search_policy.py"],
                    "create_new_allowed": False,
                    "modify_allowed": True,
                    "remove_allowed": False,
                    "singleton": True,
                },
                "interface": {
                    "required_functions": [
                        "baseline_time_fraction",
                        "max_operator_rounds",
                    ],
                    "function_signatures": {
                        "baseline_time_fraction": ["instance", "time_limit_sec"],
                        "max_operator_rounds": ["instance", "time_limit_sec"],
                    },
                    "return_contract": "deterministic scalar policy values",
                },
                "bounds": {
                    "allowed_components": ["baseline_budget", "round_limit"],
                    "numeric_ranges": {
                        "baseline_time_fraction": [0.05, 0.95],
                        "max_operator_rounds": [0, 50],
                    },
                    "complexity_scale_terms": ["problem_size", "time_limit_sec"],
                },
                "evidence": {
                    "required_runtime_fields": ["policy_loaded", "policy_errors"]
                },
                "novelty": {
                    "strategy": "semantic_signature",
                    "signature_fields": ["budget_pattern", "round_limit_pattern"],
                },
                "prompt": {
                    "hypothesis_guidance": "Explain expected budget tradeoff.",
                    "implementation_guidance": "Keep policy deterministic.",
                    "anti_patterns": "Do not read external result files.",
                },
            },
        ],
        adapter={
            "import_path": "scion.problems.toy_routing.adapter:ToyAdapter",
            "api_version": "v1",
        },
    )


def _champion(root: Path) -> ChampionState:
    (root / "operators").mkdir(parents=True)
    (root / "policies").mkdir(parents=True)
    (root / "operators" / "local_a.py").write_text(
        "class LocalA:\n    def execute(self, solution, rng):\n        return solution\n",
        encoding="utf-8",
    )
    (root / "policies" / "search_policy.py").write_text(
        "def baseline_time_fraction(instance, time_limit_sec):\n    return 0.50\n"
        "def max_operator_rounds(instance, time_limit_sec):\n    return 12\n",
        encoding="utf-8",
    )
    return ChampionState(
        version=7,
        operator_pool={
            "local_a": OperatorConfig(
                name="local_a",
                file_path="operators/local_a.py",
                category="route_local",
                weight=1.0,
                class_name="LocalA",
            )
        },
        solver_config_hash="solver-hash",
        code_snapshot_path=str(root),
        code_snapshot_hash="code-hash",
        promotion_experiment_id="promotion-secret",
        promoted_at="2026-05-06T00:00:00",
        weight_revision=3,
    )


def _stats(**overrides) -> EvalStats:
    values = {
        "n_cases": 2,
        "wins": 1,
        "losses": 1,
        "ties": 0,
        "win_rate": 0.5,
        "median_delta": 0.0,
        "ci_low": -0.1,
        "ci_high": 0.1,
        "runtime_ratio_median": 1.2,
        "runtime_delta_median_ms": 10.0,
        "runtime_regression_rate": 0.5,
        "runtime_pairs": 2,
        "total_pairs": 2,
        "attempted_pairs": 2,
        "valid_pairs": 2,
    }
    values.update(overrides)
    return EvalStats(**values)


def _hyp(surface: str = "search_policy") -> HypothesisProposal:
    novelty_signature = {}
    if surface == "search_policy":
        novelty_signature = {
            "budget_pattern": "lower_baseline_fraction",
            "round_limit_pattern": "fixed_small_cap",
        }
    return HypothesisProposal(
        hypothesis_text=f"Improve {surface}.",
        change_locus=surface,
        action="modify",
        target_file="policies/search_policy.py",
        novelty_signature=novelty_signature,
    )


def _valid_hypothesis_payload(**overrides) -> dict:
    payload = {
        "hypothesis_text": "Tighten the search policy budget while protecting solution quality.",
        "change_locus": "search_policy",
        "action": "modify",
        "target_file": "policies/search_policy.py",
        "predicted_direction": "tradeoff",
        "target_weakness": "Current policy spends too much time in weak rounds.",
        "expected_effect": "Reduce runtime while preserving distance.",
        "target_objectives": ["distance"],
        "protected_objectives": ["route_count"],
        "objective_tradeoff_policy": "Protect route count lexicographically.",
        "no_op_condition": "Keep baseline budget when size is small.",
        "risk_to_higher_priority": "May reduce search too much on large cases.",
        "target_runtime_effect": "improve",
        "complexity_claim": "O(1) policy calculations.",
        "runtime_budget_strategy": "Use fixed scalar caps.",
        "novelty_signature": {
            "budget_pattern": "lower_baseline_fraction",
            "round_limit_pattern": "fixed_small_cap",
        },
    }
    payload.update(overrides)
    if payload.get("change_locus") == "solver_design":
        if "target_file" not in overrides:
            payload["target_file"] = "policies/baseline_algorithm.py"
        if "target_objectives" not in overrides:
            payload["target_objectives"] = ["total_distance"]
        if "protected_objectives" not in overrides:
            payload["protected_objectives"] = ["fleet_violation"]
        signature = dict(payload.get("novelty_signature") or {})
        signature.setdefault("algorithm_family", "route_pair_local_search")
        signature.setdefault("construction_strategy", "nearest_neighbor_seed_pool")
        signature.setdefault("improvement_strategy", "bounded_route_pair_swap")
        signature.setdefault("acceptance_strategy", "strict_no_restart")
        signature.setdefault("runtime_budget_strategy", "bounded_passes")
        payload["novelty_signature"] = signature
    return payload


def _valid_policy_patch_payload(**overrides) -> dict:
    payload = {
        "file_path": "policies/search_policy.py",
        "action": "modify",
        "code_content": (
            "def baseline_time_fraction(instance, time_limit_sec):\n"
            "    return 0.35\n\n"
            "def max_operator_rounds(instance, time_limit_sec):\n"
            "    return 10\n"
        ),
    }
    payload.update(overrides)
    return payload


def _tool_enabled_policy() -> ContextExposurePolicy:
    return ContextExposurePolicy(
        allow_contract_preview=True,
        allow_draft_artifact=True,
    )


def _step(
    round_num: int,
    stage: ExperimentStage,
    raw_metrics_ref: str,
    *,
    gate_outcome: str = "fail",
) -> StepRecord:
    case_feedback = ()
    if stage == ExperimentStage.SCREENING:
        case_feedback = (
            CaseAggregateFeedback(
                case_id="screen-case",
                n_pairs=2,
                wins=1,
                losses=1,
                ties=0,
                win_rate=0.5,
                dominant_result="mixed",
                decisive_metric="distance",
                median_deltas={"distance": -1.0},
            ),
        )
    return StepRecord(
        round_num=round_num,
        branch_id="branch-1",
        hypothesis=_hyp(),
        patch=None,
        contract_passed=True,
        verification_passed=True,
        protocol_result=ProtocolResult(
            stage=stage,
            stats=_stats(),
            gate_outcome=gate_outcome,
            reason_codes=(f"{stage.value.upper()}_REASON",),
            exposed_summary=f"{stage.value} safe summary",
            raw_metrics_ref=raw_metrics_ref,
            case_feedback=case_feedback,
        ),
        decision=None,
        failure_stage=None,
        failure_detail=None,
    )


class UnsafeMemory:
    def render(self, view: str = "audit") -> str:
        assert view == "hypothesis"
        return (
            "safe screening idea\n"
            "champion_evolution: promoted v7\n"
            "validation holdout signal should not appear\n"
            "frozen raw_metrics path should not appear\n"
            "route_local coverage gap\n"
        )


class UnsafeDefaultOnlyMemory:
    def render(self) -> str:
        return (
            "safe screening idea\n"
            "promotion path: champion v7\n"
            "validation holdout SECRET_HOLDOUT_SIGNAL\n"
        )


class NonCallableRenderMemory:
    render = "not callable"


def _context(
    tmp_path: Path,
    *,
    policy: ContextExposurePolicy | None = None,
) -> ProposalToolContext:
    champion_root = tmp_path / "champion"
    metrics_root = tmp_path / "metrics"
    metrics_root.mkdir()
    screening_ref = metrics_root / "screening_metrics.json"
    validation_ref = metrics_root / "SECRET_VALIDATION_metrics.json"
    frozen_ref = metrics_root / "SECRET_FROZEN_metrics.json"
    screening_ref.write_text(
        json.dumps(
            {
                "pairs": [
                    {
                        "case": "/safe/screen-case",
                        "seed": 1,
                        "runtime_ratio": 2.7,
                        "candidate_elapsed_ms": 270,
                        "champion_elapsed_ms": 100,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    validation_ref.write_text('{"secret": "validation raw"}', encoding="utf-8")
    frozen_ref.write_text('{"secret": "frozen raw"}', encoding="utf-8")
    return ProposalToolContext(
        session_id="session-1",
        campaign_id="camp-1",
        branch=Branch(
            branch_id="branch-1",
            state=BranchState.EXPLORE,
            base_champion_id=7,
            base_champion_hash="code-hash",
        ),
        champion=_champion(champion_root),
        problem_spec=_problem_spec(tmp_path),
        step_history=(
            _step(1, ExperimentStage.SCREENING, str(screening_ref)),
            _step(2, ExperimentStage.VALIDATION, str(validation_ref)),
            _step(3, ExperimentStage.FROZEN, str(frozen_ref), gate_outcome="pass"),
        ),
        search_memory=UnsafeMemory(),
        policy=policy or ContextExposurePolicy(),
        problem_id="toy_routing",
        problem_spec_hash="spec-hash",
    )


def _overlapping_surface_context(tmp_path: Path) -> ProposalToolContext:
    context = _context(tmp_path, policy=_tool_enabled_policy())
    payload = _problem_spec(tmp_path).model_dump()
    payload["search_space"]["editable"] = ["shared/*.py"]
    payload["search_space"]["import_whitelist"] = ["math"]
    payload["research_surfaces"] = [
        {
            "name": "local",
            "kind": "operator",
            "description": "Broad generated files.",
            "targets": {"files": ["shared/*.py"]},
        },
        {
            "name": "budget_policy",
            "kind": "policy",
            "description": "Specific budget policy.",
            "targets": {
                "files": ["shared/policy.py"],
                "create_new_allowed": False,
                "modify_allowed": True,
                "remove_allowed": False,
                "singleton": True,
            },
            "interface": {
                "required_functions": ["choose_budget"],
                "function_signatures": {"choose_budget": ["instance"]},
            },
            "bounds": {"complexity_scale_terms": ["item_count"]},
        },
    ]
    return replace(
        context,
        problem_spec=ProblemSpecV1(**payload),
        adapter=None,
        problem_spec_hash="overlap-spec-hash",
    )


def _cvrp_context(tmp_path: Path) -> ProposalToolContext:
    spec = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    return ProposalToolContext(
        session_id="session-cvrp",
        campaign_id="camp-cvrp",
        branch=Branch(
            branch_id="branch-cvrp",
            state=BranchState.EXPLORE,
            base_champion_id=1,
            base_champion_hash="code-hash",
        ),
        champion=None,
        problem_spec=spec,
        adapter=CvrpAdapter(spec),
        step_history=(),
        policy=_tool_enabled_policy(),
        problem_id="cvrp",
        problem_spec_hash="cvrp-spec-hash",
    )


def _cvrp_context_with_champion(tmp_path: Path) -> ProposalToolContext:
    context = _cvrp_context(tmp_path)
    champion_root = tmp_path / "cvrp_champion"
    (champion_root / "policies").mkdir(parents=True)
    (champion_root / "policies" / "baseline_algorithm.py").write_text(
        (_CVRP_ROOT / "policies" / "baseline_algorithm.py").read_text(
            encoding="utf-8"
        ),
        encoding="utf-8",
    )
    shutil.copytree(
        _CVRP_ROOT / "policies" / "baseline_modules",
        champion_root / "policies" / "baseline_modules",
    )
    return replace(
        context,
        champion=ChampionState(
            version=1,
            operator_pool={},
            solver_config_hash="solver-hash",
            code_snapshot_path=str(champion_root),
            code_snapshot_hash="code-hash",
        ),
    )

__all__ = [
    name
    for name in globals()
    if not (name.startswith("__") and name.endswith("__"))
]
