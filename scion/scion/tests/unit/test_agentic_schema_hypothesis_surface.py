"""Focused tests split from test_agentic_proposal_tools_schema.py."""

from .agentic_schema_test_support import *  # noqa: F401,F403
from scion.problem.spec import ProblemSpecV1
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


def test_schema_preview_blocks_launch_focus_default_avoid_acceptance_family(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = replace(
        _cvrp_context(tmp_path),
        active_problem_boundary_surfaces=("solver_design",),
        launch_research_focus={
            "schema_version": "scion.launch_research_focus_prompt.v1",
            "proposal_visibility_only": True,
            "decision_features_excluded": True,
            "research_focus": {
                "default_avoid_directions": [
                    "route-limit seed diversification",
                    "simple initial-VNS disablement",
                    (
                        "route-pressure acceptance/adaptive-weighting variants "
                        "without a new non-acceptance causal path or direct "
                        "objective-effect telemetry"
                    ),
                ],
                "required_evidence": [
                    (
                        "a new non-acceptance causal path before revisiting "
                        "route-pressure acceptance"
                    ),
                ],
            },
        },
    )
    hypothesis = _valid_hypothesis_payload(
        change_locus="solver_design",
        target_file="policies/baseline_modules/acceptance.py",
        hypothesis_text=(
            "Modify the simulated annealing rule with a distance-scaled "
            "stagnation reheating floor after route-limit seed experiments "
            "failed."
        ),
        expected_effect="Improve large-case acceptance of uphill route moves.",
        mechanism_changes=[
            {"id": "distance_scaled_sa_reheat", "change_type": "modify"},
        ],
    )

    preview = registry.call(
        "proposal.schema_preview",
        {"hypothesis": hypothesis},
        context,
    )

    section = preview.structured_payload["hypothesis"]
    guard = section["launch_research_focus_default_avoid_guard"]
    assert preview.structured_payload["passed"] is False
    assert section["passed"] is False
    assert guard["passed"] is False
    assert guard["failure_code"] == "launch_research_focus_default_avoid"
    assert "acceptance" in guard["matched_terms"]
    assert guard["matched_default_avoid_direction"].startswith("route-pressure")
    assert "launch_research_focus_default_avoid" in section["failure_reason"]
    assert guard["proposal_visibility_only"] is True
    assert guard["decision_features_excluded"] is True


def test_schema_preview_blocks_launch_focus_default_avoid_local_search_mechanism(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = replace(
        _cvrp_context(tmp_path),
        active_problem_boundary_surfaces=("solver_design",),
        launch_research_focus={
            "research_focus": {
                "default_avoid_directions": [
                    "unchanged bounded_interroute_2opt_bridge local-search bridge",
                    "unchanged cmt_slack_aware_segment_swap local-search segment swap",
                ],
            },
        },
    )
    hypothesis = _valid_hypothesis_payload(
        change_locus="solver_design",
        target_file="policies/baseline_modules/local_search.py",
        hypothesis_text=(
            "Repeat the bounded inter-route bridge after the previous run."
        ),
        expected_effect="Improve total distance with the same bridge operator.",
        mechanism_changes=[
            {"id": "bounded_interroute_2opt_bridge", "change_type": "modify"},
        ],
        novelty_signature={
            "algorithm_family": "bounded_local_search",
            "construction_strategy": "unchanged_seed_pool",
            "improvement_strategy": "bounded_interroute_2opt_bridge",
            "acceptance_strategy": "strict_improvement_only",
            "runtime_budget_strategy": "bounded_pair_pool",
        },
    )

    preview = registry.call(
        "proposal.schema_preview",
        {"hypothesis": hypothesis},
        context,
    )

    section = preview.structured_payload["hypothesis"]
    guard = section["launch_research_focus_default_avoid_guard"]
    assert preview.structured_payload["passed"] is False
    assert section["passed"] is False
    assert guard["passed"] is False
    assert guard["failure_code"] == "launch_research_focus_default_avoid"
    assert guard["matched_default_avoid_direction"].startswith(
        "unchanged bounded_interroute_2opt_bridge"
    )
    assert {"bounded", "interroute", "bridge"} <= set(guard["matched_terms"])
    assert guard["candidate_mechanism_ids"] == ["bounded_interroute_2opt_bridge"]


def test_schema_preview_allows_nonmatching_launch_focus_default_avoid(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = replace(
        _cvrp_context(tmp_path),
        active_problem_boundary_surfaces=("solver_design",),
        launch_research_focus={
            "research_focus": {
                "default_avoid_directions": [
                    (
                        "route-pressure acceptance/adaptive-weighting variants "
                        "without a new non-acceptance causal path or direct "
                        "objective-effect telemetry"
                    ),
                ],
            },
        },
    )
    hypothesis = _valid_hypothesis_payload(
        change_locus="solver_design",
        target_file="policies/baseline_modules/local_search.py",
        hypothesis_text=(
            "Add a bounded two-opt probe for selected high-slack customer pairs."
        ),
        expected_effect="Improve total distance by testing bounded route edits.",
        mechanism_changes=[
            {"id": "bounded_two_opt_probe", "change_type": "modify"},
        ],
        novelty_signature={
            "algorithm_family": "bounded_local_search",
            "construction_strategy": "unchanged_seed_pool",
            "improvement_strategy": "bounded_two_opt_probe",
            "acceptance_strategy": "strict_improvement_only",
            "runtime_budget_strategy": "small_candidate_pool",
        },
    )

    preview = registry.call(
        "proposal.schema_preview",
        {"hypothesis": hypothesis},
        context,
    )

    guard = preview.structured_payload["hypothesis"][
        "launch_research_focus_default_avoid_guard"
    ]
    assert guard["passed"] is True
    assert guard["configured"] is True


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
    template = guidance["repair_template"]
    rendered_template = json.dumps(template, sort_keys=True)

    assert preview.structured_payload["passed"] is False
    assert "algorithm_family" in preview.summary
    assert guidance["missing_fields"] == ["algorithm_family"]
    assert template["repair_type"] == "novelty_signature_missing_fields"
    assert template["check"] == "C10_novelty"
    assert template["missing_fields"] == ["algorithm_family"]
    assert template["required_template"]["novelty_signature"]["mechanism_id"]
    assert "active solver map" in " ".join(template["agent_instruction"])
    assert "validation" not in rendered_template.lower()
    assert "frozen" not in rendered_template.lower()
    assert "raw_metrics" not in rendered_template.lower()
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


def test_schema_preview_c11_renders_exact_allowed_telemetry_template(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _context(tmp_path, policy=_tool_enabled_policy())
    spec_payload = context.problem_spec.model_dump()
    search_policy = dict(spec_payload["research_surfaces"][1])
    evidence = dict(search_policy.get("evidence") or {})
    evidence["runtime_field_roles"] = {
        "mechanism_activation": [
            f"policy_activation_{idx}.{{mechanism}}" for idx in range(7)
        ],
        "mechanism_effect": [
            f"policy_effect_{idx}.{{mechanism}}" for idx in range(6)
        ],
        "budget": [
            f"policy_budget_{idx}.{{mechanism}}" for idx in range(5)
        ],
        "activity": ["policy_loaded"],
    }
    search_policy["evidence"] = evidence
    spec_payload["research_surfaces"][1] = search_policy
    context = replace(
        context,
        problem_spec=ProblemSpecV1(**spec_payload),
        adapter=None,
    )
    hypothesis = _valid_hypothesis_payload(
        mechanism_changes=[{"id": "budget_probe", "change_type": "modify"}],
        expected_telemetry={"activation": ["policy_activation_0.aggregate"]},
    )

    preview = registry.call(
        "proposal.schema_preview",
        {"hypothesis": hypothesis},
        context,
    )

    telemetry = preview.structured_payload["hypothesis"][
        "expected_telemetry_contract"
    ]
    template = telemetry["allowed_expected_telemetry_template"]

    assert preview.structured_payload["passed"] is False
    assert telemetry["exact_allowed_top_level_categories"] == [
        "activation",
        "activity",
        "budget",
        "effect",
    ]
    assert telemetry["declared_mechanism_ids"] == ["budget_probe"]
    assert telemetry["template_mechanism_ids"] == ["budget_probe"]
    assert template["template_truncated"] is False
    assert template["mechanism_ids"] == ["budget_probe"]
    assert template["expected_telemetry"]["activation"] == [
        f"policy_activation_{idx}.budget_probe" for idx in range(7)
    ]
    assert template["expected_telemetry"]["effect"] == [
        f"policy_effect_{idx}.budget_probe" for idx in range(6)
    ]
    assert template["expected_telemetry"]["budget"] == [
        f"policy_budget_{idx}.budget_probe" for idx in range(5)
    ]


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
    assert "mechanism-specific activity evidence" in description
    assert "objective/outcome fields" in description
    assert "Aggregate outcome or activity fields" in description
    assert "effect or activity, not activation" in description
    assert "mechanism-specific path containing the declared mechanism id" in description
    assert "broad aggregate phase" in description
    assert "existing phase or component" in description
    assert "mechanism-specific activity evidence" in tool_description
    assert "broad aggregate phase" in tool_description
    assert "existing phase or component" in tool_description


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
