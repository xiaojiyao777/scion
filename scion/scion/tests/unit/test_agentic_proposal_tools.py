from __future__ import annotations

import json
from dataclasses import fields, replace
from pathlib import Path
from types import SimpleNamespace

from pydantic import BaseModel

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
    StepRecord,
)
from scion.problem.spec import ProblemSpecV1
from scion.problem.bridge import load_problem_spec_v1_from_yaml
from scion.problems.cvrp.adapter import CvrpAdapter
from scion.proposal.agentic_session import (
    AGENTIC_SESSION_SCHEMA_VERSION,
    AgenticProposalRequest,
    AgenticProposalSession,
    AgenticProposalStatus,
    AgenticSessionStore,
    AgenticTerminationReason,
    AgenticToolLoopConfig,
    FileAgenticSessionArtifactStore,
    compute_agentic_idempotency_key,
    resume_from_artifact,
    validate_agentic_session_artifact,
)
from scion.proposal.engine import CreativeLayer
from scion.proposal.tools import (
    ContextExposurePolicy,
    HoldoutExposure,
    ProposalExposureLevel,
    ProposalObservation,
    ProposalTaint,
    ProposalToolContext,
    ProposalToolFailureCode,
    ProposalToolRegistry,
)


_COMPACT_FEEDBACK_TOOL_NAMES = {
    "memory.query",
    "feedback.query_screening",
    "feedback.query_runtime",
}
_SCION_PACKAGE_ROOT = Path(__file__).resolve().parents[2]
_CVRP_ROOT = _SCION_PACKAGE_ROOT / "problems" / "cvrp"


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
    return HypothesisProposal(
        hypothesis_text=f"Improve {surface}.",
        change_locus=surface,
        action="modify",
        target_file="policies/search_policy.py",
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
    }
    payload.update(overrides)
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


def test_list_and_read_surfaces_return_v2_metadata_without_domain_hardcoding(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(tmp_path)

    listed = registry.call("context.list_surfaces", {}, context)
    read = registry.call(
        "context.read_surface",
        {"surface": "search_policy", "include_code": True},
        context,
    )

    surfaces = {s["name"]: s for s in listed.structured_payload["surfaces"]}
    assert surfaces["search_policy"]["algorithm"]["role"] == "search_budget_policy"
    assert surfaces["search_policy"]["bounds"]["allowed_components"] == [
        "baseline_budget",
        "round_limit",
    ]
    surface = read.structured_payload["surface"]
    assert surface["algorithm"]["invocation_point"] == "before_main_search"
    assert surface["interface"]["required_functions"] == [
        "baseline_time_fraction",
        "max_operator_rounds",
    ]
    assert read.structured_payload["current_artifact"]["readable"] is True


def test_list_surfaces_returns_compact_payload_for_large_surface_specs(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _cvrp_context(tmp_path)

    observation = registry.call("context.list_surfaces", {}, context)
    rendered = json.dumps(observation.structured_payload, sort_keys=True, default=str)
    surfaces = {
        surface["name"]: surface
        for surface in observation.structured_payload["surfaces"]
    }

    assert observation.is_error is False
    assert observation.structured_payload["detail"] == "compact"
    assert "algorithm_blueprint" in surfaces
    assert surfaces["algorithm_blueprint"]["algorithm"]["role"] == (
        "top_level_algorithm_lifecycle"
    )
    assert "prompt" not in rendered
    assert len(rendered) < AgenticToolLoopConfig().max_observation_chars // 2


def test_read_surface_defaults_to_compact_code_payload(tmp_path: Path) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(tmp_path)
    policy_file = (
        Path(context.champion.code_snapshot_path) / "policies" / "search_policy.py"
    )
    policy_file.write_text(
        "def baseline_time_fraction(instance, time_limit_sec):\n"
        "    return 0.50\n\n"
        "def max_operator_rounds(instance, time_limit_sec):\n"
        "    return 12\n\n"
        + "\n".join(f"# filler {idx}" for idx in range(800)),
        encoding="utf-8",
    )

    observation = registry.call(
        "context.read_surface",
        {"surface": "search_policy"},
        context,
    )
    artifact = observation.structured_payload["current_artifact"]
    rendered = json.dumps(observation.structured_payload, sort_keys=True, default=str)

    assert observation.is_error is False
    assert observation.structured_payload["detail"] == "compact"
    assert artifact["readable"] is True
    assert artifact["truncated"] is True
    assert artifact["max_chars"] == 1200
    assert len(artifact["content_preview"]) <= 1200
    assert len(rendered) < AgenticToolLoopConfig().max_observation_chars // 2


def test_read_surface_full_and_explicit_max_code_chars(tmp_path: Path) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(tmp_path)
    policy_file = (
        Path(context.champion.code_snapshot_path) / "policies" / "search_policy.py"
    )
    full_code = (
        "def baseline_time_fraction(instance, time_limit_sec):\n"
        "    return 0.50\n\n"
        "def max_operator_rounds(instance, time_limit_sec):\n"
        "    return 12\n\n"
        + "\n".join(f"# full filler {idx}" for idx in range(240))
    )
    policy_file.write_text(full_code, encoding="utf-8")

    full = registry.call(
        "context.read_surface",
        {"surface": "search_policy", "detail": "full"},
        context,
    )
    capped = registry.call(
        "context.read_surface",
        {
            "surface": "search_policy",
            "detail": "full",
            "max_code_chars": 80,
        },
        context,
    )

    full_artifact = full.structured_payload["current_artifact"]
    capped_artifact = capped.structured_payload["current_artifact"]
    assert full.is_error is False
    assert full.structured_payload["detail"] == "full"
    assert full_artifact["max_chars"] == 12000
    assert full_artifact["truncated"] is False
    assert full_artifact["content_preview"] == full_code
    assert capped.is_error is False
    assert capped_artifact["max_chars"] == 80
    assert capped_artifact["truncated"] is True
    assert len(capped_artifact["content_preview"]) <= 80


def test_read_algorithm_blueprint_compact_payload_stays_below_session_budget(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _cvrp_context(tmp_path)
    champion_root = tmp_path / "cvrp_champion"
    (champion_root / "policies").mkdir(parents=True)
    blueprint = _CVRP_ROOT / "policies" / "algorithm_blueprint.py"
    (champion_root / "policies" / "algorithm_blueprint.py").write_text(
        blueprint.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    context = replace(
        context,
        champion=ChampionState(
            version=1,
            operator_pool={},
            solver_config_hash="solver-hash",
            code_snapshot_path=str(champion_root),
            code_snapshot_hash="code-hash",
        ),
    )

    listed = registry.call("context.list_surfaces", {}, context)
    read = registry.call(
        "context.read_surface",
        {"surface": "algorithm_blueprint"},
        context,
    )
    rendered = json.dumps(
        [listed.structured_payload, read.structured_payload],
        sort_keys=True,
        default=str,
    )

    assert listed.is_error is False
    assert read.is_error is False
    assert read.structured_payload["detail"] == "compact"
    assert read.structured_payload["surface"]["name"] == "algorithm_blueprint"
    assert read.structured_payload["current_artifact"]["readable"] is True
    assert len(rendered) < AgenticToolLoopConfig().max_observation_chars


def test_read_surface_target_not_declared_fails_permission(tmp_path: Path) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(tmp_path)

    observation = registry.call(
        "context.read_surface",
        {"surface": "search_policy", "target_file": "secret/holdout_metrics.json"},
        context,
    )

    assert observation.is_error is True
    assert observation.failure_code == ProposalToolFailureCode.PERMISSION_DENIED


def test_read_surface_wildcard_does_not_match_nested_path(tmp_path: Path) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(tmp_path)
    archive = Path(context.champion.code_snapshot_path) / "operators" / "archive"
    archive.mkdir()
    (archive / "secret.py").write_text("SECRET_NESTED_OPERATOR = True\n", encoding="utf-8")

    observation = registry.call(
        "context.read_surface",
        {"surface": "route_local", "target_file": "operators/archive/secret.py"},
        context,
    )

    assert observation.is_error is True
    assert observation.failure_code == ProposalToolFailureCode.PERMISSION_DENIED
    assert "SECRET_NESTED_OPERATOR" not in json.dumps(
        observation.structured_payload,
        sort_keys=True,
    )


def test_read_surface_rejects_parent_and_absolute_target_paths(tmp_path: Path) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(tmp_path)
    absolute_target = str(
        Path(context.champion.code_snapshot_path) / "operators" / "local_a.py"
    )

    traversal = registry.call(
        "context.read_surface",
        {
            "surface": "route_local",
            "target_file": "operators/../policies/search_policy.py",
        },
        context,
    )
    absolute = registry.call(
        "context.read_surface",
        {"surface": "route_local", "target_file": absolute_target},
        context,
    )

    assert traversal.is_error is True
    assert traversal.failure_code == ProposalToolFailureCode.PERMISSION_DENIED
    assert absolute.is_error is True
    assert absolute.failure_code == ProposalToolFailureCode.PERMISSION_DENIED


def test_read_surface_declared_symlink_escape_is_not_read(tmp_path: Path) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(tmp_path)
    outside = tmp_path / "SECRET_OUTSIDE.py"
    outside.write_text("SECRET_SYMLINK_ESCAPE = True\n", encoding="utf-8")
    link = Path(context.champion.code_snapshot_path) / "operators" / "leak.py"
    link.symlink_to(outside)

    observation = registry.call(
        "context.read_surface",
        {"surface": "route_local", "target_file": "operators/leak.py"},
        context,
    )

    assert observation.is_error is False
    artifact = observation.structured_payload["current_artifact"]
    assert artifact["readable"] is False
    assert artifact["reason"] == "symlink_not_allowed"
    assert "SECRET_SYMLINK_ESCAPE" not in json.dumps(
        observation.structured_payload,
        sort_keys=True,
    )


def test_read_surface_declared_in_snapshot_symlink_is_not_read(tmp_path: Path) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(tmp_path)
    solver = Path(context.champion.code_snapshot_path) / "solver.py"
    solver.write_text("SECRET_SOLVER_CONTENT = True\n", encoding="utf-8")
    link = Path(context.champion.code_snapshot_path) / "operators" / "leak.py"
    link.symlink_to(Path("..") / "solver.py")

    observation = registry.call(
        "context.read_surface",
        {"surface": "route_local", "target_file": "operators/leak.py"},
        context,
    )

    assert observation.is_error is False
    artifact = observation.structured_payload["current_artifact"]
    assert artifact["file_path"] == "operators/leak.py"
    assert artifact["readable"] is False
    assert artifact["reason"] == "symlink_not_allowed"
    assert "SECRET_SOLVER_CONTENT" not in json.dumps(
        observation.structured_payload,
        sort_keys=True,
    )


def test_validation_and_frozen_raw_metric_refs_are_not_exposed_by_read_only_tools(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(
        tmp_path,
        policy=ContextExposurePolicy(
            validation_exposure=HoldoutExposure.AGGREGATE,
            frozen_exposure=HoldoutExposure.AGGREGATE,
        ),
    )

    observations = [
        registry.call("context.list_surfaces", {}, context),
        registry.call("context.read_problem", {}, context),
        registry.call("context.read_objective_policy", {}, context),
        registry.call("context.read_champion_summary", {}, context),
        registry.call("context.read_surface", {"surface": "search_policy"}, context),
        registry.call("memory.query", {}, context),
        registry.call("feedback.query_screening", {}, context),
        registry.call("feedback.query_holdout_summary", {}, context),
        registry.call("feedback.query_runtime", {}, context),
    ]
    rendered = json.dumps(
        [obs.structured_payload for obs in observations],
        sort_keys=True,
        default=str,
    )

    assert "raw_metrics_ref" not in rendered
    assert "SECRET_VALIDATION" not in rendered
    assert "SECRET_FROZEN" not in rendered
    assert "validation raw" not in rendered
    assert "frozen raw" not in rendered


def test_feedback_query_runtime_includes_problem_declared_failure_guidance(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(tmp_path)
    runtime_step = replace(
        context.step_history[0],
        hypothesis=HypothesisProposal(
            hypothesis_text="Local move surface produced no accepted moves.",
            change_locus="route_local",
            action="create_new",
            target_file="operators/local_new.py",
        ),
        protocol_result=ProtocolResult(
            stage=ExperimentStage.SCREENING,
            stats=_stats(wins=0, losses=0, ties=2, win_rate=0.0),
            gate_outcome="continue",
            reason_codes=("tie_dominated",),
            exposed_summary="screening safe summary",
            raw_metrics_ref="/SECRET/raw/metrics/SECRET_RAW_REF.json",
            candidate_runtime_failure_categories={"no_accepted_moves": 2},
            candidate_operator_attempts=24,
            candidate_operator_accepted=0,
        ),
    )
    context = replace(context, step_history=(runtime_step,))

    observation = registry.call("feedback.query_runtime", {}, context)
    payload = observation.structured_payload
    rendered = json.dumps(payload, sort_keys=True)

    assert "runtime_failure_guidance" in payload
    assert "recommended_surfaces: search_policy" in payload["runtime_failure_guidance"]
    assert "discouraged_surfaces: route_local" in payload["runtime_failure_guidance"]
    assert "declared budget surface" in payload["runtime_failure_guidance"]
    assert "raw_metrics_ref" not in rendered
    assert "SECRET_RAW_REF" not in rendered


def test_default_holdout_summary_exposes_no_validation_or_frozen_rows(
    tmp_path: Path,
) -> None:
    observation = ProposalToolRegistry.default_read_only().call(
        "feedback.query_holdout_summary",
        {},
        _context(tmp_path),
    )

    assert observation.structured_payload["holdout_steps"] == []
    assert observation.structured_payload["validation_exposure"] == "none"
    assert observation.structured_payload["frozen_exposure"] == "none"


def test_memory_query_hides_promotion_and_holdout_signals(tmp_path: Path) -> None:
    observation = ProposalToolRegistry.default_read_only().call(
        "memory.query",
        {},
        _context(tmp_path),
    )

    text = observation.structured_payload["text"].lower()
    assert "safe screening idea" in text
    assert "champion_evolution" not in text
    assert "promoted" not in text
    assert "promotion" not in text
    assert "validation" not in text
    assert "frozen" not in text
    assert "holdout" not in text


def test_memory_query_rejects_default_render_without_safe_view(tmp_path: Path) -> None:
    context = _context(tmp_path)
    context = ProposalToolContext(
        session_id=context.session_id,
        campaign_id=context.campaign_id,
        branch=context.branch,
        champion=context.champion,
        problem_spec=context.problem_spec,
        adapter=context.adapter,
        step_history=context.step_history,
        search_memory=UnsafeDefaultOnlyMemory(),
        research_log=context.research_log,
        policy=context.policy,
        problem_id=context.problem_id,
        problem_spec_hash=context.problem_spec_hash,
    )

    observation = ProposalToolRegistry.default_read_only().call("memory.query", {}, context)
    rendered = json.dumps(observation.structured_payload, sort_keys=True)

    assert observation.is_error is True
    assert observation.failure_code == ProposalToolFailureCode.UNSUPPORTED
    assert "SECRET_HOLDOUT_SIGNAL" not in rendered
    assert "promotion path" not in rendered


def test_memory_query_rejects_non_callable_render(tmp_path: Path) -> None:
    context = _context(tmp_path)
    context = ProposalToolContext(
        session_id=context.session_id,
        campaign_id=context.campaign_id,
        branch=context.branch,
        champion=context.champion,
        problem_spec=context.problem_spec,
        adapter=context.adapter,
        step_history=context.step_history,
        search_memory=NonCallableRenderMemory(),
        research_log=context.research_log,
        policy=context.policy,
        problem_id=context.problem_id,
        problem_spec_hash=context.problem_spec_hash,
    )

    observation = ProposalToolRegistry.default_read_only().call("memory.query", {}, context)

    assert observation.is_error is True
    assert observation.failure_code == ProposalToolFailureCode.UNSUPPORTED


def test_champion_summary_hides_version_and_promotion_fields(tmp_path: Path) -> None:
    observation = ProposalToolRegistry.default_read_only().call(
        "context.read_champion_summary",
        {},
        _context(tmp_path),
    )
    rendered = json.dumps(observation.structured_payload, sort_keys=True)

    assert "version" not in rendered
    assert "promotion" not in rendered
    assert "promoted_at" not in rendered
    assert "promotion-secret" not in rendered


def test_read_only_tools_do_not_write_workspace_files(tmp_path: Path) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(tmp_path)
    before = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))

    registry.call("context.read_surface", {"surface": "search_policy"}, context)
    registry.call("feedback.query_screening", {}, context)
    registry.call("feedback.query_holdout_summary", {}, context)
    registry.call("feedback.query_runtime", {}, context)
    registry.call("memory.query", {}, context)

    after = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    assert after == before


def test_draft_hypothesis_accepts_structured_fields_and_rejects_invalid_values(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(tmp_path, policy=_tool_enabled_policy())

    valid = registry.call(
        "proposal.draft_hypothesis",
        _valid_hypothesis_payload(),
        context,
    )
    invalid_direction = registry.call(
        "proposal.draft_hypothesis",
        _valid_hypothesis_payload(predicted_direction="sideways"),
        context,
    )
    invalid_objective = registry.call(
        "proposal.draft_hypothesis",
        _valid_hypothesis_payload(target_objectives=["SECRET_SCORE"]),
        context,
    )

    assert valid.is_error is False
    assert valid.artifact_ref is not None
    assert valid.structured_payload["artifact_kind"] == "hypothesis_draft"
    assert valid.structured_payload["hypothesis"]["target_objectives"] == ["distance"]
    assert invalid_direction.is_error is True
    assert invalid_direction.failure_code == ProposalToolFailureCode.SCHEMA_ERROR
    assert invalid_objective.is_error is True
    assert invalid_objective.failure_code == ProposalToolFailureCode.SCHEMA_ERROR


def test_draft_patch_returns_artifact_without_workspace_write(tmp_path: Path) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(tmp_path, policy=_tool_enabled_policy())
    before = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))

    observation = registry.call(
        "proposal.draft_patch",
        _valid_policy_patch_payload(),
        context,
    )

    after = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    assert observation.is_error is False
    assert observation.artifact_ref is not None
    assert observation.structured_payload["artifact_kind"] == "patch_draft"
    assert observation.structured_payload["workspace_materialized"] is False
    assert observation.structured_payload["patch"]["file_path"] == "policies/search_policy.py"
    assert after == before


def test_schema_target_and_interface_previews_catch_static_issues(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(tmp_path, policy=_tool_enabled_policy())

    schema = registry.call(
        "proposal.schema_preview",
        {"hypothesis": _valid_hypothesis_payload(predicted_direction="bad")},
        context,
    )
    unknown_surface = registry.call(
        "proposal.target_permission_preview",
        {
            "change_locus": "missing_surface",
            "action": "modify",
            "target_file": "policies/search_policy.py",
        },
        context,
    )
    disallowed_action = registry.call(
        "proposal.target_permission_preview",
        {
            "change_locus": "search_policy",
            "action": "remove",
            "target_file": "policies/search_policy.py",
        },
        context,
    )
    wrong_target = registry.call(
        "proposal.target_permission_preview",
        {
            "change_locus": "search_policy",
            "action": "modify",
            "target_file": "operators/local_a.py",
        },
        context,
    )
    missing_function = registry.call(
        "proposal.interface_preview",
        _valid_policy_patch_payload(
            code_content="def baseline_time_fraction(size):\n    return 0.35\n"
        ),
        context,
    )

    assert schema.is_error is False
    assert schema.structured_payload["passed"] is False
    assert unknown_surface.structured_payload["passed"] is False
    assert "unknown research surface" in unknown_surface.structured_payload["issues"][0]
    assert disallowed_action.structured_payload["passed"] is False
    assert wrong_target.structured_payload["passed"] is False
    assert missing_function.structured_payload["passed"] is False
    assert missing_function.structured_payload["declared_function_signatures"] == {
        "baseline_time_fraction": ["instance", "time_limit_sec"],
        "max_operator_rounds": ["instance", "time_limit_sec"],
    }
    assert any(
        "missing required functions" in check["detail"]
        for check in missing_function.structured_payload["checks"]
    )


def test_target_permission_preview_is_compact_without_full_surface_payload(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(tmp_path, policy=_tool_enabled_policy())

    observation = registry.call(
        "proposal.target_permission_preview",
        {
            "change_locus": "search_policy",
            "action": "modify",
            "target_file": "policies/search_policy.py",
        },
        context,
    )
    payload = observation.structured_payload
    rendered = json.dumps(payload, sort_keys=True)

    assert observation.is_error is False
    assert payload["passed"] is True
    assert payload["surface"] == {
        "name": "search_policy",
        "kind": "policy",
        "allowed_actions": ["modify"],
        "declared_targets": ["policies/search_policy.py"],
    }
    assert payload["permission"]["target_declared"] is True
    assert payload["issues"] == []
    assert "algorithm" not in rendered
    assert "bounds" not in rendered
    assert "interface" not in rendered
    assert "prompt" not in rendered
    assert "code_content" not in rendered


def test_contract_preview_is_static_and_does_not_materialize_workspace(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(tmp_path, policy=_tool_enabled_policy())
    before = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))

    observation = registry.call(
        "proposal.contract_preview",
        {
            "hypothesis": _valid_hypothesis_payload(),
            "patch": _valid_policy_patch_payload(),
        },
        context,
    )

    after = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))
    assert observation.is_error is False
    assert observation.structured_payload["passed"] is True
    assert observation.structured_payload["static_only"] is True
    assert observation.structured_payload["workspace_materialized"] is False
    assert observation.structured_payload["verification_run"] is False
    assert observation.structured_payload["protocol_run"] is False
    assert observation.structured_payload["decision_run"] is False
    assert after == before


def test_contract_preview_patch_payload_is_compact_without_code_content(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(tmp_path, policy=_tool_enabled_policy())
    patch_payload = _valid_policy_patch_payload()

    schema = registry.call(
        "proposal.schema_preview",
        {"patch": patch_payload},
        context,
    )
    contract = registry.call(
        "proposal.contract_preview",
        {
            "hypothesis": _valid_hypothesis_payload(),
            "patch": patch_payload,
        },
        context,
    )
    schema_patch = schema.structured_payload["patch"]["patch"]
    contract_patch = contract.structured_payload["patch"]["patch"]
    rendered = json.dumps(
        [schema.structured_payload, contract.structured_payload],
        sort_keys=True,
    )

    assert schema.is_error is False
    assert contract.is_error is False
    assert schema_patch["file_path"] == "policies/search_policy.py"
    assert schema_patch["action"] == "modify"
    assert schema_patch["code_char_count"] == len(patch_payload["code_content"])
    assert len(schema_patch["code_digest"]) == 64
    assert schema_patch["functions"] == [
        "baseline_time_fraction",
        "max_operator_rounds",
    ]
    assert schema_patch["classes"] == []
    assert contract_patch == schema_patch
    assert contract.structured_payload["patch"]["checks"]
    assert "code_content" not in rendered
    assert "return 0.35" not in rendered


def test_cvrp_policy_preview_good_defaults_pass(tmp_path: Path) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _cvrp_context(tmp_path)

    patches = [
        {
            "file_path": "policies/construction_policy.py",
            "action": "modify",
            "code_content": (
                _CVRP_ROOT / "policies" / "construction_policy.py"
            ).read_text(encoding="utf-8"),
        },
        {
            "file_path": "policies/search_policy.py",
            "action": "modify",
            "code_content": (
                _CVRP_ROOT / "policies" / "search_policy.py"
            ).read_text(encoding="utf-8"),
        },
        {
            "file_path": "policies/neighborhood_portfolio.py",
            "action": "modify",
            "code_content": (
                _CVRP_ROOT / "policies" / "neighborhood_portfolio.py"
            ).read_text(encoding="utf-8"),
        },
    ]

    for patch in patches:
        observation = registry.call("proposal.interface_preview", patch, context)
        assert observation.is_error is False
        assert observation.structured_payload["passed"] is True
        assert observation.structured_payload["problem_preview"]["passed"] is True


def test_cvrp_construction_policy_preview_fails_bad_dynamic_mode_and_bias(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _cvrp_context(tmp_path)

    observation = registry.call(
        "proposal.interface_preview",
        {
            "file_path": "policies/construction_policy.py",
            "action": "modify",
            "code_content": (
                "def construction_mode(instance, time_limit_sec):\n"
                "    mode = 'savings'\n"
                "    return mode\n\n"
                "def construction_bias(instance, time_limit_sec):\n"
                "    bias = 2.0\n"
                "    return bias\n"
            ),
        },
        context,
    )

    preview = observation.structured_payload["problem_preview"]
    assert observation.structured_payload["passed"] is False
    assert preview["passed"] is False
    assert "unknown mode" in json.dumps(preview)
    assert "construction_bias" in json.dumps(preview)


def test_cvrp_search_and_portfolio_preview_fail_bad_limits_and_components(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _cvrp_context(tmp_path)

    bad_search = registry.call(
        "proposal.interface_preview",
        {
            "file_path": "policies/search_policy.py",
            "action": "modify",
            "code_content": (
                "def baseline_time_fraction(instance, time_limit_sec):\n"
                "    return 0.8\n\n"
                "def max_operator_rounds(instance, time_limit_sec):\n"
                "    rounds = 99\n"
                "    return rounds\n\n"
                "def enable_post_baseline_operators(instance, time_limit_sec):\n"
                "    return True\n"
            ),
        },
        context,
    )
    bad_portfolio = registry.call(
        "proposal.interface_preview",
        {
            "file_path": "policies/neighborhood_portfolio.py",
            "action": "modify",
            "code_content": (
                "def enabled_components(instance, time_limit_sec):\n"
                "    component = 'not_registered'\n"
                "    return [component]\n\n"
                "def component_weights(instance, time_limit_sec):\n"
                "    return {'route_local': float('inf')}\n\n"
                "def candidate_limits(instance, time_limit_sec):\n"
                "    limit = 999\n"
                "    return {'top_k': limit}\n"
            ),
        },
        context,
    )

    assert bad_search.structured_payload["passed"] is False
    assert "max_operator_rounds" in json.dumps(
        bad_search.structured_payload["problem_preview"]
    )
    assert bad_portfolio.structured_payload["passed"] is False
    rendered = json.dumps(bad_portfolio.structured_payload["problem_preview"])
    assert "unknown components" in rendered
    assert "non-finite" in rendered
    assert "top_k" in rendered


def test_cvrp_contract_preview_records_problem_preview_failure_without_raw_refs(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _cvrp_context(tmp_path)

    observation = registry.call(
        "proposal.contract_preview",
        {
            "hypothesis": _valid_hypothesis_payload(
                change_locus="construction_policy",
                target_file="policies/construction_policy.py",
                target_objectives=["total_distance"],
                protected_objectives=["fleet_violation"],
            ),
            "patch": {
                "file_path": "policies/construction_policy.py",
                "action": "modify",
                "code_content": (
                    "def construction_mode(instance, time_limit_sec):\n"
                    "    mode = 'savings'\n"
                    "    return mode\n\n"
                    "def construction_bias(instance, time_limit_sec):\n"
                    "    return 0.5\n"
                ),
            },
        },
        context,
    )

    rendered = json.dumps(observation.structured_payload, sort_keys=True)
    assert observation.is_error is False
    assert observation.structured_payload["passed"] is False
    assert observation.structured_payload["patch"]["problem_preview"]["passed"] is False
    assert "issues" in observation.structured_payload["patch"]["problem_preview"]
    assert "synthetic_instance" not in rendered
    assert "code_content" not in rendered
    assert "raw_metrics_ref" not in rendered
    assert "SECRET_RAW" not in rendered


def test_unsupported_or_unsafe_file_targets_fail_closed(tmp_path: Path) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(tmp_path, policy=_tool_enabled_policy())

    draft = registry.call(
        "proposal.draft_patch",
        _valid_policy_patch_payload(file_path="../secret.py"),
        context,
    )
    preview = registry.call(
        "proposal.contract_preview",
        {"patch": _valid_policy_patch_payload(file_path="/tmp/secret.py")},
        context,
    )

    assert draft.is_error is True
    assert draft.failure_code == ProposalToolFailureCode.PERMISSION_DENIED
    assert preview.is_error is False
    assert preview.structured_payload["passed"] is False
    assert preview.structured_payload["patch"]["passed"] is False


def test_aps3_tool_observations_remain_tainted_and_bounded(tmp_path: Path) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(tmp_path, policy=_tool_enabled_policy())
    observations = [
        registry.call("proposal.draft_hypothesis", _valid_hypothesis_payload(), context),
        registry.call("proposal.draft_patch", _valid_policy_patch_payload(), context),
        registry.call(
            "proposal.contract_preview",
            {"patch": _valid_policy_patch_payload()},
            context,
        ),
    ]

    for observation in observations:
        tool = registry.get(observation.tool_name)
        rendered = json.dumps(observation.structured_payload, sort_keys=True, default=str)
        assert observation.taint == ProposalTaint.PROPOSAL
        assert len(rendered) <= tool.max_result_chars
    assert observations[0].exposure_level == ProposalExposureLevel.SCRATCH
    assert observations[1].exposure_level == ProposalExposureLevel.SCRATCH


def test_aps3_tool_permissions_default_deny_draft_and_contract_preview(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(tmp_path, policy=ContextExposurePolicy())

    draft = registry.call(
        "proposal.draft_hypothesis",
        _valid_hypothesis_payload(),
        context,
    )
    preview = registry.call(
        "proposal.contract_preview",
        {"patch": _valid_policy_patch_payload()},
        context,
    )

    assert draft.is_error is True
    assert draft.failure_code == ProposalToolFailureCode.PERMISSION_DENIED
    assert preview.is_error is True
    assert preview.failure_code == ProposalToolFailureCode.PERMISSION_DENIED


def test_aps3_tool_permissions_explicit_allow_passes(tmp_path: Path) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(tmp_path, policy=_tool_enabled_policy())

    draft = registry.call(
        "proposal.draft_hypothesis",
        _valid_hypothesis_payload(),
        context,
    )
    preview = registry.call(
        "proposal.contract_preview",
        {
            "hypothesis": _valid_hypothesis_payload(),
            "patch": _valid_policy_patch_payload(),
        },
        context,
    )

    assert draft.is_error is False
    assert preview.is_error is False
    assert preview.structured_payload["passed"] is True


def test_contract_preview_patch_only_is_incomplete_without_hypothesis(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(tmp_path, policy=_tool_enabled_policy())

    preview = registry.call(
        "proposal.contract_preview",
        {"patch": _valid_policy_patch_payload()},
        context,
    )

    assert preview.is_error is False
    assert preview.structured_payload["passed"] is False
    assert preview.structured_payload["needs_hypothesis"] is True
    assert preview.structured_payload["patch"]["needs_hypothesis"] is True


def test_contract_preview_rejects_nested_wildcard_target_and_allows_direct(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(tmp_path, policy=_tool_enabled_policy())
    operator_hypothesis = _valid_hypothesis_payload(
        change_locus="route_local",
        action="modify",
        target_file="operators/local_a.py",
    )
    operator_patch = {
        "file_path": "operators/local_a.py",
        "action": "modify",
        "code_content": (
            "class LocalA:\n"
            "    def execute(self, solution, rng):\n"
            "        return solution\n"
        ),
    }

    direct = registry.call(
        "proposal.contract_preview",
        {"hypothesis": operator_hypothesis, "patch": operator_patch},
        context,
    )
    nested = registry.call(
        "proposal.contract_preview",
        {
            "hypothesis": {
                **operator_hypothesis,
                "target_file": "operators/archive/evil.py",
            },
            "patch": {
                **operator_patch,
                "file_path": "operators/archive/evil.py",
            },
        },
        context,
    )

    assert direct.structured_payload["passed"] is True
    assert nested.structured_payload["passed"] is False


def test_registry_rejects_non_read_only_tool() -> None:
    class WriteTool:
        name = "unsafe.write"
        input_schema = BaseModel
        permission = "write_scratch"
        read_only = False
        concurrency_safe = False
        max_result_chars = 32000

        def call(self, args, context):  # pragma: no cover - registration must fail.
            raise AssertionError("tool should not be callable")

    registry = ProposalToolRegistry()

    try:
        registry.register(WriteTool())
    except ValueError as exc:
        assert "read-only tools only" in str(exc)
    else:  # pragma: no cover - explicit failure branch for clarity.
        raise AssertionError("non-read-only proposal tool was registered")


def test_tool_result_size_guard_returns_error(tmp_path: Path) -> None:
    registry = ProposalToolRegistry.default_read_only()
    tool = registry.get("context.read_problem")
    tool.max_result_chars = 10

    observation = registry.call("context.read_problem", {}, _context(tmp_path))

    assert observation.is_error is True
    assert observation.failure_code == ProposalToolFailureCode.RESULT_TOO_LARGE
    assert observation.structured_payload["max_result_chars"] == 10


def test_holdout_aggregate_does_not_expose_malicious_raw_refs_or_case_ids(
    tmp_path: Path,
) -> None:
    context = _context(
        tmp_path,
        policy=ContextExposurePolicy(
            validation_exposure=HoldoutExposure.AGGREGATE,
            frozen_exposure=HoldoutExposure.AGGREGATE,
        ),
    )
    malicious_step = StepRecord(
        round_num=4,
        branch_id="branch-1",
        hypothesis=_hyp(),
        patch=None,
        contract_passed=True,
        verification_passed=True,
        protocol_result=ProtocolResult(
            stage=ExperimentStage.VALIDATION,
            stats=_stats(),
            gate_outcome="fail",
            reason_codes=("VALIDATION_REASON",),
            exposed_summary="validation safe summary",
            raw_metrics_ref="/SECRET/raw/metrics/SECRET_RAW_REF.json",
            case_ids=("SECRET_CASE_ID",),
            seed_set=(999,),
            case_feedback=(
                CaseAggregateFeedback(
                    case_id="SECRET_CASE_ID",
                    n_pairs=2,
                    wins=2,
                    losses=0,
                    ties=0,
                    win_rate=1.0,
                    dominant_result="win",
                    decisive_metric="distance",
                    median_deltas={"distance": -5.0},
                ),
            ),
        ),
        decision=None,
        failure_stage=None,
        failure_detail=None,
    )
    context = ProposalToolContext(
        session_id=context.session_id,
        campaign_id=context.campaign_id,
        branch=context.branch,
        champion=context.champion,
        problem_spec=context.problem_spec,
        adapter=context.adapter,
        step_history=(malicious_step,),
        search_memory=context.search_memory,
        research_log=context.research_log,
        policy=context.policy,
        problem_id=context.problem_id,
        problem_spec_hash=context.problem_spec_hash,
    )

    observation = ProposalToolRegistry.default_read_only().call(
        "feedback.query_holdout_summary",
        {},
        context,
    )
    rendered = json.dumps(observation.structured_payload, sort_keys=True)

    assert observation.is_error is False
    assert "SECRET_RAW_REF" not in rendered
    assert "SECRET_CASE_ID" not in rendered
    assert "case_feedback" not in rendered
    assert "raw_metrics_ref" not in rendered


def test_tool_observation_fields_do_not_enter_decision_features() -> None:
    observation_fields = {field.name for field in fields(ProposalObservation)}
    decision_fields = {field.name for field in fields(DecisionFeatures)}

    assert observation_fields.isdisjoint(decision_fields)


def test_agentic_session_records_tool_observations_in_evidence_and_transcript(
    tmp_path: Path,
) -> None:
    creative = FakeCreative()
    context = _context(tmp_path, policy=_tool_enabled_policy())
    session = AgenticProposalSession(
        creative,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-1",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={"seed": "hypothesis"},
            build_code_context=lambda hypothesis: {"approved": hypothesis.change_locus},
            approve_hypothesis=lambda _hypothesis: SimpleNamespace(
                passed=True,
                failure_reason=None,
            ),
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    transcript = [event.metadata for event in output.transcript]
    tool_names = [
        event["tool_name"]
        for event in transcript
        if "tool_name" in event
    ]

    assert output.status == AgenticProposalStatus.COMPLETED
    assert output.evidence_used
    assert "context.list_surfaces" in tool_names
    assert "context.read_problem" in tool_names
    assert "memory.query" in tool_names
    assert "feedback.query_screening" in tool_names
    assert "proposal.schema_preview" in tool_names
    assert "proposal.target_permission_preview" in tool_names
    assert "proposal.contract_preview" in tool_names
    assert output.self_check.schema_valid is True
    assert output.self_check.contract_preview_passed is True
    assert creative.hypothesis_contexts[0]["agentic_tool_observations"]
    for event in output.transcript:
        if "tool_name" not in event.metadata:
            continue
        assert {
            "step_id",
            "tool_name",
            "status",
            "taint",
            "evidence_ref",
            "result_summary",
            "error_code",
        }.issubset(event.metadata)
        assert "structured_payload" not in event.metadata


def test_agentic_session_tool_loop_limits_are_enforced(tmp_path: Path) -> None:
    creative = FakeCreative()
    context = _context(tmp_path, policy=_tool_enabled_policy())
    session = AgenticProposalSession(
        creative,
        tool_registry=ProposalToolRegistry.default_read_only(),
        tool_loop_config=AgenticToolLoopConfig(max_steps=2, max_tool_calls=2),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-1",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={},
            build_code_context=lambda _hypothesis: {"kind": "code"},
            approve_hypothesis=lambda _hypothesis: SimpleNamespace(
                passed=True,
                failure_reason=None,
            ),
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    tool_events = [event for event in output.transcript if event.metadata.get("tool_name")]
    stop_events = [
        event for event in output.transcript
        if event.metadata.get("stop_reason") == "tool_loop_limit"
    ]

    assert output.status == AgenticProposalStatus.COMPLETED
    assert [event.metadata["tool_name"] for event in tool_events] == [
        "context.list_surfaces",
        "context.read_problem",
    ]
    assert stop_events


def test_agentic_session_wall_time_timeout_returns_typed_failure(
    tmp_path: Path,
) -> None:
    context = _context(tmp_path, policy=_tool_enabled_policy())
    session = AgenticProposalSession(
        FakeCreative(),
        tool_registry=ProposalToolRegistry.default_read_only(),
        tool_loop_config=AgenticToolLoopConfig(max_wall_time_sec=0.0),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-1",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={},
            build_code_context=lambda _hypothesis: {"kind": "code"},
            approve_hypothesis=lambda _hypothesis: SimpleNamespace(
                passed=True,
                failure_reason=None,
            ),
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    assert output.status == AgenticProposalStatus.FAILED
    assert output.termination_reason == AgenticTerminationReason.SESSION_TIMEOUT
    assert output.hypothesis is None
    assert output.patch is None
    assert output.tool_budget_used["tool_calls"] == 0


def test_agentic_session_repeated_tool_call_fuse_falls_back(
    tmp_path: Path,
) -> None:
    creative = PlanningCreative(
        [
            {"tool_name": "context.list_surfaces", "args": {}},
            {"tool_name": "context.list_surfaces", "args": {}},
            {"tool_name": "context.list_surfaces", "args": {}},
        ]
    )
    context = _context(tmp_path, policy=_tool_enabled_policy())
    artifact_store = FileAgenticSessionArtifactStore(tmp_path / "aps-artifacts")
    session = AgenticProposalSession(
        creative,
        artifact_store=artifact_store,
        tool_registry=ProposalToolRegistry.default_read_only(),
        tool_loop_config=AgenticToolLoopConfig(max_repeated_tool_calls=1),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-1",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={},
            build_code_context=lambda _hypothesis: {"kind": "code"},
            approve_hypothesis=lambda _hypothesis: SimpleNamespace(
                passed=True,
                failure_reason=None,
            ),
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )
    error_events = [
        event.metadata
        for event in output.transcript
        if event.metadata.get("error_code") == "repeated_tool_call_fuse"
    ]

    assert output.status == AgenticProposalStatus.COMPLETED
    assert output.termination_reason == AgenticTerminationReason.COMPLETED
    assert output.patch is not None
    assert error_events
    assert any(
        event.metadata.get("selection_source") == "fallback_selected"
        for event in output.transcript
    )


def test_agentic_idempotency_key_is_stable_and_anchor_config_sensitive(
    tmp_path: Path,
) -> None:
    context = _context(tmp_path, policy=_tool_enabled_policy())
    config = AgenticToolLoopConfig(max_tool_calls=4)
    request = AgenticProposalRequest(
        campaign_id="camp-1",
        branch=context.branch,
        champion=context.champion,
        hypothesis_context={},
        build_code_context=lambda _hypothesis: {"kind": "code"},
        problem_id=context.problem_id,
        problem_spec_hash=context.problem_spec_hash,
        tool_context=context,
    )
    same_request = AgenticProposalRequest(
        campaign_id="camp-1",
        branch=context.branch,
        champion=context.champion,
        hypothesis_context={"ignored_for_key": "different prompt text"},
        build_code_context=lambda _hypothesis: {"kind": "code"},
        problem_id=context.problem_id,
        problem_spec_hash=context.problem_spec_hash,
        tool_context=context,
    )
    changed_branch = Branch(
        branch_id=context.branch.branch_id,
        state=context.branch.state,
        base_champion_id=context.branch.base_champion_id,
        base_champion_hash="different-base",
    )
    changed_request = AgenticProposalRequest(
        campaign_id="camp-1",
        branch=changed_branch,
        champion=context.champion,
        hypothesis_context={},
        build_code_context=lambda _hypothesis: {"kind": "code"},
        problem_id=context.problem_id,
        problem_spec_hash=context.problem_spec_hash,
        tool_context=replace(context, branch=changed_branch),
    )

    key = compute_agentic_idempotency_key(request, config)
    assert key == compute_agentic_idempotency_key(same_request, config)
    assert key != compute_agentic_idempotency_key(
        request,
        AgenticToolLoopConfig(max_tool_calls=5),
    )
    assert key != compute_agentic_idempotency_key(changed_request, config)


def test_partial_hypothesis_idempotency_key_is_surface_sensitive(
    tmp_path: Path,
) -> None:
    context = _context(tmp_path, policy=_tool_enabled_policy())
    route_hypothesis = HypothesisProposal(
        **_valid_hypothesis_payload(
            change_locus="route_local",
            action="modify",
            target_file="operators/local_a.py",
        )
    )
    policy_hypothesis = HypothesisProposal(**_valid_hypothesis_payload())
    request = AgenticProposalRequest(
        campaign_id="camp-1",
        branch=context.branch,
        champion=context.champion,
        hypothesis_context={},
        build_code_context=lambda _hypothesis: {"kind": "code"},
        problem_id=context.problem_id,
        problem_spec_hash=context.problem_spec_hash,
        tool_context=context,
    )

    route_output = AgenticProposalSession(
        FakeCreative(hypothesis=route_hypothesis),
        tool_registry=ProposalToolRegistry.default_read_only(),
    ).run(request)
    policy_output = AgenticProposalSession(
        FakeCreative(hypothesis=policy_hypothesis),
        tool_registry=ProposalToolRegistry.default_read_only(),
    ).run(request)

    assert route_output.status == AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY
    assert policy_output.status == AgenticProposalStatus.PARTIAL_HYPOTHESIS_ONLY
    assert route_output.selected_surface == "route_local"
    assert policy_output.selected_surface == "search_policy"
    assert route_output.idempotency_key != policy_output.idempotency_key
    assert route_output.idempotency_key != compute_agentic_idempotency_key(
        request,
        AgenticToolLoopConfig(),
    )


def test_agentic_session_step_limit_fail_closes_missing_required_context(
    tmp_path: Path,
) -> None:
    context = _context(tmp_path, policy=_tool_enabled_policy())
    session = AgenticProposalSession(
        FakeCreative(),
        tool_registry=ProposalToolRegistry.default_read_only(),
        tool_loop_config=AgenticToolLoopConfig(max_steps=1, max_tool_calls=4),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-1",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={},
            build_code_context=lambda _hypothesis: {"kind": "code"},
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    assert output.status == AgenticProposalStatus.FAILED
    assert "missing required proposal context tools" in (output.failure_detail or "")


def test_agentic_session_fallback_fixed_plan_still_works(tmp_path: Path) -> None:
    creative = FakeCreative()
    context = _context(tmp_path, policy=_tool_enabled_policy())
    session = AgenticProposalSession(
        creative,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-1",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={},
            build_code_context=lambda _hypothesis: {"kind": "code"},
            approve_hypothesis=lambda _hypothesis: SimpleNamespace(
                passed=True,
                failure_reason=None,
            ),
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    assert output.status == AgenticProposalStatus.COMPLETED
    assert any(
        event.metadata.get("fallback") == "fixed_tool_plan"
        for event in output.transcript
    )
    assert any(
        event.metadata.get("selection_source") == "fallback_selected"
        for event in output.transcript
        if event.metadata.get("tool_name")
    )
    assert creative.hypothesis_contexts


def test_model_side_tool_selection_adapter_executes_allowed_tool(
    tmp_path: Path,
) -> None:
    client = ToolSelectionClient(
        [
            {"intent": "call_tool", "tool_name": "context.list_surfaces", "args": {}},
            {"intent": "call_tool", "tool_name": "context.read_problem", "args": {}},
            {"intent": "stop"},
        ]
    )
    creative = CreativeLayer(client, model="test-model")
    context = _context(tmp_path, policy=_tool_enabled_policy())
    session = AgenticProposalSession(
        creative,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-1",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={},
            build_code_context=lambda _hypothesis: {"kind": "code"},
            approve_hypothesis=lambda _hypothesis: SimpleNamespace(
                passed=True,
                failure_reason=None,
            ),
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    planner_events = [
        event.metadata for event in output.transcript
        if event.metadata.get("selection_source") == "planner_selected"
    ]
    assert output.status == AgenticProposalStatus.COMPLETED
    assert [event["tool_name"] for event in planner_events[:2]] == [
        "context.list_surfaces",
        "context.read_problem",
    ]
    assert client.tool_names[:2] == ["plan_proposal_tool_call"] * 2
    assert "allowed_tool_specs" in client.prompts[0]
    assert "raw_metrics_ref" not in client.prompts[0]


def test_planner_stop_after_problem_context_falls_back_to_feedback_and_surface_read(
    tmp_path: Path,
) -> None:
    creative = PlanningCreative(
        [
            {"tool_name": "context.list_surfaces", "args": {}},
            {"tool_name": "context.read_problem", "args": {}},
            {"stop": True},
        ]
    )
    context = _context(tmp_path, policy=_tool_enabled_policy())
    session = AgenticProposalSession(
        creative,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-1",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={},
            build_code_context=lambda _hypothesis: {"kind": "code"},
            approve_hypothesis=lambda _hypothesis: SimpleNamespace(
                passed=True,
                failure_reason=None,
            ),
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )
    tool_events = [
        event.metadata
        for event in output.transcript
        if event.metadata.get("tool_name")
    ]
    tool_names = [event["tool_name"] for event in tool_events]
    code_observations = creative.code_contexts[0]["agentic_tool_observations"]

    assert output.status == AgenticProposalStatus.COMPLETED
    assert any(
        event.metadata.get("error_code")
        == "planner_stopped_before_required_context"
        for event in output.transcript
    )
    assert any(name in tool_names for name in _COMPACT_FEEDBACK_TOOL_NAMES)
    assert any(
        event["tool_name"] == "context.read_surface"
        and event["selection_source"] == "selected_surface_required"
        for event in tool_events
    )
    assert any(
        observation["tool_name"] == "context.read_surface"
        and observation["structured_payload"]["surface"]["name"] == "search_policy"
        and observation["structured_payload"]["detail"] == "compact"
        and observation["structured_payload"]["current_artifact"]["max_chars"] == 1200
        for observation in code_observations
    )
    assert any(
        observation["tool_name"] in _COMPACT_FEEDBACK_TOOL_NAMES
        for observation in creative.hypothesis_contexts[0]["agentic_tool_observations"]
    )


def test_agentic_session_bounded_planner_rejects_forbidden_tool(
    tmp_path: Path,
) -> None:
    creative = PlanningCreative(
        [
            {"tool_name": "proposal.contract_preview", "args": {}},
        ]
    )
    context = _context(tmp_path, policy=ContextExposurePolicy())
    session = AgenticProposalSession(
        creative,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-1",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={},
            build_code_context=lambda _hypothesis: {"kind": "code"},
            approve_hypothesis=lambda _hypothesis: SimpleNamespace(
                passed=True,
                failure_reason=None,
            ),
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    contract_events = [
        event.metadata for event in output.transcript
        if event.metadata.get("tool_name") == "proposal.contract_preview"
    ]
    assert output.status == AgenticProposalStatus.COMPLETED
    assert contract_events
    assert contract_events[0]["status"] == "error"
    assert contract_events[0]["error_code"] == "invalid_tool_selection"
    assert contract_events[0]["fallback"] == "fixed_tool_plan"
    assert not any(
        event.get("selection_source") == "planner_selected"
        for event in contract_events
    )
    assert "proposal.contract_preview" not in creative.planner_contexts[0]["allowed_tools"]


def test_model_side_forbidden_tool_selection_is_rejected_before_execution(
    tmp_path: Path,
) -> None:
    client = ToolSelectionClient(
        [
            {
                "intent": "call_tool",
                "tool_name": "proposal.contract_preview",
                "args": {},
            }
        ]
    )
    creative = CreativeLayer(client, model="test-model")
    context = _context(tmp_path, policy=ContextExposurePolicy())
    session = AgenticProposalSession(
        creative,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-1",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={},
            build_code_context=lambda _hypothesis: {"kind": "code"},
            approve_hypothesis=lambda _hypothesis: SimpleNamespace(
                passed=True,
                failure_reason=None,
            ),
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    invalid_events = [
        event.metadata for event in output.transcript
        if event.metadata.get("error_code") == "invalid_tool_selection"
    ]
    forbidden_tool_events = [
        event.metadata for event in output.transcript
        if event.metadata.get("tool_name") == "proposal.contract_preview"
    ]
    assert output.status == AgenticProposalStatus.COMPLETED
    assert invalid_events
    assert invalid_events[0]["fallback"] == "fixed_tool_plan"
    assert not any(
        event.get("selection_source") == "planner_selected"
        for event in forbidden_tool_events
    )


def test_model_side_malformed_tool_selection_falls_back_without_raw_refs(
    tmp_path: Path,
) -> None:
    client = ToolSelectionClient(
        [
            {
                "intent": "call_tool",
                "tool_name": "context.list_surfaces",
                "args": "not-json-object",
            }
        ]
    )
    creative = CreativeLayer(client, model="test-model")
    context = _context(tmp_path, policy=_tool_enabled_policy())
    artifact_store = FileAgenticSessionArtifactStore(tmp_path / "aps-artifacts")
    session = AgenticProposalSession(
        creative,
        artifact_store=artifact_store,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-1",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={
                "raw_metrics_ref": "/SECRET/raw.json",
                "note": "safe line\nvalidation SECRET_HOLDOUT_SIGNAL",
            },
            build_code_context=lambda _hypothesis: {"kind": "code"},
            approve_hypothesis=lambda _hypothesis: SimpleNamespace(
                passed=True,
                failure_reason=None,
            ),
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    rendered_output = json.dumps(output, default=str, sort_keys=True)
    assert output.status == AgenticProposalStatus.COMPLETED
    assert any(
        event.metadata.get("error_code") == "planner_exception"
        for event in output.transcript
    )
    assert any(
        event.metadata.get("fallback") == "fixed_tool_plan"
        for event in output.transcript
    )
    assert "raw_metrics_ref" not in rendered_output
    assert "SECRET_HOLDOUT_SIGNAL" not in rendered_output
    assert "raw_metrics_ref" not in client.prompts[0]
    assert "SECRET_HOLDOUT_SIGNAL" not in client.prompts[0]


def test_agentic_session_fallback_does_not_repeat_successful_required_tools(
    tmp_path: Path,
) -> None:
    creative = PlanningCreative(
        [
            {"tool_name": "context.list_surfaces", "args": {}},
            {"tool_name": "context.read_surface", "args": "bad-args"},
        ]
    )
    context = _context(tmp_path, policy=_tool_enabled_policy())
    session = AgenticProposalSession(
        creative,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-1",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={},
            build_code_context=lambda _hypothesis: {"kind": "code"},
            approve_hypothesis=lambda _hypothesis: SimpleNamespace(
                passed=True,
                failure_reason=None,
            ),
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    tool_names = [
        event.metadata["tool_name"]
        for event in output.transcript
        if event.metadata.get("step_id")
    ]

    assert output.status == AgenticProposalStatus.COMPLETED
    assert tool_names.count("context.list_surfaces") == 1
    assert tool_names.count("context.read_problem") == 1
    assert "memory.query" in tool_names
    assert any(
        event.metadata.get("skip_reason") == "already_succeeded"
        for event in output.transcript
    )


def test_planner_nonexistent_surface_falls_back_and_generates_patch(
    tmp_path: Path,
) -> None:
    creative = PlanningCreative(
        [
            {"tool_name": "context.list_surfaces", "args": {}},
            {"tool_name": "context.read_surface", "args": {"surface": "main"}},
            {"tool_name": "context.read_surface", "args": {"surface": "main"}},
        ]
    )
    context = _context(tmp_path, policy=_tool_enabled_policy())
    artifact_store = FileAgenticSessionArtifactStore(tmp_path / "aps-artifacts")
    session = AgenticProposalSession(
        creative,
        artifact_store=artifact_store,
        tool_registry=ProposalToolRegistry.default_read_only(),
        tool_loop_config=AgenticToolLoopConfig(max_repeated_tool_calls=1),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-1",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={},
            build_code_context=lambda _hypothesis: {"kind": "code"},
            approve_hypothesis=lambda _hypothesis: SimpleNamespace(
                passed=True,
                failure_reason=None,
            ),
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    rendered = json.dumps(output, default=str, sort_keys=True)
    output_ref = next(ref for ref in output.tainted_artifact_refs if ref.endswith("output.json"))
    artifact = json.loads(Path(output_ref).read_text(encoding="utf-8"))
    rendered_artifact = json.dumps(artifact, default=str, sort_keys=True)
    read_surface_events = [
        event.metadata
        for event in output.transcript
        if event.metadata.get("tool_name") == "context.read_surface"
        and event.metadata.get("step_id")
    ]

    assert output.status == AgenticProposalStatus.COMPLETED
    assert output.hypothesis is not None
    assert output.patch is not None
    assert output.termination_reason not in {
        AgenticTerminationReason.TOOL_LOOP_LIMIT,
        AgenticTerminationReason.REPEATED_TOOL_CALL,
    }
    assert len(read_surface_events) == 2
    assert read_surface_events[0]["error_code"] == "not_found"
    assert read_surface_events[1]["status"] == "ok"
    assert read_surface_events[1]["selection_source"] == "selected_surface_required"
    assert creative.planner_contexts[1]["tool_arg_guidance"]["context.read_surface"][
        "allowed_surface_ids"
    ] == ["route_local", "search_policy"]
    assert any(
        event.metadata.get("status") == "fallback_selected"
        and event.metadata.get("fallback") == "fixed_tool_plan"
        for event in output.transcript
    )
    assert "fallback_selected" in rendered_artifact
    assert "raw_metrics_ref" not in rendered
    assert "raw_metrics_ref" not in rendered_artifact
    assert "SECRET_VALIDATION" not in rendered
    assert "SECRET_VALIDATION" not in rendered_artifact
    assert "SECRET_FROZEN" not in rendered
    assert "SECRET_FROZEN" not in rendered_artifact


def test_agentic_session_contract_preview_does_not_replace_real_gate(
    tmp_path: Path,
) -> None:
    bad_patch = PatchProposal(
        file_path="operators/local_a.py",
        action="modify",
        code_content="class LocalA:\n    def execute(self, solution, rng):\n        return solution\n",
    )
    creative = FakeCreative(patch=bad_patch)
    context = _context(tmp_path, policy=_tool_enabled_policy())
    session = AgenticProposalSession(
        creative,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-1",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={},
            build_code_context=lambda _hypothesis: {"kind": "code"},
            approve_hypothesis=lambda _hypothesis: SimpleNamespace(
                passed=True,
                failure_reason=None,
            ),
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    assert output.status == AgenticProposalStatus.COMPLETED
    assert output.patch == bad_patch
    assert output.self_check.contract_preview_passed is False
    assert output.self_check.contract_preview_codes


def test_agentic_session_does_not_emit_raw_refs_in_artifacts(tmp_path: Path) -> None:
    creative = FakeCreative()
    context = _context(tmp_path, policy=_tool_enabled_policy())
    session = AgenticProposalSession(
        creative,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-1",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={
                "raw_metrics_ref": "/SECRET/raw.json",
                "note": "safe line\nvalidation SECRET_HOLDOUT_SIGNAL",
            },
            build_code_context=lambda _hypothesis: {"kind": "code"},
            approve_hypothesis=lambda _hypothesis: SimpleNamespace(
                passed=True,
                failure_reason=None,
            ),
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    rendered_output = json.dumps(output, default=str, sort_keys=True)
    rendered_prompt = json.dumps(creative.hypothesis_contexts, default=str, sort_keys=True)

    assert "raw_metrics_ref" not in rendered_output
    assert "SECRET_VALIDATION" not in rendered_output
    assert "SECRET_FROZEN" not in rendered_output
    assert "SECRET_HOLDOUT_SIGNAL" not in rendered_output
    assert "raw_metrics_ref" not in rendered_prompt
    assert "SECRET_HOLDOUT_SIGNAL" not in rendered_prompt
    for event in output.transcript:
        rendered_event = json.dumps(event.metadata, default=str, sort_keys=True)
        assert "raw_metrics_ref" not in rendered_event
        assert "SECRET_VALIDATION" not in rendered_event
        assert "SECRET_FROZEN" not in rendered_event


def test_agentic_session_artifact_schema_version_and_digest_exist(
    tmp_path: Path,
) -> None:
    creative = FakeCreative()
    context = _context(tmp_path, policy=_tool_enabled_policy())
    artifact_store = FileAgenticSessionArtifactStore(tmp_path / "aps-artifacts")
    session = AgenticProposalSession(
        creative,
        artifact_store=artifact_store,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-1",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={},
            build_code_context=lambda _hypothesis: {"kind": "code"},
            approve_hypothesis=lambda _hypothesis: SimpleNamespace(
                passed=True,
                failure_reason=None,
            ),
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    output_ref = next(ref for ref in output.tainted_artifact_refs if ref.endswith("output.json"))
    artifact = json.loads(Path(output_ref).read_text(encoding="utf-8"))

    assert artifact["schema_version"] == AGENTIC_SESSION_SCHEMA_VERSION
    assert artifact["session_id"] == output.session_id
    assert artifact["request_id"] == output.request_id
    assert artifact["idempotency_key"] == output.idempotency_key
    assert artifact["idempotency_key"].startswith("aps:")
    assert artifact["termination_reason"] == "completed"
    assert artifact["tool_loop_config"]["max_tool_calls"] >= artifact["tool_budget_used"]["tool_calls"]
    assert artifact["transcript_digest"] == output.transcript_digest
    assert artifact["tainted"] is True
    assert artifact["patch"]["patch_body_omitted"] is True
    assert "code_content" not in json.dumps(artifact, sort_keys=True)
    assert validate_agentic_session_artifact(artifact).ok is True


def test_agentic_session_store_indexes_output_and_loads_across_instances(
    tmp_path: Path,
) -> None:
    creative = FakeCreative()
    context = _context(tmp_path, policy=_tool_enabled_policy())
    artifact_dir = tmp_path / "aps-artifacts"
    session = AgenticProposalSession(
        creative,
        artifact_store=FileAgenticSessionArtifactStore(artifact_dir),
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-1",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={},
            build_code_context=lambda _hypothesis: {"kind": "code"},
            approve_hypothesis=lambda _hypothesis: SimpleNamespace(
                passed=True,
                failure_reason=None,
            ),
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    store = AgenticSessionStore(artifact_dir)
    by_session = store.load_by_session_id(output.session_id)
    by_key = AgenticSessionStore(artifact_dir).find_by_idempotency_key(
        output.idempotency_key
    )

    assert store.index_path.exists()
    assert by_session is not None
    assert by_session.validation.ok is True
    assert by_session.entry.session_id == output.session_id
    assert by_session.entry.status == "completed"
    assert by_session.entry.transcript_digest == output.transcript_digest
    assert by_key is not None
    assert by_key.entry.session_id == output.session_id


def test_agentic_replay_validator_rejects_budget_duplicate_step_and_raw_marker(
    tmp_path: Path,
) -> None:
    artifact = {
        "schema_version": AGENTIC_SESSION_SCHEMA_VERSION,
        "session_id": "session-1",
        "request_id": "request-1",
        "termination_reason": "tool_loop_limit",
        "tool_loop_config": {
            "max_steps": 1,
            "max_tool_calls": 1,
            "max_observation_chars": 100,
        },
        "tool_budget_used": {
            "tool_steps": 2,
            "tool_calls": 1,
            "observation_chars": 10,
        },
        "transcript_digest": "wrong",
        "compact_transcript": [
            {
                "phase": "diagnose",
                "metadata": {
                    "step_id": "tool-0001",
                    "tool_name": "context.list_surfaces",
                    "status": "ok",
                    "result_summary": "safe",
                },
            },
            {
                "phase": "diagnose",
                "metadata": {
                    "step_id": "tool-0001",
                    "tool_name": "context.read_problem",
                    "status": "ok",
                    "result_summary": "raw_metrics_ref should reject",
                },
            },
        ],
    }

    result = validate_agentic_session_artifact(artifact)

    assert result.ok is False
    rendered_errors = " ".join(result.errors)
    assert "tool budget exceeded" in rendered_errors
    assert "duplicate step_id" in rendered_errors
    assert "raw ref marker" in rendered_errors


def test_resume_from_artifact_returns_sanitized_length_bounded_context(
    tmp_path: Path,
) -> None:
    creative = FakeCreative()
    context = _context(tmp_path, policy=_tool_enabled_policy())
    artifact_store = FileAgenticSessionArtifactStore(tmp_path / "aps-artifacts")
    session = AgenticProposalSession(
        creative,
        artifact_store=artifact_store,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )
    output = session.run(
        AgenticProposalRequest(
            campaign_id="camp-1",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={},
            build_code_context=lambda _hypothesis: {"kind": "code"},
            approve_hypothesis=lambda _hypothesis: SimpleNamespace(
                passed=True,
                failure_reason=None,
            ),
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )
    output_ref = next(ref for ref in output.tainted_artifact_refs if ref.endswith("output.json"))

    resume_context = resume_from_artifact(output_ref, max_chars=600)
    rendered = json.dumps(resume_context, sort_keys=True)

    assert len(resume_context["summary"]) <= 600
    assert resume_context["session_id"] == output.session_id
    assert resume_context["transcript_digest"] == output.transcript_digest
    assert resume_context["tool_steps"]
    assert {
        "tool_name",
        "status",
        "error_code",
        "evidence_ref",
        "result_summary",
    }.issubset(resume_context["tool_steps"][0])
    assert "structured_payload" not in rendered
    assert "raw_metrics_ref" not in rendered
    assert "SECRET_VALIDATION" not in rendered
    assert "code_content" not in rendered


def test_agentic_session_tool_errors_are_controlled_or_fail_closed(
    tmp_path: Path,
) -> None:
    context = _context(tmp_path, policy=_tool_enabled_policy())
    nonfatal_context = ProposalToolContext(
        session_id=context.session_id,
        campaign_id=context.campaign_id,
        branch=context.branch,
        champion=context.champion,
        problem_spec=context.problem_spec,
        adapter=context.adapter,
        step_history=context.step_history,
        search_memory=NonCallableRenderMemory(),
        research_log=context.research_log,
        policy=context.policy,
        problem_id=context.problem_id,
        problem_spec_hash=context.problem_spec_hash,
    )
    creative = FakeCreative()
    session = AgenticProposalSession(
        creative,
        tool_registry=ProposalToolRegistry.default_read_only(),
    )

    degraded = session.run(
        AgenticProposalRequest(
            campaign_id="camp-1",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={},
            build_code_context=lambda _hypothesis: {"kind": "code"},
            approve_hypothesis=lambda _hypothesis: SimpleNamespace(
                passed=True,
                failure_reason=None,
            ),
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=nonfatal_context,
        )
    )
    failed_closed = AgenticProposalSession(
        FakeCreative(),
        tool_registry=ProposalToolRegistry(),
    ).run(
        AgenticProposalRequest(
            campaign_id="camp-1",
            branch=context.branch,
            champion=context.champion,
            hypothesis_context={},
            build_code_context=lambda _hypothesis: {"kind": "code"},
            problem_id=context.problem_id,
            problem_spec_hash=context.problem_spec_hash,
            tool_context=context,
        )
    )

    memory_events = [
        event.metadata
        for event in degraded.transcript
        if event.metadata.get("tool_name") == "memory.query"
    ]
    assert degraded.status == AgenticProposalStatus.COMPLETED
    assert memory_events[0]["is_error"] is True
    assert failed_closed.status == AgenticProposalStatus.FAILED
    assert creative.hypothesis_contexts
