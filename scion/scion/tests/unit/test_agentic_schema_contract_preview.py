"""Focused tests split from test_agentic_proposal_tools_schema.py."""

from .agentic_schema_test_support import *  # noqa: F401,F403

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
