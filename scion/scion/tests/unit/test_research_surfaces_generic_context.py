from __future__ import annotations

from pathlib import Path

import pytest

from scion.core.models import (
    Branch,
    BranchState,
    CaseAggregateFeedback,
    ChampionState,
    Decision,
    EvalStats,
    ExperimentStage,
    HypothesisProposal,
    HypothesisRecord,
    ProtocolResult,
    StepRecord,
)
from scion.problem.bridge import legacy_problem_spec_from_v1
from scion.problem.spec import ProblemSpecV1
from scion.proposal import context_manager as context_manager_module
from scion.proposal.context.problem_adapter import _build_problem_summary
from scion.proposal.context.surfaces import (
    _build_research_surfaces_block,
)
from scion.proposal.context_manager import ContextManager
from scion.proposal.engine import _split_hypothesis_context
from scion.tests.unit.research_surface_helpers import _problem_payload


def test_context_manager_facade_reexports_extracted_context_helpers() -> None:
    assert (
        context_manager_module._build_research_surfaces_block
        is _build_research_surfaces_block
    )
    assert context_manager_module._build_problem_summary is _build_problem_summary


def test_context_still_renders_legacy_v1_surface_metadata(tmp_path: Path) -> None:
    payload = _problem_payload(str(tmp_path))
    payload["research_surfaces"] = [
        {
            "name": "legacy_surface",
            "kind": "operator",
            "description": "Legacy surface declaration",
            "target_files": ["operators/*.py"],
            "required_functions": ["execute"],
            "prompt_hint": "Keep moves bounded.",
            "create_new_allowed": True,
            "modify_allowed": True,
            "remove_allowed": False,
        },
    ]
    spec_v1 = ProblemSpecV1(**payload)
    legacy = legacy_problem_spec_from_v1(spec_v1)
    (tmp_path / "operators").mkdir()
    (tmp_path / "operators" / "old.py").write_text(
        "class Old:\n    pass\n",
        encoding="utf-8",
    )
    champion = ChampionState(
        version=1,
        operator_pool={},
        solver_config_hash="h",
        code_snapshot_path=str(tmp_path),
        code_snapshot_hash="h",
    )
    branch = Branch(
        branch_id="b1",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="h",
    )

    ctx = ContextManager().build_hypothesis_context(
        branch=branch,
        champion=champion,
        problem_spec=legacy,
        active_hypotheses=[],
        blacklist=[],
    )

    assert (
        "legacy_surface [operator]: Legacy surface declaration"
        in ctx["research_surfaces"]
    )
    assert "targets.files: operators/*.py" in ctx["research_surfaces"]
    assert (
        "action permissions: create_new=true, modify=true, remove=false"
        in ctx["research_surfaces"]
    )
    assert "interface.required_functions: execute" in ctx["research_surfaces"]
    assert (
        "prompt.implementation_guidance: Keep moves bounded."
        in ctx["research_surfaces"]
    )


def test_generic_v2_surface_prompt_has_no_cvrp_or_warehouse_core_terms(
    tmp_path: Path,
) -> None:
    payload = _problem_payload(str(tmp_path))
    payload["description"] = "Generic scheduling benchmark."
    payload["search_space"]["editable"] = ["policies/*.py"]
    payload["research_surfaces"] = [
        {
            "name": "dispatch_policy",
            "kind": "policy",
            "description": "Dispatch timing policy.",
            "algorithm": {
                "role": "dispatch_timing",
                "invocation_point": "before_candidate_selection",
                "description": "Controls generic timing choices.",
            },
            "targets": {
                "files": ["policies/dispatch_policy.py"],
                "create_new_allowed": False,
                "modify_allowed": True,
                "remove_allowed": False,
                "singleton": True,
            },
            "interface": {
                "required_functions": ["select_limit"],
                "function_signatures": {
                    "select_limit": ["instance", "time_limit_sec"]
                },
                "return_contract": "problem-defined scalar values",
            },
            "bounds": {
                "allowed_components": ["limit_selector"],
                "numeric_ranges": {"select_limit": [1, 10]},
                "complexity_scale_terms": ["item_count"],
            },
            "evidence": {"required_runtime_fields": ["policy_loaded"]},
            "novelty": {
                "strategy": "semantic_signature",
                "signature_fields": ["limit_pattern"],
            },
            "prompt": {
                "hypothesis_guidance": "Describe the timing change.",
                "implementation_guidance": "Keep selection bounded.",
                "anti_patterns": "Do not read external files.",
            },
        },
    ]
    spec_v1 = ProblemSpecV1(**payload)
    legacy = legacy_problem_spec_from_v1(spec_v1)
    (tmp_path / "policies").mkdir()
    (tmp_path / "policies" / "dispatch_policy.py").write_text(
        "def select_limit(instance, time_limit_sec):\n    return 5\n",
        encoding="utf-8",
    )
    champion = ChampionState(
        version=1,
        operator_pool={},
        solver_config_hash="h",
        code_snapshot_path=str(tmp_path),
        code_snapshot_hash="h",
    )
    branch = Branch(
        branch_id="b1",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="h",
    )
    manager = ContextManager()

    ctx = manager.build_hypothesis_context(
        branch=branch,
        champion=champion,
        problem_spec=legacy,
        active_hypotheses=[],
        blacklist=[],
    )
    system_blocks, user_prompt = _split_hypothesis_context(ctx)
    prompt_text = "\n".join(block["text"] for block in system_blocks) + user_prompt

    assert "algorithm.role: dispatch_timing" in prompt_text
    assert (
        "interface.function_signatures: select_limit(instance, time_limit_sec)"
        in prompt_text
    )
    assert "bounds.complexity_scale_terms: item_count" in prompt_text
    for forbidden in (
        "cvrp",
        "warehouse",
        "customer",
        "vehicle",
        "depot",
        "cvrplib",
    ):
        assert forbidden not in prompt_text.lower()

    hypothesis = HypothesisProposal(
        hypothesis_text="Tune the dispatch limit.",
        change_locus="dispatch_policy",
        action="modify",
        target_file="policies/dispatch_policy.py",
    )
    code_ctx = manager.build_code_context(
        branch=branch,
        hypothesis=hypothesis,
        champion=champion,
        problem_spec=legacy,
    )

    assert "select_limit" in code_ctx["operator_interface_spec"]
    assert (
        "interface.function_signatures: select_limit(instance, time_limit_sec)"
        in code_ctx["operator_interface_spec"]
    )
    assert "problem-defined scalar values" in code_ctx["operator_interface_spec"]


def test_forced_singleton_config_surface_context_derives_modify_target(
    tmp_path: Path,
) -> None:
    payload = _problem_payload(str(tmp_path))
    payload["search_space"]["editable"] = ["policies/*.py"]
    payload["research_surfaces"] = [
        {
            "name": "algorithm_blueprint",
            "kind": "config",
            "description": "Top-level algorithm plan.",
            "targets": {
                "files": ["policies/algorithm_blueprint.py"],
                "create_new_allowed": False,
                "modify_allowed": True,
                "remove_allowed": False,
                "singleton": True,
            },
            "interface": {
                "required_functions": ["algorithm_plan"],
                "function_signatures": {
                    "algorithm_plan": ["instance", "time_limit_sec"]
                },
                "return_contract": "bounded plan dict",
            },
            "novelty": {
                "strategy": "semantic_signature",
                "signature_fields": ["component_pattern", "budget_pattern"],
            },
        },
    ]
    spec_v1 = ProblemSpecV1(**payload)
    legacy = legacy_problem_spec_from_v1(spec_v1)
    (tmp_path / "policies").mkdir()
    (tmp_path / "policies" / "algorithm_blueprint.py").write_text(
        "def algorithm_plan(instance, time_limit_sec):\n"
        "    return {'enabled': False}\n",
        encoding="utf-8",
    )
    champion = ChampionState(
        version=1,
        operator_pool={},
        solver_config_hash="h",
        code_snapshot_path=str(tmp_path),
        code_snapshot_hash="h",
    )
    branch = Branch(
        branch_id="b1",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="h",
    )

    ctx = ContextManager().build_hypothesis_context(
        branch=branch,
        champion=champion,
        problem_spec=legacy,
        active_hypotheses=[
            HypothesisRecord(
                hypothesis_id="h1",
                branch_id="b-active",
                change_locus="algorithm_blueprint",
                action="modify",
                status="active",
                target_file="policies/algorithm_blueprint.py",
                hypothesis_text="Use the existing bounded plan.",
                novelty_signature={
                    "component_pattern": ["baseline"],
                    "budget_pattern": "conservative",
                },
            )
        ],
        blacklist=[],
        rejected_hypotheses=[
            HypothesisRecord(
                hypothesis_id="h2",
                branch_id="b-rejected",
                change_locus="algorithm_blueprint",
                action="modify",
                status="rejected",
                target_file="policies/algorithm_blueprint.py",
                hypothesis_text="Use an aggressive bounded plan.",
                novelty_signature={
                    "component_pattern": ["repair"],
                    "budget_pattern": "aggressive",
                },
            )
        ],
        forced_locus="algorithm_blueprint",
        forced_surface_diagnostic=True,
    )
    system_blocks, user_prompt = _split_hypothesis_context(ctx)
    prompt_text = "\n".join(block["text"] for block in system_blocks) + user_prompt

    assert ctx["forced_surface"] == "algorithm_blueprint"
    assert ctx["forced_action"] == "modify"
    assert ctx["forced_target_file"] == "policies/algorithm_blueprint.py"
    assert "policies/algorithm_blueprint.py" in ctx["targetable_files"]
    assert "algorithm_plan" in ctx["champion_operators_code"]
    assert "diagnostic experiment-control hook" in prompt_text
    assert "Set `change_locus` to `algorithm_blueprint`." in prompt_text
    assert "Set `action` to `modify`." in prompt_text
    assert "Set `target_file` to `policies/algorithm_blueprint.py`." in prompt_text
    assert (
        "Set `change_locus` exactly to `algorithm_blueprint`."
        in user_prompt
    )
    assert "Set `action` exactly to `modify`." in user_prompt
    assert (
        "Set `target_file` exactly to `policies/algorithm_blueprint.py`."
        in user_prompt
    )
    assert "Choose a research surface from" not in user_prompt
    assert "Do not choose any other research surface" in user_prompt
    assert "This surface uses structured semantic novelty." in prompt_text
    assert (
        "novelty.signature_fields`: component_pattern, budget_pattern"
        in prompt_text
    )
    assert "Occupied structured signatures for this surface:" in prompt_text
    assert '"budget_pattern":"conservative"' in prompt_text
    assert '"budget_pattern":"aggressive"' in prompt_text
    assert "Do not use hypothesis prose as novelty identity" in prompt_text


def test_forced_surface_context_suppresses_off_surface_switch_guidance(
    tmp_path: Path,
) -> None:
    payload = _problem_payload(str(tmp_path))
    payload["search_space"]["editable"] = ["operators/*.py", "policies/*.py"]
    payload["research_surfaces"] = [
        {
            "name": "route_local",
            "kind": "operator",
            "description": "Route-local generated operators.",
            "targets": {"files": ["operators/*.py"]},
        },
        {
            "name": "algorithm_blueprint",
            "kind": "config",
            "description": "Top-level algorithm plan.",
            "targets": {
                "files": ["policies/algorithm_blueprint.py"],
                "create_new_allowed": False,
                "modify_allowed": True,
                "remove_allowed": False,
                "singleton": True,
            },
            "interface": {
                "required_functions": ["algorithm_plan"],
                "function_signatures": {
                    "algorithm_plan": ["instance", "time_limit_sec"]
                },
            },
        },
    ]
    spec_v1 = ProblemSpecV1(**payload)
    legacy = legacy_problem_spec_from_v1(spec_v1)
    (tmp_path / "policies").mkdir()
    (tmp_path / "policies" / "algorithm_blueprint.py").write_text(
        "def algorithm_plan(instance, time_limit_sec):\n"
        "    return {'enabled': False}\n",
        encoding="utf-8",
    )
    champion = ChampionState(
        version=1,
        operator_pool={},
        solver_config_hash="h",
        code_snapshot_path=str(tmp_path),
        code_snapshot_hash="h",
    )
    branch = Branch(
        branch_id="b1",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="h",
    )
    step_history = [
        StepRecord(
            round_num=index + 1,
            branch_id="b1",
            hypothesis=HypothesisProposal(
                hypothesis_text="Try another route-local move.",
                change_locus="route_local",
                action="create_new",
                target_file=f"operators/local_{index}.py",
            ),
            patch=None,
            contract_passed=False,
            verification_passed=False,
            protocol_result=None,
            decision=None,
            failure_stage="hypothesis_contract",
            failure_detail="duplicate or weak route-local proposal",
        )
        for index in range(3)
    ]

    ctx = ContextManager().build_hypothesis_context(
        branch=branch,
        champion=champion,
        problem_spec=legacy,
        active_hypotheses=[],
        blacklist=[],
        step_history=step_history,
        forced_locus="algorithm_blueprint",
        forced_surface_diagnostic=True,
    )
    system_blocks, user_prompt = _split_hypothesis_context(ctx)
    prompt_text = "\n".join(block["text"] for block in system_blocks) + user_prompt

    assert ctx["forced_surface"] == "algorithm_blueprint"
    assert ctx["forced_action"] == "modify"
    assert "Set `change_locus` to `algorithm_blueprint`." in prompt_text
    assert "Set `action` to `modify`." in prompt_text
    assert (
        "Set `change_locus` exactly to `algorithm_blueprint`."
        in user_prompt
    )
    assert "Set `action` exactly to `modify`." in user_prompt
    assert "Choose a research surface from" not in user_prompt
    assert "Do not choose any other research surface" in user_prompt
    assert "Unexplored research surfaces" not in prompt_text
    assert "Consider trying action='modify'" not in prompt_text
    assert "Consider trying action='create_new'" not in prompt_text
    assert "Forced-surface diagnostic is active" in prompt_text


def test_forced_surface_context_rejects_unknown_surface(tmp_path: Path) -> None:
    payload = _problem_payload(str(tmp_path))
    payload["research_surfaces"] = [
        {
            "name": "dispatch_policy",
            "kind": "policy",
            "description": "Dispatch policy.",
            "target_files": ["policies/dispatch_policy.py"],
        },
    ]
    spec_v1 = ProblemSpecV1(**payload)
    legacy = legacy_problem_spec_from_v1(spec_v1)
    champion = ChampionState(
        version=1,
        operator_pool={},
        solver_config_hash="h",
        code_snapshot_path=str(tmp_path),
        code_snapshot_hash="h",
    )
    branch = Branch(
        branch_id="b1",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="h",
    )

    with pytest.raises(ValueError, match="unknown research surface 'missing'"):
        ContextManager().build_hypothesis_context(
            branch=branch,
            champion=champion,
            problem_spec=legacy,
            active_hypotheses=[],
            blacklist=[],
            forced_locus="missing",
        )


def test_validation_and_frozen_raw_metric_refs_stay_out_of_context(
    tmp_path: Path,
) -> None:
    payload = _problem_payload(str(tmp_path))
    payload["research_surfaces"] = [
        {
            "name": "local",
            "kind": "operator",
            "description": "Local surface",
            "target_files": ["operators/*.py"],
        },
    ]
    spec_v1 = ProblemSpecV1(**payload)
    legacy = legacy_problem_spec_from_v1(spec_v1)
    (tmp_path / "operators").mkdir()
    (tmp_path / "operators" / "old.py").write_text(
        "class Old:\n    pass\n",
        encoding="utf-8",
    )
    champion = ChampionState(
        version=1,
        operator_pool={},
        solver_config_hash="h",
        code_snapshot_path=str(tmp_path),
        code_snapshot_hash="h",
    )
    branch = Branch(
        branch_id="b1",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="h",
    )
    screening_hypothesis = HypothesisProposal(
        hypothesis_text="Bounded local move.",
        change_locus="local",
        action="modify",
        target_file="operators/old.py",
    )
    validation_hypothesis = HypothesisProposal(
        hypothesis_text="VALIDATION_ONLY_HYPOTHESIS_TEXT",
        change_locus="validation_only_locus",
        action="modify",
        target_file="operators/validation_only.py",
    )
    frozen_hypothesis = HypothesisProposal(
        hypothesis_text="FROZEN_ONLY_HYPOTHESIS_TEXT",
        change_locus="frozen_only_locus",
        action="modify",
        target_file="operators/frozen_only.py",
    )
    screening_stats = EvalStats(
        n_cases=6,
        wins=5,
        losses=1,
        ties=0,
        win_rate=0.83,
        median_delta=0.1234,
        ci_low=0.01,
        ci_high=0.20,
    )
    holdout_stats = EvalStats(
        n_cases=17,
        wins=7,
        losses=10,
        ties=0,
        win_rate=0.42,
        median_delta=0.4242,
        ci_low=-0.42,
        ci_high=0.43,
    )
    frozen_stats = EvalStats(
        n_cases=19,
        wins=18,
        losses=1,
        ties=0,
        win_rate=0.95,
        median_delta=9.1919,
        ci_low=0.91,
        ci_high=0.99,
    )
    holdout_case_feedback = (
        CaseAggregateFeedback(
            case_id="holdout-case-feedback-secret",
            n_pairs=3,
            wins=1,
            losses=2,
            ties=0,
            win_rate=0.33,
            dominant_result="loss",
            decisive_metric="holdout_secret_metric",
            median_deltas={"holdout_secret_metric": -123.0},
            seed_consistency=1.0,
            case_features={"path_stem": "holdout-secret-stem"},
        ),
    )
    step_history = [
        StepRecord(
            round_num=1,
            branch_id="b1",
            hypothesis=screening_hypothesis,
            patch=None,
            contract_passed=True,
            verification_passed=True,
            protocol_result=ProtocolResult(
                stage=ExperimentStage.SCREENING,
                stats=screening_stats,
                gate_outcome="expand",
                reason_codes=("screening_expand",),
                exposed_summary="screening summary may be copied",
                raw_metrics_ref="/tmp/screening-metrics.json",
            ),
            decision=Decision.EXPAND_SCREENING,
            failure_stage=None,
            failure_detail=None,
        ),
        StepRecord(
            round_num=2,
            branch_id="b1",
            hypothesis=validation_hypothesis,
            patch=None,
            contract_passed=True,
            verification_passed=True,
            protocol_result=ProtocolResult(
                stage=ExperimentStage.VALIDATION,
                stats=holdout_stats,
                gate_outcome="pass",
                reason_codes=("validation_positive",),
                exposed_summary="validation secret should not be copied",
                raw_metrics_ref="/tmp/private-validation-metrics.json",
                case_ids=("validation-secret-case",),
                seed_set=(11,),
                case_feedback=holdout_case_feedback,
            ),
            decision=Decision.QUEUE_FROZEN,
            failure_stage=None,
            failure_detail=None,
        ),
        StepRecord(
            round_num=3,
            branch_id="b1",
            hypothesis=frozen_hypothesis,
            patch=None,
            contract_passed=True,
            verification_passed=True,
            protocol_result=ProtocolResult(
                stage=ExperimentStage.FROZEN,
                stats=frozen_stats,
                gate_outcome="fail",
                reason_codes=("frozen_positive",),
                exposed_summary="frozen secret should not be copied",
                raw_metrics_ref="/tmp/private-frozen-metrics.json",
                case_ids=("frozen-secret-case",),
                seed_set=(13,),
                case_feedback=holdout_case_feedback,
            ),
            decision=Decision.ABANDON,
            failure_stage=None,
            failure_detail=None,
        ),
        StepRecord(
            round_num=4,
            branch_id="b1",
            hypothesis=frozen_hypothesis,
            patch=None,
            contract_passed=True,
            verification_passed=True,
            protocol_result=ProtocolResult(
                stage=ExperimentStage.FROZEN,
                stats=frozen_stats,
                gate_outcome="pass",
                reason_codes=("frozen_positive_promote",),
                exposed_summary="frozen promote secret should not be copied",
                raw_metrics_ref="/tmp/private-frozen-promote-metrics.json",
                case_ids=("frozen-promote-secret-case",),
                seed_set=(17,),
                case_feedback=holdout_case_feedback,
            ),
            decision=Decision.PROMOTE,
            failure_stage=None,
            failure_detail=None,
        ),
    ]

    ctx = ContextManager().build_hypothesis_context(
        branch=branch,
        champion=champion,
        problem_spec=legacy,
        active_hypotheses=[],
        blacklist=[],
        step_history=step_history,
    )
    system_blocks, user_prompt = _split_hypothesis_context(ctx)
    prompt_text = "\n".join(block["text"] for block in system_blocks) + user_prompt

    assert "private-validation-metrics" not in prompt_text
    assert "private-frozen-metrics" not in prompt_text
    assert "private-frozen-promote-metrics" not in prompt_text
    assert "raw_metrics_ref" not in prompt_text
    assert "validation-secret-case" not in prompt_text
    assert "frozen-secret-case" not in prompt_text
    assert "frozen-promote-secret-case" not in prompt_text
    assert "secret should not be copied" not in prompt_text
    assert "VALIDATION_ONLY_HYPOTHESIS_TEXT" not in prompt_text
    assert "FROZEN_ONLY_HYPOTHESIS_TEXT" not in prompt_text
    assert "validation_only_locus" not in prompt_text
    assert "frozen_only_locus" not in prompt_text
    assert "holdout-case-feedback-secret" not in prompt_text
    assert "holdout_secret_metric" not in prompt_text
    assert "holdout-secret-stem" not in prompt_text
    assert "QUEUE_FROZEN" not in prompt_text
    assert "PROMOTE" not in prompt_text
    assert "ABANDON" not in prompt_text
    assert "promoted=" not in prompt_text
    assert "failed_validation" not in prompt_text
    assert "failed_frozen" not in prompt_text
    assert "screening: case_win_rate=0.83" in prompt_text
    assert "median_delta=0.1234" in prompt_text
    assert "outcome=expand" in prompt_text
    assert "screening_expand=1" in prompt_text
    assert "n=1" in prompt_text
    assert "case_win_rate=0.42" not in prompt_text
    assert "median_delta=0.4242" not in prompt_text
    assert "case_win_rate=0.95" not in prompt_text
    assert "median_delta=9.1919" not in prompt_text
    assert "n=17" not in prompt_text
    assert "n=19" not in prompt_text
    assert "outcome=pass" not in prompt_text
    assert "outcome=fail" not in prompt_text
