from __future__ import annotations

from scion.proposal.schemas import (
    HYPOTHESIS_PROPOSAL_SCHEMA,
    HYPOTHESIS_TOOL,
    PATCH_PROPOSAL_SCHEMA,
    PatchProposalInput,
)
from scion.tests.unit.test_agentic_proposal_tools_helpers import (
    AgenticProposalSession,
    AgenticProposalSessionState,
    AgenticToolLoopConfig,
    ContextExposurePolicy,
    FakeCreative,
    Path,
    ProposalObservation,
    ProposalToolFailureCode,
    ProposalToolRegistry,
    _CVRP_ROOT,
    _compact_contract_preview_observation,
    _context,
    _cvrp_context,
    _json_size,
    _observation_prompt_payload,
    _overlapping_surface_context,
    _self_check_from_previews,
    _tool_enabled_policy,
    _valid_hypothesis_payload,
    _valid_policy_patch_payload,
    json,
    replace,
)


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
    assert payload["total_declared_surface_count"] > payload["surface_count"]
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
            "target_file": "policies/solver_algorithm.py",
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
    assert observation.failure_code == ProposalToolFailureCode.PERMISSION_DENIED
    assert observation.structured_payload["surface_state"] == "inactive_legacy"
    assert observation.structured_payload["active_problem_boundary_surfaces"] == [
        "solver_design"
    ]
    assert "active_problem_boundary_constraint" in observation.summary


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
        target_file="policies/solver_algorithm.py",
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
        target_file="policies/solver_algorithm.py",
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
    assert "top-level expected_telemetry keys" in tool_description.lower()


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
    assert (
        observation.structured_payload["patch"]["file_path"]
        == "policies/search_policy.py"
    )
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


def test_schema_and_contract_previews_stay_compact_for_large_inputs(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _cvrp_context(tmp_path)
    hypothesis_payload = _valid_hypothesis_payload(
        change_locus="construction_policy",
        target_file="policies/construction_policy.py",
        target_objectives=["total_distance"],
        protected_objectives=["fleet_violation"],
        hypothesis_text="Large diagnostic hypothesis. " * 120,
        expected_effect="Improve construction seed quality. " * 120,
        runtime_budget_strategy="Use bounded construction evaluation. " * 120,
        novelty_signature={
            "construction_mode": "savings" * 80,
            "repair_budget": list(range(40)),
        },
    )
    patch_payload = {
        "file_path": "policies/construction_policy.py",
        "action": "modify",
        "code_content": (
            "def construction_mode(instance, time_limit_sec):\n"
            "    return 'savings'\n\n"
            "def construction_bias(instance, time_limit_sec):\n"
            "    return 0.5\n\n" + "\n".join(f"# filler {idx}" for idx in range(500))
        ),
    }

    schema = registry.call(
        "proposal.schema_preview",
        {"hypothesis": hypothesis_payload, "patch": patch_payload},
        context,
    )
    contract = registry.call(
        "proposal.contract_preview",
        {"hypothesis": hypothesis_payload, "patch": patch_payload},
        context,
    )
    rendered_schema = json.dumps(schema.structured_payload, sort_keys=True)
    rendered_contract = json.dumps(contract.structured_payload, sort_keys=True)

    assert schema.is_error is False
    assert contract.is_error is False
    assert len(rendered_schema) < 6000
    assert len(rendered_contract) < 12000
    assert "Large diagnostic hypothesis." not in rendered_schema
    assert "Large diagnostic hypothesis." not in rendered_contract
    assert "code_content" not in rendered_contract
    assert "# filler" not in rendered_contract


def test_contract_preview_uses_hypothesis_selected_surface_on_overlapping_targets(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _overlapping_surface_context(tmp_path)

    observation = registry.call(
        "proposal.contract_preview",
        {
            "hypothesis": _valid_hypothesis_payload(
                change_locus="budget_policy",
                target_file="shared/policy.py",
            ),
            "patch": {
                "file_path": "shared/policy.py",
                "action": "modify",
                "code_content": (
                    "class LooksLikeOperator:\n"
                    "    def execute(self, solution, rng):\n"
                    "        return solution\n"
                ),
            },
        },
        context,
    )

    checks = observation.structured_payload["patch"]["checks"]
    c7 = next(check for check in checks if check["name"] == "C7_interface")

    assert observation.is_error is False
    assert observation.structured_payload["passed"] is False
    assert c7["passed"] is False
    assert "policy surface" in c7["detail"]


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
            "code_content": (_CVRP_ROOT / "policies" / "search_policy.py").read_text(
                encoding="utf-8"
            ),
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


def test_cvrp_interface_preview_skips_problem_preview_after_contract_failure(
    tmp_path: Path,
) -> None:
    registry = ProposalToolRegistry.default_read_only()
    context = _cvrp_context(tmp_path)

    observation = registry.call(
        "proposal.interface_preview",
        {
            "file_path": "policies/search_policy.py",
            "action": "modify",
            "code_content": (
                "def baseline_time_fraction(instance, time_limit_sec):\n"
                "    return open('/definitely/not/present/scion_secret.json').read()\n\n"
                "def max_operator_rounds(instance, time_limit_sec):\n"
                "    return 20\n\n"
                "def enable_post_baseline_operators(instance, time_limit_sec):\n"
                "    return True\n"
            ),
        },
        context,
    )

    payload = observation.structured_payload
    rendered_checks = json.dumps(payload["checks"])
    assert payload["passed"] is False
    assert payload["problem_preview"] is None
    assert "C9_sensitive_api" in rendered_checks
    assert "open" in rendered_checks


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


def test_contract_preview_compacts_pass_fail_summary_when_full_payload_exceeds_budget() -> (
    None
):
    observation = ProposalObservation(
        observation_id="contract-preview-1",
        session_id="session-1",
        tool_name="proposal.contract_preview",
        tool_call_id="tool-9",
        observation_type="contract_preview",
        summary="Static contract preview passed.",
        structured_payload={
            "passed": True,
            "static_only": False,
            "workspace_materialized": False,
            "verification_run": False,
            "protocol_run": False,
            "decision_run": False,
            "hypothesis": {
                "passed": True,
                "hypothesis_text": "x" * 8000,
                "contract": {"passed": True, "check_count": 6},
                "checks": [{"name": "C2_locus", "passed": True}],
            },
            "patch": {
                "passed": True,
                "code_content": "x" * 24000,
                "contract": {"passed": True, "check_count": 10},
                "checks": [{"name": "C7_interface", "passed": True}],
                "problem_preview": {
                    "passed": True,
                    "surface": "solver_design",
                    "checks": [{"name": "preview", "passed": True}],
                    "workspace_materialized": False,
                },
            },
        },
    )

    compact = _compact_contract_preview_observation(observation)

    assert compact is not None
    assert compact.is_error is False
    assert _json_size(_observation_prompt_payload(compact)) < 1200
    assert compact.structured_payload["passed"] is True
    assert compact.structured_payload["patch"]["contract"]["check_count"] == 10
    assert compact.structured_payload["patch"]["problem_preview"]["passed"] is True
    assert compact.structured_payload["compact_due_to_budget"] is True
    assert _self_check_from_previews([compact]).contract_preview_passed is True


def test_agentic_session_keeps_minimal_contract_preview_at_budget_edge(
    tmp_path: Path,
) -> None:
    context = _context(tmp_path, policy=_tool_enabled_policy())
    config = AgenticToolLoopConfig(max_observation_chars=64000)
    state = AgenticProposalSessionState(
        session_id="session-contract-budget",
        campaign_id="camp-1",
        branch_id="branch-1",
        observation_chars_used=62200,
    )
    session = AgenticProposalSession(
        FakeCreative(),
        tool_registry=ProposalToolRegistry.default_read_only(),
        tool_loop_config=config,
    )
    observation = ProposalObservation(
        observation_id="contract-preview-edge",
        session_id=state.session_id,
        tool_name="proposal.contract_preview",
        tool_call_id="tool-10",
        observation_type="contract_preview",
        summary="Static contract preview found issues.",
        structured_payload={
            "passed": False,
            "hypothesis": {
                "passed": True,
                "hypothesis_text": "x" * 12000,
                "checks": [{"name": "C2_locus", "passed": True}],
            },
            "patch": {
                "passed": False,
                "code_content": "x" * 50000,
                "checks": [
                    {
                        "name": f"C{i}_large_failure",
                        "passed": False,
                        "detail": "x" * 1000,
                    }
                    for i in range(8)
                ],
            },
        },
    )

    compact = session._enforce_observation_budget(context, state, observation)

    assert compact.is_error is False
    assert compact.failure_code is None
    assert compact.structured_payload["passed"] is False
    assert (
        compact.structured_payload.get("minimal_due_to_budget") is True
        or compact.structured_payload.get("compact_due_to_budget") is True
    )
    assert _json_size(_observation_prompt_payload(compact)) <= (
        config.max_observation_chars - state.observation_chars_used
    )
    self_check = _self_check_from_previews([compact])
    assert self_check.contract_preview_passed is False
    assert any("C0_large_failure" in code for code in self_check.contract_preview_codes)


def test_contract_preview_failure_issues_become_self_check_codes() -> None:
    observation = ProposalObservation(
        observation_id="contract-preview-fail",
        session_id="session-1",
        tool_name="proposal.contract_preview",
        tool_call_id="tool-9",
        observation_type="contract_preview",
        summary="Static contract preview found issues: bad lifecycle field.",
        structured_payload={
            "passed": False,
            "static_only": False,
            "patch": {
                "passed": False,
                "problem_preview": {
                    "passed": False,
                    "issues": [
                        "algorithm_body.baseline_budget_policy returned unknown value 'legacy_floor'",
                    ],
                },
            },
        },
    )

    self_check = _self_check_from_previews([observation])
    compact = _compact_contract_preview_observation(observation)

    assert self_check.contract_preview_passed is False
    assert any(
        "baseline_budget_policy" in code for code in self_check.contract_preview_codes
    )
    assert compact is not None
    assert "baseline_budget_policy" in json.dumps(compact.structured_payload)


def test_contract_preview_hypothesis_c11_failure_marks_schema_invalid() -> None:
    observation = ProposalObservation(
        observation_id="contract-preview-c11-fail",
        session_id="session-1",
        tool_name="proposal.contract_preview",
        tool_call_id="tool-9",
        observation_type="contract_preview",
        summary="Static contract preview found issues: C11_expected_telemetry.",
        structured_payload={
            "passed": False,
            "hypothesis": {
                "passed": False,
                "checks": [
                    {
                        "name": "C11_expected_telemetry",
                        "passed": False,
                        "detail": (
                            "expected_telemetry category 'attribution' is not "
                            "supported"
                        ),
                    }
                ],
            },
        },
    )

    self_check = _self_check_from_previews([observation])

    assert self_check.schema_valid is False
    assert any(
        "C11_expected_telemetry" in code
        for code in self_check.schema_preview_codes
    )
    assert self_check.contract_preview_passed is False
