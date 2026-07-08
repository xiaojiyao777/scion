from __future__ import annotations

from dataclasses import replace
import json

import pytest

from scion.research_guidance import (
    AvoidRule,
    ContinuityRequirement,
    EvidenceRequirement,
    GuidanceBlock,
    GuidanceContext,
    MeasurementGuidanceSummary,
    ProblemResearchGuidanceProvider,
    RequiredMechanism,
    ResearchGuidanceContract,
    ResearchGuidanceValidationError,
    collect_research_guidance_errors,
    expected_research_guidance_rendered_paths,
    launch_research_guidance_payload,
    render_research_guidance_contract,
    research_guidance_contract_from_dict,
    research_guidance_contract_to_dict,
    research_guidance_projection_summary,
    validate_research_guidance_contract,
    validate_research_guidance_rendered_paths,
)


class DummyGuidanceProvider:
    def build_guidance_contract(
        self,
        context: GuidanceContext,
    ) -> ResearchGuidanceContract:
        return _valid_contract(problem_family=context.problem_family)


def test_dummy_provider_contract_validates_and_renders_generic_blocks() -> None:
    provider: ProblemResearchGuidanceProvider = DummyGuidanceProvider()
    contract = provider.build_guidance_contract(
        GuidanceContext(problem_family="dummy_family", campaign_id="campaign_alpha")
    )

    validate_research_guidance_contract(contract)
    rendered = render_research_guidance_contract(contract)

    assert rendered.rendered_paths == expected_research_guidance_rendered_paths(contract)
    assert "## Required mechanisms" in rendered.text
    assert "## Evidence requirements" in rendered.text
    assert "## Avoid rules" in rendered.text
    assert "## Continuity requirements" in rendered.text
    assert "## Guidance blocks" in rendered.text
    assert "foo_activation_probe" in rendered.text
    assert "case_alpha" in rendered.text
    assert "proposal_visibility_only: true" in rendered.text
    assert "decision_features_excluded: true" in rendered.text
    assert "excluded from DecisionFeatures" in rendered.text


def test_rendered_path_coverage_fails_closed_when_projection_is_missing() -> None:
    contract = _valid_contract()
    rendered = render_research_guidance_contract(contract)
    incomplete_paths = tuple(
        path
        for path in rendered.rendered_paths
        if path != "required_mechanisms.foo_activation_probe"
    )

    with pytest.raises(ResearchGuidanceValidationError, match="missing rendered paths"):
        validate_research_guidance_rendered_paths(contract, incomplete_paths)


def test_contract_serializes_round_trips_and_summarizes_manifest_paths() -> None:
    contract = _valid_contract()
    manifest = {
        "problem_family": contract.problem_family,
        "analysis_intent": "Dummy prepared guidance.",
        "acceptance_focus": ["Keep guidance proposal-only."],
        "research_guidance_contract": research_guidance_contract_to_dict(contract),
        "research_focus": {"current_question": contract.current_question},
    }

    parsed = research_guidance_contract_from_dict(
        manifest["research_guidance_contract"]
    )
    summary = research_guidance_projection_summary(
        manifest_path="/tmp/prepared_run_manifest.v1.json",
        manifest=manifest,
        schema_version="test.research_guidance_projection.v1",
    )

    assert parsed == contract
    assert summary["contract_present"] is True
    assert summary["contract_source"] == "typed_manifest"
    assert summary["schema_valid"] is True
    assert summary["expected_rendered_paths"] == list(
        expected_research_guidance_rendered_paths(contract)
    )
    assert summary["rendered_paths"] == summary["expected_rendered_paths"]
    assert summary["missing_rendered_paths"] == []
    assert summary["available"] is True


def test_typed_manifest_flows_into_context_manager_payload(
    tmp_path,
    monkeypatch,
) -> None:
    contract = _valid_contract()
    manifest_path = tmp_path / "prepared_run_manifest.v1.json"
    manifest = {
        "problem_family": contract.problem_family,
        "analysis_intent": "Dummy prepared guidance.",
        "acceptance_focus": ["Keep guidance proposal-only."],
        "research_guidance_contract": research_guidance_contract_to_dict(contract),
        "research_focus": {"current_question": contract.current_question},
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setenv("PREPARED_RUN_MANIFEST", str(manifest_path))

    from scion.proposal.context_manager.manager import _build_launch_research_focus

    payload = _build_launch_research_focus()
    direct_payload = launch_research_guidance_payload(
        manifest_path=manifest_path,
        manifest=manifest,
    )

    assert payload == direct_payload
    assert payload["schema_version"] == "scion.launch_research_guidance_prompt.v1"
    assert payload["contract_source"] == "typed_manifest"
    assert payload["contract_schema_version"] == contract.schema_version
    assert payload["current_question"] == contract.current_question
    assert payload["decision_boundary"] == contract.decision_boundary
    assert payload["required_mechanism_ids"] == ["foo_activation_probe"]
    assert payload["target_intent_required_mechanism_ids"] == []
    assert payload["rendered_paths"] == list(
        expected_research_guidance_rendered_paths(contract)
    )
    assert "foo_activation_probe" in payload["guidance_text"]
    assert "excluded from DecisionFeatures" in payload["guidance_text"]

    from scion.proposal.engine.hypothesis_prompts import (
        _target_intent_launch_focus_required_mechanism_lines,
    )

    guard_lines = _target_intent_launch_focus_required_mechanism_lines(
        {"launch_research_focus": payload}
    )
    assert any("foo_activation_probe" in line for line in guard_lines)
    assert any(contract.current_question in line for line in guard_lines)


def test_context_only_required_mechanism_renders_without_hard_launch_binding(
    tmp_path,
) -> None:
    base_contract = _valid_contract()
    mechanism = base_contract.required_mechanisms[0]
    contract = replace(
        base_contract,
        required_mechanisms=(
            replace(
                mechanism,
                hypothesis_mechanism_binding="context_only",
            ),
        ),
    )
    manifest = {
        "problem_family": contract.problem_family,
        "analysis_intent": "Dummy prepared guidance.",
        "acceptance_focus": ["Keep guidance proposal-only."],
        "research_guidance_contract": research_guidance_contract_to_dict(contract),
    }

    payload = launch_research_guidance_payload(
        manifest_path=tmp_path / "prepared_run_manifest.v1.json",
        manifest=manifest,
    )

    assert payload["required_mechanism_ids"] == []
    assert payload["target_intent_required_mechanism_ids"] == []
    assert "foo_activation_probe" in payload["guidance_text"]
    assert "hypothesis_mechanism_binding=context_only" in payload["guidance_text"]
    assert "required_mechanisms.foo_activation_probe" in payload["rendered_paths"]
    assert payload["expected_rendered_paths"] == list(
        expected_research_guidance_rendered_paths(contract)
    )

    from scion.proposal.engine.hypothesis_prompts import (
        _target_intent_launch_focus_required_mechanism_lines,
    )

    guard_lines = _target_intent_launch_focus_required_mechanism_lines(
        {"launch_research_focus": payload}
    )
    assert guard_lines == []


def test_target_intent_required_mechanism_projects_without_formal_required_binding(
    tmp_path,
) -> None:
    base_contract = _valid_contract()
    mechanism = base_contract.required_mechanisms[0]
    contract = replace(
        base_contract,
        required_mechanisms=(
            replace(
                mechanism,
                hypothesis_mechanism_binding="target_intent_required",
            ),
        ),
    )
    manifest = {
        "problem_family": contract.problem_family,
        "analysis_intent": "Dummy target-intent prepared guidance.",
        "acceptance_focus": ["Keep formal required-mechanism guard unconfigured."],
        "research_guidance_contract": research_guidance_contract_to_dict(contract),
    }

    payload = launch_research_guidance_payload(
        manifest_path=tmp_path / "prepared_run_manifest.v1.json",
        manifest=manifest,
    )

    assert payload["required_mechanism_ids"] == []
    assert payload["target_intent_required_mechanism_ids"] == [
        "foo_activation_probe"
    ]
    assert "hypothesis_mechanism_binding=target_intent_required" in (
        payload["guidance_text"]
    )
    assert "required_mechanisms.foo_activation_probe" in payload["rendered_paths"]

    from scion.proposal.engine.hypothesis_prompts import (
        _target_intent_launch_focus_required_mechanism_lines,
    )

    guard_lines = _target_intent_launch_focus_required_mechanism_lines(
        {"launch_research_focus": payload}
    )
    assert any("target_intent_required_mechanism_ids" in line for line in guard_lines)
    assert any("foo_activation_probe" in line for line in guard_lines)


def test_legacy_manifest_projects_successor_focus_metadata(tmp_path) -> None:
    manifest = {
        "problem_family": "dummy_family",
        "analysis_intent": "Legacy successor focus.",
        "research_focus": {
            "schema_version": "legacy-focus.v1",
            "target_intent_required_mechanism_ids": ["target_probe"],
            "reviewed_mechanism_ids": ["reviewed_probe"],
            "suppressed_mechanism_ids": ["suppressed_probe"],
            "successor_opportunity_families": ["successor_family"],
            "default_avoid_directions": ["acceptance variants"],
            "next_required_direction": "Choose a successor.",
            "material_difference_requirement": {
                "schema_version": "material_difference_requirement.v1",
                "record_type": "material_difference_requirement",
                "record_id": "material_difference_requirement:legacy-test",
                "required": True,
                "required_for": "clean_fork_new_branch",
            },
        },
    }

    payload = launch_research_guidance_payload(
        manifest_path=tmp_path / "prepared_run_manifest.v1.json",
        manifest=manifest,
    )

    assert payload["required_mechanism_ids"] == []
    assert payload["target_intent_required_mechanism_ids"] == ["target_probe"]
    assert payload["reviewed_mechanism_ids"] == ["reviewed_probe"]
    assert payload["suppressed_mechanism_ids"] == ["suppressed_probe"]
    assert payload["successor_opportunity_families"] == ["successor_family"]
    assert payload["default_avoid_directions"] == ["acceptance variants"]
    assert payload["next_required_direction"] == "Choose a successor."
    assert payload["material_difference_requirement"]["record_id"] == (
        "material_difference_requirement:legacy-test"
    )
    assert "acceptance variants" in payload["guidance_text"]
    assert "hypothesis_mechanism_binding=target_intent_required" in (
        payload["guidance_text"]
    )


@pytest.mark.parametrize(
    ("case_name", "expected_error"),
    [
        (
            "missing_visibility_marker",
            "proposal_visibility_only must be true",
        ),
        (
            "duplicate_block_id",
            "duplicate guidance block id",
        ),
        (
            "empty_required_mechanism_id",
            "mechanism_id must be a non-empty string",
        ),
        (
            "unsupported_visibility_policy",
            "visibility_policy unsupported",
        ),
        (
            "unsupported_hypothesis_mechanism_binding",
            "hypothesis_mechanism_binding unsupported",
        ),
    ],
)
def test_invalid_contracts_fail_closed(
    case_name: str,
    expected_error: str,
) -> None:
    contract = _invalid_contract(case_name)
    errors = collect_research_guidance_errors(contract)

    assert any(expected_error in error for error in errors)
    with pytest.raises(ResearchGuidanceValidationError, match=expected_error):
        validate_research_guidance_contract(contract)
    with pytest.raises(ResearchGuidanceValidationError, match=expected_error):
        render_research_guidance_contract(contract)


def _invalid_contract(case_name: str) -> ResearchGuidanceContract:
    contract = _valid_contract()
    if case_name == "missing_visibility_marker":
        return replace(contract, proposal_visibility_only=None)
    if case_name == "duplicate_block_id":
        block = contract.guidance_blocks[0]
        return replace(
            contract,
            guidance_blocks=(
                block,
                replace(block, title="Repeated dummy block"),
            ),
        )
    if case_name == "empty_required_mechanism_id":
        return replace(
            contract,
            required_mechanisms=(
                replace(
                    contract.required_mechanisms[0],
                    mechanism_id=" ",
                ),
            ),
        )
    if case_name == "unsupported_visibility_policy":
        return replace(contract, visibility_policy="decision_visible")
    if case_name == "unsupported_hypothesis_mechanism_binding":
        return replace(
            contract,
            required_mechanisms=(
                replace(
                    contract.required_mechanisms[0],
                    hypothesis_mechanism_binding="decision_visible",
                ),
            ),
        )
    raise AssertionError(f"unknown invalid contract case: {case_name}")


def _valid_contract(problem_family: str = "dummy_family") -> ResearchGuidanceContract:
    return ResearchGuidanceContract(
        schema_version="research-guidance-v1",
        problem_family=problem_family,
        current_question="Which dummy activation path should be probed next?",
        required_mechanisms=(
            RequiredMechanism(
                mechanism_id="foo_activation_probe",
                category="activation_probe",
                description="Observe whether the named probe becomes active.",
                required_observations=("probe_active", "effect_observed"),
            ),
        ),
        evidence_requirements=(
            EvidenceRequirement(
                requirement_id="foo_activation_evidence",
                category="activation_evidence",
                description="Pair activation with effect evidence.",
                mechanism_ids=("foo_activation_probe",),
                protected_items=("case_alpha",),
                required_fields=("activation_status", "effect_delta"),
            ),
        ),
        avoid_rules=(
            AvoidRule(
                rule_id="avoid_unchanged_repeat",
                category="repeat_guard",
                description="Do not repeat an unchanged probe after rejected evidence.",
                applies_to=("foo_activation_probe",),
            ),
        ),
        continuity_requirements=(
            ContinuityRequirement(
                requirement_id="continue_probe_lineage",
                category="lineage",
                description="Carry forward the last probe lesson before proposing.",
                related_ids=("foo_activation_probe", "case_alpha"),
            ),
        ),
        guidance_blocks=(
            GuidanceBlock(
                block_id="dummy_focus_block",
                category="proposal_focus",
                title="Dummy focus",
                lines=(
                    "Prefer a measurable activation path.",
                    "Tie observations to case_alpha.",
                ),
            ),
        ),
        measurement_summary=MeasurementGuidanceSummary(
            summary_id="dummy_measurement_summary",
            summary="Use paired dummy deltas only as proposal guidance.",
            metric_names=("dummy_delta",),
            limitations=("proposal-only summary",),
        ),
        decision_boundary="Proposal guidance only; excluded from DecisionFeatures.",
    )
