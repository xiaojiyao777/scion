"""Focused tests split from test_agentic_proposal_tools_schema.py."""

from .agentic_schema_test_support import *  # noqa: F401,F403
from scion.proposal.schemas import HypothesisProposalInput

def test_old_style_patch_json_is_accepted_without_transport_premise_check() -> None:
    raw = {
        "file_path": "policies/search_policy.py",
        "action": "modify",
        "code_content": "def choose():\n    return 1\n",
    }

    parsed = PatchProposalInput.model_validate(raw)

    assert "premise_check" not in PATCH_PROPOSAL_SCHEMA.get("required", [])
    assert parsed.premise_check == "supported"
    assert parsed.file_path == raw["file_path"]


def test_hypothesis_normalizes_overlong_novelty_signature_scalar() -> None:
    payload = _valid_hypothesis_payload(
        novelty_signature={"improvement_strategy": "x" * 180}
    )

    parsed = HypothesisProposalInput.model_validate(payload)

    assert len(parsed.novelty_signature["improvement_strategy"]) == 120


def test_cvrp_active_solver_design_boundary_filters_and_rejects_components(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = replace(
        _cvrp_context(tmp_path),
        active_problem_boundary_surfaces=("solver_design",),
    )

    listed = registry.call("context.list_surfaces", {}, context)
    payload = listed.structured_payload
    assert [surface["name"] for surface in payload["surfaces"]] == ["solver_design"]
    assert payload["total_declared_surface_count"] == payload["surface_count"] == 1
    assert payload["active_problem_boundary_constraint"]["surfaces"] == [
        "solver_design"
    ]

    rejected = registry.call(
        "proposal.target_permission_preview",
        {
            "change_locus": "baseline_policy",
            "action": "modify",
            "target_file": "policies/baseline_policy.py",
        },
        context,
    )
    assert rejected.structured_payload["passed"] is False
    assert "active_problem_boundary_constraint" in " ".join(
        rejected.structured_payload["issues"]
    )

    accepted = registry.call(
        "proposal.target_permission_preview",
        {
            "change_locus": "solver_design",
            "action": "modify",
            "target_file": "policies/baseline_algorithm.py",
        },
        context,
    )
    assert accepted.structured_payload["passed"] is True

    accepted_module = registry.call(
        "proposal.target_permission_preview",
        {
            "change_locus": "solver_design",
            "action": "create_new",
            "target_file": "policies/baseline_modules/construction_variant.py",
        },
        context,
    )
    assert accepted_module.structured_payload["passed"] is True


def test_cvrp_active_boundary_exposes_solver_design_novelty_requirements(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = replace(
        _cvrp_context(tmp_path),
        active_problem_boundary_surfaces=("solver_design",),
    )

    listed = registry.call("context.list_surfaces", {}, context)
    constraint = listed.structured_payload["active_problem_boundary_constraint"]
    requirements = constraint["novelty_signature_requirements"]["solver_design"]

    assert requirements["strategy"] == "semantic_signature"
    assert "algorithm_family" in requirements["required_fields"]
    assert "runtime_budget_strategy" in requirements["required_fields"]
    assert "nonempty_sequence_fields" not in requirements


def test_context_read_surface_exposes_solver_design_mechanism_telemetry(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = replace(
        _cvrp_context(tmp_path),
        active_problem_boundary_surfaces=("solver_design",),
    )

    observation = registry.call(
        "context.read_surface",
        {
            "surface": "solver_design",
            "section": "evidence",
            "include_code": False,
        },
        context,
    )

    evidence = observation.structured_payload["surface"]["evidence"]
    assert evidence["activation_runtime_fields"] == {
        "{mechanism}": [
            "solver_algorithm_context_records.{mechanism}_iterations",
            "solver_algorithm_phase_runtime_ms.{mechanism}",
        ]
    }
    assert evidence["effect_probe_runtime_fields"] == [
        "solver_algorithm_phase_improvement_counts.{mechanism}",
        "solver_algorithm_phase_best_delta.{mechanism}",
    ]


def test_context_read_surface_rejects_legacy_surface_under_active_boundary(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = replace(
        _cvrp_context(tmp_path),
        active_problem_boundary_surfaces=("solver_design",),
    )

    observation = registry.call(
        "context.read_surface",
        {
            "surface": "baseline_policy",
            "section": "all",
            "include_code": False,
        },
        context,
    )

    assert observation.is_error is True
    assert observation.failure_code == ProposalToolFailureCode.NOT_FOUND
    assert observation.structured_payload["requested_surface"] == "baseline_policy"
    assert observation.structured_payload["available_surfaces"] == ["solver_design"]
    assert "Research surface not found" in observation.summary


def test_cvrp_solver_design_schema_preview_rejects_empty_deep_identity(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = replace(
        _cvrp_context(tmp_path),
        active_problem_boundary_surfaces=("solver_design",),
    )
    hypothesis = _valid_hypothesis_payload(
        change_locus="solver_design",
        target_file="policies/baseline_algorithm.py",
    )
    hypothesis["novelty_signature"]["algorithm_family"] = []

    preview = registry.call(
        "proposal.schema_preview",
        {"hypothesis": hypothesis},
        context,
    )

    guidance = preview.structured_payload["hypothesis"]["novelty_signature_guidance"]
    assert preview.structured_payload["passed"] is False
    assert "algorithm_family" in preview.summary
    assert guidance["missing_fields"] == ["algorithm_family"]
    assert "nonempty_sequence_fields" not in guidance


def test_cvrp_solver_design_schema_preview_rejects_false_deep_identity(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = replace(
        _cvrp_context(tmp_path),
        active_problem_boundary_surfaces=("solver_design",),
    )
    hypothesis = _valid_hypothesis_payload(
        change_locus="solver_design",
        target_file="policies/baseline_algorithm.py",
    )
    hypothesis["novelty_signature"]["algorithm_family"] = False

    preview = registry.call(
        "proposal.schema_preview",
        {"hypothesis": hypothesis},
        context,
    )

    guidance = preview.structured_payload["hypothesis"]["novelty_signature_guidance"]
    assert preview.structured_payload["passed"] is False
    assert guidance["missing_fields"] == ["algorithm_family"]


def test_schema_preview_invalid_expected_telemetry_category_is_hard_feedback(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(tmp_path, policy=_tool_enabled_policy())
    hypothesis = _valid_hypothesis_payload(
        expected_telemetry={"attribution": ["policy_loaded"]},
    )

    preview = registry.call(
        "proposal.schema_preview",
        {"hypothesis": hypothesis},
        context,
    )
    self_check = _self_check_from_previews([preview])
    telemetry = preview.structured_payload["hypothesis"][
        "expected_telemetry_contract"
    ]

    assert preview.structured_payload["passed"] is False
    assert self_check.schema_valid is False
    assert telemetry["invalid_categories"] == ["attribution"]
    assert "activity" in telemetry["allowed_categories"]
    assert "policy_loaded" in telemetry["declared_runtime_fields"]
    assert any(
        "C11_expected_telemetry" in code
        for code in self_check.schema_preview_codes
    )


def test_hypothesis_schema_teaches_expected_telemetry_categories() -> None:
    description = HYPOTHESIS_PROPOSAL_SCHEMA["properties"]["expected_telemetry"][
        "description"
    ]
    tool_description = HYPOTHESIS_TOOL["description"]

    for category in ("activity", "activation", "effect", "budget"):
        assert category in description
        assert category in tool_description
    for bad_category in (
        "best_delta",
        "improvement_counts",
        "phase_runtime",
        "runtime_ms",
    ):
        assert bad_category in description
        assert bad_category in tool_description
    assert "top-level categories" in description
    assert "not put explanatory prose" in description
    assert "top-level expected_telemetry keys" in tool_description.lower()
    assert (
        "solver_algorithm_context_records.<mechanism_id>_iterations" in description
    )
    assert "solver_algorithm_phase_runtime_ms.<mechanism_id>" in description
    assert "solver_algorithm_improving_moves" in description
    assert "solver_algorithm_best_improving_moves" in description
    assert "effect or activity, not activation" in description
    assert ".vns" in description
    assert (
        "solver_algorithm_context_records.<mechanism_id>_iterations"
        in tool_description
    )
    assert "solver_algorithm_phase_runtime_ms.<mechanism_id>" in tool_description
    assert ".vns" in tool_description


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


def test_draft_and_preview_report_missing_semantic_novelty_signature(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(tmp_path, policy=_tool_enabled_policy())
    missing_signature = _valid_hypothesis_payload(novelty_signature={})

    draft = registry.call(
        "proposal.draft_hypothesis",
        missing_signature,
        context,
    )
    preview = registry.call(
        "proposal.contract_preview",
        {"hypothesis": missing_signature},
        context,
    )

    assert draft.is_error is True
    assert draft.failure_code == ProposalToolFailureCode.SCHEMA_ERROR
    assert "missing structured novelty_signature identity" in (
        draft.structured_payload["failure_reason"]
    )
    guidance = draft.structured_payload["novelty_signature_guidance"]
    assert guidance["missing_fields"] == [
        "budget_pattern",
        "round_limit_pattern",
    ]
    assert preview.is_error is False
    assert preview.structured_payload["passed"] is False
    assert preview.structured_payload["hypothesis"]["novelty_signature_guidance"][
        "missing_fields"
    ] == ["budget_pattern", "round_limit_pattern"]


def test_forced_surface_constraint_rejects_off_surface_draft_and_previews(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = replace(
        _context(tmp_path, policy=_tool_enabled_policy()),
        forced_surface="search_policy",
        forced_action="modify",
        forced_target_file="policies/search_policy.py",
    )
    off_surface = _valid_hypothesis_payload(
        change_locus="route_local",
        action="create_new",
        target_file="operators/local_new.py",
        novelty_signature={},
    )

    listed = registry.call("context.list_surfaces", {}, context)
    draft = registry.call("proposal.draft_hypothesis", off_surface, context)
    schema = registry.call(
        "proposal.schema_preview",
        {"hypothesis": off_surface},
        context,
    )
    target = registry.call(
        "proposal.target_permission_preview",
        {
            "change_locus": "route_local",
            "action": "create_new",
            "target_file": "operators/local_new.py",
        },
        context,
    )

    assert listed.structured_payload["forced_surface_constraint"]["surface"] == (
        "search_policy"
    )
    assert draft.is_error is True
    assert draft.failure_code == ProposalToolFailureCode.SCHEMA_ERROR
    assert "forced_surface_constraint" in draft.structured_payload["failure_reason"]
    assert schema.is_error is False
    assert schema.structured_payload["passed"] is False
    assert "forced_surface_constraint" in (
        schema.structured_payload["hypothesis"]["failure_reason"]
    )
    assert target.is_error is False
    assert target.structured_payload["passed"] is False
    assert any(
        "forced_surface_constraint" in issue
        for issue in target.structured_payload["issues"]
    )
