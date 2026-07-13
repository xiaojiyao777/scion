from __future__ import annotations

from collections import Counter

from scion.core.models import Branch, BranchState, ChampionState, HypothesisProposal
from scion.problem.bridge import legacy_problem_spec_from_v1, load_problem_spec_v1_from_yaml
from scion.problems.cvrp.adapter import CvrpAdapter
from scion.problems.cvrp.solver_design.manifest import SOLVER_DESIGN_API_MANIFEST_FILES
from scion.proposal.context_manager import ContextManager
from scion.proposal.engine import _split_code_context, _split_hypothesis_context
from scion.tests.unit.research_surface_helpers import _CVRP_ROOT


def _active_solver_source_paths() -> tuple[str, ...]:
    module_dir = _CVRP_ROOT / "policies" / "baseline_modules"
    paths = [
        _CVRP_ROOT / "policies" / "baseline_algorithm.py",
        *(
            path
            for path in module_dir.glob("*.py")
            if path.name != "__init__.py"
        ),
    ]
    return tuple(
        path.relative_to(_CVRP_ROOT).as_posix()
        for path in sorted(paths)
    )


def _runtime():
    spec = load_problem_spec_v1_from_yaml(_CVRP_ROOT / "problem-v1.yaml")
    legacy = legacy_problem_spec_from_v1(spec)
    champion = ChampionState(
        version=1,
        operator_pool={},
        solver_config_hash="h",
        code_snapshot_path=str(_CVRP_ROOT),
        code_snapshot_hash="h",
    )
    branch = Branch(
        branch_id="direct-cvrp-guidance",
        state=BranchState.EXPLORE,
        base_champion_id=1,
        base_champion_hash="h",
    )
    return spec, legacy, champion, branch


def test_direct_cvrp_declared_sources_have_one_full_source_owner() -> None:
    spec, legacy, champion, branch = _runtime()
    target = "policies/baseline_modules/local_search.py"
    hypothesis = HypothesisProposal(
        hypothesis_text="Improve the local-search mechanism.",
        change_locus="solver_design",
        action="modify",
        target_file=target,
    )

    context = ContextManager(adapter=CvrpAdapter(spec)).build_code_context(
        branch,
        hypothesis,
        champion,
        legacy,
    )
    ledger = context["proposal_source_ledger"]
    entries = ledger["entries"]
    owned_paths = [entry["path"] for entry in entries]
    active_paths = _active_solver_source_paths()

    assert ledger["schema_version"] == "proposal-source-ledger.v2"
    assert ledger["approved_target"] == target
    assert set(owned_paths) == set(active_paths)
    assert Counter(owned_paths) == Counter(
        {path: 1 for path in active_paths}
    )
    assert set(SOLVER_DESIGN_API_MANIFEST_FILES).issubset(owned_paths)
    assert set(active_paths).issubset(ledger["views"]["api_reference"])
    assert [entry["owner"] for entry in entries].count("approved_target") == 1
    assert all(entry["content"] for entry in entries)
    assert all(entry["digest"] for entry in entries)
    system_blocks, user_prompt = _split_code_context(context)
    rendered = "\n".join(block["text"] for block in system_blocks) + user_prompt
    for path in active_paths:
        assert rendered.count(f'"path": "{path}"') == 1


def test_direct_cvrp_hypothesis_context_is_open_algorithm_guidance() -> None:
    spec, legacy, champion, branch = _runtime()

    context = ContextManager(adapter=CvrpAdapter(spec)).build_hypothesis_context(
        branch=branch,
        champion=champion,
        problem_spec=legacy,
    )
    system_blocks, user_prompt = _split_hypothesis_context(context)
    rendered = "\n".join(block["text"] for block in system_blocks) + user_prompt

    assert [surface["name"] for surface in context["research_surfaces"]] == [
        "solver_design"
    ]
    assert "No prepared file or mechanism is mandatory" in rendered
    assert "Runtime errors may explain failed outcomes" in rendered
    assert context["research_question"]["schema_version"] == (
        "scion.typed_research_question.v1"
    )
    assert "policies/baseline_algorithm.py" in context["targetable_files"]
    assert "policies/baseline_modules/*.py" in context["targetable_files"]
    for path in _active_solver_source_paths():
        assert path in context["targetable_files"]
        assert context["champion_operators_code"].count(
            f"### {path} (research surface)"
        ) == 1
    assert "target_intent" not in rendered
    assert "read_active_solver_map" not in rendered


def test_direct_cvrp_code_context_renders_source_and_object_model() -> None:
    spec, legacy, champion, branch = _runtime()
    hypothesis = HypothesisProposal(
        hypothesis_text="Test a new route-state local-search path.",
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/local_search.py",
        predicted_direction="improve",
    )

    context = ContextManager(adapter=CvrpAdapter(spec)).build_code_context(
        branch,
        hypothesis,
        champion,
        legacy,
    )
    system_blocks, user_prompt = _split_code_context(context)
    rendered = "\n".join(block["text"] for block in system_blocks) + user_prompt

    assert "solver_design_prompt_guidance" in context["proposal_renderer_inputs"]
    assert '"active_subject_code_constraints"' in rendered
    assert "source ledger" in rendered
    assert "_Solution.routes" in rendered
    assert "_Route" in rendered
    instrumentation_guidance = "\n".join(
        (
            str(context["operator_interface_spec"]),
            str(context["active_subject_code_constraints"]),
            str(context["proposal_renderer_inputs"]),
            str(context["research_surface"]),
        )
    )
    assert "record_move" not in instrumentation_guidance
    assert "record_phase" not in instrumentation_guidance
    assert "record_iteration" not in instrumentation_guidance
    assert "telemetry_identity_allowlist" not in instrumentation_guidance
    assert "target_intent" not in rendered
    assert "agentic_code_scope_control" not in rendered


def test_direct_cvrp_context_keeps_only_active_solver_surface() -> None:
    spec, legacy, champion, branch = _runtime()
    hypothesis = HypothesisProposal(
        hypothesis_text="Change the destroy and repair state transition.",
        change_locus="solver_design",
        action="modify",
        target_file="policies/baseline_modules/destroy_repair.py",
    )

    context = ContextManager(adapter=CvrpAdapter(spec)).build_code_context(
        branch,
        hypothesis,
        champion,
        legacy,
    )
    rendered = "\n".join(str(value) for value in context.values())

    assert context["research_surface"]["name"] == "solver_design"
    assert context["research_surface"]["kind"] == "solver_design"
    assert "policies/baseline_modules/destroy_repair.py" in rendered
    assert "policies/search_policy.py" not in context["editable_patterns"]
    assert "policies/solver_algorithm.py" not in context["editable_patterns"]
